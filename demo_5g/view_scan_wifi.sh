#!/bin/bash
# =============================================================================
# PC — visualiser le /scan du LiDAR (RViz) sur WiFi (DDS natif).
# Le LiDAR doit tourner sur la Jetson (launch_lidar.sh ou rplidar_composition).
# Fixed Frame = laser_frame -> aucun TF nécessaire pour voir le scan.
# =============================================================================
export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG

source /opt/ros/humble/setup.bash 2>/dev/null
if [ -f "$HOME/protova2/protova2_yass/install/setup.bash" ]; then
    source "$HOME/protova2/protova2_yass/install/setup.bash"
fi

exec rviz2 -d "$HOME/protova2/scan.rviz"
