"""
Conta as vacas no cocho e mede as visitas, num video .dav do NVR ou ao vivo (RTSP).

A cada frame processado (1 por --intervalo segundos):
  - detecta as vacas e as rastreia (cada vaca ganha um ID enquanto esta no quadro);
  - considera "no cocho" a vaca cuja cabeca passou da barra: o topo da caixa
    fica acima de --linha (fracao da altura da imagem; a barra esta em ~0.40
    nas cameras ch00 e ch01);
  - uma VISITA comeca quando a vaca entra no cocho e termina quando ela fica
    mais de --tolerancia segundos fora (levantou a cabeca, ficou escondida...).
    Se o rastreador trocar o ID da mesma vaca, a visita continua (mesma posicao).

As visitas sao ANONIMAS: o script sabe que "uma vaca" ficou 23 min, nao qual.
A identidade vem depois (re-ID / clusters), a partir dos recortes de --recortes.

Saida (pasta --saida):
  visitas.csv     uma linha por visita: inicio, fim, duracao, posicao no cocho
  ocupacao.csv    por minuto: vacas no cocho (media e maximo) e vacas no quadro
  deteccoes.csv   cada deteccao (horario, ID, caixa, confianca, no cocho?)
  video.mp4       (com --video) frames com caixas, IDs e a linha do cocho
  recortes/       (com --recortes N) recorte de cada vaca a cada N segundos

Uso:
    python contar_visitas.py "Gravações\\VIDEO.dav" --inicio 06:00 --fim 09:00 --video
    python contar_visitas.py "Gravações\\VIDEO.dav" --modelo ..\\Colega\\best.pt
    python contar_visitas.py "rtsp://admin:SENHA@192.168.10.66:554/cam/realmonitor?channel=1&subtype=1" --mostrar
"""
import argparse
import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

from comum import (PASTA_PROJETO, EscritorVideo, carregar_modelo, eh_rtsp,
                   info_video, ler_rtsp, ler_video, ocultar_senha)

RASTREADOR = PASTA_PROJETO / "rastreador.yaml"
VERDE, CINZA, VERMELHO, BRANCO = (0, 220, 0), (160, 160, 160), (0, 0, 255), (255, 255, 255)


class Visitas:
    """Abre, estende e fecha visitas a partir das vacas rastreadas no cocho."""

    def __init__(self, tolerancia, raio_x, min_duracao, ao_fechar):
        self.tolerancia = tolerancia    # s fora do cocho ate encerrar a visita
        self.raio_x = raio_x            # px: mesma posicao = mesma vaca com ID novo
        self.min_duracao = min_duracao  # s: visitas mais curtas sao descartadas
        self.ao_fechar = ao_fechar
        self.abertas = {}               # id de rastreio -> visita
        self.total = 0
        self.descartadas = 0

    def _unicas(self):
        return list({id(v): v for v in self.abertas.values()}.values())

    def atualizar(self, quando, vacas_no_cocho):
        """vacas_no_cocho: [(id de rastreio, x do centro), ...] deste frame."""
        atualizadas, novas = set(), []
        for tid, cx in vacas_no_cocho:
            if tid in self.abertas:
                v = self.abertas[tid]
                v["fim"], v["xs"] = quando, v["xs"] + [cx]
                atualizadas.add(id(v))
            else:
                novas.append((tid, cx))

        for tid, cx in novas:
            # ID novo no lugar de uma visita que "sumiu" neste frame:
            # e a mesma vaca (o rastreador trocou o ID) e a visita continua
            candidatas = [v for v in self._unicas() if id(v) not in atualizadas
                          and abs(np.median(v["xs"][-5:]) - cx) < self.raio_x]
            if candidatas:
                v = min(candidatas, key=lambda v: abs(np.median(v["xs"][-5:]) - cx))
            else:
                self.total += 1
                v = {"visita": self.total, "inicio": quando, "xs": [], "ids": set()}
            v["fim"], v["xs"] = quando, v["xs"] + [cx]
            v["ids"].add(tid)
            self.abertas[tid] = v
            atualizadas.add(id(v))

        self._fechar(lambda v: (quando - v["fim"]).total_seconds() > self.tolerancia)

    def fechar_todas(self):
        self._fechar(lambda v: True)

    def _fechar(self, deve_fechar):
        for v in self._unicas():
            if not deve_fechar(v):
                continue
            for tid in [t for t, w in self.abertas.items() if w is v]:
                del self.abertas[tid]
            if (v["fim"] - v["inicio"]).total_seconds() >= self.min_duracao:
                self.ao_fechar(v)
            else:
                self.descartadas += 1


