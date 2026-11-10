# Vacas no Cocho — GEDAI (Fazenda Palmital)

Visão computacional para medir **quantas vezes cada vaca vai ao cocho, quanto
tempo fica** e a **taxa de ocupação do cocho**, a partir das câmeras
Intelbras zenitais.

> O **porquê** de cada escolha (fatos levantados, decisões, fases, perguntas
> em aberto) está em [CONTEXT.md](CONTEXT.md). Este README é o **como usar**.

```
câmeras (1 fps) → NVR (.dav) → HD externo → lote pré-anotado (YOLOE) → CVAT (correção humana)
   → treino do segmentador (RTX 5070) → rastreamento → re-ID por clusters → visitas por vaca
   → [futuro] o mesmo pipeline ao vivo na fazenda via RTSP
```

## Estrutura

| Item | O que é |
|---|---|
| `contar_visitas.py` | vídeo `.dav` ou câmera ao vivo (RTSP) → visitas ao cocho e ocupação por minuto |
| `gerar_lote_cvat.py` | `.dav` → lote de frames com vaca + pré-anotações para o CVAT |
| `enviar_lote_cvat.py` | envia um lote para o CVAT local (projeto, task, pré-anotações, jobs) |
| `comum.py` | leitura de vídeo/RTSP e carregamento de modelo, usados pelos scripts |
| `rastreador.yaml` | configuração do rastreador (ByteTrack ajustado para 1 fps) |
| `requirements.txt` | dependências (o PyTorch com CUDA é instalado à parte, veja abaixo) |
| `CONTEXT.md` | contexto, decisões de arquitetura e roadmap |
| `modelos/` | pesos dos modelos (`yoloe-vaca.pt` é criado automaticamente) |
| `Gravações/` | vídeos `.dav` trazidos da fazenda (fora do git) |
| `lotes/` | lotes gerados para anotação (fora do git) |
| `legado/` | scripts do fluxo antigo (detecção por caixa, treino no Colab), mantidos só como referência |
| `apresentacao_projeto.html` | apresentação da versão anterior do projeto |

> ⚠️ **Esta pasta está dentro do OneDrive.** Vídeos têm ~5 GB por câmera por
> dia, e os lotes, centenas de MB. Mantenha os dados pesados **fora do
> OneDrive** (HD externo ou `C:\dados_fazenda`) e aponte os scripts para lá.

## 1. Ambiente (uma vez)

O venv fica em `..\venv` (pasta `Fazenda\venv`). Python 3.14.

```powershell
# o PyTorch precisa do Visual C++ Redistributable
winget install Microsoft.VCRedist.2015+.x64

# PyTorch com CUDA 13.0 (a RTX 5070 exige CUDA >= 12.8)
..\venv\Scripts\python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
..\venv\Scripts\python -m pip install -r requirements.txt

# conferir: deve imprimir True e o nome da placa
..\venv\Scripts\python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## 2. Trazer os vídeos da fazenda

Exportar do NVR (porta USB do NVD 1416 ou pela rede local da fazenda) para o
HD externo. Os arquivos saem como
`192.168.10.66-Ch.<canal>-VIP Intelbras-<AAAA-MM-DD-hh-mm-ss>.dav`. **Não
renomeie**: o script tira do nome a câmera e o horário de início.

Para o dataset, priorize **variedade**: dias diferentes, todas as câmeras,
madrugada/dia/noite, cocho cheio e vazio, chuva.

## 3. Gerar um lote pré-anotado

```powershell
..\venv\Scripts\python gerar_lote_cvat.py "Gravações\*.dav" --saida lotes\lote_002 --previews
```

O que o script faz com cada vídeo:
1. pega 1 frame a cada 30 s de vídeo;
2. segmenta as vacas e descarta os frames vazios;
3. escolhe até 150 frames espalhados pelas horas do dia.

Leva ~1min45s por câmera-dia na RTX 5070. Na 1ª execução, baixa o modelo
(~700 MB) uma única vez.

| Opção | Padrão | Para quê |
|---|---|---|
| `--intervalo` | 30 | segundos de vídeo entre frames candidatos |
| `--max-por-video` | 150 | frames selecionados por vídeo |
| `--min-vacas` | 1 | descarta frames com menos vacas que isso |
| `--conf` | 0.15 | confiança mínima. É baixa de propósito: apagar um falso positivo é mais rápido que desenhar uma vaca |
| `--modelo` | YOLOE "cow" | depois do 1º treino, passe o seu `best.pt` aqui |
| `--previews` | — | salva as imagens com os polígonos desenhados, para conferência rápida |

Saída:

```
lotes/lote_002/
  imagens/              frames selecionados (ch00_2026-10-01_14-00-52.jpg ...)
  imagens.zip           para criar a task no CVAT
  anotacoes_cvat.zip    pré-anotações (formato CVAT for images 1.1)
  frames.csv            índice: imagem, vídeo, câmera, data/hora, nº de vacas
  previews/             (com --previews)
