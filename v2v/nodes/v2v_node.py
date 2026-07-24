#!/usr/bin/env python3
"""
Node ROS2 V2V (Vanetza) — ProtoVA.
Lance socktap (Vanetza, CAM ETSI sur WiFi UDP), parse les CAM recus, publie les
vehicules voisins + alerte de proximite. Gere une POSITION DYNAMIQUE : la position
de CE vehicule (topic /v2v/my_gps) est poussee a socktap par UDP -> elle part dans
le CAM emis.

socktap gere CAM (ca) ET DENM (den). Quand un obstacle est detecte
(topic /obstacle/brake=True, publie par yolo_detect.py), ce node emet un DENM
(alerte d'evenement) que les autres vehicules recoivent.

Topics:
  publie  /v2v/remote_vehicles (String JSON) : vehicules detectes par CAM
  publie  /v2v/alert           (String)      : alerte si vehicule proche (CAM)
  publie  /v2v/denm            (String JSON) : DENM recu (from_id, cause, subcause,
                                 lat, lon, distance_m)
  abonne  /v2v/my_gps          (Float64MultiArray [lat, lon] ou
                                 [lat, lon, cap_deg, vitesse_mps]) : etat de CE vehicule
                                 (cap + vitesse -> partent dans le CAM emis)
  abonne  /obstacle/brake      (Bool) : True -> emet un DENM (1 Hz tant que True)

Params:
  interface, station_id, my_lat, my_lon (position initiale), alert_dist,
  socktap_bin, positioning (static|udp), pos_port (UDP position), denm_port (UDP DENM)
"""
import json
import math
import socket
import subprocess
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float64MultiArray, Float64, Bool


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


