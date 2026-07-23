import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Float32
import numpy as np

class dist_min(Node):
    def __init__(self):
        super().__init__('dist_min')

        # Subscription au Lidar
        self.subscription = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )

        # Publishers pour les distances minimales
        self.front_distance_publisher = self.create_publisher(Float32, '/closest_object_front_distance', 10)
        self.left_distance_publisher = self.create_publisher(Float32, '/closest_object_left_distance', 10)
        self.right_distance_publisher = self.create_publisher(Float32, '/closest_object_right_distance', 10)
        self.rear_distance_publisher = self.create_publisher(Float32, '/closest_object_rear_distance', 10)

        # Définition des zones (en degrés)
        self.front_range = 10     # ±10° devant
        self.side_range = 45      # ±45° côté gauche/droite
        self.rear_range = 10      # ±10° derrière

    def scan_callback(self, msg):
        ranges = np.array(msg.ranges)
        angle_min = msg.angle_min
        angle_increment = msg.angle_increment

        # Supprimer valeurs invalides
        ranges = np.where(np.isfinite(ranges), ranges, np.inf)

        # Créer tableau des angles
        angles = angle_min + np.arange(len(ranges)) * angle_increment
        angles_deg = np.degrees(angles)

        # Décaler les angles pour moteur à l'arrière
        # 0° = avant du robot
        angles_deg = (angles_deg + 180) % 360  # +180° pour remettre l'avant à 0°

        # Zones en degrés
        front_mask = (angles_deg >= 360 - self.front_range) | (angles_deg <= self.front_range)
        rear_mask = (angles_deg >= 180 - self.rear_range) & (angles_deg <= 180 + self.rear_range)
        left_mask = (angles_deg > 0 + self.front_range) & (angles_deg <= 0 + self.front_range + self.side_range)
        right_mask = (angles_deg >= 360 - self.front_range - self.side_range) & (angles_deg < 360 - self.front_range)

        # Distance minimale par zone
        front_min = np.min(ranges[front_mask]) if np.any(front_mask) else float('inf')
        left_min  = np.min(ranges[left_mask])  if np.any(left_mask)  else float('inf')
        right_min = np.min(ranges[right_mask]) if np.any(right_mask) else float('inf')
        rear_min  = np.min(ranges[rear_mask])  if np.any(rear_mask)  else float('inf')

        # Publier en convertissant en float Python
        self.front_distance_publisher.publish(Float32(data=float(front_min)))
        self.left_distance_publisher.publish(Float32(data=float(left_min)))
        self.right_distance_publisher.publish(Float32(data=float(right_min)))
        self.rear_distance_publisher.publish(Float32(data=float(rear_min)))


def main(args=None):
    rclpy.init(args=args)
    node = dist_min()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()