@echo off
rem Pergunta os dados de acesso ao NVR (Enter mantem o valor entre colchetes).
rem Usado pelos outros .bat; nao precisa ser aberto diretamente.
if not defined IP set "IP=192.168.10.66"
if not defined USUARIO set "USUARIO=admin"
echo.
set /p "IP=IP do NVR [%IP%]: "
set /p "USUARIO=Usuario do NVR [%USUARIO%]: "
set /p "SENHA=Senha do NVR: "
echo.
