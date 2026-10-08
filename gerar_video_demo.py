"""
Gera um video demo com as deteccoes e IDs de rastreamento desenhados.

Uso:
    python gerar_video_demo.py "gravações\VIDEO.avi" --saida demo.mp4
"""
import argparse

import cv2
from ultralytics import YOLO

p = argparse.ArgumentParser()
p.add_argument("video")
p.add_argument("--modelo", default="detector_vacas_v1.pt")
p.add_argument("--saida", default="demo_detector.mp4")
p.add_argument("--fps_saida", type=float, default=10,
               help="fps do video final (acelera videos de 1 fps)")
args = p.parse_args()

model = YOLO(args.modelo)
cap = cv2.VideoCapture(args.video)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

saida = cv2.VideoWriter(args.saida, cv2.VideoWriter_fourcc(*"mp4v"),
                        args.fps_saida, (w, h))
n = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    resultados = model.track(frame, persist=True, verbose=False)
    saida.write(resultados[0].plot())
    n += 1
    if n % 100 == 0:
        print(f"{n}/{total} frames...")

cap.release()
saida.release()
print(f"Demo pronta: {args.saida} ({n} frames)")
