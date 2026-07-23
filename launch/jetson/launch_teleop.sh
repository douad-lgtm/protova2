#!/bin/bash
# Jetson — teleop WiFi : volant G29 -> twist_mux -> TX -> Pico (servo/ESC), + RX encodeur.
# Le G29 (joy_node) tourne sur le PC (launch_pc_wifi.sh) et publie /joy ; ici g29_teleop
# convertit /joy -> /cmd_vel_G29.
export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG
source /opt/ros/humble/setup.bash
source /home/protova2/protova2_yass/install/setup.bash

pkill -9 -f "controller [g]29_teleop" 2>/dev/null
pkill -9 -f "[t]wist_mux" 2>/dev/null
pkill -9 -f "controller [T]X" 2>/dev/null
pkill -9 -f "[R]X RX" 2>/dev/null
sleep 2

ros2 run controller g29_teleop &
echo "g29_teleop -> /cmd_vel_G29"
ros2 run twist_mux twist_mux \
  --ros-args --params-file /home/protova2/protova2_yass/install/controller/share/controller/config/twist_mux.yaml \
  -r /cmd_vel_out:=/cmd_vel &
echo "twist_mux -> /cmd_vel"
sleep 1
ros2 run controller TX &
echo "TX -> Pico"
ros2 run RX RX &
echo "RX -> /velocity"

echo "Teleop pret. Conduis au G29. Ctrl+C pour arreter."
trap 'echo "Arret teleop..."; kill $(jobs -p) 2>/dev/null' INT TERM EXIT
wait
