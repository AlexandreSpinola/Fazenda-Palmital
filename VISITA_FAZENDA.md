# Roteiro — visita à fazenda (quinta, 12/11/2026)

Objetivos:
1. Rodar o `contar_visitas.py` **ao vivo** nas câmeras.
2. Montar um **gabarito manual** para medir a precisão do script e do modelo da colega.
3. Trazer **mais vídeos** no pen drive.
4. Levantar as pendências do projeto.

**Plano A: kit do pen drive** (`D:\Fazenda\KIT_FAZENDA`). Roda em qualquer
Windows sem instalar nada, sem internet e sem placa de vídeo. Clique duas vezes
em `1_TESTAR_KIT.bat`, depois `2_TESTAR_CAMERAS.bat`, depois
`3_CONTAR_AO_VIVO.bat`. Instruções em `LEIA-ME.html`, dentro do kit.
Testado em 10/11: 5 min de vídeo processados em ~1 min só com a CPU.

**Plano B: notebook** (RTX 3050), preparado como na seção A. Use-o se o kit
não rodar no PC da fazenda (por exemplo, por bloqueio do Smart App Control).

---

## A. Preparar o notebook (antes de sair; precisa de internet)

O notebook tem RTX 3050 e 24 GB de RAM.

1. **Driver NVIDIA atualizado.** O PyTorch com CUDA 13 exige driver ≥ 580.
   Confira com `nvidia-smi`, que mostra a versão do driver no topo.
