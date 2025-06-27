# login.py
from flask import Flask, request, redirect, url_for, session, render_template_string
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import uuid
from cryptography.fernet import Fernet
import os
import re
from concurrent.futures import ThreadPoolExecutor



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
            "EMPRESA_DESCRIPCION": "ND",
            "EMPRESA_PRODUCTOS_SERVICIOS": "ND",
            "EMPRESA_INDUSTRIAS_TARGET": "ND"
        }
    texto_scrap = (cortar_al_limite(str(row.get("scrapping", "")), 3000) + "\n" + cortar_al_limite(str(row.get("Scrapping Adicional", "")), 3000)).strip()
    texto_scrap = texto_scrap[:8000] 
    prompt = f"""
Eres un analista experto en inteligencia de negocios. Tu tarea es analizar el siguiente texto extraído del sitio web de una empresa y devolver un resumen de alta calidad en formato JSON, sin explicaciones adicionales. Extrae únicamente lo que se pueda inferir del texto, evitando suposiciones.

El formato de salida debe ser exactamente el siguiente:

{{
  "EMPRESA_DESCRIPCION": "Resumen claro y conciso sobre a qué se dedica la empresa. Si no se puede determinar, responde con 'ND'",
  "EMPRESA_PRODUCTOS_SERVICIOS": "Lista breve o resumen de los productos y/o servicios ofrecidos. Si no se puede determinar, responde con 'ND'",
  "EMPRESA_INDUSTRIAS_TARGET": "Industrias o sectores a los que sirve o está orientada la empresa. Si no se puede determinar, responde con 'ND'"
}}

Texto a analizar (scrapping del sitio web de la empresa):
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
def cortar_al_limite(texto, max_chars=3000):
    texto = texto.strip().replace("\n", " ")
    if len(texto) <= max_chars:
        return texto
    corte = texto[:max_chars]
    ultimo_punto = corte.rfind(".")
    return corte[:ultimo_punto+1] if ultimo_punto != -1 else corte


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



#####################################
# 2) Función para analizar con ChatGPT
#    el texto crudo del proveedor y
#    extraer la info solicitada
#####################################
def analizar_proveedor_scraping_con_chatgpt(texto_scrapeado: str) -> dict:

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

Eres un analista experto en inteligencia comercial. A partir del siguiente texto obtenido del sitio web de una empresa (scrapeado sin formato), tu tarea es identificar y sintetizar información clave del negocio. Devuelve la respuesta exclusivamente en **formato JSON**, sin explicaciones adicionales ni texto extra.

Instrucciones:
- Si algún dato no puede determinarse con claridad, devuelve "ND" en ese campo, excepto en Industrias, eso piensa, se creativo.
- Si puedes inferir información relevante (como industrias o ICP), hazlo con base en los productos, servicios, lenguaje del texto o clientes mencionados.
- En industrias si puedes inferir, traite industria a la que serían sus productoso servicios o ideal
- Mantén los textos concisos y profesionales.

Formato de salida esperado:

{{
  "Nombre de la Empresa": "Nombre tal como aparece en el texto (si aplica). Si no aparece, pon '-'",
  "Objetivo": "Propósito, misión o enfoque principal de la empresa. Qué hace",
  "Productos o Servicios": "Resumen o listado de lo que ofrece la empresa.",
  "Industrias": "Industrias o sectores a los que sirve. a quienes, hazlo en base al escrapping, infiere",
  "Clientes o Casos de Exito": "Empresas mencionadas como clientes o ejemplos de casos.",
  "ICP": "-"
}}

Texto extraído del sitio web:
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
        print("[LOG] Respuesta ChatGPT (Análisis proveedor):", content)

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
    """"""
    if client is None:
        print("[ERROR] 'client' es None, no se puede llamar la API.")
        return {

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
    prompt = f""""""

    prompt = _limpiar_caracteres_raros(prompt)
    print("\n📤 PROMPT ENVIADO A CHATGPT:\n" + prompt)
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
        print("\n📥 RESPUESTA DE CHATGPT:\n" + content)
        # Intentar parsear JSON
        try:
            parsed = json.loads(content)

        except Exception as ex:
            print("[ERROR] No se pudo parsear JSON en leads:")
            print("Contenido recibido:", content)
            print("Excepción:", ex)
            # Fallback: poner todo en "Personalization" si falla


        return {

        }
    except Exception as e:
        print("[ERROR] Al invocar ChatGPT (leads):", e)
        return {

        }
#Prompts individuales
def prompt_reply_rate_email(row: pd.Series) -> str:
    return f"""
