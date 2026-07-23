import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
import serial
import time


class PS4TeleopNode(Node):
    def __init__(self):
        super().__init__('ps4_teleop')

        # ================= SUBSCRIPTIONS =================
        self.joy_sub = self.create_subscription(
            Joy, '/joy', self.joy_callback, 10)
        self.check_sub = self.create_subscription(
            Bool, '/bluetooth_status', self.bt_callback, 10)

        # ================= PUBLISHER =================
        self.twist_publisher = self.create_publisher(
            Twist, '/cmd_vel', 10)

        self.get_logger().info('PS4 Teleop Node started')

        # ================= SERIAL USB =================
        self.serial_port = '/dev/ttyACM0'
        self.baudrate = 115200

        try:
            self.ser = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            time.sleep(2)
            self.get_logger().info('Serial connected to Pico')
        except Exception as e:
            self.get_logger().error(f'Serial error: {e}')
            self.ser = None

        # ================= ÉTAT BLUETOOTH =================
        self.bt_connected = False

        # ================= PARAMÈTRES SERVO =================
        self.servo_center = 83.0
        self.servo_min = self.servo_center - 55.0
        self.servo_max = self.servo_center + 55.0

        # ================= PARAMÈTRES MOTEUR =================
        self.min_speed_fwd = 0
        self.max_speed_fwd = 0.2
        
    
        self.min_speed_bwd = 0
        self.max_speed_bwd = -1.0
        self.throttle = 0.0
        self.angle = 83

    # ================= CALLBACK BLUETOOTH =================
    def bt_callback(self, msg: Bool):
        self.bt_connected = msg.data
        #self.get_logger().info(f"reçu: {self.bt_connected}")
    # ================= CALLBACK JOYSTICK =================
    def joy_callback(self, joy_msg: Joy):

        twist = Twist()

        # ================= SÉCURITÉ BLUETOOTH =================
        if not self.bt_connected:
            self.get_logger().info("La manette n'est pas connectée")
        else:

            # ================= SERVO =================
            self.angle = self.servo_center - joy_msg.axes[0] * (self.servo_max - self.servo_center)
            twist.angular.z = float(self.angle)

            # ================= MOTEUR =================
            if joy_msg.axes[4] > 0:
                self.throttle = self.map(
                    joy_msg.axes[4],
                    0.0, 1.0,
                    self.min_speed_fwd, self.max_speed_fwd
                )
            elif joy_msg.axes[4] < 0:
                self.throttle = self.map(
                    joy_msg.axes[4],
                    -1.0, 0.0,
                    self.max_speed_bwd, self.min_speed_bwd
                )
            else:
                self.throttle = 0.0

        # ================= APPLY =================
        twist.linear.x = self.throttle

        # ================= PUBLISH =================
        self.twist_publisher.publish(twist)

        # ================= ENVOI SERIAL =================
        #if self.ser is not None and self.ser.is_open:
        #    msg = f"CTRL,{int(self.angle)},{self.throttle:.3f}\n"
        #    self.ser.write(msg.encode('utf-8'))
        #    self.get_logger().info(f"Envoyé via Serial -> {msg.strip()}")

    # ================= UTILS =================
    def map(self, x, in_min, in_max, out_min, out_max):
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def main(args=None):
    rclpy.init(args=args)
    node = PS4TeleopNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
