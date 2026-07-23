from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
import os

def generate_launch_description():

    ekf_config = "/home/protova2/protova2_yass/src/localisation/EKF/ekf_config.yaml"

    return LaunchDescription([

        # ==========================
        # EKF (robot_localization)
        # ==========================
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[ekf_config]
        ),

        # ==========================
        # Ackermann odometry
        # ==========================
        Node(
            package='ackermann_odom',
            executable='ackermann_odom',
            name='ackermann_odom',
            output='screen'
        ),

        # ==========================
        # RF2O (LiDAR odometry)
        # ==========================
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    os.getenv('HOME'),
                    'protova2_yass',
                    'install',
                    'rf2o_laser_odometry',
                    'share',
                    'rf2o_laser_odometry',
                    'launch',
                    'rf2o_laser_odometry.launch.py'
                )
            )
        ),

        # ==========================
        # Multi path
        # ==========================
        Node(
            package='ackermann_odom',
            executable='multi_path',
            name='multi_path',
            output='screen'
        ),

    ])