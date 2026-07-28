#!/usr/bin/env python3
"""
Détection d'obstacles YOLO + profondeur — ProtoVA.
Brique de perception pour le freinage d'urgence (AEB) et, plus tard, l'émission
d'un DENM V2V.

La voiture (Jetson) publie sa caméra Orbbec (couleur JPEG + profondeur). Ce nœud,
côté PC, reçoit ces flux, détecte les objets avec YOLOv8n (personne, chaise...),
estime leur DISTANCE via l'image de profondeur, et lève un signal de FREINAGE si
un obstacle prioritaire (par défaut : personne) est trop proche.

Publie :
  /obstacle/detections (String JSON) : [{classe, conf, distance_m, box}]
  /obstacle/brake      (Bool)        : True = freinage d'urgence requis

L'approche : YOLO donne le "quoi/où", la profondeur donne "à quelle distance".
Sans profondeur (flux absent), repli sur la taille de la boîte.

Params : color_topic, depth_topic, model, conf, brake_dist, targets, rate, show
"""
import json

import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data, QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import String, Bool
from ultralytics import YOLO


# ---------- fonctions cœur (pures, testables sans ROS) ----------
def depth_to_meters(msg):
    """Image de profondeur ROS -> tableau numpy en mètres (ou None)."""
    if msg is None:
        return None
    if msg.encoding in ('16UC1', 'mono16'):
        arr = np.frombuffer(bytes(msg.data), np.uint16).reshape(msg.height, msg.width)
        return arr.astype(np.float32) / 1000.0      # mm -> m
    if msg.encoding == '32FC1':
        return np.frombuffer(bytes(msg.data), np.float32).reshape(msg.height, msg.width)
    return None


def sample_distance(depth_m, box, color_shape, pct=20):
    """Distance (m) à l'obstacle = son point le PLUS PROCHE dans la boîte.

    Une boîte YOLO contient l'objet (avant-plan) ET de l'arrière-plan. La médiane
    mélange les deux → distance fausse quand l'objet occupe moins de la moitié de la
    boîte (ex. personne très proche dont la boîte englobe la pièce derrière). Pour un
    obstacle, ce qui compte est sa surface AVANT : on prend donc un percentile BAS
    (20ᵉ) des profondeurs valides = le cluster le plus proche, robuste au bruit.

    On restreint à la région centrale (60 %) pour écarter l'arrière-plan des bords, et
    on ignore les pixels invalides (0, ex. cheveux foncés absorbant l'IR). Coordonnées
    mises à l'échelle de la profondeur (rapport = 1 si alignée sur la couleur).
    """
    if depth_m is None:
        return None
    ch, cw = color_shape[:2]
    dh, dw = depth_m.shape
    sx, sy = dw / cw, dh / ch
    x1, y1, x2, y2 = box
    bw, bh = x2 - x1, y2 - y1
    rx1, rx2 = int((x1 + 0.2 * bw) * sx), int((x2 - 0.2 * bw) * sx)
    ry1, ry2 = int((y1 + 0.2 * bh) * sy), int((y2 - 0.2 * bh) * sy)
    rx1, rx2 = max(0, rx1), min(dw, max(rx1 + 1, rx2))
    ry1, ry2 = max(0, ry1), min(dh, max(ry1 + 1, ry2))
    v = depth_m[ry1:ry2, rx1:rx2]
    v = v[(v > 0.15) & (v < 20.0)]       # ignore invalides et aberrations
    if v.size < 20:                       # trop peu de points fiables
        return None
    return round(float(np.percentile(v, pct)), 2)


def forward_obstacle(depth_m, band=(0.35, 0.62), cols=(0.30, 0.70), pct=10,
                     dmin=0.15, dmax=20.0, min_pts=40):
    """Distance (m) au plus proche obstacle dans un COULOIR FRONTAL central, à partir
    de la profondeur BRUTE (indépendamment de YOLO). Détecte donc TOUT — murs et
    objets inconnus que YOLO n'a pas appris. On échantillonne une bande horizontale
    centrale (évite le sol proche en bas et le plafond en haut) et on prend un
    percentile bas = la surface la plus proche, robuste au bruit.
    C'est ce qui empêche de rentrer dans les murs (là où YOLO seul échoue)."""
    if depth_m is None:
        return None
    h, w = depth_m.shape
    r1, r2 = int(band[0] * h), int(band[1] * h)
    c1, c2 = int(cols[0] * w), int(cols[1] * w)
    v = depth_m[r1:r2, c1:c2]
    v = v[(v > dmin) & (v < dmax) & np.isfinite(v)]
    if v.size < min_pts:
        return None
    return round(float(np.percentile(v, pct)), 2)


def pick_device(pref='auto'):
    """Choisit le peripherique d'inference : 'auto' -> GPU CUDA si disponible.
    Sur la Jetson (GPU Orin) l'inference passe de ~344 ms a ~30 ms par image."""
    if pref != 'auto':
        return pref
    try:
        import torch
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    except ImportError:
        return 'cpu'


