#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.interpolate import interp1d


from geometry_msgs.msg import Twist
import serial


class CmdVelStampedToSerial(Node):

    def __init__(self):
        super().__init__('cmd_vel_stamped_to_serial')

        # =============================
        # PARAMÈTRES ROS2
        # =============================
        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('servo_center', 83)
        #self.declare_parameter('deadzone', 0.08)
        

        

        self.serial_port = self.get_parameter('serial_port').value
        self.baudrate = self.get_parameter('baudrate').value
        self.servo_center = self.get_parameter('servo_center').value
        #self.deadzone = self.get_parameter('deadzone').value
        
        # =============================
        # ineterpolation moteur
        # =============================


        #self.x_table = np.array([
   # -4.500, -4.500, -4.500, -4.500, -4.500, -4.500, -4.500, -4.500, -4.500, -4.500, -4.500, -4.499, -4.497, -4.493, -4.488, -4.483, -4.477, -4.472, -4.467, -4.463, -4.460, -4.458, -4.456, -4.454, -4.452, -4.450, -4.449, -4.447, -4.446, -4.446, -4.445, -4.445, -4.444, -4.444, -4.444, -4.444, -4.444, -4.444, -4.444, -4.443, -4.443, -4.442, -4.439, -4.435, -4.429, -4.421, -4.413, -4.402, -4.390, -4.377, -4.362, -4.330, -4.273, -4.203, -4.131, -4.069, -4.019, -3.972, -3.926, -3.878, -3.824, -3.762, -3.694, -3.622, -3.545, -3.467, -3.385, -3.298, -3.208, -3.117, -3.025, -2.935, -2.844, -2.752, -2.657, -2.557, -2.452, -2.341, -2.226, -2.110, -1.992, -1.876, -1.760, -1.640, -1.514, -1.378, -1.232, -1.078, -0.912, -0.729, -0.527, -0.210, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.000, 0.210, 0.527, 0.729, 0.912, 1.078, 1.232, 1.378, 1.514, 1.640, 1.760, 1.876, 1.992, 2.110, 2.226, 2.341, 2.452, 2.557, 2.657, 2.752, 2.844, 2.935, 3.025, 3.117, 3.208, 3.298, 3.385, 3.467, 3.545, 3.622, 3.694, 3.762, 3.824, 3.878, 3.926, 3.972, 4.019, 4.069, 4.131, 4.203, 4.273, 4.330, 4.362, 4.377, 4.390, 4.402, 4.413, 4.421, 4.429, 4.435, 4.439, 4.442, 4.443, 4.443, 4.444, 4.444, 4.444, 4.444, 4.444, 4.444, 4.444, 4.445, 4.445, 4.446, 4.446, 4.447, 4.449, 4.450, 4.452, 4.454, 4.456, 4.458, 4.460, 4.463, 4.467, 4.472, 4.477, 4.483, 4.488, 4.493, 4.497, 4.499, 4.500, 4.500, 4.500, 4.500, 4.500, 4.500, 4.500, 4.500, 4.500, 4.500, 4.500
#])     
        
       # self.y_table = np.array([
  #  -1.00, -0.99, -0.98, -0.97, -0.96, -0.95, -0.94, -0.93, -0.92, -0.91, -0.90, -0.89, -0.88, -0.87, -0.86, -0.85, -0.84, -0.83, -0.82, -0.81, -0.80, -0.79, -0.78, -0.77, -0.76, -0.75, -0.74, -0.73, -0.72, -0.71, -0.70, -0.69, -0.68, -0.67, -0.66, -0.65, -0.64, -0.63, -0.62, -0.61, -0.60, -0.59, -0.58, -0.57, -0.56, -0.55, -0.54, -0.53, -0.52, -0.51, -0.50, -0.49, -0.48, -0.47, -0.46, -0.45, -0.44, -0.43, -0.42, -0.41, -0.40, -0.39, -0.38, -0.37, -0.36, -0.35, -0.34, -0.33, -0.32, -0.31, -0.30, -0.29, -0.28, -0.27, -0.26, -0.25, -0.24, -0.23, -0.22, -0.21, -0.20, -0.19, -0.18, -0.17, -0.16, -0.15, -0.14, -0.13, -0.12, -0.11, -0.10, -0.09, -0.08, -0.07, -0.06, -0.05, -0.04, -0.03, -0.02, -0.01, 0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19, 0.20, 0.21, 0.22, 0.23, 0.24, 0.25, 0.26, 0.27, 0.28, 0.29, 0.30, 0.31, 0.32, 0.33, 0.34, 0.35, 0.36, 0.37, 0.38, 0.39, 0.40, 0.41, 0.42, 0.43, 0.44, 0.45, 0.46, 0.47, 0.48, 0.49, 0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.56, 0.57, 0.58, 0.59, 0.60, 0.61, 0.62, 0.63, 0.64, 0.65, 0.66, 0.67, 0.68, 0.69, 0.70, 0.71, 0.72, 0.73, 0.74, 0.75, 0.76, 0.77, 0.78, 0.79, 0.80, 0.81, 0.82, 0.83, 0.84, 0.85, 0.86, 0.87, 0.88, 0.89, 0.90, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99, 1.00
