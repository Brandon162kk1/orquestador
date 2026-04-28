#---------- Orquestador que trabaja con Webhooks ----------
import os
import threading
import json

from flask import Flask, request, jsonify
from Docker.base import monitor_signals, lanzar_contenedor_base,generar_job_id

app = Flask(__name__)

config = {
    "SIGNAL_PATH": "/app/sync/webCorredor",
    "imagen": "web_corredor:latest",
    "nombre_base": "conWebIncRen",
    "conf_path": "/app/supervisord.conf",
    "volumen_host": os.getenv("HOST_DOWNLOADS_PATH"),
    "volumes": {
        "mapfre_codigo": "/codigo_mapfre"
    },
    "port_range": (7050, 7061)
}

# 🔗 Inyectamos la función de lanzamiento usando el core
config["lanzar_contenedor"] = lambda data, jobid: lanzar_contenedor_base(data, jobid, config)

@app.route("/notify", methods=["POST"])
def notify():

    """Recibe la llamada HTTP desde n8n y crea el flag correspondiente."""
    data = request.get_json()
    print("📩 Llamado recibido desde n8n:", data)

    flag_name = f"run_solicitud_{generar_job_id()}.flag"

    flag_path = os.path.join(config["SIGNAL_PATH"], flag_name)

    with open(flag_path, "w") as f:
        json.dump(data, f)

    print(f"✅ Flag creado: {flag_path}")
    return jsonify({"status": "ok", "flag": flag_path}), 200

if __name__ == "__main__":

    threading.Thread(
        target=monitor_signals,
        args=(config,),
        daemon=True
    ).start()

    app.run(host="0.0.0.0", port=8080)