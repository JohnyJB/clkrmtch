# login.py
from flask import Flask, request, redirect, url_for, session, render_template_string, render_template
from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import uuid
from cryptography.fernet import Fernet
import os
import re
from concurrent.futures import ThreadPoolExecutor
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
from pdfminer.high_level import extract_text
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
    <link rel="icon" type="image/x-icon" href="{{ url_for('static', filename='favicon.ico') }}">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500&display=swap" rel="stylesheet">
    <style>
        body {
            background: url('/static/background.png') no-repeat center center fixed;
            background-size: cover;
            color: #FFFFFF;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            margin: 0; padding: 0;
            text-align: center;
        }
        .container {
            max-width: 300px;
            margin: 60px auto;
            background-color: #FFFFFF;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(30,144,255,0.3);
            color: #333;
        }
        input[type="text"], input[type="email"], input[type="password"] {
            background-color: #f9f9f9;
            border: 1px solid #1E90FF;
            color: #333;
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border-radius: 8px;
        }
        button {
            width: 100%;
            padding: 10px;
            background: linear-gradient(45deg, #1E90FF, #00BFFF);
            border: none;
            color: #fff;
            cursor: pointer;
            font-weight: bold;
            font-size: 16px;
            margin-top: 10px;
        }
        button:hover {
            background-color: linear-gradient(45deg, #00BFFF, #1E90FF);
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



#Prompts
prompt_strategy = """
Quiero que actúes como un especialista en ventas B2B con enfoque en generación de citas de alto valor. 
Tu tarea es redactar correos fríos personalizados, breves y efectivos, siguiendo la fórmula “25% Reply Rate Email Formula”.
📌 CONTEXTO DE LOS DATOS (INPUTS)
Estoy trabajando con una tabla que contiene información de prospectos, con las siguientes columnas clave:
First name
Last name
Title → Puesto del prospecto (ej. Director de Marketing Digital)
Area → Area dentro de la empresa
Departamento → Departamento delntro del area de la empresa
Nivel Jerarquico → Si es Director General, Director, Gerente, Ejecutivo o Colaborador dentro de la empresa
Company Name → Empresa del prospecto
Company Industry → Industria específica en la que opera la empresa del prospecto
Location → Ciudad, estado o país
Descripcion → A que se dedica la Empresa; se obtiene del scrapping de web del contacto
PyS → Que productos o servicios ofrece; se obtiene del scrapping de web del contacto
Objetivo → A que mercado objetivo se dirige; se obtiene del scrapping de web del contacto

Propuesta de valor de mi empresa → Texto o resumen de la solución que quiero ofrecer (puede ser distinto por segmento)
(Opcional, se obtiene del scrapping) Caso de éxito relevante → Referencia breve a un cliente similar con un resultado medible


📩 OBJETIVO DEL CORREO
El objetivo es obtener una respuesta que derive en responder el mail, una llamada o reunión con el prospecto.

🧱 ESTRUCTURA OBLIGATORIA DEL CORREO (5 PÁRRAFOS)
El correo debe tener exactamente 5 párrafos separados por doble salto de línea (\n\n). Cada párrafo debe contener una sola idea. No mezcles ideas ni omitas líneas en blanco.

🔒 INSTRUCCIÓN ESTRICTA DE FORMATO
Siempre incluye el Párrafo 1 (saludo y personalización). Nunca lo omitas.

Nunca fusiones el saludo con el segundo párrafo.

Si algún dato falta, escribe una frase neutra, pero nunca elimines el párrafo.

El modelo debe generar 5 bloques visuales claramente separados.

1. PÁRRAFO 1: Saludo + Personalización del Prospecto (natural, sin sonar robótico)
Saluda por su nombre.

Menciona su rol y contribución según el título:

Si el título contiene “Director”, “Head”, “VP”, “CEO”, “General Manager”, etc.: Destaca que su liderazgo o visión es clave para la estrategia de la empresa, pero sin exagerar ni usar adjetivos subjetivos.

Si el título contiene “Manager”, "Gerente": Enfócate en su impacto operativo o contribución al área, sin atribuirle decisiones estratégicas generales.

Si la empresa es reconocida, puedes mencionar brevemente su posición destacada, sin usar palabras como “impresionante” o “admirable”.

🔄 Tono natural y conversacional:
Evita frases genéricas como “Vi que lideras…”, “empresa destacada…”, “seguro es fundamental…”.
Usa frases más reales y humanas como:

“Imagino que desde tu rol has impulsado…”

“Debe ser muy interesante liderar…”

“Veo que están haciendo un gran trabajo en…”


PÁRRAFO 2: Motivo de contacto + Propuesta de Valor + Objetivo del Prospecto + Productos o Mercado

Inicia siempre con:

“Te contacto porque ofrecemos un servicio integral...”
o una variante natural que indique el motivo del mensaje.

Describe qué haces y cómo has ayudado a empresas similares, sin sonar vendedor ni mencionar el nombre de tu empresa.

Refuerza que entiendes lo que esa persona quiere lograr (visibilidad, eficiencia, ventas, automatización, etc.), a resolver desafíos como los suyos.

Cuando sea posible, menciona de forma natural alguno de los siguientes elementos del prospecto (basado en el scrapping):

Productos o líneas clave

Servicios ofrecidos

Tipo de clientes o mercados objetivo

PÁRRAFO 3: Gancho o Prueba Social

Menciona que tienes un plan concreto que ya ha funcionado con empresas similares.

Si hay un caso de éxito específico, inclúyelo brevemente.

PÁRRAFO 4: Llamado a la Acción (CTA)

Invita directamente a agendar una llamada o revisar el plan.

Ejemplos:

¿Te va bien una llamada esta semana para mostrártelo?

¿Te puedo enseñar cómo funcionaría en tu operación?

¿Lo revisamos juntos esta semana?

PÁRRAFO 5: Despedida limpia (sin firma)

Incluye solamente una frase de cierre profesional como:

Saludos

Será un gusto platicar contigo

Estoy a tus órdenes

Gracias por tu tiempo

❌ No incluyas tu nombre, empresa, cargo ni ningún dato de contacto.

✍️ INSTRUCCIONES DE ESTILO
Longitud máxima: 130 palabras

Tono: Profesional, directo y personalizado

Evita lenguaje genérico, frases cliché o plantilladas

Escribe como si fuera para un tomador de decisión ocupado

✅ INPUTS

Info del contacto:
Nombre: {row.get("First name", "-")}
Puesto: {row.get("Title", "-")}
Area: {row.get("Area", "(no se sabe)")}
Departamento: {row.get("Departamento", "(no se sabe)")}
Nivel Jerarquico: {row.get("Nivel Jerarquico", "(no se sabe)")}
Company Name: {row.get("Company Name", "(no se sabe)")}
Company Industry: {row.get("Company Industry", "-")}
Location: {row.get("Location", "-")}
scrapping de web del contacto: ({cortar_al_limite(str(row.get('scrapping', '-')), 3000)} {cortar_al_limite(str(row.get('Scrapping Adicional', '-')), 3000)})

Info de nosotros:
Propuesta de valor de mi empresa: {descripcion_proveedor}
Caso de éxito: (Opcional, en base al scrapp del contacto)
scrapping de nuestra web: {plan_estrategico}


✅ EJEMPLO DE OUTPUT ESPERADO (no uses estos datos, son solo de ejemplo)
Hola Mónica,

Imagino que desde tu rol al frente de Trade Marketing en Industrias Tajín has impulsado iniciativas clave para fortalecer la ejecución en tienda y conectar mejor con el shopper, especialmente en una marca con tanta presencia en alimentos y bebidas.

Te contacto porque ofrecemos un servicio integral de Publicidad en Punto de Venta, incluyendo producción, instalación y mantenimiento de materiales a nivel nacional. Hemos ayudado a marcas como la tuya a incrementar visibilidad y consistencia en puntos de venta clave.

Contamos con un plan probado que ya ha generado buenos resultados en empresas similares del sector.

¿Te gustaría agendar una llamada esta semana para mostrarte cómo podríamos aplicarlo en tu operación?

Será un gusto conversar


La salida debe ser únicamente el texto del cuerpo del correo, sin encabezado, sin firma, sin explicación.
"""

# inicializar prompt strategy
prompt_strategy_default = """
Quiero que actúes como un especialista en ventas B2B con enfoque en generación de citas de alto valor. 
Tu tarea es redactar correos fríos personalizados, breves y efectivos, siguiendo la fórmula “25% Reply Rate Email Formula”.
📌 CONTEXTO DE LOS DATOS (INPUTS)
Estoy trabajando con una tabla que contiene información de prospectos, con las siguientes columnas clave:
First name
Last name
Title → Puesto del prospecto (ej. Director de Marketing Digital)
Area → Area dentro de la empresa
Departamento → Departamento delntro del area de la empresa
Nivel Jerarquico → Si es Director General, Director, Gerente, Ejecutivo o Colaborador dentro de la empresa
Company Name → Empresa del prospecto
Company Industry → Industria específica en la que opera la empresa del prospecto
Location → Ciudad, estado o país
Descripcion → A que se dedica la Empresa; se obtiene del scrapping de web del contacto
PyS → Que productos o servicios ofrece; se obtiene del scrapping de web del contacto
Objetivo → A que mercado objetivo se dirige; se obtiene del scrapping de web del contacto

Propuesta de valor de mi empresa → Texto o resumen de la solución que quiero ofrecer (puede ser distinto por segmento)
(Opcional, se obtiene del scrapping) Caso de éxito relevante → Referencia breve a un cliente similar con un resultado medible


📩 OBJETIVO DEL CORREO
El objetivo es obtener una respuesta que derive en responder el mail, una llamada o reunión con el prospecto.

🧱 ESTRUCTURA OBLIGATORIA DEL CORREO (5 PÁRRAFOS)
El correo debe tener exactamente 5 párrafos separados por doble salto de línea (\n\n). Cada párrafo debe contener una sola idea. No mezcles ideas ni omitas líneas en blanco.

🔒 INSTRUCCIÓN ESTRICTA DE FORMATO
Siempre incluye el Párrafo 1 (saludo y personalización). Nunca lo omitas.

Nunca fusiones el saludo con el segundo párrafo.

Si algún dato falta, escribe una frase neutra, pero nunca elimines el párrafo.

El modelo debe generar 5 bloques visuales claramente separados.

1. PÁRRAFO 1: Saludo + Personalización del Prospecto (natural, sin sonar robótico)
Saluda por su nombre.

Menciona su rol y contribución según el título:

Si el título contiene “Director”, “Head”, “VP”, “CEO”, “General Manager”, etc.: Destaca que su liderazgo o visión es clave para la estrategia de la empresa, pero sin exagerar ni usar adjetivos subjetivos.

Si el título contiene “Manager”, "Gerente": Enfócate en su impacto operativo o contribución al área, sin atribuirle decisiones estratégicas generales.

Si la empresa es reconocida, puedes mencionar brevemente su posición destacada, sin usar palabras como “impresionante” o “admirable”.

🔄 Tono natural y conversacional:
Evita frases genéricas como “Vi que lideras…”, “empresa destacada…”, “seguro es fundamental…”.
Usa frases más reales y humanas como:

“Imagino que desde tu rol has impulsado…”

“Debe ser muy interesante liderar…”

“Veo que están haciendo un gran trabajo en…”


PÁRRAFO 2: Motivo de contacto + Propuesta de Valor + Objetivo del Prospecto + Productos o Mercado

Inicia siempre con:

“Te contacto porque ofrecemos un servicio integral...”
o una variante natural que indique el motivo del mensaje.

Describe qué haces y cómo has ayudado a empresas similares, sin sonar vendedor ni mencionar el nombre de tu empresa.

Refuerza que entiendes lo que esa persona quiere lograr (visibilidad, eficiencia, ventas, automatización, etc.), a resolver desafíos como los suyos.

Cuando sea posible, menciona de forma natural alguno de los siguientes elementos del prospecto (basado en el scrapping):

Productos o líneas clave

Servicios ofrecidos

Tipo de clientes o mercados objetivo

PÁRRAFO 3: Gancho o Prueba Social

Menciona que tienes un plan concreto que ya ha funcionado con empresas similares.

Si hay un caso de éxito específico, inclúyelo brevemente.

PÁRRAFO 4: Llamado a la Acción (CTA)

Invita directamente a agendar una llamada o revisar el plan.

Ejemplos:

¿Te va bien una llamada esta semana para mostrártelo?

¿Te puedo enseñar cómo funcionaría en tu operación?

¿Lo revisamos juntos esta semana?

PÁRRAFO 5: Despedida limpia (sin firma)

Incluye solamente una frase de cierre profesional como:

Saludos

Será un gusto platicar contigo

Estoy a tus órdenes

Gracias por tu tiempo

❌ No incluyas tu nombre, empresa, cargo ni ningún dato de contacto.

✍️ INSTRUCCIONES DE ESTILO
Longitud máxima: 130 palabras

Tono: Profesional, directo y personalizado

Evita lenguaje genérico, frases cliché o plantilladas

Escribe como si fuera para un tomador de decisión ocupado

✅ INPUTS

Info del contacto:
Nombre: {row.get("First name", "-")}
Puesto: {row.get("Title", "-")}
Area: {row.get("Area", "(no se sabe)")}
Departamento: {row.get("Departamento", "(no se sabe)")}
Nivel Jerarquico: {row.get("Nivel Jerarquico", "(no se sabe)")}
Company Name: {row.get("Company Name", "(no se sabe)")}
Company Industry: {row.get("Company Industry", "-")}
Location: {row.get("Location", "-")}
scrapping de web del contacto: ({cortar_al_limite(str(row.get('scrapping', '-')), 3000)} {cortar_al_limite(str(row.get('Scrapping Adicional', '-')), 3000)})

Info de nosotros:
Propuesta de valor de mi empresa: {descripcion_proveedor}
Caso de éxito: (Opcional, en base al scrapp del contacto)
scrapping de nuestra web: {plan_estrategico}


✅ EJEMPLO DE OUTPUT ESPERADO (no uses estos datos, son solo de ejemplo)
Hola Mónica,

Imagino que desde tu rol al frente de Trade Marketing en Industrias Tajín has impulsado iniciativas clave para fortalecer la ejecución en tienda y conectar mejor con el shopper, especialmente en una marca con tanta presencia en alimentos y bebidas.

Te contacto porque ofrecemos un servicio integral de Publicidad en Punto de Venta, incluyendo producción, instalación y mantenimiento de materiales a nivel nacional. Hemos ayudado a marcas como la tuya a incrementar visibilidad y consistencia en puntos de venta clave.

Contamos con un plan probado que ya ha generado buenos resultados en empresas similares del sector.

¿Te gustaría agendar una llamada esta semana para mostrarte cómo podríamos aplicarlo en tu operación?

Será un gusto conversar


La salida debe ser únicamente el texto del cuerpo del correo, sin encabezado, sin firma, sin explicación.
"""

# inicializar con ese por default
prompt_strategy = prompt_strategy_default



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
            "Descripcion": "ND",
            "PyS": "ND",
            "Objetivo": "ND"
        }
    texto_scrap = (cortar_al_limite(str(row.get("scrapping", "")), 3000) + "\n" + cortar_al_limite(str(row.get("Scrapping Adicional", "")), 3000)).strip()
    texto_scrap = texto_scrap[:8000] 
    prompt = f"""
Eres un analista experto en inteligencia de negocios. Tu tarea es analizar el siguiente texto extraído del sitio web de una empresa y devolver un resumen de alta calidad en formato JSON, sin explicaciones adicionales. Extrae únicamente lo que se pueda inferir del texto, evitando suposiciones.

El formato de salida debe ser exactamente el siguiente:

{{
  "Descripcion": "Resumen claro y conciso sobre a qué se dedica la empresa. Si no se puede determinar, responde con 'ND'",
  "PyS": "Lista breve o resumen de los productos y/o servicios ofrecidos. Si no se puede determinar, responde con 'ND'",
  "Objetivo": "Industrias o sectores a los que sirve o está orientada la empresa. Si no se puede determinar, responde con 'ND'"
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
            "Descripcion": "-",
            "PyS": "-",
            "Objetivo": "-"
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


def realizar_scrapingProv(url: str) -> str:
    import requests
    from bs4 import BeautifulSoup

    url = _asegurar_https(url)
    if not url:
        return "-"

    rutas = [""]  # solo raíz
    texto_total = ""

    for path in rutas:
        try:
            full_url = url.rstrip("/") + path

            headers = {
                "Host": full_url.replace("https://", "").replace("http://", "").split("/")[0],
                "Connection": "keep-alive",
                "Cache-Control": "max-age=0",
                "Upgrade-Insecure-Requests": "1",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept-Language": "es-ES,es;q=0.9"
            }

            print(f"[SCRAPING] Visitando: {full_url}")
            resp = requests.get(full_url, headers=headers, timeout=5, verify=False)

            if resp.status_code == 200:
                sopa = BeautifulSoup(resp.text, "html.parser")
                texto_total = sopa.get_text()
                print("[SCRAPING COMPLETO RAW]")
                print(texto_total[:2000])  # los primeros 2000 chars para debug

            else:
                print(f"[SKIP] Código HTTP {resp.status_code} en {full_url}")

        except Exception as e:
            print(f"[ERROR] al scrapear {full_url}:", e)

        if len(texto_total) >= MAX_SCRAPING_CHARS:
            break

    texto_total = _limpiar_caracteres_raros(texto_total)

    if texto_total.strip():
        print(f"[DEBUG] Retornando scraping completo de longitud: {len(texto_total)}")
        return texto_total[:MAX_SCRAPING_CHARS]
    else:
        print("[DEBUG] Texto vacío tras limpiar, retorna '-'")
        return "-"






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
#
def prompt_reply_rate_email(row: dict) -> str:
    return prompt_strategy.replace(
        "{row.get(\"First name\", \"-\")}", str(row.get("First name", "-") or "-")
    ).replace(
        "{row.get(\"Title\", \"-\")}", str(row.get("Title", "-") or "-")
    ).replace(
        "{row.get(\"Area\", \"(no se sabe)\")}", str(row.get("Area", "(no se sabe)") or "-")
    ).replace(
        "{row.get(\"Departamento\", \"(no se sabe)\")}", str(row.get("Departamento", "(no se sabe)") or "-")
    ).replace(
        "{row.get(\"Nivel Jerarquico\", \"(no se sabe)\")}", str(row.get("Nivel Jerarquico", "(no se sabe)") or "-")
    ).replace(
        "{row.get(\"Company Name\", \"(no se sabe)\")}", str(row.get("Company Name", "(no se sabe)") or "-")
    ).replace(
        "{row.get(\"Company Industry\", \"-\")}", str(row.get("Company Industry", "-") or "-")
    ).replace(
        "{row.get(\"Location\", \"-\")}", str(row.get("Location", "-") or "-")
    ).replace(
        "{cortar_al_limite(str(row.get('scrapping', '-')), 3000)}", cortar_al_limite(str(row.get('scrapping', '-')), 3000)
    ).replace(
        "{cortar_al_limite(str(row.get('Scrapping Adicional', '-')), 3000)}", cortar_al_limite(str(row.get('Scrapping Adicional', '-')), 3000)
    ).replace(
        "{descripcion_proveedor}", descripcion_proveedor
    ).replace(
        "{plan_estrategico}", plan_estrategico
    )


def prompt_one_sentence_email(row: dict) -> str:
    return f"""creame un mail de one_sentence_email""" 
def prompt_asking_for_introduction(row: dict) -> str:
    return f"""creame un mail de asking_for_introduction""" 
def prompt_ask_for_permission(row: dict) -> str:
    return f"""creame un mail de ask_for_permission""" 
def prompt_loom_video(row: dict) -> str:
    return f"""creame un mail de loom_video""" 
def prompt_free_sample_list(row: dict) -> str:
    return f"""creame un mail de loom_video""" 

def generar_email_por_estrategia(row: dict, prompt_func, col_name: str) -> str:
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
            row_dict = row.to_dict()
            for col_name, prompt_func in estrategias:
                try:
                    result = generar_email_por_estrategia(row_dict, prompt_func, col_name)
                    # Sanitizar para evitar floats o None
                    if pd.isnull(result):
                        result = "-"
                    else:
                        result = str(result)
                    df_leads.at[idx, col_name] = result
                except Exception as e:
                    print(f"[ERROR] Falló idx={idx}, col={col_name}: {e}")
        print(f"[INFO] Procesado batch {i} a {i+batch_size-1}")


def cleanup_leads():
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
            # Convierte todo a str explícito
            df_leads[col] = df_leads[col].astype(str)
            # Ahora ya es seguro usar replace
            df_leads[col] = df_leads[col].replace(
                ["NaN", "nan", "None", "none"], "-", regex=True
            )
            # Quitar corchetes si aparecen
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
        return "<p><em>Configura tu lista de contactos</em></p>"

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
    columnas_moradas = {"Area","area", "departamento", "Departamento", "Nivel Jerarquico", "Strategy - Reply Rate Email", "Industria Mayor", "scrapping", "URLs on WEB", "Scrapping Adicional", "Descripcion", "PyS", "Objetivo", "EMPRESA_DESCRIPCION", "EMPRESA_PRODUCTOS_SERVICIOS", "EMPRESA_INDUSTRIAS_TARGET"}
    thead = "".join(
        f"<th class='{'col-ancha ' if col in anchas else ''}{'highlighted' if col in columnas_moradas else ''}'>{col}</th>"
        for col in cols
    )
    rows_html = ""
    for _, row in subset.iterrows():
        row_html = ""
        for col in cols:
            valor = str(row.get(col, "")).strip()

            if col in ["Linkedin", "Company Linkedin Url"]:
                if valor and pd.notna(valor) and valor != "-":
                    row_html += f"""<td><a href="{valor}" target="_blank">
                        <img src="/static/icons/linkedin.png" alt="LinkedIn" style="width:24px; height:24px;">
                    </a></td>"""
                else:
                    row_html += "<td>-</td>"
            elif col == "Logo":
                if valor and pd.notna(valor) and valor.lower().startswith("http"):
                    row_html += f"<td><img src='{valor}' alt='Logo' style='max-height:40px;'/></td>"
                else:
                    row_html += "<td>-</td>"
            else:
                row_html += (
                    f"<td class='col-ancha'><div class='cell-collapsible'>{valor}</div></td>"
                    if col in anchas else
                    f"<td><div class='cell-collapsible'>{valor}</div></td>"
                )
        rows_html += f"<tr>{row_html}</tr>"




    return f"<p><strong></strong></p>" + f"<table><tr>{thead}</tr>{rows_html}</table>"
    #return f"<p><strong>📊 Total Registros: {len(subset)}</strong></p>" + f"<table><tr>{thead}</tr>{rows_html}</table>"


df_temp_upload = pd.DataFrame()
df_leads = pd.DataFrame()
##########################################
# Rutas Flask
##########################################
@app.route("/", methods=["GET","POST"])
def index():
    global df_temp_upload, df_leads, mapeo_nombre_contacto, mapeo_puesto, mapeo_empresa, mapeo_industria, mapeo_website, mapeo_location    
    if "user" not in session:
        return redirect("/login")  # redirige al login principal
    if request.method == "POST":
        leadf = request.files.get("leads_csv")
        if leadf and leadf.filename:
            df_temp_upload = pd.read_csv(leadf)
            return redirect("/map_columns")
        
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
    global prompt_strategy
    global prompt_mails

    status_msg = ""
    
    url_proveedor_global = ""  # Moveremos esto a variable local
    accion = request.form.get("accion", "")
        # Asignar los mapeos con tolerancia a campos vacíos o None
    mapeo_nombre_contacto = (request.form.get("col_nombre") or mapeo_nombre_contacto or "").strip() or mapeo_nombre_contacto
    mapeo_puesto = (request.form.get("col_puesto") or mapeo_puesto or "").strip() or mapeo_puesto
    mapeo_empresa = (request.form.get("col_empresa") or mapeo_empresa or "").strip() or mapeo_empresa
    mapeo_industria = (request.form.get("col_industria") or mapeo_industria or "").strip() or mapeo_industria
    mapeo_website = (request.form.get("col_website") or mapeo_website or "").strip() or mapeo_website
    mapeo_location = (request.form.get("col_location") or mapeo_location or "").strip() or mapeo_location

    if request.method == "POST":
         
        if accion == "guardar_prompt_chatgpt":
            nuevo_prompt = request.form.get("prompt_chatgpt", "").strip()
            prompt_actual = nuevo_prompt
            status_msg += "✅ Prompt actualizado en memoria.<br>"

        elif accion == "guardar_prompt_strategy":
            
            prompt_strategy = request.form.get("prompt_strategy", "").strip()
        elif accion == "guardar_prompt_mails":
            
            prompt_strategy = request.form.get("prompt_strategy", "").strip()
            nuevo = request.form.get("prompt_mails", "").strip()
            prompt_mails = nuevo
            guardar_prompt_mails_en_archivo(nuevo)
            status_msg += "✅ Prompt de mails de estrategia actualizado.<br>"

        elif accion == "reiniciar_prompt_strategy":
            
            prompt_strategy = prompt_strategy_default
            status_msg += "♻️ Prompt strategy reiniciado a valor original.<br>"
        
        if accion == "clasificar_global":
            print("[DEBUG] ENTRÓ A CLASIFICAR_GLOBAL con accion =", accion)
            print("COLUMNAS EN DF_LEADS:", df_leads.columns.tolist())
            print("MAPEO PUESTO:", mapeo_puesto)
            print("MAPEO INDUSTRIA:", mapeo_industria)
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
                        print("[DEBUG] Después de clasificar puestos columnas:", df_leads.columns.tolist())
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

                            if clave_words.issubset(t_words):  # todas las palabras clave están presentes, columnas en el archivo
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
                        df_leads["Departamento"], df_leads["Area"] = zip(*df_leads[mapeo_puesto].map(asignar_areas))
                        print("[DEBUG] Después de clasificar áreas columnas:", df_leads.columns.tolist())
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
                    print("[DEBUG] Después de merge industrias columnas:", df_leads.columns.tolist())
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
                    print("[DEBUG] Columnas finales tras clasificar_global:", df_leads.columns.tolist())

                else:
                    status_msg += "No hay datos para clasificar o falta el archivo catalogoindustrias.csv.<br>"
            except Exception as e:
                status_msg += f"Error al clasificar industrias: {e}<br>"
        
        #Gardar edición de prompt
        if accion == "guardar_prompt_strategy":
            nuevo_prompt = request.form.get("prompt_strategy", "").strip()
            
            prompt_strategy = nuevo_prompt
            status_msg += "✅ Prompt de strategy guardado en memoria.<br>"
        if accion == "reiniciar_prompt_strategy":
            
            prompt_strategy = prompt_strategy_default
            status_msg += "Reiniciar Prompt.<br>"
                
                
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

        if accion == "eliminar_columnas_emails":
            columnas_a_borrar = [
                "Strategy - Reply Rate Email",
                "Strategy - One Sentence Email",
                "Strategy - Asking for an Introduction",
                "Strategy - Ask for Permission",
                "Strategy - Loom Video",
                "Strategy - Free Sample List"
            ]
            eliminadas = []
            for col in columnas_a_borrar:
                if col in df_leads.columns:
                    df_leads.drop(columns=[col], inplace=True)
                    eliminadas.append(col)
            status_msg += f"🗑️ Columnas eliminadas: {', '.join(eliminadas)}<br>" if eliminadas else "No se encontraron columnas para eliminar.<br>"

       
        if accion == "cargar_contactos_db":
            try:
                filtro = request.form.get("filtro_busqueda", "").strip().lower()
                source = request.form.get("source", "").strip().lower()
                industria = request.form.get("industria", "").strip().lower()
                area = request.form.get("area", "").strip().lower()
                departamento = request.form.get("departamento", "").strip().lower()
                tamano = request.form.get("company_employee_count_range", "").strip().lower()

                condiciones = []

                if filtro:
                    condiciones.append(f"""(
                        LOWER(c.first_name) LIKE '%{filtro}%' OR
                        LOWER(c.last_name) LIKE '%{filtro}%' OR
                        LOWER(c.company_name) LIKE '%{filtro}%' OR
                        LOWER(c.company_website) LIKE '%{filtro}%'
                    )""")
                if source:
                    condiciones.append(f"LOWER(c.search) LIKE '%{source}%'")
                if industria:
                    condiciones.append(f"LOWER(e.industria_mayor) LIKE '%{industria}%'")
                if area:
                    condiciones.append(f"LOWER(c.area) LIKE '%{area}%'")
                if departamento:
                    condiciones.append(f"LOWER(c.departamento) LIKE '%{departamento}%'")
                if tamano:
                    condiciones.append(f"LOWER(c.company_employee_count_range) LIKE '%{tamano}%'")

                where_clause = "WHERE " + " AND ".join(condiciones) if condiciones else ""

                # Control del límite
                max_rows_str = request.form.get("max_rows", "10000")
                try:
                    max_rows = int(max_rows_str)
                    if max_rows <= 0:
                        max_rows = 10000
                except:
                    max_rows = 10000

                query_str = f"""
                    SELECT 
                        c.image_link AS "Logo",
                        c.company_name AS "Company Name",
                        c.first_name AS "First name",
                        c.last_name AS "Last name",
                        c.job_title AS "Title",
                        c.area AS "Area",
                        c.departamento AS "Departamento",
                        c.niveljerarquico AS "Nivel Jerarquico",
                        c.email AS "Email",
                        c.profile_link AS "Linkedin",
                        c.location AS "Location",
                        c.company_website AS "Company Website",
                        c.employee_count_start AS "Company Employee Start",
                        c.employee_count_end AS "Company Employee End",
                        c.industries AS "Company Industry",
                        c.industria_mayor AS "Industria Mayor",
                        c.scrapping AS "scrapping",
                        c.urlsonweb AS "URLs on WEB",
                        c.scrappingadicional AS "Scrapping Adicional",
                        c.descripcion AS "Descripcion",
                        c.productos AS "PyS",
                        c.mercado AS "Objetivo",
                        c.mail_strategy AS "Strategy - Reply Rate Email",
                        c.search AS "Lista Search",
                        c.ide AS "IDE"
                    FROM contactos_expandi_historico c
                    {where_clause}
                    ORDER BY c.id ASC
                    LIMIT {max_rows}
                """

                print("\n[DEBUG QUERY PARA PGADMIN]")
                print(query_str)

                # Ejecutar realmente (usa bind seguro aquí si quieres)
                with engine.connect() as conn:
                    result = conn.execute(text(query_str)).mappings().all()
                    df_leads = pd.DataFrame(result)
                    # Reemplazar None / NaN por vacío
                    df_leads = df_leads.fillna("")
                    df_leads = df_leads.applymap(lambda x: "" if x is None else x)
                    num_registros = len(df_leads)
                    status_msg += f"✅ Se cargaron {num_registros} contactos desde la DB.<br>"

                for k in acciones_realizadas:
                    acciones_realizadas[k] = False
                                   
                orden_columnas = [
                        "Logo",
                        "Company Name",
                        "First name",
                        "Last name",
                        "Title",
                        "Area",
                        "Departamento",
                        "Nivel Jerarquico",
                        "Email",
                        "Linkedin",
                        "Location",
                        "Company Website",
                        "Company Employee Start",
                        "Company Employee End",
                        "Company Industry",
                        "Industria Mayor",
                        "scrapping",
                        "URLs on WEB",
                        "Scrapping Adicional",
                        "Descripcion",
                        "PyS",
                        "Objetivo",
                        "Strategy - Reply Rate Email",
                        "Lista Search",
                        "IDE"
                ]

                # Solo las que existan en el dataframe
                columnas_presentes = [col for col in orden_columnas if col in df_leads.columns]
                otras_columnas = [col for col in df_leads.columns if col not in columnas_presentes]

                # Reordenar el dataframe
                df_leads = df_leads[columnas_presentes + otras_columnas]

                # CHECAR MAPEOS
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

                for k in acciones_realizadas:
                    acciones_realizadas[k] = False
                                                
                

            except Exception as e:
                status_msg += f"❌ Error al cargar desde la base de datos: {e}<br>"

        if accion == "cargar_y_mapear_csv":
            try:
                csv_file = request.files.get("csv_file")
                if csv_file and csv_file.filename.endswith(".csv"):
                    df_temp = pd.read_csv(csv_file)
                    columnas_csv = list(df_temp.columns)
                    columnas_db = [
                        "ide", "first_name", "last_name", "profile_link", "job_title",
                        "company_name", "email", "phone", "address", "image_link",
                        "follower_count", "tags", "contact_status", "conversation_status",
                        "object_urn", "public_identifier", "profile_link_public_identifier",
                        "thread", "invited_at", "connected_at", "company_universal_name",
                        "company_website", "employee_count_start", "employee_count_end",
                        "industries", "location", "name", "imported_profile_link", "search"
                    ]
                    # Guardar en sesión temporal
                    session["df_temp_csv"] = df_temp.to_json(orient="split")
                    session["columnas_csv"] = columnas_csv
                    session["columnas_db"] = columnas_db

                    status_msg += f"✅ CSV cargado. Ahora mapea las columnas.<br>"
                    return render_template("mapeo.html", columnas_csv=columnas_csv, columnas_db=columnas_db, status_msg=status_msg)
                else:
                    status_msg += "❌ Sube un archivo CSV válido.<br>"
            except Exception as e:
                status_msg += f"❌ Error al cargar CSV: {e}<br>"

        if accion == "subir_csv_a_db":
            try:
                # Recuperar CSV de sesión
                df_temp = pd.read_json(session.get("df_temp_csv"), orient="split")

                # Construir mapeo
                columnas_db = session.get("columnas_db", [])
                columnas_csv = session.get("columnas_csv", [])

                insert_data = []
                for idx, row in df_temp.iterrows():
                    record = {}
                    for csv_col in columnas_csv:
                        db_col = request.form.get(f"map_{csv_col}")
                        if db_col:
                            record[db_col] = row[csv_col]
                    insert_data.append(record)

                # Insertar en la base
                with engine.connect() as conn:
                    for record in insert_data:
                        # Rellenar faltantes con NULL
                        for col in columnas_db:
                            if col not in record:
                                record[col] = None
                        conn.execute(text(f"""
                            INSERT INTO contactos_expandi_historico ({", ".join(record.keys())})
                            VALUES ({", ".join([":%s" % k for k in record.keys()])})
                        """), record)

                status_msg += f"✅ Se insertaron {len(insert_data)} registros en la base de datos.<br>"
            except Exception as e:
                status_msg += f"❌ Error al insertar en DB: {e}<br>"

        if accion == "subir_csv_a_db":
            try:
                # Recuperar CSV de sesión
                df_temp = pd.read_json(session.get("df_temp_csv"), orient="split")

                # Construir mapeo
                columnas_db = session.get("columnas_db", [])
                columnas_csv = session.get("columnas_csv", [])

                insert_data = []
                for idx, row in df_temp.iterrows():
                    record = {}
                    for csv_col in columnas_csv:
                        db_col = request.form.get(f"map_{csv_col}")
                        if db_col:
                            record[db_col] = row[csv_col]
                    insert_data.append(record)

                # Insertar en la base
                with engine.connect() as conn:
                    for record in insert_data:
                        # Rellenar faltantes con NULL
                        for col in columnas_db:
                            if col not in record:
                                record[col] = None
                        conn.execute(text(f"""
                            INSERT INTO contactos_expandi_historico ({", ".join(record.keys())})
                            VALUES ({", ".join([":%s" % k for k in record.keys()])})
                        """), record)

                status_msg += f"✅ Se insertaron {len(insert_data)} registros en la base de datos.<br>"
            except Exception as e:
                status_msg += f"❌ Error al insertar en DB: {e}<br>"

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
            # Leer todo el archivo primero en un DataFrame
            df_full = pd.read_csv(leadf)
            
            # Obtener el rango
            start_row_str = request.form.get("start_row", "").strip()
            end_row_str = request.form.get("end_row", "").strip()
            
            try:
                start_row = int(start_row_str) if start_row_str else 0
            except:
                start_row = 0
            try:
                end_row = int(end_row_str) if end_row_str else len(df_full) - 1
            except:
                end_row = len(df_full) - 1
            
            # Corregir rangos fuera de límites
            if start_row < 0:
                start_row = 0
            if end_row >= len(df_full):
                end_row = len(df_full) - 1
            
            if start_row > end_row:
                # Si el rango es inválido, crea un DataFrame vacío con las mismas columnas
                df_leads = pd.DataFrame(columns=df_full.columns)
                status_msg += f"⚠️ Rango inválido: start_row={start_row}, end_row={end_row}. Se cargaron 0 filas.<br>"
            else:
                # Si el rango es válido, filtra solo esas filas
                df_leads = df_full.iloc[start_row:end_row+1].copy()
                status_msg += f"✅ Leads cargados del {start_row} al {end_row}: {len(df_leads)} filas.<br>"

                                                                

            # Si quieres dejarlo como antes:
            # -> Nada de mapeo temporal, solo directo

            # Asegurar banderas
            for k in acciones_realizadas:
                acciones_realizadas[k] = False

            status_msg += (
                f"Leads CSV cargado. Filas totales={len(df_full)}. "
                f"Rango aplicado [{start_row}, {end_row}] => {len(df_leads)} filas cargadas.<br>"
            )

            # Si quieres el orden de columnas original
            orden_columnas = [
                "Logo",
                "Company Name",
                "Nombre",
                "First name",
                "Last name",
                "Title",
                "Nivel Jerarquico",
                "Area",
                "Departamento",
                "Email",
                "Linkedin",
                "Location",
                "Company Domain",
                "Company Website",
                "Company Employee Count Range",
                "Company Founded",
                "Company Industry",
                "Industria Mayor",
                "Company Type",
                "Company Headquarters",
                "Company Revenue Range",
                "Company Linkedin Url"
            ]
            columnas_presentes = [col for col in orden_columnas if col in df_leads.columns]
            otras_columnas = [col for col in df_leads.columns if col not in columnas_presentes]
            df_leads = df_leads[columnas_presentes + otras_columnas].copy()

            # Asignar mapeos automáticos
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


        # Acción scrap proveedor scrapp proveedor
        accion = request.form.get("accion", "")
        if accion == "scrap_proveedor" and url_proveedor_global:
            # Scrapeo y análisis del proveedor
            sc = realizar_scrapingProv(url_proveedor_global)
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
            df_leads.reset_index(drop=True, inplace=True)
            for col in ["scrapping", "URLs on WEB", "Scrapping Adicional", "Descripcion", "PyS", "Objetivo"]:
                if col not in df_leads.columns:
                    df_leads[col] = "-"

            if df_leads.empty:
                status_msg += "No hay leads para aplicar scraping tras scrap del proveedor.<br>"
            else:
                scraping_progress["total"] = len(df_leads)
                scraping_progress["procesados"] = 0
                scrap_cache = {}
                urls_cache = {}
                adicional_cache = {}

                # Función principal
                def scrapear_lead(idx_row_tuple):
                    idx, row_data = idx_row_tuple
                    row = dict(zip(df_leads.columns, row_data))
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

                # Función scraping adicional
                def scrapear_adicional(idx_row_tuple):
                    idx, row_data = idx_row_tuple
                    row = dict(zip(df_leads.columns, row_data))
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

                # Ejecutar scraping principal
                with ThreadPoolExecutor(max_workers=10) as executor:
                    resultados = list(executor.map(scrapear_lead, list(enumerate(df_leads.itertuples(index=False, name=None)))))
                for idx, res in resultados:
                    df_leads.at[idx, "scrapping"] = res["scrapping"]
                    df_leads.at[idx, "URLs on WEB"] = res["urls"]
                    scraping_progress["procesados"] += 1

                status_msg += "✅ Scraping de leads y URLs ejecutado en paralelo.<br>"

                # Ejecutar scraping adicional
                with ThreadPoolExecutor(max_workers=10) as executor:
                    adicionales = list(executor.map(scrapear_adicional, list(enumerate(df_leads.itertuples(index=False, name=None)))))
                for idx, texto in adicionales:
                    df_leads.at[idx, "Scrapping Adicional"] = texto

                status_msg += "✅ Scraping adicional ejecutado en paralelo.<br>"

                # Generar info con ChatGPT
                for idx, row_data in enumerate(df_leads.itertuples(index=False, name=None)):
                    row = dict(zip(df_leads.columns, row_data))
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
    num_leads_cargados = len(df_leads) if not df_leads.empty else 0

    #filtros
    industrias = ["Finance","Technology","Education","Retail","Retail Manufacturing",
                "Professional Services","Hotel and Travel","Health","Industrial Manufacturing",
                "Construction","Logistics","Marketing Services","Automotive","Entertainment",
                "Restaurants","Human Resources","Government","Real Estate","Consumer Services",
                "Telco","Energy","ONG","Media","Industrial","Legal","Environmental","Public Services"]
    industria_options_html = "".join([f'<option value="{i}">{i}</option>' for i in industrias])
    areas = ["Comercial","Dirección General","Operaciones","Marketing","Recursos Humanos",
            "Finanzas","Tecnología","Académica","Administración","Producto","Jurídico",
            "Salud","Construcción","Producción Artistica","Municipio"]

    area_options_html = "".join([f'<option value="{a}">{a}</option>' for a in areas])
    departamentos = ["Ventas","Rectoria","Operaciones","Presidencia","Compras","Dirección General",
                    "Marketing","Desarrollo de Software","Recursos Humanos","Ventas regionales",
                    "Profesores","Retail","Finanzas","Ecommerce","Servicio al Cliente","Logística",
                    "Administración","Consejo de Administración","Seguridad","Tecnología",
                    "Contraloría","Practicas Profesionales","Calidad","Trade Marketing","Produccion",
                    "Desarrollo de Personal","Contabilidad","Networker","Comercailización",
                    "Business Intelligence","Branding","Contratos y Litigios","Mantenimiento",
                    "Almacén","Tecnología de la Infromacion","Comunicación","Reclutamiento y Selección",
                    "Cocina","Cuentas","Medios Publicitarios","Médico","Contenidos",
                    "Regulatorio y Cumplimiento","Compensaciones","Eventos y Patrocinios",
                    "SEO / SEM / Medios Digitales","Operaciones Aéreas","Cobranza","Farmacia",
                    "Control de Riesgos","Infraestructura TI","Tesorería","Creativo",
                    "Revenue Management","KAM","Inversiones","Growth Marketing","Expansión",
                    "Construcción","Desarrollo de Producto","Producción Audiovisual",
                    "Distribución y Transporte","Crédito","Innovación","Project Management",
                    "CRM","Investigación","Nómina","Caja","Sustentabilidad","Seguridad e Higiene",
                    "Recepción","Actuación","Desarrollo de Negocio","Seguridad de la Informacion",
                    "Presidencia Municipal","Agente de Viajes","Desarrollo Web","Investigación y Desarrollo",
                    "Psicología","Fiduciario","Transformación Digital","Ventas Mayoreo","Nutrición",
                    "Agente Inmobiliario","Redes Sociales","Wellness","Digital Marketing","UX / UI",
                    "Alianzas Estratégicas","Cuentas por Pagar","Planeacion Financiera","Profesor Decano",
                    "Base de Datos","Pérdidas y Mermas","Preventa","Servicio al cliente","Doctorado",
                    "Ventas Telefónicas","Mesa de Control","Relaciones Públicas","Finanzas Corporativas",
                    "Planeación Estratégica","Soporte Técnico","Protección de Datos",
                    "Investigación de Mercados","Agente de Seguros","Chofer","Ingeniería",
                    "Desarrollo web","Dirección General Adjunta"]
    tamanos = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10,000", "10,000+"]
    departamento_options_html = "".join([f'<option value="{d}">{d}</option>' for d in departamentos])
    industria_options_html = "".join([f'<option value="{i.strip()}">{i.strip()}</option>' for i in industrias])
    area_options_html = "".join([f'<option value="{a.strip()}">{a.strip()}</option>' for a in areas])
    departamento_options_html = "".join([f'<option value="{d.strip()}">{d.strip()}</option>' for d in departamentos])
    tamano_options_html = "".join([f'<option value="{d.strip()}">{d.strip()}</option>' for d in tamanos])
    
    page_html = f"""
    <html>
    <head>
        <title>ClickerMatch Beta</title>
        <style>
            body {{
                background: url('/static/background.png') no-repeat center center fixed;
                background-size: cover;
                color: #FFFFFF;
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                margin: 0; padding: 0;
                text-align: center;
            }}
            h1, h2, h3 {{
                font-family: 'Orbitron', sans-serif;
            }}  
            .container {{
                background: rgba(0, 45, 99, 0.6); /* ahora más cercano a #002d63 */
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                width: 5%;
                max-width: 300px;
                min-width: 300px;
                flex-shrink: 0; 
                margin: 40px auto;
                padding: 20px 30px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            }}
            .container-wide {{
                max-width: 100%;
                flex-grow: 1;
                overflow-x: auto;
                margin: 20px auto;
                background: rgba(0, 45, 99, 0.6); /* ahora más cercano a #002d63 */
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                padding: 20px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.4);
                overflow-x: auto;
            }}
            .container-wide {{
                max-height: 600px;
                overflow-y: auto;
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
            textarea,
            select {{
                width: 100%;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #ccc;
                background-color: #fff;
                color: #333;
                margin-bottom: 12px;
                font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                font-size: 14px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            textarea {{
                background-color: #fff;
                color: #333;
            }}
            button {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px; /* espacio entre ícono y texto */
                font-weight: bold;
                padding: 10px 16px;
                border-radius: 5px; /* <- sin bordes redondeados */
                background: linear-gradient(45deg, #003366, #005599);
                color: #fff;
                cursor: pointer;
                font-size: 14px;
                width: 100%; /* <- que ocupen todo el ancho */
                box-sizing: border-box; /* para que el padding no los saque del contenedor */
            }}
            button:hover {{
                background: linear-gradient(45deg, #005599, #003366);
            }}
            details summary {{
                background: linear-gradient(45deg, #00BFFF, #1E90FF);
                color: #ffffff !important;
                font-weight: bold;
                padding: 12px 20px;
                cursor: pointer;
                border: none;
                outline: none;
                width: 100%;
                box-sizing: border-box;
                margin: 8px 0;
                display: flex;
                align-items: center;
                justify-content: space-between;
                position: relative;
                overflow: hidden;
            }}
            details summary::before {{
                content: "";
                position: absolute;
                left: 50px;
                top: 0;
                height: 100%;
                width: 2px;
                background: rgba(255,255,255,0.4);
                transform: skewX(-40deg);
            }}
            details summary img.icon {{
                height: 20px;
                filter: brightness(0) invert(1);
                margin-left: 10px;
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
                background: rgba(10, 20, 40, 0.6);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.2);
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

            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
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
            .container input,
            .container select,
            .container textarea,
            .container details summary,
            .container .status,
            .container .scrap-container {{
                background-color: #fff;
                color: #333;
                border: 1px solid #ccc;
            }}

            .container details summary {{
                background-color: #f0f0f0;
                color: #333;
                font-weight: bold;
            }} 
            .custom-file-upload {{
                display: inline-block;
                padding: 10px 16px;
                width: 100%;
                box-sizing: border-box;
                border-radius: 5px;
                background: linear-gradient(45deg, #003366, #005599);
                color: #fff;
                font-weight: bold;
                cursor: pointer;
                text-align: center;
                font-size: 14px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                margin-bottom: 12px;
            }}

            .custom-file-upload:hover {{
                background: linear-gradient(45deg, #005599, #003366);
                opacity: 0.9;
            }}  
            .select2-results__option {{
                color: #000 !important;
                background-color: #fff !important;
            }}

            .select2-results__option--highlighted {{
                background-color: #888 !important;
                color: #fff !important;
            }}             

        </style>
    </head>
    <body>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500&display=swap" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>

        <div style="
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 20px 30px;
                background: linear-gradient(to right, #1E90FF 0%, transparent 100%);
                border-radius: 0 0 20px 20px;
                box-shadow: 0 4px 20px rgba(30, 144, 255, 0.3);
            ">

                <img src="/static/LOGO-CLICKER-MATCH.png" alt="ClickerMatch"
                    style="max-height: 80px;" />

                <h1 style="
                    color: white;
                    font-size: 28px;
                    font-family: 'Orbitron', sans-serif;
                    font-weight: 500;
                    text-shadow: 1px 1px 4px rgba(0,0,0,0.5);
                    letter-spacing: 1px;
                    margin: 0;
                ">
                    IA que prospecta y agenda citas con tomadores de decisiones.
                </h1>

            <div class="profile-container" style="
            position: relative;
            z-index: 2000;
            display: flex;
            align-items: center;
            background: rgba(0, 45, 99, 0.6);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 8px 12px;
            cursor: pointer;
            transition: background 0.3s;
        ">
            <img src="/static/profilepic/profile.png" alt="Profile" style="
                height: 40px;
                width: 40px;
                border-radius: 50%;
                margin-right: 10px;
                object-fit: cover;
                border: 2px solid #fff;
            "/>
            <div style="color: white; text-align: left;">
                <div style="font-weight: bold;">{ session.get("user", "Usuario") }</div>
                <div style="font-size: 12px; color: #ddd;">{ session.get("correo", "") }</div>
            </div>
            <div id="dropdownMenu" style="
                display: none;
                position: absolute;
                right: 0;
                top: 55px;
                background: rgba(0, 45, 99, 0.9);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 10px;
                min-width: 220px;
                z-index: 1000;
                box-shadow: 0 8px 16px rgba(0,0,0,0.4);
                padding: 12px;
            ">
                <p style="margin: 0; color: #fff;"><strong>{ session.get("user", "Usuario") }</strong></p>
                <p style="margin: 0; font-size: 12px; color: #ccc;">{ session.get("correo", "") }</p>
                <hr style="border-color: #555;">
                <a href="/mapeo" class="custom-file-upload" style=style="
                    color: #FF4C4C;
                    text-decoration: none;
                    display: block;
                    margin-top: 5px;
                    font-weight: bold;
                ">
                    📂 Importar CSV a DB
                </a>
                <a href="/logout" style="
                    color: #FF4C4C;
                    text-decoration: none;
                    display: block;
                    margin-top: 5px;
                    font-weight: bold;
                ">🚪 Cerrar sesión</a>
            </div>
        </div>


        </div>
    </div>

  
    <div style="display: flex; gap: 20px; align-items: flex-start;">
    <div class="container">
    <!-- Sección 0: Cargar Base de datos de servidor-->    
    <details>
    <summary style="cursor: pointer; font-weight: bold;"><img src="/static/icons/db.png" class="icon" alt="icono db"> Base de Datos Online</summary>
    <form method="POST">
        <input type="hidden" name="accion" value="cargar_contactos_db" />

        <label>🔍 Busqueda Universal:</label>
        <input type="text" name="filtro_busqueda" placeholder="Ej. Acme, gmail, alto" style="margin-bottom:10px;" />

        <label>Lista:</label>
        <input type="text" name="source" placeholder="" />

        <label for="industria_mayor">Industria:</label>
        <select name="industria_mayor" id="industria_mayor">
            <option value="">-- Todas --</option>
            <option value="Finance">Finance</option>
            <option value="Technology">Technology</option>
            <option value="Education">Education</option>
            <option value="Retail">Retail</option>
            <option value="Retail Manufacturing">Retail Manufacturing</option>
            <option value="Professional Services">Professional Services</option>
            <option value="Hotel and Travel">Hotel and Travel</option>
            <option value="Health">Health</option>
            <option value="Industrial Manufacturing">Industrial Manufacturing</option>
            <option value="Construction">Construction</option>
            <option value="Logistics">Logistics</option>
            <option value="Marketing Services">Marketing Services</option>
            <option value="Automotive">Automotive</option>
            <option value="Entertainment">Entertainment</option>
            <option value="Restaurants">Restaurants</option>
            <option value="Human Resources">Human Resources</option>
            <option value="Government">Government</option>
            <option value="Real Estate">Real Estate</option>
            <option value="Consumer Services">Consumer Services</option>
            <option value="Telco">Telco</option>
            <option value="Energy">Energy</option>
            <option value="ONG">ONG</option>
            <option value="Media">Media</option>
            <option value="Industrial">Industrial</option>
            <option value="Legal">Legal</option>
            <option value="Environmental">Environmental</option>
            <option value="Public Services">Public Services</option>
        </select>


        <label for="area">Área:</label>
        <select name="area" id="area">
            <option value="">-- Todas --</option>
            <option value="Comercial">Comercial</option>
            <option value="Dirección General">Dirección General</option>
            <option value="Operaciones">Operaciones</option>
            <option value="Marketing">Marketing</option>
            <option value="Recursos Humanos">Recursos Humanos</option>
            <option value="Finanzas">Finanzas</option>
            <option value="Tecnología">Tecnología</option>
            <option value="Académica">Académica</option>
            <option value="Administración">Administración</option>
            <option value="Producto">Producto</option>
            <option value="Jurídico">Jurídico</option>
            <option value="Salud">Salud</option>
            <option value="Construcción">Construcción</option>
            <option value="Producción Artistica">Producción Artistica</option>
            <option value="Municipio">Municipio</option>
        </select>

        <label for="departamento">Departamento:</label>
        <select name="departamento" id="departamento">
            <option value="">-- Todos --</option>
            <option value="Ventas">Ventas</option>
            <option value="Rectoria">Rectoria</option>
            <option value="Operaciones">Operaciones</option>
            <option value="Presidencia">Presidencia</option>
            <option value="Compras">Compras</option>
            <option value="Dirección General">Dirección General</option>
            <option value="Marketing">Marketing</option>
            <option value="Desarrollo de Software">Desarrollo de Software</option>
            <option value="Recursos Humanos">Recursos Humanos</option>
            <option value="Ventas regionales">Ventas regionales</option>
            <option value="Profesores">Profesores</option>
            <option value="Retail">Retail</option>
            <option value="Finanzas">Finanzas</option>
            <option value="Ecommerce">Ecommerce</option>
            <option value="Servicio al Cliente">Servicio al Cliente</option>
            <option value="Logística">Logística</option>
            <option value="Administración">Administración</option>
            <option value="Consejo de Administración">Consejo de Administración</option>
            <option value="Seguridad">Seguridad</option>
            <option value="Tecnología">Tecnología</option>
            <option value="Contraloría">Contraloría</option>
            <option value="Practicas Profesionales">Practicas Profesionales</option>
            <option value="Calidad">Calidad</option>
            <option value="Trade Marketing">Trade Marketing</option>
            <option value="Produccion">Produccion</option>
            <option value="Desarrollo de Personal">Desarrollo de Personal</option>
            <option value="Contabilidad">Contabilidad</option>
            <option value="Networker">Networker</option>
            <option value="Comercailización">Comercailización</option>
            <option value="Business Intelligence">Business Intelligence</option>
            <option value="Branding">Branding</option>
            <option value="Contratos y Litigios">Contratos y Litigios</option>
            <option value="Mantenimiento">Mantenimiento</option>
            <option value="Almacén">Almacén</option>
            <option value="Tecnología de la Infromacion">Tecnología de la Infromacion</option>
            <option value="Comunicación">Comunicación</option>
            <option value="Reclutamiento y Selección">Reclutamiento y Selección</option>
            <option value="Cocina">Cocina</option>
            <option value="Cuentas">Cuentas</option>
            <option value="Medios Publicitarios">Medios Publicitarios</option>
            <option value="Médico">Médico</option>
            <option value="Contenidos">Contenidos</option>
            <option value="Regulatorio y Cumplimiento">Regulatorio y Cumplimiento</option>
            <option value="Compensaciones">Compensaciones</option>
            <option value="Eventos y Patrocinios">Eventos y Patrocinios</option>
            <option value="SEO / SEM / Medios Digitales">SEO / SEM / Medios Digitales</option>
            <option value="Operaciones Aéreas">Operaciones Aéreas</option>
            <option value="Cobranza">Cobranza</option>
            <option value="Farmacia">Farmacia</option>
            <option value="Control de Riesgos">Control de Riesgos</option>
            <option value="Infraestructura TI">Infraestructura TI</option>
            <option value="Tesorería">Tesorería</option>
            <option value="Creativo">Creativo</option>
            <option value="Revenue Management">Revenue Management</option>
            <option value="KAM">KAM</option>
            <option value="Inversiones">Inversiones</option>
            <option value="Growth Marketing">Growth Marketing</option>
            <option value="Expansión">Expansión</option>
            <option value="Construcción">Construcción</option>
            <option value="Desarrollo de Producto">Desarrollo de Producto</option>
            <option value="Producción Audiovisual">Producción Audiovisual</option>
            <option value="Distribución y Transporte">Distribución y Transporte</option>
            <option value="Crédito">Crédito</option>
            <option value="Innovación">Innovación</option>
            <option value="Project Management">Project Management</option>
            <option value="CRM">CRM</option>
            <option value="Investigación">Investigación</option>
            <option value="Nómina">Nómina</option>
            <option value="Caja">Caja</option>
            <option value="Sustentabilidad">Sustentabilidad</option>
            <option value="Seguridad e Higiene">Seguridad e Higiene</option>
            <option value="Recepción">Recepción</option>
            <option value="Actuación">Actuación</option>
            <option value="Desarrollo de Negocio">Desarrollo de Negocio</option>
            <option value="Seguridad de la Informacion">Seguridad de la Informacion</option>
            <option value="Presidencia Municipal">Presidencia Municipal</option>
            <option value="Agente de Viajes">Agente de Viajes</option>
            <option value="Desarrollo Web">Desarrollo Web</option>
            <option value="Investigación y Desarrollo">Investigación y Desarrollo</option>
            <option value="Psicología">Psicología</option>
            <option value="Fiduciario">Fiduciario</option>
            <option value="Transformación Digital">Transformación Digital</option>
            <option value="Ventas Mayoreo">Ventas Mayoreo</option>
            <option value="Nutrición">Nutrición</option>
            <option value="Agente Inmobiliario">Agente Inmobiliario</option>
            <option value="Redes Sociales">Redes Sociales</option>
            <option value="Wellness">Wellness</option>
            <option value="Digital Marketing">Digital Marketing</option>
            <option value="UX / UI">UX / UI</option>
            <option value="Alianzas Estratégicas">Alianzas Estratégicas</option>
            <option value="Cuentas por Pagar">Cuentas por Pagar</option>
            <option value="Planeacion Financiera">Planeacion Financiera</option>
            <option value="Profesor Decano">Profesor Decano</option>
            <option value="Base de Datos">Base de Datos</option>
            <option value="Pérdidas y Mermas">Pérdidas y Mermas</option>
            <option value="Preventa">Preventa</option>
            <option value="Servicio al cliente">Servicio al cliente</option>
            <option value="Doctorado">Doctorado</option>
            <option value="Ventas Telefónicas">Ventas Telefónicas</option>
            <option value="Mesa de Control">Mesa de Control</option>
            <option value="Relaciones Públicas">Relaciones Públicas</option>
            <option value="Finanzas Corporativas">Finanzas Corporativas</option>
            <option value="Planeación Estratégica">Planeación Estratégica</option>
            <option value="Soporte Técnico">Soporte Técnico</option>
            <option value="Protección de Datos">Protección de Datos</option>
            <option value="Investigación de Mercados">Investigación de Mercados</option>
            <option value="Agente de Seguros">Agente de Seguros</option>
            <option value="Chofer">Chofer</option>
            <option value="Ingeniería">Ingeniería</option>
            <option value="Desarrollo web">Desarrollo web</option>
            <option value="Dirección General Adjunta">Dirección General Adjunta</option>
        </select>
        
        <label for="company_employee_count_range">Tamaño de Empresa:</label>
        <select name="company_employee_count_range" id="company_employee_count_range">
            <option value="">-- Todos --</option>
            <option value="10001+">10001+</option>
            <option value="10000.0">10000.0</option>
            <option value="5001 - 10000">5001 - 10000</option>
            <option value="5000.0">5000.0</option>
            <option value="1001 - 5000">1001 - 5000</option>
            <option value="1000.0">1000.0</option>
            <option value="501 - 1000">501 - 1000</option>
            <option value="500.0">500.0</option>
            <option value="201 - 500">201 - 500</option>
            <option value="200.0">200.0</option>
            <option value="51 - 200">51 - 200</option>
            <option value="50.0">50.0</option>
            <option value="11 - 50">11 - 50</option>
            <option value="10.0">10.0</option>
            <option value="2 - 10">2 - 10</option>
            <option value="1.0">1.0</option>
        </select>
        
        <label>Limite:</label>
        <input type="text" name="max_rows" placeholder="Ej. 100" />        
        
        <button type="submit">📥 Buscar y Cargar</button>
    </form>

    </details>



        <!-- Sección 1: Cargar CSV y Mapeo -->
    <details>
    <summary style="cursor: pointer; font-weight: bold;"><img src="/static/icons/file.png" class="icon" alt="icono db"> Carga de base de datos</summary>
        <form method="POST" enctype="multipart/form-data">
        <hr>
        <label>Base de Datos:</label>
        <label class="custom-file-upload">
            📁 Seleccionar archivo
            <input type="file" name="leads_csv" />
        </label>
    
        <button type="submit">
            <img src="/static/icons/diskette.png" alt="icon" style="height:18px; filter: brightness(0) invert(1);">
            Subir Archivo
        </button>               
        </form>
    </details>    
        <hr>
        <!-- Sección: Clasificación de Puestos -->
    <details>
    <summary style="cursor: pointer; font-weight: bold;"><img src="/static/icons/data-classification.png" class="icon" alt="icono db">Clasificadores</summary>
        <!-- <button type="button" onclick="clasificarTodo()" style="background-color: {color_puestos};">
            Clasificar (Puestos + Áreas + Industrias)
        </button> -->
        <!-- <details>
        <summary>Clasificadores Individualmente</summary> -->
        <form method="POST" enctype="multipart/form-data">
            <input type="hidden" name="accion" value="clasificar_global"/>
            <button type="submit" style="background-color: {color_puestos};">
                <img src="/static/icons/diskette.png" alt="icon" style="height:18px; filter: brightness(0) invert(1);">Clasificar
            </button>
        </form>
        <!-- </details> -->
        <form method="POST">
            <input type="hidden" name="accion" value="scrapp_leads_on"/>
            <button type="submit" style="background-color: {color_scrap};">
                <img src="/static/icons/hacker.png" alt="icon" style="height:18px; filter: brightness(0) invert(1);">Análisis de Empresas
            </button>
        </form>   
        <form method="POST">
            <input type="hidden" name="accion" value="extraer_redes_y_telefono"/>
            <button type="submit"><img src="/static/icons/contact-information.png" alt="icon" style="height:18px; filter: brightness(0) invert(1);">Extraer Redes y Teléfono</button>
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

    <summary style="cursor: pointer; font-weight: bold;"><img src="/static/icons/apartment.png" class="icon" alt="icono db"> Nuestra Info</summary>

    <form method="POST" enctype="multipart/form-data">
        <label>Plan Estratégico:</label>
        <textarea name="plan_estrategico" rows="3" style="width:100%;border-radius:10px;margin-top:8px;">{plan_estrategico or ''}</textarea>

        <details>
            <summary style="cursor:pointer; font-weight: bold;"><img src="/static/icons/db.png" class="icon" alt="icono db"> Plan Estrategico</summary>
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
<details>
    <summary style="cursor:pointer; font-weight: bold;"><img src="/static/icons/artificial-intelligence_atomic.png" class="icon" alt="icono db"> Motor IA </summary> 
        <details>
            <summary style="cursor:pointer; font-weight: bold;"><img src="/static/icons/artificial-intelligence_atomic.png" class="icon" alt="icono db"> Edición Prompt </summary>    
            <div style="margin-top:30px;">
                <h3>✍️ Prompt para Strategy - Reply Rate Email</h3>
                <form method="POST">
                    <input type="hidden" name="accion" value="guardar_prompt_strategy" />
                    <textarea name="prompt_strategy" rows="10" style="width:100%;border-radius:10px;">{prompt_strategy}</textarea>
                    <button type="submit" style="margin-top:10px;">
                        💾 Guardar Strategy Prompt
                    </button>
                </form>
                <form method="POST" style="flex:1;">
                    <input type="hidden" name="accion" value="reiniciar_prompt_strategy" />
                    <button type="submit" style="width:100%;">
                        ♻️ Reiniciar prompt
                    </button>
                </form>
                <form method="POST">
                    <input type="hidden" name="accion" value="eliminar_columnas_emails">
                    <button type="submit">🗑️ Eliminar columnas de estrategias</button>
                </form>
            </div>
        </details>
    <form method="POST">
        <input type="hidden" name="accion" value="generar_tabla"/>
        <button type="submit" style="background-color: {{ 'green' if acciones_realizadas['generar_tabla'] else '#1E90FF' }};">
            <img src="/static/icons/artificial-intelligence_atomic.png" alt="icon" style="height:18px; filter: brightness(0) invert(1);">
            Generar Mails con I.A.
        </button>
    </form> 
</details>    
   
    <!--
    <details>
    <summary style="cursor: pointer; font-weight: bold;"><img src="/static/icons/db.png" class="icon" alt="icono db"> Edición de IA Prompts</summary>           
    <details>
    <summary style="cursor: pointer; font-weight: bold;"><img src="/static/icons/db.png" class="icon" alt="icono db"> Prompt Value</summary>
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
    <summary style="cursor: pointer; font-weight: bold;"><img src="/static/icons/db.png" class="icon" alt="icono db"> Prompt Mails Estrategia</summary>
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
    <summary style="cursor: pointer; font-weight: bold;"><img src="/static/icons/export.png" class="icon" alt="icono db"> Exportar</summary>
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
        <h2>Lista de Contactos</h2>
        <h3 style="color: white;">Total registros cargados: {num_leads_cargados}</h3>
        {tabla_html(df_leads,50)}
    </div>

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
    
    document.addEventListener("click", function(event) {{
        const profile = document.querySelector(".profile-container");
        const dropdown = document.getElementById("dropdownMenu");
        if (profile.contains(event.target)) {{
            dropdown.style.display = dropdown.style.display === "block" ? "none" : "block";
        }} else {{
            dropdown.style.display = "none";
        }}
    }});

    </script>


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

@app.route("/map_columns", methods=["GET", "POST"])
def map_columns():
    global df_temp_upload, df_leads
    global mapeo_nombre_contacto, mapeo_puesto, mapeo_empresa
    global mapeo_industria, mapeo_website, mapeo_location

    columnas = list(df_temp_upload.columns)

    if request.method == "POST":
        # Obtener rango
        start_row_str = request.form.get("start_row", "").strip()
        end_row_str = request.form.get("end_row", "").strip()
        
        try:
            start_row = int(start_row_str) if start_row_str else 0
        except:
            start_row = 0
        try:
            end_row = int(end_row_str) if end_row_str else len(df_temp_upload) - 1
        except:
            end_row = len(df_temp_upload) - 1

        if start_row < 0:
            start_row = 0
        if end_row >= len(df_temp_upload):
            end_row = len(df_temp_upload) - 1

        if start_row > end_row:
            df_leads = pd.DataFrame(columns=df_temp_upload.columns)
        else:
            df_leads = df_temp_upload.iloc[start_row:end_row+1].copy()

        # Obtener selecciones
        mapeo_nombre_contacto = (request.form.get("col_nombre") or "").strip()
        mapeo_puesto = (request.form.get("col_puesto") or "").strip()
        mapeo_empresa = (request.form.get("col_empresa") or "").strip()
        mapeo_industria = (request.form.get("col_industria") or "").strip()
        mapeo_website = (request.form.get("col_website") or "").strip()
        mapeo_location = (request.form.get("col_location") or "").strip()

        # Renombrar columnas
        renames = {}
        if mapeo_nombre_contacto: renames[mapeo_nombre_contacto] = "First name"
        if mapeo_puesto: renames[mapeo_puesto] = "Title"
        if mapeo_empresa: renames[mapeo_empresa] = "Company Name"
        if mapeo_industria: renames[mapeo_industria] = "Company Industry"
        if mapeo_website: renames[mapeo_website] = "Company Website"
        if mapeo_location: renames[mapeo_location] = "Location"

        if renames:
            df_leads.rename(columns=renames, inplace=True)

        # ACTUALIZAR mapeos a los nombres finales
        if "First name" in df_leads.columns:
            mapeo_nombre_contacto = "First name"
        if "Title" in df_leads.columns:
            mapeo_puesto = "Title"
        if "Company Name" in df_leads.columns:
            mapeo_empresa = "Company Name"
        if "Company Industry" in df_leads.columns:
            mapeo_industria = "Company Industry"
        if "Company Website" in df_leads.columns:
            mapeo_website = "Company Website"
        if "Location" in df_leads.columns:
            mapeo_location = "Location"

        return redirect("/")

    return render_template("map_columns.html", columnas=columnas)

@app.route("/mapeo")
def mapeo():
    return render_template("mapeo.html")

@app.route("/subir_mapeado", methods=["POST"])
def subir_mapeado():
    file = request.files.get("csvFile")
    mappings = {k[8:]: v for k, v in request.form.items() if k.startswith("mapping_") and v}

    if file and mappings:
        df = pd.read_csv(file)
        # Renombrar columnas según mappings
        df = df.rename(columns=mappings)
        # Insertar en la DB (asegúrate de que df.columns coincidan con la tabla)
        basename = os.path.splitext(file.filename)[0]
        df["search"] = basename
        df.to_sql("contactos_expandi_historico", engine, if_exists="append", index=False)
        return render_template("successupload.html")
    return "⚠️ No se pudo subir."


if __name__ == "__main__":
    print("[LOG] Inicia la app con la modificación para parsear JSON con llaves.")
    app.run(debug=True, port=5000)

    
    