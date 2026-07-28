#!/bin/bash
# Watchdog caméra Orbbec — relance automatiquement la caméra si elle fige.
# (La Femto Bolt gèle sporadiquement : processus vivant mais plus aucune image.)
# Tourne en service systemd (root). Pour le suspendre : touch /tmp/camera_off
# Pour l'arrêter :  sudo systemctl stop camera-watchdog
LOG=/home/protova2/camera_watchdog.log
# IMPORTANT : les verifications ROS doivent se faire EN TANT QUE protova2 —
# root ne voit pas les topics DDS de protova2 (transport memoire partagee FastDDS).
check_flux() {
    runuser -u protova2 -- bash -lc 'source /opt/ros/humble/setup.bash; export ROS_DOMAIN_ID=125 RMW_IMPLEMENTATION=rmw_fastrtps_cpp; timeout 6 ros2 topic echo /camera/color/image_raw/compressed --once > /dev/null 2>&1'
}
echo "$(date '+%F %T') watchdog demarre" >> $LOG

restart_camera() {
    echo "$(date '+%F %T') CAMERA FIGEE -> reset" >> $LOG
    pkill -9 -f "[c]amera_container" 2>/dev/null
    pkill -9 -f "[f]emto_bolt" 2>/dev/null
    sleep 2
    # reset USB PROFOND (USBDEVFS_RESET) — méthode validée le 2026-07-28 :
    # le simple unbind/bind laissait parfois la caméra en "Resource busy".
    DEVNUM=$(lsusb | grep -i orbbec | head -1 | sed 's/.*Device \([0-9]*\):.*/\1/')
    if [ -n "$DEVNUM" ]; then
        python3 - "/dev/bus/usb/001/$DEVNUM" <<'PYRESET'
import fcntl, sys
try:
    f = open(sys.argv[1], "wb"); fcntl.ioctl(f, 21780, 0)
except Exception as e:
    print(e)
PYRESET
    fi
    sleep 8
    runuser -u protova2 -- bash -lc 'nohup ~/launch_camera.sh > /tmp/y_cam.log 2>&1 & disown'
    echo "$(date '+%F %T') camera relancee" >> $LOG
    sleep 40   # laisser le temps de l'init (~25-30 s)
}

while true; do
    if [ -f /tmp/camera_off ]; then sleep 10; continue; fi
    # la camera est-elle censee tourner ?
    if pgrep -f "[c]amera_container" > /dev/null; then
        # GRACE : ne pas toucher un container jeune (init ~30 s)
        AGE=$(ps -o etimes= -p $(pgrep -f "[c]amera_container" | head -1) 2>/dev/null | tr -d " ")
        if [ -n "$AGE" ] && [ "$AGE" -lt 60 ]; then sleep 8; continue; fi
        # recoit-on une image en 6 s ?
        if ! check_flux; then
            # double verification avant de frapper
            if ! check_flux; then
                restart_camera
            fi
        fi
    else
        # camera absente (crash complet) -> relancer aussi
        restart_camera
    fi
    sleep 8
done
