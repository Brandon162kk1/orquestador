import os
import json
import threading
import redis

from flask import Flask, request, jsonify
from Docker.base import monitor_queue,lanzar_contenedor_base,generar_job_id

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

config = {
    "queue_name": "cola_webcorredor",
    "imagen": "web_corredor:latest",
    "nombre_base": "conWebIncRen",
    "conf_path": "/app/supervisord.conf",
    "volumen_host": os.getenv("HOST_DOWNLOADS_PATH"),
    "port_range": (7050, 7061)
}

# 🔗 Inyectamos launcher reutilizable
config["lanzar_contenedor"] = (
    lambda data, jobid:
    lanzar_contenedor_base(data, jobid, config)
)

@app.route("/notify", methods=["POST"])
def notify():

    data = request.get_json()

    print("📩 Llamado recibido desde n8n")

    job = {
        "job_id": generar_job_id(),
        "payload": data
    }

    # 🔴 Enviar job a Redis Queue
    r.lpush(
        config["queue_name"],
        json.dumps(job)
    )

    print(f"✅ Job enviado a cola: {job['job_id']}")

    return jsonify({
        "status": "queued",
        "job_id": job["job_id"]
    }), 200

if __name__ == "__main__":

    # 🔴 Consumidor de cola Redis
    threading.Thread(
        target=monitor_queue,
        args=(config,),
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=8080
    )