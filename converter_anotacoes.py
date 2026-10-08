"""
Converte anotacoes exportadas do CVAT (formato "CVAT for images 1.1")
para os datasets dos tres modelos:

  1. dataset_yolo/   -> deteccao (formato YOLO: images/ + labels/ + data.yaml)
  2. recortes_identidade/<vaca>/  -> re-identificacao (crops por identidade)
  3. recortes_comendo/{comendo,nao_comendo}/ -> classificador de comportamento

Tambem imprime estatisticas de cobertura (por identidade, posicao, comendo).

Uso:
    python converter_anotacoes.py "CVAT jobs\\job_4360042\\annotations.xml" --imagens frames
"""
import argparse
import math
import os
import shutil
import xml.etree.ElementTree as ET
from collections import Counter

import cv2
import numpy as np


def ler_imagem(caminho):
    # imread/imwrite falham em caminhos com acento no Windows
    return cv2.imdecode(np.fromfile(caminho, dtype=np.uint8), cv2.IMREAD_COLOR)


def salvar_imagem(caminho, img):
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if ok:
        buf.tofile(caminho)
    return ok


def caixa_alinhada(xtl, ytl, xbr, ybr, rotacao_graus, w_img, h_img):
    """Converte caixa (possivelmente rotacionada em torno do centro) na
    menor caixa alinhada aos eixos que a contem, limitada a imagem."""
    cx, cy = (xtl + xbr) / 2, (ytl + ybr) / 2
    ang = math.radians(rotacao_graus)
    cos_a, sin_a = math.cos(ang), math.sin(ang)
    xs, ys = [], []
    for x, y in [(xtl, ytl), (xbr, ytl), (xbr, ybr), (xtl, ybr)]:
        dx, dy = x - cx, y - cy
        xs.append(cx + dx * cos_a - dy * sin_a)
        ys.append(cy + dx * sin_a + dy * cos_a)
    x1 = max(0, min(xs)); y1 = max(0, min(ys))
    x2 = min(w_img, max(xs)); y2 = min(h_img, max(ys))
    return x1, y1, x2, y2


def main():
    p = argparse.ArgumentParser()
    p.add_argument("xml", help="caminho do annotations.xml exportado do CVAT")
    p.add_argument("--imagens", default="frames",
                   help="pasta onde estao os JPGs originais (padrao: frames)")
    p.add_argument("--saida", default="dataset",
                   help="pasta raiz de saida (padrao: dataset)")
    p.add_argument("--val", type=int, default=6,
                   help="1 a cada N blocos de frames vai para validacao (padrao: 6)")
    args = p.parse_args()

    raiz = args.saida
    dir_yolo_img = {s: os.path.join(raiz, "dataset_yolo", s, "images") for s in ("train", "val")}
    dir_yolo_lbl = {s: os.path.join(raiz, "dataset_yolo", s, "labels") for s in ("train", "val")}
    for d in list(dir_yolo_img.values()) + list(dir_yolo_lbl.values()):
        os.makedirs(d, exist_ok=True)

    arvore = ET.parse(args.xml)
    imagens = [el for el in arvore.getroot().iter("image")]
    # so nos importam imagens que foram de fato anotadas (com caixa) ou
    # explicitamente vazias dentro do trecho anotado
    imagens_com_caixa = [el for el in imagens if el.findall("box")]
    print(f"Imagens no XML: {len(imagens)} | com anotacao: {len(imagens_com_caixa)}")

    stats_id = Counter(); stats_pos = Counter(); stats_com = Counter()
    faltando = 0
    BLOCO = 10  # frames consecutivos ficam no mesmo conjunto (evita vazamento)

    for i, el in enumerate(imagens_com_caixa):
        nome = el.get("name")
        w_img, h_img = float(el.get("width")), float(el.get("height"))
        origem = os.path.join(args.imagens, nome)
        if not os.path.exists(origem):
            faltando += 1
            continue
        conjunto = "val" if (i // BLOCO) % args.val == 0 else "train"

        img = None  # carregada so se houver recorte a salvar
        linhas_yolo = []
        for box in el.findall("box"):
            x1, y1, x2, y2 = caixa_alinhada(
                float(box.get("xtl")), float(box.get("ytl")),
                float(box.get("xbr")), float(box.get("ybr")),
                float(box.get("rotation", 0)), w_img, h_img)
            if x2 - x1 < 5 or y2 - y1 < 5:
                continue

            # linha YOLO: classe cx cy w h (normalizados)
            cx = (x1 + x2) / 2 / w_img; cy = (y1 + y2) / 2 / h_img
            bw = (x2 - x1) / w_img; bh = (y2 - y1) / h_img
            linhas_yolo.append(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

            atrib = {a.get("name"): a.text for a in box.findall("attribute")}
            ident = atrib.get("identidade", "desconhecida") or "desconhecida"
            comendo = (atrib.get("comendo", "false") == "true")
            stats_id[ident] += 1
            stats_pos[atrib.get("posicao", "?")] += 1
            stats_com["comendo" if comendo else "nao_comendo"] += 1

            if img is None:
                img = ler_imagem(origem)
            if img is None:
                continue
            recorte = img[int(y1):int(y2), int(x1):int(x2)]
            base = os.path.splitext(nome)[0]
            sufixo = f"{base}_{int(x1)}x{int(y1)}.jpg"
            if ident != "desconhecida":
                d = os.path.join(raiz, "recortes_identidade", ident)
                os.makedirs(d, exist_ok=True)
                salvar_imagem(os.path.join(d, sufixo), recorte)
            d = os.path.join(raiz, "recortes_comendo",
                             "comendo" if comendo else "nao_comendo")
            os.makedirs(d, exist_ok=True)
            salvar_imagem(os.path.join(d, sufixo), recorte)

        shutil.copy2(origem, os.path.join(dir_yolo_img[conjunto], nome))
        with open(os.path.join(dir_yolo_lbl[conjunto],
                               os.path.splitext(nome)[0] + ".txt"),
                  "w", encoding="utf-8") as f:
            f.write("\n".join(linhas_yolo))

    # data.yaml para o Ultralytics (caminhos relativos a raiz do dataset_yolo)
    with open(os.path.join(raiz, "dataset_yolo", "data.yaml"), "w",
              encoding="utf-8") as f:
        # caminho absoluto do Colab (/content), onde o treino acontece
        f.write("path: /content/dataset_yolo\ntrain: train/images\n"
                "val: val/images\nnames:\n  0: vaca\n")

    n_train = len(os.listdir(dir_yolo_img["train"]))
    n_val = len(os.listdir(dir_yolo_img["val"]))
    print(f"\nDataset YOLO: {n_train} train / {n_val} val -> {raiz}\\dataset_yolo")
    if faltando:
        print(f"AVISO: {faltando} imagens do XML nao encontradas em '{args.imagens}'")
    print("\n--- Cobertura ---")
    print("Por identidade:", dict(stats_id))
    print("Por posicao:   ", dict(stats_pos))
    print("Comendo:       ", dict(stats_com))


if __name__ == "__main__":
    main()
