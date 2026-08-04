# 🚗 ProtoVA1 — Téléopération G29 : runbook & état (2026-08-03)

> ProtoVA1 = Jetson Nano « old » (`protova1@172.20.10.3`, mdp `altenalten`), Ubuntu 20.04, **ROS 2 Foxy**.
> Réseau actuel : partage de connexion iPhone (`172.20.10.x`) — PC en `.2`, Jetson en `.3`.

## ✅ Ce qui a été accompli aujourd'hui
| Étape | Détail |
|---|---|
| Accès Jetson | SSH OK, workspace `~/protova1_ws` (package `controller` : G29Teleop, TX, ackermann_odom) |
| **Firmware Pico flashé** | `pico_car_freertos.ino` (FreeRTOS, 3 tâches) — servo GP15, ESC GP16, encodeur GP2/GP3 |
| **Bug neutre ESC corrigé** | `NEUTRAL 1400 → 1500 µs` (1400 = marche arrière rapide sur cet ESC !) |
| Servo | ✅ validé (balayage 28↔138, centre 83) |
| Moteur | ✅ tourne (penser à armer l'ESC : off → 3 s → on, avec le Pico branché) |
| **Encodeur** | ✅ **40 ticks/tour** (décision 2026-08-04 : décodage ×2 = les deux fronts de CLK, DT ignoré) — KY-040 20 PPR, filtre RC + 74HC14 ; le banc de juin donnait 80 en ×4 |
| Paramètres ROS | `ticks_per_rev = 40` dans TX.py et ackermann_odom.py (⚠️ à appliquer : `find ~/protova1_ws -name "TX.py" -o -name "ackermann_odom.py" \| xargs sed -i 's/\(ticks_per_rev[^0-9]*\)80/\140/'`) — RX.py = doublon, non utilisé |
| twist_mux | installé (`ros-foxy-twist-mux`), config priorités : aeb 255 > ps4 60 > g29 30 |
| **Pont /joy UDP** | le hotspot iPhone **bloque les données DDS** inter-machines (découverte OK, données NON) → pont UDP unicast maison : `joy_udp_bridge_tx.py` (PC) → `joy_udp_bridge_rx.py` (Jetson, port 9001) |
| Service systemd | `p1teleop.service` créé (pile complète, Restart on-failure) — actuellement **désactivé** (mode terminaux préféré) |

## 🎮 Lancer la téléop — 4 terminaux

### 💻 PC — T1 : volant
```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ros2 run joy joy_node
```
✔️ `Opened joystick: Logitech G29`

### 💻 PC — T2 : retour de force
```bash
source /opt/ros/humble/setup.bash
source ~/protova2/protova2_yass/install/setup.bash
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ros2 run ros_g29_force_feedback g29_force_feedback --ros-args --params-file ~/protova2/protova2_yass/src/ros-g29-force-feedback/config/g29.yaml
```
✔️ `device opened` + `force feedback supported`

### 💻 PC — T3 : pont /joy → Jetson
```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
python3 ~/joy_udp_bridge_tx.py --dest-ip 172.20.10.3 --dest-port 9001
```

### 🖥️ JETSON — T4 : pile voiture complète
```bash
ssh protova1@172.20.10.3        # mdp altenalten
./launch_teleop_p1.sh
```
✔️ 4× `[p1teleop] ... lancé` puis les `CTRL,<angle>,<vitesse>` défilent. **Ctrl+C arrête tout.**

Alternative sans terminal : `sudo systemctl start p1teleop`

### 🚗 Conduite
1. **Armer l'ESC** : interrupteur off → 3 s → on (bips) — le Pico maintient le neutre 1500 µs
2. Volant → direction · Accélérateur → avance · Frein → marche arrière
3. Terminal 4 = moniteur des commandes en direct

## ⚠️ Pièges appris (à ne pas réapprendre)
- **Hotspot iPhone** : ping/UDP unicast OK dans les 2 sens, mais **données DDS bloquées** → pont UDP obligatoire pour /joy
- **pkill en SSH** : toujours les motifs bracketés (`[G]29Teleop`) sinon suicide de session
- **nohup meurt avec le SSH** sur ce Nano → systemd ou script `wait` en avant-plan
- **Flash Pico à distance** : touch 1200 bauds → `RPI-RP2` → attention le device peut se ré-énumérer (sda1→sdb1), toujours re-résoudre par label avant `mount`/`cp`/`sync`/`umount`
- Protocole série Pico : `CTRL,<angle 28..138>,<throttle -1..1>` (fraction pleine puissance) ; le Pico émet `TICKS,<delta>` à 50 Hz

## 📋 Prochaines étapes (plan 2 véhicules)
1. Valider la conduite complète (fait ? → cocher)
2. Monter l'odométrie : `ackermann_odom` (80 t/rev, roue Ø104 mm, empattement 245 mm)
3. **V2V** : compiler Vanetza/socktap sur le Nano (test CMake/boost sur 18.04/20.04 à faire) + `v2v_node` léger → CAM avec position odométrie réelle
4. La démo finale : ProtoVA2 freine (AEB) → DENM → **ProtoVA1 réagit** — sécurité coopérative entre deux vrais véhicules
