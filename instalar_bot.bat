@echo off
SETLOCAL ENABLEEXTENSIONS
SET BOTDIR=C:\TelegramBot

echo ===============================================
echo Instalador del Bot de Telegram como Servicio
echo ===============================================

:: Crear carpeta destino
echo [+] Creando carpeta: %BOTDIR%
mkdir %BOTDIR% 2>nul

:: Copiar archivos
echo [+] Copiando archivos del bot...
xcopy /Y "%~dp0telegram_bot.py" "%BOTDIR%\"
xcopy /Y "%~dp0telegram_bot_service.py" "%BOTDIR%\"

:: Cambiar a la carpeta del bot
cd /d %BOTDIR%

:: Instalar pywin32
echo [+] Instalando pywin32 con ruta específica de Python...
py -m pip install pywin32

:: Registrar el servicio
echo [+] Registrando servicio de Windows...
py telegram_bot_service.py --username=.\Username --password="psswd1234##***" install

:: Iniciar el servicio
echo [+] Iniciando el servicio...
py telegram_bot_service.py start

echo [✓] Bot de Telegram instalado y ejecutándose como servicio.
pause
