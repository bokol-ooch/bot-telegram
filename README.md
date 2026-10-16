# Bot de Telegram de control (Windows)

Bot de Telegram que corre como **servicio de Windows** y permite, desde el celular, lanzar tareas del Programador de tareas, refrescar modelos de Power BI, consultar el estado de las tareas y ejecutar comandos de PowerShell en el servidor.

Está hecho con `python-telegram-bot` (v20+, asíncrono) y se mantiene vivo con **NSSM**.

---

## Contenido

- [Estructura de archivos](#estructura-de-archivos)
- [Requisitos](#requisitos)
- [Configuración](#configuración)
- [Comandos del bot](#comandos-del-bot)
- [Instalación](#instalación)
- [Administrar el servicio](#administrar-el-servicio)
- [Logs](#logs)
- [Seguridad](#seguridad)
- [Solución de problemas](#solución-de-problemas)
- [Notas técnicas](#notas-técnicas)

---

## Estructura de archivos

```
C:\TelegramBot\
├── telegram_bot.py        # El bot (todo el código)
├── token.txt              # Token del bot (solo el token, sin comillas)
├── nssm.exe               # Convierte el bot en servicio de Windows
├── instalar_bot.bat       # Instalador (copia archivos y registra el servicio)
├── reiniciarServicio.bat  # Atajo: net stop / net start del servicio
├── desinstalar.bat        # Atajo: elimina el servicio
├── bot.log                # Log del bot (rotativo, 5 MB x 3 archivos)
├── bot_stdout.txt         # Salida estándar/errores del proceso (la gestiona NSSM)
└── refresh_modelo.log     # Salida de los refrescos de Power BI
```

`telegram_bot_service.py` (versión anterior basada en pywin32) **ya no se usa**; NSSM lo reemplaza.

---

## Requisitos

- Windows Server con acceso a internet hacia `api.telegram.org`.
- Python 3.10 o superior (probado con 3.14) y la librería:
  ```powershell
  py -m pip install python-telegram-bot
  ```
- [NSSM](https://nssm.cc/download) (`win64\nssm.exe`).
- Un bot creado con **@BotFather** y su token.
- La cuenta con la que corre el servicio (por defecto `.\Administrador`) debe poder ejecutar las tareas programadas y tener acceso a `C:\TelegramBot`.

---

## Configuración

### Token

El token **no va en el código**. El bot lo lee, en este orden, de:

1. La variable de entorno `TELEGRAM_BOT_TOKEN`.
2. El archivo `token.txt` junto al script.

### Parámetros en `telegram_bot.py`

Están al inicio del archivo:

| Variable | Descripción |
|---|---|
| `USUARIOS_AUTORIZADOS` | Lista de IDs de Telegram con permiso para usar el bot. |
| `PS_USUARIOS` | IDs que pueden usar `/ps`. Por defecto copia a los autorizados; consérvala lo más corta posible. |
| `PS_TIMEOUT` | Segundos máximos por comando de `/ps` (60 por defecto). |
| `PS_MAX_CHARS` | Tamaño máximo de la respuesta de `/ps` (3500 por defecto). |
| `MODELOS_POWERBI` | Modelos que acepta `/refrescar_modelo` (`ventas`, `cedis`, `compras`). |
| `REFRESH_SCRIPT_PATH` | Ruta del script de PowerShell que refresca Power BI. |
| `SCRIPTS_VALIDOS` | Relación clave → tarea programada para `/ejecutar` y los atajos. |
| `COMANDOS` | Relación comando de Telegram → clave de `SCRIPTS_VALIDOS`. |

Para saber tu ID de Telegram, escríbele a `@userinfobot`.

### Tareas predefinidas (`SCRIPTS_VALIDOS`)

| Clave | Tarea programada |
|---|---|
| `venta` | `actualizarVentasDiarias` |
| `instock` | `instock` |
| `conciliacion` | `concoliacion` (verifica que el nombre coincida con la tarea real) |
| `gateway` | `reiniciarServicioPBI` |
| `refrescar` | `actualizarPowerBi` |

---

## Comandos del bot

Solo responden a usuarios autorizados.

| Comando | Qué hace |
|---|---|
| `/start`, `/iniciar` | Confirma que el bot está activo y muestra la lista de comandos. |
| `/listar` | Muestra los comandos disponibles. |
| `/ping` | Responde `pong`. Sirve para comprobar que el bot está vivo. |
| `/ejecutar_venta` | Lanza la tarea de ventas diarias. |
| `/ejecutar_instock` | Lanza la tarea de instock. |
| `/ejecutar_conciliacion` | Lanza la tarea de conciliación. |
| `/ejecutar_gateway` | Lanza la tarea que reinicia el servicio de Power BI. |
| `/ejecutar_refrescar` | Lanza la tarea de actualización de Power BI. |
| `/ejecutar <script>` | Igual que los anteriores, indicando la clave (p. ej. `/ejecutar venta`). |
| `/refrescar_modelo <nombre>` | Refresca un modelo de Power BI (`ventas`, `cedis` o `compras`). |
| `/modelos` | Lista los modelos disponibles. |
| `/tareas [filtro]` | Lista las tareas del Programador de tareas (sin las de Microsoft) con su estado, última ejecución y código de resultado. |
| `/correr <nombre>` | Ejecuta **cualquier** tarea de la raíz del Programador de tareas. El nombre puede llevar espacios, sin comillas. |
| `/ps <comando>` | Ejecuta un comando de PowerShell en el servidor y devuelve la salida. |

### Ejemplos

```
/tareas venta
/correr tarea que inicia aqui
/refrescar_modelo ventas
/ps Get-Service TelegramBotService
/ps cd C:\TelegramBot; dir
```

### Códigos de resultado de `/tareas`

- ✅ Código `0`: la última ejecución terminó sin error.
- ⚠️ Otro código: revisar. Algunos no son errores reales: `267009` indica que la tarea sigue corriendo y `267011` que nunca se ha ejecutado.

### Particularidades de `/ps`

- Cada comando es **independiente**: un `cd` o una variable no persisten al siguiente mensaje. Usa rutas completas o encadena con `;`.
- Se cancela a los 60 segundos.
- No admite comandos que pidan entrada o confirmación (usa `-Force` o `-Confirm:$false`).
- La salida se recorta a 3500 caracteres.
- Cada comando queda registrado en `bot.log`.

---

## Instalación

### Opción A: instalador automático

1. Crea una carpeta con estos archivos: `telegram_bot.py`, `instalar_bot.bat` y `nssm.exe`.
2. Crea `C:\TelegramBot\token.txt` con el token del bot.
3. Ejecuta `instalar_bot.bat` **como administrador**.

El instalador comprueba permisos y archivos, detecta el Python instalado con `py`, instala `python-telegram-bot`, registra el servicio `TelegramBotService` con arranque automático, lo inicia y muestra su estado. Si el servicio ya existía, lo reemplaza.

Al inicio del `.bat` están `SVCUSER` y `SVCPASS` (cuenta del servicio). Si dejas `SVCPASS` vacío, la pide al instalar.

### Opción B: manual (PowerShell como administrador)

```powershell
cd C:\TelegramBot
$py = (py -c "import sys; print(sys.executable)")
& $py -m pip install python-telegram-bot

.\nssm.exe install TelegramBotService "$py" "C:\TelegramBot\telegram_bot.py"
.\nssm.exe set TelegramBotService AppDirectory "C:\TelegramBot"
.\nssm.exe set TelegramBotService ObjectName ".\Administrador" 'TU_CONTRASEÑA'
.\nssm.exe set TelegramBotService Start SERVICE_AUTO_START
.\nssm.exe set TelegramBotService AppStdout "C:\TelegramBot\bot_stdout.txt"
.\nssm.exe set TelegramBotService AppStderr "C:\TelegramBot\bot_stdout.txt"
.\nssm.exe set TelegramBotService AppExit Default Restart
.\nssm.exe start TelegramBotService
```

### Verificar

```powershell
Get-Service TelegramBotService
Get-Content C:\TelegramBot\bot.log -Tail 5
```

Debe mostrar `Running` y una línea `Application started`. Luego envía `/ping` desde Telegram, cierra todas las ventanas y vuelve a enviarlo: si responde, corre como servicio.

---

## Administrar el servicio

```powershell
Get-Service TelegramBotService          # estado
Restart-Service TelegramBotService      # reiniciar (necesario tras cambiar telegram_bot.py)
Stop-Service TelegramBotService         # detener
Start-Service TelegramBotService        # iniciar
.\nssm.exe get TelegramBotService Application   # ver el Python configurado
.\nssm.exe set TelegramBotService Application "C:\ruta\python.exe"   # cambiarlo
.\nssm.exe remove TelegramBotService confirm    # eliminar el servicio
```

Tras actualizar `telegram_bot.py`, basta con reemplazar el archivo y reiniciar el servicio.

---

## Logs

| Archivo | Contenido |
|---|---|
| `bot.log` | Actividad del bot: arranques, comandos ejecutados, quién los lanzó, intentos no autorizados, errores. Rotativo (5 MB, 3 copias). |
| `bot_stdout.txt` | Salida estándar y errores del proceso, incluidos los fallos de arranque (módulo no encontrado, token faltante). |
| `refresh_modelo.log` | Salida de los refrescos de Power BI lanzados con `/refrescar_modelo`. |

Seguir el log en vivo:

```powershell
Get-Content C:\TelegramBot\bot.log -Wait -Tail 20
```

El nivel de `httpx` se limita a `WARNING` para que no registre cada petición a Telegram.

---

## Seguridad

- **El token es una credencial.** Quien lo tenga puede operar el bot. Si se expone, revócalo con `/revoke` en @BotFather y guarda el nuevo en `token.txt`.
- **El bot valida solo el ID de usuario de Telegram.** Quien controle tu cuenta de Telegram controla el servidor, sobre todo con `/ps` y `/correr`. Activa la **verificación en dos pasos** en Telegram.
- El servicio corre con la cuenta configurada (por defecto `Administrador`), así que `/ps` ejecuta comandos con esos permisos.
- No escribas contraseñas dentro de comandos `/ps`: quedan en `bot.log` y en el historial del chat.
- Mantén cortas `USUARIOS_AUTORIZADOS` y `PS_USUARIOS`. Para desactivar `/ps` por completo, deja `PS_USUARIOS = []`.
- `/correr` solo acepta tareas de la raíz del Programador de tareas y bloquea rutas como `\Microsoft\...`.
- Si guardas la contraseña de la cuenta en `instalar_bot.bat`, restringe quién puede leer el archivo.

---

## Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Unexpected status SERVICE_STOPPED in response to START control` | El proceso se cerró al arrancar | Revisar `bot_stdout.txt` y los eventos de NSSM (ver abajo). |
| Evento NSSM: `CreateProcess() failed: no puede encontrar el archivo` | La ruta de Python configurada ya no existe | `nssm get TelegramBotService Application` y corregir con `nssm set`. |
| `No module named 'telegram'` | La librería no está en el Python del servicio | `<ruta python> -m pip install python-telegram-bot` |
| `Falta el token` | No existe `token.txt` | Crearlo en `C:\TelegramBot` con solo el token. |
| `Conflict: terminated by other getUpdates request` | Hay dos instancias con el mismo token | Cerrar los `python.exe` sueltos (ver abajo). |
| El bot arranca pero no recibe mensajes | Hay un webhook configurado | `curl.exe "https://api.telegram.org/bot<TOKEN>/deleteWebhook"` |
| `/correr` responde "No pude lanzar" | Nombre inexacto o sin permisos | Copiar el nombre desde `/tareas` y probar `schtasks /run /tn "nombre"` en el servidor. |
| Error `1069` al iniciar el servicio | Usuario o contraseña incorrectos | Volver a ejecutar `nssm set ... ObjectName`. |
| Se cierra al cerrar la ventana | Corre en consola y no como servicio | Instalar el servicio con NSSM. |

### Comandos de diagnóstico

```powershell
# Eventos de NSSM
Get-WinEvent -LogName Application -MaxEvents 40 | Where-Object { $_.ProviderName -match 'nssm' } | Format-List TimeCreated, Message

# Procesos de Python en ejecución (no debe haber duplicados)
Get-CimInstance Win32_Process -Filter "name like 'python%'" | Select ProcessId, CommandLine | Format-List

# Probar el bot a mano, con el mismo Python del servicio
& (py -c "import sys; print(sys.executable)") C:\TelegramBot\telegram_bot.py

# Verificar el token
curl.exe "https://api.telegram.org/bot<TOKEN>/getMe"
```

Usa `curl.exe` y no `curl`, porque en PowerShell `curl` es un alias de otro comando.

---

## Notas técnicas

- **Arranque limpio:** el bot usa `drop_pending_updates=True`, así que al reiniciar **no ejecuta** los comandos que se enviaron mientras estaba caído. Evita lanzar una tarea varias veces por error.
- **Sin bloqueos:** las llamadas a `schtasks` y PowerShell se ejecutan en hilos (`asyncio.to_thread`), para no congelar el bot mientras responden.
- **Salida a archivo, no a PIPE:** los procesos lanzados por el bot (`refrescar_modelo`) escriben a archivo. Un `PIPE` que nadie lee se llena (~64 KB en Windows) y puede congelar el proceso en silencio; fue la causa sospechosa de los cuelgues de la versión anterior.
- **Reinicio automático:** NSSM reinicia el proceso si se cierra, y el servicio arranca con Windows.
- **Manejo de errores:** hay un `error_handler` global que registra cualquier excepción no controlada en `bot.log`.
- **Por qué NSSM:** el registro del servicio con pywin32 se quedaba colgado en este servidor; NSSM lanza `python.exe` directamente y es más sencillo de diagnosticar.
