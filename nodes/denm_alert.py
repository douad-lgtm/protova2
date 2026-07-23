#!/usr/bin/env python3
"""
Afficheur d'ALERTE V2V — vehicule qui RECOIT (ProtoVA).
S'abonne a /v2v/denm (publie par v2v_node quand un DENM est recu) et affiche une
alerte bien visible dans le terminal : un autre vehicule signale un danger/freinage.
"""
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

CAUSES = {
    99: "Situation dangereuse",
    97: "Risque de collision",
    10: "Obstacle sur la route",
    11: "Animal sur la route",
}
SUBCAUSES = {2: "freinage d'urgence"}


class DenmAlert(Node):
    def __init__(self):
        super().__init__('denm_alert')
        self.create_subscription(String, '/v2v/denm', self.cb, 10)
        self.get_logger().info("En attente d'alertes DENM sur /v2v/denm ...")

    def cb(self, msg):
        try:
            d = json.loads(msg.data)
        except ValueError:
            return
        cause = CAUSES.get(d.get('cause'), f"cause {d.get('cause')}")
        sub = SUBCAUSES.get(d.get('subcause'), '')
        lat, lon = d.get('lat'), d.get('lon')
        dist = d.get('distance_m')
        bar = "=" * 64
        lines = ["", bar,
                 f"  *** ALERTE V2V ***  FREINAGE D'URGENCE signalé par le véhicule {d.get('from_id')}",
                 f"  Un véhicule voisin freine pour un danger détecté devant lui.",
                 f"  Cause : {cause}" + (f" ({sub})" if sub else "")]
        if dist is not None:
            lines.append(f"  Distance au véhicule émetteur : ~{dist} m (positions relatives)")
        lines += [bar, ""]
        print("\n".join(lines), flush=True)


def main():
    rclpy.init()
    try:
        rclpy.spin(DenmAlert())
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
