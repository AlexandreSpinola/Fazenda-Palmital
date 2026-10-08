# Visão Computacional — GEDAI (identificação de vacas no cocho)

Pipeline: câmeras Intelbras (zenital, 90°) → vídeos do NVR → frames →
anotação no CVAT → conversão → treino no Colab → modelos.

## Fluxo de trabalho

1. **Baixar vídeos** pelo app da Intelbras para `gravações\`
2. **Extrair frames** (1 a cada 15 s; registra no log `videos_processados.csv`
   e pula vídeos já processados — depois disso o vídeo pode ser apagado):
   ```
   venv\Scripts\python extrair_frames.py "gravações\VIDEO.avi" --intervalo 15 --saida lote_cvat
   ```
3. **Anotar no CVAT** ([app.cvat.ai](https://app.cvat.ai)), projeto com rótulo
   `vaca` (retângulo) e atributos: `identidade` (select), `comendo` (checkbox),
   `posicao` (esquerda/centro/direita). Uma task por vídeo/lote.
4. **Exportar** a task no formato "CVAT for images 1.1" (sem imagens) e
   **converter** (gera dataset YOLO + recortes por identidade + recortes
   comendo + estatísticas de cobertura):
   ```
   venv\Scripts\python converter_anotacoes.py "CVAT jobs\EXPORT\annotations.xml" --imagens frames --saida dataset_vX
   ```
5. **Treinar no Colab** (GPU T4 gratuita): subir `treinar_detector_colab.ipynb`
   + o zip do `dataset_yolo`, rodar as células, baixar o `best.pt`.
6. **Testar localmente**:
   ```
   venv\Scripts\python testar_detector.py "gravações\VIDEO.avi"
   venv\Scripts\python gerar_video_demo.py "gravações\VIDEO.avi" --saida demo.mp4
   ```

## Arquivos e pastas

| Item | O que é |
|---|---|
| `extrair_frames.py` | vídeo → JPGs a cada N segundos (+ log CSV) |
| `converter_anotacoes.py` | XML do CVAT → dataset YOLO + recortes |
| `treinar_detector_colab.ipynb` | notebook de fine-tuning no Colab |
| `testar_detector.py` | roda o modelo num vídeo, ao vivo na tela |
| `gerar_video_demo.py` | gera vídeo com detecções desenhadas |
| `detector_vacas_v1.pt` | **modelo v1** (96 imagens, 13/08/2026) |
| `yolo11n.pt` | modelo base pré-treinado (ponto de partida dos treinos) |
| `demo_detector_h264.mp4` | vídeo demo (H.264, abre em qualquer player) |
| `frames\` | 874 frames do vídeo 11/ago 16h (estão no CVAT — não apagar) |
| `frames_anotacao_v2\` | 322 frames variados (madrugada/manhã/tarde) p/ anotação |
| `lote_cvat\` | frames extraídos a cada 15 s (lotes novos) |
| `dataset_v2\` | dataset convertido do 1º ciclo (96 imgs anotadas) |
| `CVAT jobs\` | exports (XML) baixados do CVAT |
| `videos_processados.csv` | log dos vídeos já transformados em frames |

## Roadmap dos modelos

1. **Detecção** (`vaca` no frame) — ✅ v1 treinada, mAP alto no vídeo diurno;
   falta robustez noturna e mais vacas → escalar anotação
2. **Identificação individual** (qual vaca, pelo padrão de manchas) — usa
   `recortes_identidade\`; requer cada vaca em esquerda/centro/direita,
   dia e noite
3. **Comportamento** (comendo ou não) — usa `recortes_comendo\`; hoje há
   só 4 exemplos "não comendo", priorizar na anotação
4. **Visitas ao cocho** — juntar rastreamento + identidade + comendo em
   eventos (vaca, início, duração) e gerar relatórios

## Referências

- RTSP das câmeras (só funciona na rede da fazenda ou via VPN):
  `rtsp://admin:SENHA@192.168.10.66:554/cam/realmonitor?channel=1&subtype=1`
- NVR: Intelbras NVD 1416, acesso remoto via nuvem (SIM Next), P2P sem RTSP
- Anotação: https://app.cvat.ai — organização GEDAI, papel Worker p/ estudantes
