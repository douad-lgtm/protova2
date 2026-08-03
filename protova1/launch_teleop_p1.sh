#!/bin/bash
# ProtoVA1 — pile de téléopération complète (lancée par systemd : p1teleop.service)
# Chaîne : /joy (pont UDP depuis le PC) -> g29_teleop -> twist_mux -> TX -> Pico
# Script AUTONOME : source ROS explicitement (systemd ne lit pas ~/.bashrc).

source /opt/ros/foxy/setup.bash
source /home/protova1/protova1_ws/install/setup.bash
export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# nettoyage d'éventuels restes (motifs bracketés = jamais d'auto-match)
pkill -f "joy_udp_bridge_[r]x" 2>/dev/null
pkill -f "[G]29Teleop" 2>/dev/null
pkill -x twist_mux 2>/dev/null
sleep 1

# 1) pont /joy : reçoit l'UDP du PC et republie en local
python3 /home/protova1/joy_udp_bridge_rx.py --port 9001 &
echo "[p1teleop] pont /joy lancé"

# 2) conversion volant -> consigne
ros2 run controller g29_teleop &
echo "[p1teleop] g29_teleop lancé"

# 3) multiplexeur de commandes (priorités : aeb 255 > ps4 60 > g29 30)
ros2 run twist_mux twist_mux --ros-args \
  --params-file /home/protova1/protova1_ws/src/controller/config/twist_mux.yaml \
  -r /cmd_vel_out:=/cmd_vel &
echo "[p1teleop] twist_mux lancé"
sleep 2

# 4) liaison série vers le Pico (+ publication /velocity depuis les TICKS)
ros2 run controller TX &
echo "[p1teleop] TX lancé"

# garder le script vivant : ses enfants survivent ainsi aux aléas SSH
trap 'kill $(jobs -p) 2>/dev/null' INT TERM
wait