def run_detection(model, bgr, depth_m, targets, conf, brake_dist, brake_on_any=True,
                  detect_walls=True, wall_band=(0.35, 0.62), wall_cols=(0.30, 0.70),
                  wall_pct=10, device='cpu'):
    """Retourne (liste_detections, freinage_bool, image_annotée).

    Freinage : par défaut (`brake_on_any=True`) TOUT objet détecté à moins de
    `brake_dist` déclenche le freinage, quelle que soit sa classe. Un objet loin ne
    déclenche rien. Si `brake_on_any=False`, seules les classes de `targets` comptent.

    L'image annotée affiche pour chaque objet : classe + DISTANCE (m) + confiance,
    avec un code couleur : ROUGE = proche → freine ; VERT = loin → OK.
    """
    res = model(bgr, verbose=False, conf=conf, device=device)[0]
    h, w = bgr.shape[:2]
    area = float(h * w)
    dets, brake = [], False
    img = bgr.copy()
    for b in res.boxes:
        cls = res.names[int(b.cls)]
        box = [int(v) for v in b.xyxy[0].tolist()]
        dist = sample_distance(depth_m, box, bgr.shape)
        conf_v = round(float(b.conf), 2)
        area_ratio = ((box[2] - box[0]) * (box[3] - box[1])) / area
        dets.append({'class': cls, 'conf': conf_v, 'distance_m': dist, 'box': box})

        compte = brake_on_any or (cls in targets)      # cet objet compte-t-il pour le frein ?
        proche = (dist is not None and dist < brake_dist) \
            or (dist is None and area_ratio > 0.15)     # repli sans profondeur : grosse boîte = proche
        close = compte and proche
        if close:
            brake = True

        # --- dessin : boîte + label "classe distance (conf)" ---
        color = (0, 0, 255) if close else (0, 200, 0)   # rouge = freine, vert = OK
        x1, y1, x2, y2 = box
        dtxt = f"{dist:.1f}m" if dist is not None else "?m"
        label = f"{cls} {dtxt} ({conf_v:.2f})"
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        yt = max(y1, th + 9)
        cv2.rectangle(img, (x1, yt - th - 9), (x1 + tw + 6, yt), color, -1)
        cv2.putText(img, label, (x1 + 3, yt - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # --- obstacle GÉNÉRIQUE par profondeur (murs + objets inconnus, hors YOLO) ---
    # Complète YOLO : détecte toute surface proche devant, même non reconnue par YOLO.
    if detect_walls:
        d_fwd = forward_obstacle(depth_m, wall_band, wall_cols, wall_pct)
        if d_fwd is not None:
            fb = [int(w * wall_cols[0]), int(h * wall_band[0]),
                  int(w * wall_cols[1]), int(h * wall_band[1])]
            # on ne l'ajoute que s'il est le plus proche (obstacle que YOLO a manqué)
            plus_proche = min([d['distance_m'] for d in dets
                               if d['distance_m'] is not None], default=None)
            if plus_proche is None or d_fwd <= plus_proche + 0.05:
                dets.append({'class': 'obstacle', 'conf': 1.0,
                             'distance_m': d_fwd, 'box': fb})
            close = d_fwd < brake_dist
            if close:
                brake = True
            col = (0, 0, 255) if close else (0, 180, 255)
            cv2.rectangle(img, (fb[0], fb[1]), (fb[2], fb[3]), col, 2)
            cv2.putText(img, f"obstacle {d_fwd}m", (fb[0], max(fb[1] - 8, 14)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)

    return dets, brake, img


# ---------- nœud ROS ----------
class YoloDetect(Node):
    def __init__(self):
        super().__init__('yolo_detect')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.color_topic = g('color_topic', '/camera/color/image_raw/compressed')
        self.depth_topic = g('depth_topic', '/camera/depth/image_raw')
        model_path = g('model', 'yolov8n.pt')
        self.conf = float(g('conf', 0.35))
        self.brake_dist = float(g('brake_dist', 2.0))
        self.targets = list(g('targets', ['person']))
        self.brake_on_any = bool(g('brake_on_any', True))   # True = freiner sur TOUT objet proche
        self.show = bool(g('show', False))
        rate = float(g('rate', 5.0))
        # detection d'obstacle GENERIQUE par profondeur (murs/objets inconnus, hors YOLO)
        self.detect_walls = bool(g('detect_walls', True))
        self.wall_band = (float(g('wall_band_top', 0.35)), float(g('wall_band_bot', 0.62)))
        self.wall_cols = (float(g('wall_cols_left', 0.30)), float(g('wall_cols_right', 0.70)))
        self.wall_pct = int(g('wall_pct', 10))

        self.device = pick_device(g('device', 'auto'))
        self.color_msg = None
        self.depth_msg = None
        self.model = YOLO(model_path)
        try:
            self.model.to(self.device)
        except Exception:
            pass
        self.bgr = None
        self.depth = None
        self.pub_det = self.create_publisher(String, '/obstacle/detections', 10)
        self.pub_brake = self.create_publisher(Bool, '/obstacle/brake', 10)
        # image annotee (JPEG compresse) : permet de superviser la detection depuis
        # une autre machine (ex. YOLO sur la Jetson, visualisation sur le PC) sans
        # transporter le flux brut. Desactivable avec -p publish_annotated:=false.
        self.publish_annotated = bool(g('publish_annotated', True))
        # QoS "sensor data" (best-effort) OBLIGATOIRE pour un flux d'images sur WiFi :
        # en RELIABLE, DDS retransmet et le flux se bloque -> le PC ne recoit rien.
        # C'est la meme QoS que les topics de la camera (qui, eux, traversent bien).
        # depth=1 : on ne garde QUE la derniere image. Sinon les images s'empilent
        # sur un WiFi lent et la latence grimpe a plusieurs secondes.
        qos_img = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                             history=HistoryPolicy.KEEP_LAST, depth=1)
        self.pub_img = self.create_publisher(CompressedImage,
                                             '/obstacle/annotated/compressed', qos_img)
        # largeur de l'image publiee (reduite = moins de donnees = moins de latence)
        self.annot_width = int(g('annot_width', 960))
        self.annot_quality = int(g('annot_quality', 80))
        # depth=1 : on ne traite QUE l'image la plus recente. En depth=5, la camera
        # (15 Hz) remplit la file plus vite qu'on ne traite (10 Hz) -> retard accumule.
        qos_in = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                            history=HistoryPolicy.KEEP_LAST, depth=1)
        self.create_subscription(CompressedImage, self.color_topic, self.cb_color, qos_in)
        self.create_subscription(Image, self.depth_topic, self.cb_depth, qos_in)
        self.create_timer(1.0 / rate, self.tick)
        self.get_logger().info(
            f"yolo_detect prêt : couleur={self.color_topic}, profondeur={self.depth_topic}, "
            f"cibles={self.targets}, frein<{self.brake_dist} m, device={self.device}")

    def cb_color(self, msg):
        # callback ULTRA-LEGER : on stocke le message, le decodage se fait dans tick()
        # (1 fois par cycle, sur la DERNIERE image seulement). Decoder ici a 15 Hz
        # saturait le CPU -> les callbacks prenaient du retard -> latence de plusieurs s.
        self.color_msg = msg

    def cb_depth(self, msg):
        self.depth_msg = msg

    def tick(self):
        if self.color_msg is None:
            return
        cmsg = self.color_msg
        arr = np.frombuffer(bytes(cmsg.data), np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return
        self.bgr = img
        self.depth = depth_to_meters(self.depth_msg) if self.depth_msg is not None else None
        dets, brake, annotated = run_detection(
            self.model, self.bgr, self.depth, self.targets, self.conf,
            self.brake_dist, self.brake_on_any,
            self.detect_walls, self.wall_band, self.wall_cols, self.wall_pct,
            self.device)
        self.pub_det.publish(String(data=json.dumps(dets)))
        self.pub_brake.publish(Bool(data=brake))
        if self.publish_annotated:
            out = annotated
            if self.annot_width and annotated.shape[1] > self.annot_width:
                sc = self.annot_width / annotated.shape[1]
                out = cv2.resize(annotated, (self.annot_width,
                                             int(annotated.shape[0] * sc)))
            ok, jpg = cv2.imencode('.jpg', out,
                                   [cv2.IMWRITE_JPEG_QUALITY, self.annot_quality])
            if ok:
                m = CompressedImage()
                m.header.stamp = cmsg.header.stamp   # heure de capture -> latence mesurable
                m.format = 'jpeg'
                m.data = jpg.tobytes()
                self.pub_img.publish(m)
        proches = [f"{d['class']} {d['distance_m']}m" for d in dets
                   if d['distance_m'] is not None and d['distance_m'] < self.brake_dist
                   and (self.brake_on_any or d['class'] in self.targets)]
        if brake:
            self.get_logger().warning(f"FREINAGE ! obstacle(s) proche(s) : {proches}")
        elif dets:
            self.get_logger().info(f"{len(dets)} objet(s) détecté(s), rien de proche",
                                   throttle_duration_sec=2.0)
        if self.show:
            cv2.putText(annotated, "FREINAGE" if brake else "", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            cv2.imshow('ProtoVA - detection YOLO', annotated)
            cv2.waitKey(1)

    def destroy_node(self):
        if self.show:
            cv2.destroyAllWindows()
        super().destroy_node()


def main():
    rclpy.init()
    node = YoloDetect()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
