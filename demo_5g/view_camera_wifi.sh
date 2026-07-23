#!/bin/bash
# =============================================================================
# PC side — open rqt_image_view on the car's camera over WiFi (native FastDDS).
# Defaults to the color stream with COMPRESSED transport (light on WiFi).
#
# Usage:
#   ./view_camera_wifi.sh                 # color, compressed (default)
#   ./view_camera_wifi.sh depth           # depth stream
#   ./view_camera_wifi.sh ir              # IR stream
#   ./view_camera_wifi.sh /my/topic raw   # any base topic + transport
#
# NOTE: always pass the BASE topic (e.g. /camera/color/image_raw), NEVER the
# transport-specific one (.../compressed) — subscribing to that directly makes
# rqt crash with "incompatible type / invalid allocator".
# =============================================================================

# Same environment as the WiFi launch scripts (no Zenoh, native DDS).
export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
unset ZENOH_SESSION_CONFIG_URI ZENOH_ROUTER_CONFIG_URI ZENOH_CONFIG

source /opt/ros/humble/setup.bash 2>/dev/null
if [ -f "$HOME/protova2/protova2_yass/install/setup.bash" ]; then
    source "$HOME/protova2/protova2_yass/install/setup.bash"
fi

# Resolve the topic + transport from the arguments.
TRANSPORT="compressed"
case "$1" in
    ""|color) TOPIC="/camera/color/image_raw" ;;
    depth)    TOPIC="/camera/depth/image_raw" ;;
    ir)       TOPIC="/camera/ir/image_raw" ;;
    /*)       TOPIC="$1" ;;                       # explicit base topic
    *)        TOPIC="/camera/$1/image_raw" ;;     # e.g. "color"
esac
[ -n "$2" ] && TRANSPORT="$2"                     # optional transport override

echo "Opening rqt_image_view on $TOPIC (transport: $TRANSPORT) over WiFi..."
echo "In the window: keep the BASE topic selected and set transport to '$TRANSPORT'."

exec ros2 run rqt_image_view rqt_image_view "$TOPIC" _image_transport:="$TRANSPORT"
