# Kit da fazenda — contar vacas no cocho sem instalar nada

Este pen drive roda o contador de visitas em **qualquer computador com
Windows 10/11 (64 bits)**:
- sem instalar Python;
- sem internet;
- sem placa de vídeo;
- sem senha de administrador.

Os resultados ficam gravados **no próprio pen drive** (`app\resultados`).

> Se algo não funcionar no computador da fazenda, use o **notebook** (veja
> `VISITA_FAZENDA.html`).

## Passo a passo

Clique duas vezes nos arquivos, **nesta ordem**:

### 1. `1_TESTAR_KIT.bat`: o kit roda neste computador?
Processa 10 minutos de um vídeo gravado (já está no pen drive). Deve abrir uma
janela com as vacas: **caixa verde** = vaca no cocho, com o número da visita e o
cronômetro. Leva de 1 a 5 minutos. Faça isso **antes** de mexer com as câmeras.

### 2. `2_TESTAR_CAMERAS.bat`: as câmeras respondem?
O computador precisa estar na **rede da fazenda**, no mesmo roteador do NVR.
- Pergunta o IP do NVR (Enter aceita `192.168.10.66`), o usuário (Enter aceita `admin`) e a **senha**.
- Salva uma foto de cada câmera em `app\resultados` e abre a pasta.
- **Confira** na foto se a **linha vermelha (0.40)** passa sobre a barra do cocho.
  Se a barra estiver em outra linha, anote o número. Se for o caso, posso
  ajustar o `--linha` depois.

### 3. `3_CONTAR_AO_VIVO.bat`: contar visitas
- Pergunta o acesso ao NVR e o modelo:
  - **1** = nosso (YOLOE);
  - **2** = da colega;
  - **3** = os dois ao mesmo tempo, para comparar.
- Abre **uma janela por câmera**. A janela de vídeo mostra as vacas; a janela
  preta mostra o andamento a cada minuto.
- **Para encerrar:** tecla **q** na janela do vídeo, ou **Ctrl+C** na janela
  preta. Se ela perguntar "Deseja finalizar o arquivo em lotes (S/N)?", tanto
  faz: os dados já foram salvos.
- Os CSVs são gravados **durante** a execução. Se o computador desligar, o que
  já foi medido não se perde.

## O que sai em `app\resultados\<camera>_<data_hora>\`
| Arquivo | Conteúdo |
|---|---|
| `visitas.csv` | uma linha por visita: entrou, saiu, duração (min), posição no cocho |
| `ocupacao.csv` | por minuto: vacas no cocho (média e máximo) e vacas no quadro |
| `deteccoes.csv` | cada detecção, para reprocessar no laboratório |
| `recortes\` | foto de cada vaca a cada 30 s (para os clusters de identidade) |

## Se der problema
| Sintoma | O que fazer |
|---|---|
| Janela pisca e fecha, ou erro de **DLL** | Rode `extras\vc_redist.x64.exe` (pede administrador) e tente de novo |
| "Uma política de Controle de Aplicativo bloqueou este arquivo" | É o *Smart App Control* do Windows. Neste computador o kit não vai rodar; use o notebook |
| `[FALHOU]` no teste das câmeras | Confira o IP do NVR (menu do NVR → Rede), a senha e se o RTSP está habilitado (porta 554). Teste com `subtype=0` no lugar de `subtype=1` |
| Senha com `&`, `%`, `@`, `:` ou `/` | Esses caracteres atrapalham a URL. Use o notebook e digite a URL com a senha codificada (ex. `@` vira `%40`) |
| Muito lento (o horário na janela atrasa em relação ao relógio) | Use só o modelo 2 (da colega), que é ~7× mais leve |

## Conteúdo do pen drive
- `python\`: Python 3.14 portátil com PyTorch (CPU), Ultralytics, OpenCV e PyAV
- `app\`: os scripts (`contar_visitas.py`, `testar_camera.py`) e os modelos
- `videos\`: 2 h de vídeo de 01/10/2026 (ch01, 5h–7h), para o teste do passo 1
- `extras\vc_redist.x64.exe`: instalador oficial da Microsoft, caso falte DLL
- `VISITA_FAZENDA.html`: o roteiro completo da visita (gabarito manual, pendências)
