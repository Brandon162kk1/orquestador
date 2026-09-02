import os
import time
import json
import random
import string
import subprocess
import socket
import redis

# 🔴 Redis del Orquestador
r = redis.Redis(
    host="redis",
    port=6379,
    decode_responses=True,
    socket_timeout=None,
    socket_connect_timeout=5,
    health_check_interval=30
)

def generar_job_id():
    return "job_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))

def get_free_port_default(rango_inicio=7000, rango_fin=7100):
    try:
        usados = subprocess.check_output(
            "docker ps --format '{{.Ports}}'",
            shell=True,
            text=True
        )
    except Exception:
        usados = ""

    puertos_docker = set()

    for p in usados.split():
        try:
            if "->" in p and ":" in p:
                host = p.split("->")[0]
                port = host.split(":")[-1]

                if port.isdigit():
                    puertos_docker.add(int(port))
        except Exception:
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

# ==================== WORKERS PERSISTENTES ====================

def is_container_running(container_name):
    try:
        res = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True
        )
        return res.returncode == 0 and res.stdout.strip().lower() == "true"
    except Exception:
        return False

def container_exists(container_name):
    try:
        res = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True
        )
        return res.returncode == 0
    except Exception:
        return False

def get_worker_status(worker_id):
    try:
        status = r.get(f"worker:{worker_id}:status")
        heartbeat = r.get(f"worker:{worker_id}:heartbeat")
        info = r.hgetall(f"worker:{worker_id}:info")
        running = is_container_running(worker_id)
        return {
            "worker_id": worker_id,
            "running": running,
            "status": status or ("DEAD" if not running else "UNKNOWN"),
            "heartbeat": heartbeat is not None,
            "info": info
        }
    except Exception as e:
        print(f"⚠️ Error obteniendo estado de {worker_id}: {e}")
        return {"worker_id": worker_id, "running": False, "status": "ERROR", "heartbeat": False, "info": {}}

def lanzar_worker_persistente(worker_id, config, host_port, worker_idx=1):
    imagen = config["imagen"]
    conf_path = config["conf_path"]
    volumen_host = config.get("volumen_host") or os.getenv("HOST_DOWNLOADS_PATH")
    browser_data_host = config.get("browser_data_host") or f"{volumen_host}/browser_data_{config['nombre_base']}"

    # Asignación determinista de puertos internos y display según worker_idx
    display_num = 50 + worker_idx
    vnc_port = 5900 + display_num
    novnc_port = 6080 + display_num

    print(f"🚀 Lanzando Worker Persistente '{worker_id}' | Puerto Host={host_port} | DISPLAY=:{display_num}")

    cred_path = os.getenv("ENV_FILE")

    # Si existe un contenedor previo detenido o colgado, limpiarlo
    if container_exists(worker_id):
        print(f"🧹 Limpiando contenedor previo '{worker_id}'...")
        subprocess.run(["docker", "rm", "-f", worker_id], capture_output=True, text=True)

    cmd = [
        "docker", "run", "-d",
        "--restart", "unless-stopped",
        "--network", "orchestrator_network",
        "-p", f"{host_port}:{novnc_port}",
        "-v", f"{volumen_host}:/app/Downloads",
        "-v", f"{browser_data_host}:/app/browser_data",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "--env-file", cred_path,
        "--name", worker_id,
        "-e", f"WORKER_ID={worker_id}",
        "-e", f"QUEUE_NAME={config.get('queue_name', 'cola_cotizador')}",
        "-e", f"NOVNC_PORT={novnc_port}",
        "-e", f"VNC_PORT={vnc_port}",
        "-e", f"DISPLAY_NUM={display_num}",
        "-e", f"puerto={host_port}",
        "-e", "REDIS_HOST=redis",
        "-e", "REDIS_PORT=6379",
        imagen,
        "supervisord", "-c", conf_path
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Worker {worker_id} lanzado correctamente: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al lanzar worker {worker_id}: {e.stderr.strip()}")
    finally:
        print("------------------------------------------------------------------")

def ensure_workers(config):
    max_workers = config.get("max_workers", 1)
    nombre_base = config.get("nombre_base")
    rango_inicio, _ = config.get("port_range")
    rango_inicio = int(rango_inicio)

    for idx in range(1, max_workers + 1):
        worker_id = nombre_base if max_workers == 1 else f"{nombre_base}_{idx:02d}"
        host_port = rango_inicio + (idx - 1)

        running = is_container_running(worker_id)
        hb_active = r.get(f"worker:{worker_id}:heartbeat") is not None

        if not running:
            print(f"🔍 Worker '{worker_id}' no está corriendo. Iniciando...")
            lanzar_worker_persistente(worker_id, config, host_port, worker_idx=idx)
        else:
            # Si corre pero no tiene heartbeat y ya pasó tiempo de gracia, verificar
            status = r.get(f"worker:{worker_id}:status")
            if not hb_active and status not in ("STARTING", None):
                print(f"⚠️ Worker '{worker_id}' está corriendo pero su Heartbeat expiró. Reiniciando...")
                lanzar_worker_persistente(worker_id, config, host_port, worker_idx=idx)

def monitor_workers(config, interval=15):

    cola = config.get("queue_name", "cola_cotizador")
    print(f"👁️ Administrador de Workers iniciado para cola: {cola} (intervalo: {interval}s)")

    # Asegurar workers al arrancar
    ensure_workers(config)

    while True:
        try:
            time.sleep(interval)
            ensure_workers(config)
        except Exception as e:
            print(f"⚠️ Error en monitor_workers: {e}")

# ==================== MODO LEGACY / COMPATIBILIDAD ====================

def lanzar_contenedor_base(data, jobid, config):
    json_data = json.dumps(data)
    nombre = f"{config['nombre_base']}_{jobid}"
    imagen = config["imagen"]
    conf_path = config["conf_path"]
    volumen_host = config["volumen_host"]

    print(f"⌛ Lanzando contenedor efímero '{nombre}'")

    display_num = random.randint(1, 99)
    vnc_port = 5900 + display_num
    novnc_port = 6080 + display_num

    get_free_port = config.get("get_free_port")
    if get_free_port:
        host_port = get_free_port()
    else:
        rango = config.get("port_range", (7000, 7100))
        host_port = get_free_port_default(*rango)

    print(f"🖥 DISPLAY=:{display_num} | VNC={vnc_port} | noVNC={novnc_port} → host={host_port}")

    cred_path = os.getenv("ENV_FILE")

    cmd = [
        "docker", "run", "--rm", "-d",
        "--network", "orchestrator_network",
        "-p", f"{host_port}:{novnc_port}",
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
    ]

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"🚀 Contenedor lanzado correctamente: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error al lanzar {nombre}: {e.stderr.strip()}")
    finally:
        print("------------------------------------------------------------------")

def monitor_queue(config):
    cola = config["queue_name"]
    print(f"👂 Escuchando cola Redis (modo efímero): {cola}")

    while True:
        try:
            resultado = r.brpop(cola, timeout=0)
            if resultado:
                _, job_json = resultado
                job = json.loads(job_json)
                job_id = job["job_id"]
                data = job["payload"]
                print(f"📦 Job recibido: {job_id}")
                config["lanzar_contenedor"](data, job_id)
        except Exception as e:
            print(f"⚠️ Error monitor_queue: {e}")