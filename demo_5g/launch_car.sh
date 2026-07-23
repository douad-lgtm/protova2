#!/bin/bash

export ROS_DOMAIN_ID=125
export RMW_IMPLEMENTATION=rmw_zenoh_cpp
export ZENOH_CONFIG=/home/protova2/zenoh_session_car.json5

# Find 5G interface: prefer udev-renamed 5g0, else find by USB VID 2c7c (Quectel RM530N-GL)
IFACE_5G=""
if ip link show 5g0 &>/dev/null; then
    IFACE_5G="5g0"
else
    for iface_path in /sys/class/net/enx*; do
        iface=$(basename "$iface_path")
        dev="$iface_path/device"
        for _ in 1 2 3 4; do
            vid=$(cat "$dev/idVendor" 2>/dev/null)
            [ "$vid" = "2c7c" ] && { IFACE_5G="$iface"; break 2; }
            dev="$dev/.."
        done
    done
fi

if [ -z "$IFACE_5G" ]; then
    echo "ERROR: 5G dongle not found. Plug in the Quectel RM530N-GL dongle."
    exit 1
fi
echo "5G interface: $IFACE_5G"

# Ensure interface is up
sudo ip link set "$IFACE_5G" up 2>/dev/null || true
sleep 1

# Set up 5G IP: use ifup for 5g0 (static config in /etc/network/interfaces),
# else use dhclient + upgrade /30→/28 for dynamically-named enx* interfaces
if ip -4 addr show "$IFACE_5G" 2>/dev/null | grep -q "172.16.48.6/28"; then
    echo "  IP already set to /28, skipping assignment."
elif [ "$IFACE_5G" = "5g0" ]; then
    echo "Assigning static IP via ifupdown..."
    sudo ifup 5g0
else
    echo "Getting IP via dhclient on $IFACE_5G..."
    sudo dhclient "$IFACE_5G"
    sleep 2
    # DHCP gives /30 — upgrade to /28 so 172.16.48.7 is unicast-reachable
    sudo ip addr del 172.16.48.6/30 brd 172.16.48.7 dev "$IFACE_5G" 2>/dev/null || true
    sudo ip addr add 172.16.48.6/28 brd 172.16.48.15 dev "$IFACE_5G" 2>/dev/null || true
fi

# Verify connectivity
echo "Waiting for 172.16.48.6 on $IFACE_5G (up to 15s)..."
for i in $(seq 1 15); do
    if ip -4 addr show "$IFACE_5G" 2>/dev/null | grep -q "172.16.48.6"; then
        echo "  5G ready — 172.16.48.6 on $IFACE_5G"
        break
    fi
    sleep 1
done

if ! ip -4 addr show "$IFACE_5G" 2>/dev/null | grep -q "172.16.48.6"; then
    echo "WARNING: No IP on $IFACE_5G. Check antenna / SIM / 5G coverage."
fi

# Remove default route via 5G gateway (keep WiFi as default)
ip route del default via 172.16.48.5 2>/dev/null || true

# Kill any stale nodes from a previous session
pkill -f "controller/(TX|g29_teleop)" 2>/dev/null
pkill -x rmw_zenohd 2>/dev/null
sleep 1

# Start Zenoh router (bridges local nodes to PC router at 172.16.48.7:7447)
ZENOH_CONFIG=/home/protova2/zenoh_router_car.json5 ros2 run rmw_zenoh_cpp rmw_zenohd &
ROUTER_PID=$!
echo "Zenoh router started (PID $ROUTER_PID), connecting to PC at 172.16.48.7:7447..."
sleep 3

source /home/protova2/protova2_yass/install/setup.bash

ros2 run controller TX &
ros2 run controller g29_teleop &

echo "Car side ready — ROS2 over 5G via Zenoh"
