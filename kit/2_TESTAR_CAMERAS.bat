@echo off
title Teste das cameras (RTSP)
cd /d "%~dp0app"
call "%~dp0_configurar.bat"
set "URL1=rtsp://%USUARIO%:%SENHA%@%IP%:554/cam/realmonitor?channel=1&subtype=1"
set "URL2=rtsp://%USUARIO%:%SENHA%@%IP%:554/cam/realmonitor?channel=2&subtype=1"
echo Conectando nas cameras (canais 1 e 2)...
"%~dp0python\python.exe" testar_camera.py "%URL1%" "%URL2%"
echo.
echo As fotos de teste estao em app\resultados (abrindo a pasta).
echo Confira se a linha VERMELHA (0.40) passa sobre a barra do cocho.
start "" "%~dp0app\resultados"
pause
