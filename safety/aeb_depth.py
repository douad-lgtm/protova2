#!/usr/bin/env python3
"""
aeb_depth.py — Freinage d'urgence RÉFLEXE, exécuté LOCALEMENT sur la Jetson.

Contrairement à l'AEB basé sur YOLO (caméra -> PC -> détections -> retour Jetson,
~5 Hz + latence WiFi), ce nœud lit DIRECTEMENT l'image de profondeur de la caméra sur
la Jetson et réagit à CHAQUE image (~15 Hz, ~66 ms). Aucun passage par le PC ni par
YOLO -> réaction quasi-instantanée = vrai freinage d'urgence.

Il mesure le plus proche obstacle dans un couloir frontal (profondeur brute -> détecte
TOUT, murs inclus) et publie immédiatement un ARRÊT sur /cmd_vel_aeb (priorité 255 dans
twist_mux, donc il reprend la main sur le conducteur). Complète l'AEB YOLO (qui garde
la classification piéton -> DENM).

Params : depth_topic, driver_topic, d_stop (arrêt franc), d_slow (début ralentissement),
         band_top/bot + cols_left/right (couloir frontal), pct, dmin.
"""
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Float32


def depth_to_m(msg):
    if msg.encoding in ('16UC1', 'mono16'):
        a = np.frombuffer(bytes(msg.data), np.uint16).reshape(msg.height, msg.width)
        return a.astype(np.float32) / 1000.0
    if msg.encoding == '32FC1':
        return np.frombuffer(bytes(msg.data), np.float32).reshape(msg.height, msg.width)
    return None


class AebDepth(Node):
    def __init__(self):
        super().__init__('aeb_depth')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.depth_topic = g('depth_topic', '/camera/depth/image_raw')
        self.driver_topic = g('driver_topic', '/cmd_vel_G29')
        self.d_stop = float(g('d_stop', 0.6))     # arrêt franc en dessous
        self.d_slow = float(g('d_slow', 1.2))     # commence à ralentir
        self.band = (float(g('band_top', 0.35)), float(g('band_bot', 0.62)))
        self.cols = (float(g('cols_left', 0.30)), float(g('cols_right', 0.70)))
        self.pct = int(g('pct', 10))
        self.dmin = float(g('dmin', 0.15))
        # frein ACTIF optionnel : brève marche arrière pour vaincre l'inertie (0 = coast/roue libre)
        self.brake_reverse = float(g('brake_reverse', 0.0))   # amplitude (ex. 0.3) ; 0 = désactivé
        self.brake_time = float(g('brake_time', 0.2))         # durée de l'impulsion (s)
        self._stop_start = None
        self.driver = Twist()
        self.pub = self.create_publisher(Twist, '/cmd_vel_aeb', 10)
        self.pub_b = self.create_publisher(Bool, '/obstacle/brake', 10)
        self.pub_lvl = self.create_publisher(Float32, '/obstacle/brake_level', 10)
        self.create_subscription(Image, self.depth_topic, self.cb_depth, qos_profile_sensor_data)
        self.create_subscription(Twist, self.driver_topic, self.cb_drv, 10)
        self.get_logger().info(
            f"AEB reflexe (profondeur, LOCAL Jetson) pret : {self.depth_topic}, "
            f"arret<{self.d_stop} m, ralentir<{self.d_slow} m")

    def cb_drv(self, m):
        self.driver = m

    def cb_depth(self, msg):
        d = depth_to_m(msg)
        if d is None:
            return
        h, w = d.shape
        v = d[int(self.band[0] * h):int(self.band[1] * h),
              int(self.cols[0] * w):int(self.cols[1] * w)]
        v = v[(v > self.dmin) & np.isfinite(v)]
        if v.size < 40:                      # pas assez de points fiables
            self.pub_b.publish(Bool(data=False))
            self.get_logger().info(
                f"profondeur : couloir vide / hors portee (points valides={v.size}) "
                f"[shape={h}x{w}]", throttle_duration_sec=1.0)
            return
        dist = float(np.percentile(v, self.pct))
        self.get_logger().info(f"obstacle le plus proche : {dist:.2f} m",
                               throttle_duration_sec=1.0)
        # facteur de vitesse : arrêt FRANC sous d_stop (réponse rapide)
        if dist <= self.d_stop:
            f = 0.0
        elif dist >= self.d_slow:
            f = 1.0
        else:
            f = (dist - self.d_stop) / (self.d_slow - self.d_stop)

        self.pub_lvl.publish(Float32(data=float(1.0 - f)))
        if f >= 0.999:                       # rien de proche -> on laisse conduire
            self._stop_start = None
            self.pub_b.publish(Bool(data=False))
            return
        t = Twist()
        vx = self.driver.linear.x
        if f <= 0.01:
            # arrêt franc : impulsion de FREIN ACTIF (marche arrière brève) si activé,
            # sinon point mort (roue libre). L'impulsion vainc l'inertie -> arrêt rapide.
            now = self.get_clock().now()
            if self._stop_start is None:
                self._stop_start = now
            elapsed = (now - self._stop_start).nanoseconds * 1e-9
            if self.brake_reverse > 0.0 and elapsed < self.brake_time:
                t.linear.x = -self.brake_reverse         # frein actif (recul bref)
            else:
                t.linear.x = 0.0                         # maintien à l'arrêt
        else:
            self._stop_start = None
            t.linear.x = vx * f if vx > 0.0 else vx      # ralentissement proportionnel
        t.angular.z = self.driver.angular.z              # garde la direction du conducteur
        self.pub.publish(t)
        self.pub_b.publish(Bool(data=True))
        if f <= 0.01:
            self.get_logger().warn(f"*** AEB URGENCE : ARRET — obstacle a {dist:.2f} m ***",
                                   throttle_duration_sec=0.4)


def main():
    rclpy.init()
    node = AebDepth()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
