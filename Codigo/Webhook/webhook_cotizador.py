# ---------- Orquestador con Redis Queue & Workers Paralelos (Rimac + Positiva) ----------
import os
import json
import threading
import redis

from flask import Flask, request, jsonify
from Docker.base import (
    monitor_workers,
    monitor_queue,
    ensure_workers,
    lanzar_contenedor_base,
    generar_job_id,
    get_worker_status
)

app = Flask(__name__)

# 🔴 Redis
r = redis.Redis(
    host="redis",
    port=6379,
    decode_responses=True,
    socket_timeout=None,
    socket_connect_timeout=5,
    health_check_interval=30
)

# ⚙️ Configuración de Workers
host_downloads = os.getenv("HOST_DOWNLOADS_PATH")
browser_data_path = os.getenv("HOST_BROWSER_DATA_PATH", f"{host_downloads}/browser_data_positiva")

# 1️⃣ Configuración Rímac (Contenedor Efímero / On-Demand)
config_rimac = {
    "queue_name": "cola_cotizador_rimac",
    "imagen": "cotizador:latest",
    "nombre_base": "cotizador",
    "conf_path": "/app/supervisord.conf",
    "volumen_host": host_downloads,
    "port_range": (7062, 7071)
}
# Launcher para Rímac
config_rimac["lanzar_contenedor"] = (
    lambda data, jobid: lanzar_contenedor_base(data, jobid, config_rimac)
)

# 2️⃣ Configuración Positiva (Worker Persistente)
config_positiva = {
    "queue_name": "cola_cotizador_positiva",
    "imagen": "cotizacion_positiva:latest",
    "nombre_base": "cotizador_positiva",
    "conf_path": "/etc/supervisor/conf.d/supervisord.conf",
    "volumen_host": host_downloads,
    "browser_data_host": browser_data_path,
    "port_range": (8086, 8086),
    "max_workers": 1,
    "persistent": True
}

@app.route("/notify", methods=["POST"])
def notify():
    data = request.get_json() or {}

    print("📩 Llamado recibido desde n8n")

    job_id = generar_job_id()
    job = {
        "job_id": job_id,
        "payload": data
    }
    job_json = json.dumps(job)

    # 🔴 1. Enviar a cola de Rímac (Lanzará contenedor efímero)
    r.lpush(config_rimac["queue_name"], job_json)
    print(f"📦 Job {job_id} enviado a Rímac (Cola: {config_rimac['queue_name']})")

    # 🔴 2. Enviar a cola de Positiva (Worker persistente)
    r.lpush(config_positiva["queue_name"], job_json)
    print(f"📦 Job {job_id} enviado a Positiva (Cola: {config_positiva['queue_name']})")

    # 🚀 Asegurar que el Worker persistente de Positiva esté disponible
    try:
        ensure_workers(config_positiva)
    except Exception as e:
        print(f"⚠️ Error verificando worker Positiva en /notify: {e}")

    return jsonify({
        "status": "queued",
        "job_id": job_id,
        "targets": ["rimac", "positiva"]
    }), 200

@app.route("/status", methods=["GET"])
def status():
    """Endpoint informativo para consultar estado de colas y workers"""
    # Estado Positiva
    nombre_base = config_positiva.get("nombre_base")
    max_workers = config_positiva.get("max_workers", 1)
    workers_positiva = []
    for idx in range(1, max_workers + 1):
        worker_id = nombre_base if max_workers == 1 else f"{nombre_base}_{idx:02d}"
        workers_positiva.append(get_worker_status(worker_id))

    return jsonify({
        "rimac": {
            "queue": config_rimac["queue_name"],
            "pending_jobs": r.llen(config_rimac["queue_name"])
        },
        "positiva": {
            "queue": config_positiva["queue_name"],
            "pending_jobs": r.llen(config_positiva["queue_name"]),
            "workers": workers_positiva
        }
    }), 200

if __name__ == "__main__":
    # 🧵 Hilo 1: Escucha cola de Rímac y crea contenedores efímeros
    threading.Thread(
        target=monitor_queue,
        args=(config_rimac,),
        daemon=True
    ).start()

    # 🧵 Hilo 2: Monitor de Positiva (mantiene worker persistente)
    threading.Thread(
        target=monitor_workers,
        args=(config_positiva,),
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=9090
    )