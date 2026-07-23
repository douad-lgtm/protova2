#!/usr/bin/env python3
"""
slam.launch.py - LiDAR + TF + odometrie laser (rf2o) pour ProtoVA.
Equivalent fonctionnel recree d'apres specs (l'original etait sur la Jetson).

Publie :
  /scan        LaserScan (RPLIDAR sur /dev/ttyUSB0)
  /odom_rf2o   nav_msgs/Odometry (via rf2o a partir de /scan)  <-- utilise par odom_to_gps
  TF  base_link -> laser (statique)

Lancer : ros2 launch slam.launch.py
Prerequis : paquets ros-humble-rplidar-ros et rf2o_laser_odometry.

NOTE : ajuster 'serial_baudrate' selon ton modele de LiDAR
       (RPLIDAR A1 = 115200 ; A2/A3/S1 = 256000). Et l'offset TF base_link->laser
       (ici z=0.10 m) selon ta mecanique.
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    lidar = Node(
        package='rplidar_ros', executable='rplidar_composition', name='rplidar',
        output='screen',
        parameters=[{
            'serial_port': '/dev/ttyUSB0',
            'serial_baudrate': 115200,        # A1=115200 ; A2/A3/S1=256000 -> a ajuster
            'frame_id': 'laser',
            'angle_compensate': True,
            'scan_mode': 'Standard',
        }],
    )

    tf_base_laser = Node(
        package='tf2_ros', executable='static_transform_publisher', name='tf_base_laser',
        # x y z  yaw pitch roll  parent child
        arguments=['0', '0', '0.10', '0', '0', '0', 'base_link', 'laser'],
    )

    rf2o = Node(
        package='rf2o_laser_odometry', executable='rf2o_laser_odometry_node', name='rf2o',
        output='screen',
        parameters=[{
            'laser_scan_topic': '/scan',
            'odom_topic': '/odom_rf2o',
            'publish_tf': True,
            'base_frame_id': 'base_link',
            'odom_frame_id': 'odom',
            'init_pose_from_topic': '',
            'freq': 10.0,
        }],
    )

    # --- Optionnel : cartographie SLAM (decommenter si besoin) ---
    # slam = Node(
    #     package='slam_toolbox', executable='async_slam_toolbox_node', name='slam_toolbox',
    #     output='screen',
    #     parameters=[{'odom_frame': 'odom', 'base_frame': 'base_link',
    #                  'scan_topic': '/scan', 'mode': 'mapping'}],
    # )

    return LaunchDescription([lidar, tf_base_laser, rf2o])  # , slam
