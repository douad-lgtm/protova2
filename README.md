# ProtoVA — Communication V2V, perception et sécurité coopérative

Véhicule autonome à échelle réduite (Jetson Orin Nano + ROS 2 Humble) doté d'une
chaîne complète de **sécurité coopérative V2V** : perception caméra (YOLO + profondeur),
freinage d'urgence gradué (AEB), et échange de messages **ETSI C-ITS** (CAM / DENM)
entre véhicules via la pile open-source **Vanetza**.

> Projet réalisé par **Douae Sebti** — la chaîne V2V (CAM enrichie, application DENM,
> intégration ROS 2) constitue ma contribution personnelle au projet ProtoVA.

## Architecture

```
   VOITURE A (Jetson, domaine ROS 125)                 PC / VOITURE B
   ┌────────────────────────────────┐
   │ Caméra Orbbec Femto Bolt       │── images ──► YOLO (yolo_detect.py, dom. 125)
   │  (profondeur alignée couleur)  │                    │ /obstacle/detections
   │ v2v_node.py  (station 2) ◄─────┼────────────────────┘
   │   │  filtre danger confirmé :  │
   │   │  piéton < 5 m, 3 images    │              ┌───────────────────────────┐
   │   ▼                            │              │ v2v_node.py (station 1,   │
   │ socktap (Vanetza)              │─── CAM ────► │  domaine ROS 2 séparé)    │
   │  CAM 1 Hz + DENM cause 99/2    │─── DENM ───► │ denm_alert.py → ALERTE 🚨 │
   └────────────────────────────────┘  (UDP WiFi)  └───────────────────────────┘
```

- **CAM** (EN 302 637-2) : position + **cap + vitesse réels** (odométrie), 1 Hz.
- **DENM** (EN 302 637-3) : émise uniquement sur **danger confirmé**
  (classe piéton, distance < 5 m, persistance 3 images) — cause 99
  *dangerousSituation*, sous-cause 2 *emergencyElectronicBrakeEngaged*.
- Les deux véhicules sont sur des **domaines ROS séparés** : l'alerte transite par
  le **V2V (Vanetza/UDP)**, jamais par DDS — comme entre deux vrais véhicules.
- **AEB gradué** (`aeb_node.py`) : ralentissement puis arrêt selon classe/distance,
  priorité 255 dans `twist_mux` (l'humain ne peut pas outrepasser le frein).

## Contenu du dépôt

| Dossier | Contenu |
|---|---|
| `socktap/` | Fichiers **Vanetza/socktap modifiés** : CAM enrichie (cap/vitesse), **application DENM** (nouvelle), fournisseur de position UDP, `main.cpp` + CMake |
| `nodes/` | Nœuds ROS 2 : `v2v_node.py` (CAM/DENM ↔ ROS), `yolo_detect.py` (YOLO + profondeur), `aeb_node.py` (freinage gradué), `odom_to_gps.py` (odométrie → position), `denm_alert.py` (alerte), `v2v_car_monitor.py`, `v2v_gps_sim.py`, `view_camera.py` |
| `launch/pc/` | Scripts côté PC (WiFi, 5G/Zenoh, récepteur DENM) |
| `launch/jetson/` | Scripts côté voiture (caméra, téléop, V2V odométrie, DENM, SLAM, 5G) |
| `tools/` | `monitor_5g.py`, `bench_5g_live.py` (dashboards 5G), `jetson.sh` (découverte SSH par MAC) |
| `docs/` | Checklist de remise en route Jetson + **rapports LaTeX** du projet |

## Compiler socktap (Vanetza) avec le support DENM

```bash
git clone https://github.com/riebl/vanetza.git
cp socktap/* vanetza/tools/socktap/
cd vanetza && mkdir build && cd build
cmake -DBUILD_SOCKTAP=ON .. && make socktap -j$(nproc)
# binaire : build/bin/socktap  (options ajoutées : -a den, --denm-trigger-port,
#                               --print-rx-denm / --print-tx-denm, --denm-cause)
```

## Lancer la démo terrain complète

**Terminal 1 — Jetson (caméra)** :
```bash
./launch_camera.sh
```
**Terminal 2 — Jetson (V2V voiture A)** :
```bash
./launch_denm_car.sh
```
**Terminal 3 — PC (perception YOLO, domaine 125)** :
```bash
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
source /opt/ros/humble/setup.bash
python3 nodes/yolo_detect.py
```
**Terminal 4 — PC (voiture B : réception + alerte)** :
```bash
./launch/pc/launch_denm_pc.sh
```

Puis se placer devant la caméra (< 5 m, ~3 s) : YOLO détecte le piéton, la
voiture A émet la DENM, la voiture B affiche **« FREINAGE D'URGENCE signalé par
le véhicule 2 »**. Un obstacle non piéton (chaise…) déclenche le freinage local
mais **pas** de DENM — c'est le filtre anti-faux-positifs.

## Prérequis

- ROS 2 Humble (Ubuntu 22.04) sur les deux machines, même réseau WiFi
- Jetson : JetPack 6.x, driver caméra `orbbec_camera`, règles udev Orbbec
- PC : `ultralytics` (YOLOv8), `python3-serial`, `tf_transformations`
- Voir `docs/checklist_remise_en_route_jetson.md` pour la reconstruction complète
