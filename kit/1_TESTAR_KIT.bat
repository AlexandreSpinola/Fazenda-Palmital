@echo off
title Teste do kit (video gravado)
cd /d "%~dp0app"
set "YOLO_OFFLINE=1"
set "VIDEO="
for %%f in ("%~dp0videos\*.mp4") do set "VIDEO=%%~f"
if not defined VIDEO (
    echo Nenhum video .mp4 na pasta videos\
    pause
    exit /b 1
)
echo Testando o kit com 10 minutos do video gravado (leva de 1 a 5 minutos)...
echo Deve abrir uma janela com as vacas: caixas verdes = no cocho. Tecla q fecha.
echo.
"%~dp0python\python.exe" contar_visitas.py "%VIDEO%" --inicio 05:30 --fim 05:40 --mostrar --saida "%~dp0app\resultados\teste_kit"
echo.
if errorlevel 1 (
    echo [ERRO] O kit nao rodou neste computador. Veja a mensagem acima e o LEIA-ME.
) else (
    echo [OK] O kit funciona neste computador.
)
pause
