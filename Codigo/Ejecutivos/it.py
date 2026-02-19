#---------- Orquestador que trabaja revisando Correos ----------
# -*- coding: utf-8 -*-
# -- Imports --
import os
import logging
import sys
import msal
import requests
import threading
import time
import subprocess
import socket
import random
import re
import json
#---- Froms ---
from io import StringIO
from Tiempo.fechas_horas import get_hora_minuto_segundo, get_dia, get_mes, get_anio
from bs4 import BeautifulSoup
#from ssl import ALERT_DESCRIPTION_CERTIFICATE_UNOBTAINABLE

# --- Variables de entorno ---
vP = os.getenv("variablePrueba")
nom_serv = os.getenv("nom_serv")
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
SCOPE = [os.getenv("SCOPE")]
EMAIL_ACCOUNT = os.getenv("remitente")
volumen_host = os.getenv("HOST_DOWNLOADS_PATH")
#-----MS Graph API URL para obtener correos-------
GRAPH_API_URL = 'https://graph.microsoft.com/v1.0/users/{}/messages'.format(EMAIL_ACCOUNT)
#---- Path para señales ----
SIGNAL_PATH = "/app/sync"

def obtener_token():
    app = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET
    )
    
    result = app.acquire_token_for_client(scopes=SCOPE)
    
    if 'access_token' in result:
        return result['access_token']
    else:
        print("Error al obtener el token:", result.get("error"), result.get("error_description"))
        sys.exit(1)

def extraer_codigo_del_mensaje(cuerpo_texto):
    # Buscar un número de 6 dígitos
    match = re.search(r"\b(\d{6})\b", cuerpo_texto)

    if match:
        codigo = match.group(1)
        return codigo
    else:
        return None

def marcar_como_leido(message_id, token):
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
    }
    payload = {
        "isRead": True
    }
    
    response = requests.patch(f"{GRAPH_API_URL}/{message_id}", headers=headers, json=payload)
    
    if response.status_code == 200:
        print(f"🟢 Correo marcado como leído.")
    else:
        print(f"🛑 Error al marcar el correo como leído: {response.status_code}, {response.text}")

def extraer_codigo_de_cuerpo(cuerpo_html):
    
    #Extrae el código (por lo general 6 dígitos) buscando primero la frase contextual ("código de acceso", "código de verificación", ...)y luego el primer número que aparezca después de esa frase.
    if not cuerpo_html:
        return None

    soup = BeautifulSoup(cuerpo_html, "html.parser")

    # Texto limpio (un solo string) para búsquedas globales
    full_text = soup.get_text(separator=" ")
    full_text = re.sub(r'\s+', ' ', full_text).strip()

    # Frases que suelen indicar el código
    frases = [
        r'c[oó]digo\s+de\s+acceso',
        r'c[oó]digo\s+de\s+verificaci[oó]n',
        r'c[oó]digo\s+de\s+verificaci[oó]n',
        r'c[oó]digo\s+de\s+verificaci[oó]n',
        r'c[oó]digo'
    ]

    # Buscar la posición de la primera frase encontrada
    frase_idx = None
    for f in frases:
        m = re.search(f, full_text, flags=re.I)
        if m:
            if frase_idx is None or m.start() < frase_idx:
                frase_idx = m.start()

    #buscar todas las ocurrencias de 4 a 8 dígitos (por si varía)
    matches = list(re.finditer(r'\b\d{4,8}\b', full_text))

    if not matches:
        return None

    # Si encontramos la frase, devolvemos la primera coincidencia que ocurra
    # después de ella (preferente)
    if frase_idx is not None:
        for mt in matches:
            if mt.start() >= frase_idx:
                return mt.group()
        # Si no hay coincidencias *después* de la frase, devolver la más cercana
        closest = min(matches, key=lambda m: abs(m.start() - frase_idx))
        return closest.group()

    # Si no encontramos la frase, preferimos un match de 6 dígitos
    six = [m for m in matches if len(m.group()) == 6]
    if six:
        return six[0].group()

    # Fallback: devolver la primera coincidencia en el texto
    return matches[0].group()

