#!/usr/bin/env python3
"""Compte les images/s recues sur le PC via WiFi pendant 60 s -> fps_wifi.txt"""
import time, rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

class F(Node):
    def __init__(s):
        super().__init__('fps_probe')
        s.n = 0
        s.create_subscription(CompressedImage, '/camera/color/image_raw/compressed',
                              lambda m: setattr(s, 'n', s.n + 1), qos_profile_sensor_data)

rclpy.init()
node = F()
fps = []
t_end = time.time() + 60
while time.time() < t_end:
    t1 = time.time() + 1.0
    node.n = 0
    while time.time() < t1:
        rclpy.spin_once(node, timeout_sec=0.05)
    fps.append(node.n)
open("fps_wifi.txt", "w").write("\n".join(str(x) for x in fps))
print(f"FPS WiFi : moyen {sum(fps)/len(fps):.1f} | min {min(fps)} | max {max(fps)} | n={len(fps)}s")
