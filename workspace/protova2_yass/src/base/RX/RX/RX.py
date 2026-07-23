#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import serial
import time
import numpy as np
from collections import deque
import tf_transformations
import numpy as np

from sensor_msgs.msg import Imu, MagneticField
from std_msgs.msg import Float32
from std_msgs.msg import Header


class RXNode(Node):

    def __init__(self):
        super().__init__('RX')

        # ==========================
        # PARAMÈTRES
        # ==========================
        self.declare_parameter('port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('frame_imu', 'imu_link')

        port = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
        self.frame_imu = self.get_parameter('frame_imu').value
        # ==========================
        # Variables
        # ==========================
        self.ticks = 0
        self.velocity = 0
        self.acceleration = 0
        self.jerk = 0
        self.voltage = 0
        self.steering_angle = 0
        self.angle_servo = 0
        self.imu_queue = deque(maxlen=50)
        self.enc_queue = deque(maxlen=50)
        self.str_queue = deque(maxlen=20)

        # ==========================
        # SERIAL
        # ==========================
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)
            self.get_logger().info(f"Connecté au port série {port}")
        except Exception as e:
            self.get_logger().error(f"Erreur ouverture port série: {e}")
            raise e

        # ==========================
        # PUBLISHERS
        # ==========================
        self.imu_pub = self.create_publisher(Imu, 'imu', 10)
        self.mag_pub = self.create_publisher(MagneticField, 'mag', 10)
        
        self.velocity_pub = self.create_publisher(Float32, 'velocity', 10)
        self.acc_pub = self.create_publisher(Float32, 'acc', 10)
        self.jerk_pub = self.create_publisher(Float32, 'jerk', 10)
        self.ticks_pub = self.create_publisher(Float32, 'ticks', 10)
        self.steering_angle_pub = self.create_publisher(Float32, 'steering_angle', 10)
        

        # ==========================
        # TIMERS (100 Hz)
        # ==========================
        self.serial_timer = self.create_timer(0.005, self.read_serial_cb)
        self.imu_timer = self.create_timer(0.005, self.read_IMU)
        self.enc_timer = self.create_timer(0.005, self.read_ENC)

    
    
    def read_serial_cb(self):
        while self.ser.in_waiting:
            line = self.ser.readline().decode('utf-8', errors='ignore').strip()

            if line.startswith("IMU"):
                self.imu_queue.append(line)
                #self.get_logger().info(f"{self.imu_queue}")

            elif line.startswith("MOTION"):
                self.enc_queue.append(line)

            elif line.startswith("STR"):
                self.str_queue.append(line)
            else :
                self.get_logger().warn(f"Message reçu depuis la pico: {line}")
    

    
    
    
    def read_ENC(self):
        if not self.enc_queue:
            return

        line = self.enc_queue.popleft()
        #self.get_logger().info(f"{line}")
        parts = line.split(',')
        #self.get_logger().info(f"{parts}")
        if len(parts) != 8:
            return
        try:
            _, ticks, vel, acc, jerk, voltage, steering_angle, angle_servo = parts
            self.ticks = float(ticks)
            self.velocity = float(vel)
            self.acceleration = float(acc)
            self.jerk = float(jerk)
            self.voltage = float(voltage)
            self.steering_angle = float(steering_angle)
            self.steering_angle = np.deg2rad(self.steering_angle)
            self.angle_servo = int(angle_servo)

            #now = self.get_clock().now().to_msg()
            #Publier la vitesse
            ticks_msg = Float32()
            ticks_msg.data = self.ticks
            self.ticks_pub.publish(ticks_msg)
            
            #Publier la vitesse
            velocity_msg = Float32()
            velocity_msg.data = self.velocity
            self.velocity_pub.publish(velocity_msg)
            
            #Publier l'accélération
            acc_msg = Float32()
            acc_msg.data = self.acceleration
            self.acc_pub.publish(acc_msg)
            
            #Publier le jerk
            jerk_msg = Float32()
            jerk_msg.data = self.jerk
            self.jerk_pub.publish(jerk_msg)
            
            #Publier l'angle de braquage
            steering_msg = Float32()
            steering_msg.data = self.steering_angle
            self.steering_angle_pub.publish(steering_msg)
        
        except ValueError:
            self.get_logger().warn(f"Conversion ENC échouée: {line}")


            

        
            
            
            
    
    
            
            
            
            
    def read_IMU(self):
        if not self.imu_queue:
            return

        line = self.imu_queue.popleft()
        #self.get_logger().info(f"{line}")

        parts = line.split(',')
        if len(parts) != 15:
            return

        try:
            _, ax, ay, az, gx, gy, gz, qx, qy, qz, qw, mx, my, mz, magAccuracy = parts

            ax, ay, az = float(ax), float(ay), float(az)
            gx, gy, gz = float(gx), float(gy), float(gz)
            qx, qy, qz, qw = float(qx), float(qy), float(qz), float(qw)
            mx, my, mz = float(mx), float(my), float(mz)
            magAccuracy = int(magAccuracy)
            #self.get_logger().info(f"{yaw}")
        except ValueError:
            return

        now = self.get_clock().now().to_msg()
        
        #if(magAccuracy == 0):
        #    self.get_logger().info("MAG Unreliable") 
        #if(magAccuracy == 1):
        #    self.get_logger().info("MAG Low") 
        #if(magAccuracy == 2):
        #    self.get_logger().info("MAG Medium") 
        #if(magAccuracy == 3):
        #    self.get_logger().info("MAG High") 

        # ==========================
        # IMU MSG
         # ==========================
        imu_msg = Imu()
        imu_msg.header = Header(stamp=now, frame_id=self.frame_imu)

        imu_msg.linear_acceleration.x = ax
        imu_msg.linear_acceleration.y = ay
        imu_msg.linear_acceleration.z = az

        imu_msg.angular_velocity.x = gx
        imu_msg.angular_velocity.y = gy
        imu_msg.angular_velocity.z = gz
            
        #quat = tf_transformations.quaternion_from_euler(roll,pitch,yaw,axes='sxyz')

        imu_msg.orientation.x = qx
        imu_msg.orientation.y = qy
        imu_msg.orientation.z = qz
        imu_msg.orientation.w = qw
        # ==========================
        # COVARIANCES (CRITIQUE)
        # ==========================

        # Orientation covariance (roll, pitch, yaw)
        imu_msg.orientation_covariance = [
          0.02, 0.0, 0.0,
          0.0, 0.02, 0.0,
          0.0, 0.0, 0.02
        ]

        # Angular velocity covariance
        imu_msg.angular_velocity_covariance = [
        0.02, 0.0, 0.0,
        0.0, 0.02, 0.0,
        0.0, 0.0, 0.02
        ]

        # Linear acceleration covariance
        imu_msg.linear_acceleration_covariance = [
        0.1, 0.0, 0.0,
        0.0, 0.1, 0.0,
        0.0, 0.0, 0.2
        ]
            
        self.imu_pub.publish(imu_msg)
        mag_msg = MagneticField()
        mag_msg.header = Header(stamp=now, frame_id=self.frame_imu)

        mag_msg.magnetic_field.x = mx
        mag_msg.magnetic_field.y = my
        mag_msg.magnetic_field.z = mz

        # Covariance (à ajuster selon ton capteur)
        mag_msg.magnetic_field_covariance = [
            0.01, 0.0, 0.0,
            0.0, 0.01, 0.0,
            0.0, 0.0, 0.01
          ]

        self.mag_pub.publish(mag_msg)
        

            

        


def main(args=None):
    rclpy.init(args=args)
    node = RXNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.ser.close()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
