#-- Imports --
import requests
import time
import sys
import msal
import re
import os
#-- Froms --
from bs4 import BeautifulSoup

# --- Variables de entorno ---
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
AUTHORITY = f'https://login.microsoftonline.com/{TENANT_ID}'
SCOPE = [os.getenv("SCOPE")]
EMAIL_ACCOUNT = os.getenv("ariadne")
#-----MS Graph API URL para obtener correos-------
GRAPH_API_URL = 'https://graph.microsoft.com/v1.0/users/{}/messages'.format(EMAIL_ACCOUNT)

def extraer_codigo_de_cuerpo(cuerpo_html):
    """
    Extrae el código (por lo general 6 dígitos) buscando primero
    la frase contextual ("código de acceso", "código de verificación", ...)
    y luego el primer número que aparezca después de esa frase.
    """
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
    # Payload para marcar el mensaje como leído
    payload = {
        "isRead": True
    }
    
    response = requests.patch(f"{GRAPH_API_URL}/{message_id}", headers=headers, json=payload)
    
    if response.status_code == 200:
        print(f"🟢 Correo marcado como leído.")
    else:
        print(f"Error al marcar el correo como leído: {response.status_code}, {response.text}")

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

def revisar_correo_ariadne():

    token = obtener_token()
    headers = {
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json'
    }
    
    response = requests.get(GRAPH_API_URL, headers=headers, params={'$filter': "isRead eq false"})
   
    if response.status_code == 200:
        messages = response.json().get('value', [])
        print(f"Correos no leídos detectados: {len(messages)}")
    
        for message in messages:
            # Obtener el asunto del correo
            asunto = message.get('subject')
            message_id = message.get('id')
            print(f"Asunto del correo: {asunto}")
            cuerpo = message.get('body', {}).get('content', '')

            try:
                if asunto and asunto.startswith('Código de verificación MAPFRE'):
                    codigo = extraer_codigo_de_cuerpo(cuerpo)
                    print("Código extraído:", codigo)
                    return codigo  # o acumular y seguir según tu lógica
                elif asunto and asunto.startswith('Código de Autenticación - Inicio sesión SAS'):
                    codigo = extraer_codigo_del_mensaje(cuerpo)
                    print("Código extraído:", codigo)
                    return codigo  # o acumular y seguir según tu lógica
            finally:
                marcar_como_leido(message_id,token)
                time.sleep(5)
    
    else:
        print(f"Error al obtener correos: {response.status_code}, {response.text}")

if __name__ == "__main__":
    revisar_correo_ariadne()