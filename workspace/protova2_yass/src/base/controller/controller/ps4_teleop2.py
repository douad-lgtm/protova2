#!/usr/bin/env python3

import rclpy
import numpy as np
from rclpy.node import Node

from sensor_msgs.msg import Joy
from geometry_msgs.msg import TwistStamped


class PS4TeleopNode(Node):

    def __init__(self):
        super().__init__('ps4_teleop')

        # =============================
        # PARAMÈTRES ROS2
        # =============================
        self.declare_parameter('max_throttle', 3)     # m/s
        self.declare_parameter('speed_factor', 1.0)    # 0 → 1
        self.declare_parameter('deadzone', 0.45)
        self.declare_parameter('axis_throttle', 4)
        self.declare_parameter('axis_steering', 0)
        self.declare_parameter('max_steering_angle', 25)  # degrés

        self.max_throttle = self.get_parameter('max_throttle').value
        self.speed_factor = self.get_parameter('speed_factor').value
        self.deadzone = self.get_parameter('deadzone').value
        self.axis_throttle = self.get_parameter('axis_throttle').value
        self.axis_steering = self.get_parameter('axis_steering').value
        self.max_steering_angle = self.get_parameter('max_steering_angle').value

        # =============================
        # ROS PUB / SUB
        # =============================
        self.joy_sub = self.create_subscription(
            Joy,
            '/joy',
            self.joy_callback,
            10
        )

        self.cmd_pub = self.create_publisher(
            TwistStamped,
            '/cmd_vel',
            10
        )

        self.get_logger().info('PS4 Teleop node started')

    # =============================
    # UTILS
    # =============================
    def apply_deadzone(self, x):
        if abs(x) < self.deadzone:
            return 0.0
        return x

    
    # =============================
    # CALLBACK
    # =============================
    def joy_callback(self, joy_msg: Joy):

        # Sécurité index
        if (self.axis_throttle >= len(joy_msg.axes)
                or self.axis_steering >= len(joy_msg.axes)):
            self.get_logger().warn('Index axe joystick invalide')
            return

        # =============================
        # THROTTLE
        # =============================
        throttle_axis = joy_msg.axes[self.axis_throttle]
        throttle_axis = self.apply_deadzone(throttle_axis)

        throttle = throttle_axis * self.max_throttle * self.speed_factor

        # =============================
        # STEERING
        # =============================
        steering_axis = joy_msg.axes[self.axis_steering]
        

        steering_angle =  np.deg2rad(steering_axis * self.max_steering_angle)

        # =============================
        # CMD_VEL
        # =============================
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'

        msg.twist.linear.x = throttle
        msg.twist.angular.z = steering_angle

        self.cmd_pub.publish(msg)

    # =============================
    # MAIN
    # =============================


def main(args=None):
    rclpy.init(args=args)
    node = PS4TeleopNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
