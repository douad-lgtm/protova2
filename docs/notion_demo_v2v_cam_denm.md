# Démo V2V — CAM + DENM en même temps

> ℹ️ **À retenir :** le CAM et le DENM ne sont pas séparés. Un seul programme (`socktap`, lancé avec `-a ca den`) gère les deux **en même temps** : le CAM part en continu (~1 Hz), le DENM part quand un événement survient. Chaque véhicule émet ET reçoit les deux simultanément.

## Ce que fait chaque message

| Message | Rôle | Rythme |
| --- | --- | --- |
| **CAM** | « je suis là » : position, cap, vitesse | continu (~1 Hz) |
| **DENM** | « danger ici » : cause + position | sur événement (obstacle détecté) |

## Prérequis

- PC et Jetson sur le **même WiFi**
- Caméra branchée sur la Jetson
- Trouver l'IP de la Jetson : `ip neigh | grep 14:75:5b`

## Les étapes (4 terminaux)

### Voiture A — Jetson

1. **Terminal 1 — caméra**

    ```bash
    ssh protova2@10.37.11.29
    ./launch_camera.sh
    ```

2. **Terminal 2 — CAM + DENM (émission)**

    ```bash
    ssh protova2@10.37.11.29
    ./launch_denm_car.sh
    ```

    → `v2v_node` lance `socktap -a ca den` : il émet des **CAM** en continu **et** un **DENM** quand un obstacle est signalé.

### Voiture B — PC

3. **Terminal 3 — détection YOLO**

    ```bash
    ./run_yolo_pc.sh
    ```

    → publie `/obstacle/brake` quand un obstacle est proche.

4. **Terminal 4 — CAM + DENM (réception + alerte)**

    ```bash
    ./launch_denm_pc.sh
    ```

    → reçoit les **CAM** (position de l'autre véhicule) **et** les **DENM** (alertes), et affiche l'alerte.

## Voir les DEUX flux en même temps

- **CAM** (présence continue) — dans un 5ᵉ terminal PC :

    ```bash
    export ROS_DOMAIN_ID=2
    source /opt/ros/humble/setup.bash
    ros2 topic echo /v2v/remote_vehicles
    ```

    → affiche en continu la position / cap / vitesse de la voiture A.

- **DENM** (alerte ponctuelle) — dans le **Terminal 4** :

    → la bannière `*** ALERTE V2V ***` apparaît quand un obstacle est détecté.

> ✅ Les deux tournent en parallèle : le CAM défile en continu pendant que le DENM se déclenche uniquement lors d'un danger.

## Option — CAM avec cap et vitesse réels

Par défaut la démo utilise une position fixe (`positioning:=static`). Pour que le CAM porte le **cap et la vitesse réels** (issus de l'odométrie), lancer la voiture A en `positioning:=udp` avec `odom_to_gps.py`.

## Schéma de la chaîne

```
Caméra (Jetson) → YOLO + profondeur (PC) → /obstacle/brake
                                                |
     CAM (continu) ←→ socktap "-a ca den" ←—————+
                                                |
                        DENM (sur obstacle) → autre véhicule → *** ALERTE ***
```
