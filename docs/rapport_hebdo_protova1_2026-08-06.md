# 📅 Rapport hebdomadaire — ProtoVA1 : remise en service et téléopération

**Douae Sebti — PFE ALTEN Labs (ProtoVA) · Semaine du 3 au 6 août 2026**

## 🎯 Objectif de la semaine

Rendre **ProtoVA1** (Jetson Nano, ROS 2 Foxy) de nouveau **pleinement téléopérable** au volant Logitech G29 avec retour de force, en intégrant le nouvel encodeur avec son étage de filtrage — première étape vers la démonstration finale : **deux plateformes opérationnelles échangeant des messages V2V (DENM)**.

**✅ Objectif atteint : la voiture a roulé au sol, téléopérée au G29 avec retour de force.**

## 🔗 Architecture mise en place

```
G29 + retour de force (PC)
   → joy_node → pont UDP /joy (maison)
      → Jetson Nano : g29_teleop → twist_mux → nœud TX (série USB)
         → Raspberry Pi Pico (FreeRTOS) → servo de direction + ESC moteur
         ← TICKS encodeur (40/tour) → topic /velocity
```

## ✅ Travaux réalisés

### 1. Firmware Raspberry Pi Pico (réécrit, compilé, flashé)
- **FreeRTOS**, 3 tâches : réception série (`CTRL,angle,vitesse`), contrôle servo+ESC, encodeur (`TICKS,n` à 50 Hz)
- **Recalibration du neutre ESC : 1400 → 1500 µs** — bug critique, à 1400 µs la voiture partait en marche arrière rapide sur la commande « stop »
- **Armement ESC automatique** : le signal neutre est désormais émis dès la mise sous tension (avant : il fallait débrancher/rebrancher l'alimentation à chaque session, le firmware attendait l'ouverture du port série avant de sortir le moindre signal)

### 2. Encodeur KY-040 + conditionnement du signal
- Chaîne validée : encodeur → filtre RC → trigger de Schmitt **74HC14** → Pico (élimination des rebonds mécaniques)
- Étude des décodages possibles (×1 = 20, ×2 = 40, ×4 = 80 ticks/tour) → **décodage ×2 retenu : 40 ticks/tour**
- Paramètres d'odométrie mis en cohérence côté ROS (`ticks_per_rev = 40` dans TX et ackermann_odom)

### 3. Réseau : pont UDP /joy
- Diagnostic : le partage de connexion utilisé **bloque les données DDS** entre machines (la découverte passe, les données non) — vérifié objectivement (UDP brut OK dans les deux sens)
- Développement d'un **pont UDP unicast** dédié : le PC envoie /joy en texte sur le port 9001, la Jetson le republie localement → interopérabilité Humble (PC) ↔ Foxy (Jetson) rétablie

### 4. Pile logicielle Jetson
- `twist_mux` installé et configuré (priorités : AEB 255 > PS4 60 > G29 30) — prêt pour l'arrivée d'un freinage d'urgence coopératif
- Script de lancement unique (`launch_teleop_p1.sh`) + service systemd `p1teleop` (résilient aux coupures SSH)
- Runbook complet documenté (flash → armement → 4 terminaux → conduite → diagnostic)

### 5. Premier roulage au sol et itération de réglages
Constats du premier essai → corrections immédiates :

| Constat | Cause | Correction |
|---|---|---|
| Retards à l'accélération | Consigne minimale dans la zone morte de l'ESC | Minimum relevé au-dessus de la zone morte |
| Vitesse bridée | Pédale à fond = 20 % de puissance seulement | Plage élargie à 35 % (ajustable) |
| Manque de précision | Course de pédale écrasée sur une plage étroite | Plage élargie → meilleure résolution |
| ESC à réarmer en débranchant | Firmware muet avant ouverture du port série | Neutre émis dès la mise sous tension |

## 📦 Livrables (dépôt GitHub `protova2`)
- `protova1/pico_car_freertos.ino` — firmware final
- `protova1/joy_udp_bridge_tx.py` / `joy_udp_bridge_rx.py` — pont /joy
- `protova1/launch_teleop_p1.sh` — pile complète
- `docs/protova1_teleop_runbook.md` — procédure reproductible de A à Z

## 📋 Prochaine étape : ProtoVA2, puis la démo à deux véhicules
1. **ProtoVA2** : investiguer le bug « avance sans accélérateur » (boîte noire), calibrations
2. Émission **DENM au freinage AEB** côté ProtoVA2 (Vanetza déjà opérationnel)
3. Portage V2V sur ProtoVA1 (compilation Vanetza sur le Nano + nœud CAM/DENM léger)
4. **Démo finale** : ProtoVA2 freine (AEB) → DENM → ProtoVA1 réagit — sécurité coopérative entre deux véhicules réels
