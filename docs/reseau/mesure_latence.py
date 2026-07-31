#!/usr/bin/env python3
"""
COURBE 1 — LATENCE réseau (ping).
Sur quoi ça se base : la commande systeme `ping` envoie un paquet ICMP par
intervalle ; la cible repond ; le temps aller-retour (RTT) de CHAQUE paquet
est extrait de la sortie ("time=12.3 ms") -> un point de la courbe.

Usage : python3 mesure_latence.py [cible] [duree_s]
        (defaut : 10.37.11.34, 30 s)
"""
import re, subprocess, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

cible = sys.argv[1] if len(sys.argv) > 1 else "10.37.11.34"
duree = int(sys.argv[2]) if len(sys.argv) > 2 else 30
# nom du reseau deduit de l'IP cible (pour le titre de la courbe)
reseau = "5G" if cible.startswith("172.16.48.") else ("WiFi" if cible.startswith("10.37.") else cible)
INTERVALLE = 0.2                      # 1 ping toutes les 0,2 s
n = int(duree / INTERVALLE)

print(f"ping {cible} : {n} paquets sur {duree} s ...")
sortie = subprocess.run(["ping", "-i", str(INTERVALLE), "-c", str(n), cible],
                        capture_output=True, text=True).stdout
rtt = [float(m) for m in re.findall(r"time=([\d.]+)", sortie)]
if not rtt:
    sys.exit("aucune reponse au ping !")

temps = [i * INTERVALLE for i in range(len(rtt))]
moy = sum(rtt) / len(rtt)
print(f"RTT : moy {moy:.1f} ms | min {min(rtt):.1f} | max {max(rtt):.1f} | perdus {n-len(rtt)}")

open("latence_donnees.txt", "w").write("\n".join(map(str, rtt)))
plt.figure(figsize=(9, 4.5))
plt.plot(temps, rtt, color="#14508C", lw=1)
plt.axhline(moy, color="#BE2828", ls="--", lw=1, label=f"moyenne {moy:.1f} ms")
plt.title(f"Latence — réseau {reseau}")
plt.xlabel("temps (s)"); plt.ylabel("RTT (ms)")
plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
plt.savefig("courbe_latence.png", dpi=130)
print("-> courbe_latence.png")
