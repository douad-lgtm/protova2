#!/usr/bin/env python3
"""
Pont /joy PC -> Jetson, cote reception (voir joy_udp_bridge_tx.py pour le
contexte : contourne un blocage du trafic DDS multicast sur le partage de
connexion iPhone, en relayant /joy par UDP unicast simple).

Ce noeud tourne sur la Jetson : il ecoute le port UDP, deserialise le texte
recu et republie un vrai sensor_msgs/Joy sur /joy EN LOCAL, que g29_teleop
consomme normalement (abonnement local = fiable, aucune dependance DDS
inter-machines).

Usage : python3 joy_udp_bridge_rx.py --port 9001
"""
import argparse
import socket

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy


class JoyUdpRx(Node):
    def __init__(self, port):
        super().__init__('joy_udp_bridge_rx')
        self.pub = self.create_publisher(Joy, '/joy', 10)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('0.0.0.0', port))
        self.sock.setblocking(False)
        self.create_timer(0.01, self._poll)   # 100 Hz
        self.get_logger().info(f'Pont /joy <- UDP :{port} (republie en local)')

    def _poll(self):
        try:
            while True:
                data, _ = self.sock.recvfrom(4096)
                self._handle(data.decode('utf-8'))
        except BlockingIOError:
            pass

    def _handle(self, line):
        try:
            axes_part, btn_part = line.split('|')
            _, axes_rest = axes_part.split(':', 1)
            n_axes, *axes_vals = axes_rest.split(',')
            _, btn_rest = btn_part.split(':', 1)
            n_btn, *btn_vals = btn_rest.split(',')

            msg = Joy()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.axes = [float(v) for v in axes_vals[:int(n_axes)]]
            msg.buttons = [int(v) for v in btn_vals[:int(n_btn)]]
            self.pub.publish(msg)
        except (ValueError, IndexError) as e:
            self.get_logger().warning(f'trame invalide ignoree : {e}', throttle_duration_sec=2.0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=9001)
    args, _ = p.parse_known_args()

    rclpy.init()
    node = JoyUdpRx(args.port)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
