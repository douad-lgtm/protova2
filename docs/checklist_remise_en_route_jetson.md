# Checklist — Remise en route de la Jetson (Orin Nano) après reflash

> **Contexte** : la Jetson ne bootait plus (OS corrompu sur le NVMe), mais le matériel est vivant (détectée en recovery `NVIDIA APX`). On reflashe un OS neuf, puis on reconstruit l'environnement ProtoVA.
>
> **✅ Tout est sauvegardé** : `protova2_yass` (tu l'as), ton code + `~/vanetza` sur le PC, les launchs (PC + voiture), les configs Zenoh, `monitor_5g.py` + `bench_5g_live.py` (recréés). Le reflash n'efface **rien d'important**.

---

## Phase 0 — Reflasher la Jetson
- [ ] Installer **NVIDIA SDK Manager** sur le PC (compte NVIDIA Developer gratuit) — *ou* utiliser `flash.sh` du BSP déjà téléchargé (`~/Downloads/Linux_for_Tegra`).
- [ ] Mettre la Jetson en **recovery** : pont broches **9–10** (FC_REC + GND) + **USB-C** au PC + rebrancher l'alim (pont ~2 s, retirer).
- [ ] Vérifier : `lsusb | grep -i nvidia` → **`NVIDIA Corp. APX`**.
- [ ] Lancer le **flash** (SDK Manager → JetPack **5.x** → Flash). ⏳ ~20–40 min.
- [ ] La Jetson **reboote** → premier écran Ubuntu.

## Phase 1 — Premier démarrage (config Ubuntu)
- [ ] Config initiale : **utilisateur `protova2`**, langue, fuseau, **WiFi** (même réseau que le PC, `10.37.11.x`).
- [ ] Vérifier l'IP : `hostname -I` → doit être en `10.37.11.x`.
- [ ] `sudo apt update && sudo apt upgrade -y`

## Phase 2 — Accès matériel (permissions + ports)
- [ ] **Groupe dialout** (Pico + lidar en série, sans sudo) :
  ```bash
  sudo usermod -aG dialout $USER
  ```
  puis **se déconnecter/reconnecter** (ou rebooter).
- [ ] Brancher et vérifier chaque périphérique :
  ```bash
  ls /dev/ttyACM0        # Pico (servo/ESC)
  ls /dev/ttyUSB0        # LiDAR (CP2102)
  lsusb | grep -i 10c4   # LiDAR (Silicon Labs)
  lsusb | grep -i 2bc5   # Caméra Orbbec Femto Bolt
  ```
- [ ] **Pico** : rien à reprogrammer (son firmware est sur la Pico, intact). Elle réapparaît seule en `/dev/ttyACM0`.

## Phase 3 — ROS 2 Humble
- [ ] Installer **ROS 2 Humble** (`ros-humble-desktop`) + outils (`colcon`, `rosdep`).
- [ ] Dépendances des paquets utilisés :
  ```bash
  sudo apt install ros-humble-twist-mux ros-humble-rplidar-ros \
    ros-humble-slam-toolbox ros-humble-navigation2 ros-humble-nav2-bringup \
    ros-humble-joy
  ```
- [ ] **Caméra Orbbec** : réinstaller le paquet ROS `orbbec_camera` (SDK Orbbec + build dans le workspace).
- [ ] **rf2o** (odométrie laser) : `ros-humble-rf2o-laser-odometry` (ou le build depuis les sources).

## Phase 4 — Workspace `protova2_yass`
- [ ] Copier `protova2_yass` (ta sauvegarde) vers `~/protova2_yass` sur la Jetson.
- [ ] Résoudre les dépendances puis compiler :
  ```bash
  cd ~/protova2_yass
  rosdep install --from-paths src --ignore-src -r -y
  colcon build --symlink-install
  source install/setup.bash
  ```
- [ ] Vérifier le package `controller` (nœuds **TX**, **RX**, **g29_teleop**) + la config **twist_mux** (`config/twist_mux.yaml` avec le slot AEB `/cmd_vel_aeb` priorité 255).

## Phase 5 — Vanetza / V2V (socktap)
- [ ] Depuis le PC, recopier les **sources socktap modifiées** (`~/vanetza/tools/socktap/`) :
  `cam_application.cpp` (cap+vitesse), `udp_position_provider.cpp/.hpp` (4 champs),
  `denm_application.cpp/.hpp` (DENM), `main.cpp` (`-a den`), `CMakeLists.txt`.
  ```bash
  # sur la Jetson : cloner Vanetza puis remplacer ces fichiers par tes versions du PC
  git clone --depth 1 https://github.com/riebl/vanetza.git ~/vanetza
  # scp depuis le PC : les 6 fichiers ci-dessus dans ~/vanetza/tools/socktap/
  cd ~/vanetza && mkdir -p build && cd build
  cmake -DBUILD_SOCKTAP=ON .. && make socktap -j$(nproc)
  ```
- [ ] Binaire attendu : `~/vanetza/build/bin/socktap`.

## Phase 6 — Scripts (redéposer depuis le PC)
- [ ] Depuis le PC (`scp` vers la Jetson `~/`) :
  - **V2V** : `v2v_node.py`, `odom_to_gps.py`, `v2v_gps_sim.py`
  - **AEB / perception** : `aeb_node.py` (YOLO à porter séparément sur Jetson si besoin)
  - **5G** : `monitor_5g.py`, `bench_5g_live.py` (recréés), `launch_car.sh`
  - **Launchs voiture** : `launch_camera.sh`, `launch_v2v_odom.sh`, `launch_denm_car.sh`, `launch_teleop.sh`, `launch_car_wifi.sh`, `launch_slam.sh`, `slam.launch.py`
  *(je peux te recréer ceux que j'avais faits si tu ne les as pas).*
- [ ] `chmod +x ~/*.sh`

## Phase 7 — 5G (si tu refais la démo 5G)
- [ ] Dongle **Quectel RM530N-GL** branché.
- [ ] Recréer la **règle udev** (`/etc/udev/rules.d/70-quectel-5g.rules` → renomme en `5g0`) + **sudoers** (`/etc/sudoers.d/protova2-5g`) — via `setup_5g.sh` (à recréer si perdu).
- [ ] IP statique **172.16.48.6/28** (attention au bug /30→/28, déjà géré dans `launch_car.sh`).

## Phase 8 — Vérifications finales (tester chaque brique)
- [ ] **Pico / actionneurs** : lancer `TX` → la voiture réagit au G29.
- [ ] **LiDAR / SLAM** : `./launch_slam.sh` → `/scan` + `/odom_rf2o` publient.
- [ ] **Caméra** : `./launch_camera.sh` → `/camera/color/image_raw` publie.
- [ ] **V2V CAM** : `socktap -a ca` PC↔Jetson → échange bidirectionnel.
- [ ] **DENM** : `./launch_denm_car.sh` + piéton devant la caméra → DENM émis, reçu sur le PC.
- [ ] **AEB** : obstacle proche → `/cmd_vel_aeb` → la voiture freine.
- [ ] **5G** : `monitor_5g.py` (port 8088), `bench_5g_live.py` (port 8089).

---

## Rappels utiles
- **IP Jetson** : change avec le DHCP → `./jetson.sh` (sur le PC) la retrouve par sa MAC `14:75:5b:15:59:32`.
- **Domaine ROS** : `ROS_DOMAIN_ID=125` + `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` (WiFi) / Zenoh (5G).
- **Piège SSH** : `pkill -f nom` peut tuer la session si « nom » apparaît ailleurs dans la commande → motif entre crochets `[n]om`, dans une commande séparée.
- **Piège LiDAR** : le connecteur CP2102 se débranche → vérifier `lsusb | grep 10c4` avant chaque essai.
