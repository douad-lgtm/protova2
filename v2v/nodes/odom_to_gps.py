#!/usr/bin/env python3
"""
Convertit l'odometrie locale (nav_msgs/Odometry, metres) en position GPS
(lat/lon) + cap + vitesse, et publie /v2v/my_gps -> alimente le CAM V2V avec
la position, le CAP et la VITESSE REELS.

Repere local : origine georeferencee (origin_lat, origin_lon).
  x (avant) -> Nord ; y (gauche) -> Est   (convention demo, coherente).
  cap = lacet (yaw) du quaternion, degres Nord vrai [0,360[.
  vitesse = norme de la vitesse lineaire (twist), m/s.

Publie /v2v/my_gps (Float64MultiArray [lat, lon, cap_deg, vitesse_mps]).

Params:
  odom_topic   (str)   topic d'odometrie (/odom_rf2o ou /odometry/filtered)
  origin_lat   (float) latitude de l'origine du repere odom
  origin_lon   (float) longitude de l'origine du repere odom
"""
import math
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from std_msgs.msg import Float64MultiArray


class OdomToGps(Node):
    def __init__(self):
        super().__init__('odom_to_gps')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.lat0 = float(g('origin_lat', 48.76680))
        self.lon0 = float(g('origin_lon', 11.43200))
        self.topic = g('odom_topic', '/odom_rf2o')
        self.m_per_deg_lat = 111320.0
        self.m_per_deg_lon = 111320.0 * math.cos(math.radians(self.lat0))
        self.pub = self.create_publisher(Float64MultiArray, '/v2v/my_gps', 10)
        self.create_subscription(Odometry, self.topic, self.cb, 10)
        self.n = 0
        self.get_logger().info(
            f"odom_to_gps: {self.topic} -> /v2v/my_gps  origine=({self.lat0},{self.lon0})")

    def cb(self, msg):
        x = msg.pose.pose.position.x   # avant -> Nord
        y = msg.pose.pose.position.y   # gauche -> Est
        lat = self.lat0 + x / self.m_per_deg_lat
        lon = self.lon0 + y / self.m_per_deg_lon

        # cap (yaw du quaternion) -> degres Nord vrai [0,360[
        q = msg.pose.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        heading = math.degrees(yaw) % 360.0

        # vitesse : norme de la composante lineaire du twist (m/s)
        v = msg.twist.twist.linear
        speed = math.hypot(v.x, v.y)

        self.pub.publish(Float64MultiArray(data=[lat, lon, heading, speed]))
        self.n += 1
        if self.n % 20 == 0:
            self.get_logger().info(
                f"odom (x={x:.2f}, y={y:.2f} m, cap={heading:.0f} deg, "
                f"v={speed:.2f} m/s) -> GPS ({lat:.7f}, {lon:.7f})")


def main():
    rclpy.init()
    rclpy.spin(OdomToGps())


if __name__ == '__main__':
    main()
