@echo off
rem Roda o contar_visitas.py ao vivo numa camera.
rem Uso (pelos outros .bat): _camera.bat <canal RTSP> <nome da camera> <nosso|colega>
cd /d "%~dp0app"
set "YOLO_OFFLINE=1"
set "URL=rtsp://%USUARIO%:%SENHA%@%IP%:554/cam/realmonitor?channel=%~1&subtype=1"
if /i "%~3"=="colega" (
    "%~dp0python\python.exe" contar_visitas.py "%URL%" --camera "%~2_colega" --modelo modelos\colega.pt --conf 0.25 --mostrar --recortes 30
) else (
    "%~dp0python\python.exe" contar_visitas.py "%URL%" --camera "%~2" --mostrar --recortes 30
)
echo.
echo Encerrado. Os resultados estao em app\resultados