Quiero que actúes como un especialista en ventas B2B con enfoque en generación de citas de alto valor. 
Tu tarea es redactar correos fríos personalizados, breves y efectivos, siguiendo la fórmula “25% Reply Rate Email Formula”.
📌 CONTEXTO DE LOS DATOS (INPUTS)
Estoy trabajando con una tabla que contiene información de prospectos, con las siguientes columnas clave:
First name
Last name
Title → Puesto del prospecto (ej. Director de Marketing)
Company Name
Company Industry → Industria específica en la que opera
Location → Ciudad, estado o país
Propuesta de valor de mi empresa → Texto o resumen de la solución que quiero ofrecer (puede ser distinto por segmento)
(Opcional, se obtiene del scrapping) Caso de éxito relevante → Referencia breve a un cliente similar con un resultado medible

📩 OBJETIVO DEL CORREO
El correo debe estar diseñado para obtener una respuesta que derive en una llamada o reunión.

🧱 ESTRUCTURA QUE DEBES USAR
[Personalización]
 Comienza con una frase relevante basada en el puesto, empresa, logros públicos o tipo de industria del prospecto. Puede provenir de su LinkedIn, sitio web o de su contexto empresarial.

[Nuestra propuesta de valor]
 Resume qué hace nuestra empresa y cómo puede ayudar a ese tipo de perfil, industria o empresa.

[Segmentación clara]
 Menciona de forma específica el tipo de empresa, ubicación o función del prospecto para que sienta que el mensaje fue escrito para él.

[Objetivo o desafío del prospecto]
 Muestra que comprendes lo que esa persona quiere lograr (ej. más visibilidad, eficiencia, ventas, automatización, control, etc.).

[Caso de uso o promesa] (opcional)
 Si tienes un caso de éxito relevante o un resultado similar, menciona de forma breve el beneficio logrado.

[Cliffhanger + CTA]
 Cierra con una invitación clara y directa a agendar una llamada o revisar un plan diseñado para ese tipo de empresa.

✍️ INSTRUCCIONES DE ESTILO
Longitud máxima: 130 palabras
Tono: Profesional, directo y personalizado
Evita lenguaje genérico o plantillado
Escribe como si lo fueras a mandar a un tomador de decisión ocupado

✅ INPUTS

Info del contacto:
First name: {row.get("First name", "-")}
Title: {row.get("Title", "-")}
Company Name: {row.get("Company Name", "-")}
Company Industry: {row.get("Company Industry", "-")}
Location: {row.get("Location", "-")}
scrapping de web del contacto: ({cortar_al_limite(str(row.get('scrapping', '-')), 3000)} {cortar_al_limite(str(row.get('Scrapping Adicional', '-')), 3000)})

Info de nosotros:
Propuesta de valor de mi empresa: {descripcion_proveedor}
Caso de éxito: (Opcional, en base al scrapp del contacto)
scrapping de nuestra web: {plan_estrategico}


✅ EJEMPLO DE OUTPUT ESPERADO (no uses estos datos, son solo de ejemplo)
Hola Jonathan,
Vi que lideras Trade Marketing y Category Management en Alpura, una marca clave en la industria láctea mexicana.
Desde MARKETPRO, ayudamos a directores como tú a mejorar la eficiencia en la ejecución y control en punto de venta, creando experiencias consistentes en canales físicos y digitales.
Trabajamos con empresas de consumo como la tuya para perfeccionar la conexión con el shopper, reforzando estrategia de marca con ejecución en PDV, capacitación y marketing omnicanal.
Tengo un plan que podría incrementar la visibilidad y conversión en tus principales cadenas de retail.
¿Te va bien una llamada esta semana para mostrártelo?
Saludos



