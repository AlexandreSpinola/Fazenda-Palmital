"""
Gera um lote pre-anotado para o CVAT a partir dos videos .dav do NVR Intelbras.

Para cada video:
  1. le os frames em sequencia. O NVR grava por MOVIMENTO (o arquivo de 24h
     tem buracos), entao o horario de cada frame vem do timestamp do video,
     nunca da contagem de frames;
  2. pega 1 frame candidato a cada --intervalo segundos de video;
  3. segmenta as vacas e descarta os frames sem vaca;
  4. escolhe ate --max-por-video frames espalhados pelas horas do dia
     (variedade de luz: madrugada, manha, tarde, noite).

Saida (pasta --saida):
  imagens/             JPGs selecionados (nome = camera + data/hora)
  imagens.zip          as mesmas imagens, para criar a task no CVAT
  anotacoes_cvat.zip   pre-anotacoes (formato "CVAT for images 1.1")
  frames.csv           indice: imagem, video, camera, data_hora, n_vacas
  previews/            (com --previews) imagens com os poligonos desenhados

Modelo: por padrao usa YOLOE com o vocabulario "cow" (zero-shot, sem treino).
Depois do 1o ciclo de anotacao, passe o modelo treinado com --modelo.

Uso:
    python gerar_lote_cvat.py "Gravações\\VIDEO.dav"
    python gerar_lote_cvat.py "Gravações\\*.dav" --saida lotes\\lote_002 --previews
    python gerar_lote_cvat.py VIDEO.dav --modelo runs\\segment\\v1\\weights\\best.pt
"""
import argparse
import csv
import glob
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from comum import PASTA_PROJETO, carregar_modelo, info_video, ler_video

ROTULO = "vaca"

AREA_MIN = 2000  # px; descarta mascaras minusculas (pedaco de rabo/pata na borda)
# a barra do cocho as vezes corta a mascara em duas (cabeca / corpo);
# um fechamento morfologico une os pedacos antes de virar poligono
KERNEL_FECHAMENTO = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))


# ---------------------------------------------------------------- modelo

def mascara_para_poligono(mascara, tolerancia_px=2.0):
    m = (mascara > 0.5).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, KERNEL_FECHAMENTO)
    contornos, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None
    c = max(contornos, key=cv2.contourArea)
    if cv2.contourArea(c) < AREA_MIN:
        return None
    c = cv2.approxPolyDP(c, tolerancia_px, True).reshape(-1, 2)
    return c if len(c) >= 3 else None


def segmentar(modelo, frame, conf):
    """Retorna [(poligono Nx2, confianca), ...] das vacas no frame."""
    r = modelo.predict(frame, conf=conf, iou=0.5, retina_masks=True, verbose=False)[0]
    if r.masks is None:
        return []
    vacas = []
    for mascara, c in zip(r.masks.data.cpu().numpy(), r.boxes.conf.tolist()):
        pol = mascara_para_poligono(mascara)
        if pol is not None:
            vacas.append((pol, c))
    return vacas


# ---------------------------------------------------------------- selecao

def espalhados(lista, k):
    if k >= len(lista):
        return list(lista)
    idx = np.linspace(0, len(lista) - 1, k).round().astype(int)
    return [lista[i] for i in idx]


