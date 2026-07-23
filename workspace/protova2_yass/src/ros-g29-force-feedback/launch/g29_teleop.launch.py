from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    # Path to config file
    config_file = PathJoinSubstitution([
        FindPackageShare('ros_g29_force_feedback'),
        'config',
        'g29.yaml'
    ])

    return LaunchDescription([
        # Joy node
        Node(
            package='joy',
            executable='joy_node',
            name='joy_node',
            output='screen'
        ),
        
        # G29 teleop node
        Node(
            package='protoVA_Utils',
            executable='g29_teleop',
            name='g29_teleop',
            output='screen'
        ),
        
        # G29 force feedback node
        Node(
            package='ros_g29_force_feedback',
            executable='g29_force_feedback',
            name='g29_force_feedback',
            parameters=[config_file],
            output='screen'
        ),
    ])
