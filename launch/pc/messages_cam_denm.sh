#!/bin/bash
# PC — VOITURE B (celle qui RECOIT et AFFICHE l'alerte).
# Domaine ROS SEPARE (2) expres : l'alerte doit arriver par le V2V (Vanetza/WiFi),
# PAS par ROS DDS. Recoit le DENM emis par la voiture A -> l'affiche.
export ROS_DOMAIN_ID=2 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG
source /opt/ros/humble/setup.bash 2>/dev/null
[ -f "$HOME/protova2/protova2_yass/install/setup.bash" ] && source "$HOME/protova2/protova2_yass/install/setup.bash"

echo "Voiture B : reception V2V (station 1) + affichage des alertes"
# Position du PC dans le MEME repere que l'odometrie du robot (origine
# 48.76680, 11.43200 dans launch_v2v_odom.sh). Ici : 8 m DERRIERE l'origine
# (scenario "feu stop d'urgence" : le vehicule qui freine previent le suiveur).
# Comme le robot bouge (odometrie reelle), la distance affichee devient VRAIE et
# DYNAMIQUE au lieu des 13 m fixes.
python3 "$HOME/v2v_node.py" --ros-args \
  -p interface:=wlp2s0 -p station_id:=1 -p positioning:=static \
  -p my_lat:=48.766728 -p my_lon:=11.43200 \
  -p socktap_bin:="$HOME/vanetza/build/bin/socktap" &
V2V_PID=$!
sleep 3
# afficheur d'alerte
python3 "$HOME/denm_alert.py"
kill $V2V_PID 2>/dev/null
