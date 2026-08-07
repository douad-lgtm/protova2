#!/bin/bash
# ARRET D'URGENCE ProtoVA2 — tue tous les noeuds + met la Pico au neutre.
# Usage : ./stop_all.sh
for p in $(ps -eo pid,args --no-headers | grep -E "[c]ontroller|[t]wist_mux|[R]X/RX|[r]oamer|[a]eb_fusion|ros2 (run|launch)|[r]plidar|[s]lam|[e]kf|[r]f2o|launch_[c]ar|launch_[s]lam|[o]rbbec|[c]amera_container|[m]ulti_path|[r]obot_state" | awk '{print $1}'); do
    kill -9 "$p" 2>/dev/null
done
python3 - <<PYEOF
import serial, time
try:
    s = serial.Serial("/dev/ttyACM0", 115200, timeout=0.5)
    for _ in range(10):
        s.write(b"CTRL,83,0.0\n"); time.sleep(0.05)
    s.close()
    print(">>> Pico au NEUTRE (roues droites, gaz 0)")
except Exception as e:
    print(f">>> Pico injoignable ({e}) -> coupe l'interrupteur ESC !")
PYEOF
echo ">>> Tous les noeuds tues. Voiture stoppee."
