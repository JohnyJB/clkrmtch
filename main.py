# login.py
from flask import Flask, request, redirect, url_for, session, render_template_string
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import uuid
from cryptography.fernet import Fernet
import os

global prompt_actual
PROMPT_FILE = "prompt_chatgpt.txt"
prompt_actual = ""  # se sobreescribe al inicio de la app
# ───────── Prompt de Estrategia de Mails ─────────
PROMPT_MAILS_FILE = "prompt_mails_estrategia.txt"
prompt_mails = ""  # se sobreescribe al inicio de la app

def cargar_prompt_mails_original() -> str:
    if not os.path.exists(PROMPT_MAILS_FILE):
        return ""
    with open(PROMPT_MAILS_FILE, "r", encoding="utf-8") as f:
        return f.read()

def guardar_prompt_mails_en_archivo(prompt: str):
    with open(PROMPT_MAILS_FILE, "w", encoding="utf-8") as f:
        f.write(prompt.strip())

# al iniciar la app
prompt_mails = cargar_prompt_mails_original()

def cargar_prompt_original():
    if not os.path.exists(PROMPT_FILE):
        return ""
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

prompt_actual = cargar_prompt_original()

def cargar_prompt_desde_archivo() -> str:
    if not os.path.exists(PROMPT_FILE):
        return ""
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()

def guardar_prompt_en_archivo(prompt: str):
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(prompt.strip())


# 🔐 Clave para desencriptar db.txt
ENCRYPTION_KEY = b'yMybaWCe4meeb3v4LWNI4Sxz7oS54Gn0Fo9yJovqVN0='

app = Flask(__name__)

# Configuración Flask
app.secret_key = "clave_ultra_segura_que_deberias_guardar_en_env"
app.permanent_session_lifetime = timedelta(hours=1)

# ✅ Cargar db.txt encriptado
def load_db_config(file_path: str) -> dict:
    with open(file_path, "rb") as f:
        encrypted = f.read()
    fernet = Fernet(ENCRYPTION_KEY)
    decrypted = fernet.decrypt(encrypted).decode("utf-8")

    lines = decrypted.strip().splitlines()
    config = {}
    for line in lines:
        if "=" in line:
            k, v = line.split("=", 1)
            config[k.strip()] = v.strip()
    return config

# 🔌 Conexión a PostgreSQL
try:
    db_conf = load_db_config("db.txt")
    db_url = f"postgresql://{db_conf['username']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['database']}?sslmode={db_conf['sslmode']}"
    engine = create_engine(db_url)
    print("[INFO] Conexión a DB configurada correctamente.")
except Exception as e:
    print("[ERROR] No se pudo conectar a la base de datos:", e)
    engine = None

# HTML embebido (igual que antes, intacto)
template_base = '''
<!DOCTYPE html>
<html>
<head>
    <title>ClickerMatch - {{ titulo }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500&display=swap" rel="stylesheet">
    <style>
        body {
            background: url('/static/background.png') no-repeat center center fixed;
            background-size: cover;
            color: #FFFFFF;
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0; padding: 0;
            text-align: center;
        }
        .container {
            max-width: 300px;
            margin: 60px auto;
            background-color: #1F1F1F;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
        }
        input[type="text"], input[type="email"], input[type="password"] {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            background-color: #2A2A2A;
            border: 1px solid #ccc;
            border-radius: 8px;
            color: #fff;
        }
        button {
            width: 100%;
            padding: 10px;
            background-color: #1E90FF;
            border: none;
            color: white;
            cursor: pointer;
            font-size: 16px;
            margin-top: 10px;
        }
        button:hover {
            background-color: #00BFFF;
        }
        .msg {
            color: #ff8080;
            margin: 10px 0;
        }
        a { color: #1E90FF; }
    </style>
</head>
<body>
<div class="container">
    <h2>{{ titulo }}</h2>
    <form method="POST">
        {% if register %}
            <input type="text" name="nombre" placeholder="Nombre" required><br>
        {% endif %}
        <input type="email" name="correo" placeholder="Correo" required><br>
        <input type="password" name="pass" placeholder="Contraseña" required><br>
        <button type="submit">{{ 'Registrar' if register else 'Entrar' }}</button>
    </form>
    <div class="msg">{{ msg }}</div>
    {% if register %}
        <a href="/">Volver al login</a>
    {% else %}
        <!-- <a href="/register">Crear cuenta</a> -->
    {% endif %}
</div>
</body>
</html>
'''

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if engine is None:
        msg = "Base de datos no disponible."
    elif request.method == "POST":
        correo = request.form["correo"]
        password = request.form["pass"]
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT * FROM usuarios WHERE correo = :correo"), {"correo": correo}).mappings().first()
                if result and check_password_hash(result["pass"], password):
                    session.permanent = True
                    session["user"] = result["nombre"]
                    session["correo"] = correo
                    session["session_id"] = str(uuid.uuid4())
                    conn.execute(text("UPDATE usuarios SET session_id = :sid WHERE correo = :correo"), {
                        "sid": session["session_id"], "correo": correo
                    })
                    return redirect("/")
                else:
                    msg = "Correo o contraseña incorrecta."
        except Exception as e:
            print("[ERROR en login]:", e)
            msg = "Error interno en login."
    return render_template_string(template_base, msg=msg, register=False, titulo="Iniciar Sesión")

@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ""
    if engine is None:
        msg = "Base de datos no disponible."
    elif request.method == "POST":
        nombre = request.form["nombre"]
        correo = request.form["correo"]
        password = generate_password_hash(request.form["pass"])
        try:
            with engine.connect() as conn:
                exists = conn.execute(text("SELECT 1 FROM usuarios WHERE correo = :correo"), {"correo": correo}).scalar()
                if exists:
                    msg = "Este correo ya está registrado."
                else:
                    conn.execute(text("""
                        INSERT INTO usuarios (nombre, correo, pass, es_admin, creado_en)
                        VALUES (:nombre, :correo, :pass, false, NOW())
                    """), {"nombre": nombre, "correo": correo, "pass": password})
                    msg = "Cuenta creada correctamente. Ahora puedes iniciar sesión."
        except Exception as e:
            print("[ERROR en registro]:", e)
            msg = "Error interno al registrar usuario."
    return render_template_string(template_base, msg=msg, register=True, titulo="Crear Cuenta")

# Si corres localmente





# plataforma.py
import time
import os
import io
import re
import json
import requests
import pandas as pd
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from flask import Flask, request, make_response, session, redirect, url_for
from cryptography.fernet import Fernet
from pdfminer.high_level import extract_text
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
# Rutas comunes para explorar además de la principal
EXTRA_PATHS = ["/about", "/about-us", "/nosotros", "/quienes-somos", "/servicios", "/services"]
COMMON_INFO_PATHS = [
    "/about", "/about-us", "/nosotros", "/quienes-somos", "/servicios", "/services", "/recursos",
    "/company", "/compañia", "/compania", "/equipo", "/team", "/products", "/productos", "/solutions", "/soluciones",
    "/what-we-do", "/mission", "/mision", "/historia", "/history", "/markets", "/industries", "/cases", "/case-studies",
    "/casestudies", "/casosdeexito", "/sobre-nosotros"
]
#corporate 
# Si tu wrapper es distinto, adapta la importación:
try:
    from openai import OpenAI
except ImportError:
    print("[ERROR] No se encontró 'from openai import OpenAI'. Ajusta la librería según corresponda.")
    OpenAI = None

###############################
# 1) Hardcodear la API Key
###############################


def decrypt_api_key(encrypted_data: bytes) -> str:
    """
    Desencripta los datos en bytes usando ENCRYPTION_KEY,
    y devuelve la API key en texto plano.
    """
    f = Fernet(ENCRYPTION_KEY)
    decrypted_bytes = f.decrypt(encrypted_data)
    return decrypted_bytes.decode("utf-8")

