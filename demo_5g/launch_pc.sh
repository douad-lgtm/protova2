#!/bin/bash
# PC side — configure 5G dongle and launch Zenoh router + G29 teleoperation

export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_zenoh_cpp

# Find 5G dongle (Quectel RM530N-GL, vendor 2c7c:0801)
DONGLE_VENDOR="2c7c"
DONGLE_MODEL="0801"

find_5g_iface() {
    for iface in $(ls /sys/class/net/); do
        local uevent="/sys/class/net/$iface/device/../uevent"
        if [ -f "$uevent" ] && grep -q "PCI_ID=.*${DONGLE_VENDOR}:${DONGLE_MODEL}" "$uevent" 2>/dev/null; then
            echo "$iface"; return
        fi
        # USB device path
        local usb_id=$(cat /sys/class/net/$iface/device/idVendor 2>/dev/null)
        local usb_model=$(cat /sys/class/net/$iface/device/idProduct 2>/dev/null)
        if [ "$usb_id" = "$DONGLE_VENDOR" ] && [ "$usb_model" = "$DONGLE_MODEL" ]; then
            echo "$iface"; return
        fi
    done
    # Fallback: find by interface type (USB ethernet not named eth/wl/en[Pp])
    ip -o link | awk '/enx/{print $2}' | tr -d ':' | head -1
}

IFACE_5G=$(find_5g_iface)

if [ -z "$IFACE_5G" ]; then
    echo "ERROR: 5G dongle not found. Plug in the Quectel RM530N-GL dongle."
    exit 1
fi
echo "5G interface: $IFACE_5G"

# Bring interface up
sudo ip link set "$IFACE_5G" up 2>/dev/null || true
sleep 1

# Get IP if not already assigned
if ! ip -4 addr show "$IFACE_5G" 2>/dev/null | grep -q "172.16.48"; then
    echo "Getting IP via dhclient..."
    sudo dhclient "$IFACE_5G"
    sleep 2
fi

# Fix subnet /30 → /28 so .6 (Nano) and .7 (PC) are both unicast
# Match only the inet address (not the brd address on the same line)
CURRENT_IP=$(ip -4 addr show "$IFACE_5G" | grep -oP 'inet \K172\.16\.48\.\d+' | head -1)
if [ -n "$CURRENT_IP" ]; then
    # Remove /30 if that's what we have
    sudo ip addr del "${CURRENT_IP}/30" dev "$IFACE_5G" 2>/dev/null || true
    # Set static /28
    sudo ip addr add 172.16.48.7/28 brd 172.16.48.15 dev "$IFACE_5G" 2>/dev/null || true
fi

# Remove 5G as default route (keep WiFi/ethernet as default internet route)
# Delete by interface, not gateway — DHCP gateway varies (.8 observed, not .5)
sudo ip route del default dev "$IFACE_5G" 2>/dev/null || true

# Verify
echo "Waiting for 172.16.48.7 on $IFACE_5G..."
for i in $(seq 1 10); do
    if ip -4 addr show "$IFACE_5G" 2>/dev/null | grep -q "172.16.48.7"; then
        echo "  5G ready — 172.16.48.7 on $IFACE_5G"
        break
    fi
    sleep 1
done

if ! ip -4 addr show "$IFACE_5G" 2>/dev/null | grep -q "172.16.48.7"; then
    echo "WARNING: Could not set 172.16.48.7 on $IFACE_5G. Check SIM / 5G coverage."
    exit 1
fi

# Test connectivity to Nano
echo "Pinging Nano (172.16.48.6)..."
if ! ping -c 2 -W 2 172.16.48.6 &>/dev/null; then
    echo "WARNING: Nano not reachable at 172.16.48.6. Is launch_car.sh running on the Nano?"
fi

# Source workspace (must happen before any `ros2` command, including the router)
if [ -f "$HOME/protova2/protova2_yass/install/setup.bash" ]; then
    source "$HOME/protova2/protova2_yass/install/setup.bash"
elif [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
fi

# Start Zenoh router (PC is the central hub)
# rmw_zenoh reads ZENOH_ROUTER_CONFIG_URI / ZENOH_SESSION_CONFIG_URI (NOT ZENOH_CONFIG)
# Create router config if missing (portable: PC user/home differs from Jetson)
ROUTER_CFG="$HOME/zenoh_router_pc.json5"
if [ ! -f "$ROUTER_CFG" ]; then
    cat > "$ROUTER_CFG" <<'EOF'
{
  mode: "router",
  listen: {
    endpoints: ["tcp/0.0.0.0:7447"]
  }
}
EOF
fi
ZENOH_ROUTER_CONFIG_URI="$ROUTER_CFG" ros2 run rmw_zenoh_cpp rmw_zenohd &
ROUTER_PID=$!
echo "Zenoh router started (PID $ROUTER_PID), listening on 0.0.0.0:7447..."
sleep 3

# Node sessions: client mode, connect to the local router (create config if missing)
SESSION_CFG="$HOME/zenoh_session_pc.json5"
if [ ! -f "$SESSION_CFG" ]; then
    cat > "$SESSION_CFG" <<'EOF'
{
  mode: "client",
  connect: {
    endpoints: ["tcp/127.0.0.1:7447"]
  }
}
EOF
fi
export ZENOH_SESSION_CONFIG_URI="$SESSION_CFG"

# Launch G29 joy node and teleop
ros2 run joy joy_node &
echo "joy_node started"
sleep 1

ros2 run ros_g29_force_feedback g29_force_feedback \
    --ros-args --params-file \
    "$HOME/protova2/protova2_yass/src/ros-g29-force-feedback/config/g29.yaml" &
echo "G29 force feedback started"

echo ""
echo "PC side ready — ROS2 over 5G via Zenoh"
echo "Nano IP: 172.16.48.6  |  PC IP: 172.16.48.7"
echo ""
echo "To monitor topics: ros2 topic list"
echo "To check graph:    rqt &"
