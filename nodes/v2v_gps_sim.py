#!/usr/bin/env python3
# Publie /v2v/my_gps (Float64MultiArray [lat,lon,cap_deg,vitesse_mps]) en
# deplacement lineaire de (start) vers (end) sur 'duration' secondes
# -> simule un vehicule qui approche, avec cap et vitesse coherents.
import math
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

class Sim(Node):
    def __init__(self):
        super().__init__('v2v_gps_sim')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.slat = float(g('start_lat', 48.76770)); self.slon = float(g('start_lon', 11.43200))
        self.elat = float(g('end_lat', 48.76683));   self.elon = float(g('end_lon', 11.43200))
        self.dur = float(g('duration', 20.0))
        self.pub = self.create_publisher(Float64MultiArray, '/v2v/my_gps', 10)

        # cap (constant) et vitesse du trajet start->end, convention Nord=+lat, Est=+lon
        m_lat = 111320.0
        m_lon = 111320.0 * math.cos(math.radians(self.slat))
        d_north = (self.elat - self.slat) * m_lat
        d_east = (self.elon - self.slon) * m_lon
        self.heading = math.degrees(math.atan2(d_east, d_north)) % 360.0
        self.speed = math.hypot(d_north, d_east) / self.dur if self.dur > 0 else 0.0

        self.t0 = self.get_clock().now()
        self.create_timer(0.2, self.tick)
        self.get_logger().info(
            f"sim: ({self.slat},{self.slon}) -> ({self.elat},{self.elon}) en {self.dur}s "
            f"(cap={self.heading:.0f} deg, v={self.speed:.2f} m/s)")
    def tick(self):
        el = (self.get_clock().now() - self.t0).nanoseconds * 1e-9
        f = min(el / self.dur, 1.0)
        lat = self.slat + f * (self.elat - self.slat)
        lon = self.slon + f * (self.elon - self.slon)
        speed = self.speed if f < 1.0 else 0.0   # arrete a l'arrivee
        self.pub.publish(Float64MultiArray(data=[lat, lon, self.heading, speed]))

def main():
    rclpy.init(); rclpy.spin(Sim())

if __name__ == '__main__':
    main()
