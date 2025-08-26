from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import subprocess
import os
import datetime
import sys

# Configuracion
BOT_TOKEN = "1234567890:qwertyuiopasdfghjklñzxcvbnm"
USUARIOS_AUTORIZADOS = [987654321]
LOG_PATH = r"C:\TelegramBot\log.txt"
PYTHON_EXE = r"C:\Python3.13.3\python.exe" # cambiar dependiendo del lugar de instalacion de python

# Scripts disponibles
SCRIPTS_VALIDOS = {
    "venta": "TASK:actualizarVentasDiarias",
    "carrera": r"C:\ejecutarweb.ps1",
    "tickets": r"C:\actualizarTickets.ps1",
}

def escribir_log(mensaje):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {mensaje}\n")

def lanzar_script(ruta_script):
    if ruta_script.startswith("TASK:"):
        nombre_tarea = ruta_script.split("TASK:")[1]
        # Ejecutar tarea programada con schtasks
        resultado = subprocess.run(
            ['schtasks', '/run', '/tn', nombre_tarea],
            capture_output=True, text=True
        )
        if resultado.returncode != 0:
            raise Exception(f"Error al ejecutar tarea programada: {resultado.stderr.strip()}")
        return resultado
    ext = os.path.splitext(ruta_script)[1].lower()
    if ext == ".ps1":
        return subprocess.Popen([
            "powershell", "-File", ruta_script
        ])
    elif ext == ".py":
        return subprocess.Popen([
            PYTHON_EXE, ruta_script
        ])
    else:
        raise Exception(f"Tipo de script no soportado: {ext}")


def autorizado(user_id):
    return user_id in USUARIOS_AUTORIZADOS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not autorizado(update.effective_user.id):
        return
    await update.message.reply_text("Bot activo. Usa /ejecutar <nombre_script>")
    texto = obtener_lista()
    await update.message.reply_text(texto)

async def ejecutar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not autorizado(user_id):
        await update.message.reply_text("No tienes permiso para usar este bot.")
        escribir_log(f"Intento no autorizado de {user_id}")
        return

    if not context.args:
        await update.message.reply_text("Usa el comando así: /ejecutar nombre_script")
        return

    script_key = context.args[0].lower()

    if script_key not in SCRIPTS_VALIDOS:
        await update.message.reply_text(f"{script_key} no reconocido.")
        return

    ruta_script = SCRIPTS_VALIDOS[script_key]

    try:
        resultado = lanzar_script(ruta_script)
        if isinstance(resultado, subprocess.CompletedProcess):
            # Es una tarea programada ejecutada con subprocess.run()
            await update.message.reply_text(f"Tarea programada ejecutada correctamente.")
        else:
            await update.message.reply_text(f"Ejecutando '{script_key}'...")
        escribir_log(f"Script/tarea '{script_key}' ejecutado por {user_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al ejecutar el script/tarea. {e}")
    escribir_log(f"Error al ejecutar '{script_key}' por {user_id}: {e}")

async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not autorizado(user_id):
        return

    lista = "\n".join(f"/ejecutar {k}" for k in SCRIPTS_VALIDOS.keys())
    await update.message.reply_text(f"📜 Scripts disponibles:\n{lista}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ejecutar", ejecutar))
    app.add_handler(CommandHandler("listar", listar))

    escribir_log("Bot iniciado.")
    app.run_polling()

if __name__ == "__main__":
    main()
