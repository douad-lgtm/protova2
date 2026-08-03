#!/usr/bin/env python3
"""
Banc de test du protocole serie du Pico (ProtoVA1) — roues EN L'AIR.

Question a trancher : le firmware attend-il
  Convention A (comme TX.py)      : CTRL,<angle 28..138>,<vitesse m/s>   ex CTRL,83,0.120
  Convention B (comme test_pico)  : CTRL,<angle 60..120>,<PWM us>        ex CTRL,90,1600

Methode OBJECTIVE : l'encodeur est cable -> si le moteur tourne, le Pico
renvoie des lignes TICKS,<n> avec n != 0. On essaie chaque convention 2 s
et on compte les ticks recus. Zero intervention humaine necessaire.

Etapes :
  1. lecture seule 3 s  -> voir ce que le firmware emet spontanement
  2. convention A : neutre, puis avance douce 2 s, puis neutre -> ticks ?
  3. convention B : neutre, puis avance douce 2 s, puis neutre -> ticks ?
  4. verdict
"""
import serial
import time

PORT = '/dev/ttyACM0'
BAUD = 115200


def lire(ser, duree):
    """Lit le port pendant `duree` s ; retourne (lignes, somme_ticks)."""
    lignes, total_ticks = [], 0
    fin = time.time() + duree
    while time.time() < fin:
        try:
            line = ser.readline().decode('utf-8', errors='replace').strip()
        except Exception:
            continue
        if not line:
            continue
        lignes.append(line)
        if line.startswith('TICKS,'):
            try:
                total_ticks += abs(int(line.split(',')[1]))
            except (ValueError, IndexError):
                pass
    return lignes, total_ticks


def envoyer(ser, msg):
    ser.write((msg + '\n').encode('utf-8'))
    print(f'  -> envoye : {msg}')


ser = serial.Serial(PORT, BAUD, timeout=0.05)
time.sleep(2)                      # laisser le Pico (re)demarrer
ser.reset_input_buffer()

print('=== 1) ECOUTE SEULE (3 s) : que dit le firmware ? ===')
lignes, ticks = lire(ser, 3)
uniques = sorted(set(l.split(',')[0] for l in lignes if ',' in l))
print(f'  {len(lignes)} lignes recues | prefixes : {uniques or "AUCUN"}')
for l in lignes[:5]:
    print(f'  exemple : {l}')

print('=== 2) CONVENTION A : CTRL,angle(83),vitesse m/s ===')
envoyer(ser, 'CTRL,83,0.0')
time.sleep(1)
ser.reset_input_buffer()
envoyer(ser, 'CTRL,83,0.12')
lignes, ticks_a = lire(ser, 2)
envoyer(ser, 'CTRL,83,0.0')
time.sleep(1)
print(f'  ticks pendant l essai A : {ticks_a}')

print('=== 3) CONVENTION B : CTRL,angle(90),PWM us ===')
ser.reset_input_buffer()
envoyer(ser, 'CTRL,90,1500')
time.sleep(1)
ser.reset_input_buffer()
envoyer(ser, 'CTRL,90,1580')
lignes, ticks_b = lire(ser, 2)
envoyer(ser, 'CTRL,90,1500')
print(f'  ticks pendant l essai B : {ticks_b}')

print('=== VERDICT ===')
if ticks_a > 5 and ticks_a > ticks_b:
    print(f'  ==> CONVENTION A (angle + m/s, comme TX.py)  [A={ticks_a}, B={ticks_b}]')
elif ticks_b > 5 and ticks_b > ticks_a:
    print(f'  ==> CONVENTION B (angle + PWM us)            [A={ticks_a}, B={ticks_b}]')
else:
    print(f'  ==> AUCUN mouvement detecte (A={ticks_a}, B={ticks_b}) :')
    print('      verifier ESC allume / encodeur cable / firmware flashe')

ser.close()
