#!/usr/bin/env python3
"""
COURBE 2 — DÉBIT « style speedtest » (comme fast.com).
Sur quoi ça se base : Linux compte TOUS les octets recus par chaque interface
reseau dans /sys/class/net/<iface>/statistics/rx_bytes. On lance plusieurs
telechargements en parallele (pour saturer la connexion, comme le fait un
speedtest), et chaque seconde on lit ce compteur :
    debit(t) = (octets_maintenant - octets_il_y_a_1s) x 8 / 1e6   [Mbps]

Usage : python3 mesure_debit.py [duree_s]     (defaut 20 s)
"""
import subprocess, sys, time
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

duree = int(sys.argv[1]) if len(sys.argv) > 1 else 20
URL = "https://proof.ovh.net/files/1Gb.dat"      # gros fichier public
FLUX = 4                                          # 4 telechargements paralleles

# interface qui porte l'internet (celle de la route par defaut)
route = subprocess.run(["ip", "route", "get", "8.8.8.8"],
                       capture_output=True, text=True).stdout
iface = route.split(" dev ")[1].split()[0]
compteur = f"/sys/class/net/{iface}/statistics/rx_bytes"
print(f"interface : {iface} | {FLUX} flux vers {URL} | {duree} s")

# lancer les telechargements (jetes dans /dev/null : seul le debit compte)
dls = [subprocess.Popen(["curl", "-s", "-o", "/dev/null",
                         "--max-time", str(duree + 2), URL]) for _ in range(FLUX)]

lire = lambda: int(open(compteur).read())
mbps, prev = [], lire()
for _ in range(duree):
    time.sleep(1)
    cur = lire()
    mbps.append((cur - prev) * 8 / 1e6)
    prev = cur
for p in dls:
    p.terminate()

moy = sum(mbps) / len(mbps)
print(f"debit : moy {moy:.1f} Mbps | pic {max(mbps):.1f}")
open("debit_donnees.txt", "w").write("\n".join(f"{m:.2f}" for m in mbps))

plt.figure(figsize=(9, 4.5))
t = range(1, len(mbps) + 1)
plt.fill_between(t, mbps, color="#1E783C", alpha=0.25)
plt.plot(t, mbps, color="#1E783C", marker="o", ms=4, lw=1.5)
plt.axhline(moy, color="#BE2828", ls="--", lw=1, label=f"moyenne {moy:.0f} Mbps")
plt.title(f"Débit Internet (style speedtest, {FLUX} flux, interface {iface})")
plt.xlabel("temps (s)"); plt.ylabel("Mbps")
plt.legend(); plt.grid(alpha=0.3); plt.ylim(bottom=0); plt.tight_layout()
plt.savefig("courbe_debit.png", dpi=130)
print("-> courbe_debit.png")
