#!/usr/bin/env python3
"""
COURBE 2 — DÉBIT du lien PC <-> Jetson (le chemin de la teleoperation !).
Sur quoi ça se base : iperf3 envoie un flux TCP a fond entre les 2 machines
et mesure le debit reellement transfere CHAQUE SECONDE (sortie JSON -J,
champ intervals[]) -> chaque seconde = un point de la courbe.
Les 2 sens sont mesures : PC->Jetson (commandes) et Jetson->PC (video).
Le script demarre lui-meme le serveur iperf3 sur la Jetson (via SSH).

Usage : python3 mesure_debit.py [ip_jetson] [duree_s]   (defaut 10.37.11.34, 20 s)
"""
import json, subprocess, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

jetson = sys.argv[1] if len(sys.argv) > 1 else "10.37.11.34"
duree = int(sys.argv[2]) if len(sys.argv) > 2 else 20

# 1) demarrer le serveur iperf3 sur la Jetson (idempotent)
subprocess.run(["ssh", "-o", "ConnectTimeout=8", f"protova2@{jetson}",
                "pkill -x iperf3 2>/dev/null; nohup iperf3 -s >/dev/null 2>&1 & disown; echo ok"],
               capture_output=True, text=True, timeout=20)

def mesurer(sens_reverse):
    cmd = ["iperf3", "-c", jetson, "-t", str(duree), "-J"]
    if sens_reverse:
        cmd.append("-R")                      # -R = la Jetson emet, le PC recoit
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=duree + 15)
    d = json.loads(r.stdout)
    if "error" in d:
        sys.exit("iperf3 : " + d["error"])
    return [i["sum"]["bits_per_second"] / 1e6 for i in d["intervals"]]

print(f"debit PC->Jetson ({duree} s)...")
montant = mesurer(False)
print(f"debit Jetson->PC ({duree} s)...")
descendant = mesurer(True)

m1, m2 = sum(montant)/len(montant), sum(descendant)/len(descendant)
print(f"PC->Jetson : moy {m1:.0f} Mbps | Jetson->PC : moy {m2:.0f} Mbps")
open("debit_donnees.txt", "w").write(
    "PC->Jetson: " + " ".join(f"{x:.1f}" for x in montant) +
    "\nJetson->PC: " + " ".join(f"{x:.1f}" for x in descendant) + "\n")

plt.figure(figsize=(9, 4.5))
t1 = range(1, len(montant) + 1); t2 = range(1, len(descendant) + 1)
plt.fill_between(t1, montant, color="#1E783C", alpha=0.15)
plt.plot(t1, montant, color="#1E783C", marker="o", ms=4, lw=1.5,
         label=f"PC → Jetson (moy {m1:.0f} Mbps)")
plt.fill_between(t2, descendant, color="#DC8214", alpha=0.15)
plt.plot(t2, descendant, color="#DC8214", marker="o", ms=4, lw=1.5,
         label=f"Jetson → PC (moy {m2:.0f} Mbps)")
plt.title(f"Débit du lien PC ↔ Jetson (iperf3, {duree} s par sens)")
plt.xlabel("temps (s)"); plt.ylabel("Mbps")
plt.legend(); plt.grid(alpha=0.3); plt.ylim(bottom=0); plt.tight_layout()
plt.savefig("courbe_debit.png", dpi=130)
print("-> courbe_debit.png")