def selecionar(candidatos, n):
    """Ate n candidatos espalhados pelas horas do dia: cada hora recebe uma
    cota igual; o que uma hora vazia nao usa passa para as mais cheias."""
    if len(candidatos) <= n:
        return candidatos
    por_hora = defaultdict(list)
    for c in candidatos:
        por_hora[c["hora"]].append(c)
    grupos = sorted(por_hora.values(), key=len)
    escolhidos, restante = [], n
    for i, grupo in enumerate(grupos):
        pegar = espalhados(grupo, restante // (len(grupos) - i))
        escolhidos += pegar
        restante -= len(pegar)
    return sorted(escolhidos, key=lambda c: c["t"])


# ---------------------------------------------------------------- saida

def escrever_xml_cvat(registros, caminho):
    """Formato 'CVAT for images 1.1'. O id de cada imagem segue a ordem
    alfabetica dos nomes, que e a ordem padrao em que o CVAT monta a task."""
    raiz = ET.Element("annotations")
    ET.SubElement(raiz, "version").text = "1.1"
    for i, r in enumerate(registros):
        img = ET.SubElement(raiz, "image", id=str(i), name=r["imagem"],
                            width=str(r["largura"]), height=str(r["altura"]))
        for pol, _ in r["vacas"]:
            ET.SubElement(img, "polygon", label=ROTULO, source="auto",
                          occluded="0", z_order="0",
                          points=";".join(f"{x:.1f},{y:.1f}" for x, y in pol))
    ET.indent(raiz)
    ET.ElementTree(raiz).write(caminho, encoding="utf-8", xml_declaration=True)


def desenhar_preview(img, vacas):
    sobreposicao = img.copy()
    for pol, _ in vacas:
        cv2.fillPoly(sobreposicao, [pol.astype(np.int32)], (0, 0, 255))
    saida = cv2.addWeighted(img, 0.6, sobreposicao, 0.4, 0)
    for pol, conf in vacas:
        cv2.polylines(saida, [pol.astype(np.int32)], True, (0, 0, 255), 2)
        x, y = pol.min(axis=0)
        cv2.putText(saida, f"{conf:.2f}", (int(x) + 4, int(y) + 24), 0, 0.8, (0, 0, 255), 2)
    return saida


def expandir_videos(padroes):
    # o PowerShell nao expande '*.dav', entao o proprio script expande
    videos = []
    for p in padroes:
        achados = sorted(glob.glob(p))
        videos += achados if achados else [p]
    return [Path(v) for v in videos]


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("videos", nargs="+", help="arquivos .dav (aceita curingas: *.dav)")
    p.add_argument("--saida", help="pasta do lote (padrao: lotes/lote_AAAAMMDD_HHMM)")
    p.add_argument("--intervalo", type=float, default=30,
                   help="segundos de video entre frames candidatos (padrao 30)")
    p.add_argument("--max-por-video", type=int, default=150,
                   help="maximo de frames selecionados por video (padrao 150)")
    p.add_argument("--min-vacas", type=int, default=1,
                   help="descarta frames com menos vacas que isso (padrao 1)")
    p.add_argument("--conf", type=float, default=0.15,
                   help="confianca minima da deteccao (padrao 0.15; baixa de proposito: "
                        "e mais rapido apagar um falso positivo no CVAT do que desenhar uma vaca)")
    p.add_argument("--modelo", help="modelo .pt de segmentacao (padrao: YOLOE 'cow')")
    p.add_argument("--previews", action="store_true", help="salva imagens com as mascaras desenhadas")
    args = p.parse_args()

    videos = expandir_videos(args.videos)
    faltando = [v for v in videos if not v.exists()]
    if faltando:
        sys.exit("Arquivo(s) nao encontrado(s):\n  " + "\n  ".join(map(str, faltando)))

    saida = Path(args.saida or PASTA_PROJETO / "lotes" / f"lote_{datetime.now():%Y%m%d_%H%M}")
    if saida.exists() and any(saida.iterdir()):
        sys.exit(f"A pasta de saida ja existe e nao esta vazia: {saida}")
    pasta_imagens = saida / "imagens"
    pasta_imagens.mkdir(parents=True)
    if args.previews:
        (saida / "previews").mkdir()

    modelo = carregar_modelo(args.modelo)
    registros = []

    for video in videos:
        camera, inicio = info_video(video)
        print(f"\n{video.name}  (camera {camera}, inicio {inicio or 'desconhecido'})")
        candidatos, n_lidos = [], 0
        for t, frame in ler_video(video, args.intervalo):
            n_lidos += 1
            vacas = segmentar(modelo, frame, args.conf)
            if len(vacas) < args.min_vacas:
                continue
            quando = inicio + timedelta(seconds=t) if inicio else None
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            candidatos.append({
                "t": t, "quando": quando, "vacas": vacas, "jpg": jpg,
                "hora": quando.hour if quando else int(t // 3600),
                "altura": frame.shape[0], "largura": frame.shape[1],
            })

        selecionados = selecionar(candidatos, args.max_por_video)
        for c in selecionados:
            marca = f"{c['quando']:%Y-%m-%d_%H-%M-%S}" if c["quando"] else f"t{int(c['t']):06d}"
            nome = f"{camera}_{marca}.jpg"
            c["jpg"].tofile(pasta_imagens / nome)  # tofile: aceita acento no caminho
            if args.previews:
                img = cv2.imdecode(c["jpg"], cv2.IMREAD_COLOR)
                cv2.imencode(".jpg", desenhar_preview(img, c["vacas"]))[1].tofile(saida / "previews" / nome)
            registros.append({
                "imagem": nome, "video": video.name, "camera": camera,
                "data_hora": c["quando"].isoformat(sep=" ") if c["quando"] else "",
                "t_video_s": round(c["t"], 1), "n_vacas": len(c["vacas"]),
                "vacas": c["vacas"], "altura": c["altura"], "largura": c["largura"],
            })
        horas = sorted({c["hora"] for c in selecionados})
        print(f"  {n_lidos} candidatos lidos | {len(candidatos)} com vaca | "
              f"{len(selecionados)} selecionados | horas cobertas: {horas}")

    if not registros:
        sys.exit("Nenhum frame com vaca encontrado; nada foi gerado.")

    registros.sort(key=lambda r: r["imagem"])
    escrever_xml_cvat(registros, saida / "annotations.xml")
    with zipfile.ZipFile(saida / "anotacoes_cvat.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.write(saida / "annotations.xml", "annotations.xml")
    (saida / "annotations.xml").unlink()
    with zipfile.ZipFile(saida / "imagens.zip", "w", zipfile.ZIP_STORED) as z:
        for r in registros:
            z.write(pasta_imagens / r["imagem"], r["imagem"])

    colunas = ["imagem", "video", "camera", "data_hora", "t_video_s", "n_vacas"]
    with open(saida / "frames.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        w.writeheader()
        w.writerows(registros)

    total_vacas = sum(r["n_vacas"] for r in registros)
    print(f"\nLote pronto: {saida}")
    print(f"  {len(registros)} imagens, {total_vacas} vacas pre-anotadas")
    print("  CVAT: crie a task com imagens.zip (rotulo 'vaca', tipo poligono) e depois")
    print("        Actions > Upload annotations > 'CVAT 1.1' > anotacoes_cvat.zip")


if __name__ == "__main__":
    main()
