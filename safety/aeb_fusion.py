#!/usr/bin/env python3
"""
aeb_fusion.py — Freinage d'urgence par FUSION lidar + caméra profondeur (local Jetson).

Pourquoi la fusion : la caméra ToF (profondeur IR) échoue sur certaines surfaces
(caoutchouc, sombre, absorbant l'IR) -> profondeur invalide. Le LIDAR envoie un laser
qui rebondit sur TOUT -> détection fiable des murs/obstacles dans son plan, 360°.
On combine les deux et on prend la distance de danger = MINIMUM des deux capteurs.
C'est l'approche des vraies voitures (capteurs complémentaires).

  LIDAR (/scan)               -> plus proche obstacle dans le secteur frontal (fiable murs)
  CAMÉRA (/camera/depth...)   -> plus proche obstacle dans le couloir central (complément)
  danger = min(lidar, depth)  -> arrêt franc sur /cmd_vel_aeb (priorité 255)

Params : scan_topic, depth_topic, driver_topic, d_stop, d_slow,
         sector_deg + front_offset_deg (secteur lidar), band/cols (couloir caméra),
         use_depth (activer/désactiver la caméra), brake_reverse/brake_time (frein actif),
         rate.
"""
import math
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan, Image
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, Float32


def depth_to_m(msg):
    if msg.encoding in ('16UC1', 'mono16'):
        a = np.frombuffer(bytes(msg.data), np.uint16).reshape(msg.height, msg.width)
        return a.astype(np.float32) / 1000.0
    if msg.encoding == '32FC1':
        return np.frombuffer(bytes(msg.data), np.float32).reshape(msg.height, msg.width)
    return None


class AebFusion(Node):
    def __init__(self):
        super().__init__('aeb_fusion')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.scan_topic = g('scan_topic', '/scan')
        self.depth_topic = g('depth_topic', '/camera/depth/image_raw')
        self.driver_topic = g('driver_topic', '/cmd_vel_G29')
        self.d_stop = float(g('d_stop', 0.6))
        self.d_slow = float(g('d_slow', 1.2))
        # secteur frontal du lidar
        self.sector = math.radians(float(g('sector_deg', 45.0)))
        self.front = math.radians(float(g('front_offset_deg', 0.0)))
        self.rmin = float(g('range_min', 0.06))
        self.rmax = float(g('range_max', 12.0))
        # couloir de la caméra
        self.use_depth = bool(g('use_depth', True))
        self.band = (float(g('band_top', 0.35)), float(g('band_bot', 0.62)))
        self.cols = (float(g('cols_left', 0.30)), float(g('cols_right', 0.70)))
        self.pct = int(g('pct', 10))
        self.dmin = float(g('dmin', 0.15))
        # frein actif optionnel
        self.brake_reverse = float(g('brake_reverse', 0.0))
        self.brake_time = float(g('brake_time', 0.2))
        self.rate = float(g('rate', 30.0))

        self.driver = Twist()
        self.d_lidar = None
        self.d_depth = None
        self.t_lidar = None
        self.t_depth = None
        self._stop_start = None

        self.pub = self.create_publisher(Twist, '/cmd_vel_aeb', 10)
        self.pub_b = self.create_publisher(Bool, '/obstacle/brake', 10)
        self.pub_lvl = self.create_publisher(Float32, '/obstacle/brake_level', 10)
        self.create_subscription(LaserScan, self.scan_topic, self.cb_scan, qos_profile_sensor_data)
        if self.use_depth:
            self.create_subscription(Image, self.depth_topic, self.cb_depth, qos_profile_sensor_data)
        self.create_subscription(Twist, self.driver_topic, self.cb_drv, 10)
        self.create_timer(1.0 / self.rate, self.tick)
        self.get_logger().info(
            f"AEB FUSION prêt : lidar({self.scan_topic}, avant ±{math.degrees(self.sector):.0f}°) "
            f"+ profondeur({'ON' if self.use_depth else 'OFF'}), arrêt<{self.d_stop} m")

    def cb_drv(self, m):
        self.driver = m

    def cb_scan(self, scan):
        best = None
        a = scan.angle_min
        for r in scan.ranges:
            da = math.atan2(math.sin(a - self.front), math.cos(a - self.front))
            if abs(da) <= self.sector and self.rmin < r < self.rmax and math.isfinite(r):
                if best is None or r < best:
                    best = r
            a += scan.angle_increment
        self.d_lidar = best
        self.t_lidar = self.get_clock().now()

    def cb_depth(self, msg):
        d = depth_to_m(msg)
        if d is None:
            return
        h, w = d.shape
        v = d[int(self.band[0] * h):int(self.band[1] * h),
              int(self.cols[0] * w):int(self.cols[1] * w)]
        v = v[(v > self.dmin) & np.isfinite(v)]
        self.d_depth = float(np.percentile(v, self.pct)) if v.size >= 40 else None
        self.t_depth = self.get_clock().now()

    def _fresh(self, t, max_age=0.5):
        return t is not None and (self.get_clock().now() - t).nanoseconds * 1e-9 < max_age

    def tick(self):
        cands = []
        if self.d_lidar is not None and self._fresh(self.t_lidar):
            cands.append(('lidar', self.d_lidar))
        if self.d_depth is not None and self._fresh(self.t_depth):
            cands.append(('depth', self.d_depth))
        if not cands:
            self._stop_start = None
            self.pub_b.publish(Bool(data=False))
            return
        src, dist = min(cands, key=lambda c: c[1])
        self.get_logger().info(f"danger : {dist:.2f} m ({src})", throttle_duration_sec=1.0)

        if dist <= self.d_stop:
            f = 0.0
        elif dist >= self.d_slow:
            f = 1.0
        else:
            f = (dist - self.d_stop) / (self.d_slow - self.d_stop)

        self.pub_lvl.publish(Float32(data=float(1.0 - f)))
        if f >= 0.999:
            self._stop_start = None
            self.pub_b.publish(Bool(data=False))
            return

        t = Twist()
        vx = self.driver.linear.x
        if f <= 0.01:
            now = self.get_clock().now()
            if self._stop_start is None:
                self._stop_start = now
            elapsed = (now - self._stop_start).nanoseconds * 1e-9
            if self.brake_reverse > 0.0 and elapsed < self.brake_time:
                t.linear.x = -self.brake_reverse          # frein actif (recul bref)
            else:
                t.linear.x = 0.0
        else:
            self._stop_start = None
            t.linear.x = vx * f if vx > 0.0 else vx
        t.angular.z = self.driver.angular.z
        self.pub.publish(t)
        self.pub_b.publish(Bool(data=True))
        if f <= 0.01:
            self.get_logger().warn(f"*** AEB URGENCE : ARRET — {src} à {dist:.2f} m ***",
                                   throttle_duration_sec=0.4)


def main():
    rclpy.init()
    node = AebFusion()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