class V2VNode(Node):
    def __init__(self):
        super().__init__('v2v_node')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.iface = g('interface', 'wlP1p1s0')
        self.station_id = int(g('station_id', 2))
        self.my_lat = float(g('my_lat', 48.7668))
        self.my_lon = float(g('my_lon', 11.4320))
        self.my_heading = 0.0   # cap (deg Nord vrai), maj par /v2v/my_gps
        self.my_speed = 0.0     # vitesse (m/s), maj par /v2v/my_gps
        self.alert_dist = float(g('alert_dist', 10.0))
        self.socktap = g('socktap_bin', '/home/protova2/vanetza/build/bin/socktap')
        self.positioning = g('positioning', 'udp')   # 'udp'=odometrie, 'lidar'=distance lidar reelle
        self.pos_port = int(g('pos_port', 9001))
        # 'lidar' : le voisin (PC) est a cette position de reference ; on se declare
        # a la distance MESUREE PAR LE LIDAR de ce point -> le recepteur calcule la vraie distance.
        self.ref_lat = float(g('ref_lat', self.my_lat))
        self.ref_lon = float(g('ref_lon', self.my_lon))
        self.denm_port = int(g('denm_port', 9002))    # port declencheur DENM de socktap

        self.pub_veh = self.create_publisher(String, '/v2v/remote_vehicles', 10)
        self.pub_alert = self.create_publisher(String, '/v2v/alert', 10)
        self.pub_denm = self.create_publisher(String, '/v2v/denm', 10)

        # socktap gere CAM (ca) ET DENM (den) : emet et recoit les deux
        cmd = [self.socktap, '-l', 'udp', '-i', self.iface, '-a', 'ca', 'den',
               '--print-rx-cam', '--print-rx-denm', '--security', 'none',
               '--station-id', str(self.station_id),
               '--denm-trigger-port', str(self.denm_port)]
        if self.positioning in ('udp', 'lidar'):
            cmd += ['-p', 'udp', '--pos-port', str(self.pos_port)]
            # socket pour pousser notre position a socktap
            self.tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            if self.positioning == 'udp':
                self.create_subscription(Float64MultiArray, '/v2v/my_gps', self.cb_gps, 10)
            else:  # 'lidar' : distance reelle mesuree par le lidar
                self.create_subscription(Float64, '/v2v/neighbor_dist', self.cb_neighbor, 10)
            self.create_timer(0.2, self.push_position)   # 5 Hz
        else:
            cmd += ['--latitude', str(self.my_lat), '--longitude', str(self.my_lon)]

        # DENM emis SEULEMENT sur un vrai danger CONFIRME (evite les fausses alertes
        # sur le mobilier) : une classe dangereuse (def pieton), proche, DANS la
        # trajectoire, et PERSISTANTE sur plusieurs images.
        self.denm_classes = list(g('denm_classes', ['person']))
        self.denm_dist = float(g('denm_dist', 5.0))       # danger si distance < 5 m
        self.denm_persist = int(g('denm_persist', 3))     # confirme sur N images consecutives
        self.denm_corridor = float(g('denm_corridor', 0.6))
        self.image_width = float(g('image_width', 1280.0))
        self.denm_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._hazard_count = 0
        self._hazard = None                               # (classe, distance) du danger confirme
        self.create_subscription(String, '/obstacle/detections', self.cb_det_denm, 10)
        self.create_timer(1.0, self.denm_tick)            # 1 DENM/s tant que danger confirme

        self.get_logger().info('socktap: ' + ' '.join(cmd))
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
        self.cur = {}
        self.mode = None
        threading.Thread(target=self._reader, daemon=True).start()
        self.get_logger().info(
            f"V2V node pret (id={self.station_id}, positioning={self.positioning}, "
            f"pos init=({self.my_lat},{self.my_lon}), alerte<{self.alert_dist}m)")

    # ---- position de CE vehicule -> socktap (CAM emis) ----
    def cb_gps(self, msg):
        d = msg.data
        if len(d) >= 2:
            self.my_lat, self.my_lon = float(d[0]), float(d[1])
        if len(d) >= 4:
            self.my_heading, self.my_speed = float(d[2]), float(d[3])

    def cb_neighbor(self, msg):
        # distance lidar REELLE au voisin -> on se place a D metres au nord de la
        # reference (position du voisin) : le recepteur calcule alors exactement D.
        d = float(msg.data)
        self.my_lat = self.ref_lat + d / 111320.0
        self.my_lon = self.ref_lon
        self.my_heading = 180.0   # oriente vers le voisin
        self.my_speed = 0.0

    def push_position(self):
        if self.positioning in ('udp', 'lidar'):
            try:
                # "lat,lon,cap,vitesse" -> socktap remplit position + cap + vitesse du CAM
                self.tx.sendto(
                    f"{self.my_lat:.7f},{self.my_lon:.7f},"
                    f"{self.my_heading:.1f},{self.my_speed:.2f}".encode(),
                    ('127.0.0.1', self.pos_port))
            except OSError:
                pass

    # ---- messages recus (CAM + DENM) -> ROS2 ----
    def _reader(self):
        for line in self.proc.stdout:
            line = line.strip()
            try:
                if line.startswith('Received CAM'):
                    self.mode = 'cam'; self.cur = {}
                elif line.startswith('Received DENM'):
                    self.mode = 'denm'; self.cur = {}
                elif line.startswith('Station ID:'):
                    self.cur['id'] = int(line.split(':')[1])
                elif line.startswith('Latitude:'):
                    self.cur['lat'] = int(line.split(':')[1]) * 1e-7
                elif line.startswith('Longitude:'):
                    self.cur['lon'] = int(line.split(':')[1]) * 1e-7
                    if self.mode == 'denm' and {'id', 'cause', 'lat', 'lon'} <= self.cur.keys() \
                            and self.cur['id'] != self.station_id:
                        self._handle_denm(dict(self.cur)); self.cur = {}
                elif self.mode == 'cam' and line.startswith('Heading'):
                    self.cur['heading'] = int(line.split(':')[1].split('[')[0]) * 0.1
                elif self.mode == 'cam' and line.startswith('Speed'):
                    self.cur['speed'] = int(line.split(':')[1].split('[')[0]) * 0.01
                    if {'id', 'lat', 'lon'} <= self.cur.keys() and self.cur['id'] != self.station_id:
                        self._handle_cam(dict(self.cur)); self.cur = {}
                elif self.mode == 'denm' and line.startswith('Cause:'):
                    self.cur['cause'] = int(line.split(':')[1])
                elif self.mode == 'denm' and line.startswith('SubCause:'):
                    self.cur['subcause'] = int(line.split(':')[1])
            except (ValueError, IndexError):
                pass

    def _handle_cam(self, v):
        dist = haversine(self.my_lat, self.my_lon, v['lat'], v['lon'])
        v['distance_m'] = round(dist, 2)
        self.pub_veh.publish(String(data=json.dumps(v)))
        if dist < self.alert_dist:
            msg = (f"ALERTE proximite: vehicule {v['id']} a {dist:.1f} m "
                   f"(pos {v['lat']:.6f},{v['lon']:.6f})")
            self.pub_alert.publish(String(data=msg))
            self.get_logger().warning(msg)
        else:
            self.get_logger().info(f"vehicule {v['id']} a {dist:.1f} m (RAS)",
                                   throttle_duration_sec=2.0)

    def _handle_denm(self, d):
        dist = haversine(self.my_lat, self.my_lon, d['lat'], d['lon'])
        payload = {'from_id': d['id'], 'cause': d.get('cause'),
                   'subcause': d.get('subcause'), 'lat': d['lat'], 'lon': d['lon'],
                   'distance_m': round(dist, 2)}
        self.pub_denm.publish(String(data=json.dumps(payload)))
        self.get_logger().warning(
            f"*** DENM RECU du vehicule {d['id']} : cause {d.get('cause')}/{d.get('subcause')} "
            f"(danger/freinage) a {dist:.1f} m ***")

    # ---- DENM emis SEULEMENT sur un vrai danger confirme ----
    def cb_det_denm(self, msg):
        """Confirme un danger : classe dangereuse (pieton), proche, dans le couloir,
        et vue sur plusieurs images consecutives -> evite les fausses alertes."""
        try:
            dets = json.loads(msg.data)
        except ValueError:
            return
        half = self.image_width / 2.0
        best = None
        for d in dets:
            cls, dist, box = d.get('class'), d.get('distance_m'), d.get('box')
            if cls not in self.denm_classes or dist is None or not box:
                continue
            if dist >= self.denm_dist:                       # trop loin -> pas un danger
                continue
            cx = (box[0] + box[2]) / 2.0
            if abs(cx - half) > self.denm_corridor * half:   # hors trajectoire -> ignore
                continue
            if best is None or dist < best[1]:
                best = (cls, dist)
        if best is not None:
            self._hazard_count = min(self._hazard_count + 1, self.denm_persist)
            self._hazard = best
        else:
            self._hazard_count = 0
            self._hazard = None

    def denm_tick(self):
        if self._hazard is not None and self._hazard_count >= self.denm_persist:
            try:
                self.denm_tx.sendto(b'brake', ('127.0.0.1', self.denm_port))
                cls, dist = self._hazard
                self.get_logger().warning(
                    f"DANGER CONFIRME ({cls} à {dist} m) -> DENM émis aux autres véhicules",
                    throttle_duration_sec=2.0)
            except OSError:
                pass

    def destroy_node(self):
        try:
            self.proc.terminate()
        except Exception:
            pass
        super().destroy_node()


def main():
    rclpy.init()
    node = V2VNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