def scrapear_linkedin_empresa(linkedin_url: str) -> str:
    """
    Hace scraping de un perfil público de empresa en LinkedIn.
    Extrae texto visible en la descripción o secciones relevantes.
    """
    linkedin_url = _asegurar_https(linkedin_url)
    try:
        if "linkedin.com/company/" not in linkedin_url:
            return "-"
        headers = {
            "User-Agent": "Mozilla/5.0",
        }
        resp = requests.get(linkedin_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[ERROR] LinkedIn HTTP {resp.status_code} para {linkedin_url}")
            return "-"

        soup = BeautifulSoup(resp.text, "html.parser")
        texto = soup.get_text(separator=" ", strip=True)
        limpio = _limpiar_caracteres_raros(texto)
        return limpio[:1500]  # Puedes ajustar el tamaño máximo

    except Exception as e:
        print(f"[ERROR] al scrapear LinkedIn {linkedin_url}:", e)
        return "-"


def load_api_key_from_file(file_path: str) -> str:
    """
    Lee el contenido cifrado de 'api.txt' y lo desencripta.
    Retorna la clave original (en texto claro).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No se encontró el archivo: {file_path}")
    
    with open(file_path, "rb") as f:
        encrypted_data = f.read()
    
    return decrypt_api_key(encrypted_data)




# -------------------------------
# Cargamos la clave descifrada
# -------------------------------
try:
    HARDCODED_API_KEY = load_api_key_from_file("api.txt")
except Exception as e:
    # Por si el archivo no existe o hay error
    HARDCODED_API_KEY = ""
    print("[ERROR]", e)
    


###############################
# Inicializar el cliente
###############################
client = None
if OpenAI:
    client = OpenAI(api_key=HARDCODED_API_KEY)
else:
    print("[ERROR] La clase OpenAI no está disponible. Por favor revisa tu librería o wrapper de OpenAI.")

# Estados para saber si ya se ejecutó cada acción
acciones_realizadas = {
    "clasificar_puestos": False,
    "clasificar_areas": False,
    "clasificar_industrias": False,
    "super_scrap_leads": False,
    "generar_desafios": False,
    "generar_tabla": False
}

app.secret_key = "CLAVE_SECRETA_PARA_SESSION"  # si deseas usar session

# DataFrame principal
df_leads = pd.DataFrame()
scraping_progress = {
    "total": 0,
    "procesados": 0
}

logs_urls_scrap = []

#Campos industria y area
propuesta_valor = ""
contexto_prov = ""
icp_prov = ""
plan_estrategico = ""

#Variables proveedor inicialización
nombre_empresa_usuario = ""
descripcion_proveedor = ""
productos_proveedor = ""
mercado_proveedor = ""
icp_proveedor = ""


# Catálogo de puestos cargado por el usuario
catalogo_df = pd.DataFrame()
columnas_catalogo = []
columna_comparacion_catalogo = "Puesto Director"

# Datos del proveedor (estructurado desde ChatGPT)
info_proveedor_global = {
    "Nombre de la Empresa": "-",
    "Objetivo": "-",
    "Productos o Servicios": "-",
    "Industrias": "-",
    "Clientes o Casos de Exito": "-"
}

# Texto crudo del scraping (seguimos usándolo internamente)
scrap_proveedor_text = ""

# Mapeos de columnas para df_leads
mapeo_nombre_contacto = "Name"
mapeo_puesto = "title"
mapeo_empresa = "companyName"
mapeo_industria = "industry"
mapeo_website = "website"
mapeo_empleados = "Company Employee Count Range"
mapeo_location = "location"



# Configuraciones
MAX_SCRAPING_CHARS = 6000
OPENAI_MODEL = "gpt-3.5-turbo"
OPENAI_MAX_TOKENS = 1000

###############################
# Funciones auxiliares
###############################
def generar_info_empresa_chatgpt(row: pd.Series) -> dict:
    if client is None:
        return {
            "EMPRESA_DESCRIPCION": "-",
            "EMPRESA_PRODUCTOS_SERVICIOS": "-",
            "EMPRESA_INDUSTRIAS_TARGET": "-"
        }

    texto_scrap = (str(row.get("scrapping", "")) + "\n" + str(row.get("Scrapping Adicional", ""))).strip()
    prompt = f"""
Eres un analista de datos empresariales. A partir de este texto sacado del sitio web de una empresa, genera lo siguiente en formato JSON:

{{
  "EMPRESA_DESCRIPCION": "Resumen general de lo que hace la empresa.Si no tiene pon -",
  "EMPRESA_PRODUCTOS_SERVICIOS": "Lista o resumen de los productos o servicios que ofrece.Si no tiene pon -",
  "EMPRESA_INDUSTRIAS_TARGET": "Industrias a las que atiende o está enfocado.Si no tiene pon -"
}}

Texto de la empresa:
{texto_scrap or "-"}
    """

    try:
        respuesta = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": _limpiar_caracteres_raros(prompt)}],
            max_tokens=500,
            temperature=0.0,
            timeout=30
        )
        content = respuesta.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").strip()
        if content.endswith("```"):
            content = content[:-3].strip()
        return json.loads(content)
    except Exception as e:
        print("[ERROR] al generar info empresa:", e)
        return {
            "EMPRESA_DESCRIPCION": "-",
            "EMPRESA_PRODUCTOS_SERVICIOS": "-",
            "EMPRESA_INDUSTRIAS_TARGET": "-"
        }


def guardar_prompt_log(prompt: str, lead_name: str = "", idx: int = -1):
    """
    Guarda el prompt en un archivo de texto. Usa el nombre del contacto o índice para identificarlo.
    """
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"logs/prompt_{idx}_{lead_name}_{timestamp}.txt".replace(" ", "_").replace(":", "-")
    
    os.makedirs("logs", exist_ok=True)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(prompt)

def _limpiar_caracteres_raros(texto: str) -> str:
    """
    Elimina caracteres extraños y normaliza los saltos de línea.
    """
    # 1. Elimina caracteres extraños no deseados
    texto = re.sub(r'[^\w\sáéíóúÁÉÍÓÚñÑüÜ:;,.!?@#%&()"+\-\//$\'\"\n\r\t¿¡]', '', texto)

    # 2. Reemplaza múltiples saltos de línea por uno solo
    texto = re.sub(r'\n\s*\n+', '\n', texto)

    # 3. Reemplaza múltiples espacios por uno solo
    texto = re.sub(r'[ ]{2,}', ' ', texto)

    return texto.strip()

def _asegurar_https(url: str) -> str:
    """Asegura que la URL comience con https://"""
    url = url.strip()
    if not url:
        return ""
    if url.startswith("http://"):
        url = url.replace("http://", "https://")
    elif not url.startswith("https://"):
        url = "https://" + url
    return url

def extraer_texto_pdf(pdf_path: str) -> str:
    try:
        texto = extract_text(pdf_path)
        if texto.strip():
            return texto
        else:
            # Si no tiene texto, intenta OCR
            imagenes = convert_from_path(pdf_path, dpi=300)
            texto_ocr = ""
            for imagen in imagenes:
                texto_ocr += pytesseract.image_to_string(imagen, lang='spa') + "\n"
            return texto_ocr
    except Exception as e:
        print("[ERROR] Al leer PDF:", e)
        return "-"



def realizar_super_scraping(base_url: str) -> str:
    """
    Hace scraping de rutas comunes como /about, /nosotros, /servicios si están disponibles.
    Concatena todo el texto encontrado.
    """
    rutas = ["/", "/about", "/about-us", "/nosotros", "/servicios", "/services"]
    texto_total = ""

    for ruta in rutas:
        try:
            full_url = base_url.rstrip("/") + ruta
            full_url = _asegurar_https(full_url)
            resp = requests.get(full_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, verify=False)
            if resp.status_code == 200:
                sopa = BeautifulSoup(resp.text, "html.parser")
                texto = sopa.get_text()
                #print(f"[DEBUG] Texto obtenido: {texto[:300]}")
                limpio = _limpiar_caracteres_raros(texto[:2000])
                texto_total += f"\n[{ruta}]\n{limpio}\n"
        except:
            continue  # Si alguna ruta falla, continúa con las otras

    return texto_total if texto_total.strip() else "-"

def realizar_scraping(url: str) -> str:
    url = _asegurar_https(url)
    if not url:
        return "-"

    rutas = [""]  # ruta principal + adicionales
    texto_total = ""

    for path in rutas:
        try:
            full_url = url.rstrip("/") + path
            #print("[SCRAPING]", full_url)
            resp = requests.get(full_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5, verify=False)

            if resp.status_code == 200:
                sopa = BeautifulSoup(resp.text, "html.parser")
                texto = sopa.get_text()
                #print(f"[DEBUG] Texto obtenido: {texto[:300]}")
                texto = _limpiar_caracteres_raros(texto)
                texto_total += texto + "\n"
            else:
                print(f"[SKIP] Código HTTP {resp.status_code} en {full_url}")
        except Exception as e:
            print(f"[ERROR] al scrapear {full_url}:", e)

        if len(texto_total) >= MAX_SCRAPING_CHARS:
            break

    return texto_total[:MAX_SCRAPING_CHARS] if texto_total.strip() else "-"

#Scrapping de urls
def extraer_urls_de_web(base_url: str) -> str:
    """Extrae todos los enlaces href del sitio principal de la empresa y los devuelve separados por coma y espacio."""
    base_url = _asegurar_https(base_url)
    try:
        resp = requests.get(base_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, verify=False)
        if resp.status_code == 200:
            sopa = BeautifulSoup(resp.text, "html.parser")
            enlaces = [a.get("href") for a in sopa.find_all("a", href=True)]

            # Filtrar duplicados y normalizar
            enlaces_filtrados = list(set(filter(None, enlaces)))

            # Convertir relativos a absolutos
            enlaces_absolutos = [
                enlace if enlace.startswith("http") else base_url.rstrip("/") + "/" + enlace.lstrip("/")
                for enlace in enlaces_filtrados
            ]

            return ", ".join(enlaces_absolutos)
    except Exception as e:
        print(f"[ERROR] al extraer enlaces de {base_url}:", e)
    return "-"

def realizar_scrap_adicional(urls_csv: str) -> str:
    """
    Recibe un string de URLs separadas por coma (campo "URLs on WEB"),
    filtra aquellas que contienen rutas comunes, y concatena el texto de scraping.
    """
    urls = [u.strip() for u in urls_csv.split(",") if u.strip()]
    
    # 🔒 Filtrar dominios no deseados como LinkedIn
    urls = [u for u in urls if not any(domain in u.lower() for domain in ["linkedin.com"])]

    # 🎯 Solo tomar las rutas que coinciden con las comunes
    matching_urls = [u for u in urls if any(path in u for path in COMMON_INFO_PATHS)]

    #print(f"[SCRAP-ADICIONAL] Coincidencias encontradas: {len(matching_urls)}")

    texto_total = ""
    for link in matching_urls:
        try:
            full_url = _asegurar_https(link)
            resp = requests.get(full_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, verify=False)
            if resp.status_code == 200:
                sopa = BeautifulSoup(resp.text, "html.parser")
                texto = sopa.get_text()
                #print(f"[DEBUG] Texto obtenido: {texto[:300]}")
                limpio = _limpiar_caracteres_raros(texto[:3000])
                texto_total += f"\n[{link}]\n{limpio}\n"
        except Exception as e:
            print(f"[ERROR] Scraping adicional falló en {link} →", e)

    return texto_total if texto_total.strip() else "-"

#Extraer redes de scrapp
def extraer_contactos_redes(url: str) -> dict:
    """Extrae teléfono y redes sociales de un sitio web."""
    resultado = {
        "web_celular": "",
        "web_instagram": "",
        "web_facebook": "",
        "web_linkedin": ""
    }

    url = _asegurar_https(url)
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=8, verify=False)
        if resp.status_code != 200:
            return resultado

        soup = BeautifulSoup(resp.text, "html.parser")
        enlaces = [a.get("href") for a in soup.find_all("a", href=True)]

        for href in enlaces:
            if not href: continue
            if "tel:" in href:
                resultado["web_celular"] = href.replace("tel:", "").strip()
            elif "facebook.com" in href and not resultado["web_facebook"]:
                resultado["web_facebook"] = href
            elif "instagram.com" in href and not resultado["web_instagram"]:
                resultado["web_instagram"] = href
            elif "linkedin.com" in href and not resultado["web_linkedin"]:
                resultado["web_linkedin"] = href

        # Buscar también por texto (teléfono sin <a href="tel:...">)
        texto = soup.get_text()
        match_tel = re.search(r"\(?\+?\d{1,3}[\s\-\.]?\(?\d{2,3}\)?[\s\-\.]?\d{3,4}[\s\-\.]?\d{4}", texto)
        if match_tel and not resultado["web_celular"]:
            resultado["web_celular"] = match_tel.group()

    except Exception as e:
        print(f"[ERROR] al extraer redes/teléfono de {url}:", e)

    return resultado
#Generar desafíos
def generar_desafios_por_lead(row: pd.Series) -> dict:
    if client is None:
        return {"Desafio 1": "-", "Desafio 2": "-", "Desafio 3": "-"}

    title = str(row.get("title", "-"))
    nivel = str(row.get("Nivel Jerarquico", "-"))
    subarea = str(row.get("departamento", "-"))
    area = str(row.get("Company Industry", "-"))
    municipio = str(row.get("Municipio", "-"))
    estado = str(row.get("Estado", "-"))
    pais = str(row.get("Pais", "-"))
    objetivo = str(row.get("Objetivo", "-"))
    productos = str(row.get("Productos o Servicios", "-"))
    industria = str(row.get("Industria Mayor", "-"))
    emp_count = str(row.get("Company Employee Count Range", "-"))
    founded = str(row.get("Company Founded", "-"))
    descripcion = str(row.get("linkedin_description", "-"))
    scrap_basico = str(row.get("scrapping", "-"))
    scrap_adicional = str(row.get("Scrapping Adicional", "-"))

    prompt = f"""
Eres un analista de negocio B2B. Con base en esta información de un lead, genera 3 desafíos específicos que esta persona podría estar enfrentando en su empresa.

Devuelve la respuesta en este JSON:
{{
  "Desafio 1": "...",
  "Desafio 2": "...",
  "Desafio 3": "..."
}}

Datos del lead:
- Puesto: {title}
- Nivel Jerárquico: {nivel}
- Área Mayor: {area}
- Industria: {industria}

"""

    try:
        respuesta = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.7,
            timeout=30
        )
        content = respuesta.choices[0].message.content.strip()

        if content.startswith("```json"):
            content = content.replace("```json", "").strip()
        if content.endswith("```"):
            content = content[:-3].strip()

        parsed = json.loads(content)
        return {
            "Desafio 1": parsed.get("Desafio 1", "-"),
            "Desafio 2": parsed.get("Desafio 2", "-"),
            "Desafio 3": parsed.get("Desafio 3", "-")
        }
    except Exception as e:
        print("[ERROR] al generar desafíos:", e)
        return {"Desafio 1": "-", "Desafio 2": "-", "Desafio 3": "-"}



#####################################
# 2) Función para analizar con ChatGPT
#    el texto crudo del proveedor y
#    extraer la info solicitada
#####################################
def analizar_proveedor_scraping_con_chatgpt(texto_scrapeado: str) -> dict:
    """
    Envía a ChatGPT el texto scrapeado del proveedor para obtener:
    (1) Nombre de la Empresa
    (2) Objetivo
    (3) Productos o Servicios
    (4) Industrias
    (5) Clientes o Casos de Exito
    (6) ICP
    Retorna un dict con esas claves.
    """
    if client is None:
        print("[ERROR] Cliente ChatGPT es None. Retorno info vacía.")
        return {
            "Nombre de la Empresa": "-",
            "Objetivo": "-",
            "Productos o Servicios": "-",
            "Industrias": "-",
            "Clientes o Casos de Exito": "-",
            "ICP": "-"
        }

    prompt = f"""
Eres un asistente que analiza la información de un sitio web de una empresa (texto crudo).
Devuélveme exactamente en formato JSON los siguientes campos:
- "Nombre de la Empresa"
- Objetivo (o misión o enfoque principal)
- "Productos o Servicios" (Si no dice el scrapp, infiere sobre que son)
- "Industrias" (a qué industrias sirve o en cuáles se especializa)
- "Clientes o Casos de Exito" (si aparecen referencias a clientes o casos)
- "ICP" (Ideal Costumer Profile, de industria, puesto)

Si no encuentras algo, simplemente pon "-".

Texto del sitio (Si a continuación no te doy info del sitio, pon - en todas):
{texto_scrapeado}
    """

    # Limpiamos caracteres raros del prompt:
    prompt = _limpiar_caracteres_raros(prompt)

    try:
        respuesta = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.0,
            timeout=30
        )
        content = respuesta.choices[0].message.content.strip()
        #print("[LOG] Respuesta ChatGPT (Análisis proveedor):", content)

        # Parsear JSON
        try:
            parsed = json.loads(content)
            # Asegurarnos de tener todas las claves (si no existen, ponemos "-")
            nombre = parsed.get("Nombre de la Empresa", "-")
            objetivo = parsed.get("Objetivo", "-")
            prod_serv = parsed.get("Productos o Servicios", "-")
            industrias = parsed.get("Industrias", "-")
            clientes = parsed.get("Clientes o Casos de Exito", "-")
            icp = parsed.get("ICP", "-")
            return {
                "Nombre de la Empresa": nombre,
                "Objetivo": objetivo,
                "Productos o Servicios": prod_serv,
                "Industrias": industrias,
                "Clientes o Casos de Exito": clientes,
                "ICP": icp
            }
        except Exception as ex_json:
            print("[ERROR] No se pudo parsear la respuesta de ChatGPT como JSON:", ex_json)
            return {
                "Nombre de la Empresa": "-",
                "Objetivo": "-",
                "Productos o Servicios": "-",
                "Industrias": "-",
                "Clientes o Casos de Exito": "-",
                "ICP": "-"
            }
    except Exception as ex:
        print("[ERROR] Al invocar ChatGPT para analizar proveedor:", ex)
        return {
            "Nombre de la Empresa": "-",
            "Objetivo": "-",
            "Productos o Servicios": "-",
            "Industrias": "-",
            "Clientes o Casos de Exito": "-",
            "ICP": "-"
        }

#####################################
# Función ChatGPT para leads
#####################################


