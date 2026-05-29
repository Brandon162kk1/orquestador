#---------- Orquestador que trabaja revisando Correos ----------
# -*- coding: utf-8 -*-
# -- Imports --
import os
import threading
import time
#---- Froms ---
from flask import Flask, jsonify,request
from threading import Lock
from Ejecutivos.metodos import extraer_codigo_de_cuerpo
from MicrosoftGraph.graph_client import GraphMailClient

codigo_actualMapfre = None
codigo_actualPositiva = None
lock = Lock()

# --- Variables de entorno ---
API_KEY_MAPFRE = os.getenv("API_KEY_MAPFRE")
API_KEY_POSITIVA = os.getenv("API_KEY_POSITIVA")

cliente = GraphMailClient(
    tenant_id=os.getenv("TENANT_ID"),
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    scope=os.getenv("SCOPE"),
    email_account=os.getenv("remitente")
)

def revisar_correo():
    
    global codigo_actualMapfre
    global codigo_actualPositiva

    mensajes, token = cliente.obtener_correos_no_leidos()

    for message in mensajes:

        asunto = message.get("subject")
        print(f"Asunto del correo: {asunto}")
        cuerpo = message.get("body", {}).get("content", "")
        message_id = message.get("id")

        try:

            if asunto.startswith("Código de verificación MAPFRE"):

                codigoMapfre = extraer_codigo_de_cuerpo(cuerpo)

                if codigoMapfre:
                    with lock:
                        codigo_actualMapfre = codigoMapfre
                        print(f"📩 Código de Mapfre guardado: {codigoMapfre}")

            if asunto.startswith("Portal Comercial - Código de verificación"):

                codigoPositiva = extraer_codigo_de_cuerpo(cuerpo)

                if codigoPositiva:
                    with lock:
                        codigo_actualPositiva = codigoPositiva
                        print(f"📩 Código de Positiva guardado: {codigoPositiva}")

            # elif asunto.startswith("Envio de Codigo"):
            #     codigo_rimac_WC = extraer_codigo_de_cuerpo(cuerpo)
            #     print(f"Enviando codigo '{codigo_rimac_WC}' para que ingrese a Web Corredores.")
            #     with open("/codigo_rimac_WC/codigo.txt", "w") as f:
            #         f.write(codigo_rimac_WC)
            else:
                pass

        finally:
            cliente.marcar_como_leido(message_id, token)
            print("---------------------------------")

def main_loop():
    
    while True:
        try:
            revisar_correo()
        except Exception as e:
            print(f"Error revisando correo: {e}")
        time.sleep(5)

app = Flask(__name__)

# 🌐 ENDPOINT FLASK
@app.route("/codigoMapfre", methods=["GET"])
def obtener_codigo():
    global codigo_actualMapfre

    # 🔐 validar API KEY
    api_key_cliente = request.headers.get("x-api-key")

    if api_key_cliente != API_KEY_MAPFRE:
        print("⛔ Acceso no autorizado")
        return jsonify({"error": "unauthorized"}), 401

    with lock:
        if not codigo_actualMapfre:
            return jsonify({"status": "sin_codigo"}), 404

        codigo = codigo_actualMapfre
        codigo_actualMapfre = None

        print(f"✅ Código de Mapfre entregado por API y eliminado: {codigo}")

    return jsonify({"codigo": codigo})

@app.route("/codigoPositiva", methods=["GET"])
def obtener_codigo_positiva():

    global codigo_actualPositiva

    # 🔐 validar API KEY
    api_key_cliente = request.headers.get("x-api-key")

    if api_key_cliente != API_KEY_POSITIVA:
        print("⛔ Acceso no autorizado")
        return jsonify({"error": "unauthorized"}), 401

    with lock:
        if not codigo_actualPositiva:
            return jsonify({"status": "sin_codigo"}), 404

        codigo = codigo_actualPositiva
        codigo_actualPositiva = None

        print(f"✅ Código de Positiva entregado por API y eliminado: {codigo}")

    return jsonify({"codigo": codigo})

if __name__ == "__main__":

    # 🔥 correr revisión de correos en segundo plano
    threading.Thread(target=main_loop, daemon=True).start()

    # 🔥 levantar API Flask
    app.run(host="0.0.0.0", port=8080)