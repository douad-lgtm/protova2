#!/usr/bin/env python3
"""
Visualiseur camera WiFi — ProtoVA (remplace rqt_image_view, plus fiable).

S'abonne au flux JPEG compresse de la camera (QoS best-effort, comme la camera),
decode chaque image avec OpenCV et l'affiche en direct. Contourne les soucis de
rqt_image_view (QoS + syntaxe _image_transport traitee comme un remap).

Prerequis : la camera tourne sur la Jetson (via launch_car_wifi.sh), PC et Jetson
sur le meme WiFi, ROS_DOMAIN_ID=125.

Usage:
  python3 view_camera.py                       # couleur compressee, fenetre live
  python3 view_camera.py --topic /camera/depth/image_raw/compressed
  python3 view_camera.py --save ~/cam_test.png # mode sans ecran : sauve 1 image et quitte
Fenetre live : touche 'q' pour quitter.
"""
import argparse
import time

import numpy as np
import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage


class CamViewer(Node):
    def __init__(self, topic, save_path):
        super().__init__('cam_viewer')
        self.save_path = save_path
        self.last = None
        self.n = 0
        self.t0 = time.time()
        # QoS best-effort : indispensable pour matcher le flux camera (capteur).
        # depth=1 : toujours la DERNIERE image, pas de file d'attente (latence mini)
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT,
                         history=HistoryPolicy.KEEP_LAST, depth=1)
        self.create_subscription(CompressedImage, topic, self.cb, qos)
        self.get_logger().info(f"abonne a {topic} (best-effort) — en attente d'images...")

    def cb(self, msg):
        arr = np.frombuffer(bytes(msg.data), np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return
        self.last = img
        self.n += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--topic', default='/camera/color/image_raw/compressed')
    ap.add_argument('--save', default=None, help='sauver la 1ere image ici puis quitter (sans ecran)')
    args = ap.parse_args()

    rclpy.init()
    node = CamViewer(args.topic, args.save)
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            if node.last is None:
                continue
            if args.save:
                cv2.imwrite(args.save, node.last)
                node.get_logger().info(f"image {node.last.shape} sauvee -> {args.save}")
                break
            fps = node.n / max(time.time() - node.t0, 1e-3)
            frame = node.last.copy()
            cv2.putText(frame, f"ProtoVA cam  {frame.shape[1]}x{frame.shape[0]}  {fps:4.1f} fps",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            cv2.imshow('ProtoVA - camera voiture (WiFi)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
