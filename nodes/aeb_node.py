#!/usr/bin/env python3
"""
Freinage d'urgence automatique GRADUE (AEB), complementaire de YOLO — ProtoVA.

Au lieu d'un arret tout-ou-rien, ce noeud module la vitesse en fonction de ce que
YOLO percoit. Il exploite les TROIS sorties de la detection :

  1) DISTANCE  -> freinage progressif : loin = rien, moyen = ralentit, proche = arret.
  2) CLASSE    -> priorite pieton : une "person" freine plus tot / avec plus de marge.
  3) POSITION  -> couloir : on ne reagit qu'aux obstacles DANS la trajectoire (centre
                  de l'image), pas a ceux sur les cotes.

La DIRECTION du conducteur est preservee : on plafonne seulement la vitesse. Comme
/cmd_vel_aeb est prioritaire (255) dans twist_mux, publier dessus reprend la main ;
quand aucun freinage n'est requis, on ne publie pas -> la conduite passe normalement.

Topics:
  abonne  /obstacle/detections (String JSON)  detections YOLO [{class,conf,distance_m,box}]
  abonne  <driver_topic> (Twist, def /cmd_vel_G29)  commande du conducteur (pour la direction)
  publie  /cmd_vel_aeb        (Twist)   commande limitee (prioritaire)
  publie  /obstacle/brake_level (Float32)  intensite de freinage 0..1 (pour affichage)

Params:
  driver_topic, corridor_frac, image_width, rate,
  d_slow, d_stop            (obstacle generique : distances debut/fin de freinage, m)
  d_slow_person, d_stop_person  (pieton : marges plus grandes)
"""
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32
from geometry_msgs.msg import Twist


class AEBNode(Node):
    def __init__(self):
        super().__init__('aeb_node')
        g = lambda n, d: self.declare_parameter(n, d).value
        self.driver_topic = g('driver_topic', '/cmd_vel_G29')
        self.corridor_frac = float(g('corridor_frac', 0.6))   # fraction centrale = couloir
        self.image_width = float(g('image_width', 1280.0))
        self.rate = float(g('rate', 20.0))
        self.d_slow = float(g('d_slow', 3.0))                 # obstacle : ralentir dès 3 m
        self.d_stop = float(g('d_stop', 1.0))                 # obstacle : arrêt à 1 m
        self.d_slow_person = float(g('d_slow_person', 4.0))   # piéton : ralentir dès 4 m
        self.d_stop_person = float(g('d_stop_person', 1.5))   # piéton : arrêt à 1,5 m
        self.det_timeout = float(g('det_timeout', 0.8))       # s sans détections -> conduite libre

        self.factor = 1.0            # facteur de vitesse 0..1 (1 = pas de freinage)
        self.reason = ''             # objet le plus critique (pour le log)
        self.driver = Twist()
        self.last_det = None

        self.pub = self.create_publisher(Twist, '/cmd_vel_aeb', 10)
        self.pub_lvl = self.create_publisher(Float32, '/obstacle/brake_level', 10)
        self.create_subscription(String, '/obstacle/detections', self.cb_det, 10)
        self.create_subscription(Twist, self.driver_topic, self.cb_driver, 10)
        self.create_timer(1.0 / self.rate, self.tick)
        self.get_logger().info(
            f"AEB gradué prêt : conduite={self.driver_topic}, couloir={self.corridor_frac}, "
            f"obstacle {self.d_stop}-{self.d_slow} m, piéton {self.d_stop_person}-{self.d_slow_person} m")

    # ---- entrées ----
    def cb_driver(self, msg):
        self.driver = msg

    def cb_det(self, msg):
        self.last_det = self.get_clock().now()
        try:
            dets = json.loads(msg.data)
        except ValueError:
            return
        factor, reason = 1.0, ''
        half = self.image_width / 2.0
        for d in dets:
            dist = d.get('distance_m')
            box = d.get('box')
            if dist is None or not box:
                continue
            cx = (box[0] + box[2]) / 2.0
            if abs(cx - half) > self.corridor_frac * half:    # hors du couloir -> ignoré
                continue
            f = self.obstacle_factor(dist, d.get('class', ''))
            if f < factor:
                factor, reason = f, f"{d.get('class')} à {dist} m"
        self.factor = factor
        self.reason = reason

    def obstacle_factor(self, dist, cls):
        """Facteur de vitesse 0..1 selon la distance (freinage progressif), classe-dépendant."""
        if cls == 'person':
            d_slow, d_stop = self.d_slow_person, self.d_stop_person
        else:
            d_slow, d_stop = self.d_slow, self.d_stop
        if dist >= d_slow:
            return 1.0
        if dist <= d_stop:
            return 0.0
        return (dist - d_stop) / (d_slow - d_stop)            # interpolation linéaire

    # ---- sortie ----
    def tick(self):
        # sécurité : détections trop anciennes -> pas de freinage (le conducteur garde la main)
        if self.last_det is not None:
            age = (self.get_clock().now() - self.last_det).nanoseconds * 1e-9
            if age > self.det_timeout:
                self.factor = 1.0

        self.pub_lvl.publish(Float32(data=float(1.0 - self.factor)))

        if self.factor >= 0.999:          # aucun freinage requis -> conduite normale (on ne publie pas)
            return

        t = Twist()
        v = self.driver.linear.x
        # on ne limite que la marche avant ; on garde la direction du conducteur
        t.linear.x = v * self.factor if v > 0.0 else v
        t.angular.z = self.driver.angular.z
        self.pub.publish(t)

        if self.factor <= 0.01:
            self.get_logger().warning(f"*** AEB : ARRET — {self.reason} ***",
                                      throttle_duration_sec=1.0)
        else:
            self.get_logger().info(
                f"AEB : ralentissement à {int(self.factor*100)}% ({self.reason})",
                throttle_duration_sec=1.0)


def main():
    rclpy.init()
    node = AEBNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
