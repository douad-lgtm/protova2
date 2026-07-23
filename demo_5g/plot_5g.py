#!/usr/bin/env python3
"""Parse monitor_5g.log and plot latency, throughput, network load curves."""
import re
import sys
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

LOG_FILE = sys.argv[1] if len(sys.argv) > 1 else 'monitor_5g.log'

RE = re.compile(
    r'\[(\d{2}:\d{2}:\d{2})\] '
    r'rtt=([\d.]+|None)ms tcp=([\d.]+|None)ms '
    r'loss=([\d.]+|None)% '
    r'rx=([\d.]+|None)kb/s tx=([\d.]+|None)kb/s '
    r'joy=([\d.]+|None)Hz zenoh=(\w+)'
)

times, rtt, tcp, loss, rx, tx, joy, zenoh = [], [], [], [], [], [], [], []

with open(LOG_FILE) as f:
    for line in f:
        m = RE.search(line)
        if not m:
            continue
        t = datetime.strptime(m.group(1), '%H:%M:%S').replace(year=2026, month=6, day=15)
        times.append(t)
        def v(s): return float(s) if s != 'None' else np.nan
        rtt.append(v(m.group(2)))
        tcp.append(v(m.group(3)))
        loss.append(v(m.group(4)))
        rx.append(v(m.group(5)))
        tx.append(v(m.group(6)))
        joy.append(v(m.group(7)))
        zenoh.append(1 if m.group(8) == 'ESTAB' else 0)

times = np.array(times)
rtt   = np.array(rtt)
tcp   = np.array(tcp)
loss  = np.array(loss)
rx    = np.array(rx)
tx    = np.array(tx)
joy   = np.array(joy)

fig, axes = plt.subplots(4, 1, figsize=(14, 16), sharex=True)
fig.suptitle('Lien 5G ProtoVA2 — Analyse session', fontsize=14, fontweight='bold')

FMT = mdates.DateFormatter('%H:%M')

# --- Latence ---
ax = axes[0]
ax.plot(times, rtt, color='#4fc3f7', linewidth=1.2, label='ICMP RTT')
ax.plot(times, tcp, color='#ffb74d', linewidth=1.2, label='TCP RTT (Zenoh :7447)')
ax.axhline(np.nanmean(rtt), color='#4fc3f7', linestyle='--', linewidth=0.8, alpha=0.6,
           label=f'Moy ICMP {np.nanmean(rtt):.1f} ms')
ax.axhline(np.nanmean(tcp), color='#ffb74d', linestyle='--', linewidth=0.8, alpha=0.6,
           label=f'Moy TCP  {np.nanmean(tcp):.1f} ms')
ax.set_ylabel('Latence (ms)')
ax.set_ylim(bottom=0)
ax.legend(fontsize=8, loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_title('Latence', fontsize=10)

# --- Débit ---
ax = axes[1]
ax.fill_between(times, rx, alpha=0.35, color='#66bb6a')
ax.fill_between(times, tx, alpha=0.35, color='#ef5350')
ax.plot(times, rx, color='#66bb6a', linewidth=1.0, label='RX ↓')
ax.plot(times, tx, color='#ef5350', linewidth=1.0, label='TX ↑')
ax.set_ylabel('Débit (kb/s)')
ax.set_ylim(bottom=0)
ax.legend(fontsize=8, loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_title('Débit 5G', fontsize=10)

# --- Charge réseau : perte paquets ---
ax = axes[2]
ax.bar(times, loss, width=0.0025, color='#ef5350', alpha=0.8, label='Perte ICMP (%)')
ax.set_ylabel('Perte (%)')
ax.set_ylim(0, max(np.nanmax(loss) * 1.5, 12))
ax.legend(fontsize=8, loc='upper right')
ax.grid(True, alpha=0.3, axis='y')
ax.set_title('Perte paquets', fontsize=10)

# --- Fréquence /joy ---
ax = axes[3]
valid = ~np.isnan(joy)
ax.plot(times[valid], joy[valid], color='#4fc3f7', linewidth=1.2, label='/joy Hz')
ax.axhline(np.nanmean(joy), color='#4fc3f7', linestyle='--', linewidth=0.8, alpha=0.6,
           label=f'Moy {np.nanmean(joy):.1f} Hz')
ax.set_ylabel('Hz')
ax.set_ylim(bottom=0)
ax.legend(fontsize=8, loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_title('Fréquence topic /joy (commandes joystick reçues)', fontsize=10)
ax.xaxis.set_major_formatter(FMT)

fig.autofmt_xdate()
plt.tight_layout()
out = LOG_FILE.replace('.log', '_curves.png')
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f'Saved: {out}')
