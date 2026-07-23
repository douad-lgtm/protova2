#!/usr/bin/env python3
"""
monitor_5g.py - Superviseur PASSIF du lien 5G (ProtoVA).
Recree d'apres specs (l'original etait sur la Jetson). Bibliotheque STANDARD
seulement (aucun pip). Tableau de bord web sur le port 8088.

Mesure, chaque seconde :
  - Latence : RTT ICMP (ping) + RTT TCP de la connexion Zenoh (via `ss`)
  - Debit 5G : RX/TX en Mbps (compteurs /sys, formule octets*8/dt/1e6)
  - Charge reseau : paquets/s RX/TX
  - Hz d'un topic ROS (ex. /joy) - best effort
  - iperf3 periodique (toutes les 60 s, 3 s) comme 4e mesure
  - Etat du lien Zenoh (ESTAB / DOWN)

Log : ~/monitor_5g.log au format
  [HH:MM:SS] rtt=Xms tcp=Xms loss=X% rx=XMbps tx=XMbps joy=XHz zenoh=ESTAB/DOWN

Lancer :  python3 monitor_5g.py     puis ouvrir  http://<ip_5g>:8088/
Env : IFACE (interface 5G, def 5g0), PEER (IP du PC/hub Zenoh, def 172.16.48.7)
"""
import collections
import http.server
import json
import os
import re
import subprocess
import threading
import time

IFACE = os.environ.get('IFACE', '5g0')
PEER = os.environ.get('PEER', '172.16.48.7')      # PC = hub Zenoh
ZENOH_PORT = 7447
JOY_TOPIC = os.environ.get('JOY_TOPIC', '/joy')
PORT = 8088
LOG = os.path.expanduser('~/monitor_5g.log')
N = 120                                            # points d'historique

KEYS = ('t', 'rtt', 'tcp', 'loss', 'rx', 'tx', 'rxpps', 'txpps', 'iperf', 'joy')
hist = {k: collections.deque(maxlen=N) for k in KEYS}
state = {'zenoh': 'DOWN', 'joy': 0.0, 'iperf': 0.0}
lock = threading.Lock()


# ------------------------------------------------------------------ mesures
def read_stat(name):
    try:
        with open(f'/sys/class/net/{IFACE}/statistics/{name}') as f:
            return int(f.read())
    except OSError:
        return None


def ping():
    try:
        out = subprocess.run(['ping', '-c', '1', '-W', '1', PEER],
                             capture_output=True, text=True, timeout=3).stdout
        m = re.search(r'time=([\d.]+)', out)
        loss = 0.0 if m else 100.0
        return (float(m.group(1)) if m else None), loss
    except Exception:
        return None, 100.0