def generar_contenido_chatgpt_por_fila(row: pd.Series) -> dict:
    """
    Genera las columnas definidas: Personalization, Your Value Prop, etc.
    usando la API de ChatGPT.
    Devuelve un dict con esas claves separadas.
    """
    if client is None:
        print("[ERROR] 'client' es None, no se puede llamar la API.")
        return {
            "Personalization": "-",
            "Your Value Prop": "-",
            "Target Niche": "-",
            "Your Targets Goal": "-",
            "Your Targets Value Prop": "-",
            "Cliffhanger Value Prop": "-",
            "CTA": "-"
        }

    # Extraer datos
    lead_name = str(row.get(mapeo_nombre_contacto, "-"))
    scrap_clean = str(row.get("scrapping", "-")).strip().replace("\n", " ")[:1500]
    scrap_adicional_clean = str(row.get("Scrapping Adicional", "-")).strip().replace("\n", " ")[:1500]
    title = str(row.get(mapeo_puesto, "-"))
    industry = str(row.get(mapeo_industria, "-"))
    companyName = str(row.get(mapeo_empresa, "-"))
    employee_range = str(row.get(mapeo_empleados, "-"))
    location = str(row.get(mapeo_location, "-"))
    scrapping_lead = str(row.get("scrapping", "-"))
    scrapping_proveedor = str(row.get("scrapping_proveedor", "-"))

    # PROMPT: Claves con ChatGPT 
    prompt = f"""
INSTRUCCIONES:
- Devuelve la respuesta SOLO como un objeto JSON (usando llaves)
- No incluyas texto adicional antes o después del JSON
- Utiliza únicamente estas claves:
  "Personalization",
  "Your Value Prop",
  "Your Target Niche",
  "Your Client Goal",
  "Your Client Value Prop",
  "Cliffhanger Value Prop",
  "CTA".

Tenemos un cliente llamado {companyName}.
Descripción: {row.get("EMPRESA_DESCRIPCION", "-")}
Productos y servicios: {row.get("EMPRESA_PRODUCTOS_SERVICIOS	", "-")}
Industria Objetivo: {row.get("EMPRESA_INDUSTRIAS_TARGET", "-")}
Basado en esta información del cliente y del proveedor, genera los siguientes campos en español:

Personalization: Es una introducción personalizada basada en un hecho reciente o logro de la empresa cliente, el objetivo es captar su atención de inmediato. Empresa Cliente → Se basa en su actividad, logros o contexto. 
 Cómo calcularla:
Fuente
Campo(s) utilizados
Tabla Contactos
Title, Departamento, Área, Desafíos
Tabla Empresas
Company Website, Productos / Servicios, Objetivo

Método:
Analiza Title, Desafíos del contacto para destacar algo que esté enfrentando o liderando.


Analiza Empresa, Objetivo o Industria de la Empresa para conectar el mensaje al contexto.


Your Value Prop. Es la propuesta de valor de tu empresa, lo que ofreces y cómo ayudas a resolver un problema específico. Proveedor → Es nuestro diferenciador y lo que podemos hacer por el cliente.
 Cómo calcularla:
Fuente
Interna (no viene en las tablas)
Mi Info
Descripcion, Producto o Servicio, 

Método:
Usa reglas según el área o industria del contacto para insertar una versión relevante de tu propuesta.

Ejemplo:
“Ayudamos a líderes de marketing educativo a aumentar sus leads calificados usando automatización de datos.”

Your Target Niche (Niche, Subsegment, Location). El segmento de mercado al que queremos llegar, definido por industria, subsegmento y ubicación. Proveedor → Es nuestra audiencia objetivo.

 Cómo calcularla:
Fuente
Campo(s) utilizados
Tabla Contactos
Area, Departamento, Nivel Jerarquico
Tabla Empresas
Company Industry, Estado, País

Método:
Concatenar:

python
CopiarEditar
Target_Niche = f"{row.get("area", "-")}, {row.get("departamento", "-")}, {row.get("Nivel Jerarquico", "-")}, {row.get("Company Industry", "-")}, {row.get("Nivel Jerarquico", "-")}, {row.get("Nivel Jerarquico", "-")}"

Ejemplo:
Retail – Ciudad de México, México
Your Client Goal. La meta principal del puesto del cliente. ¿Qué quiere lograr con su negocio o estrategia?. Cliente → Es su necesidad o aspiración.
Cómo calcularla:
Fuente
Campo(s) utilizados
Tabla Contactos
Title, Departamento, Área, Nivel Jerarquico, Desafíos
Tabla Empresas
Company Industria, Website, Objetivo, Productos / Servicios, Industrias Target

Método:
Analiza Departamento, Área, Nivel Jerarquico, Company Industria y propone retos de relacionados a mas ingresos o reducción de costos, productividad / eficiencia en función de Objetivo
Ejemplo:
Reducir el ciclo de venta mediante mayor personalización y automatización.
Your Client Value Prop. La propuesta de valor del cliente. ¿Cómo se diferencian ellos en su mercado? ¿Qué buscan potenciar?. Cliente → Es cómo ellos se presentan en su industria.
Cómo calcularla:
Fuente
Campo(s) utilizados
Tabla Empresas
Objetivo, Productos / Servicios, Industria Target, Website

Método:
Detectar cómo se presentan o qué comunican como ventaja competitiva.

Si no está explícito, se puede inferir de Objetivo.

Ejemplo:
“[Empresa] ayuda a organizaciones educativas a formar líderes con visión global.”
Cliffhanger Value Prop. Una propuesta intrigante o gancho para motivar la conversación, generalmente una promesa de resultados o insights valiosos. Proveedor → Un beneficio atractivo para generar curiosidad.

Cómo calcularla:
Fuente
Interna (propuesta del proveedor) + contexto del cliente

Método:
Usa la lógica: "¿Qué podría interesarle resolver y que nosotros sabemos resolver mejor?"

Genera versiones por segmento.

Ejemplo:
“¿Te gustaría ver cómo otras universidades han triplicado su conversión en 30 días?”
CTA (Call to Action). La acción concreta que queremos que tome el cliente, como agendar una reunión o responder al correo. Proveedor → Es nuestra invitación a la acción.

Cómo calcularla:
Fuente
No depende de la tabla, se define por estrategia comercial
Personalizable
Según nivel jerárquico y tipo de conversación

Ejemplos de CTA:
“¿Te muestro un ejemplo la próxima semana?”

“¿Tienes 15 minutos esta semana para verlo?”

“¿Te interesa conocer como lo hacemos?”

Escríbelos de manera que conecten en un solo mensaje

Información del lead:
- Empresa: {companyName}
- Contacto: {lead_name}
- Puesto: {title}
- Nivel Jerárquico: {row.get("Nivel Jerarquico", "-")}
- Área: {row.get("area", "-")}
- Departamento: {row.get("departamento", "-")}
- Industria: {industry}
- Desafíos posibles:
    - {row.get("Desafio 1", "-")}
    - {row.get("Desafio 2", "-")}
    - {row.get("Desafio 3", "-")}

Información del ICP (Ideal Customer Profile):
- Propuesta de valor de nosotros:" {propuesta_valor} "
- Contexto adicional de nosotros:" {contexto_prov} "
- Nuestro Ideal Costumer Profile:" {icp_prov} "

- Contenido del sitio web del cliente (scrapping del cliente): {scrap_clean} 
- Contenido adicional del sitio (scrapping común): {scrap_adicional_clean}

- La ubicación de la empresa es: (si no te doy una ubicación, ignóralo)

Información del proveedor:
- Contenido extraído del sitio web del proveedor: 
{plan_estrategico}
SOLICITUD:
Genera cada uno de estos campos en español y de forma breve:
1) Personalization
2) Your Value Prop
3) Your Target Niche
4) Your Client Goal
5) Your Client Value Prop
6) Cliffhanger Value Prop
7) CTA


Recuerda: la respuesta debe ser válido JSON con llaves y comillas en cada clave-valor, sin texto adicional.
"""

    prompt = _limpiar_caracteres_raros(prompt)
    #guardar_prompt_log(prompt, lead_name=lead_name, idx=row.name)
    #print(f"[PROMPT] idx={row.name}, lead={lead_name}")
    #print(prompt)

    try:
        print("[LOG] Llamando ChatGPT (leads)...")
        respuesta = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=OPENAI_MAX_TOKENS,
            temperature=0.7,
            timeout=30
        )
        content = respuesta.choices[0].message.content.strip()

        # Intentar parsear JSON
        try:
            parsed = json.loads(content)
            personalization = parsed.get("Personalization", "-")
            value_prop = parsed.get("Your Value Prop", "-")
            target_niche = parsed.get("Your Target Niche", "-")
            targets_goal = parsed.get("Your Client Goal", "-")
            targets_value_prop = parsed.get("Your Client Value Prop", "-")
            cliffhanger = parsed.get("Cliffhanger Value Prop", "-")
            cta = parsed.get("CTA", "-")
        except Exception as ex:
            print("[ERROR] No se pudo parsear JSON en leads:")
            print("Contenido recibido:", content)
            print("Excepción:", ex)
            # Fallback: poner todo en "Personalization" si falla
            personalization = content
            value_prop = "-"
            target_niche = "-"
            targets_goal = "-"
            targets_value_prop = "-"
            cliffhanger = "-"
            cta = "-"

        return {
            "Personalization": personalization,
            "Your Value Prop": value_prop,
            "Target Niche": target_niche,
            "Your Targets Goal": targets_goal,
            "Your Targets Value Prop": targets_value_prop,
            "Cliffhanger Value Prop": cliffhanger,
            "CTA": cta
        }
    except Exception as e:
        print("[ERROR] Al invocar ChatGPT (leads):", e)
        return {
            "Personalization": "-",
            "Your Value Prop": "-",
            "Target Niche": "-",
            "Your Targets Goal": "-",
            "Your Targets Value Prop": "-",
            "Cliffhanger Value Prop": "-",
            "CTA": "-"
        }

def generar_emails_estrategia(row: pd.Series) -> dict:
    if client is None:
        print("[ERROR] Cliente ChatGPT no disponible.")
        return {k: "-" for k in [
            "Strategy - 25% Reply Rate Email", "Strategy - One Sentence Email",
            "Strategy - Asking for an Introduction", "Strategy - Ask for Permission",
            "Strategy - Loom Video", "Strategy - Free Sample List"
        ]}
    lead_name = str(row.get(mapeo_nombre_contacto, "-"))
    title = str(row.get(mapeo_puesto, "-"))
    industry = str(row.get(mapeo_industria, "-"))
    companyName = str(row.get(mapeo_empresa, "-"))
    employee_range = str(row.get(mapeo_empleados, "-"))
    location = str(row.get(mapeo_location, "-"))
    lead_name = str(row.get(mapeo_nombre_contacto, "-"))  # Esto ya está definido arriba
    
    base_context = f"""
Nombre del contacto: {lead_name}

Resultados para adaptar:
- "Personalization": {row.get("Personalization", "-")}
- "Your Value Prop": {row.get("Your Value Prop", "-")}
- "Target Niche": {row.get("Target Niche", "-")}
- "Your Client Goal": {row.get("Your Targets Goal", "-")}
- "Your Client Value Prop": {row.get("Your Targets Value Prop", "-")}
- "Cliffhanger Value Prop": {row.get("Cliffhanger Value Prop", "-")}
- "CTA": {row.get("CTA", "-")}

Con base en los datos anteriores, desarrolla los siguientes 6 correos personalizados según cada estrategia de prospección. Cada correo debe incluir:
Información adicional del lead:
- Nivel Jerárquico: {row.get("Nivel Jerarquico", "-")}
- Área Mayor: {row.get("area", "-")}
- Área Menor: {row.get("departamento", "-")}
- Desafíos actuales: {row.get("Desafio 1", "-")}, {row.get("Desafio 2", "-")}, {row.get("Desafio 3", "-")}
- Fragmentos del sitio web: {row.get("scrapping", "-")}
- Texto adicional del sitio: {row.get("Scrapping Adicional", "-")}

- Asunto (subject)
- Saludo personalizado (Ej. Hola [Nombre del contacto])
- Cuerpo dividido en párrafos claros, según la estructura indicada
- Despedida cordial
- Firma con nombre de empresa ficticia o genérica ("Equipo de ClickerMatch")

Importante:
- No uses la palabra "vender" en ninguno de los correos.
- Usa alternativas como "llegar a más clientes", "acercar tu solución", "posicionar tu propuesta", etc.

Devuelve tu respuesta en formato JSON (sin explicaciones ni comentarios, solo el JSON):

{{
  "Strategy - 25% Reply Rate Email": "Asunto: ...\\nHola [nombre]...\\n\\n[Párrafo 1]...\\n[Párrafo 2]...\\nSaludos,\\nEquipo de ClickerMatch",
  "Strategy - One Sentence Email": "Asunto: ...\\nHola [nombre]...\\n\\n[Frase breve]...\\nSaludos,\\nEquipo de ClickerMatch",
  "Strategy - Asking for an Introduction": "Asunto: ...\\nHola [nombre]...\\n\\n[Mensaje para pedir introducción]...\\nGracias,\\nEquipo de ClickerMatch",
  "Strategy - Ask for Permission": "...",
  "Strategy - Loom Video": "...",
  "Strategy - Free Sample List": "..."
}}

Estructuras:

- Strategy: 25% Reply Rate Email  
  Personalization | Your Value Prop | Target Niche | Your Targets Goal | Your Targets Value Prop | Cliffhanger Value Prop | CTA

- Strategy: One Sentence Email  
  Personalization | Your Value Prop | Target Niche | CTA

- Strategy: Asking for an Introduction  
  Personalization | Your Targets Value Prop | CTA

- Strategy: Ask for Permission  
  Personalization | Your Targets Value Prop | Cliffhanger Value Prop | CTA

- Strategy: Loom Video  
  Personalization | Your Targets Value Prop | Your Value Prop | CTA

- Strategy: Free Sample List  
  Personalization | Your Targets Goal | Your Value Prop | CTA
"""
    #print(base_context)
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": base_context}],
            max_tokens=1000,
            temperature=0.7,
            timeout=30
        )
        content = response.choices[0].message.content.strip()
        #print("[RAW RESPONSE EMAILS STRATEGY]:", content)

        # 🔥 FIX para quitar ```json y ```
        if content.startswith("```json"):
            content = content.replace("```json", "").strip()
        if content.endswith("```"):
            content = content[:-3].strip()

        parsed = json.loads(content)
        return parsed

    except Exception as e:
        print("[ERROR] Fallo al generar emails por estrategia:", e)
        return {k: "-" for k in [
            "Strategy - 25% Reply Rate Email", "Strategy - One Sentence Email",
            "Strategy - Asking for an Introduction", "Strategy - Ask for Permission",
            "Strategy - Loom Video", "Strategy - Free Sample List"
        ]}

