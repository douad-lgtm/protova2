#!/usr/bin/env python3
"""
roamer.py v2 — exploration autonome complete pour ProtoVA2 (follow-the-gap
+ freinage actif + marche arriere de degagement).

Machine a etats :
  FWD    : avance en visant le passage le plus large (braque gauche/droite)
  BRAKE  : freinage ACTIF (impulsion inverse, calibree comme l'AEB)
  PAUSE  : neutre court (l'ESC exige neutre avant d'accepter la marche arriere)
  BACKUP : recule en contre-braquage pour pointer le nez vers le passage libre
           (surveille l'ARRIERE au lidar, s'arrete si obstacle derriere)
  PAUSE2 : neutre court puis retour en FWD

Publie /cmd_vel_nav (prio mux 10) — le G29 (30) et l'AEB (255) restent au-dessus.
Convention : angular.z = angle servo BRUT (83 ± 55), linear.x = fraction gaz.
Lidar : 0 = ARRIERE du robot -> avant a 180 deg.
"""
import math
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class Roamer(Node):
    def __init__(self):
        super().__init__('roamer')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.front_offset = math.radians(float(g('front_offset_deg', 180.0)))
        self.sector = math.radians(float(g('sector_deg', 70.0)))
        self.corridor = math.radians(float(g('corridor_deg', 18.0)))
        self.rear_corridor = math.radians(float(g('rear_corridor_deg', 25.0)))
        self.d_stop = float(g('d_stop', 0.45))      # m avant : arret/degagement
        self.d_slow = float(g('d_slow', 0.85))      # m avant : ralenti
        self.d_free = float(g('d_free', 0.70))      # m : seuil passage libre
        self.d_rear_stop = float(g('d_rear_stop', 0.35))  # m arriere : stop recul
        self.speed_cruise = float(g('speed_cruise', 0.16))
        self.speed_slow = float(g('speed_slow', 0.13))
        self.speed_back = float(g('speed_back', -0.25))
        self.brake_throttle = float(g('brake_throttle', -0.5))  # calibre AEB
        self.t_brake = float(g('t_brake', 0.4))     # s
        self.t_pause = float(g('t_pause', 0.35))    # s (neutre avant recul)
        self.t_backup = float(g('t_backup', 2.0))   # s de recul max
        self.steer_sign = float(g('steer_sign', 1.0))  # -1 si braquage inverse
        self.full_lock = math.radians(float(g('full_lock_deg', 30.0)))
        self.rmax = float(g('range_max', 4.0))
        self.stuck_time = float(g('stuck_time', 2.0))  # s bloque -> recul

        self.scan = None
        self.scan_time = 0.0
        self.throttle = 0.0
        self.state = 'FWD'
        self.t_state = self.now()
        self.t_blocked = None       # depuis quand on est bloque a l'arret
        self.phi_escape = 0.0       # direction du passage vise (pour le recul)

        self.wheel_vel = 0.0
        self.t_stall = None         # depuis quand on commande sans que ca roule
        self.create_subscription(LaserScan, '/scan', self.on_scan,
                                 qos_profile_sensor_data)
        self.create_subscription(Float32, '/velocity', self.on_vel, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel_nav', 10)
        self.create_timer(0.1, self.step)
        self.get_logger().info('Roamer v2 pret (avance/freine/recule) — /cmd_vel_nav')

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def on_scan(self, msg):
        self.scan = msg
        self.scan_time = self.now()

    def on_vel(self, msg):
        self.wheel_vel = float(msg.data)

    def set_state(self, s):
        if s != self.state:
            self.get_logger().info(f'etat: {self.state} -> {s}')
        self.state = s
        self.t_state = self.now()

    def servo(self, steer_norm):
        s = max(-1.0, min(1.0, steer_norm)) * self.steer_sign
        return 83.0 + 55.0 * s

    def analyse(self):
        """Retourne (d_front, d_rear, phi_target, gap_ok)."""
        s = self.scan
        r = np.asarray(s.ranges, dtype=np.float32)
        ang = s.angle_min + np.arange(r.size, dtype=np.float32) * s.angle_increment
        phi = np.vectorize(wrap)(ang - self.front_offset)
        bad = ~np.isfinite(r) | (r <= max(s.range_min, 0.05))
        r = np.where(bad, self.rmax, np.minimum(r, self.rmax))

        # arriere
        mr = np.abs(np.vectorize(wrap)(phi - math.pi)) <= self.rear_corridor
        d_rear = float(np.min(r[mr])) if np.any(mr) else self.rmax

        # secteur avant
        m = np.abs(phi) <= self.sector
        phi_s, r_s = phi[m], r[m]
        order = np.argsort(phi_s)
        phi_s, r_s = phi_s[order], r_s[order]
        if phi_s.size < 5:
            return self.rmax, d_rear, 0.0, False

        cor = np.abs(phi_s) <= self.corridor
        d_front = float(np.min(r_s[cor])) if np.any(cor) else self.rmax

        blocked = np.convolve((r_s < self.d_free).astype(float),
                              np.ones(11), mode='same') > 0
        free = ~blocked
        runs, cur_len, cur_start = [], 0, 0
        for i, f in enumerate(free):
            if f:
                if cur_len == 0:
                    cur_start = i
                cur_len += 1
            else:
                if cur_len:
                    runs.append((cur_start, cur_len))
                cur_len = 0
        if cur_len:
            runs.append((cur_start, cur_len))

        if runs:
            chosen = None
            for st, ln in runs:
                if phi_s[st] <= 0.0 <= phi_s[st + ln - 1]:
                    chosen = (st, ln)
                    break
            if chosen is None:
                chosen = max(runs, key=lambda x: x[1])
            st, ln = chosen
            return d_front, d_rear, float(phi_s[st + ln // 2]), True

        # aucun passage "libre" : on retient quand meme la direction la plus degagee
        i_best = int(np.argmax(r_s))
        return d_front, d_rear, float(phi_s[i_best]), False

    def step(self):
        cmd = Twist()
        cmd.angular.z = 83.0
        cmd.linear.x = 0.0
        t = self.now()

        if self.scan is None or t - self.scan_time > 1.0:
            self.throttle = 0.0
            self.pub.publish(cmd)      # pas de lidar -> neutre
            return

        d_front, d_rear, phi_t, gap_ok = self.analyse()
        dt_state = t - self.t_state

        if self.state == 'FWD':
            blocked_now = d_front < self.d_stop
            if blocked_now and self.throttle > 0.06:
                # on roulait -> freinage actif puis manoeuvre
                self.phi_escape = phi_t
                self.set_state('BRAKE')
            elif blocked_now:
                # deja a l'arret : patiente un peu puis recule
                if self.t_blocked is None:
                    self.t_blocked = t
                elif t - self.t_blocked > self.stuck_time:
                    self.phi_escape = phi_t
                    self.t_blocked = None
                    self.set_state('BRAKE')
                self.throttle = 0.0
            else:
                self.t_blocked = None
                target = self.speed_slow if (d_front < self.d_slow or not gap_ok) else self.speed_cruise
                self.throttle = 0.7 * self.throttle + 0.3 * target
                cmd.angular.z = self.servo(phi_t / self.full_lock)
                cmd.linear.x = float(self.throttle)
                # coince : on commande d'avancer mais les roues ne tournent pas
                if self.throttle > 0.10 and abs(self.wheel_vel) < 0.02 and dt_state > 1.5:
                    if self.t_stall is None:
                        self.t_stall = t
                    elif t - self.t_stall > self.stuck_time:
                        self.get_logger().warn('coince (gaz sans mouvement) -> degagement')
                        self.phi_escape = phi_t
                        self.t_stall = None
                        self.set_state('BRAKE')
                else:
                    self.t_stall = None

        elif self.state == 'BRAKE':
            cmd.linear.x = self.brake_throttle      # impulsion inverse = frein
            if dt_state > self.t_brake:
                self.throttle = 0.0
                self.set_state('PAUSE')

        elif self.state == 'PAUSE':
            cmd.linear.x = 0.0                      # neutre : l'ESC "arme" le recul
            if dt_state > self.t_pause:
                self.set_state('BACKUP')

        elif self.state == 'BACKUP':
            if d_rear < self.d_rear_stop or dt_state > self.t_backup:
                self.set_state('PAUSE2')
            else:
                # contre-braquage : en marche arriere, roues a l'oppose du
                # passage vise -> le nez pivote VERS le passage
                cmd.angular.z = self.servo(-math.copysign(1.0, self.phi_escape or 1.0))
                cmd.linear.x = self.speed_back

        elif self.state == 'PAUSE2':
            cmd.linear.x = 0.0
            if dt_state > self.t_pause:
                self.throttle = 0.0
                self.set_state('FWD')

        self.pub.publish(cmd)


def main():
    rclpy.init()
    rclpy.spin(Roamer())


if __name__ == '__main__':
    main()
