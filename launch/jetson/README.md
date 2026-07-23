# jetson_scripts/ — bundle à redéposer sur la Jetson après reflash

Contenu à copier sur la Jetson (dans `/home/protova2/`) une fois reflashée et le
workspace `protova2_yass` reconstruit.

## Copier tout d'un coup (depuis le PC)
```bash
scp -r ~/jetson_scripts/*.sh ~/jetson_scripts/*.py protova2@<ip_jetson>:~/
ssh protova2@<ip_jetson> 'chmod +x ~/*.sh'
```
*(`<ip_jetson>` : `./jetson.sh ip` sur le PC.)*

## Scripts de lancement (recréés fidèlement)
| Script | Rôle |
|---|---|
| `launch_camera.sh` | caméra Orbbec + profondeur alignée (D2C) |
| `launch_teleop.sh` | conduite : g29_teleop + twist_mux + TX (Pico) + RX |
| `launch_car_wifi.sh` | conduite + caméra en WiFi (FastDDS) |
| `launch_v2v_odom.sh` | lidar + rf2o + odom_to_gps + v2v_node (CAM/DENM = position réelle) |
| `launch_denm_car.sh` | voiture A : émission DENM sur détection (station 2) |

## Brique système (recréée — équivalent fonctionnel)
| Fichier | Rôle | À adapter |
|---|---|---|
| `slam.launch.py` | lidar RPLIDAR + TF `base_link→laser` + rf2o → `/odom_rf2o` | **baudrate** lidar (115200 vs 256000), offset TF |
| `setup_5g.sh` | (sudo, 1×) règle udev `5g0` + sudoers réseau pour la 5G | VID/PID Quectel via `lsusb` |

## Fichiers Python (copiés ici depuis le PC)
`v2v_node.py`, `odom_to_gps.py`, `v2v_gps_sim.py`, `aeb_node.py`, `denm_alert.py`,
`monitor_5g.py`, `bench_5g_live.py`.

## Tu as déjà (ailleurs — rien à refaire)
- `launch_car.sh` (5G/Zenoh côté voiture) → `~/protova2/launch_car.sh` sur le PC.
- Helpers optionnels `launch_slam.sh` / `launch_lidar.sh` = juste des wrappers de
  `ros2 launch slam.launch.py` — recréables en 2 lignes au besoin.

## Vanetza / socktap (à rebuild sur la Jetson)
Recopier tes **6 fichiers modifiés** depuis `~/vanetza/tools/socktap/` du PC :
`cam_application.cpp`, `udp_position_provider.cpp/.hpp`, `denm_application.cpp/.hpp`,
`main.cpp`, `CMakeLists.txt` → puis `cmake -DBUILD_SOCKTAP=ON .. && make socktap`.

Voir la checklist complète : `~/checklist_remise_en_route_jetson.md`.
