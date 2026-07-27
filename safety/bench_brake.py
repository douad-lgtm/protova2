#!/usr/bin/env python3
"""
bench_brake.py — banc de mesure du temps d'arrêt (roues en l'air).

Compare, mesures encodeur (/velocity) à l'appui :
  Essai 1 (roue libre)  : avance 0.18 m/s 2 s, puis throttle 0.0
  Essai 2 (frein actif) : avance 0.18 m/s 2 s, puis -0.30 pendant 0.30 s, puis 0.0

Publie sur /cmd_vel_aeb (priorité twist_mux 255 — mais ici TX écoute /cmd_vel, donc
on publie DIRECTEMENT sur /cmd_vel car twist_mux n'est pas lancé sur ce banc minimal).
Mesure le temps entre la coupure des gaz et velocity < seuil. Affiche un rapport.
"""
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32

SERVO_CENTER = 83.0
V_FWD = 0.18
V_BRAKE = -0.30
T_FWD = 2.0
T_BRAKE = 0.30
V_STOPPED = 0.15     # seuil "arrêté" sur /velocity
TIMEOUT = 6.0


class Bench(Node):
    def __init__(self):
        super().__init__('bench_brake')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.vel = 0.0
        self.create_subscription(Float32, '/velocity', self.cb, 10)

    def cb(self, m):
        self.vel = float(m.data)

    def send(self, vx):
        t = Twist()
        t.linear.x = float(vx)
        t.angular.z = SERVO_CENTER
        self.pub.publish(t)

    def run_for(self, vx, dur):
        t0 = time.time()
        while time.time() - t0 < dur:
            self.send(vx)
            rclpy.spin_once(self, timeout_sec=0.02)
            time.sleep(0.02)

    def wait_stop(self):
        """Après coupure : envoie 0 en continu, mesure le temps jusqu'à l'arrêt."""
        t0 = time.time()
        vmax = self.vel
        while time.time() - t0 < TIMEOUT:
            self.send(0.0)
            rclpy.spin_once(self, timeout_sec=0.02)
            vmax = max(vmax, abs(self.vel))
            if abs(self.vel) < V_STOPPED:
                return time.time() - t0, vmax
            time.sleep(0.02)
        return None, vmax

    def trial(self, name, brake):
        print(f"--- {name} ---", flush=True)
        self.run_for(V_FWD, T_FWD)
        v_launch = self.vel
        print(f"vitesse atteinte : {v_launch:.2f}", flush=True)
        if brake:
            self.run_for(V_BRAKE, T_BRAKE)      # impulsion de frein
        t_stop, vmax = self.wait_stop()
        if t_stop is None:
            print(f"PAS ARRETE en {TIMEOUT}s (velocity={self.vel:.2f})", flush=True)
        else:
            extra = T_BRAKE if brake else 0.0
            print(f"TEMPS D'ARRET : {t_stop + extra:.2f} s "
                  f"(depuis la coupure des gaz)", flush=True)
        self.run_for(0.0, 1.5)                  # repos entre essais
        return t_stop


def main():
    rclpy.init()
    n = Bench()
    # attendre les liaisons
    for _ in range(30):
        rclpy.spin_once(n, timeout_sec=0.1)
    print("=== BANC DE FREINAGE (roues en l'air) ===", flush=True)
    t1 = n.trial("Essai 1 : ROUE LIBRE (throttle 0)", brake=False)
    t2 = n.trial("Essai 2 : FREIN ACTIF (-0.30 pendant 0.30 s)", brake=True)
    print("=== BILAN ===", flush=True)
    print(f"roue libre : {t1 if t1 is not None else '>6'} s | "
          f"frein actif : {(t2 + T_BRAKE) if t2 is not None else '>6'} s", flush=True)
    n.send(0.0)
    n.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
