# Contexto do projeto — Vacas no Cocho (GEDAI / Fazenda Palmital)

Documento de contexto: **o problema, os fatos levantados, as decisões de
arquitetura e o porquê de cada uma**. O passo a passo de uso está no
[README.md](README.md). Atualize este arquivo quando uma decisão mudar.

_Última revisão: 10/11/2026._

---

## 1. Objetivo

Medir, por vaca, **quantas vezes ela vai ao cocho e quanto tempo fica**, e a
**taxa de ocupação do cocho** ao longo do dia. Depois, correlacionar esses
dados com produção de leite, mastite etc.

## 2. Fatos levantados

### Fazenda e rebanho
- **~52 vacas** holandesas (preto e branco). Vistas de cima, o padrão de
  manchas do dorso é único, como uma impressão digital.
- As vacas **têm RFID**, mas ele só é lido na porteira e no **robô de
  ordenha**. Não há sensor no cocho.
- O robô de ordenha identifica a vaca a cada ordenha e registra a produção
  por vaca. É a fonte dos dados de leite para a correlação.

### Câmeras e gravação
- Câmeras Intelbras **zenitais** (de cima, apontadas para o cocho).
  **2 instaladas** (canais 0 e 1) e **14 compradas**, ainda por instalar,
  somando **16** e cobrindo o cocho inteiro.
- NVR **Intelbras NVD 1416**, que tem 16 canais: com as 16 câmeras ele fica
  lotado.
- Vídeos exportados em **`.dav`** (formato Dahua): **H.265, 1280x720, 1 fps**,
  ~**5,3 GB por câmera por dia**.
- **O NVR grava por movimento.** O arquivo "de 24h" tem só ~50 mil frames, e
  não 86.400, com centenas de buracos nos períodos parados. Consequências:
  - o horário de um frame **tem que vir do timestamp (pts)**, nunca de
    `nº do frame ÷ fps`;
  - o contador de tempo do ffmpeg (`time=`) engana. Ele parece "parar" em
    ~13h40, mas o arquivo é lido inteiro.
  - O pts do `.dav` é o horário Unix do relógio do NVR.
    O nome do arquivo traz o início em hora local:
    `192.168.10.66-Ch.0-VIP Intelbras-2026-10-01-00-00-53.dav`.
- O decodificador HEVC emite milhares de avisos (`CABAC_MAX_BIN`,
  `Two slices reporting...`) que **não afetam a imagem**. O OpenCV não deixa
  silenciá-los no Windows; o **PyAV** deixa, e por isso é ele que lê os vídeos.
- O relógio impresso na imagem bate com nome do arquivo + pts (diferença de 1–2 s).
- À noite o galpão é iluminado e a imagem continua colorida.

### Infraestrutura
- **Laboratório** (esta máquina): fica em outra rede, fora da fazenda.
  Windows 11, **RTX 5070 com 12 GB**.
- Acesso remoto atual: app **SIM Next** (nuvem/P2P da Intelbras). Baixar
  vídeo por ele é **muito lento**.
- **PC da fazenda:** configuração **ainda desconhecida**. Só importa na
  implantação (fase 5).
- Resultado ruim que motivou o recomeço: o YOLO pré-treinado no COCO detecta
  mal (chama vaca de "urso" e perde muitas). Ele aprendeu vacas vistas de lado.
  De cima ele não as reconhece, e isso se resolve com fine-tuning.

## 3. Decisões de arquitetura

| # | Decisão | Por quê |
|---|---|---|
| D1 | **HD externo** para trazer os vídeos do dataset inicial | A nuvem da Intelbras é lenta demais. O dataset precisa de dias *variados* (luz, clima, lotação), não de meses. |
| D2 | No longo prazo, **processar na fazenda** e trazer só os resultados (CSV/SQLite) | Trazer vídeo de 16 câmeras é inviável (~85 GB/dia). Os eventos ocupam poucos KB. |
| D3 | **Segmentação de instância** (polígono/máscara), não só caixa | As vacas ficam na diagonal e se sobrepõem, e a caixa de uma pega a vizinha. A máscara dá recorte limpo para a identificação e permite saber se a cabeça passou da barra. Com pré-anotação, custa o mesmo trabalho que caixa. |
| D4 | **Pré-anotação com YOLOE** (prompt de texto "cow"), com correção humana no CVAT | Testado em 12 frames contra Grounding DINO + SAM 2. O YOLOE achou quase todas as vacas, inclusive pretas e cortadas na borda; o Grounding DINO perdeu muitas, principalmente as pretas. Roda a ~27 ms/frame na 5070. |
| D5 | **Anotação em ciclos** (pré-anota → corrige → treina → pré-anota com o modelo novo) | A cada ciclo há menos para corrigir. Esperado: 2–3 ciclos de ~300 frames. |
| D6 | **Identidade por re-ID com clusters**, não por anotação manual frame a frame | O rastreador agrupa sozinho os frames da mesma vaca em trilhas. Embeddings e clusters agrupam as trilhas. **O humano só confirma ou nomeia clusters.** A confiabilidade vem dessa confirmação humana. |
| D7 | **Galeria + similaridade** (open-set), não classificador fixo de 52 classes | Vaca entra e sai do rebanho: basta cadastrar, sem retreinar. Vaca sem correspondência vira "desconhecida" para revisão. |
| D8 | "Está no cocho / comendo" = **regra geométrica** (máscara cruza a linha da barra), não um modelo | Elimina um modelo inteiro e um tipo de anotação. Se não bastar, revisitar. |
| D9 | **CVAT instalado nesta máquina** (Docker), com estudantes de zootecnia via **Tailscale** | Sem limites do plano gratuito, dados ficam no laboratório, e não precisa abrir porta no roteador. Até instalar, dá para usar o app.cvat.ai. |
| D10 | **Treino local na RTX 5070** (o notebook do Colab foi aposentado) | A GPU local é mais rápida e não tem limite de sessão. |
| D11 | Implantação: **RTSP a 1 fps** → segmentação → rastreamento → re-ID → eventos, com o modelo exportado para **ONNX/OpenVINO** | A 1 fps por câmera, a inferência é leve e provavelmente cabe em CPU. Validar antes **offline** com vídeos gravados. |
| D12 | Com 16 câmeras: **zonas sem sobreposição** por câmera, e identidade global pelo re-ID | Evita contar a mesma vaca duas vezes e permite seguir a vaca de uma câmera para a outra. |

