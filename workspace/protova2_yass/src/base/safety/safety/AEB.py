#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from geometry_msgs.msg import Twist

class AEB(Node):
    def __init__(self):
        super().__init__('AEB')
        # ===== Paramètres =====
        self.ttc_threshold  = 1.3   # seuil TTC [s]
        self.dist_threshold = 0.40  # seuil distance [m]
        self.vel_threshold  = 0.7   # seuil vitesse [m/s]
        self.max_speed      = 4.0   # m/s

        # ===== Variables =====
        self.velocity = 0.0
        self.distance = None

        # ===== Bool de déclenchement (latché) =====
        self.aeb_triggered = False

        # ===== Subscribers =====
        self.create_subscription(Float32, '/velocity',
                                 self.cb_velocity, 10)
        self.create_subscription(Float32, '/closest_object_front_distance',
                                 self.cb_distance, 10)
        self.create_subscription(Twist, '/cmd_vel',
                                 self.cb_cmd_vel, 10)

        # ===== Publishers =====
        self.pub_cmd = self.create_publisher(Twist, '/cmd_vel_aeb', 10)
        self.pub_ttc = self.create_publisher(Twist, '/ttc', 10)

        # ===== Loop =====
        self.timer = self.create_timer(0.001, self.loop)
        self.get_logger().info("AEB node started → /cmd_vel_aeb")

    # ================= Callbacks =================
    def cb_velocity(self, msg):
        self.velocity = float(msg.data)

    def cb_distance(self, msg):
        self.distance = float(msg.data)
        
    def cb_cmd_vel(self, msg):
        self.cmd_vel = msg.linear.x

    # ================= Main Loop =================
    def loop(self):
        if self.distance is None:
            return

        # --------------------------------------------------
        # 1) Reset du latch uniquement quand vitesse = 0
        # --------------------------------------------------
        if self.aeb_triggered and self.velocity <= 0.1:
            self.aeb_triggered = False
            self.get_logger().info("✅ AEB reset — véhicule arrêté")
            return

        # --------------------------------------------------
        # 2) Activation du latch si TTC < seuil
        # --------------------------------------------------
        ttc = self.distance / max(abs(self.velocity), 0.001)
        ttc_condition = (self.velocity > 0.01) and (ttc < self.ttc_threshold)

        if ttc_condition:
            self.aeb_triggered = True
            
            
        if self.aeb_triggered and self.velocity <= 0.01:
            self.aeb_triggered = False
            self.get_logger().info("✅ AEB reset — véhicule arrêté")
            return

        # --------------------------------------------------
        # 3) Si latché → maintien du frein jusqu'à arrêt
        # --------------------------------------------------
        if self.aeb_triggered:
            cmd = Twist()
            cmd.angular.z = 83.0
            cmd.linear.x  = -0.8
            self.pub_cmd.publish(cmd)
            self.get_logger().warning(
                f"🚨 AEB MAINTENU | TTC={ttc:.2f}s | dist={self.distance:.2f}m | v={self.velocity:.2f}m/s"
            )
            
        if self.aeb_triggered and self.velocity <= 0.01:
            self.aeb_triggered = False
            self.get_logger().info("✅ AEB reset — véhicule arrêté")
            return
            
        
        # --------------------------------------------------
        # 4) Obstacle proche + commande avant → bloque l'avance
        # --------------------------------------------------
        if self.distance < self.dist_threshold and self.cmd_vel > 0:
            cmd = Twist()
            cmd.angular.z = 83.0
            cmd.linear.x  = 0.0
            self.pub_cmd.publish(cmd)
            self.get_logger().warning(
                f"🛑 OBSTACLE TROP PROCHE | Tu ne peux pas avancer, il y a un obstacle ! | dist={self.distance:.2f}m"
            )


def main(args=None):
    rclpy.init(args=args)
    node = AEB()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
