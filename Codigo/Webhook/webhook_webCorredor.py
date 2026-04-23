#---------- Orquestador que trabaja con Webhooks ----------

from flask import Flask, request, jsonify
import os
import threading
import time
import subprocess
import random
import string
import json
from Tiempo.fechas_horas import get_hora_minuto_segundo,get_dia,get_mes,get_anio

volumen_host = os.getenv("HOST_DOWNLOADS_PATH")
#volumen_host_codigo = os.getenv("HOST_CODIGO_PATH")
app = Flask(__name__)

#SIGNAL_PATH = "/app/sync"
SIGNAL_PATH  = "/app/sync/webCorredor"
# 👇 AGREGA ESTO
os.makedirs(SIGNAL_PATH, exist_ok=True)

def generar_job_id():
    return "job_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def monitor_signals():
    """Lógica que ya tienes — revisa flags y lanza contenedores."""
    while True:
        try:
            for flag in os.listdir(SIGNAL_PATH ):
                ruta_flag = os.path.join(SIGNAL_PATH , flag)
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

    usados = subprocess.check_output(
        "docker ps --format '{{.Ports}}'",
        shell=True,
        text=True
    )

    puertos_usados = set()

    for p in usados.split():
        try:
            if "->" in p and ":" in p:
                host = p.split("->")[0]
                port = host.split(":")[-1]

                if port.isdigit():
                    puertos_usados.add(int(port))
        except Exception:
            continue

    for port in range(7050, 7061):
        if port not in puertos_usados:
            return port

    raise RuntimeError("❌ No hay puertos libres entre 7050 y 7060")

def lanzar_contenedor(nombre,imagen,conf_path,json_data,jobid):

    """Ejecuta docker run dinámicamente con manejo de errores"""
    print(f"⌛ Lanzando contenedor '{nombre}' , Fecha: {get_dia()}-{get_mes()}-{get_anio()}.")

    display_num = random.randint(1, 99)
    vnc_port = 5900 + display_num
    novnc_port = 6080 + display_num

    host_port = get_free_port()
    print(f"🖥 DISPLAY=:{display_num} | VNC interno={vnc_port} | noVNC interno={novnc_port} → host={host_port}")

    data_dict = json.loads(json_data)
    entorno = data_dict.get("entorno")

    print(f"🌎 Entorno detectado: {entorno}")

    host_base = os.getenv("HOST_PROJECT_PATH")

    cred_path = os.path.join(
        host_base,
        "env",
        "desarrollo.env" if entorno == "LOCAL" else "produccion.env"
    )

    #print("📂 Ruta REAL HOST:", cred_path)

    volumes = {
        "mapfre_codigo": "/codigo_mapfre",
    }

    cmd = [
        "docker", "run", "--rm", "-d",
        #"docker", "run", "-d",
        "--network", "orchestrator_network",
        "-p", f"{host_port}:{novnc_port}",
    ]

    # Agregamos todos los volúmenes
    for host_vol, container_path in volumes.items():
        cmd.extend(["-v", f"{host_vol}:{container_path}"])

    # # 👇 Solo agregar si existe // Separa Desarrollo con Producción
    # if volumen_host_codigo:
    #     cmd.extend([
    #         "-v", f"{volumen_host_codigo}:/app/Codigo",
    #     ])

    # Agregamos variables de entorno y demás
    cmd.extend([
        "-v", f"{volumen_host}:/app/Downloads",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{cred_path}:/app/variables.env",
        #"--env-file", "/app/variables.env",
        #"--env-file", cred_path,
        "--name", nombre,
        "-e", f"NOVNC_PORT={novnc_port}",
        "-e", f"VNC_PORT={vnc_port}",
        "-e", f"DISPLAY_NUM={display_num}",
        "-e", f"DATA={json_data}",
        "-e", f"jobid={jobid}",
        "-e", f"puerto={host_port}",
        imagen,
        "supervisord", "-c", conf_path
    ])

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
    #print("📩 Llamado recibido desde n8n:", data)
    print("📩 Llamado recibido desde n8n")

    flag_path = os.path.join(SIGNAL_PATH , "run_solicitud.flag")

    with open(flag_path, "w") as f:
        json.dump(data, f)

    print(f"✅ Flag creado: {flag_path}")
    return jsonify({"status": "ok", "flag": flag_path}), 200

if __name__ == "__main__":
    threading.Thread(target=monitor_signals, daemon=True).start()
    app.run(host="0.0.0.0", port=8080)