### Como os rótulos de identidade vão ganhar nome

Para nomear um cluster ("essa é a vaca 1234"), alguém precisa de uma
referência que ligue a aparência ao número. Opções, da melhor para a pior:

1. **Câmera zenital sobre o leitor RFID da porteira automática** ✅ *viável,
   confirmado em 20/10/2026*. A porteira lê o RFID e abre para uma vaca de
   cada vez. Cruzando *vaca + horário da leitura* com o vídeo, cada vaca ganha
   fotos do dorso rotuladas automaticamente, todo dia. Assim se gera e
   atualiza a galeria do re-ID sem trabalho manual. Pendências:
   - definir se usa uma das 14 câmeras novas ou uma 17ª, já que o NVR tem
     16 canais;
   - descobrir como exportar o log de leituras RFID (vaca, horário);
   - manter o relógio do NVR e o do sistema da porteira sincronizados.
2. **Fotografar o dorso de cada vaca** na saída da ordenha, anotando o brinco
   ou RFID (uma "carteirinha" por vaca).
3. Brinco visível na imagem do cocho. Aparece às vezes, mas não é confiável.

## 4. Fases

| Fase | Entrega | Precisa de identidade? | Status |
|---|---|---|---|
| 0 | Ambiente + gerador de lotes pré-anotados + CVAT local + acesso remoto | — | ✅ feito |
| 1 | Segmentador de vacas treinado (fine-tuning) + **ocupação do cocho** | não | 🔄 ocupação já funciona com o YOLOE; falta anotar o lote 001 e treinar |
| 2 | Rastreamento + regra "no cocho" → **visitas anônimas** (início, fim, duração) | não | 🔄 v0 em `contar_visitas.py`; falta validar contra contagem manual |
| 3 | Embeddings + clusters + galeria → **visitas por vaca** | sim | ⏳ |
| 4 | Validação offline contra anotação humana (~2h de visitas reais) | sim | ⏳ |
| 5 | **Implantação ao vivo na fazenda** (RTSP, PC da fazenda, envio diário de resumo) | sim | ⏳ |
| 6 | Correlação com produção de leite, mastite etc. | sim | ⏳ |

## 5. Achados (novembro/2026)

- **Modelo da colega** (`../Colega/best.pt`): YOLO11n de **detecção**, 1 classe,
  ~100 vacas anotadas de poucos minutos de 27/07. O mAP de 0,99 do treino é
  inflado, porque a validação usou frames quase iguais aos do treino. Em 01/10
  (dia que ele nunca viu) ele detecta bem, mas **duplica caixas** de vacas
  parciais. No `contar_visitas.py`, o tempo total de cocho ficou igual ao do
  YOLOE (279 vs 273 min-vaca), mas com mais visitas fragmentadas (38 vs 29).
- **Catálogo de identidade:** os zips `Frames-*.zip` e `Vacas-*.zip` (na pasta
  `Fazenda`) têm **31 vacas com nome × 3 posições** (esquerda/centro/direita),
  com frame inteiro e recorte, de set–out/2026. É a **galeria inicial do re-ID**.
  Falta ligar nome ↔ brinco/RFID.
- **Rastreamento a 1 fps:** com o ByteTrack padrão, um ID durava em média 38 s.
  O ajuste em `rastreador.yaml` levou a 198 s. A **ocupação** (minutos-vaca no
  cocho) é estável entre configurações; a **segmentação das visitas** ainda
  fragmenta. Validar com contagem manual.
- **Definição de visita é zootécnica:** quanto tempo fora do cocho separa duas
  refeições (`--tolerancia`)? Combinar com o orientador.
- **Windows Smart App Control** bloqueou DLLs do pandas nesta máquina. Pode
  bloquear bibliotecas no notebook ou no PC da fazenda; os scripts evitam o pandas.

## 6. Perguntas em aberto

- Configuração do **PC da fazenda** (CPU, RAM, GPU?) e **velocidade de upload**
  da internet de lá. Isso define a fase 5.
- Quantos dias o NVR guarda antes de sobrescrever, para planejar as idas com o HD.
- As 16 câmeras terão áreas sobrepostas? Isso define as zonas da D12.
- Dá para acessar os registros do robô de ordenha (vaca, horário, produção)?
  Isso define a referência de identidade e a fase 6.
