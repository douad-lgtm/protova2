# ProtoVA 2 — Véhicule autonome : téléopération 5G, perception, V2V

Projet complet du véhicule autonome à échelle réduite **ProtoVA 2**
(Jetson Orin Nano + ROS 2 Humble) : téléopération (WiFi et **5G**), cartographie
SLAM et navigation, **perception caméra (YOLO + profondeur)**, **freinage
d'urgence gradué (AEB)** et **communication V2V ETSI C-ITS (CAM / DENM)** via la
pile Vanetza.

> Par **Douae Sebti**. La chaîne V2V (CAM enrichie, application DENM,
> intégration ROS 2) constitue ma contribution personnelle au projet.

## Vue d'ensemble

```
        ┌────────────────────────── VOITURE (Jetson Orin Nano) ─────────────────────────┐
        │ Pico RP2040 (servo+ESC, encodeur)   RPLIDAR A1 → SLAM (rf2o + slam_toolbox)   │
        │ Caméra Orbbec Femto Bolt (RGB-D, profondeur alignée couleur)                  │
        │ twist_mux : téléop G29  <  navigation  <  AEB (priorité 255)                  │
        │ v2v_node + socktap (Vanetza) : CAM 1 Hz (cap/vitesse réels) + DENM sur danger │
        └───────────┬────────────────────────────────┬──────────────────────────────────┘
             WiFi (FastDDS, dom. 125)         5G (Zenoh hub-and-spoke)
        ┌───────────┴────────────────────────────────┴──────────────────────────────────┐
        │ PC : volant G29, YOLO (détection + distance), récepteur V2V (domaine séparé), │
        │      dashboards 5G (monitor_5g / bench_5g_live)                               │
        └────────────────────────────────────────────────────────────────────────────────┘
```

## Organisation du dépôt

| Dossier | Contenu |
|---|---|
| `workspace/protova2_yass/` | **Workspace ROS 2** : `base` (controller G29/TX/RX Pico, capteurs Orbbec/RPLIDAR/usb_cam), `car_description`, `detection`, `localisation` (rf2o, SLAM), `navigation` (follow_the_gap, Nav2), `ros-g29-force-feedback` |
| `v2v/socktap/` | **Vanetza/socktap modifiés** : CAM enrichie (cap + vitesse d'odométrie), **application DENM** (cause 99/2, déclencheur UDP), fournisseur de position UDP |
| `v2v/nodes/` | `v2v_node.py` (pont CAM/DENM ↔ ROS 2, filtre danger confirmé), `odom_to_gps.py` (odométrie → position partagée), `denm_alert.py` (alerte reçue), `v2v_car_monitor.py`, `v2v_gps_sim.py` |
| `perception/` | `yolo_detect.py` (YOLOv8 + distance par profondeur alignée, percentile-20), `view_camera.py` |
| `safety/` | `aeb_node.py` — freinage **gradué** selon classe/distance (piéton : ralentit <4 m, stop <1,5 m), priorité max dans twist_mux |
| `demo_5g/` | Téléop **5G** : `launch_pc.sh` (routeur Zenoh) / `launch_car.sh`, configs `zenoh_*.json5`, bridge zenoh-dds (zip), dashboards `monitor_5g.py` (port 8088) et `bench_5g_live.py` (8089), `plot_5g.py` |
| `launch/pc/` | Démos WiFi côté PC : `launch_pc_wifi.sh` (G29), `launch_denm_pc.sh` (voiture B : réception V2V + alerte) |
| `launch/jetson/` | Côté voiture : `launch_camera.sh` (D2C), `launch_teleop.sh`, `launch_car_wifi.sh`, `launch_v2v_odom.sh` (V2V sur odométrie réelle), `launch_denm_car.sh`, `slam.launch.py`, `setup_5g.sh` (udev/sudoers 5G) |
| `tools/` | `jetson.sh` — retrouve la Jetson sur le réseau par MAC et ouvre le SSH |
| `docs/` | `checklist_remise_en_route_jetson.md` (reconstruction complète après reflash), démo pas-à-pas, **rapports LaTeX** (`docs/rapports/`) |

## Construire

### Workspace ROS 2 (sur la Jetson)
```bash
cd workspace/protova2_yass
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
```
Dépendances apt notables : `ros-humble-twist-mux`, `slam-toolbox`, `navigation2`,
`python3-serial`, `ros-humble-tf-transformations`. Règles udev caméra :
`workspace/.../orbbec_camera/scripts/99-obsensor-libusb.rules` → `/etc/udev/rules.d/`.

### socktap (Vanetza) avec le support DENM
```bash
git clone https://github.com/riebl/vanetza.git
cp v2v/socktap/* vanetza/tools/socktap/
cd vanetza && mkdir build && cd build && cmake -DBUILD_SOCKTAP=ON .. && make socktap -j$(nproc)
```
Options ajoutées : `-a den`, `--denm-trigger-port`, `--denm-cause`,
`--print-rx-denm/--print-tx-denm`.

## Lancer les démos

### Téléopération WiFi (volant G29)
Jetson : `launch/jetson/launch_car_wifi.sh` — PC : `launch/pc/launch_pc_wifi.sh`
*(FastDDS natif, `ROS_DOMAIN_ID=125` des deux côtés)*

### Téléopération 5G
PC (routeur Zenoh) : `demo_5g/launch_pc.sh` — Voiture : `demo_5g/launch_car.sh`
Dashboards : `monitor_5g.py` → http://localhost:8088, `bench_5g_live.py` → :8089

### Démo V2V complète (perception → DENM → alerte)
1. Jetson : `launch/jetson/launch_camera.sh` puis `launch/jetson/launch_denm_car.sh`
2. PC (domaine 125) : `python3 perception/yolo_detect.py --ros-args -p show:=true`
3. PC (domaine 2) : `launch/pc/launch_denm_pc.sh`
4. Se placer devant la caméra (< 5 m, ~3 s) → la voiture A émet la **DENM**
   (cause 99 *dangerousSituation* / sous-cause 2 *emergencyElectronicBrakeEngaged*),
   la voiture B affiche **« FREINAGE D'URGENCE signalé par le véhicule 2 »**.

Fiabilité anti-faux-positifs : la DENM n'est émise que sur danger **confirmé**
(classe piéton, < 5 m, persistance 3 images, couloir central) — un obstacle
quelconque proche déclenche le freinage local (AEB) mais pas d'alerte réseau.
Les deux véhicules sont sur des **domaines ROS séparés** : l'alerte transite
uniquement par le V2V (Vanetza/UDP), comme entre deux véhicules réels.

## Documentation

`docs/rapports/` contient les rapports LaTeX du projet : bilan de projet,
rapports hebdomadaires, explication pas-à-pas du V2V, guides 5G
(monitor/bench), SLAM/navigation, démo terrain, roadmap.
`docs/checklist_remise_en_route_jetson.md` décrit la reconstruction complète de
la Jetson (reflash JetPack 6.2.1, WiFi iwlwifi, ROS, workspace, Vanetza, 5G).
