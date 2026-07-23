#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import serial
import time
import numpy as np

from sensor_msgs.msg import Imu, MagneticField
from std_msgs.msg import Float64
from std_msgs.msg import Header


class ImuSerialNode(Node):

    def __init__(self):
        super().__init__('imu_serial_node')

        # ==========================
        # PARAMÈTRES
        # ==========================
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('frame_id', 'imu_link')

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
        self.frame_id = self.get_parameter('frame_id').value

        # ==========================
        # SERIAL
        # ==========================
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)
            self.get_logger().info(f"Connecté au port série {port}")
        except Exception as e:
            self.get_logger().error(f"Erreur ouverture port série: {e}")
            raise e

        # ==========================
        # PUBLISHERS
        # ==========================
        self.imu_pub = self.create_publisher(Imu, 'imu/raw', 10)
        self.mag_pub = self.create_publisher(MagneticField, 'mag/raw', 10)
        self.yaw_pub = self.create_publisher(Float64, 'imu/yaw_mag', 10)

        # ==========================
        # TIMER (100 Hz)
        # ==========================
        self.timer = self.create_timer(0.01, self.read_serial)

    def read_serial(self):
        if not self.ser.in_waiting:
            return

        try:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if not line.startswith("IMU"):
                return

            parts = line.split(',')
            if len(parts) != 10:
                return

            _, ax, ay, az, gx, gy, gz, mx, my, mz = parts

            ax, ay, az = float(ax), float(ay), float(az)
            gx, gy, gz = float(gx), float(gy), float(gz)
            mx, my, mz = float(mx), float(my), float(mz)

            now = self.get_clock().now().to_msg()

            # ==========================
            # IMU MSG
            # ==========================
            imu_msg = Imu()
            imu_msg.header = Header(stamp=now, frame_id=self.frame_id)

            imu_msg.linear_acceleration.x = ax
            imu_msg.linear_acceleration.y = ay
            imu_msg.linear_acceleration.z = az

            imu_msg.angular_velocity.x = gx
            imu_msg.angular_velocity.y = gy
            imu_msg.angular_velocity.z = gz

            imu_msg.orientation_covariance[0] = -1.0
            self.imu_pub.publish(imu_msg)

            # ==========================
            # MAG MSG
            # ==========================
            mag_msg = MagneticField()
            mag_msg.header = imu_msg.header
            mag_msg.magnetic_field.x = mx
            mag_msg.magnetic_field.y = my
            mag_msg.magnetic_field.z = mz
            self.mag_pub.publish(mag_msg)

            # ==========================
            # ROLL / PITCH / YAW (MAG)
            # ==========================
            roll  = np.arctan2(ay, az)
            pitch = np.arctan2(-ax, np.hypot(ay, az))

            mx2 = ( mx*np.cos(pitch)
                  + my*np.sin(roll)*np.sin(pitch)
                  + mz*np.cos(roll)*np.sin(pitch) )

            my2 = ( my*np.cos(roll)
                  - mz*np.sin(roll) )

            yaw_mag = np.degrees(np.arctan2(-my2, mx2))
            yaw_msg = Float64()
            yaw_msg.data = yaw_mag
            self.yaw_pub.publish(yaw_msg)

            self.get_logger().info(f"yaw_mag = {yaw_mag:.1f} deg")

        except Exception as e:
            self.get_logger().warn(f"Ligne invalide: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = ImuSerialNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.ser.close()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
