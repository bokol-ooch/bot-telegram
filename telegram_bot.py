import asyncio
import datetime
import logging
import os
import subprocess
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================= CONFIGURACION =================
BASE_DIR = Path(__file__).resolve().parent
USUARIOS_AUTORIZADOS = [123456789]
# Quién puede usar /ps (ejecuta comandos de PowerShell en el servidor). Déjalo lo más corto posible.
PS_USUARIOS = list(USUARIOS_AUTORIZADOS)
PS_TIMEOUT = 60          # segundos máximos por comando
PS_MAX_CHARS = 3500      # la respuesta se recorta a este tamaño
MODELOS_POWERBI = ["ventas", "cedis", "compras"]
REFRESH_SCRIPT_PATH = r"C:\Users\Administrador\Documents\actualizar-pbi\actualizar-pbi.ps1"

# comando de Telegram -> clave en SCRIPTS_VALIDOS
COMANDOS = {
    "ejecutar_venta": "venta",
    "ejecutar_instock": "instock",
    "ejecutar_conciliacion": "conciliacion",
    "ejecutar_gateway": "gateway",
    "ejecutar_refrescar": "refrescar",
}

SCRIPTS_VALIDOS = {
    "venta": "TASK:actualizarVentasDiarias",
    "instock": "TASK:instock",
    "conciliacion": "TASK:concoliacion",   # revisa que el nombre de la tarea sea exactamente este
    "gateway": "TASK:reiniciarServicioPBI",
    "refrescar": "TASK:actualizarPowerBi",
}


# ================= TOKEN Y LOGGING =================
def cargar_token() -> str:
    """El token NO va en el codigo: variable de entorno o archivo token.txt junto al script."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        return token
    archivo = BASE_DIR / "token.txt"
    if archivo.exists():
        return archivo.read_text(encoding="utf-8").strip()
    raise SystemExit("Falta el token: crea token.txt junto al script o define TELEGRAM_BOT_TOKEN")


def configurar_logging():
    handler = RotatingFileHandler(
        BASE_DIR / "bot.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    # httpx registra CADA peticion a Telegram en nivel INFO; lo bajamos para no inundar el log
    logging.getLogger("httpx").setLevel(logging.WARNING)


log = logging.getLogger("bot")


# ================= AUXILIARES =================
def autorizado(user_id) -> bool:
    return user_id in USUARIOS_AUTORIZADOS


async def lanzar_tarea(nombre_tarea: str):
    # Se ejecuta en un hilo para no bloquear el bot mientras schtasks responde
    r = await asyncio.to_thread(
        subprocess.run,
        ["schtasks", "/run", "/tn", nombre_tarea],
        capture_output=True, text=True, errors="replace", timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(f"schtasks: {(r.stderr or r.stdout).strip()}")


async def comprobar_permiso(update: Update) -> bool:
    user_id = update.effective_user.id
    if autorizado(user_id):
        return True
    await update.message.reply_text("❌ No tienes permiso para usar este bot.")
    log.warning("Intento no autorizado de %s", user_id)
    return False


# ================= COMANDOS =================
async def ejecutar_script(update: Update, context: ContextTypes.DEFAULT_TYPE, clave: str):
    if not await comprobar_permiso(update):
        return
    destino = SCRIPTS_VALIDOS.get(clave)
    if destino is None:
        await update.message.reply_text(f"❌ Script '{clave}' no reconocido.")
        return
    try:
        await lanzar_tarea(destino.removeprefix("TASK:"))
        await update.message.reply_text(f"✅ Tarea '{clave}' lanzada.")
        log.info("Tarea '%s' ejecutada por %s", clave, update.effective_user.id)
    except Exception as e:
        await update.message.reply_text(f"❌ Error al ejecutar '{clave}': {e}")
        log.error("Error al ejecutar '%s': %s", clave, e)


def crear_handler(clave: str):
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await ejecutar_script(update, context, clave)
    return handler


async def ejecutar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usa: /ejecutar <nombre_script>")
        return
    await ejecutar_script(update, context, context.args[0].lower())


async def refrescar_modelo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await comprobar_permiso(update):
        return
    if not context.args:
        await update.message.reply_text(
            "Usa: /refrescar_modelo <nombre>\nDisponibles: " + ", ".join(MODELOS_POWERBI)
        )
        return
    modelo = context.args[0].lower()
    if modelo not in MODELOS_POWERBI:
        await update.message.reply_text(
            f"❌ Modelo '{modelo}' no reconocido. Disponibles: {', '.join(MODELOS_POWERBI)}"
        )
        return
    try:
        # La salida va a un archivo: con PIPE sin leer, el proceso se bloquea al llenarse el buffer
        with open(BASE_DIR / "refresh_modelo.log", "ab") as salida:
            salida.write(f"\n--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} modelo={modelo} ---\n".encode())
            salida.flush()
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", REFRESH_SCRIPT_PATH, "-Models", modelo],
                stdout=salida, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        await update.message.reply_text(f"🔄 Refresh de '{modelo}' iniciado.")
        log.info("Refresh de '%s' iniciado por %s", modelo, update.effective_user.id)
    except Exception as e:
        await update.message.reply_text(f"❌ Error al iniciar el refresh de '{modelo}': {e}")
        log.error("Error al iniciar refresh de '%s': %s", modelo, e)


async def modelos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update.effective_user.id):
        return
    await update.message.reply_text("Modelos disponibles:\n" + "\n".join(f"- {m}" for m in MODELOS_POWERBI))


async def tareas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/tareas [filtro] -> lista las tareas del Programador de tareas (sin las de Microsoft)."""
    if not await comprobar_permiso(update):
        return
    filtro = " ".join(context.args).lower() if context.args else ""
    ps = (
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\\Microsoft\\*' } | "
        "ForEach-Object { $i = $_ | Get-ScheduledTaskInfo; "
        "'{0}|{1}|{2}|{3}' -f $_.TaskName, $_.State, $i.LastRunTime, $i.LastTaskResult }"
    )
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        salida = r.stdout.decode("utf-8", errors="replace")
        lineas = []
        for fila in salida.splitlines():
            partes = fila.split("|")
            if len(partes) != 4 or filtro not in partes[0].lower():
                continue
            nombre, estado, ultima, resultado = partes
            icono = "✅" if resultado.strip() == "0" else "⚠️"
            lineas.append(f"{icono} {nombre} [{estado}]\n    última: {ultima} (código {resultado})")
        if not lineas:
            await update.message.reply_text("No encontré tareas" + (f" que contengan '{filtro}'." if filtro else "."))
            return
        # Telegram acepta máx. 4096 caracteres por mensaje: se envía en partes
        bloque = ""
        for linea in lineas:
            if len(bloque) + len(linea) > 3800:
                await update.message.reply_text(bloque)
                bloque = ""
            bloque += linea + "\n"
        if bloque:
            await update.message.reply_text(bloque)
        log.info("Lista de tareas consultada por %s", update.effective_user.id)
    except Exception as e:
        await update.message.reply_text(f"❌ Error al listar las tareas: {e}")
        log.error("Error al listar tareas: %s", e)


