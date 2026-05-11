#-- Imports --
import time
import os
import threading
#-- Froms --
from Ejecutivos.metodos import extraer_codigo_rimac
from flask import Flask, jsonify,request
from threading import Lock
from MicrosoftGraph.graph_client import GraphMailClient

codigo_actualRimacWeb = None
lock = Lock()

# --- Variables de entorno ---
API_KEY = os.getenv("API_KEY_RIMAC_WEB")

cliente = GraphMailClient(
    tenant_id=os.getenv("TENANT_ID"),
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    scope=os.getenv("SCOPE"),
    email_account=os.getenv("email_leer")
)

def revisar_correo_ejecutivo():

    global codigo_actualRimacWeb

    mensajes, token = cliente.obtener_correos_no_leidos()

    for message in mensajes:

        asunto = message.get("subject")
        cuerpo = message.get("body", {}).get("content", "")
        message_id = message.get("id")

        if asunto.startswith("Envio de Codigo"):

            codigo = extraer_codigo_rimac(cuerpo)

            if codigo:

                with lock:
                    codigo_actualRimacWeb = codigo
                    print(f"📩 Código de Rimac Web guardado: {codigo}")

                cliente.marcar_como_leido(message_id, token)

def main_loop():
    
    while True:
        try:
            revisar_correo_ejecutivo()
        except Exception as e:
            print(f"Error revisando correo: {e}")
        time.sleep(5)

app = Flask(__name__)

# 🌐 ENDPOINT FLASK
@app.route("/codigoRimacWeb", methods=["GET"])
def obtener_codigo():
    global codigo_actualRimacWeb

    # 🔐 validar API KEY
    api_key_cliente = request.headers.get("x-api-key")

    if api_key_cliente != API_KEY:
        print("⛔ Acceso no autorizado")
        return jsonify({"error": "unauthorized"}), 401

    with lock:
        if not codigo_actualRimacWeb:
            return jsonify({"status": "sin_codigo"}), 404

        codigo = codigo_actualRimacWeb
        codigo_actualRimacWeb = None

        print(f"✅ Código de Rimac Web entregado por API y eliminado: {codigo}")

    return jsonify({"codigo": codigo})

if __name__ == "__main__":
    
    # 🔥 correr revisión de correos en segundo plano
    threading.Thread(target=main_loop, daemon=True).start()

    # 🔥 levantar API Flask
    app.run(host="0.0.0.0", port=6060)