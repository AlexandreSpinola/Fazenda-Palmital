"""
Testa o detector treinado num video, mostrando as deteccoes na tela.

Uso:
    python testar_detector.py "gravações\NOME_DO_VIDEO.avi"
    python testar_detector.py "gravações\NOME_DO_VIDEO.avi" --modelo outro_modelo.pt
"""
import argparse

import cv2
from ultralytics import YOLO

p = argparse.ArgumentParser()
p.add_argument("video")
p.add_argument("--modelo", default="detector_vacas_v1.pt")
args = p.parse_args()

model = YOLO(args.modelo)
cap = cv2.VideoCapture(args.video)
print("Pressione 'q' para sair.")

while cap.isOpened():
    ok, frame = cap.read()
    if not ok:
        print("Fim do video.")
        break
    resultados = model.track(frame, persist=True, verbose=False)
    frame_anotado = resultados[0].plot()
    cv2.imshow("Detector de vacas v1", cv2.resize(frame_anotado, (1280, 720)))
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
