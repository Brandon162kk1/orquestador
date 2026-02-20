#---------- Orquestador que trabaja con Webhooks ----------

from flask import Flask, request, jsonify
import os
import threading
import time
import subprocess
import random
import socket
import string
import json
from Tiempo.fechas_horas import get_hora_minuto_segundo,get_dia,get_mes,get_anio

volumen_host = os.getenv("HOST_DOWNLOADS_PATH")
volumen_host_codigo = os.getenv("HOST_CODIGO_PATH")
app = Flask(__name__)

SIGNAL_PATH = "/app/sync"  

def generar_job_id():
    return "job_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def monitor_signals():
    """Lógica que ya tienes — revisa flags y lanza contenedores."""
    while True:
        try:
            for flag in os.listdir(SIGNAL_PATH):
                ruta_flag = os.path.join(SIGNAL_PATH, flag)
                with open(ruta_flag) as f:
                    data = json.load(f)
                
                json_data = json.dumps(data)
                os.remove(ruta_flag)

                job_id = generar_job_id()

                lanzar_contenedor(
                    f"conWebIncRen_{get_hora_minuto_segundo()}",
                    "web_corredor:latest",
                    "/app/supervisord.conf",                  
                    f"{json_data}",
                    f"{job_id}"
                )

        except Exception as e:
            print(f"⚠️ Error en monitor_signals: {e}")

        time.sleep(5)  

def get_free_port():
    """
    Devuelve un puerto libre, seguro y de 4 dígitos (rango 1024–9999),
    evitando colisiones con otros procesos o reservas del sistema.
    """
    while True:
        port = random.randint(7050, 7060)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue

def lanzar_contenedor(nombre,imagen,conf_path,json_data,jobid):

    """Ejecuta docker run dinámicamente con manejo de errores"""
    print(f"⌛ Lanzando contenedor '{nombre}' , Fecha: {get_dia()}-{get_mes()}-{get_anio()}.")

    display_num = random.randint(1, 99)
    vnc_port = 5900 + display_num
    novnc_port = 6080 + display_num

    host_port = get_free_port()
    print(f"🖥 DISPLAY=:{display_num} | VNC interno={vnc_port} | noVNC interno={novnc_port} → host={host_port}")

    cmd = [
        "docker", "run", "--rm", "-d",
        "--network", "orchestrator_network" ,
        "-p", f"{host_port}:{novnc_port}",
        "-v", f"{volumen_host_codigo}:/app/Codigo",
        "-v", f"mapfre_codigo:/codigo_mapfre",
        "-v", "pacifico_codigo:/codigo",
        "-v", "rimac_SAS:/codigo_rimac_SAS",
        "-v", "rimac_web_corredores:/codigo_rimac_WC",
        "-v", f"{volumen_host}:/app/Downloads",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "--env-file", "/app/variables.env",
        "--name", nombre,
        "-e", f"NOVNC_PORT={novnc_port}",
        "-e", f"VNC_PORT={vnc_port}",
        "-e", f"DISPLAY_NUM={display_num}",
        "-e", f"DATA={json_data}",
        "-e", f"jobid={jobid}",
        "-e", f"puerto={host_port}",
        imagen,
        "supervisord", "-c", conf_path
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"🚀 Contenedor lanzado correctamente: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al lanzar {nombre}: {e.stderr.strip()}")
    finally:
        print("------------------------------------------------------------------")

@app.route("/notify", methods=["POST"])
def notify():
    """Recibe la llamada HTTP desde n8n y crea el flag correspondiente."""
    data = request.get_json()
    print("📩 Llamado recibido desde n8n:", data)

    flag_path = os.path.join(SIGNAL_PATH, "run_solicitud.flag")

    with open(flag_path, "w") as f:
        json.dump(data, f)

    print(f"✅ Flag creado: {flag_path}")
    return jsonify({"status": "ok", "flag": flag_path}), 200

if __name__ == "__main__":
    threading.Thread(target=monitor_signals, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)