La salida debe ser únicamente el texto del cuerpo del correo, sin encabezado, sin firma, sin explicación.
"""

def prompt_one_sentence_email(row: pd.Series) -> str:
    return f"""creame un mail de one_sentence_email""" 
def prompt_asking_for_introduction(row: pd.Series) -> str:
    return f"""creame un mail de asking_for_introduction""" 
def prompt_ask_for_permission(row: pd.Series) -> str:
    return f"""creame un mail de ask_for_permission""" 
def prompt_loom_video(row: pd.Series) -> str:
    return f"""creame un mail de loom_video""" 
def prompt_free_sample_list(row: pd.Series) -> str:
    return f"""creame un mail de loom_video""" 

def generar_email_por_estrategia(row: pd.Series, prompt_func, col_name: str) -> str:
    if pd.notnull(row.get(col_name)) and row.get(col_name) != "-":
        return row.get(col_name)  # ya está generado

    prompt = prompt_func(row)

    # 🖨️ Imprimir en el log
    print(f"\n\n[LOG - PROMPT para {col_name}]")
    print(f"Contacto: {row.get('First name', '-') or '-'} {row.get('Last name', '-') or '-'}")
    print(prompt)
    print("-" * 60)

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,  
            temperature=0.7,
            timeout=30
        )
        content = response.choices[0].message.content.strip()
        print(f"\n[LOG - RESPUESTA para {col_name}]\n{content}\n" + "-"*60)
        return content
    except Exception as e:
        print(f"[ERROR] Falló generación de '{col_name}': {e}")
        return "-"


def procesar_leads():
    """Scrapea website de cada lead y rellena df_leads con el texto."""
    global df_leads
    if df_leads.empty:
        print("[LOG] df_leads vacío. No se hace nada en procesar_leads.")
        return

    needed_cols = [
    ]
    for c in needed_cols:
        if c not in df_leads.columns:
            df_leads[c] = ""
    estrategias_cols = [
        "Strategy - Reply Rate Email",
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

def generar_contenido_para_todos(batch_size=10):
    """Itera sobre df_leads en bloques y llama a ChatGPT para generar estrategias de email."""
    global df_leads
    if df_leads.empty:
        print("[LOG] df_leads vacío, no generamos contenido.")
        return

    estrategias = [
        ("Strategy - Reply Rate Email", prompt_reply_rate_email),
        # Puedes activar más si quieres velocidad menor:
        # ("Strategy - One Sentence Email", prompt_one_sentence_email),
        # ("Strategy - Asking for an Introduction", prompt_asking_for_introduction),
        # ("Strategy - Ask for Permission", prompt_ask_for_permission),
        # ("Strategy - Loom Video", prompt_loom_video),
        # ("Strategy - Free Sample List", prompt_free_sample_list),
    ]

    for i in range(0, len(df_leads), batch_size):
        batch = df_leads.iloc[i:i+batch_size]
        for idx, row in batch.iterrows():
            for col_name, prompt_func in estrategias:
                try:
                    if pd.notnull(df_leads.at[idx, col_name]) and df_leads.at[idx, col_name] != "-":
                        continue  # Ya existe
                    df_leads.at[idx, col_name] = generar_email_por_estrategia(row, prompt_func, col_name)
                except Exception as e:
                    print(f"[ERROR] Falló idx={idx}, col={col_name}: {e}")
        print(f"[INFO] Procesado batch {i} a {i+batch_size-1}")


def cleanup_leads():
    """Reemplaza NaN, None y corchetes en las columnas de texto final."""
    global df_leads
    if df_leads.empty:
        return
    cols_to_clean = [
        "Strategy - Reply Rate Email", "Strategy - One Sentence Email",
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

def remove_illegal_chars(val):
    if isinstance(val, str):
        return re.sub(r'[\x00-\x1F\x7F]', '', val)
    return val


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
        "Strategy - Reply Rate Email", "Strategy - One Sentence Email",
        "Strategy - Asking for an Introduction", "Strategy - Ask for Permission",
        "Strategy - Loom Video", "Strategy - Free Sample List", "super_scrapping",
        "scrapping", "URLs on WEB", "Scrapping Adicional"
    ]
    columnas_moradas = {"area", "departamento", "Nivel Jerarquico", "Strategy - Reply Rate Email", "Industria Mayor", "scrapping", "URLs on WEB", "Scrapping Adicional", "EMPRESA_DESCRIPCION", "EMPRESA_PRODUCTOS_SERVICIOS", "EMPRESA_INDUSTRIAS_TARGET"}
    thead = "".join(
        f"<th class='{'col-ancha ' if col in anchas else ''}{'highlighted' if col in columnas_moradas else ''}'>{col}</th>"
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

        if accion == "clasificar_global":
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
            #CG Clasificar area---------------------------------
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
            #CG Clasificar industria mayor---------------------------------
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
            #if not df_leads.empty:
                #df_leads["scrapping_proveedor"] = sc

            status_msg += "Scraping y análisis del proveedor completado.<br>"
  
        if accion == "scrapp_leads_on":
            print(f"[INFO] Scraping paralelo iniciado")
            if df_leads.empty:
                status_msg += "No hay leads para aplicar scraping tras scrap del proveedor.<br>"
            else:
                if "scrapping" not in df_leads.columns:
                    df_leads["scrapping"] = "-"
                if "URLs on WEB" not in df_leads.columns:
                    df_leads["URLs on WEB"] = "-"
                if "Scrapping Adicional" not in df_leads.columns:
                    df_leads["Scrapping Adicional"] = "-"
                scraping_progress["total"] = len(df_leads)
                scraping_progress["procesados"] = 0
                scrap_cache = {}          # cache para scrapping de sitio
                urls_cache = {}           # cache para URLs on WEB
                adicional_cache = {}      # cache para scraping adicional
                # ───────── FUNCIÓN: Scraping principal y URLs ─────────
                def scrapear_lead(idx_row_tuple):
                    idx, row = idx_row_tuple
                    url = str(row.get(mapeo_website, "")).strip()
                    resultado = {"scrapping": "-", "urls": "-"}

                    if url:
                        if url in scrap_cache:
                            resultado["scrapping"] = scrap_cache[url]
                        else:
                            try:
                                resultado["scrapping"] = realizar_scraping(url)
                                scrap_cache[url] = resultado["scrapping"]
                            except Exception as e:
                                print(f"[ERROR] Scraping lead idx={idx}: {e}")

                        if url in urls_cache:
                            resultado["urls"] = urls_cache[url]
                        else:
                            try:
                                resultado["urls"] = extraer_urls_de_web(url)
                                urls_cache[url] = resultado["urls"]
                            except Exception as e:
                                print(f"[ERROR] Extrayendo URLs idx={idx}: {e}")

                    return (idx, resultado)
                                                
                # ───────── FUNCIÓN: Scraping Adicional ─────────
                def scrapear_adicional(idx_row_tuple):
                    idx, row = idx_row_tuple
                    urls_csv = str(row.get("URLs on WEB", "")).strip()

                    if urls_csv in adicional_cache:
                        return (idx, adicional_cache[urls_csv])

                    resultado = "-"
                    if urls_csv and urls_csv != "-":
                        try:
                            resultado = realizar_scrap_adicional(urls_csv)
                            adicional_cache[urls_csv] = resultado
                        except Exception as e:
                            print(f"[ERROR] Scraping adicional idx={idx}: {e}")
                    return (idx, resultado)


                # ───────── Ejecutar scraping en paralelo ─────────
                with ThreadPoolExecutor(max_workers=10) as executor:
                    resultados = list(executor.map(scrapear_lead, df_leads.iterrows()))
                for idx, res in resultados:
                    df_leads.at[idx, "scrapping"] = res["scrapping"]
                    df_leads.at[idx, "URLs on WEB"] = res["urls"]
                    scraping_progress["procesados"] += 1

                status_msg += "✅ Scraping de leads y URLs ejecutado en paralelo.<br>"

                # ───────── Scraping adicional ─────────
                with ThreadPoolExecutor(max_workers=10) as executor:
                    adicionales = list(executor.map(scrapear_adicional, df_leads.iterrows()))
                for idx, texto in adicionales:
                    df_leads.at[idx, "Scrapping Adicional"] = texto

                status_msg += "✅ Scraping adicional ejecutado en paralelo.<br>"

                # ───────── Generar info de empresa con ChatGPT ─────────
                if "EMPRESA_DESCRIPCION" not in df_leads.columns:
                    df_leads["EMPRESA_DESCRIPCION"] = "-"
                if "EMPRESA_PRODUCTOS_SERVICIOS" not in df_leads.columns:
                    df_leads["EMPRESA_PRODUCTOS_SERVICIOS"] = "-"
                if "EMPRESA_INDUSTRIAS_TARGET" not in df_leads.columns:
                    df_leads["EMPRESA_INDUSTRIAS_TARGET"] = "-"

                for idx, row in df_leads.iterrows():
                    result = generar_info_empresa_chatgpt(row)
                    for key, val in result.items():
                        df_leads.at[idx, key] = val

                status_msg += "✅ Información de empresa generada con éxito.<br>"


        elif accion == "generar_tabla":
            procesar_leads()
            generar_contenido_para_todos(batch_size=10)
            acciones_realizadas["generar_tabla"] = True
            status_msg += "Leads procesados y contenido de ChatGPT generado.<br>"


        elif accion == "exportar_archivo":
            formato = request.form.get("formato", "csv")
            if df_leads.empty:
                status_msg += "No hay leads para exportar.<br>"
            else:
                # Crea una copia del df sin la columna que quieres omitir
                df_export = df_leads.copy().applymap(remove_illegal_chars)
                if formato == "csv":
                    csv_output = io.StringIO()
                    df_export.to_csv(csv_output, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL, line_terminator="\n")
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

    block_text_es = """"""


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
        <title>ClickerMatch</title>
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
            th.highlighted {{
                background-color: #a020f0; /* morado */
                color: white;
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
                    👤 { session.get("user", "Usuario") }
                </button>
                <div id="dropdownMenu" style="display: none; position: absolute; right: 0; background-color: #1F1F1F; min-width: 200px; box-shadow: 0px 8px 16px rgba(0,0,0,0.4); border-radius: 10px; z-index: 1000; padding: 10px;">
                    <p style="margin: 0; color: white;"><strong>{ session.get("user", "Usuario") }</strong></p>
                    <p style="margin: 0; font-size: 12px; color: #ccc;">{ session.get("correo", "") }</p>
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
        <!-- <button type="button" onclick="clasificarTodo()" style="background-color: {color_puestos};">
            Clasificar (Puestos + Áreas + Industrias)
        </button> -->
        <!-- <details>
        <summary>Clasificadores Individualmente</summary> -->
        <form method="POST" enctype="multipart/form-data">
            <input type="hidden" name="accion" value="clasificar_global"/>
            <button type="submit" style="background-color: {color_puestos};">
                Clasificar
            </button>
        </form>
        <!-- </details> -->
        <form method="POST">
            <input type="hidden" name="accion" value="scrapp_leads_on"/>
            <button type="submit" style="background-color: {color_scrap};">
                Scraping de Leads
            </button>
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
            <!-- <button type="submit" style="background-color: {color_desafios};">
                Determinar Desafíos con IA
            </button> -->
        </form>

                 
    </details> 
    
    
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
            <button type="submit" name="accion" value="scrap_proveedor">🔍 Scrapping de mi sitio</button>
        </div>
    </form>

    </details>
    <form method="POST">
        <input type="hidden" name="accion" value="generar_tabla"/>
        <button type="submit" style="background-color: {{ 'green' if acciones_realizadas['generar_tabla'] else '#1E90FF' }};">
            Generar Mails con ChatGPT
        </button>
    </form>    
    <!--
    <details>
    <summary style="cursor: pointer; font-weight: bold;">🧠 Edición de IA Prompts</summary>           
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
    </details>
    -->
      
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

    
    