#!/bin/bash
# Jetson — YOLO EMBARQUÉ (GPU CUDA) : détection piéton/obstacles EN LOCAL.
# Plus de WiFi dans la boucle de perception -> quasi temps réel (~20 ms/inférence).
# Publie /obstacle/detections (pour v2v_node/DENM) et /obstacle/annotated/compressed
# (image annotée légère, à visualiser depuis le PC avec :
#   python3 ~/view_camera.py --topic /obstacle/annotated/compressed )
# Prérequis : launch_camera.sh déjà lancé (topics /camera/...).
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG
source /opt/ros/humble/setup.bash
source /home/protova2/protova2_yass/install/setup.bash

pkill -9 -f "[y]olo_detect" 2>/dev/null
sleep 1

# rate plus élevé qu'au PC : l'inférence GPU est ~10x plus rapide
# annot_width:=0 = image PLEINE RESOLUTION native (nettete max, demande utilisatrice).
# Compromis mesure : 1280px q85 -> ~320 ms de latence, ~6 Hz au PC (WiFi).
# Pour plus de fluidite : -p annot_width:=960 -p annot_quality:=75 (~230 ms, 10 Hz).
python3 /home/protova2/yolo_detect.py --ros-args \
  -p show:=false -p publish_annotated:=true -p rate:=10.0 \
  -p annot_width:=0 -p annot_quality:=85 "$@"