2. **Python 3.14:** `winget install Python.Python.3.14`
3. **Código pelo git**, numa pasta nova (ex. `C:\Fazenda`):
   ```powershell
   git clone -b reestruturacao-pipeline https://github.com/AlexandreSpinola/Fazenda-Palmital.git
   ```
   **Do pen drive (`D:\Fazenda\`)**, copie:
   - `para_notebook\yoloe-vaca.pt` → `Fazenda-Palmital\modelos\`
   - `best.pt` (modelo da colega) → `Colega\best.pt`, ao lado de `Fazenda-Palmital`
   - `KIT_FAZENDA\videos\...Ch.1...2026-10-01-05-00-23.mp4` (2 h de vídeo,
     para o teste sem internet; **não renomeie**, porque o horário vem do nome)
4. **Ambiente** (na pasta acima de `Fazenda-Palmital`):
   ```powershell
   winget install Microsoft.VCRedist.2015+.x64
   py -3.14 -m venv venv
   venv\Scripts\python -m pip install torch==2.14.1 torchvision==0.29.1 --index-url https://download.pytorch.org/whl/cu130
   venv\Scripts\python -m pip install -r Fazenda-Palmital\requirements.txt
   venv\Scripts\python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
   ```
5. **Teste sem internet**, com um `.dav` copiado:
   ```powershell
   cd Fazenda-Palmital
   ..\venv\Scripts\python contar_visitas.py "CAMINHO\VIDEO.dav" --inicio 05:30 --fim 05:40 --mostrar
   ```
   Se o Windows bloquear alguma DLL ("política de Controle de Aplicativo"),
   anote qual é. É o Smart App Control, o mesmo que bloqueou o pandas aqui.
6. Instale o **VLC** (para testar o RTSP).

## B. Na fazenda

### 1. Conectar nas câmeras (15 min)
- Ligue o notebook na **rede da fazenda** (cabo ou Wi-Fi do mesmo roteador do NVR).
- Teste no **VLC** (Mídia → Abrir fluxo de rede):
  `rtsp://admin:SENHA@192.168.10.66:554/cam/realmonitor?channel=1&subtype=1`
  - `channel=1` e `channel=2` são as duas câmeras. Anote **qual é qual**.
  - `subtype=1` é o fluxo leve (substream). Se a imagem vier muito pequena,
    teste `subtype=0`.
- Se não abrir: confirme o IP do NVR no menu dele e se o RTSP está habilitado
  (Rede → Conexão / RTSP, porta 554).

### 2. Rodar ao vivo (1–2 h), as duas câmeras ao mesmo tempo
Dois terminais:
```powershell
..\venv\Scripts\python contar_visitas.py "rtsp://admin:SENHA@192.168.10.66:554/cam/realmonitor?channel=1&subtype=1" --camera ch00 --mostrar --recortes 30
..\venv\Scripts\python contar_visitas.py "rtsp://admin:SENHA@192.168.10.66:554/cam/realmonitor?channel=2&subtype=1" --camera ch01 --mostrar --recortes 30
```
- **Ctrl+C** encerra salvando tudo (os CSVs também são gravados durante a execução).
- Confira na janela se a **linha vermelha** passa sobre a barra do cocho. Se
  não passar, rode com outro `--linha` (ex. `--linha 0.38`).
- Num terceiro terminal, se a GPU aguentar, rode o modelo da colega numa das
  câmeras (`--modelo ..\Colega\best.pt --camera ch00_colega`).

### 3. Gabarito manual, durante a execução (o mais importante)
Numa planilha ou papel, com o **relógio do notebook**:

| A cada 5 min | ch00: vacas com a cabeça no cocho | ch01: vacas com a cabeça no cocho |
|---|---|---|
| 08:00 | | |
| 08:05 | | |

E escolha **3–4 vacas fáceis de reconhecer** (manchas marcantes, brinco
visível). Anote cada vez que elas **entram e saem** do cocho:

| Vaca (descrição/nome) | Câmera | Entrou | Saiu |
|---|---|---|---|

Isso dá para comparar ocupação e visitas do script (e do modelo da colega)
com a realidade.

### 4. Copiar vídeos do NVR para o pen drive
- O pen drive tem **32 GB** (~27 GB livres) e está em **FAT32**, que **não
  aceita arquivos maiores que 4 GB**. Um dia inteiro de uma câmera tem ~5,3 GB.
  Na exportação do NVR, **escolha períodos de até ~12 h por arquivo** (ex.
  00:00–12:00 e 12:00–24:00), ou o NVR pode falhar ou cortar o arquivo.
- Pela porta USB do NVR: Backup → selecionar canais 1 e 2 → período.
- Cerca de **10,6 GB por dia** (2 câmeras). Com o kit ocupando ~2 GB, sobram
  ~25 GB, ou **~2 dias**. Se der, leve também o HD externo.
- O pen drive grava a **~7 MB/s**: cada dia das duas câmeras leva **~30 min**
  para copiar, ou mais se a porta USB do NVR for lenta. **Comece a exportação
  logo que chegar** e rode o contador enquanto isso.
- Priorize **variedade**: dias diferentes da semana, um dia de chuva se houver,
  e o próprio dia da visita (para casar com o gabarito).

### 5. Levantar as pendências
- [ ] **PC da fazenda:** processador, RAM, placa de vídeo, Windows (Home/Pro)
- [ ] **Internet:** velocidade de **upload** (fast.com ou speedtest)
- [ ] **NVR:** quantos dias de gravação ele guarda (menu de armazenamento)
- [ ] **14 câmeras novas:** onde vão ficar? As áreas vão se sobrepor? Fotos do cocho inteiro
- [ ] **Porteira com RFID:** dá para exportar o log (vaca + horário)? Quem
      fornece o sistema? Onde caberia uma câmera em cima?
- [ ] **Nome ↔ brinco:** existe uma lista ligando os nomes das vacas (Manuela,
      Braúna...) aos números de brinco/RFID?
- [ ] **Robô de ordenha:** dá para exportar a produção por vaca?

## C. Na volta
- Copiar `resultados/` do notebook e os vídeos do pen drive para o laboratório.
- Rodar o `contar_visitas.py` nos vídeos do dia da visita **aqui**, com os dois
  modelos, e comparar com o gabarito.
- Gerar o `lote_002` com os vídeos novos e enviar ao CVAT.