def generar_emails_bloque_1(row: pd.Series) -> dict:
    prompt = f"""
Nombre del contacto: {row.get(mapeo_nombre_contacto, "-")}

Resultados para adaptar:
- "Personalization": {row.get("Personalization", "-")}
- "Your Value Prop": {row.get("Your Value Prop", "-")}
- "Target Niche": {row.get("Target Niche", "-")}
- "Your Client Goal": {row.get("Your Targets Goal", "-")}
- "Your Client Value Prop": {row.get("Your Targets Value Prop", "-")}
- "Cliffhanger Value Prop": {row.get("Cliffhanger Value Prop", "-")}
- "CTA": {row.get("CTA", "-")}
Información adicional del contacto:
- Nivel Jerárquico: {row.get("Nivel Jerarquico", "-")}
- Área Mayor: {row.get("area", "-")}
- Área Menor: {row.get("departamento", "-")}
- Desafíos:
    - {row.get("Desafio 1", "-")}
    - {row.get("Desafio 2", "-")}
    - {row.get("Desafio 3", "-")}
- Fragmentos del sitio web: {row.get("scrapping", "-")}
- Fragmentos adicionales: {row.get("Scrapping Adicional", "-")}

Desarrolla los siguientes correos con estructura completa de email:
- Strategy - 25% Reply Rate Email
- Strategy - One Sentence Email
- Strategy - Asking for an Introduction

Incluye: Asunto, saludo personalizado, cuerpo dividido en párrafos, despedida y firma como 'Equipo de ClickerMatch'.  
NO uses la palabra "vender", mejor usa "llegar".

Devuelve solo este JSON:
{{
  "Strategy - 25% Reply Rate Email": "...",
  "Strategy - One Sentence Email": "...",
  "Strategy - Asking for an Introduction": "..."
}}
"""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.7,
        timeout=30
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```json"):
        content = content.replace("```json", "").strip()
    if content.endswith("```"):
        content = content[:-3].strip()
    return json.loads(content)

def generar_emails_bloque_2(row: pd.Series) -> dict:
    prompt = f"""
Nombre del contacto: {row.get(mapeo_nombre_contacto, "-")}

Resultados para adaptar:
- "Personalization": {row.get("Personalization", "-")}
- "Your Value Prop": {row.get("Your Value Prop", "-")}
- "Target Niche": {row.get("Target Niche", "-")}
- "Your Client Goal": {row.get("Your Targets Goal", "-")}
- "Your Client Value Prop": {row.get("Your Targets Value Prop", "-")}
- "Cliffhanger Value Prop": {row.get("Cliffhanger Value Prop", "-")}
- "CTA": {row.get("CTA", "-")}
Información adicional del contacto:
- Nivel Jerárquico: {row.get("Nivel Jerarquico", "-")}
- Área Mayor: {row.get("area", "-")}
- Área Menor: {row.get("departamento", "-")}
- Desafíos:
    - {row.get("Desafio 1", "-")}
    - {row.get("Desafio 2", "-")}
    - {row.get("Desafio 3", "-")}
- Fragmentos del sitio web: {row.get("scrapping", "-")}
- Fragmentos adicionales: {row.get("Scrapping Adicional", "-")}

Desarrolla los siguientes correos con estructura completa de email:
- Strategy - Ask for Permission
- Strategy - Loom Video
- Strategy - Free Sample List


Incluye: Asunto, saludo personalizado, cuerpo dividido en párrafos, despedida y firma como 'Equipo de ClickerMatch'.  
NO uses la palabra "vender", mejor usa "llegar".

Devuelve solo este JSON:
{{
  "Strategy - Ask for Permission": "...",
  "Strategy - Loom Video": "...",
  "Strategy - Free Sample List": "..."
}}
"""
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.7,
        timeout=30
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```json"):
        content = content.replace("```json", "").strip()
    if content.endswith("```"):
        content = content[:-3].strip()
    return json.loads(content)


def procesar_leads():
    """Scrapea website de cada lead y rellena df_leads con el texto."""
    global df_leads
    if df_leads.empty:
        print("[LOG] df_leads vacío. No se hace nada en procesar_leads.")
        return

    needed_cols = [
        "scrapping_proveedor", "scrapping", "Personalization",
        "Your Value Prop", "Target Niche", "Your Targets Goal",
        "Your Targets Value Prop", "Cliffhanger Value Prop", "CTA"
    ]
    for c in needed_cols:
        if c not in df_leads.columns:
            df_leads[c] = ""

    estrategias_cols = [
        "Strategy - 25% Reply Rate Email",
        "Strategy - One Sentence Email",
        "Strategy - Asking for an Introduction",
        "Strategy - Ask for Permission",
        "Strategy - Loom Video",
        "Strategy - Free Sample List"
    ]
    for col in estrategias_cols:
        if col not in df_leads.columns:
            df_leads[col] = "-"


    for idx, row in df_leads.iterrows():
        website = str(row.get(mapeo_website, "")).strip()
        if website:
            sc_lead = realizar_scraping(website)
            df_leads.at[idx, "scrapping"] = sc_lead
        else:
            df_leads.at[idx, "scrapping"] = "-"
def build_select_options(default_value, columns):
    """
    Crea las etiquetas <option> para un <select>, 
    marcando con 'selected' la que coincida con 'default_value'.
    """
    # Opción inicial para no cambiar nada manualmente
    opts = ["<option value=''> (Sin cambio) </option>"]
    for col in columns:
        selected = "selected" if col == default_value else ""
        opts.append(f"<option value='{col}' {selected}>{col}</option>")
    return "\n".join(opts)

def generar_contenido_para_todos():
    """Itera sobre df_leads y llama a ChatGPT para generar las columnas definidas."""
    global df_leads
    if df_leads.empty:
        print("[LOG] df_leads vacío, no generamos contenido.")
        return

    for idx, row in df_leads.iterrows():
        try:
            print(f"[LOG] Generando contenido ChatGPT para lead idx={idx}...")
            result = generar_contenido_chatgpt_por_fila(row)

            df_leads.at[idx, "Personalization"] = result["Personalization"]
            df_leads.at[idx, "Your Value Prop"] = result["Your Value Prop"]
            df_leads.at[idx, "Target Niche"] = result["Target Niche"]
            df_leads.at[idx, "Your Targets Goal"] = result["Your Targets Goal"]
            df_leads.at[idx, "Your Targets Value Prop"] = result["Your Targets Value Prop"]
            df_leads.at[idx, "Cliffhanger Value Prop"] = result["Cliffhanger Value Prop"]
            df_leads.at[idx, "CTA"] = result["CTA"]
            row.update(result)  # <- ACTUALIZA los valores en la variable row
            emails_1 = generar_emails_bloque_1(row)
            emails_2 = generar_emails_bloque_2(row)

            for col, val in {**emails_1, **emails_2}.items():
                df_leads.at[idx, col] = val



        except Exception as e:
            print(f"[ERROR] Error inesperado en lead idx={idx}: {e}")

    # Limpieza final
    cleanup_leads()

def cleanup_leads():
    """Reemplaza NaN, None y corchetes en las columnas de texto final."""
    global df_leads
    if df_leads.empty:
        return
    cols_to_clean = [
        "Personalization", "Your Value Prop", "Target Niche",
        "Your Targets Goal", "Your Targets Value Prop",
        "Cliffhanger Value Prop", "CTA",
        "Strategy - 25% Reply Rate Email", "Strategy - One Sentence Email",
        "Strategy - Asking for an Introduction", "Strategy - Ask for Permission",
        "Strategy - Loom Video", "Strategy - Free Sample List"
    ]

    for col in cols_to_clean:
        if col in df_leads.columns:
            df_leads[col] = df_leads[col].astype(str)
            df_leads[col] = df_leads[col].replace(
                ["NaN", "nan", "None", "none"], "-", regex=True
            )
            # Quitar corchetes de array si aparecieran
            df_leads[col] = df_leads[col].replace(r"\[|\]", "", regex=True)

##########################################
# Mostrar tabla HTML (solo primeros 10)
##########################################
def tabla_html(df: pd.DataFrame, max_filas=50) -> str:
    if df.empty:
        return "<p><em>DataFrame vacío</em></p>"

    # Crear una copia solo para la visualización, eliminando las columnas ocultas
    #subset = df.drop(columns=["scrapping_proveedor", "scrapping"], errors="ignore").head(max_filas)
    # Forzar orden de columnas: Company Name, Name, Title primero
    columnas_prioritarias = ["Company Name", "Name", "Title"]
    otras = [col for col in df.columns if col not in columnas_prioritarias]
    subset = df[columnas_prioritarias + otras] if all(c in df.columns for c in columnas_prioritarias) else df.head(max_filas)
    cols = list(subset.columns)

    anchas = [
        "Personalization", "Your Value Prop", "Target Niche", "Your Targets Goal",
        "Your Targets Value Prop", "Cliffhanger Value Prop", "CTA",
        "Strategy - 25% Reply Rate Email", "Strategy - One Sentence Email",
        "Strategy - Asking for an Introduction", "Strategy - Ask for Permission",
        "Strategy - Loom Video", "Strategy - Free Sample List", "super_scrapping",
        "scrapping", "URLs on WEB", "Scrapping Adicional"
    ]
    thead = "".join(
        f"<th class='col-ancha'>{col}</th>" if col in anchas else f"<th>{col}</th>"
        for col in cols
    )

    rows_html = ""
    for _, row in subset.iterrows():
        row_html = ""
        for col in cols:
            valor = str(row[col])
            if col == "Company Logo Url Secondary" and pd.notnull(row[col]) and valor.strip().lower().startswith("http"):
                row_html += f"<td><img src='{valor}' alt='Logo' style='max-height:40px;'/></td>"
            else:
                row_html += (
                    f"<td class='col-ancha'><div class='cell-collapsible'>{valor}</div></td>"
                    if col in anchas else
                    f"<td><div class='cell-collapsible'>{valor}</div></td>"
                )
        rows_html += f"<tr>{row_html}</tr>"


    return f"<p><strong>📊 Total Registros: {len(subset)}</strong></p>" + f"<table><tr>{thead}</tr>{rows_html}</table>"


