#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool
import usb.core


class USBStatusNode(Node):

    def __init__(self):
        super().__init__('usb_status_node')

        # ===== PARAMÈTRES =====
        self.vendor_id  = 0x046D   # Logitech
        self.product_id = 0xC24F   # G29 / volant
        self.usb_connected = False

        # Publisher
        self.pub = self.create_publisher(Bool, '/usb_status', 10)

        # Timer (ex: 5 Hz)
        self.timer = self.create_timer(0.2, self.timer_callback)

        self.get_logger().info("USB status node started")

    def timer_callback(self):
        """Callback périodique USB watchdog"""
        dev = usb.core.find(idVendor=self.vendor_id,
                            idProduct=self.product_id)

        connected = dev is not None

        # Log uniquement si changement
        if connected != self.usb_connected:
            self.usb_connected = connected
            if connected:
                self.get_logger().info("USB CONNECTED")
            else:
                self.get_logger().warn("USB DISCONNECTED")

        # Publish status
        msg = Bool()
        msg.data = self.usb_connected
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = USBStatusNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
