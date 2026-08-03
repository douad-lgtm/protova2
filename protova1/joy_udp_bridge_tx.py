#!/usr/bin/env python3
"""
Pont /joy PC -> Jetson par UDP brut (contourne un probleme de multicast DDS
sur le partage de connexion iPhone : la decouverte DDS passe, mais pas les
donnees. L'UDP unicast direct, lui, fonctionne dans les deux sens - verifie
au prealable avec `nc -u`).

Ce noeud tourne sur le PC : il s'abonne a /joy EN LOCAL (fiable, meme
machine) et renvoie chaque message par UDP simple vers la Jetson, qui le
republie localement avec joy_udp_bridge_rx.py.

Format du message (texte, lisible, independant de la version Python/ROS) :
    AXES:n,v1,v2,...,vn|BTN:m,b1,b2,...,bm

Usage : python3 joy_udp_bridge_tx.py --dest-ip 172.20.10.3 --dest-port 9001
"""
import argparse
import socket

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy


class JoyUdpTx(Node):
    def __init__(self, dest_ip, dest_port):
        super().__init__('joy_udp_bridge_tx')
        self.dest = (dest_ip, dest_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.create_subscription(Joy, '/joy', self.cb, 10)
        self.get_logger().info(f'Pont /joy -> UDP {dest_ip}:{dest_port}')

    def cb(self, msg: Joy):
        axes = ','.join(f'{a:.4f}' for a in msg.axes)
        btns = ','.join(str(b) for b in msg.buttons)
        line = f'AXES:{len(msg.axes)},{axes}|BTN:{len(msg.buttons)},{btns}'
        try:
            self.sock.sendto(line.encode('utf-8'), self.dest)
        except OSError as e:
            self.get_logger().warning(f'envoi UDP echoue : {e}', throttle_duration_sec=2.0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dest-ip', default='172.20.10.3')
    p.add_argument('--dest-port', type=int, default=9001)
    args, _ = p.parse_known_args()

    rclpy.init()
    node = JoyUdpTx(args.dest_ip, args.dest_port)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
