# -*- coding: utf-8 -*-
# -- Froms ---
# -- Imports --
import os
import logging
import requests
import json
import base64
import glob
from Tiempo.fechas_horas import get_timestamp

# --- Variables de Entorno ---
remitente = os.getenv("remitente")
client_id = os.getenv("client_id")
client_secret = os.getenv("client_secret")
tenant_id = os.getenv("TENANT_ID")
SCOPE = os.getenv("SCOPE")

# Convertir listas de correos a objetos Graph
def formato_correos(lista):
    return [{"emailAddress": {"address": correo}} for correo in lista]

def enviarCorreoIT(destinatarios_to,destinatarios_cc,asunto, mensaje, ruta_imagen,lista_adjuntos=None):
    token_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
 
    if lista_adjuntos is None:
        lista_adjuntos = []
    
    # Paso 1: Obtener el token
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": SCOPE
    }
    token_response = requests.post(token_endpoint, data=token_data)
    access_token = token_response.json().get("access_token")
 
    if not access_token:
        logging.info("❌ No se pudo obtener el token.")
        return
 
    # Paso 2: Construir el cuerpo del mensaje
    email_body = {
        "message": {
            "subject": asunto,
            "body": {
                "contentType": "HTML",
                "content": f"""
        <html>
        <body>
        {mensaje}
        </body>
        </html>
                """
            },
            "toRecipients": formato_correos(destinatarios_to),
            "ccRecipients": formato_correos(destinatarios_cc),
        },
        "saveToSentItems": "true"
    }
 
    attachments = []

    for archivo_path in lista_adjuntos:
        if os.path.exists(archivo_path):
            with open(archivo_path, "rb") as f:
                contenido_base64 = base64.b64encode(f.read()).decode('utf-8')
                attachments.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": os.path.basename(archivo_path),
                    "contentBytes": contenido_base64,
                    "contentType": "application/octet-stream"
                })
        else:
            logging.info(f"\n⚠️ Archivo no encontrado: {archivo_path}")

    if ruta_imagen and os.path.exists(ruta_imagen):
        with open(ruta_imagen, "rb") as f:
            contenido_base64 = base64.b64encode(f.read()).decode('utf-8')
            attachments.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": os.path.basename(ruta_imagen),
                "contentBytes": contenido_base64,
                "contentType": "image/png"
            })
 
    # Solo agregar attachments si existen
    if attachments:
         email_body["message"]["attachments"] = attachments

    # Paso 3: Enviar el correo con Microsoft Graph
    url_envio = f"https://graph.microsoft.com/v1.0/users/{remitente}/sendMail"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    try:

        response = requests.post(
            url_envio,
            headers=headers,
            data=json.dumps(email_body),
            timeout=30
        )
        if response.status_code == 202:
            logging.info(f"📧 Correo enviado correctamente a {destinatarios_to} y con copia a {destinatarios_cc}.")
        else:
            logging.info("❌ Error al enviar correo:", response.status_code, response.text)
    except requests.exceptions.Timeout:
        logging.info("⏰ El envío del correo tardó demasiado y fue cancelado (timeout).")
    except Exception as e:
        logging.info(f"❌ Error inesperado al enviar el correo: {e}")

def enviarCaptcha(para, copia, puerto, cia, imagen):
    url = f"http://jishucloud.redirectme.net:{puerto}"

    asunto = f"🧩 Resolver Captcha en {cia}"
    mensaje = f"""
    <p>Ingresar al siguiente enlace y resolver el captcha manualmente si es que aparece.</p>
    <p>
        👉 <a href="{url}" target="_blank">{url}</a>
    </p>
    <p>Finaliza con clic en <b>Ingresar</b>.</p>
    """

    enviarCorreoIT(para, copia, asunto, mensaje, imagen, None)

def obtener_documentos_adjuntos(carpeta,extensiones):
    archivos = [
        archivo for archivo in glob.glob(os.path.join(carpeta, "*"))
        if os.path.isfile(archivo) and archivo.lower().endswith(extensiones)
    ]
    return archivos

def armar_correo(driver,para,copia,palabra_clave,msj,imagen,ruta_archivos_x_inclu,archivos,numero_poliza,compania):

    if archivos:
        extensiones_permitidas = (".pdf",".xlsx",".xls")
        archivos_para_adjuntar = obtener_documentos_adjuntos(ruta_archivos_x_inclu,extensiones_permitidas)
    else:
        archivos_para_adjuntar=None

    if imagen:
        ruta_imagen = os.path.join(ruta_archivos_x_inclu,f"{get_timestamp()}.png")
        driver.save_screenshot(ruta_imagen)
    else:
        ruta_imagen = None

    texto_compania = f" en la Compañía {compania}" if compania else ""
    texto_solicitud = f"Se detectó un error al procesar la póliza <b>{numero_poliza}</b> en la compañía" if compania else "Hubo un incoveniente en la plataforma de Birlik"
    asunto = f"❌ Error en la {palabra_clave} para la Póliza {numero_poliza}{texto_compania}"
    mensaje=f"""
             {texto_solicitud}. Porfavor revisar la {palabra_clave} manualmente de manera inmediata.<br><br>
             <b>Error Técnico y evidencia visual:</b><br><br>
             <pre>{msj}</pre><br>
             Gracias.
             """

    enviarCorreoIT(para,copia,asunto,mensaje,ruta_imagen,archivos_para_adjuntar)