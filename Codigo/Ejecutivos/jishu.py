#-- Imports --
import time
import os
import threading
#-- Froms --
from Ejecutivos.metodos import extraer_codigo_del_mensaje
from flask import Flask, jsonify,request
from threading import Lock
from MicrosoftGraph.graph_client import GraphMailClient

codigo_actualRimacSAS = None
lock = Lock()

# --- Variables de entorno ---
API_KEY = os.getenv("API_KEY_RIMAC_SAS")

cliente = GraphMailClient(
    tenant_id=os.getenv("TENANT_ID_JISHU"),
    client_id=os.getenv("CLIENT_ID_JISHU"),
    client_secret=os.getenv("CLIENT_SECRET_JISHU"),
    scope=os.getenv("SCOPE"),
    email_account=os.getenv("JISHU")
)

def revisar_correo_jishu():

    global codigo_actualRimacSAS

    mensajes, token = cliente.obtener_correos_no_leidos()

    for message in mensajes:

        asunto = message.get("subject")
        print(f"Asunto del correo: {asunto}")
        cuerpo = message.get("body", {}).get("content", "")
        message_id = message.get("id")

        try:
            if asunto and asunto.startswith('Código de Autenticación - Inicio sesión SAS'):
                codigoRimacSAS = extraer_codigo_del_mensaje(cuerpo)
                #print(f"Enviando codigo '{codigo}' para que ingrese a Rimac - SAS.")
                # Esto monta en un volumen compart
                # with open("/codigo_rimac_SAS/codigo.txt", "w") as f:
                #     f.write(codigo)
                if codigoRimacSAS:
                    with lock:
                        codigo_actualRimacSAS = codigoRimacSAS
                        print(f"📩 Código de Rimac SAS guardado: {codigoRimacSAS}")
            else:
                pass
        finally:
            cliente.marcar_como_leido(message_id, token)
            print("---------------------------------")

def main_loop():
    
    while True:
        try:
            revisar_correo_jishu()
        except Exception as e:
            print(f"Error revisando correo: {e}")
        time.sleep(5)

app = Flask(__name__)

@app.route("/codigoRimacSAS", methods=["GET"])
def obtener_codigo():
    global codigo_actualRimacSAS

    # 🔐 validar API KEY
    api_key_cliente = request.headers.get("x-api-key")

    if api_key_cliente != API_KEY:
        print("⛔ Acceso no autorizado")
        return jsonify({"error": "unauthorized"}), 401


    with lock:
        if not codigo_actualRimacSAS:
            return jsonify({"status": "sin_codigo"}), 404

        codigo = codigo_actualRimacSAS
        codigo_actualRimacSAS = None

        print(f"✅ Código entregado por API y eliminado: {codigo}")

    return jsonify({"codigo": codigo})

if __name__ == "__main__":

    # 🔥 correr revisión de correos en segundo plano
    threading.Thread(target=main_loop, daemon=True).start()

    # 🔥 levantar API Flask
    app.run(host="0.0.0.0", port=8080)