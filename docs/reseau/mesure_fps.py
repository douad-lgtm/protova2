#!/usr/bin/env python3
"""
COURBE 3 — FPS de la caméra recus a travers le reseau.
Sur quoi ça se base : un mini-noeud ROS 2 s'abonne au topic des images
compressees de la camera ; il INCREMENTE un compteur a chaque image recue,
et note ce compteur chaque seconde (puis le remet a zero) :
    fps(t) = nombre d'images arrivees pendant la seconde t

Prerequis : la camera publie (launch_camera.sh sur la Jetson) et l'env ROS
est charge (ROS_DOMAIN_ID=125, FastDDS pour le WiFi).
Usage : python3 mesure_fps.py [duree_s]      (defaut 60 s)
"""
import sys, time
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

duree = int(sys.argv[1]) if len(sys.argv) > 1 else 60
import os
# zenoh = chemin 5G ; FastDDS = chemin WiFi
reseau = "5G" if "zenoh" in os.environ.get("RMW_IMPLEMENTATION", "") else "WiFi"
TOPIC = "/camera/color/image_raw/compressed"

class Compteur(Node):
    def __init__(self):
        super().__init__("mesure_fps")
        self.n = 0
        self.create_subscription(CompressedImage, TOPIC,
                                 lambda m: setattr(self, "n", self.n + 1),
                                 qos_profile_sensor_data)

rclpy.init()
node = Compteur()
print(f"comptage des images sur {TOPIC} pendant {duree} s ...")
fps = []
fin = time.time() + duree
while time.time() < fin:
    tick = time.time() + 1.0
    node.n = 0
    while time.time() < tick:
        rclpy.spin_once(node, timeout_sec=0.05)
    fps.append(node.n)
rclpy.shutdown()

moy = sum(fps) / len(fps)
print(f"FPS : moy {moy:.1f} | min {min(fps)} | max {max(fps)}")
open("fps_donnees.txt", "w").write("\n".join(map(str, fps)))

plt.figure(figsize=(9, 4.5))
plt.plot(range(1, len(fps) + 1), fps, color="#14508C", marker=".", lw=1.2)
plt.axhline(moy, color="#BE2828", ls="--", lw=1, label=f"moyenne {moy:.1f} FPS")
plt.title(f"FPS caméra — réseau {reseau}")
plt.xlabel("temps (s)"); plt.ylabel("images/s")
plt.legend(); plt.grid(alpha=0.3); plt.ylim(0, max(fps) + 5); plt.tight_layout()
plt.savefig("courbe_fps.png", dpi=130)
print("-> courbe_fps.png")
