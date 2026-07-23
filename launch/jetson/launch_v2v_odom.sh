#!/bin/bash
# Jetson — V2V avec position issue de l'ODOMETRIE REELLE.
# LiDAR + rf2o (odom) + odom_to_gps (->/v2v/my_gps) + v2v_node (CAM/DENM = position reelle).
# => la distance affichee cote recepteur devient VRAIE et dynamique quand le robot bouge.
export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG
source /opt/ros/humble/setup.bash
source /home/protova2/protova2_yass/install/setup.bash

pkill -9 -f "[r]plidar_composition" 2>/dev/null
pkill -9 -f "[s]lam_toolbox" 2>/dev/null
pkill -9 -f "[r]f2o" 2>/dev/null
pkill -9 -f "[o]dom_to_gps" 2>/dev/null
pkill -9 -f "[v]2v_node" 2>/dev/null
pkill -9 -f "[s]ocktap" 2>/dev/null
sleep 2

ros2 launch /home/protova2/slam.launch.py &
echo "[v2v-odom] LiDAR + rf2o lances, attente odom..."
sleep 12

python3 /home/protova2/odom_to_gps.py --ros-args \
  -p odom_topic:=/odom_rf2o -p origin_lat:=48.76680 -p origin_lon:=11.43200 &
echo "[v2v-odom] odom_to_gps lance (-> /v2v/my_gps)"

python3 /home/protova2/v2v_node.py --ros-args \
  -p interface:=wlP1p1s0 -p station_id:=2 -p positioning:=udp -p pos_port:=9001 \
  -p alert_dist:=5.0 -p socktap_bin:=/home/protova2/vanetza/build/bin/socktap &
echo "[v2v-odom] v2v_node lance (CAM = position odometrie reelle)"

trap 'echo stop; kill $(jobs -p) 2>/dev/null' INT TERM EXIT
wait