##########################################
# Rutas Flask
##########################################
@app.route("/", methods=["GET","POST"])
def index():
    if "user" not in session:
        return redirect("/login")  # redirige al login principal
   
    global df_leads
    global scrap_proveedor_text
    global info_proveedor_global
    global mapeo_nombre_contacto, mapeo_puesto, mapeo_empresa
    global mapeo_industria, mapeo_website, mapeo_location, mapeo_empleados
    global propuesta_valor, contexto_prov, plan_estrategico, icp_prov
    global logs_urls_scrap
    global descripcion_proveedor, productos_proveedor, mercado_proveedor, icp_proveedor
    global prompt_actual
    global prompt_mails
    status_msg = ""
    
    url_proveedor_global = ""  # Moveremos esto a variable local
    accion = request.form.get("accion", "")
    if request.method == "POST":

        if accion == "generar_info_empresa":
            if not df_leads.empty:
                for col in ["EMPRESA_DESCRIPCION", "EMPRESA_PRODUCTOS_SERVICIOS", "EMPRESA_INDUSTRIAS_TARGET"]:
                    if col not in df_leads.columns:
                        df_leads[col] = "-"

                for idx, row in df_leads.iterrows():
                    result = generar_info_empresa_chatgpt(row)
                    for key, val in result.items():
                        df_leads.at[idx, key] = val
                status_msg += "Información de la empresa generada con éxito con ChatGPT.<br>"
            else:
                status_msg += "Primero debes cargar una base de leads.<br>"
            
        if accion == "guardar_prompt_chatgpt":
            nuevo_prompt = request.form.get("prompt_chatgpt", "").strip()
            prompt_actual = nuevo_prompt
            status_msg += "✅ Prompt actualizado en memoria.<br>"

        elif accion == "reiniciar_prompt_chatgpt":
            prompt_actual = cargar_prompt_original()
            status_msg += "♻️ Prompt reiniciado desde el archivo original.<br>"
        elif accion == "guardar_prompt_mails":
            nuevo = request.form.get("prompt_mails", "").strip()
            prompt_mails = nuevo
            guardar_prompt_mails_en_archivo(nuevo)
            status_msg += "✅ Prompt de mails de estrategia actualizado.<br>"

        elif accion == "reiniciar_prompt_mails":
            prompt_mails = cargar_prompt_mails_original()
            status_msg += "♻️ Prompt de mails de estrategia reiniciado.<br>"


        if accion == "guardar_custom_fields":
            propuesta_valor = request.form.get("propuesta_valor", "").strip()
            contexto_prov = request.form.get("contexto_prov", "").strip()
            icp_prov = request.form.get("icp_prov", "").strip()
            plan_estrategico_input = request.form.get("plan_estrategico", "").strip()

            url_scrap_plan = request.form.get("url_scrap_plan", "").strip()

            # Si se dio una URL, usamos scraping. Si no, usamos lo que el usuario haya escrito manualmente
            if url_scrap_plan:
                try:
                    plan_estrategico = realizar_scraping(url_scrap_plan)
                    status_msg += f"✅ Scraping exitoso desde <code>{url_scrap_plan}</code><br>"
                except Exception as e:
                    plan_estrategico = plan_estrategico_input
                    status_msg += f"❌ Error al hacer scraping: {e}<br>Usando el texto proporcionado manualmente.<br>"
            else:
                plan_estrategico = plan_estrategico_input
                status_msg += f"✅ Texto ingresado manualmente cargado como Plan Estratégico.<br>"

        url_scrap_plan = request.form.get("url_scrap_plan", "").strip()
        if url_scrap_plan:
            try:
                texto_scrapeado = realizar_scraping(url_scrap_plan)
                plan_estrategico = texto_scrapeado
                status_msg += f"Texto extraído desde {url_scrap_plan} para Plan Estratégico.<br>"
            except Exception as e:
                status_msg += f"Error al hacer scraping de {url_scrap_plan}: {e}<br>"
        
        if accion == "generar_desafios":
            if not df_leads.empty:
                for col in ["Desafio 1", "Desafio 2", "Desafio 3"]:
                    if col not in df_leads.columns:
                        df_leads[col] = "-"

                for idx, row in df_leads.iterrows():
                    if all(df_leads.at[idx, col] in ["-", "", None] for col in ["Desafio 1", "Desafio 2", "Desafio 3"]):
                        resultado = generar_desafios_por_lead(row)
                        df_leads.at[idx, "Desafio 1"] = resultado.get("Desafio 1", "-")
                        df_leads.at[idx, "Desafio 2"] = resultado.get("Desafio 2", "-")
                        df_leads.at[idx, "Desafio 3"] = resultado.get("Desafio 3", "-")
                acciones_realizadas["generar_desafios"] = True
                status_msg += "Desafíos generados con éxito.<br>"
            else:
                status_msg += "Primero debes cargar una base de leads.<br>"
        if accion == "scrapear_linkedin_empresas":
            if not df_leads.empty and "Company Linkedin Url" in df_leads.columns:
                if "linkedin_description" not in df_leads.columns:
                    df_leads["linkedin_description"] = "-"

                for idx, row in df_leads.iterrows():
                    linkedin_url = str(row.get("Company Linkedin Url", "")).strip()
                    if linkedin_url:
                        descripcion = scrapear_linkedin_empresa(linkedin_url)
                        df_leads.at[idx, "linkedin_description"] = descripcion
                status_msg += "Scraping de LinkedIn completado y guardado en 'linkedin_description'.<br>"
            else:
                status_msg += "No se encontró la columna 'Company Linkedin Url' o no hay datos.<br>"

        if accion == "extraer_redes_y_telefono":
            if not df_leads.empty:
                for col in ["web_celular", "web_instagram", "web_facebook", "web_linkedin"]:
                    if col not in df_leads.columns:
                        df_leads[col] = ""

                for idx, row in df_leads.iterrows():
                    sitio = str(row.get(mapeo_website, "")).strip()
                    if sitio:
                        info = extraer_contactos_redes(sitio)
                        for k, v in info.items():
                            df_leads.at[idx, k] = v
                status_msg += "Redes sociales y teléfonos extraídos desde los sitios web.<br>"
            else:
                status_msg += "Carga primero tu base de leads para extraer redes y teléfonos.<br>"

        if accion == "scrap_urls_filtradas":
            if not df_leads.empty:
                if "URLs on WEB" not in df_leads.columns:
                    status_msg += "Primero debes ejecutar 'ExtraerURLs'.<br>"
                else:
                    df_leads["Scrapping Adicional"] = "-"
                    scraping_progress["total"] = len(df_leads)
                    scraping_progress["procesados"] = 0

                    for idx, row in df_leads.iterrows():
                        urls_csv = str(row.get("URLs on WEB", "")).strip()
                        if urls_csv and urls_csv != "-":
                            texto_adicional = realizar_scrap_adicional(urls_csv)
                            df_leads.at[idx, "Scrapping Adicional"] = texto_adicional
                        else:
                            df_leads.at[idx, "Scrapping Adicional"] = "-"
                        scraping_progress["procesados"] += 1

                    status_msg += "Scraping adicional de URLs comunes completado.<br>"
            else:
                status_msg += "Primero carga una base de leads.<br>"

        if accion == "extraer_urls_leads":
            logs_urls_scrap.clear()
            if not df_leads.empty:
                df_leads["URLs on WEB"] = "-"
                scraping_progress["total"] = len(df_leads)
                scraping_progress["procesados"] = 0

                for idx, row in df_leads.iterrows():
                    url = str(row.get(mapeo_website, "")).strip()

                    if url:
                        logs_urls_scrap.append(f"🔗 Iniciando scraping de: {url}")
                        urls_extraidas = extraer_urls_de_web(url)
                        df_leads.at[idx, "URLs on WEB"] = urls_extraidas
                        logs_urls_scrap.append(f"✅ Finalizado: {url}")
                    else:
                        logs_urls_scrap.append(f"⚠️ URL vacía en fila {idx}")

                    scraping_progress["procesados"] += 1

                status_msg += "Extracción de URLs completada para todos los leads.<br>"
            else:
                status_msg += "Primero carga una base de leads.<br>"

        if accion == "super_scrap_leads":
            if not df_leads.empty:
                if "scrapping" not in df_leads.columns:
                    df_leads["scrapping"] = "-"
                if "URLs on WEB" not in df_leads.columns:
                    df_leads["URLs on WEB"] = "-"
                
                scraping_progress["total"] = len(df_leads)
                scraping_progress["procesados"] = 0

                for idx, row in df_leads.iterrows():
                    url = str(row.get(mapeo_website, "")).strip()
                    if url:
                        print(f"[SCRAP-LEAD] Scraping principal en: {url}")
                        try:
                            texto_scrap = realizar_scraping(url)
                            df_leads.at[idx, "scrapping"] = texto_scrap if texto_scrap.strip() else "-"
                        except Exception as e:
                            print(f"[ERROR] Scraping lead idx={idx}: {e}")
                            df_leads.at[idx, "scrapping"] = "-"

                        #print(f"[SCRAP-URLS] Extrayendo URLs de: {url}")
                        try:
                            urls_extraidas = extraer_urls_de_web(url)
                            df_leads.at[idx, "URLs on WEB"] = urls_extraidas if urls_extraidas.strip() else "-"
                        except Exception as e:
                            print(f"[ERROR] Extrayendo URLs idx={idx}: {e}")
                            df_leads.at[idx, "URLs on WEB"] = "-"
                    else:
                        print(f"[SCRAP-LEAD] Sin URL en idx={idx}")
                        df_leads.at[idx, "scrapping"] = "-"
                        df_leads.at[idx, "URLs on WEB"] = "-"

                    scraping_progress["procesados"] += 1
                    porcentaje = int(scraping_progress["procesados"] / scraping_progress["total"] * 100)
                    acciones_realizadas["super_scrap_leads"] = True
                    print(f"[LOG] Scrapping {scraping_progress['procesados']} de {scraping_progress['total']} ({porcentaje}%)")

                status_msg += "Scraping principal y extracción de URLs completados para todos los leads.<br>"
            else:
                status_msg += "Cargue una base de leads primero.<br>"
                        
        if accion == "cargar_contactos_db":
            try:
                id_inicio = request.form.get("id_inicio", "").strip()
                id_fin = request.form.get("id_fin", "").strip()
                filtro = request.form.get("filtro_busqueda", "").strip().lower()

                condiciones = []
                params = {}

                if id_inicio.isdigit() and id_fin.isdigit():
                    condiciones.append("c.id BETWEEN :start AND :end")
                    params["start"] = int(id_inicio)
                    params["end"] = int(id_fin)

                if filtro:
                    condiciones.append("""(
                        LOWER(c.name) LIKE :filtro OR
                        LOWER(c.first_name) LIKE :filtro OR
                        LOWER(c.last_name) LIKE :filtro OR
                        LOWER(e.company_name) LIKE :filtro OR
                        LOWER(e.company_domain) LIKE :filtro OR
                        LOWER(e.company_revenue_range) LIKE :filtro
                    )""")
                    params["filtro"] = f"%{filtro}%"

                where_clause = "WHERE " + " AND ".join(condiciones) if condiciones else ""

                query = text(f"""
                    SELECT 
                        e.company_name AS "Company Name",
                        c.name AS "Name",
                        c.title AS "Title",

                        c.first_name AS "First name",
                        c.last_name AS "Last name",
                        c.email AS "Email",
                        c.email_status AS "Email Status",
                        c.linkedin AS "Linkedin",
                        c.location AS "Location",
                        c.added_on AS "Added On",

                        e.company_domain AS "Company Domain",
                        e.company_website AS "Company Website",
                        e.company_employee_count AS "Company Employee Count",
                        e.company_employee_count_range AS "Company Employee Count Range",
                        e.company_founded AS "Company Founded",
                        e.company_industry AS "Company Industry",
                        e.company_type AS "Company Type",
                        e.company_headquarters AS "Company Headquarters",
                        e.company_revenue_range AS "Company Revenue Range",
                        e.company_linkedin_url AS "Company Linkedin Url",
                        e.company_crunchbase_url AS "Company Crunchbase Url",
                        e.company_funding_rounds AS "Company Funding Rounds",
                        e.company_last_funding_round_amount AS "Company Last Funding Round Amount",
                        e.company_logo_url_primary AS "Company Logo Url, Primary",
                        e.company_logo_url_secondary AS "Company Logo Url Secondary"
                    FROM contactos c
                    LEFT JOIN empresas e ON c.empresa_id = e.id
                    {where_clause}
                    ORDER BY c.id ASC
                """)

                with engine.connect() as conn:
                    result = conn.execute(query, params).mappings().all()
                    df_leads = pd.DataFrame(result)
                    num_registros = len(df_leads)
                    status_msg += f"✅ Se cargaron {num_registros} contactos desde la DB.<br>"
                for k in acciones_realizadas:
                    acciones_realizadas[k] = False

                status_msg += f"✅ Se cargaron {len(df_leads)} contactos desde la DB.<br>"

                # Auto mapeo (ajustado)
                mapeo_nombre_contacto = 'Name'
                mapeo_puesto = 'Title'
                mapeo_empresa = 'Company Name'
                mapeo_industria = 'Company Industry'
                mapeo_website = 'Company Website'
                mapeo_location = 'Location'
                mapeo_empleados = 'Company Employee Count Range'

            except Exception as e:
                status_msg += f"❌ Error al cargar desde la base de datos: {e}<br>"


        if accion == "subir_pdf_plan":                                   
        # PDF para Plan Estratégico
                pdf_file = request.files.get("pdf_plan_estrategico")
                if pdf_file and pdf_file.filename.endswith(".pdf"):
                    ruta_temp = "plan_temp.pdf"
                    pdf_file.save(ruta_temp)
                    texto_extraido = extraer_texto_pdf(ruta_temp)
                    plan_estrategico = texto_extraido
                    status_msg += "Texto extraído del PDF cargado en Plan Estratégico.<br>"

        # Clasificar area
        if accion == "clasificar_areas":
            if os.path.exists("catalogoarea.xlsx"):
                try:
                    catalogo_area = pd.read_excel("catalogoarea.xlsx")
                    catalogo_area["title_minusc"] = catalogo_area["title_minusc"].str.strip().str.lower()

                    def asignar_areas(title):
                        t = str(title).strip().lower().replace(",", " ")
                        t_words = set(t.split())

                        # 1️⃣ Buscar coincidencias con TODAS las palabras
                        for _, row in catalogo_area.iterrows():
                            clave = str(row["title_minusc"]).strip().lower().replace(",", " ")
                            clave_words = set(clave.split())

                            if clave_words.issubset(t_words):  # todas las palabras clave están presentes
                                return row["departamento"], row["area"]


                        # 2️⃣ Si no encontró exacto, buscar coincidencia con al menos UNA palabra
                        for _, row in catalogo_area.iterrows():
                            clave = str(row["title_minusc"]).strip().lower().replace(",", " ")
                            clave_words = set(clave.split())

                            if t_words & clave_words:  # al menos una palabra coincide
                                return row["departamento"], row["area"]


                        return "", ""



                    if not df_leads.empty:
                        # Asignar área y departamento
                        df_leads["departamento"], df_leads["area"] = zip(*df_leads[mapeo_puesto].map(asignar_areas))

                        # Asegurar que estén justo después de la columna del puesto
                        cols = list(df_leads.columns)
                        for col in ["departamento", "area"]:
                            if col in cols:
                                cols.remove(col)
                                insert_idx = cols.index(mapeo_puesto) + 1
                                cols.insert(insert_idx, col)
                        df_leads = df_leads[cols]
                        acciones_realizadas["clasificar_areas"] = True

                        status_msg += "Clasificación de áreas aplicada correctamente desde catalogoarea.xlsx.<br>"
                    else:
                        status_msg += "Carga primero tu base de leads antes de clasificar áreas.<br>"

                except Exception as e:
                    status_msg += f"Error al clasificar áreas: {e}<br>"
            else:
                status_msg += "No se encontró el archivo catalogoarea.xlsx.<br>"

        if accion == "clasificar_industrias":
            try:
                if not df_leads.empty and os.path.exists("catalogoindustrias.csv"):
                    df_cat = pd.read_csv("catalogoindustrias.csv")

                    df_cat['company_industry'] = df_cat['company_industry'].astype(str).str.strip().str.lower()
                    df_leads[mapeo_industria] = df_leads[mapeo_industria].astype(str).str.strip().str.lower()

                    # Hacemos merge left para mantener todas las filas originales
                    df_leads = df_leads.merge(df_cat, how='left', left_on=mapeo_industria, right_on='company_industry')
                    # Crear columna si no existe
                    if 'Industria Mayor' not in df_leads.columns:
                        df_leads['Industria Mayor'] = ""

                    # Crear columna si no existe
                    if 'Industria Mayor' not in df_leads.columns:
                        df_leads['Industria Mayor'] = ""

                    # Si hay datos en company_mayor_industry, copiarlos a 'Industria Mayor'
                    if 'company_mayor_industry' in df_leads.columns:
                        df_leads['Industria Mayor'] = df_leads['company_mayor_industry'].fillna(df_leads['Industria Mayor'])

                    # Limpiar columnas auxiliares usadas solo para el merge
                    df_leads.drop(columns=['company_industry', 'company_mayor_industry'], errors='ignore', inplace=True)

                    # Reordenar columna si existe
                    if 'Industria Mayor' in df_leads.columns and mapeo_industria in df_leads.columns:
                        cols = list(df_leads.columns)
                        cols.remove('Industria Mayor')
                        insert_idx = cols.index(mapeo_industria) + 1
                        cols.insert(insert_idx, 'Industria Mayor')
                        df_leads = df_leads[cols]
                    acciones_realizadas["clasificar_industrias"] = True
                    status_msg += "Clasificación de industrias aplicada desde catalogoindustrias.csv.<br>"
                else:
                    status_msg += "No hay datos para clasificar o falta el archivo catalogoindustrias.csv.<br>"
            except Exception as e:
                status_msg += f"Error al clasificar industrias: {e}<br>"

        
        
        if accion == "clasificar_puestos":
            if os.path.exists("catalogopuesto.xlsx"):
                try:
                    global catalogo_df
                    catalogo_df = pd.read_excel("catalogopuesto.xlsx")

                    def clasificar_puesto(title):
                        title = str(title).strip().lower()

                        # Ordenar catálogo por longitud de palabra clave descendente (para priorizar coincidencias más específicas)
                        catalogo_ordenado = catalogo_df.copy()
                        catalogo_ordenado["longitud"] = catalogo_ordenado["Palabra Clave"].astype(str).apply(len)
                        catalogo_ordenado = catalogo_ordenado.sort_values(by="longitud", ascending=False)

                        for _, row in catalogo_ordenado.iterrows():
                            palabra_clave = str(row.get("Palabra Clave", "")).strip().lower()
                            if palabra_clave and palabra_clave in title:
                                return row.get("Nivel Jerárquico", "")
                        return "-"

                    if not df_leads.empty:
                        df_leads["Nivel Jerarquico"] = df_leads[mapeo_puesto].apply(clasificar_puesto)

                        cols = list(df_leads.columns)
                        if mapeo_puesto in cols and "Nivel Jerarquico" in cols:
                            cols.remove("Nivel Jerarquico")
                            insert_idx = cols.index(mapeo_puesto) + 1
                            cols.insert(insert_idx, "Nivel Jerarquico")
                            df_leads = df_leads[cols]
                            acciones_realizadas["clasificar_puestos"] = True
                        status_msg += "Clasificación de puestos aplicada usando 'Palabra Clave' y 'Nivel Jerárquico'.<br>"
                    else:
                        status_msg += "Carga primero tu base de leads antes de clasificar.<br>"

                except Exception as e:
                    status_msg += f"Error al cargar o clasificar con catalogopuesto.xlsx: {e}<br>"
            else:
                status_msg += "No se encontró el archivo catalogopuesto.xlsx.<br>"


        # Subir CSV de leads
        leadf = request.files.get("leads_csv")
        if leadf and leadf.filename:
            # Leer sin filtrar primero
            df_full = pd.read_csv(leadf)
            # Rango de filas
            start_row_str = request.form.get("start_row", "").strip()
            end_row_str = request.form.get("end_row", "").strip()

            try:
                start_row = int(start_row_str) if start_row_str else 0
            except:
                start_row = 0
            try:
                end_row = int(end_row_str) if end_row_str else (len(df_full) - 1)
            except:
                end_row = len(df_full) - 1

            if start_row < 0:
                start_row = 0
            if end_row >= len(df_full):
                end_row = len(df_full) - 1
            if start_row > end_row:
                start_row, end_row = 0, len(df_full) - 1

            df_leads = df_full.iloc[start_row:end_row+1].copy()
            for k in acciones_realizadas:
                acciones_realizadas[k] = False

            status_msg += (
                f"Leads CSV cargado. Filas totales={len(df_full)}. "
                f"Rango aplicado [{start_row}, {end_row}] => {len(df_leads)} filas cargadas.<br>"
            )

            # (AÑADIDO) Checar si existen columnas específicas y reasignar por default
            if 'First name' in df_leads.columns:
                mapeo_nombre_contacto = 'First name'
            if 'Title' in df_leads.columns:
                mapeo_puesto = 'Title'
            if 'Company Name' in df_leads.columns:
                mapeo_empresa = 'Company Name'
            if 'Company Industry' in df_leads.columns:
                mapeo_industria = 'Company Industry'
            if 'Company Website' in df_leads.columns:
                mapeo_website = 'Company Website'
            if 'Location' in df_leads.columns:
                mapeo_location = 'Location'

        # URL del proveedor
        new_urlp = request.form.get("url_proveedor", "").strip()
        if new_urlp:
            url_proveedor_global = new_urlp
            status_msg += f"URL Proveedor={url_proveedor_global}<br>"


               

        # Mapeo de columnas (por si el usuario quiere sobreescribir manualmente)
        mapeo_nombre_contacto = request.form.get("col_nombre", mapeo_nombre_contacto).strip() or mapeo_nombre_contacto
        mapeo_puesto = request.form.get("col_puesto", mapeo_puesto).strip() or mapeo_puesto
        mapeo_empresa = request.form.get("col_empresa", mapeo_empresa).strip() or mapeo_empresa
        mapeo_industria = request.form.get("col_industria", mapeo_industria).strip() or mapeo_industria
        mapeo_website = request.form.get("col_website", mapeo_website).strip() or mapeo_website
        mapeo_location = request.form.get("col_location", mapeo_location).strip() or mapeo_location
        mapeo_empleados = request.form.get("col_employees", mapeo_empleados).strip() or mapeo_empleados


        # Acción
        accion = request.form.get("accion", "")
        if accion == "scrap_proveedor" and url_proveedor_global:
            # Scrapeo y análisis del proveedor
            sc = realizar_scraping(url_proveedor_global)
            plan_estrategico = sc  
            scrap_proveedor_text = sc

            info_proveedor_global = analizar_proveedor_scraping_con_chatgpt(sc)

            descripcion_proveedor = str(info_proveedor_global.get("Objetivo", ""))
            productos_proveedor = str(info_proveedor_global.get("Productos o Servicios", ""))
            mercado_proveedor = info_proveedor_global.get("Industrias", "")
            icp_proveedor = str(info_proveedor_global.get("ICP", ""))

            if isinstance(mercado_proveedor, list):
                mercado_proveedor = ", ".join(mercado_proveedor)
            else:
                mercado_proveedor = str(mercado_proveedor)
        
            if not df_leads.empty:
                df_leads["scrapping_proveedor"] = sc

            status_msg += "Scraping y análisis del proveedor completado.<br>"

            # 🚀 Ejecutar también super_scrap_leads
            if not df_leads.empty:
                if "scrapping" not in df_leads.columns:
                    df_leads["scrapping"] = "-"
                if "URLs on WEB" not in df_leads.columns:
                    df_leads["URLs on WEB"] = "-"
                
                scraping_progress["total"] = len(df_leads)
                scraping_progress["procesados"] = 0

                for idx, row in df_leads.iterrows():
                    url = str(row.get(mapeo_website, "")).strip()
                    if url:
                        try:
                            texto_scrap = realizar_scraping(url)
                            df_leads.at[idx, "scrapping"] = texto_scrap if texto_scrap.strip() else "-"
                        except Exception as e:
                            df_leads.at[idx, "scrapping"] = "-"
                            print(f"[ERROR] Scraping lead idx={idx}: {e}")
                        try:
                            urls_extraidas = extraer_urls_de_web(url)
                            df_leads.at[idx, "URLs on WEB"] = urls_extraidas if urls_extraidas.strip() else "-"
                        except Exception as e:
                            df_leads.at[idx, "URLs on WEB"] = "-"
                            print(f"[ERROR] Extrayendo URLs idx={idx}: {e}")
                    else:
                        df_leads.at[idx, "scrapping"] = "-"
                        df_leads.at[idx, "URLs on WEB"] = "-"

                    scraping_progress["procesados"] += 1

                acciones_realizadas["super_scrap_leads"] = True
                status_msg += "Scraping de leads ejecutado tras scrap del proveedor.<br>"
            else:
                status_msg += "No hay leads para aplicar scraping tras scrap del proveedor.<br>"

            # ➕ También ejecutar scraping adicional de URLs comunes
            if not df_leads.empty and "URLs on WEB" in df_leads.columns:
                if "Scrapping Adicional" not in df_leads.columns:
                    df_leads["Scrapping Adicional"] = "-"
                for idx, row in df_leads.iterrows():
                    urls_csv = str(row.get("URLs on WEB", "")).strip()
                    if urls_csv and urls_csv != "-":
                        try:
                            texto_adicional = realizar_scrap_adicional(urls_csv)
                            df_leads.at[idx, "Scrapping Adicional"] = texto_adicional
                        except Exception as e:
                            print(f"[ERROR] Scraping adicional idx={idx}:", e)
                            df_leads.at[idx, "Scrapping Adicional"] = "-"
                status_msg += "Scraping adicional también ejecutado tras scrap del proveedor.<br>"


        elif accion == "generar_tabla":
            procesar_leads()
            generar_contenido_para_todos()
            acciones_realizadas["generar_tabla"] = True
            status_msg += "Leads procesados y contenido de ChatGPT generado.<br>"

        elif accion == "exportar_archivo":
            formato = request.form.get("formato", "csv")
            if df_leads.empty:
                status_msg += "No hay leads para exportar.<br>"
            else:
                # Crea una copia del df sin la columna que quieres omitir
                df_export = df_leads.drop(columns=["scrapping_proveedor"], errors="ignore")

                if formato == "csv":
                    csv_output = io.StringIO()
                    df_export.to_csv(csv_output, index=False, encoding="utf-8-sig")
                    csv_output.seek(0)
                    resp = make_response(csv_output.getvalue())
                    resp.headers["Content-Disposition"] = "attachment; filename=leads_final.csv"
                    resp.headers["Content-Type"] = "text/csv"
                    return resp
                else:
                    from openpyxl import Workbook
                    bio = io.BytesIO()
                    df_export.to_excel(bio, index=False, engine="openpyxl")
                    bio.seek(0)
                    resp = make_response(bio.getvalue())
                    resp.headers["Content-Disposition"] = "attachment; filename=leads_final.xlsx"
                    resp.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    return resp
    

    # Bloque informativo (en español)

    block_text_es = """
<h2>Cold Email Strategy</h2>
<p>Ejemplo de estructura para tu email:</p>
<p><strong>Personalization</strong> | <strong>Your Value Prop</strong> | <strong>Target Niche</strong> | <strong>Your Targets Goal</strong> | <strong>Your Targets Value Prop</strong> | <strong>Cliffhanger Value Prop</strong> | <strong>CTA</strong></p>
<pre>Ejemplo:
"Hey Carla,
¡Vi que lanzaste una nueva colección de playeras y han tenido bastante popularidad!
Quería escribirte porque ayudamos a marcas de ropa enfocadas en diseño urbano (como la tuya) a conectarse con grandes minoristas de e-commerce que buscan expandir su catálogo.
Me encantaría mostrarte nuestra propuesta, enfocada en duplicar la distribución de tu marca en los próximos 3 meses.
¿Tienes tiempo esta semana para una breve llamada?
¡Quedo atenta!
Laura"
</pre>

<h2>Definición de Variables y Diferencias (Proveedor vs. Cliente)</h2>
<table border="1" style="background:#fff; color:#000; margin:15px auto; max-width:1000px;">
  <tr>
    <th>Variable</th>
    <th>Descripción</th>
    <th>¿Pertenece a nosotros (Proveedor) o al Cliente?</th>
  </tr>
  <tr>
    <td>Personalization</td>
    <td>Introducción personalizada basada en un hecho reciente o logro del cliente. El objetivo es captar su atención de inmediato.</td>
    <td>Cliente → Se basa en su actividad, logros o contexto.</td>
  </tr>
  <tr>
    <td>Your Value Prop</td>
    <td>Propuesta de valor de tu empresa (proveedor). Explica cómo ayudas a resolver un problema específico.</td>
    <td>Proveedor → Nuestro diferenciador y lo que podemos hacer por el cliente.</td>
  </tr>
  <tr>
    <td>Target Niche</td>
    <td>Segmento de mercado al que queremos llegar (industria, subsegmento, ubicación).</td>
    <td>Proveedor → Nuestra audiencia objetivo.</td>
  </tr>
  <tr>
    <td>Your Targets Goal</td>
    <td>Meta principal del cliente; lo que quiere lograr en su negocio o estrategia.</td>
    <td>Cliente → Su necesidad o aspiración.</td>
  </tr>
  <tr>
    <td>Your Targets Value Prop</td>
    <td>Propuesta de valor del cliente. Cómo se diferencian en su mercado y qué buscan potenciar.</td>
    <td>Cliente → Cómo se presentan en su industria.</td>
  </tr>
  <tr>
    <td>Cliffhanger Value Prop</td>
    <td>Propuesta intrigante para motivar la conversación, generalmente una promesa de resultados.</td>
    <td>Proveedor → Gancho atractivo para generar curiosidad.</td>
  </tr>
  <tr>
    <td>CTA (Call to Action)</td>
    <td>Acción específica que buscamos: agendar reunión, responder el correo, etc.</td>
    <td>Proveedor → Invitación a la acción concreta.</td>
  </tr>
</table>
"""


    # Construcción final del HTML
    # Generar HTML del select para columna_comparacion_catalogo
    opciones_select = ""
    if columnas_catalogo:
        for col in columnas_catalogo:
            selected = "selected" if col == columna_comparacion_catalogo else ""
            opciones_select += f"<option value='{col}' {selected}>{col}</option>"
    else:
        opciones_select = "<option selected value='Puesto Director'>Puesto Director</option>"

    # Asignar colores según acciones realizadas
    color_puestos = "green" if acciones_realizadas["clasificar_puestos"] else "#1E90FF"
    color_areas = "green" if acciones_realizadas["clasificar_areas"] else "#1E90FF"
    color_industrias = "green" if acciones_realizadas["clasificar_industrias"] else "#1E90FF"
    color_scrap = "green" if acciones_realizadas["super_scrap_leads"] else "#1E90FF"
    color_desafios = "green" if acciones_realizadas["generar_desafios"] else "#1E90FF"
    color_tabla = "green" if acciones_realizadas["generar_tabla"] else "#1E90FF"
     
    #Creación prompt
    prompt_chatgpt = cargar_prompt_desde_archivo()   
        
    page_html = f"""
    <html>
    <head>
        <title>ClickerMaker</title>
        <style>
            body {{
                background: url('/static/background.png') no-repeat center center fixed;
                background-size: cover;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 0; padding: 0;
                text-align: center;
            }}
            .container {{
                width: 5%;
                max-width: 300px;
                min-width: 300px;
                flex-shrink: 0; 
                margin: 40px auto;
                background-color: #1F1F1F;
                padding: 20px 30px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            }}
            .container-wide {{
                max-width: 100%;
                flex-grow: 1;
                overflow-x: auto;
                margin: 20px auto;
                background-color: #1F1F1F;
                padding: 20px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.4);
                overflow-x: auto;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
                background: #fff;
                color: #000;
            }}
            table th {{
                background-color: #1E90FF;
                color: #fff;
            }}
            table td {{
                padding: 8px;
                border: 1px solid #444;
            }}
            input[type="file"],
            input[type="text"],
            select {{
                width: 100%;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #ccc;
                background-color: #2A2A2A;
                color: #fff;
                margin-bottom: 12px;
            }}
            button {{
                padding: 10px 16px;
                border: none;
                border-radius: 0px; /* <- sin bordes redondeados */
                background-color: #1E90FF;
                color: #fff;
                cursor: pointer;
                margin: 6px 0;
                font-size: 14px;
                width: 100%; /* <- que ocupen todo el ancho */
                box-sizing: border-box; /* para que el padding no los saque del contenedor */
            }}
            button:hover {{
                background-color: #00BFFF;
            }}
            details summary {{
                background-color: #2A2A2A;
                color: #ffffff;
                font-weight: bold;
                padding: 12px;
                cursor: pointer;
                border: none;
                outline: none;
                width: 100%;
                box-sizing: border-box;
                margin: 8px 0;
                display: block;
            }}

            details summary::marker {{
                color: #aaa;
            }}


            .status {{
                background-color: #333;
                margin: 10px auto;
                padding: 10px;
                width: 90%;
                border-radius: 6px;
                text-align: left;
                font-size: 13px;
            }}
            .scrap-container {{
                background-color: #2A2A2A;
                margin: 10px auto;
                padding: 10px;
                border-radius: 8px;
                text-align: left;
            }}
            .content-block {{
                max-width: 1000px;
                margin: 20px auto;
                background-color: #2A2A2A;
                color: #fff;
                padding: 20px;
                border-radius: 10px;
                text-align: left;
            }}
            .spinner {{
                margin: 20px auto;
                width: 50px;
                height: 50px;
                border: 6px solid #ccc;
                border-top: 6px solid #1E90FF;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                }}
            .cell-collapsible {{
                max-height: 60px;
                overflow: hidden;
                position: relative;
                cursor: pointer;
                transition: max-height 0.3s ease;
                white-space: pre-wrap;
            }}
            .cell-collapsible.expanded {{
                max-height: 1000px;
            }}
            .cell-collapsible::after {{
                content: '▼';
                position: absolute;
                bottom: 5px;
                right: 10px;
                font-size: 12px;
                color: gray;
            }}
            .cell-collapsible.expanded::after {{
                content: '▲';
            }}

            table th {{
                background-color: #1E90FF;
                color: #fff;
                position: sticky;
                top: 0;
                z-index: 1;
            }}

            .container-wide {{
                max-height: 600px;
                overflow-y: auto;
            }}

            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
                }}
            th.col-ancha, td.col-ancha {{
                min-width: 250px;
                max-width: 500px;
                word-wrap: break-word;
                white-space: pre-wrap;
            }}
            @media (max-width: 900px) {{
                div[style*="display: flex"] {{
                    flex-direction: column;
                }}
            }}
            .editor {{
                background-color: #222;
                color: white;
                border: 1px solid #333;
                border-radius: 10px;
                padding: 10px;
                min-height: 200px;
                white-space: pre-wrap;
                font-family: monospace;
            }}
            .editor .var {{
                color: #00aaff;
                font-weight: bold;
            }}     
        </style>
    </head>
    <body>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500&display=swap" rel="stylesheet">

    <div style="
        position: relative;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        padding: 30px 20px;
        overflow: hidden;
        background: linear-gradient(to right, #1E90FF 0%, transparent 100%);
        border-radius: 0 0 20px 20px;
        box-shadow: 0 4px 20px rgba(30, 144, 255, 0.3);
    ">
        <img src="https://recordsencrisis.com/wp-content/uploads/2025/05/LOGO-CLICKER-MATCH.png" alt="ClickerMatch"
            style="max-height: 80px; margin-right: 20px;" />
        <div style="position: absolute; top: 20px; right: 30px;">
            <div style="position: relative; display: inline-block;">
                <button onclick="toggleDropdown()" style="background: transparent; border: none; color: white; font-weight: bold; cursor: pointer;">
                    👤 {{ session.get("user", "Usuario") }}
                </button>
                <div id="dropdownMenu" style="display: none; position: absolute; right: 0; background-color: #1F1F1F; min-width: 200px; box-shadow: 0px 8px 16px rgba(0,0,0,0.4); border-radius: 10px; z-index: 1000; padding: 10px;">
                    <p style="margin: 0; color: white;"><strong>{{ session.get("user", "Usuario") }}</strong></p>
                    <p style="margin: 0; font-size: 12px; color: #ccc;">{{ session.get("correo", "") }}</p>
                    <hr style="border-color: #444;">
                    <a href="/logout" style="color: #FF4C4C; text-decoration: none; display: block; margin-top: 5px;">Cerrar sesión</a>
                </div>
            </div>
        </div>

        <h1 style="
            color: white;
            font-size: 30px;
            font-family: 'Orbitron', sans-serif;
            font-weight: 500;
            text-shadow: 1px 1px 4px rgba(0,0,0,0.5);
            letter-spacing: 1px;
        ">
            IA que prospecta y agenda citas con tomadores de decisiones.
        </h1>
    </div>
  
    <div style="display: flex; gap: 20px; align-items: flex-start;">
    <div class="container">
    <!-- Sección 0: Cargar Base de datos de servidor-->    
    <details>
    <summary style="cursor: pointer; font-weight: bold;">📡 Buscar y cargar contactos desde DB</summary>
    <form method="POST">
        <input type="hidden" name="accion" value="cargar_contactos_db" />

        <label>🔍 Buscar texto (en Nombre, Empresa, Dominio...):</label>
        <input type="text" name="filtro_busqueda" placeholder="Ej. Acme, gmail, alto" style="margin-bottom:10px;" />

        <label for="id_inicio">ID desde:</label>
        <input type="number" name="id_inicio" min="1" placeholder="1" />

        <label for="id_fin">hasta:</label>
        <input type="number" name="id_fin" min="1" placeholder="100" />

        <button type="submit">📥 Buscar y Cargar</button>
    </form>
    </details>



        <!-- Sección 1: Cargar CSV y Mapeo -->
    <details>
    <summary style="cursor: pointer; font-weight: bold;">➕ Carga de base de datos</summary>
        <form method="POST" enctype="multipart/form-data">
        <hr>
        <label>Base de Datos:</label>
        <input type="file" name="leads_csv"/>
        <div style="display: flex; gap: 10px; align-items: center; justify-content: center;">
        <label for="start_row">Filas:</label>
        <input type="text" name="start_row" placeholder="Inicio" style="width: 80px;" />
        <span>a</span>
        <input type="text" name="end_row" placeholder="Fin" style="width: 80px;" />
        </div>
    
    <details>
    <summary style="cursor: pointer; font-weight: bold;">➕ Mapeo de columnas (clic para mostrar u ocultar)</summary>
        <p>Mapeo de columnas:</p>
        <div style="margin-top:10px;">
        <label>Nombre del contacto:</label>
        <select name="col_nombre">{build_select_options(mapeo_nombre_contacto, df_leads.columns if not df_leads.empty else [])}</select>
        <label>Puesto/Title:</label>
        <select name="col_puesto">{build_select_options(mapeo_puesto, df_leads.columns if not df_leads.empty else [])}</select>
        <label>Nombre de la empresa:</label>
        <select name="col_empresa">{build_select_options(mapeo_empresa, df_leads.columns if not df_leads.empty else [])}</select>
        <label>Industria:</label>
        <select name="col_industria">{build_select_options(mapeo_industria, df_leads.columns if not df_leads.empty else [])}</select>
        <label>Website:</label>
        <select name="col_website">{build_select_options(mapeo_website, df_leads.columns if not df_leads.empty else [])}</select>
        <label>Rango de empleados:</label>
        <select name="col_employees">{build_select_options(mapeo_empleados, df_leads.columns if not df_leads.empty else [])}</select>
        <label>Ubicación:</label>
        <select name="col_location">{build_select_options(mapeo_location, df_leads.columns if not df_leads.empty else [])}</select>
        </div>
        </details>
        
        <button type="submit">Subir Archivo</button>
        </form>
    </details>    
        <hr>
        <!-- Sección: Clasificación de Puestos -->
    <details>
    <summary style="cursor: pointer; font-weight: bold;">➕ Clasificadores</summary>
        <button type="button" onclick="clasificarTodo()" style="background-color: {color_puestos};">
            Clasificar (Puestos + Áreas + Industrias)
        </button>
        <details>
        <summary>Clasificadores Individualmente</summary>
        <form method="POST" enctype="multipart/form-data">
            <input type="hidden" name="accion" value="clasificar_puestos"/>
            <button type="submit" style="background-color: {color_puestos};">
                Clasificar Puesto
            </button>
        </form>
        <form method="POST">
            <input type="hidden" name="accion" value="clasificar_areas"/>
            <button type="submit" style="background-color: {color_areas};">
                Clasificar Área y Departamento
            </button>
        </form>
        <form method="POST">
            <input type="hidden" name="accion" value="clasificar_industrias"/>
            <button type="submit" style="background-color: {color_industrias};">
                Clasificar Industria Mayor
            </button>
        </form>
        </details>
        <form method="POST">
            <input type="hidden" name="accion" value="super_scrap_leads"/>
            <button type="submit" style="background-color: {color_scrap};">
                Scraping de Leads
            </button>
        </form>   
        <form method="POST">
        <input type="hidden" name="accion" value="scrap_urls_filtradas"/>
        <button type="submit" style="background-color: #1E90FF;">
            Scraping Adicional de URLs comunes
        </button>
        </form>

        <form method="POST">
            <input type="hidden" name="accion" value="scrap_urls_filtradas"/>
            <!-- <button type="submit">Scrapping URLs Filtradas</button> -->
        </form> 
        <form method="POST">
            <input type="hidden" name="accion" value="extraer_redes_y_telefono"/>
            <button type="submit">Extraer Redes y Teléfono</button>
        </form>
        <form method="POST">
            <input type="hidden" name="accion" value="scrapear_linkedin_empresas"/>
            <!-- <button type="submit">Srapp Linkedin (Próximamente)</button> -->
        </form>  
        <form method="POST">
            <input type="hidden" name="accion" value="generar_desafios"/>
            <button type="submit" style="background-color: {color_desafios};">
                Determinar Desafíos con IA
            </button>
        </form>

                 
    </details>            
    <details>
    <summary style="cursor: pointer; font-weight: bold;">🧠 Prompt Value</summary>
    <form method="POST" style="margin-bottom: 10px;" onsubmit="guardarContenidoEditor()">
        <button type="button" onclick="resaltarVariables()">🎨 Resaltar variables</button>
        <input type="hidden" name="accion" value="guardar_prompt_chatgpt"/>
        <div id="editor" class="editor" contenteditable="true">
            {prompt_actual}
        </div>
        <input type="hidden" name="prompt_chatgpt" id="prompt_oculto">
        <button type="submit">💾 Guardar Prompt</button>
    </form>

    <form method="POST">
        <input type="hidden" name="accion" value="reiniciar_prompt_chatgpt"/>
        <button type="submit">♻️ Reiniciar desde archivo .txt</button>
    </form>
    </details>
    <details>
    <summary style="cursor: pointer; font-weight: bold;">🧠 Prompt Mails Estrategia</summary>
    <form method="POST" style="margin-bottom: 10px;" onsubmit="guardarContenidoEditorMails()">
        <button type="button" onclick="resaltarVariablesMails()">🎨 Resaltar variables</button>
        <input type="hidden" name="accion" value="guardar_prompt_mails"/>
        <div id="editor_mails" class="editor" contenteditable="true">
        {prompt_mails}
        </div>
        <input type="hidden" name="prompt_mails" id="prompt_mails_oculto">
        <button type="submit">💾 Guardar Prompt Mails</button>
    </form>
    <form method="POST">
        <input type="hidden" name="accion" value="reiniciar_prompt_mails"/>
        <button type="submit">♻️ Reiniciar desde archivo .txt</button>
    </form>
    </details>             
    <form method="POST">
        <input type="hidden" name="accion" value="generar_info_empresa"/>
        <button type="submit" style="background-color:#1E90FF;">
            🧠 Generar Info Empresa con ChatGPT
        </button>
    </form>

    <hr>
    <details>

    <summary style="cursor: pointer; font-weight: bold;">➕ Mi Info</summary>

    <form method="POST" enctype="multipart/form-data">
        <label>Plan Estratégico:</label>
        <textarea name="plan_estrategico" rows="3" style="width:100%;border-radius:10px;margin-top:8px;">{plan_estrategico or ''}</textarea>

        <details>
            <summary style="cursor:pointer; font-weight: bold;">📄 Plan Estrategico</summary>
            <h4>Información analizada desde el sitio del proveedor</h4>

            <p><strong>Descripción:</strong><br>
            <textarea rows="3" style="width: 100%;" readonly>{descripcion_proveedor or '-'}</textarea></p>

            <p><strong>Productos:</strong><br>
            <textarea rows="3" style="width: 100%;" readonly>{productos_proveedor or '-'}</textarea></p>

            <p><strong>Mercado objetivo:</strong><br>
            <textarea rows="3" style="width: 100%;" readonly>{mercado_proveedor or '-'}</textarea></p>
            
            <p><strong>ICP:</strong><br>
            <textarea rows="3" style="width: 100%;" readonly>{icp_proveedor or '-'}</textarea></p>

            <p><strong>Propuesta de Valor:</strong> {propuesta_valor or '-'}</p>
            <p><strong>Contexto:</strong> {contexto_prov or '-'}</p>
        </details>

        <label>Sube PDF para Plan Estratégico:</label>
        <input type="file" name="pdf_plan_estrategico" id="pdf_plan_estrategico" accept="application/pdf" />

        <label>URL del proveedor para hacer scraping:</label>
        <input type="text" name="url_proveedor" placeholder="https://miempresa.com/about" />

        <label>Propuesta de Valor:</label>
        <input type="text" name="propuesta_valor" value="{propuesta_valor or ''}" placeholder="Ej: Automatización B2B, eficiencia, etc."/>

        <label>Contexto:</label>
        <input type="text" name="contexto_prov" value="{contexto_prov or ''}" placeholder="Ej: Lanzamiento, Expo, etc."/>

        <div style="display:flex; flex-direction: column; gap: 10px; margin-top: 10px;">
            <button type="submit" name="accion" value="guardar_custom_fields">💾 Guardar Campos</button>
            <button type="submit" name="accion" value="scrap_proveedor">🔍 Scraping del Proveedor</button>
        </div>
    </form>

    <hr>

    <form method="POST">
        <input type="hidden" name="accion" value="generar_tabla"/>
        <button type="submit" style="background-color: {{ 'green' if acciones_realizadas['generar_tabla'] else '#1E90FF' }};">
            Generar Mails con ChatGPT
        </button>
    </form>

    <hr>
    </details>
  
    
    <details>
    <summary style="cursor: pointer; font-weight: bold;">➕ Exportar</summary>
        <form method="POST">
        <h2>Exportar</h2>
        <label>Formato:</label>
        <select name="formato">
            <option value="xlsx">XLSX</option>
            <option value="csv">CSV</option>
        </select>
        <input type="hidden" name="accion" value="exportar_archivo"/>
        <button type="submit">Exportar</button>
        </form>
    </div>
    </details>
    <div class="container-wide">
        <h2>Base de datos (primeros 50 registros)</h2>
        {tabla_html(df_leads,50)}
    </div>
    </div>

    <div class="content-block">
        {block_text_es}
    </div>
    
    <script>
    document.getElementById("pdf_plan_estrategico").addEventListener("change", function () {{
        const fileInput = this;
        const file = fileInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("pdf_plan_estrategico", file);
        formData.append("accion", "subir_pdf_plan");

        fetch("/", {{
            method: "POST",
            body: formData,
        }})
        .then((resp) => resp.text())
        .then((html) => {{
            const textarea = document.querySelector("textarea[name='plan_estrategico']");
            if (textarea) {{
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, "text/html");
                const value = doc.querySelector("textarea[name='plan_estrategico']").value;
                textarea.value = value;
            }}
        }})
        .catch((error) => {{
            console.error("Error al subir el PDF:", error);
        }});
    }});
    
    function resaltarVariables() {{
        const editor = document.getElementById("editor");
        const textoPlano = editor.innerText;
        const conHTML = textoPlano.replace(/{{(.*?)}}/g, "<span class='var'>{{$1}}</span>")
                                .replace(/{{/g, "{{")  // Escapa por si acaso
                                .replace(/}}/g, "}}");
        editor.innerHTML = conHTML;
        colocarCursorAlFinal(editor);
    }}

    function colocarCursorAlFinal(element) {{
        const range = document.createRange();
        const sel = window.getSelection();
        range.selectNodeContents(element);
        range.collapse(false);
        sel.removeAllRanges();
        sel.addRange(range);
    }}

    function guardarContenidoEditor() {{
        const editor = document.getElementById("editor");
        const contenido = editor.innerText;
        document.getElementById("prompt_oculto").value = contenido;
    }}  
    </script>
    
    <div id="scrap-progress" style="margin-top:20px; text-align:center; display:none;">
    <div style="color:white; font-weight:bold;" id="progress-text">Scraping: 0 de 0 (0%)</div>
    <div style="width:80%; margin:auto; background:#444; border-radius:10px; overflow:hidden;">
        <div id="progress-bar" style="height:20px; background:#1E90FF; width:0%;"></div>
    </div>
    </div>

    <script>
    function actualizarProgresoScraping() {{
    fetch("/progreso_scrap")
        .then(resp => resp.json())
        .then(data => {{
        if (data.total > 0) {{
            document.getElementById("scrap-progress").style.display = "block";
            document.getElementById("progress-bar").style.width = data.porcentaje + "%";
            document.getElementById("progress-text").innerText = 
            "Scraping: " + data.procesados + " de " + data.total + " (" + data.porcentaje + "%)";
            
            if (data.procesados < data.total) {{
            setTimeout(actualizarProgresoScraping, 1000);
            }}
        }}
        }});
    }}
    document.addEventListener("DOMContentLoaded", () => {{
        document.querySelectorAll(".cell-collapsible").forEach(cell => {{
            cell.addEventListener("click", () => {{
                cell.classList.toggle("expanded");
            }});
        }});
    }});
    function clasificarTodo() {{
        const acciones = ["clasificar_puestos", "clasificar_areas", "clasificar_industrias"];

        acciones.forEach(accion => {{
            const formData = new FormData();
            formData.append("accion", accion);

            fetch("/", {{
                method: "POST",
                body: formData
            }})
            .then(resp => resp.text())
            .then(data => {{
                console.log(`✅ Acción completada: ${{accion}}`);
            }})
            .catch(err => {{
                console.error(`❌ Error al ejecutar ${{accion}}:`, err);
            }});
        }});

        alert("🛠️ Clasificación en proceso (ver consola para detalles)");
    }}
    
    function toggleDropdown() {{
        const dropdown = document.getElementById("dropdownMenu");
        dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
    }}
    function toggleDropdown() {{
        const dropdown = document.getElementById("dropdownMenu");
        const isVisible = dropdown.style.display === "block";
        dropdown.style.display = isVisible ? "none" : "block";
    }}

    document.addEventListener("click", function(event) {{
        const dropdown = document.getElementById("dropdownMenu");
        const button = event.target.closest("button");

        // Si haces clic fuera del menú y no fue en el botón, ciérralo
        if (!event.target.closest("#dropdownMenu") && !button) {{
            dropdown.style.display = "none";
        }}
    }});                                                                                                
    function resaltarVariablesMails() {{
    const editor = document.getElementById("editor_mails");
    const textoPlano = editor.innerText;
    const conHTML = textoPlano.replace(/{{{{(.*?)}}}}/g,
        '<span class="var">{{{{$1}}}}</span>');
    editor.innerHTML = conHTML;
    colocarCursorAlFinal(editor);
    }}

    function guardarContenidoEditorMails() {{
    const editor = document.getElementById("editor_mails");
    const contenido = editor.innerText;
    document.getElementById("prompt_mails_oculto").value = contenido;
    }}
    </script>


    <a href="/logout" style="color: #FF4C4C; text-decoration: none; display: block; margin-top: 10px;">
    🚪 Cerrar sesión
    </a>
    </body>
    <div id="loader" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9999;text-align:center;padding-top:200px;">
    <div style="color:white;font-size:20px;">⏳ Cargando datos... por favor espera</div>
    <div class="spinner"></div>
    </div>
    <div class="scrap-container">
        <h3>Logs de Scraping</h3>
        <pre>{{ logs_text }}</pre>
    </div>
    

    </html>
    """
    # Rellenar valores dinámicos para botones
    #for clave, valor in acciones_realizadas.items():
    #    page_html = page_html.replace(f"{{{{ acciones_realizadas['{clave}'] }}}}", str(valor).lower())
    #page_html = page_html.replace("{descripcion_proveedor}", str(descripcion_proveedor or ""))
    #page_html = page_html.replace("{productos_proveedor}", str(productos_proveedor or ""))
    #page_html = page_html.replace("{mercado_proveedor}", str(mercado_proveedor or ""))
    #page_html = page_html.replace("{icp_proveedor}", str(icp_proveedor or ""))
    
    prompt_chatgpt = cargar_prompt_desde_archivo()
    prompt_mails = cargar_prompt_mails_original()

    page_html = page_html.replace("{ prompt_chatgpt }", prompt_chatgpt or "")
    return page_html


@app.route("/progreso_scrap")
def progreso_scrap():
    porcentaje = 0
    if scraping_progress["total"] > 0:
        porcentaje = int(scraping_progress["procesados"] / scraping_progress["total"] * 100)
    return {"porcentaje": porcentaje, "total": scraping_progress["total"], "procesados": scraping_progress["procesados"]}



if __name__ == "__main__":
    print("[LOG] Inicia la app con la modificación para parsear JSON con llaves.")
    app.run(debug=True, port=5000)

    
    