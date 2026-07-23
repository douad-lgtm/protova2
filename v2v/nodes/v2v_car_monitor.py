#!/usr/bin/env python3
"""
Moniteur V2V terrain (cote PC) — DEMO EN CONDITIONS REELLES.

La voiture (Jetson) roule et emet des CAM ETSI portant sa position, son CAP et sa
VITESSE reels (issus de l'odometrie). Ce script, lance sur le PC que l'on tient en
suivant la voiture, RECOIT ces CAM et affiche un tableau de bord en direct :
position, cap (avec fleche/boussole), vitesse (m/s et km/h), distance au PC et
alerte de proximite.

Il lance socktap lui-meme : PAS besoin de ROS sur le PC. Il emet aussi la position
(statique) du PC, pour que la voiture puisse a son tour "voir" le PC.

Usage typique (le PC est sur le WiFi commun) :
  python3 v2v_car_monitor.py --iface wlp2s0 --my-lat 48.76680 --my-lon 11.43200 \
      --alert 5 --socktap ~/vanetza/build/bin/socktap
Arret : Ctrl-C.
"""
import argparse
import math
import os
import subprocess
import sys
import time

HEADING_UNAVAILABLE = 3601      # sentinelle ETSI (0,1 deg)
SPEED_UNAVAILABLE = 16383       # sentinelle ETSI (0,01 m/s)

CARDINAUX = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO']
FLECHES = ['^', '/', '>', '\\', 'v', '/', '<', '\\']  # ASCII, robuste en SSH


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def cardinal(deg):
    idx = int((deg % 360) / 45.0 + 0.5) % 8
    return CARDINAUX[idx], FLECHES[idx]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iface', default='wlp2s0', help='interface WiFi du PC')
    ap.add_argument('--my-lat', type=float, default=48.76680, help='latitude du PC (reference distance)')
    ap.add_argument('--my-lon', type=float, default=11.43200, help='longitude du PC')
    ap.add_argument('--alert', type=float, default=5.0, help='seuil d alerte proximite (m)')
    ap.add_argument('--station-id', type=int, default=1, help='ID station du PC')
    ap.add_argument('--socktap', default=os.path.expanduser('~/vanetza/build/bin/socktap'))
    args = ap.parse_args()

    cmd = [args.socktap, '-l', 'udp', '-i', args.iface, '-a', 'ca',
           '--print-rx-cam', '--security', 'none', '--station-id', str(args.station_id),
           '-p', 'static', '--latitude', str(args.my_lat), '--longitude', str(args.my_lon)]

    print("=" * 72)
    print(" MONITEUR V2V TERRAIN — reception des CAM de la voiture")
    print(f"   interface={args.iface}  PC=({args.my_lat},{args.my_lon})  alerte<{args.alert} m")
    print("   " + " ".join(cmd))
    print("=" * 72)
    print("En attente des CAM de la voiture (fais-la rouler)...\n")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    cur = {}
    n_cam = 0
    t_last = None
    hz = 0.0
    try:
        for raw in proc.stdout:
            line = raw.strip()
            try:
                if line.startswith('Station ID:'):
                    cur = {'id': int(line.split(':')[1])}
                elif line.startswith('Longitude:') and cur:
                    cur['lon'] = int(line.split(':')[1]) * 1e-7
                elif line.startswith('Latitude:') and cur:
                    cur['lat'] = int(line.split(':')[1]) * 1e-7
                elif line.startswith('Heading') and cur:
                    cur['heading_raw'] = int(line.split(':')[1].split('[')[0])
                elif line.startswith('Speed') and cur:
                    cur['speed_raw'] = int(line.split(':')[1].split('[')[0])
                    if 'lat' in cur and 'lon' in cur and cur['id'] != args.station_id:
                        now = time.time()
                        if t_last is not None:
                            dt = now - t_last
                            if dt > 0:
                                hz = 0.7 * hz + 0.3 * (1.0 / dt)
                        t_last = now
                        n_cam += 1
                        _display(cur, args, n_cam, hz)
                        cur = {}
            except (ValueError, IndexError):
                pass
    except KeyboardInterrupt:
        pass
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        print("\nArret du moniteur.")


def _display(v, args, n_cam, hz):
    dist = haversine(args.my_lat, args.my_lon, v['lat'], v['lon'])

    hr = v.get('heading_raw', HEADING_UNAVAILABLE)
    if hr == HEADING_UNAVAILABLE:
        cap_txt = "cap  --  (indispo)"
    else:
        deg = hr * 0.1
        card, fleche = cardinal(deg)
        cap_txt = f"cap {deg:5.1f} {card:>2} {fleche}"

    sr = v.get('speed_raw', SPEED_UNAVAILABLE)
    if sr == SPEED_UNAVAILABLE:
        v_txt = "v  --  (indispo)"
    else:
        mps = sr * 0.01
        v_txt = f"v {mps:5.2f} m/s ({mps * 3.6:5.1f} km/h)"

    alerte = "  *** ALERTE <{:.0f}m ***".format(args.alert) if dist < args.alert else ""
    ligne = (f"[voiture #{v['id']}] {v['lat']:.6f},{v['lon']:.6f} | {cap_txt} | "
             f"{v_txt} | dist {dist:5.1f} m | {n_cam:4d} CAM @ {hz:3.1f} Hz{alerte}")
    # ecrase la ligne precedente (tableau de bord "live")
    sys.stdout.write("\r" + ligne + " " * 6)
    sys.stdout.flush()
    if alerte:
        sys.stdout.write("\n")  # garde une trace des alertes


if __name__ == '__main__':
    main()
