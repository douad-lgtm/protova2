from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import Command
from launch_ros.parameter_descriptions import ParameterValue
import os


def generate_launch_description():

    urdf_file = os.path.expanduser(
        "~/protova2_yass/src/car_description/urdf/car.urdf"
    )

    robot_description = ParameterValue(
        Command(["cat ", urdf_file]),
        value_type=str
    )

    return LaunchDescription([

        # ── robot_state_publisher ─────────────────────────
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[{
                "robot_description": robot_description,
                "use_sim_time": False
            }]
        ),

        # ── joint_state_publisher ─────────────────────────
        Node(
            package="joint_state_publisher",
            executable="joint_state_publisher",
            name="joint_state_publisher",
            output="screen",
            parameters=[{
                "robot_description": robot_description,
                "rate": 200.0   # ← augmente à 50 Hz
            }]
        ),

    ])