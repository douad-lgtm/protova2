#!/bin/bash
# Jetson — camera Orbbec Femto Bolt avec profondeur ALIGNEE sur la couleur (D2C).
# Indispensable pour que yolo_detect.py lise des distances CORRECTES.
# Laisser ce terminal ouvert (Ctrl+C arrete la camera).
# Si un ancien lancement est bloque : dans un AUTRE terminal, faire
#   pkill -9 -f "[c]amera_container"
export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG
source /opt/ros/humble/setup.bash
source /home/protova2/protova2_yass/install/setup.bash
# 30 fps + sans synchro couleur/profondeur + horodatage systeme : mesure 2026-07-28,
# le mode 15 fps avec frame_sync tamponnait ~10 images -> 700 ms de latence camera !
# Avec cette config : ~90 ms camera, ~230 ms capture->PC au total.
ros2 launch orbbec_camera femto_bolt.launch.py depth_registration:=true \
  color_fps:=30 depth_fps:=30 enable_frame_sync:=false time_domain:=system "$@"
