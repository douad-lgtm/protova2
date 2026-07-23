#!/bin/bash
# Jetson — VOITURE A (celle qui detecte et alerte).
# A lancer EN PLUS de ./launch_camera.sh (meme domaine 125).
# La detection YOLO tourne sur le PC (sur la camera de la voiture) et publie
# /obstacle/detections ; v2v_node emet un DENM sur un DANGER confirme (pieton).
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG
source /opt/ros/humble/setup.bash
source /home/protova2/protova2_yass/install/setup.bash
echo "Voiture A : emission DENM sur detection d'obstacle (station 2)"
python3 /home/protova2/v2v_node.py --ros-args \
  -p interface:=wlP1p1s0 -p station_id:=2 -p positioning:=static \
  -p my_lat:=48.76690 -p my_lon:=11.43210 \
  -p socktap_bin:=/home/protova2/vanetza/build/bin/socktap
