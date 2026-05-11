#-- Imports --
import re
import json
#-- Froms --
from bs4 import BeautifulSoup

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

def extraer_codigo_del_mensaje(cuerpo_texto):
    # Buscar un número de 6 dígitos
    match = re.search(r"\b(\d{6})\b", cuerpo_texto)

    if match:
        codigo = match.group(1)
        return codigo
    else:
        return None

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