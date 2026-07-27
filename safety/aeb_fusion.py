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
        # RPLIDAR monte "moteur a l'arriere" : le 0 du scan pointe vers l'ARRIERE
        # -> l'avant du robot est a 180 deg (verifie sur scan reel : 0deg=0.67m arriere, 180deg=3.2m avant)
        self.front = math.radians(float(g('front_offset_deg', 180.0)))
        self.rmin = float(g('range_min', 0.06))
        self.rmax = float(g('range_max', 12.0))
        # couloir de la caméra
        self.use_depth = bool(g('use_depth', True))
        self.band = (float(g('band_top', 0.35)), float(g('band_bot', 0.62)))
        self.cols = (float(g('cols_left', 0.30)), float(g('cols_right', 0.70)))
        self.pct = int(g('pct', 10))
        self.dmin = float(g('dmin', 0.15))
        # frein actif : impulsion de marche arriere = frein moteur ESC. Banc encodeur
        # (roues en l'air) : roue libre 1.94 s ; -0.3/0.25s 1.16 s ; -0.5/0.5s 0.61 s ;
        # -0.8 n'apporte rien (saturation ESC) -> defaut -0.5 / 0.5 s.
        self.brake_reverse = float(g('brake_reverse', 0.5))
        self.brake_time = float(g('brake_time', 0.5))
        self.wheel_vel = 0.0    # /velocity (encodeur) : coupe le frein des l'arret reel
        self.rate = float(g('rate', 30.0))

        self.driver = Twist()
        self.d_lidar = None
        self.d_rear = None      # plus proche obstacle ARRIERE (lidar 360)
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
        self.create_subscription(Float32, '/velocity',
                                 lambda m: setattr(self, 'wheel_vel', float(m.data)), 10)
        self.create_timer(1.0 / self.rate, self.tick)
        self.get_logger().info(
            f"AEB FUSION prêt : lidar({self.scan_topic}, avant ±{math.degrees(self.sector):.0f}°) "
            f"+ profondeur({'ON' if self.use_depth else 'OFF'}), arrêt<{self.d_stop} m")

    def cb_drv(self, m):
        self.driver = m

    def cb_scan(self, scan):
        # un seul passage : secteur AVANT (self.front) et secteur ARRIERE (front+180)
        best_f, best_r = None, None
        rear = self.front + math.pi
        a = scan.angle_min
        for r in scan.ranges:
            if self.rmin < r < self.rmax and math.isfinite(r):
                da_f = math.atan2(math.sin(a - self.front), math.cos(a - self.front))
                if abs(da_f) <= self.sector and (best_f is None or r < best_f):
                    best_f = r
                da_r = math.atan2(math.sin(a - rear), math.cos(a - rear))
                if abs(da_r) <= self.sector and (best_r is None or r < best_r):
                    best_r = r
            a += scan.angle_increment
        self.d_lidar = best_f
        self.d_rear = best_r
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

    def _factor(self, dist):
        """facteur de vitesse 0..1 selon la distance (None = rien de detecte)."""
        if dist is None:
            return 1.0
        if dist <= self.d_stop:
            return 0.0
        if dist >= self.d_slow:
            return 1.0
        return (dist - self.d_stop) / (self.d_slow - self.d_stop)

    def tick(self):
        # --- distances AVANT (lidar + camera) et ARRIERE (lidar seul, 360) ---
        d_front, src_front = None, ''
        if self.d_lidar is not None and self._fresh(self.t_lidar):
            d_front, src_front = self.d_lidar, 'lidar'
        if self.d_depth is not None and self._fresh(self.t_depth):
            if d_front is None or self.d_depth < d_front:
                d_front, src_front = self.d_depth, 'depth'
        d_rear = self.d_rear if self._fresh(self.t_lidar) else None

        ftxt = f"{d_front:.2f} m ({src_front})" if d_front is not None else "libre"
        rtxt = f"{d_rear:.2f} m" if d_rear is not None else "libre"
        self.get_logger().info(f"avant : {ftxt} | arriere : {rtxt}",
                               throttle_duration_sec=1.0)

        f_fwd = self._factor(d_front)     # limite la marche AVANT
        f_rev = self._factor(d_rear)      # limite la marche ARRIERE

        vx = self.driver.linear.x
        if vx > 0.0:
            f, side, dist = f_fwd, 'AVANT', d_front
        elif vx < 0.0:
            f, side, dist = f_rev, 'ARRIERE', d_rear
        else:
            self._stop_start = None
            self.pub_b.publish(Bool(data=False))
            self.pub_lvl.publish(Float32(data=0.0))
            return

        self.pub_lvl.publish(Float32(data=float(1.0 - f)))
        if f >= 0.999:                    # direction demandee libre -> conduite normale
            self._stop_start = None
            self.pub_b.publish(Bool(data=False))
            return

        t = Twist()
        if f <= 0.01:
            # arret d'urgence : la voiture s'arrete et RESTE arretee (0 publie en
            # continu, priorite 255) meme si le conducteur garde l'accelerateur.
            # Impulsion de frein actif UNIQUEMENT en marche AVANT (calibree au banc,
            # coupee des l'arret encodeur). En marche ARRIERE : arret direct a 0,
            # AUCUN mouvement vers l'avant (demande utilisatrice).
            now = self.get_clock().now()
            if self._stop_start is None:
                self._stop_start = now
            elapsed = (now - self._stop_start).nanoseconds * 1e-9
            if vx > 0.0 and self.brake_reverse > 0.0 and elapsed < self.brake_time \
                    and abs(self.wheel_vel) > 0.2:
                t.linear.x = -self.brake_reverse
            else:
                t.linear.x = 0.0
        else:
            self._stop_start = None
            t.linear.x = vx * f           # ralentissement progressif (les 2 sens)
        t.angular.z = self.driver.angular.z
        self.pub.publish(t)
        self.pub_b.publish(Bool(data=True))
        if f <= 0.01:
            self.get_logger().warn(
                f"*** AEB URGENCE ({side}) : ARRET — obstacle à {dist:.2f} m ***",
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
