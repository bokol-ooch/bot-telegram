@echo off
SETLOCAL ENABLEEXTENSIONS
SET BOTDIR=C:\TelegramBot
SET SVC=TelegramBotService

:: Cuenta con la que corre el servicio. Si dejas SVCPASS vacio, te la pide al instalar.
SET SVCUSER=.\Administrador
SET SVCPASS=

echo ===============================================
echo  Instalador del Bot de Telegram (servicio NSSM)
echo ===============================================

:: 1. Requiere administrador
net session >nul 2>&1
if errorlevel 1 (
    echo [!] Ejecuta este archivo como administrador: clic derecho, Ejecutar como administrador.
    pause
    exit /b 1
)

:: 2. Archivos necesarios junto a este .bat
if not exist "%~dp0telegram_bot.py" (
    echo [!] No encuentro telegram_bot.py junto a este archivo.
    pause
    exit /b 1
)
if not exist "%~dp0nssm.exe" (
    echo [!] Falta nssm.exe junto a este archivo. Descargalo de https://nssm.cc/download ^(carpeta win64^).
    pause
    exit /b 1
)

:: 3. Detectar el Python instalado
SET BOTPY=
for /f "delims=" %%i in ('py -c "import sys; print(sys.executable)" 2^>nul') do set BOTPY=%%i
if "%BOTPY%"=="" (
    echo [!] No encuentro Python. Instala Python o revisa que el comando "py" funcione.
    pause
    exit /b 1
)
echo [+] Python detectado: %BOTPY%

:: 4. Copiar archivos
echo [+] Copiando archivos a %BOTDIR%
mkdir %BOTDIR% 2>nul
xcopy /Y "%~dp0telegram_bot.py" "%BOTDIR%\" >nul
xcopy /Y "%~dp0nssm.exe" "%BOTDIR%\" >nul

if not exist "%BOTDIR%\token.txt" (
    echo [!] Falta %BOTDIR%\token.txt con el token del bot ^(solo el token, sin comillas^).
    pause
    exit /b 1
)

:: 5. Dependencias en ese mismo Python
echo [+] Instalando python-telegram-bot...
"%BOTPY%" -m pip install --quiet python-telegram-bot
if errorlevel 1 (
    echo [!] Fallo la instalacion de python-telegram-bot.
    pause
    exit /b 1
)

:: 6. Credenciales
if "%SVCPASS%"=="" set /p SVCPASS=Contrasena de %SVCUSER% : 

cd /d %BOTDIR%

:: 7. Si ya existia el servicio, se reemplaza
sc query %SVC% >nul 2>&1
if not errorlevel 1 (
    echo [+] Eliminando servicio anterior...
    nssm.exe stop %SVC% >nul 2>&1
    nssm.exe remove %SVC% confirm >nul 2>&1
)

:: 8. Crear y configurar el servicio
echo [+] Registrando servicio %SVC%...
nssm.exe install %SVC% "%BOTPY%" "%BOTDIR%\telegram_bot.py"
if errorlevel 1 (
    echo [!] Fallo el registro del servicio.
    pause
    exit /b 1
)
nssm.exe set %SVC% AppDirectory "%BOTDIR%"
nssm.exe set %SVC% DisplayName "Telegram Bot de Control"
nssm.exe set %SVC% Description "Bot de Telegram para tareas automatizadas"
nssm.exe set %SVC% ObjectName "%SVCUSER%" "%SVCPASS%"
nssm.exe set %SVC% Start SERVICE_AUTO_START
nssm.exe set %SVC% AppStdout "%BOTDIR%\bot_stdout.txt"
nssm.exe set %SVC% AppStderr "%BOTDIR%\bot_stdout.txt"
nssm.exe set %SVC% AppRotateFiles 1
nssm.exe set %SVC% AppRotateBytes 5242880
nssm.exe set %SVC% AppExit Default Restart
nssm.exe set %SVC% AppRestartDelay 10000

:: 9. Arrancar y verificar
echo [+] Iniciando servicio...
nssm.exe start %SVC%
timeout /t 8 /nobreak >nul
echo.
sc query %SVC% | find "STATE"
echo.
echo Ultimas lineas de bot.log:
powershell -NoProfile -Command "Get-Content '%BOTDIR%\bot.log' -Tail 3"
echo.
echo [OK] Si dice RUNNING, ya puedes cerrar esta ventana. Prueba /ping en Telegram.
pause
