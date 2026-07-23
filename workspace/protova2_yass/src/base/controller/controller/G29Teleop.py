import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
import serial
import time


class G29TeleopNode(Node):
    def __init__(self):
        super().__init__('g29_teleop')

        # Abonnement au joystick G29 (joy_node publie sur /joy)
        self.subscription = self.create_subscription(
            Joy,
            '/joy',                  # adapte si tu remappes le topic
            self.joy_callback,
            10
        )
        
        
        self.twist_publisher = self.create_publisher(Twist, '/cmd_vel_G29', 10)
        
        self.get_logger().info('G29 Teleop Node started, listening on /joy')

        # Paramètres servo 
        self.servo_center = 83
        self.servo_min = self.servo_center - 55
        self.servo_max = self.servo_center + 55
        
        # ================= PARAMÈTRES MOTEUR =================
        self.min_speed_fwd = 0.06
        self.max_speed_fwd = 0.2
        self.min_speed_bwd = -0.06
        self.max_speed_bwd = -0.35

        

        # Indices d’axes pour le G29 (à vérifier avec /joy)
        self.steer_axis = 0      # volant : -1 gauche, 0 centre, +1 droite
        self.throttle_axis = 2   # pédale accélération : -1 relâché, +1 appuyé
        self.brake_axis = 3      # pédale frein        : -1 relâché, +1 appuyé

        # "Sensibilité" volant : 1/4 de tour -> butée servo
        #  => si l'axe vaut ±0.33, on considère déjà ±1 côté servo
        self.steer_input_saturation = 0.33

        

        # ===== SERIAL USB =====
        self.serial_port = '/dev/ttyACM0'   # à adapter si besoin
        self.baudrate = 115200

        try:
            self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            time.sleep(2)  # laisser la Pico redémarrer
            self.get_logger().info('Serial connected to Pico')
        except Exception as e:
            self.get_logger().error(f'Serial error: {e}')
            self.ser = None

    
    
        
        
    def joy_callback(self, joy_msg: Joy):
        twist = Twist()
        

        # --- 1) Mapping SERVO (direction) avec saturation à 1/4 de tour ---
        steer_raw = joy_msg.axes[self.steer_axis]   # -1..1

        # On compresse l'entrée : 0.25 d'axe = 1.0 effectif
        # steer_scaled = steer_raw / 0.25, clampé dans [-1, 1]
        if abs(self.steer_input_saturation) < 1e-6:
            steer_scaled = steer_raw
        else:
            steer_scaled = steer_raw / self.steer_input_saturation
            if steer_scaled > 1.0:
                steer_scaled = 1.0
            elif steer_scaled < -1.0:
                steer_scaled = -1.0

        # Puis on applique ton mapping servo (identique, mais avec steer_scaled)
        angle = self.servo_center - steer_scaled * (self.servo_max - self.servo_center)
        twist.angular.z = angle

        # --- 2) Lecture des pédales G29 ---
        throttle_pedale_raw = joy_msg.axes[self.throttle_axis]  # [-1..1]
        brake_pedale_raw = joy_msg.axes[self.brake_axis]        # [-1..1]

        # Normalisation en [0..1] (0 relâché, 1 appuyé)
        throttle_pedale = (throttle_pedale_raw + 1.0) / 2.0
        brake_pedale = (brake_pedale_raw + 1.0) / 2.0  # frein et marche arrière 
        

        #
        v = throttle_pedale - brake_pedale

        
        # --- 5) Mapping v ∈ [-1..1] vers tes vitesses moteur ---
        if v> 0.0:
            # marche avant
            twist.linear.x = self.map(
                v,
                0.0, 1.0,
                self.min_speed_fwd, self.max_speed_fwd
            )
        elif v < 0.0:
            # marche arrière
            twist.linear.x = self.map(
                v,
                -1.0, 0.0,
                self.max_speed_bwd, self.min_speed_bwd
            )
        else:
            twist.linear.x = 0.0

        # ===== PUBLISH =====
        self.twist_publisher.publish(twist)

        # ===== ENVOI SERIAL angle,throttle =====
        #if self.ser is not None and self.ser.is_open:
        #    angle = int(twist.angular.z)
        #    throttle = twist.linear.x
        #    msg = f"CTRL,{twist.angular.z},{twist.linear.x:.3f}\n"
        #    self.ser.write(msg.encode('utf-8'))

            # debug
       #     self.get_logger().info(f"Envoyé via Serial -> {msg.strip()}")

    def map(self, x, in_min, in_max, out_min, out_max):
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

    def destroy_node(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
            self.get_logger().info('Serial connection closed')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = G29TeleopNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

