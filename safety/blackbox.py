#!/usr/bin/env python3
"""boite noire 90s : timeline de toute la chaine AEB"""
import math, time, rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32

FRONT = math.pi  # avant robot = 180 deg du scan

class BB(Node):
    def __init__(s):
        super().__init__('blackbox')
        s.df = s.dr = None
        s.g29 = s.aeb = s.out = None
        s.t_aeb = 0.0
        s.vel = 0.0
        s.create_subscription(LaserScan, '/scan', s.cb_scan, qos_profile_sensor_data)
        s.create_subscription(Twist, '/cmd_vel_G29', lambda m: setattr(s, 'g29', m.linear.x), 10)
        s.create_subscription(Twist, '/cmd_vel_aeb', s.cb_aeb, 10)
        s.create_subscription(Twist, '/cmd_vel', lambda m: setattr(s, 'out', m.linear.x), 10)
        s.create_subscription(Float32, '/velocity', lambda m: setattr(s, 'vel', float(m.data)), 10)
    def cb_aeb(s, m):
        s.aeb = m.linear.x; s.t_aeb = time.time()
    def cb_scan(s, scan):
        bf = br = None
        a = scan.angle_min
        for r in scan.ranges:
            if 0.06 < r < 12.0 and math.isfinite(r):
                da = math.atan2(math.sin(a-FRONT), math.cos(a-FRONT))
                if abs(da) <= math.radians(45) and (bf is None or r < bf): bf = r
                da2 = math.atan2(math.sin(a), math.cos(a))
                if abs(da2) <= math.radians(45) and (br is None or r < br): br = r
            a += scan.angle_increment
        s.df, s.dr = bf, br

rclpy.init(); n = BB()
print("t    | AVANT | ARR  | pedale | AEBpub | SORTIE | roues", flush=True)
t0 = time.time()
last = 0
while time.time() - t0 < 90:
    rclpy.spin_once(n, timeout_sec=0.05)
    el = time.time() - t0
    if el - last >= 0.5:
        last = el
        aeb = f"{n.aeb:+.2f}" if (n.aeb is not None and time.time()-n.t_aeb < 0.4) else "  -  "
        f = lambda v: f"{v:+.2f}" if v is not None else "  ?  "
        d = lambda v: f"{v:.2f}" if v is not None else " ?  "
        print(f"{el:4.1f} | {d(n.df)} | {d(n.dr)} | {f(n.g29)} | {aeb} | {f(n.out)} | {n.vel:+.2f}", flush=True)
