#!/usr/bin/env python3
"""Visualiseur de carte SLAM en direct — contourne le bug d'affichage RViz.

S'abonne a /map (slam_toolbox) + TF map->base_link, rend la carte en PNG
et la sert sur http://localhost:8090 (rafraichissement auto 1 s).
Blanc = libre, noir = mur, gris = inconnu, triangle rouge = la voiture.
"""
import io
import math
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from nav_msgs.msg import OccupancyGrid
from PIL import Image, ImageDraw
from tf2_ros import Buffer, TransformListener

SCALE = 4  # agrandissement pixels

PAGE = b"""<!doctype html><html><head><meta charset="utf-8">
<title>Carte SLAM ProtoVA2</title>
<style>body{background:#222;color:#eee;font-family:sans-serif;text-align:center}
img{image-rendering:pixelated;border:1px solid #555;max-width:95vw;max-height:85vh}</style>
</head><body>
<h3>Carte SLAM ProtoVA2 <small id="s"></small></h3>
<img id="m" src="/map.png">
<script>
setInterval(()=>{document.getElementById('m').src='/map.png?'+Date.now();},1000);
setInterval(()=>{fetch('/status').then(r=>r.text()).then(t=>{document.getElementById('s').textContent=t;});},1000);
</script></body></html>"""


class MapViz(Node):
    def __init__(self):
        super().__init__('map_live_viz')
        self.grid = None
        self.lock = threading.Lock()
        qos = QoSProfile(depth=1,
                         reliability=QoSReliabilityPolicy.RELIABLE,
                         durability=QoSDurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(OccupancyGrid, '/map', self.cb, qos)
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

    def cb(self, msg):
        with self.lock:
            self.grid = msg

    def robot_pose(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_link',
                                                rclpy.time.Time())
            q = t.transform.rotation
            yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                             1.0 - 2.0 * (q.y * q.y + q.z * q.z))
            return t.transform.translation.x, t.transform.translation.y, yaw
        except Exception:
            return None

    def render_png(self):
        with self.lock:
            g = self.grid
        if g is None:
            img = Image.new('RGB', (320, 240), (40, 40, 40))
            ImageDraw.Draw(img).text((60, 110), 'En attente de /map ...',
                                     fill=(220, 220, 220))
        else:
            w, h = g.info.width, g.info.height
            data = np.array(g.data, dtype=np.int8).reshape(h, w)
            img_a = np.full((h, w), 128, dtype=np.uint8)   # inconnu = gris
            img_a[(data >= 0) & (data < 50)] = 255          # libre = blanc
            img_a[data >= 50] = 0                           # occupe = noir
            img_a = np.flipud(img_a)                        # y vers le haut
            img = Image.fromarray(img_a, 'L').convert('RGB')
            img = img.resize((w * SCALE, h * SCALE), Image.NEAREST)
            pose = self.robot_pose()
            if pose:
                x, y, yaw = pose
                res = g.info.resolution
                px = (x - g.info.origin.position.x) / res * SCALE
                py = (h - 1 - (y - g.info.origin.position.y) / res) * SCALE
                d = ImageDraw.Draw(img)
                r = 3 * SCALE
                pts = []
                for a in (0.0, 2.5, -2.5):
                    pts.append((px + r * math.cos(yaw + a),
                                py - r * math.sin(yaw + a)))
                d.polygon(pts, fill=(220, 30, 30))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def status(self):
        with self.lock:
            g = self.grid
        if g is None:
            return 'pas encore de carte'
        s = f'{g.info.width}x{g.info.height} @ {g.info.resolution:.2f} m/cell'
        p = self.robot_pose()
        if p:
            s += f' | voiture: x={p[0]:.2f} y={p[1]:.2f} cap={math.degrees(p[2]):.0f}\N{DEGREE SIGN}'
        return s


def main():
    rclpy.init()
    node = MapViz()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith('/map.png'):
                body, ctype = node.render_png(), 'image/png'
            elif self.path.startswith('/status'):
                body, ctype = node.status().encode(), 'text/plain; charset=utf-8'
            else:
                body, ctype = PAGE, 'text/html; charset=utf-8'
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

    srv = ThreadingHTTPServer(('0.0.0.0', 8090), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    node.get_logger().info('Carte en direct sur http://localhost:8090')
    rclpy.spin(node)


if __name__ == '__main__':
    main()
