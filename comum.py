"""
Funcoes compartilhadas pelos scripts: leitura de video (.dav do NVR e RTSP
ao vivo), horario/camera a partir do nome do arquivo e carregamento do modelo.
"""
import os
import re
import time
from datetime import datetime
from pathlib import Path

import av
import av.error
import av.logging
from tqdm import tqdm

# o HEVC do NVR gera milhares de avisos ('CABAC_MAX_BIN', 'Two slices...')
# que nao afetam a imagem; o PyAV deixa silenciar o ffmpeg de verdade
av.logging.set_level(av.logging.PANIC)

PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_MODELOS = PASTA_PROJETO / "modelos"
MODELO_PADRAO = PASTA_MODELOS / "yoloe-vaca.pt"

RE_CANAL = re.compile(r"Ch\.(\d+)", re.IGNORECASE)
RE_INICIO = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})")
RE_CANAL_RTSP = re.compile(r"channel=(\d+)", re.IGNORECASE)


# ---------------------------------------------------------------- modelo

def preparar_modelo_padrao():
    """Cria modelos/yoloe-vaca.pt: YOLOE com o vocabulario 'cow' embutido,
    para nao precisar carregar o codificador de texto (~600 MB) toda vez."""
    from ultralytics import YOLOE

    print("Preparando o modelo padrao (download unico, ~700 MB)...")
    PASTA_MODELOS.mkdir(exist_ok=True)
    cwd = os.getcwd()
    os.chdir(PASTA_MODELOS)  # os downloads do ultralytics caem na pasta atual
    try:
        m = YOLOE("yoloe-11l-seg.pt")
        m.set_classes(["cow"], m.get_text_pe(["cow"]))
        m.save(MODELO_PADRAO.name)
    finally:
        os.chdir(cwd)
    for f in ("yoloe-11l-seg.pt", "mobileclip_blt.ts"):
        (PASTA_MODELOS / f).unlink(missing_ok=True)


def carregar_modelo(caminho=None):
    """Sem caminho: YOLOE 'cow' (zero-shot). Com caminho: qualquer .pt do
    Ultralytics (deteccao ou segmentacao), ex. o modelo treinado no CVAT."""
    from ultralytics import YOLO, YOLOE

    if caminho is None:
        if not MODELO_PADRAO.exists():
            preparar_modelo_padrao()
        caminho = MODELO_PADRAO
    caminho = Path(caminho)
    return YOLOE(str(caminho)) if "yoloe" in caminho.stem else YOLO(str(caminho))


# ---------------------------------------------------------------- video

def eh_rtsp(fonte):
    return str(fonte).lower().startswith("rtsp://")


def ocultar_senha(url):
    return re.sub(r"//[^@/]+@", "//***@", str(url))


def info_video(fonte):
    """Camera e horario de inicio a partir do nome que o NVR da ao arquivo:
    '192.168.10.66-Ch.0-VIP Intelbras-2026-10-01-00-00-53.dav'.
    Para RTSP, a camera vem do 'channel=N' da URL e o inicio e None."""
    if eh_rtsp(fonte):
        m = RE_CANAL_RTSP.search(str(fonte))
        # no NVR Intelbras o channel=1 da URL e o 'Ch.0' do arquivo
        return (f"ch{int(m.group(1)) - 1:02d}" if m else "rtsp"), None
    nome = Path(fonte).stem
    m = RE_CANAL.search(nome)
    camera = f"ch{int(m.group(1)):02d}" if m else re.sub(r"\W+", "_", nome)[:30]
    m = RE_INICIO.search(nome)
    inicio = datetime.strptime(m.group(1), "%Y-%m-%d-%H-%M-%S") if m else None
    return camera, inicio


def ler_video(caminho, intervalo, barra_desc="  video"):
    """Gera (segundos desde o inicio do video, frame BGR) a cada `intervalo`
    segundos de video. O NVR grava por MOVIMENTO: o tempo vem do timestamp
    (pts) de cada frame, nunca da contagem de frames, e pode dar saltos."""
    with av.open(str(caminho)) as conteiner:
        stream = conteiner.streams.video[0]
        stream.thread_type = "AUTO"
        duracao = conteiner.duration / av.time_base if conteiner.duration else 0
        barra = tqdm(total=round(duracao), unit="s", desc=barra_desc, leave=False)
        t_inicial, proximo = None, 0.0
        try:
            for frame in conteiner.decode(stream):
                if frame.time is None:
                    continue
                if t_inicial is None:
                    t_inicial = frame.time
                t = frame.time - t_inicial
                if t < proximo:
                    continue
                barra.update(max(0, min(round(t), barra.total) - barra.n))
                yield t, frame.to_ndarray(format="bgr24")
                proximo = t + intervalo
        finally:
            barra.close()


class EscritorVideo:
    """Grava MP4 em H.264 (abre em qualquer player, ao contrario do 'mp4v'
    do OpenCV) e bem menor."""

    def __init__(self, caminho, largura, altura, fps=8):
        self.conteiner = av.open(str(caminho), "w")
        self.stream = self.conteiner.add_stream("libx264", rate=fps)
        self.stream.width, self.stream.height = largura - largura % 2, altura - altura % 2
        self.stream.pix_fmt = "yuv420p"
        self.stream.options = {"crf": "26", "preset": "veryfast"}

    def escrever(self, img_bgr):
        img = img_bgr[:self.stream.height, :self.stream.width]
        for pacote in self.stream.encode(av.VideoFrame.from_ndarray(img, format="bgr24")):
            self.conteiner.mux(pacote)

    def fechar(self):
        for pacote in self.stream.encode():
            self.conteiner.mux(pacote)
        self.conteiner.close()


def ler_rtsp(url, intervalo, espera_reconexao=10):
    """Gera (horario atual, frame BGR) da camera ao vivo a cada `intervalo`
    segundos. Se a conexao cair, tenta de novo indefinidamente."""
    proximo = 0.0
    while True:
        try:
            with av.open(url, options={"rtsp_transport": "tcp", "timeout": "10000000"}) as c:
                stream = c.streams.video[0]
                stream.thread_type = "AUTO"
                print(f"  conectado: {ocultar_senha(url)}")
                for frame in c.decode(stream):
                    agora = time.monotonic()
                    if agora < proximo:
                        continue  # decodifica tudo (precisa), mas so processa 1 a cada `intervalo`
                    proximo = agora + intervalo
                    yield datetime.now(), frame.to_ndarray(format="bgr24")
        except (av.error.FFmpegError, OSError) as e:
            # a mensagem do ffmpeg repete a URL, com a senha
            print(f"  conexao com a camera falhou ({ocultar_senha(e)}); nova tentativa em {espera_reconexao} s")
            time.sleep(espera_reconexao)
