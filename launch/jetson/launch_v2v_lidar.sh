#!/bin/bash
# Jetson — VOITURE A : V2V avec distance RÉELLE mesurée par le LIDAR.
# Le lidar (qui tourne/cartographie) mesure la vraie distance au véhicule voisin (le PC).
#   rplidar (A1, 115200) -> /scan
#   lidar_neighbor.py    -> /v2v/neighbor_dist  (distance réelle à l'objet devant)
#   v2v_node (positioning=lidar) : se déclare à cette distance de la position du PC
#     => le PC affiche la VRAIE distance lidar dans l'alerte (plus de valeur fictive).
# La DENM part toujours sur détection piéton (/obstacle/detections depuis YOLO).
# Le PC de référence est à ref_lat/ref_lon (= sa position dans messages_cam_denm.sh).
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG
source /opt/ros/humble/setup.bash
source /home/protova2/protova2_yass/install/setup.bash

pkill -9 -f "[r]plidar" 2>/dev/null
pkill -9 -f "[l]idar_neighbor" 2>/dev/null
pkill -9 -f "[v]2v_node" 2>/dev/null
pkill -9 -f "[s]ocktap" 2>/dev/null
sleep 2

ros2 launch rplidar_ros rplidar_a1_launch.py &
echo "[v2v-lidar] lidar A1 lancé (-> /scan)"
sleep 6

python3 /home/protova2/lidar_neighbor.py --ros-args -p sector_deg:=40.0 -p range_min:=0.05 &
echo "[v2v-lidar] lidar_neighbor lancé (-> /v2v/neighbor_dist)"

python3 /home/protova2/v2v_node.py --ros-args \
  -p interface:=wlP1p1s0 -p station_id:=2 -p positioning:=lidar \
  -p ref_lat:=48.766728 -p ref_lon:=11.43200 \
  -p socktap_bin:=/home/protova2/vanetza/build/bin/socktap &
echo "[v2v-lidar] v2v_node lancé (CAM = distance lidar réelle, DENM sur piéton)"

trap 'echo stop; kill $(jobs -p) 2>/dev/null' INT TERM EXIT
wait
