#!/bin/bash
# =============================================================================
# PC — teleop WiFi (DDS natif FastDDS). Pas de Zenoh, pas de 5G.
# A utiliser quand le PC et la voiture (Jetson) sont sur le MEME WiFi.
# Pendant cote Jetson : ~/launch_teleop.sh (g29_teleop + twist_mux + TX + RX).
# Le volant G29 doit etre branche SUR LE PC (joy_node lit le volant -> /joy).
# =============================================================================
export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG

source /opt/ros/humble/setup.bash 2>/dev/null
if [ -f "$HOME/protova2/protova2_yass/install/setup.bash" ]; then
    source "$HOME/protova2/protova2_yass/install/setup.bash"
else
    echo "ATTENTION: workspace ~/protova2/protova2_yass introuvable -> g29_force_feedback echouera."
fi

# --- Verif volant G29 branche sur le PC ---
if ! ls /dev/input/js* &>/dev/null && ! (lsusb | grep -qiE "046d|logitech"); then
    echo "ATTENTION: aucun volant G29 detecte sur le PC (lsusb / /dev/input/js*)."
    echo "           Branche le G29 sur le PC avant de conduire."
fi

# --- Trouver l'IP du jour de la Jetson (DHCP change l'IP ; MAC = 14:75:5b:15:59:32) ---
JETSON_MAC="14:75:5b:15:59:32"
CAR_IP=$(ip neigh | awk -v m="$JETSON_MAC" 'tolower($0) ~ m {print $1; exit}')
[ -z "$CAR_IP" ] && CAR_IP=10.37.11.29   # repli
if ping -c 1 -W 2 "$CAR_IP" &>/dev/null; then
    echo "Voiture joignable a $CAR_IP (WiFi)"
else
    echo "ATTENTION: voiture injoignable a $CAR_IP — memes WiFi ? (ip neigh | grep 14:75:5b)"
fi

# --- Nettoyage d'anciens noeuds ---
pkill -x rmw_zenohd 2>/dev/null
pkill -f "joy_node" 2>/dev/null
pkill -f "g29_force_feedback" 2>/dev/null
sleep 1

# --- Volant G29 : entree + retour de force ---
ros2 run joy joy_node &
echo "joy_node lance (-> /joy)"
sleep 1
ros2 run ros_g29_force_feedback g29_force_feedback \
    --ros-args --params-file \
    "$HOME/protova2/protova2_yass/src/ros-g29-force-feedback/config/g29.yaml" &
echo "g29_force_feedback lance"

echo ""
echo "PC pret — ROS 2 sur WiFi (FastDDS natif, domaine $ROS_DOMAIN_ID)."
echo "Cote Jetson : lance ~/launch_teleop.sh (conduite) et ~/launch_v2v_odom.sh (CAM)."
echo "Garde ce terminal ouvert (Ctrl+C arrete tout)."
trap 'echo "Arret des noeuds..."; kill $(jobs -p) 2>/dev/null' INT TERM EXIT
wait
