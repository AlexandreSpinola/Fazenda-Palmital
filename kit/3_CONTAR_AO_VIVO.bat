@echo off
title Contar visitas ao vivo
call "%~dp0_configurar.bat"
echo Qual modelo?
echo   1 = nosso (YOLOE)
echo   2 = da colega
echo   3 = os dois ao mesmo tempo (para comparar; abre 4 janelas)
choice /c 123 /n /m "Escolha 1, 2 ou 3: "
set "OPCAO=%errorlevel%"
if not "%OPCAO%"=="2" (
    start "ch00 - nosso" cmd /k call "%~dp0_camera.bat" 1 ch00 nosso
    start "ch01 - nosso" cmd /k call "%~dp0_camera.bat" 2 ch01 nosso
)
if not "%OPCAO%"=="1" (
    start "ch00 - colega" cmd /k call "%~dp0_camera.bat" 1 ch00 colega
    start "ch01 - colega" cmd /k call "%~dp0_camera.bat" 2 ch01 colega
)
echo.
echo Abriu uma janela por camera. Para ENCERRAR e salvar: clique na janela
echo preta da camera e aperte Ctrl+C (ou a tecla q na janela do video).
echo Os resultados ficam em app\resultados
pause
