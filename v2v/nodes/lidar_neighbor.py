#!/usr/bin/env python3
"""
lidar_neighbor.py — mesure la distance RÉELLE au véhicule/obstacle voisin avec le lidar.

Le RPLIDAR balaie 360° ; ce nœud cherche l'obstacle le plus proche dans un secteur
FRONTAL (par défaut ±40° devant le robot) et publie sa distance + son azimut.
C'est une mesure directe, au centimètre, du robot vers l'objet en face — par exemple
l'autre véhicule / le PC posé devant. Quand le robot ou l'objet bouge, la distance
change en temps réel : c'est une VRAIE mesure, pas une position déclarée.

Publie :
  /v2v/neighbor_dist (Float64)   : distance (m) au voisin le plus proche devant
  /v2v/neighbor      (String JSON): {"dist_m":..., "bearing_deg":...}

Params :
  sector_deg       (def 40)   demi-secteur frontal analysé (±40° = 80° devant)
  front_offset_deg (def 0)    où est "l'avant" du lidar (0 = axe X du scan)
  range_min        (def 0.05) ignore les points trop proches (le robot lui-même)
  range_max        (def 12.0) portée max
  smooth           (def 0.3)  lissage exponentiel (0=aucun, proche de 1=très lisse)
"""
import json
import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float64, String


class LidarNeighbor(Node):
    def __init__(self):
        super().__init__('lidar_neighbor')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.sector = math.radians(float(g('sector_deg', 40.0)))
        # RPLIDAR monte "moteur a l'arriere" : l'avant du robot = 180 deg du scan
        self.front = math.radians(float(g('front_offset_deg', 180.0)))
        self.rmin = float(g('range_min', 0.05))
        self.rmax = float(g('range_max', 12.0))
        self.alpha = float(g('smooth', 0.3))
        self.filt = None
        self.pub_d = self.create_publisher(Float64, '/v2v/neighbor_dist', 10)
        self.pub_s = self.create_publisher(String, '/v2v/neighbor', 10)
        self.create_subscription(LaserScan, '/scan', self.cb, 10)
        self.get_logger().info(
            f"lidar_neighbor : secteur avant +/-{math.degrees(self.sector):.0f} deg, "
            f"/scan -> /v2v/neighbor_dist")

    def cb(self, scan):
        best_r, best_a = None, None
        a = scan.angle_min
        for r in scan.ranges:
            # angle du point ramené par rapport à l'avant du robot (-pi..pi)
            da = math.atan2(math.sin(a - self.front), math.cos(a - self.front))
            if abs(da) <= self.sector and self.rmin < r < self.rmax and math.isfinite(r):
                if best_r is None or r < best_r:
                    best_r, best_a = r, da
            a += scan.angle_increment
        if best_r is None:
            return
        # lissage pour un affichage stable
        self.filt = best_r if self.filt is None else \
            (1 - self.alpha) * self.filt + self.alpha * best_r
        d = round(self.filt, 3)
        self.pub_d.publish(Float64(data=d))
        self.pub_s.publish(String(data=json.dumps(
            {"dist_m": d, "bearing_deg": round(math.degrees(best_a), 1)})))
        self.get_logger().info(f"voisin devant : {d:.2f} m  (azimut {math.degrees(best_a):+.0f} deg)")


def main():
    rclpy.init()
    node = LidarNeighbor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
