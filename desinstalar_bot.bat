cd /d C:\TelegramBot
@echo off
setlocal

set SERVICIO=TelegramBotService

echo.
echo === GESTIÓN DEL SERVICIO: %SERVICIO% ===

:: Verificar si el servicio existe
sc query %SERVICIO% >nul 2>&1
if errorlevel 1060 (
    echo El servicio %SERVICIO% no existe.
    goto :EOF
)

:: Intentar detener el servicio
echo Deteniendo servicio %SERVICIO%...
sc stop %SERVICIO%
timeout /t 3 > nul

:: Obtener PID del servicio (por si no se detuvo bien)
for /f "tokens=2 delims=:" %%A in ('sc queryex %SERVICIO% ^| find "PID"') do (
    set "PID=%%A"
)

:: Quitar espacios del valor del PID
set "PID=%PID: =%"

if not "%PID%"=="" (
    echo PID del servicio: %PID%
    echo Forzando cierre del proceso...
    taskkill /PID %PID% /F >nul 2>&1
)

:: Eliminar el servicio
echo Eliminando servicio %SERVICIO%...
sc delete %SERVICIO%

echo.
echo ? Servicio %SERVICIO% detenido y eliminado correctamente.
pause
endlocal
