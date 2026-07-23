#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
import subprocess


class BluetoothStatusNode(Node):

    def __init__(self):
        super().__init__('bluetooth_status_node')

        self.address = "98:B6:E9:DE:60:0F"
        self.bt_connected = False

        self.pub = self.create_publisher(Bool, '/bluetooth_status', 10)

        # 2 Hz = largement suffisant
        self.timer = self.create_timer(0.5, self.timer_callback)

        self.get_logger().info("Bluetooth status node started")

    def is_device_connected(self) -> bool:
        try:
            out = subprocess.check_output(
                ["bluetoothctl", "info", self.address],
                stderr=subprocess.DEVNULL
            )
            return b"Connected: yes" in out
        except subprocess.CalledProcessError:
            return False

    def timer_callback(self):
        connected = self.is_device_connected()

        if connected != self.bt_connected:
            self.bt_connected = connected
            if connected:
                self.get_logger().info("Bluetooth CONNECTED")
            else:
                self.get_logger().warn("Bluetooth DISCONNECTED")

        msg = Bool()
        msg.data = self.bt_connected
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = BluetoothStatusNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