def extraer_codigo_rimac(cuerpo_html):
    if not cuerpo_html:
        return None

    # 1️⃣ Intentar detectar JSON dentro del html
    try:
        json_texts = re.findall(r'\{.*?\}', cuerpo_html, flags=re.DOTALL)
        for block in json_texts:
            try:
                data = json.loads(block)
                # Si existe key "code", devolverlo
                if "code" in data and isinstance(data["code"], str):
                    return data["code"]
            except:
                pass
    except:
        pass

    # 2️⃣ Parsear HTML y buscar span con clase string
    soup = BeautifulSoup(cuerpo_html, "html.parser")

    span = soup.find("span", class_="string")
    if span:
        # El código viene como "R123456"
        codigo = span.get_text(strip=True)
        if codigo and len(codigo) >= 6:
            return codigo

    # 3️⃣ Extraer cualquier bloque tipo "R123456"
    match = re.search(r'\bR\d{6}\b', cuerpo_html)
    if match:
        return match.group()

    # 4️⃣ Último fallback: cualquier número de 6 dígitos
    match = re.search(r'\b\d{6}\b', cuerpo_html)
    if match:
        return match.group()

    return None

def revisar_correo():
    
    token = obtener_token()
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
    }
    
    response = requests.get(GRAPH_API_URL, headers=headers, params={'$filter': "isRead eq false"})
   
    if response.status_code == 200:
        messages = response.json().get('value', [])
    
        for message in messages:

            log_buffer = StringIO()
            logging.basicConfig(
                level=logging.INFO,
                format="%(message)s",
                handlers=[logging.StreamHandler(log_buffer)],
                force=True
            )

            asunto = message.get('subject')
            message_id = message.get('id')  
            print(f"Asunto del correo: {asunto}")
            cuerpo = message.get('body', {}).get('content', '')

            try:

                if asunto.startswith('RB15'):
                    SIGNAL_FILE = "/app/sync/run_solicitud.flag"
                    with open(SIGNAL_FILE, "w") as f:
                        f.write(f"{asunto}|{token}|{message_id}")
                elif asunto.startswith('VC_'):
                    SIGNAL_FILE = "/app/sync/run_verificar.flag"
                    with open(SIGNAL_FILE, "w") as f:
                        f.write(f"{asunto}|{token}|{message_id}")
                elif asunto.startswith('Código de verificación MAPFRE'):

                    # codigo = extraer_codigo_de_cuerpo(cuerpo)
                    # print(f"Enviando el código {codigo} al API Local de Mapfre")
                    # requests.post(f"http://{nom_serv}:5000/recibir-codigo",
                    # json={
                    #     "codigo": codigo
                    # })

                    codigo = extraer_codigo_de_cuerpo(cuerpo)
                    print(f"Enviando codigo '{codigo}' para que ingrese a Mapfre.")
                    with open("/codigo_mapfre/codigo.txt", "w") as f:
                        f.write(codigo)

                elif asunto.startswith('Envio de Codigo'):

                    codigo_rimac_WC = extraer_codigo_rimac(cuerpo)
                    print(f"Enviando codigo '{codigo_rimac_WC}' para que ingrese a Web Corredores.")
                    with open("/codigo_rimac_Web/codigo.txt", "w") as f:
                        f.write(codigo_rimac_WC)
                # else:
                #     pass
                #     #print(f"Asunto no reconocido: {asunto}")

            finally :
                marcar_como_leido(message_id,token)
                print("---------------------------------")
    
    else:
        print(f"❌ Error al obtener correos: {response.status_code}, {response.text}")