async def correr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/correr <nombre exacto de la tarea> -> ejecuta cualquier tarea de la raíz del Programador de tareas."""
    if not await comprobar_permiso(update):
        return
    if not context.args:
        await update.message.reply_text("Usa: /correr <nombre de la tarea>\nMira los nombres con /tareas")
        return
    nombre = " ".join(context.args).strip()
    # Solo tareas de la raíz: se bloquean rutas (\Microsoft\...) para no tocar tareas del sistema
    if nombre.startswith(("\\", "/")) or "\\" in nombre:
        await update.message.reply_text("❌ Indica solo el nombre de la tarea, sin rutas.")
        return
    try:
        await lanzar_tarea(nombre)
        await update.message.reply_text(f"✅ Tarea '{nombre}' lanzada.")
        log.info("Tarea '%s' lanzada con /correr por %s", nombre, update.effective_user.id)
    except Exception as e:
        await update.message.reply_text(f"❌ No pude lanzar '{nombre}': {e}")
        log.error("Error al lanzar '%s': %s", nombre, e)


async def ps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ps <comando> -> ejecuta un comando de PowerShell y devuelve la salida."""
    user_id = update.effective_user.id
    if user_id not in PS_USUARIOS:
        await update.message.reply_text("❌ No tienes permiso para usar /ps.")
        log.warning("Intento de /ps no autorizado de %s", user_id)
        return
    # Se toma el texto original (no context.args) para conservar comillas y espacios
    comando = (update.message.text or "").partition(" ")[2].strip()
    if not comando:
        await update.message.reply_text("Usa: /ps <comando>\nEj.: /ps Get-Service TelegramBotService")
        return
    log.info("/ps de %s: %s", user_id, comando[:300])
    try:
        r = await asyncio.to_thread(
            subprocess.run,
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + comando],
            capture_output=True, stdin=subprocess.DEVNULL, timeout=PS_TIMEOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        salida = (r.stdout + r.stderr).decode("utf-8", errors="replace").strip() or "(sin salida)"
        if len(salida) > PS_MAX_CHARS:
            salida = salida[:PS_MAX_CHARS] + f"\n... [recortado, {len(salida)} caracteres en total]"
        await update.message.reply_text(f"{salida}\n\n[código de salida: {r.returncode}]")
    except subprocess.TimeoutExpired:
        await update.message.reply_text(f"⏱️ El comando superó {PS_TIMEOUT}s y se canceló.")
        log.warning("/ps agotó el tiempo: %s", comando[:300])
    except Exception as e:
        await update.message.reply_text(f"❌ Error al ejecutar el comando: {e}")
        log.error("Error en /ps: %s", e)


async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update.effective_user.id):
        return
    lineas = ["Comandos disponibles:"] + [f"/{c}" for c in COMANDOS]
    lineas += ["/refrescar_modelo <nombre>", "/modelos", "/tareas [filtro]", "/correr <tarea>", "/ps <comando>", "/ping", "", "También: /ejecutar <script>, p. ej. venta"]
    await update.message.reply_text("\n".join(lineas))


async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update.effective_user.id):
        return
    await update.message.reply_text("Bot activo.")
    await listar(update, context)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if autorizado(update.effective_user.id):
        await update.message.reply_text("pong 🏓")


async def error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Excepcion no controlada", exc_info=context.error)


# ================= MAIN =================
def main():
    configurar_logging()
    app = ApplicationBuilder().token(cargar_token()).build()

    app.add_handler(CommandHandler(["start", "iniciar"], iniciar))   # /start es el comando por defecto de Telegram
    app.add_handler(CommandHandler("listar", listar))
    app.add_handler(CommandHandler("ejecutar", ejecutar))
    app.add_handler(CommandHandler("refrescar_modelo", refrescar_modelo))
    app.add_handler(CommandHandler("modelos", modelos))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("tareas", tareas))
    app.add_handler(CommandHandler("correr", correr))
    app.add_handler(CommandHandler("ps", ps))
    for comando, clave in COMANDOS.items():
        app.add_handler(CommandHandler(comando, crear_handler(clave)))
    app.add_error_handler(error_handler)

    log.info("Bot iniciado.")
    # drop_pending_updates: al reiniciar NO se ejecutan comandos acumulados mientras el bot estaba caido
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
