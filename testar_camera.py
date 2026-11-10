"""
Testa a conexao com as cameras (RTSP) e salva uma foto de cada uma, com
linhas de referencia para conferir a altura da barra do cocho (o --linha
do contar_visitas.py; a barra estava em 0.40 nas cameras ch00 e ch01).

Uso:
    python testar_camera.py "rtsp://admin:SENHA@192.168.10.66:554/cam/realmonitor?channel=1&subtype=1" [outra URL ...]
"""
import sys
from datetime import datetime

import av
import av.error
import cv2

from comum import PASTA_PROJETO, info_video, ocultar_senha

CORES = {0.30: (255, 0, 0), 0.35: (0, 255, 0), 0.40: (0, 0, 255), 0.45: (0, 255, 255), 0.50: (255, 0, 255)}


def testar(url, pasta):
    camera, _ = info_video(url)
    try:
        with av.open(url, options={"rtsp_transport": "tcp", "timeout": "10000000"}) as c:
            stream = c.streams.video[0]
            frame = next(c.decode(stream)).to_ndarray(format="bgr24")
            fps = float(stream.average_rate or 0)
    except (av.error.FFmpegError, OSError, StopIteration) as e:
        print(f"[FALHOU] {camera}: {ocultar_senha(e)}")
        return False
    altura, largura = frame.shape[:2]
    for frac, cor in CORES.items():
        y = int(frac * altura)
        cv2.line(frame, (0, y), (largura, y), cor, 2)
        cv2.putText(frame, f"{frac:.2f}", (8, y - 6), 0, 0.8, cor, 2)
    arquivo = pasta / f"teste_{camera}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    cv2.imencode(".jpg", frame)[1].tofile(arquivo)
    print(f"[OK] {camera}: {largura}x{altura}, {fps:.0f} fps -> {arquivo}")
    return True


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pasta = PASTA_PROJETO / "resultados"
    pasta.mkdir(exist_ok=True)
    resultados = [testar(url, pasta) for url in sys.argv[1:]]
    sys.exit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
