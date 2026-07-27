#!/usr/bin/env python3
"""banc frein parametrable : bench_brake2.py <v_brake> <t_brake>"""
import sys, time, rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32

VB, TB = float(sys.argv[1]), float(sys.argv[2])

class B(Node):
    def __init__(s):
        super().__init__('bench2')
        s.pub = s.create_publisher(Twist, '/cmd_vel', 10)
        s.vel = 0.0
        s.create_subscription(Float32, '/velocity',
                              lambda m: setattr(s, 'vel', float(m.data)), 10)
    def send(s, v):
        t = Twist(); t.linear.x = float(v); t.angular.z = 83.0
        s.pub.publish(t)
    def run(s, v, dur):
        t0 = time.time()
        while time.time() - t0 < dur:
            s.send(v); rclpy.spin_once(s, timeout_sec=0.02); time.sleep(0.02)

rclpy.init()
n = B()
for _ in range(30):
    rclpy.spin_once(n, timeout_sec=0.1)
n.run(0.18, 2.0)
v0 = n.vel
t0 = time.time()
n.run(VB, TB)
while time.time() - t0 < 6.0:
    n.send(0.0); rclpy.spin_once(n, timeout_sec=0.02)
    if abs(n.vel) < 0.15:
        break
    time.sleep(0.02)
dt = time.time() - t0
print("frein %.2f pendant %.2fs : ARRET en %.2f s (v0=%.2f)" % (VB, TB, dt, v0), flush=True)
n.run(0.0, 1.0)
n.send(0.0)
