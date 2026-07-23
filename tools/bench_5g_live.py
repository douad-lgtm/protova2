#!/usr/bin/env python3
"""
bench_5g_live.py - Benchmark ACTIF du lien 5G (ProtoVA).
Recree d'apres specs. Bibliotheque STANDARD seulement. Tableau de bord web
sur le port 8089. Mesure la CAPACITE du lien (iperf3 au coeur).

Toutes les 30 s : iperf3 5 s en montant (UL) + 5 s en descendant (DL, -R).
En continu (1 s) : latence ICMP, trafic passif (kb/s), perte de paquets.
4 graphes : Latence ICMP, Debit iperf3 TCP (UL/DL, Mbps), Trafic passif kb/s,
            Perte paquets %.
Bouton "Tester maintenant" -> lance un iperf3 immediat.
Affiche une erreur si `iperf3 -s` n'est pas lance sur le PC.
AUCUNE dependance ROS / Zenoh.

Prerequis : sur le PC (PEER), lancer d'abord :  iperf3 -s
Lancer :  python3 bench_5g_live.py    puis ouvrir  http://<ip_5g>:8089/
Env : IFACE (interface 5G, def 5g0), PEER (IP du PC, def 172.16.48.7)
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
PEER = os.environ.get('PEER', '172.16.48.7')
PORT = 8089
N = 120

KEYS = ('t', 'rtt', 'loss', 'ul', 'dl', 'rxkb', 'txkb')
hist = {k: collections.deque(maxlen=N) for k in KEYS}
state = {'ul': 0.0, 'dl': 0.0, 'err': '', 'running': False}
lock = threading.Lock()


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
        return (float(m.group(1)) if m else None), (0.0 if m else 100.0)
    except Exception:
        return None, 100.0


def iperf_once(reverse):
    """Un test iperf3 de 5 s. Retourne les Mbps, ou leve une erreur explicite."""
    cmd = ['iperf3', '-c', PEER, '-t', '5', '-J']
    if reverse:
        cmd.append('-R')
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(out.stderr.strip() or 'iperf3 injoignable (serveur lance ?)')
    d = json.loads(out.stdout)
    if 'error' in d:
        raise RuntimeError(d['error'])
    return round(d['end']['sum_received']['bits_per_second'] / 1e6, 2)


def run_iperf():
    with lock:
        if state['running']:
            return
        state['running'] = True
    try:
        ul = iperf_once(reverse=False)
        dl = iperf_once(reverse=True)
        with lock:
            state['ul'], state['dl'], state['err'] = ul, dl, ''
    except Exception as e:
        with lock:
            state['err'] = ('iperf3 -s non lance sur le PC ? ' + str(e))[:160]
            state['ul'] = state['dl'] = 0.0
    finally:
        with lock:
            state['running'] = False


def bench_loop():
    while True:
        run_iperf()
        time.sleep(30)


def passive_loop():
    last = None
    while True:
        now = time.time()
        rxb, txb = read_stat('rx_bytes'), read_stat('tx_bytes')
        rtt, loss = ping()
        with lock:
            if last and None not in (rxb, txb, last['rxb']):
                dt = (now - last['t']) or 1.0
                rxkb = (rxb - last['rxb']) * 8 / dt / 1e3       # kb/s
                txkb = (txb - last['txb']) * 8 / dt / 1e3
                hist['t'].append(time.strftime('%H:%M:%S'))
                hist['rtt'].append(round(rtt, 1) if rtt else None)
                hist['loss'].append(round(loss, 1))
                hist['ul'].append(state['ul'])
                hist['dl'].append(state['dl'])
                hist['rxkb'].append(round(rxkb, 1))
                hist['txkb'].append(round(txkb, 1))
            last = {'t': now, 'rxb': rxb, 'txb': txb}
        time.sleep(1)


def snapshot():
    with lock:
        d = {k: list(hist[k]) for k in KEYS}
        d['err'] = state['err']
        d['ul_now'] = state['ul']
        d['dl_now'] = state['dl']
    return d


PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Bench 5G live - ProtoVA</title><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 body{font-family:system-ui,Arial;margin:0;background:#0f1220;color:#e8eaf0}
 header{background:#00695c;padding:12px 18px;display:flex;gap:20px;flex-wrap:wrap;align-items:center}
 header h1{font-size:18px;margin:0;margin-right:10px}
 .tile{background:#173a36;border-radius:8px;padding:8px 14px;min-width:120px}
 .tile b{display:block;font-size:22px}.tile span{font-size:11px;opacity:.7}
 button{background:#ffca28;border:0;border-radius:8px;padding:9px 16px;font-weight:bold;cursor:pointer}
 #err{color:#ff8a80;font-size:13px;padding:0 18px}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:16px}
 .card{background:#181b2e;border-radius:10px;padding:10px}
 .card h3{margin:2px 0 6px;font-size:13px;color:#80cbc4}
 canvas{width:100%;height:180px}
 @media(max-width:800px){.grid{grid-template-columns:1fr}}
</style></head><body>
<header>
 <h1>Bench 5G live - ProtoVA</h1>
 <div class="tile"><b id="h_dl">-</b><span>Debit &#8595; DL (Mbps)</span></div>
 <div class="tile"><b id="h_ul">-</b><span>Debit &#8593; UL (Mbps)</span></div>
 <button onclick="fetch('/run')">&#9654; Tester maintenant</button>
</header>
<div id="err"></div>
<div class="grid">
 <div class="card"><h3>Latence ICMP - ms</h3><canvas id="c_lat"></canvas></div>
 <div class="card"><h3>Debit iperf3 TCP (UL/DL) - Mbps</h3><canvas id="c_ip"></canvas></div>
 <div class="card"><h3>Trafic passif (RX/TX) - kb/s</h3><canvas id="c_kb"></canvas></div>
 <div class="card"><h3>Perte de paquets - %</h3><canvas id="c_loss"></canvas></div>
</div>
<script>
function draw(id, series, colors){
 const c=document.getElementById(id), dpr=devicePixelRatio||1;
 const W=c.clientWidth, H=c.clientHeight; c.width=W*dpr; c.height=H*dpr;
 const x=c.getContext('2d'); x.scale(dpr,dpr); x.clearRect(0,0,W,H);
 let max=1; series.forEach(s=>s.forEach(v=>{if(v!=null&&v>max)max=v;}));
 x.strokeStyle='#333a5a'; x.beginPath(); x.moveTo(0,H-1); x.lineTo(W,H-1); x.stroke();
 series.forEach((s,i)=>{ x.strokeStyle=colors[i]; x.lineWidth=2; x.beginPath(); let st=false;
   s.forEach((v,j)=>{ if(v==null)return; const px=s.length<2?0:j/(s.length-1)*W;
     const py=H-4-(v/max)*(H-10); if(!st){x.moveTo(px,py);st=true;}else x.lineTo(px,py);});
   x.stroke(); });
 x.fillStyle='#80cbc4'; x.font='11px system-ui'; x.fillText('max '+max.toFixed(1),4,12);
}
async function tick(){
 let d; try{ d=await (await fetch('/data')).json(); }catch(e){return;}
 document.getElementById('h_dl').textContent=(d.dl_now??0).toFixed(1);
 document.getElementById('h_ul').textContent=(d.ul_now??0).toFixed(1);
 document.getElementById('err').textContent=d.err||'';
 draw('c_lat',[d.rtt],['#42a5f5']);
 draw('c_ip',[d.ul,d.dl],['#ef5350','#66bb6a']);
 draw('c_kb',[d.rxkb,d.txkb],['#26c6da','#ab47bc']);
 draw('c_loss',[d.loss],['#ff7043']);
}
setInterval(tick,1000); tick();
</script></body></html>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith('/data'):
            self._send(json.dumps(snapshot()).encode(), 'application/json')
        elif self.path.startswith('/run'):
            threading.Thread(target=run_iperf, daemon=True).start()
            self._send(b'ok', 'text/plain')
        else:
            self._send(PAGE.encode(), 'text/html; charset=utf-8')

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    threading.Thread(target=passive_loop, daemon=True).start()
    threading.Thread(target=bench_loop, daemon=True).start()
    print(f"Bench 5G live : http://<ip_5g>:{PORT}/   (iface={IFACE}, peer={PEER})")
    print("Prerequis : lancer 'iperf3 -s' sur le PC (PEER).")
    http.server.ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
