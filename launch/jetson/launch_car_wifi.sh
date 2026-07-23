#!/bin/bash
# =============================================================================
# Jetson (cote voiture) — demo WiFi en DDS natif (FastDDS). Pas de Zenoh, pas de 5G.
# g29_teleop + TX + RX + twist_mux + camera Orbbec. Pendant PC : ~/launch_pc_wifi.sh
# (le volant G29 est sur le PC). Memes ROS_DOMAIN_ID sur les 2 machines.
# =============================================================================
export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG
source /opt/ros/humble/setup.bash
source /home/protova2/protova2_yass/install/setup.bash

pkill -x rmw_zenohd 2>/dev/null
pkill -f "ros2 run controller g29_teleop" 2>/dev/null
pkill -f "ros2 run controller TX" 2>/dev/null
pkill -f "ros2 run RX RX" 2>/dev/null
pkill -f "ros2 run twist_mux twist_mux" 2>/dev/null
pkill -f "ros2 launch orbbec_camera" 2>/dev/null
pkill -f "component_container.*camera_container" 2>/dev/null
sleep 2

ros2 run controller g29_teleop &
echo "g29_teleop started"
ros2 run controller TX &
echo "TX started"
ros2 run RX RX &
echo "RX started"
ros2 run twist_mux twist_mux \
    --ros-args --params-file /home/protova2/protova2_yass/install/controller/share/controller/config/twist_mux.yaml \
    -r /cmd_vel_out:=/cmd_vel &
echo "twist_mux started"
ros2 launch orbbec_camera femto_bolt.launch.py &
echo "Camera started"

echo ""
echo "Car side ready — ROS 2 over WiFi (native FastDDS, domain $ROS_DOMAIN_ID)"
echo "Keep this terminal open (Ctrl+C stops everything). Pour SSH : run inside tmux/screen si dispo."
trap 'echo "Stopping all nodes..."; kill $(jobs -p) 2>/dev/null' INT TERM EXIT
wait
