"""
Extrai frames de vídeos das câmeras a cada N segundos e salva como JPG.
Opcionalmente filtra frames sem vaca usando YOLO (--filtrar-vacas).

Uso:
    python extrair_frames.py "caminho/do/video.avi"
    python extrair_frames.py "caminho/do/video.avi" --intervalo 2
    python extrair_frames.py "caminho/do/video.avi" --intervalo 10 --filtrar-vacas
"""
import argparse
import csv
import os
from datetime import datetime

import cv2

ARQUIVO_LOG = "videos_processados.csv"


def ja_processado(nome_video):
    if not os.path.exists(ARQUIVO_LOG):
        return False
    with open(ARQUIVO_LOG, newline="", encoding="utf-8") as f:
        return any(linha["video"] == nome_video for linha in csv.DictReader(f))


def registrar_no_log(nome_video, intervalo, frames_salvos, duracao_min):
    novo = not os.path.exists(ARQUIVO_LOG)
    with open(ARQUIVO_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["video", "data_processamento", "intervalo_seg",
                        "frames_salvos", "duracao_min"])
        w.writerow([nome_video, datetime.now().strftime("%Y-%m-%d %H:%M"),
                    intervalo, frames_salvos, f"{duracao_min:.1f}"])


def extrair(caminho_video, intervalo_seg, pasta_saida, filtrar_vacas):
    nome_video = os.path.basename(caminho_video)
    if ja_processado(nome_video):
        print(f"PULADO (ja consta no log {ARQUIVO_LOG}): {nome_video}")
        return

    cap = cv2.VideoCapture(caminho_video)
    if not cap.isOpened():
        print(f"ERRO: nao consegui abrir o video: {caminho_video}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0:
        fps = 1.0  # fallback para arquivos com metadados quebrados
    duracao = total_frames / fps
    print(f"Video: {os.path.basename(caminho_video)}")
    print(f"FPS: {fps:.2f} | Frames: {total_frames} | Duracao: {duracao/60:.1f} min")

    modelo = None
    if filtrar_vacas:
        from ultralytics import YOLO
        modelo = YOLO("yolo11n.pt")
        print("Filtro de vacas ativado (YOLO11n, classe 'cow').")

    os.makedirs(pasta_saida, exist_ok=True)
    nome_base = os.path.splitext(os.path.basename(caminho_video))[0]
    # Nome curto para os arquivos de saida (os nomes do NVR sao gigantes)
    nome_curto = nome_base[:40].replace(" ", "_")

    passo = max(1, round(fps * intervalo_seg))  # frames a pular entre capturas
    salvos, descartados, idx = 0, 0, 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % passo == 0:
            segundos = idx / fps
            manter = True
            if modelo is not None:
                # O YOLO pre-treinado (COCO) nao reconhece bem vacas vistas
                # de cima: costuma chutar person/dog/horse. Entao aceitamos
                # qualquer detecao "grande" dessas classes com conf baixa,
                # como um filtro de "tem algo no frame".
                # COCO: 0=person 16=dog 17=horse 18=sheep 19=cow 20=elephant 21=bear
                resultado = modelo(frame, classes=[0, 16, 17, 18, 19, 20, 21],
                                   conf=0.15, verbose=False)[0]
                manter = len(resultado.boxes) > 0
            if manter:
                nome_arq = f"{nome_curto}_t{int(segundos):05d}s.jpg"
                # imencode + tofile em vez de imwrite: imwrite falha em
                # caminhos com acentos no Windows (ex.: "Visão")
                ok_enc, buf = cv2.imencode(".jpg", frame,
                                           [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ok_enc:
                    buf.tofile(os.path.join(pasta_saida, nome_arq))
                    salvos += 1
            else:
                descartados += 1
            if (salvos + descartados) % 50 == 0:
                print(f"  progresso: {segundos/60:.1f} min processados, {salvos} salvos...")
        idx += 1

    cap.release()
    registrar_no_log(nome_video, intervalo_seg, salvos, duracao / 60)
    print(f"\nConcluido: {salvos} frames salvos em '{pasta_saida}'"
          + (f" ({descartados} descartados sem vaca)" if modelo else "")
          + f" | registrado em {ARQUIVO_LOG}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extrai frames de video a cada N segundos")
    p.add_argument("video", help="caminho do arquivo de video (.avi, .mp4...)")
    p.add_argument("--intervalo", type=float, default=2.0,
                   help="segundos entre frames extraidos (padrao: 2)")
    p.add_argument("--saida", default="frames",
                   help="pasta de saida (padrao: ./frames)")
    p.add_argument("--filtrar-vacas", action="store_true",
                   help="descarta frames sem vaca detectada (mais lento)")
    args = p.parse_args()
    extrair(args.video, args.intervalo, args.saida, args.filtrar_vacas)