```

**`lotes/lote_001`** já foi gerado com os vídeos de 01/10/2026 (canais 0 e 1):
300 imagens e 547 vacas pré-anotadas.

## 4. Corrigir no CVAT

1. **Projeto** (uma vez): um único rótulo `vaca`, tipo **Polygon**, sem atributos.
   A identidade da vaca **não** é anotada no CVAT; ela vem dos clusters (fase 3).
2. **Task**: *Create task* → projeto acima → enviar o `imagens.zip`.
3. **Pré-anotações**: na task, *Actions → Upload annotations* → formato
   **CVAT 1.1** → `anotacoes_cvat.zip`.
4. **Corrigir** frame a frame (regras abaixo) e marcar o job como concluído.
5. **Exportar**: *Export task dataset* → formato **Ultralytics YOLO Segmentation**.

**Regras de anotação** (para os estudantes):
- Anotar **toda vaca visível**, inclusive as cortadas na borda e as que só
  mostram a cabeça.
- O polígono cobre **cabeça + corpo**, passando por cima da barra do cocho.
- Vaca atrás de outra: anotar **só a parte visível**, sem invadir a vizinha.
- Corrigir os erros típicos do pré-anotador:
  - **vaca preta não detectada**: desenhar;
  - **um polígono cobrindo duas vacas**: separar;
  - **sombra ou pedaço de cocho marcado como vaca**: apagar.
- Na dúvida se é uma vaca ou duas, olhar o frame anterior e o seguinte.

## 5. Contar visitas e ocupação do cocho

```powershell
# vídeo gravado (dá para limitar o horário)
..\venv\Scripts\python contar_visitas.py "Gravações\VIDEO.dav" --inicio 05:00 --fim 07:00 --video

# câmera ao vivo (só na rede da fazenda); q fecha a janela, Ctrl+C encerra salvando
..\venv\Scripts\python contar_visitas.py "rtsp://admin:SENHA@192.168.10.66:554/cam/realmonitor?channel=1&subtype=1" --mostrar

# mesmo vídeo com o modelo da colega, para comparar
..\venv\Scripts\python contar_visitas.py "Gravações\VIDEO.dav" --modelo ..\Colega\best.pt
```

Como funciona:
1. Detecta e **rastreia** as vacas, 1 frame por segundo.
2. Considera **"no cocho"** a vaca cuja cabeça passou da barra: o topo da caixa
   fica acima de `--linha` (0,40 da altura da imagem nas câmeras ch00 e ch01).
3. Uma **visita** termina quando a vaca fica mais de `--tolerancia` segundos
   (padrão 60) fora do cocho.

As visitas são **anônimas**; a identidade vem com o re-ID (fase 3).

Saída em `resultados/<camera>_<data>/`:
- `visitas.csv`: uma visita por linha;
- `ocupacao.csv`: vacas por minuto;
- `deteccoes.csv`: tudo, para reprocessar;
- `video.mp4` (com `--video`);
- `recortes/` (com `--recortes 30`): recorte de cada vaca a cada 30 s, matéria-prima dos clusters.

**Confiabilidade** (teste em 01/10, ch01, 5h30–6h30):
- a **ocupação é robusta**: o tempo total de cocho variou só 2–8% entre modelos e configurações;
- **onde uma visita começa e termina ainda é incerto**: há fragmentação quando o
  rastreador perde a vaca, e o `--tolerancia` é uma decisão zootécnica
  (critério de intervalo entre refeições). Falta validar contra uma contagem
  manual.

Velocidade: ~2 min por hora de vídeo na RTX 5070.

## 6. Próximas etapas (ainda não implementadas)

- **Treino do segmentador** (YOLO-seg na RTX 5070) com o export do CVAT, e depois
  usar o `best.pt` em `--modelo` para pré-anotar os lotes seguintes.
- **Re-ID** (embeddings + clusters + galeria) a partir dos `recortes/`, usando
  as 89 fotos nomeadas (31 vacas × esquerda/centro/direita) como galeria
  inicial. Ver as fases em [CONTEXT.md](CONTEXT.md).

## Referências

- RTSP das câmeras (só funciona na rede da fazenda ou via VPN):
  `rtsp://admin:SENHA@192.168.10.66:554/cam/realmonitor?channel=1&subtype=1`
- NVR: Intelbras NVD 1416 (16 canais). Acesso remoto atual pelo SIM Next
  (nuvem P2P, sem RTSP e lento para baixar vídeo).
- CVAT na nuvem (provisório): https://app.cvat.ai, organização GEDAI, com papel
  *Worker* para os estudantes.
