#!/usr/bin/env python3

import math
import rclpy
from rclpy.node import Node

from std_msgs.msg import Float32
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped, Quaternion, Point, Vector3
from geometry_msgs.msg import TwistWithCovarianceStamped
from tf2_ros import TransformBroadcaster
from tf_transformations import quaternion_from_euler
from sensor_msgs.msg import Imu
from tf_transformations import euler_from_quaternion


class AckermannOdometryNode(Node):
    """Calcule et publie l'odométrie d'un robot à direction Ackermann."""

    def __init__(self):
        super().__init__("ackermann_odometry")

        # ── Paramètres ──────────────────────────────────────────────────────
        self.declare_parameter("wheelbase", 0.245)          # L [m]
        self.declare_parameter("odom_frame_id", "odom")
        self.declare_parameter("base_frame_id", "base_link")
        self.declare_parameter("publish_tf", True)
        self.declare_parameter("update_rate", 50.0)         # Hz

        self.L: float = float(self.get_parameter("wheelbase").value)
        self.odom_frame: str = self.get_parameter("odom_frame_id").value
        self.base_frame: str = self.get_parameter("base_frame_id").value
        self.publish_tf: bool = bool(self.get_parameter("publish_tf").value)
        update_rate: float = float(self.get_parameter("update_rate").value)

        self.get_logger().info(
            f"Ackermann Odometry — L={self.L:.3f} m  (bicycle model)"
        )

        # ── État du robot ────────────────────────────────────────────────────
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0  # yaw [rad]
        
        self.x_imu = 0.0
        self.y_imu = 0.0
        self.theta_imu = 0.0
        self.omega_imu = 0.0

        self.velocity = 0.0       # v [m/s]
        self.steering_angle = 0.0 # δ [rad]

        self._last_time = None

        # ── Subscribers ──────────────────────────────────────────────────────
        self.create_subscription(Float32, "/velocity", self._velocity_cb, 10)
        self.create_subscription(Float32, "/steering_angle", self._steering_cb, 10)
        self.create_subscription(Imu, "/imu", self._imu_cb, 10)

        # ── Publisher odométrie ──────────────────────────────────────────────
        self._odom_pub = self.create_publisher(Odometry, "/odom_ackermann", 10)
        self._odom_imu_pub = self.create_publisher(Odometry, "/odom_imu", 10)
        self._twist_pub = self.create_publisher(TwistWithCovarianceStamped,  "/twist",10)

        # ── TF broadcaster ───────────────────────────────────────────────────
        if self.publish_tf:
            self._tf_broadcaster = TransformBroadcaster(self)
        else:
            self._tf_broadcaster = None

        # ── Timer d'intégration ──────────────────────────────────────────────
        self.create_timer(1.0 / update_rate, self._update)

    # ── Callbacks subscribers ────────────────────────────────────────────────
    def _velocity_cb(self, msg: Float32) -> None:
        self.velocity = float(msg.data)

    def _steering_cb(self, msg: Float32) -> None:
        self.steering_angle = float(msg.data)
        
    def _imu_cb(self, msg: Imu):
        q = msg.orientation
        _, _, yaw = euler_from_quaternion([q.x, q.y, q.z, q.w])
        
        self.theta_imu = yaw
        self.omega_imu = msg.angular_velocity.z
        self.get_logger().info(f"Yaw (rad): {yaw:.3f}")

    # ── Boucle d'intégration ─────────────────────────────────────────────────
    def _update(self) -> None:
        now: float = self.get_clock().now().nanoseconds * 1e-9  # s

        if self._last_time is None:
            self._last_time = now
            return

        dt: float = now - self._last_time
        self._last_time = now

        if dt <= 0.0:
            return

        

        v = self.velocity
        delta = self.steering_angle
        theta_imu = self.theta_imu 
        omega_imu = self.omega_imu 
        

        # ── Modèle cinématique Ackermann — Modèle Bicyclette ───────
        # ω = v * tan(δ) / L
        # distances CG
        L = self.L

        # slip angle beta

        # vitesse angulaire corrigée
        omega = (v / L) * math.tan(delta)

        theta_old = self.theta
        self.theta += omega * dt

        # intégration avec beta
        self.x += v * math.cos(theta_old ) * dt
        self.y += v * math.sin(theta_old) * dt
        
        
        #self.get_logger().info(f"x: {self.x:.3f}, y: {self.y:.3f}, theta: {self.theta:.3f}")
        

        # Normalisation de l'angle dans [-π, π]
        self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))

        # Vitesses corps (repère base_link)
        vx_body: float = v
        vy_body: float = 0.0

        # ── Quaternion ────────────────────────────────────────────────────
        qx, qy, qz, qw = quaternion_from_euler(0.0, 0.0, self.theta)
        q = Quaternion(x=qx, y=qy, z=qz, w=qw)

        # ── Message Odometry ──────────────────────────────────────────────
        time_msg = self.get_clock().now().to_msg()

        odom = Odometry()
        odom.header.stamp = time_msg
        odom.header.frame_id = self.odom_frame
        odom.child_frame_id = self.base_frame

        # Pose
        odom.pose.pose.position = Point(x=self.x, y=self.y, z=0.0)
        odom.pose.pose.orientation = q

        # Twist (dans le repère robot)
        odom.twist.twist.linear = Vector3(x=vx_body, y=vy_body, z=0.0)
        odom.twist.twist.angular = Vector3(x=0.0, y=0.0, z=omega)

        # Covariances diagonales (à calibrer)
        odom.pose.covariance[0] = 0.1    # var(x)
        odom.pose.covariance[7] = 0.1    # var(y)
        odom.pose.covariance[35] = 0.01   # var(yaw)
        odom.twist.covariance[0] = 0.1   # var(vx)
        odom.twist.covariance[7] = 0.1   # var(vy)
        odom.twist.covariance[35] = 0.01 # var(ω)

        self._odom_pub.publish(odom)
        
        #-------- ODOM IMU -----------
        self.x_imu += v * math.cos(theta_imu) * dt
        self.y_imu += v * math.sin(theta_imu) * dt
        
        qx2, qy2, qz2, qw2 = quaternion_from_euler(0.0, 0.0, self.theta_imu)
        q_imu = Quaternion(x=qx2, y=qy2, z=qz2, w=qw2)
        odom_imu = Odometry()
        odom_imu.header.stamp = time_msg
        odom_imu.header.frame_id = self.odom_frame
        odom_imu.child_frame_id = self.base_frame

        odom_imu.pose.pose.position = Point(x=self.x_imu, y=self.y_imu, z=0.0) 
        odom_imu.pose.pose.orientation = q_imu

        odom_imu.twist.twist.linear = Vector3(x=v, y=0.0, z=0.0)
        odom_imu.twist.twist.angular = Vector3(x=0.0, y=0.0, z=omega_imu)
        # Covariances diagonales (à calibrer)
        odom_imu.pose.covariance[0] = 0.1    # var(x)
        odom_imu.pose.covariance[7] = 0.01    # var(y)
        odom_imu.pose.covariance[35] = 0.01   # var(yaw)
        odom_imu.twist.covariance[0] = 0.1   # var(vx)
        odom_imu.twist.covariance[7] = 0.1   # var(vy)
        odom_imu.twist.covariance[35] = 0.01 # var(ω)

        self._odom_imu_pub.publish(odom_imu)
        
        # ── Message TwistWithCovarianceStamped (/twist_imu) ──────────────
        #
        #   vx      → vitesse linéaire encodeur  (fiable en X)
        #   omega_z → vitesse angulaire IMU       (fiable en yaw)
        #
        #   robot_localization utilisera uniquement ce twist
        #   (pas de double intégration IMU sur la position)
        #
        twist_msg = TwistWithCovarianceStamped()
        twist_msg.header.stamp    = time_msg
        twist_msg.header.frame_id = self.base_frame  # repère robot !
 
        twist_msg.twist.twist.linear  = Vector3(x=v,   y=0.0, z=0.0)
        twist_msg.twist.twist.angular = Vector3(x=0.0, y=0.0, z=omega_imu)
        # Covariances — vx bien connu, omega_imu très bon → variances faibles
        cov = [0.0] * 36
        cov[0]  = 0.08   # var(vx)   — encodeur fiable
        cov[7]  = 1e6    # var(vy)   — non observé, laisser grand
        cov[14] = 1e6    # var(vz)   — non observé
        cov[21] = 1e6    # var(ωx)
        cov[28] = 1e6    # var(ωy)
        cov[35] = 0.005  # var(ωz)   — IMU très fiable
        twist_msg.twist.covariance = cov
 
        self._twist_pub.publish(twist_msg)

        # ── TF odom → base_link ───────────────────────────────────────────
        if self.publish_tf and self._tf_broadcaster is not None:
            tf = TransformStamped()
            tf.header.stamp = time_msg
            tf.header.frame_id = self.odom_frame
            tf.child_frame_id = self.base_frame
            tf.transform.translation.x = self.x
            tf.transform.translation.y = self.y
            tf.transform.translation.z = 0.0
            tf.transform.rotation = q
            self._tf_broadcaster.sendTransform(tf)




def main(args=None):
    rclpy.init(args=args)
    node = AckermannOdometryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()