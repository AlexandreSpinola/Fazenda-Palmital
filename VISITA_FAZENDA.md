# Roteiro — visita à fazenda (quinta, 12/11/2026)

Objetivos:
1. Rodar o `contar_visitas.py` **ao vivo** nas câmeras.
2. Montar um **gabarito manual** para medir a precisão do script e do modelo da colega.
3. Trazer **mais vídeos** no pen drive.
4. Levantar as pendências do projeto.

---

## A. Preparar o notebook (antes de sair; precisa de internet)

O notebook tem RTX 3050 e 24 GB de RAM.

1. **Driver NVIDIA atualizado.** O PyTorch com CUDA 13 exige driver ≥ 580.
   Confira com `nvidia-smi`, que mostra a versão do driver no topo.
2. **Python 3.14:** `winget install Python.Python.3.14`
3. **Copiar o projeto** pelo pen drive ou pelo git. Basta a pasta
   `Fazenda-Palmital` **sem** `Gravações/`, `lotes/` e `resultados/`, mas
   **com** `modelos/yoloe-vaca.pt` (70 MB). Para comparar, copie também
   `Colega/best.pt`.
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

### 4. Copiar vídeos do NVR para o pen drive (64 GB)
- Pela porta USB do NVR: Backup → selecionar canais 1 e 2 → período.
- Cerca de **10,6 GB por dia** (2 câmeras), então cabem **~5 dias**.
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
