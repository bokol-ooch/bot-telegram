import win32serviceutil
import win32service
import win32event
import servicemanager
import subprocess
import time
import os
import sys

class TelegramBotService(win32serviceutil.ServiceFramework):
    _svc_name_ = "TelegramBotService"
    _svc_display_name_ = "Telegram Bot de Control"
    _svc_description_ = "Servicio que ejecuta un bot de Telegram para tareas automatizadas"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.log_path = r"C:\TelegramBot\service_log.txt"

    def log(self, mensaje):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {mensaje}\n")

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.log("Servicio detenido correctamente.")
        self.running = False
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        self.log("Servicio iniciado.")
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.main()

    def main(self):
        try:
            ruta_script = r"C:\TelegramBot\telegram_bot.py"
    
            self.log("Lanzando telegram_bot.py en segundo plano...")
            while self.running:
                proceso = subprocess.Popen(
                    ["python", ruta_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True  # para decodificar automáticamente
                )
    
                stdout, stderr = proceso.communicate()
    
                if stdout:
                    self.log(f"[stdout] {stdout}")
                if stderr:
                    self.log(f"[stderr] {stderr}")
    
                self.log("El bot se cerró inesperadamente. Reiniciando en 10 segundos...")
                time.sleep(10)
    
        except Exception as e:
            self.log(f"Error en el servicio: {e}")
    
        self.log("Servicio detenido por main().")

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(TelegramBotService)
    