#])
        
        # une autre fonction d'ineterpolation mais la PCHIP était meilleure 

        #self.interp2 = interp1d(
    #y,                  # valeurs d'entrée
    #x,                  # valeurs correspondantes
    #kind='cubic',      # type d'interpolation: 'linear', 'nearest', 'zero', 'slinear', 'quadratic', 'cubic'
    #axis=-1,            # axe le long duquel interpoler (utile pour tableaux multidimensionnels)
    #copy=True,          # si True, copie x et y
    #bounds_error=False, # si True, lève une erreur pour x hors de l'intervalle, sinon utilise fill_value
    #fill_value="extrapolate",  # valeur de sortie pour x hors de l'intervalle, ou "extrapolate" pour extrapoler
    #assume_sorted=True # si True, x doit être trié, sinon il sera trié automatiquement
#)

        
        

        # =============================
        # SERIAL
        # =============================
        self.ser = None
        try:
            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
                timeout=0.01
            )
            self.get_logger().info(
                f"Serial ouvert sur {self.serial_port} @ {self.baudrate}"
            )
        except serial.SerialException as e:
            self.get_logger().error(f"Erreur ouverture serial: {e}")

        # =============================
        # SUBSCRIBER
        # =============================
        self.sub = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.cmd_vel_callback,
            10
        )

        self.get_logger().info('Serial TX node started')

    # =============================
    # CALLBACK
    # =============================
    #def fast_interp(self, val):
    #    y = self.y_table
    #    x = self.x_table

        # saturation
    #    if val <= x[0]:
    #        return y[0]
    #    if val >= x[-1]:
    #        return y[-1]

        # index à droite
    #    idx = np.searchsorted(x, val)

    #    x0, x1 = x[idx-1], x[idx]
    #    y0, y1 = y[idx-1], y[idx]

        # interpolation linéaire
    #    return y0 + (val - x0) * (y1 - y0) / (x1 - x0)

    
    def cmd_vel_callback(self, msg: Twist):

        # Extraction
        v = msg.linear.x
        #if -self.deadzone <= v <= self.deadzone:
            #throttle = 0
        #angle = -126.0507149*msg.twist.angular.z+93
        angle = msg.angular.z
        throttle = v
        #throttle = self.fast_interp(v)
        #if -0.08 <= throttle <= 0.08:
        #    throttle = 0
        #angle = -126.0507149*msg.twist.angular.z+93
        
        angle = int(angle)
        serial_msg = f"CTRL,{angle},{throttle:.3f}\n"
        self.get_logger().info(       f"{serial_msg.strip()}")

        # =============================
        # ENVOI SERIAL
        # =============================
        if self.ser is not None and self.ser.is_open:
            serial_msg = f"CTRL,{angle},{throttle:.3f}\n"
            self.ser.write(serial_msg.encode('utf-8'))

            self.get_logger().debug(
                f"Envoyé via Serial -> {serial_msg.strip()}"
           )

    # =============================
    # CLEANUP
    # =============================
    def destroy_node(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
            self.get_logger().info('Serial fermé')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CmdVelStampedToSerial()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()

