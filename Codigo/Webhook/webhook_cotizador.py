#---------- Orquestador que trabaja con Webhooks ----------
import os
import threading
import json

from flask import Flask, request, jsonify
from Docker.base import monitor_signals, lanzar_contenedor_base,generar_job_id

app = Flask(__name__)

# 🔧 Configuración específica del cotizador
config = {
    "SIGNAL_PATH": "/app/sync/cotizador",
    "imagen": "cotizador:latest",
    "nombre_base": "cotizador",
    "conf_path": "/app/supervisord.conf",
    "volumen_host": os.getenv("HOST_DOWNLOADS_PATH"),
    "volumes": {
        "rimac_SAS": "/codigo_rimac_SAS"
    },
    "port_range": (7062, 7071)
}

# 🔗 Inyectamos la función de lanzamiento usando el core
config["lanzar_contenedor"] = lambda data, jobid: lanzar_contenedor_base(data, jobid, config)

@app.route("/notify", methods=["POST"])
def notify():

    """Recibe la llamada HTTP desde n8n y crea el flag correspondiente."""
    data = request.get_json()
    print("📩 Llamado recibido desde n8n:", data)

    flag_name = f"cotizar_{generar_job_id()}.flag"

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

    app.run(host="0.0.0.0", port=9090)
