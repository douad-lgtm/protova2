from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():

    pkg_share = get_package_share_directory('controller')
    mux_config = os.path.join(pkg_share, 'config', 'twist_mux.yaml')

    return LaunchDescription([

         # --- PS4 TELEOP ---
        Node(
            package='controller',
            executable='ps4_teleop',
            name='ps4_teleop',
            output='screen'
        ),
        

        # --- AEB NODE ---
        Node(
            package='safety',
            executable='AEB',
            name='AEB',
            output='screen'
        ),

        # --- dist_min ---
        Node(
            package='detection',
            executable='dist_min',
            name='dist_min',
            output='screen'
        ),
        # --- RX ---
        Node(
            package='RX',
            executable='RX',
            name='RX',
            output='screen'
        ),
        # --- TX ---
        Node(
            package='controller',
            executable='TX',
            name='TX',
            output='screen'
        ),

        # --- TWIST MUX ---
        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            parameters=[mux_config],
            remappings=[
                ('/cmd_vel_out', '/cmd_vel')  # <-- remap ici
            ],
            output='screen'
        ),

    ])