def lanzar_contenedor(nombre,imagen,conf_path,asunto,token,message_id):

    print(f"⌛ Lanzando contenedor '{nombre}' , Fecha: {get_dia()}-{get_mes()}-{get_anio()} a las {get_hora_minuto_segundo()}.")

    # Asignar display y puertos internos únicos
    display_num = random.randint(1, 99)
    vnc_port = 5900 + display_num
    novnc_port = 6080 + display_num #6108

    # Obtener un puerto libre del host para mapear el noVNC
    host_port = get_free_port()
    print(f"🖥 DISPLAY=:{display_num} | VNC interno={vnc_port} | noVNC interno={novnc_port} → host={host_port}")

    cmd = [
        "docker", "run", "--rm", "-d",
        #"docker", "run", "-d",
        "--network", "orchestrator_network" ,               # Nos conectamos a una red en docker (Antes tenemos que crearla sea por comando o en docker compose)
        "-p", f"{host_port}:{novnc_port}",                  # host:container
        "-v", f"mapfre_codigo:/codigo_mapfre",               # volumen para pasar codigo de mapfre (Mapfre)
        "-v", "pacifico_codigo:/codigo",                    # volumen para pasar codigo compartido (Pacifico)
        "-v", "rimac_web_corredores:/codigo_rimac_WC",      # volumen para pasar codigo compartido (Rimac Web Corredores)
        "-v", "rimac_SAS:/codigo_rimac_SAS",                # volumen para pasar codigo compartido (Rimac SAS)
        "-v", f"{volumen_host}:/app/Downloads", 
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "--env-file", "/app/variables.env",
        "--name", nombre,
        "-e", f"NOVNC_PORT={novnc_port}",
        "-e", f"VNC_PORT={vnc_port}",
        "-e", f"DISPLAY_NUM={display_num}",
        "-e", f"asunto={asunto}",
        "-e", f"token={token}",
        "-e", f"message_id={message_id}",
        "-e", f"CONT_NAME={nombre}",
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
        print("---------------------------------")

def monitor_signals():

    #Escucha señales que indiquen qué contenedor lanzar"""
    while True:
        for flag in os.listdir(SIGNAL_PATH):
            ruta_flag = os.path.join(SIGNAL_PATH, flag)

            # Leer asunto y token del archivo flag
            with open(ruta_flag) as f:
                contenido = f.read().strip()
                try:
                    asunto_flag, token_flag, message_id_flag = contenido.split("|")
                except ValueError:
                    print(f"⚠️ Formato inesperado en {flag}: {contenido}")
                    continue

            if flag == "run_solicitud.flag":
                os.remove(ruta_flag)
                lanzar_contenedor(
                    f"conIncRen_{get_hora_minuto_segundo()}",
                    #"inclusiones_renovaciones:latest",
                    "inclusiones:latest",
                    "/app/supervisord.conf",
                    f"{asunto_flag}",
                    f"{token_flag}",
                    f"{message_id_flag}"
                )
            elif flag == "run_verificar.flag":
                os.remove(ruta_flag)
                lanzar_contenedor(
                    f"vfCuotas_{get_hora_minuto_segundo()}",
                    "automatizacion:latest",
                    "/app/supervisord/supervisord_vf_cuotas.conf",
                    f"{asunto_flag}",
                    f"{token_flag}",
                    f"{message_id_flag}"
                )
        time.sleep(5)

def main_loop():
    
    #Bucle principal: revisa correos y crea flags"""
    while True:
        try:
            revisar_correo()
        except Exception as e:
            print(f"Error revisando correo: {e}")
        time.sleep(5)

def get_free_port():
    
    #Devuelve un puerto libre, seguro y de 4 dígitos (rango 1024–9999),evitando colisiones con otros procesos o reservas del sistema.

    while True:
        port = random.randint(1024, 9999)  
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Probamos a enlazar para comprobar que está libre
                s.bind(('', port))
                return port
            except OSError:
                # Si el puerto está ocupado o reservado, intentamos otro
                continue

if __name__ == "__main__":
    hilo = threading.Thread(target=monitor_signals, daemon=True)
    hilo.start()
    main_loop()