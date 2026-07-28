#!/usr/bin/env python3
"""Bench YOLO GPU vs CPU sur la Jetson."""
import time, numpy as np, torch
from ultralytics import YOLO

print("torch", torch.__version__, "| CUDA:", torch.cuda.is_available(), flush=True)
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0), flush=True)

img = (np.random.rand(720, 1280, 3) * 255).astype(np.uint8)
m = YOLO('yolov8n.pt')

for dev in (['cpu', 'cuda'] if torch.cuda.is_available() else ['cpu']):
    m.to(dev)
    for _ in range(3):                       # warmup
        m(img, verbose=False, device=dev)
    if dev == 'cuda':
        torch.cuda.synchronize()
    t0 = time.time()
    N = 15
    for _ in range(N):
        m(img, verbose=False, device=dev)
    if dev == 'cuda':
        torch.cuda.synchronize()
    dt = (time.time() - t0) / N
    print(f"{dev.upper():5s} : {dt*1000:6.1f} ms/image  ({1/dt:5.1f} FPS)", flush=True)