class Ocupacao:
    """Agrega, por minuto, quantas vacas estao no cocho e no quadro."""

    def __init__(self, ao_fechar_minuto):
        self.ao_fechar_minuto = ao_fechar_minuto
        self.minuto, self.cocho, self.quadro = None, [], []

    def adicionar(self, quando, n_cocho, n_quadro):
        minuto = quando.replace(second=0, microsecond=0)
        if self.minuto is not None and minuto != self.minuto:
            self.fechar()
        self.minuto = minuto
        self.cocho.append(n_cocho)
        self.quadro.append(n_quadro)

    def fechar(self):
        if self.minuto is not None and self.cocho:
            self.ao_fechar_minuto(self.minuto, self.cocho, self.quadro)
        self.minuto, self.cocho, self.quadro = None, [], []


def ler_hhmm(texto):
    return datetime.strptime(texto, "%H:%M").time() if texto else None


def desenhar(frame, caixas, linha_px, cabecalho, quando, visitas):
    """Verde: vaca no cocho, com o numero da visita e o cronometro dela.
    Cinza: vaca no quadro, mas fora do cocho (so o ID de rastreio)."""
    img = frame.copy()
    cv2.line(img, (0, linha_px), (img.shape[1], linha_px), VERMELHO, 2)
    for (x1, y1, x2, y2), tid, no_cocho in caixas:
        v = visitas.abertas.get(tid) if no_cocho else None
        cor = VERDE if v else CINZA
        cv2.rectangle(img, (x1, y1), (x2, y2), cor, 3)
        if v:
            seg = int((quando - v["inicio"]).total_seconds())
            textos = [f"visita {v['visita']}", f"{seg // 60}:{seg % 60:02d}"]
        else:
            textos = [f"id {tid}"]
        y = max(y1, 44) + 8
        for texto in textos:
            (lt, at), _ = cv2.getTextSize(texto, 0, 0.9, 2)
            cv2.rectangle(img, (x1, y), (x1 + lt + 12, y + at + 14), cor, -1)
            cv2.putText(img, texto, (x1 + 6, y + at + 6), 0, 0.9, (0, 0, 0), 2)
            y += at + 18
    cv2.rectangle(img, (0, 0), (img.shape[1], 44), (0, 0, 0), -1)
    cv2.putText(img, cabecalho, (10, 31), 0, 0.9, BRANCO, 2)
    return img


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("fonte", help="arquivo .dav/.mp4 ou URL rtsp:// da camera")
    p.add_argument("--modelo", help="modelo .pt (padrao: YOLOE 'cow'; ex. ..\\Colega\\best.pt)")
    p.add_argument("--saida", help="pasta de resultados (padrao: resultados/<camera>_<data_hora>)")
    p.add_argument("--camera", help="nome da camera (padrao: tirado do nome do arquivo ou da URL)")
    p.add_argument("--intervalo", type=float, default=1.0, help="segundos entre frames processados (padrao 1)")
    p.add_argument("--inicio", help="(arquivo) processar a partir deste horario, HH:MM")
    p.add_argument("--fim", help="(arquivo) parar neste horario, HH:MM")
    p.add_argument("--linha", type=float, default=0.40,
                   help="altura da barra do cocho, em fracao da imagem (padrao 0.40)")
    p.add_argument("--margem", type=float, default=0.03,
                   help="quanto a cabeca precisa passar da barra, em fracao da imagem (padrao 0.03)")
    p.add_argument("--tolerancia", type=float, default=60,
                   help="segundos fora do cocho ate encerrar a visita (padrao 60)")
    p.add_argument("--min-visita", type=float, default=20,
                   help="visitas mais curtas que isso (s) sao descartadas (padrao 20)")
    p.add_argument("--conf", type=float, default=0.15, help="confianca minima da deteccao (padrao 0.15)")
    p.add_argument("--rastreador", default=str(RASTREADOR), help="configuracao do rastreador (.yaml)")
    p.add_argument("--gap-max", type=float, default=60,
                   help="(arquivo) buraco na gravacao maior que isso (s) encerra as visitas abertas")
    p.add_argument("--video", action="store_true", help="salva video.mp4 com as deteccoes desenhadas")
    p.add_argument("--mostrar", action="store_true", help="mostra as deteccoes numa janela (tecla q encerra)")
    p.add_argument("--recortes", type=float, default=0,
                   help="salva o recorte de cada vaca a cada N segundos (para os clusters; 0 = nao salva)")
    args = p.parse_args()

    ao_vivo = eh_rtsp(args.fonte)
    if not ao_vivo and not Path(args.fonte).exists():
        sys.exit(f"Arquivo nao encontrado: {args.fonte}")
    camera, inicio_video = info_video(args.fonte)
    camera = args.camera or camera
    if not ao_vivo and inicio_video is None:
        print("AVISO: horario de inicio nao esta no nome do arquivo; usando 00:00 de 01/01/2000")
        inicio_video = datetime(2000, 1, 1)
    h_inicio, h_fim = ler_hhmm(args.inicio), ler_hhmm(args.fim)

    rotulo = f"{camera}_{(datetime.now() if ao_vivo else inicio_video):%Y%m%d_%H%M}"
    saida = Path(args.saida or PASTA_PROJETO / "resultados" / rotulo)
    saida.mkdir(parents=True, exist_ok=True)
    print(f"Fonte: {ocultar_senha(args.fonte)}\nCamera: {camera}\nResultados: {saida}")

    # CSVs gravados linha a linha: se o notebook desligar no meio, o que ja
    # foi medido fica salvo
    arq_vis = open(saida / "visitas.csv", "w", newline="", encoding="utf-8")
    arq_ocu = open(saida / "ocupacao.csv", "w", newline="", encoding="utf-8")
    arq_det = open(saida / "deteccoes.csv", "w", newline="", encoding="utf-8")
    w_vis, w_ocu, w_det = csv.writer(arq_vis), csv.writer(arq_ocu), csv.writer(arq_det)
    w_vis.writerow(["camera", "visita", "inicio", "fim", "duracao_min", "posicao_x", "ids_rastreio"])
    w_ocu.writerow(["camera", "minuto", "frames", "no_cocho_media", "no_cocho_max", "no_quadro_media"])
    w_det.writerow(["camera", "data_hora", "id", "x1", "y1", "x2", "y2", "conf", "no_cocho"])

    duracoes = []
    largura = None

    def gravar_visita(v):
        dur = (v["fim"] - v["inicio"]).total_seconds() / 60
        duracoes.append(dur)
        w_vis.writerow([camera, v["visita"], f"{v['inicio']:%Y-%m-%d %H:%M:%S}",
                        f"{v['fim']:%Y-%m-%d %H:%M:%S}", f"{dur:.2f}",
                        f"{np.median(v['xs']) / largura:.3f}", " ".join(sorted(v["ids"]))])
        arq_vis.flush()

    picos = []

    def gravar_minuto(minuto, cocho, quadro):
        picos.append(max(cocho))
        w_ocu.writerow([camera, f"{minuto:%Y-%m-%d %H:%M}", len(cocho),
                        f"{np.mean(cocho):.2f}", max(cocho), f"{np.mean(quadro):.2f}"])
        arq_ocu.flush()

    visitas = None  # criado no 1o frame, quando se sabe a largura da imagem
    ocupacao = Ocupacao(gravar_minuto)
    modelo = carregar_modelo(args.modelo)
    escritor_video = None
    ultimo_recorte = {}

    if ao_vivo:
        frames = ler_rtsp(args.fonte, args.intervalo)
    else:
        frames = ((inicio_video + timedelta(seconds=t), f) for t, f in ler_video(args.fonte, args.intervalo))

    segmento, persistir, anterior, n_frames = 1, False, None, 0
    try:
        for quando, frame in frames:
            if h_inicio and quando.time() < h_inicio:
                continue
            if h_fim and quando.time() >= h_fim:
                break
            altura, largura = frame.shape[:2]
            if visitas is None:
                visitas = Visitas(args.tolerancia, 0.08 * largura, args.min_visita, gravar_visita)
            linha_px = int(args.linha * altura)
            limite_cabeca = (args.linha - args.margem) * altura

            # buraco na gravacao (o NVR grava por movimento): nao da para saber o
            # que aconteceu no meio, entao as visitas abertas sao encerradas e o
            # rastreador recomeca
            if anterior is not None and (quando - anterior).total_seconds() > args.gap_max:
                visitas.fechar_todas()
                segmento += 1
                persistir = False
            anterior = quando

            r = modelo.track(frame, persist=persistir, conf=args.conf, iou=0.5,
                             tracker=args.rastreador, verbose=False)[0]
            persistir = True
            n_frames += 1

            caixas, no_cocho = [], []
            if r.boxes.id is not None:
                for (x1, y1, x2, y2), tid, c in zip(r.boxes.xyxy.tolist(), r.boxes.id.int().tolist(),
                                                     r.boxes.conf.tolist()):
                    tid = f"{segmento}-{tid}"
                    dentro = y1 < limite_cabeca
                    caixa = tuple(int(v) for v in (x1, y1, x2, y2))
                    caixas.append((caixa, tid, dentro))
                    if dentro:
                        no_cocho.append((tid, (x1 + x2) / 2))
                    w_det.writerow([camera, f"{quando:%Y-%m-%d %H:%M:%S}", tid, *caixa, f"{c:.3f}", int(dentro)])

                    if args.recortes and (quando - ultimo_recorte.get(tid, datetime.min)).total_seconds() >= args.recortes:
                        ultimo_recorte[tid] = quando
                        pasta = saida / "recortes" / f"{camera}_{tid}"
                        pasta.mkdir(parents=True, exist_ok=True)
                        x1c, y1c, x2c, y2c = caixa
                        cv2.imencode(".jpg", frame[max(0, y1c):y2c, max(0, x1c):x2c])[1].tofile(
                            pasta / f"{quando:%Y%m%d_%H%M%S}.jpg")

            visitas.atualizar(quando, no_cocho)
            ocupacao.adicionar(quando, len(no_cocho), len(caixas))

            if args.video or args.mostrar:
                cabecalho = (f"{camera}  {quando:%d/%m %H:%M:%S}   no cocho: {len(no_cocho)}"
                             f"   no quadro: {len(caixas)}   visitas: {visitas.total}")
                img = desenhar(frame, caixas, linha_px, cabecalho, quando, visitas)
                if args.video:
                    # metade da resolucao, em H.264: o arquivo fica pequeno
                    tamanho = (largura // 2, altura // 2)
                    if escritor_video is None:
                        escritor_video = EscritorVideo(saida / "video.mp4", *tamanho)
                    escritor_video.escrever(cv2.resize(img, tamanho))
                if args.mostrar:
                    cv2.imshow(f"Vacas no cocho - {camera}", cv2.resize(img, (1280, 720)))
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
            if ao_vivo and n_frames % 60 == 0:
                print(f"  {quando:%H:%M:%S}  no cocho: {len(no_cocho)}  visitas ate agora: {visitas.total}")
    except KeyboardInterrupt:
        print("\nInterrompido (Ctrl+C); salvando o que foi medido...")
    finally:
        if visitas is not None:
            visitas.fechar_todas()
        ocupacao.fechar()
        for arq in (arq_vis, arq_ocu, arq_det):
            arq.close()
        if escritor_video is not None:
            escritor_video.fechar()
        if args.mostrar:
            cv2.destroyAllWindows()

    print(f"\nFrames processados: {n_frames}")
    if duracoes:
        print(f"Visitas: {len(duracoes)} (descartadas por durar < {args.min_visita:.0f} s: "
              f"{visitas.descartadas})")
        print(f"  duracao mediana: {np.median(duracoes):.1f} min | media: {np.mean(duracoes):.1f} min"
              f" | maior: {max(duracoes):.1f} min")
    else:
        print("Nenhuma visita registrada.")
    if picos:
        print(f"Pico de ocupacao: {max(picos)} vacas no cocho ao mesmo tempo")
    print(f"Resultados em: {saida}")


if __name__ == "__main__":
    main()
