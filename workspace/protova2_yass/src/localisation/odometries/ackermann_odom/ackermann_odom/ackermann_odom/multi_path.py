#!/usr/bin/env python3

import rclpy
from rclpy.node import Node

from nav_msgs.msg import Path, Odometry
from geometry_msgs.msg import PoseStamped


class MultiPath(Node):

    def __init__(self):
        super().__init__('multi_path')

        # ===== Publishers =====
        self.ackerman_path_pub = self.create_publisher(Path, 'ackerman_path', 10)
        self.lidar_path_pub = self.create_publisher(Path, 'lidar_path', 10)
        self.imu_path_pub = self.create_publisher(Path, 'imu_path', 10)
        self.filter_path_pub = self.create_publisher(Path, 'filter_path', 10)

        # ===== Paths =====
        self.frame_id = 'odom'

        self.ackerman_path = Path()
        self.ackerman_path.header.frame_id = self.frame_id

        self.lidar_path = Path()
        self.lidar_path.header.frame_id = self.frame_id

        self.imu_path = Path()
        self.imu_path.header.frame_id = self.frame_id

        self.filter_path = Path()
        self.filter_path.header.frame_id = self.frame_id

        # ===== Subscriptions =====
        self.create_subscription(Odometry, '/odom_ackermann', self.ackerman_callback, 10)
        self.create_subscription(Odometry, '/odom_rf2o', self.lidar_callback, 10)
        self.create_subscription(Odometry, '/odom_imu', self.imu_callback, 10)
        self.create_subscription(Odometry, '/odometry/filtered', self.filter_callback, 10)

        self.get_logger().info("MultiPath node started 🚀")

    # ==========================
    # Utils
    # ==========================
    def odom_to_pose(self, msg: Odometry):
        pose = PoseStamped()
        pose.header = msg.header
        pose.pose = msg.pose.pose
        return pose

    def update_path(self, path, pose, stamp):
        path.poses.append(pose)
        path.header.stamp = stamp

    # ==========================
    # Callbacks
    # ==========================
    def ackerman_callback(self, msg: Odometry):
        pose = self.odom_to_pose(msg)
        self.update_path(self.ackerman_path, pose, msg.header.stamp)
        self.ackerman_path_pub.publish(self.ackerman_path)

    def imu_callback(self, msg: Odometry):
        pose = self.odom_to_pose(msg)
        self.update_path(self.imu_path, pose, msg.header.stamp)
        self.imu_path_pub.publish(self.imu_path)

    def lidar_callback(self, msg: Odometry):
        pose = self.odom_to_pose(msg)
        self.update_path(self.lidar_path, pose, msg.header.stamp)
        self.lidar_path_pub.publish(self.lidar_path)

    def filter_callback(self, msg: Odometry):
        pose = self.odom_to_pose(msg)
        self.update_path(self.filter_path, pose, msg.header.stamp)
        self.filter_path_pub.publish(self.filter_path)


# ==========================
# Main
# ==========================
def main(args=None):
    rclpy.init(args=args)
    node = MultiPath()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()