def tcp_rtt():
    """RTT TCP + etat de la connexion Zenoh (PEER:7447) via ss."""
    try:
        out = subprocess.run(['ss', '-tin'], capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return None, False
    target = f'{PEER}:{ZENOH_PORT}'
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if target in line:
            info = line + (lines[i + 1] if i + 1 < len(lines) else '')
            m = re.search(r'rtt:([\d.]+)', info)
            return (float(m.group(1)) if m else None), True
    return None, False


def log_line(rtt, trtt, loss, rx, tx):
    line = (f"[{time.strftime('%H:%M:%S')}] rtt={(rtt or 0):.0f}ms tcp={(trtt or 0):.0f}ms "
            f"loss={loss:.0f}% rx={rx:.2f}Mbps tx={tx:.2f}Mbps "
            f"joy={state['joy']:.0f}Hz zenoh={state['zenoh']}")
    try:
        with open(LOG, 'a') as f:
            f.write(line + '\n')
    except OSError:
        pass


# ------------------------------------------------------------------ boucles
def sampler():
    last = None
    while True:
        now = time.time()
        rxb, txb = read_stat('rx_bytes'), read_stat('tx_bytes')
        rxp, txp = read_stat('rx_packets'), read_stat('tx_packets')
        rtt, loss = ping()
        trtt, est = tcp_rtt()
        with lock:
            state['zenoh'] = 'ESTAB' if est else 'DOWN'
            if last and None not in (rxb, txb, rxp, txp, last['rxb']):
                dt = (now - last['t']) or 1.0
                rx = (rxb - last['rxb']) * 8 / dt / 1e6          # Mbps
                tx = (txb - last['txb']) * 8 / dt / 1e6
                rxpps = (rxp - last['rxp']) / dt
                txpps = (txp - last['txp']) / dt
                hist['t'].append(time.strftime('%H:%M:%S'))
                hist['rtt'].append(round(rtt, 1) if rtt else None)
                hist['tcp'].append(round(trtt, 1) if trtt else None)
                hist['loss'].append(round(loss, 1))
                hist['rx'].append(round(rx, 4))
                hist['tx'].append(round(tx, 4))
                hist['rxpps'].append(round(rxpps, 1))
                hist['txpps'].append(round(txpps, 1))
                hist['iperf'].append(state['iperf'])
                hist['joy'].append(state['joy'])
                log_line(rtt, trtt, loss, rx, tx)
            last = {'t': now, 'rxb': rxb, 'txb': txb, 'rxp': rxp, 'txp': txp}
        time.sleep(1)


def iperf_loop():
    while True:
        try:
            out = subprocess.run(['iperf3', '-c', PEER, '-t', '3', '-J'],
                                 capture_output=True, text=True, timeout=20).stdout
            d = json.loads(out)
            state['iperf'] = round(d['end']['sum_received']['bits_per_second'] / 1e6, 2)
        except Exception:
            state['iperf'] = 0.0
        time.sleep(60)


def joy_loop():
    while True:
        try:
            out = subprocess.run(
                ['bash', '-lc', f'ros2 topic hz {JOY_TOPIC} --window 10 2>/dev/null'],
                capture_output=True, text=True, timeout=6).stdout
            m = re.search(r'average rate:\s*([\d.]+)', out)
            state['joy'] = float(m.group(1)) if m else 0.0
        except Exception:
            state['joy'] = 0.0
        time.sleep(5)


# ------------------------------------------------------------------ web
def snapshot():
    with lock:
        data = {k: list(hist[k]) for k in KEYS}
        data['zenoh'] = state['zenoh']
    return data


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Monitor 5G - ProtoVA</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 body{font-family:system-ui,Arial;margin:0;background:#0f1220;color:#e8eaf0}
 header{background:#1a237e;padding:12px 18px;display:flex;gap:22px;flex-wrap:wrap;align-items:center}
 header h1{font-size:18px;margin:0;margin-right:12px}
 .tile{background:#262a44;border-radius:8px;padding:8px 14px;min-width:110px}
 .tile b{display:block;font-size:22px}.tile span{font-size:11px;opacity:.7}
 .badge{padding:4px 12px;border-radius:14px;font-weight:bold}
 .up{background:#2e7d32}.down{background:#c62828}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:16px}
 .card{background:#181b2e;border-radius:10px;padding:10px}
 .card h3{margin:2px 0 6px;font-size:13px;color:#9fa8da}
 canvas{width:100%;height:180px}
 @media(max-width:800px){.grid{grid-template-columns:1fr}}
</style></head><body>
<header>
 <h1>Monitor 5G - ProtoVA</h1>
 <div class="tile"><b id="h_rtt">-</b><span>Latence (ms)</span></div>
 <div class="tile"><b id="h_rx">-</b><span>Debit &#8595; (Mbps)</span></div>
 <div class="tile"><b id="h_tx">-</b><span>Debit &#8593; (Mbps)</span></div>
 <span id="zenoh" class="badge down">Zenoh: DOWN</span>
</header>
<div class="grid">
 <div class="card"><h3>Latence (ICMP + TCP Zenoh) - ms</h3><canvas id="c_lat"></canvas></div>
 <div class="card"><h3>Debit 5G (RX/TX) - Mbps</h3><canvas id="c_thr"></canvas></div>
 <div class="card"><h3>Charge reseau (RX/TX) - paquets/s</h3><canvas id="c_pps"></canvas></div>
 <div class="card"><h3>iperf3 (Mbps, toutes les 60 s)</h3><canvas id="c_ip"></canvas></div>
</div>
<script>
function draw(id, series, colors){
 const c=document.getElementById(id), dpr=devicePixelRatio||1;
 const W=c.clientWidth, H=c.clientHeight; c.width=W*dpr; c.height=H*dpr;
 const x=c.getContext('2d'); x.scale(dpr,dpr); x.clearRect(0,0,W,H);
 let max=1; series.forEach(s=>s.forEach(v=>{if(v!=null&&v>max)max=v;}));
 x.strokeStyle='#333a5a'; x.beginPath(); x.moveTo(0,H-1); x.lineTo(W,H-1); x.stroke();
 series.forEach((s,i)=>{ x.strokeStyle=colors[i]; x.lineWidth=2; x.beginPath(); let started=false;
   s.forEach((v,j)=>{ if(v==null){return;} const px=s.length<2?0:j/(s.length-1)*W;
     const py=H-4-(v/max)*(H-10); if(!started){x.moveTo(px,py);started=true;}else x.lineTo(px,py);});
   x.stroke(); });
 x.fillStyle='#9fa8da'; x.font='11px system-ui'; x.fillText('max '+max.toFixed(1),4,12);
}
async function tick(){
 let d; try{ d=await (await fetch('/data')).json(); }catch(e){return;}
 const last=a=>a&&a.length?a[a.length-1]:null;
 document.getElementById('h_rtt').textContent=(last(d.rtt)??'-');
 document.getElementById('h_rx').textContent=(last(d.rx)??0).toFixed(2);
 document.getElementById('h_tx').textContent=(last(d.tx)??0).toFixed(2);
 const z=document.getElementById('zenoh'); z.textContent='Zenoh: '+d.zenoh;
 z.className='badge '+(d.zenoh==='ESTAB'?'up':'down');
 draw('c_lat',[d.rtt,d.tcp],['#42a5f5','#ffb74d']);
 draw('c_thr',[d.rx,d.tx],['#66bb6a','#ef5350']);
 draw('c_pps',[d.rxpps,d.txpps],['#26c6da','#ab47bc']);
 draw('c_ip',[d.iperf],['#ffca28']);
}
setInterval(tick,1000); tick();
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith('/data'):
            body = json.dumps(snapshot()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = PAGE.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main():
    for fn in (sampler, iperf_loop, joy_loop):
        threading.Thread(target=fn, daemon=True).start()
    print(f"Monitor 5G : http://<ip_5g>:{PORT}/   (iface={IFACE}, peer={PEER})")
    http.server.ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
