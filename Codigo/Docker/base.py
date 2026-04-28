import os
import json
import time
import random
import string
import subprocess
import socket

def generar_job_id():
    return "job_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def monitor_signals(config):
    SIGNAL_PATH = config["SIGNAL_PATH"]
    os.makedirs(SIGNAL_PATH, exist_ok=True)

    while True:
        try:
            for flag in os.listdir(SIGNAL_PATH):
                ruta_flag = os.path.join(SIGNAL_PATH, flag)

                with open(ruta_flag) as f:
                    data = json.load(f)

                os.remove(ruta_flag)

                job_id = generar_job_id()

                config["lanzar_contenedor"](data, job_id)

        except Exception as e:
            print(f"⚠️ Error en monitor_signals: {e}")

        time.sleep(5)

def get_free_port_default(rango_inicio=7000, rango_fin=7100):

    usados = subprocess.check_output(
        "docker ps --format '{{.Ports}}'",
        shell=True,
        text=True
    )

    puertos_docker = set()

    for p in usados.split():
        try:
            if "->" in p and ":" in p:
                host = p.split("->")[0]
                port = host.split(":")[-1]

                if port.isdigit():
                    puertos_docker.add(int(port))
        except:
            continue

    for port in range(rango_inicio, rango_fin + 1):
        if port in puertos_docker:
            continue

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except OSError:
                continue

    raise RuntimeError(f"❌ No hay puertos libres entre {rango_inicio} y {rango_fin}")

def lanzar_contenedor_base(data, jobid, config):

    json_data = json.dumps(data)

    nombre = f"{config['nombre_base']}_{jobid}"
    imagen = config["imagen"]
    conf_path = config["conf_path"]
    volumen_host = config["volumen_host"]
    volumes = config["volumes"]

    print(f"⌛ Lanzando contenedor '{nombre}'")

    display_num = random.randint(1, 99)
    vnc_port = 5900 + display_num
    novnc_port = 6080 + display_num

    get_free_port = config.get("get_free_port")

    if get_free_port:
        host_port = get_free_port()
    else:
        rango = config.get("port_range", (7000, 7100))
        host_port = get_free_port_default(*rango)

    print(f"🖥 DISPLAY=:{display_num} | VNC interno={vnc_port} | noVNC interno={novnc_port} → host={host_port}")

    entorno = data.get("entorno")
    cred_path = "/app/env/desarrollo.env" if entorno == "LOCAL" else "/app/env/produccion.env"

    print(f"🌎 Entorno detectado: {entorno}")
    print(F"📂 Ruta REAL HOST: {cred_path}")

    cmd = [
        "docker", "run", "--rm", "-d",
        "--network", "orchestrator_network",
        "-p", f"{host_port}:{novnc_port}",
    ]

    for host_vol, container_path in volumes.items():
        cmd.extend(["-v", f"{host_vol}:{container_path}"])

    cmd.extend([
        "-v", f"{volumen_host}:/app/Downloads",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "--env-file", cred_path,
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