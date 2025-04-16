#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
# -*- coding: utf-8 -*-
import time
import os
import io
import re
import json
import requests
import pandas as pd
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from flask import Flask, request, make_response
from cryptography.fernet import Fernet


# Si tu wrapper es distinto, adapta la importación:
try:
    from openai import OpenAI
except ImportError:
    print("[ERROR] No se encontró 'from openai import OpenAI'. Ajusta la librería según corresponda.")
    OpenAI = None

###############################
# 1) Hardcodear la API Key
###############################
ENCRYPTION_KEY = b'yMybaWCe4meeb3v4LWNI4Sxz7oS54Gn0Fo9yJovqVN0='

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

app = Flask(__name__)
app.secret_key = "CLAVE_SECRETA_PARA_SESSION"  # si deseas usar session

# DataFrame principal
df_leads = pd.DataFrame()

#Campos industria y area
industrias_interes = ""
area_interes = ""
plan_estrategico = ""



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
    Elimina caracteres extraños (ej. emojis o símbolos no usuales)
    manteniendo letras, dígitos, ciertos signos de puntuación y acentos básicos.
    """
    return re.sub(r'[^\w\sáéíóúÁÉÍÓÚñÑüÜ:;,.!?@#%&()"+\-\//$\'\"\n\r\t¿¡]', '', texto)

def _asegurar_https(url: str) -> str:
    """Si la URL no empieza con http(s)://, antepone https://."""
    url = url.strip()
    if not url:
        return ""
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = "https://" + url
    return url

def realizar_scraping(url: str) -> str:
    """Scrapea la URL (hasta MAX_SCRAPING_CHARS) y devuelve texto plano limpio."""
    url = _asegurar_https(url)
    if not url:
        return "-"
    print("[LOG] Scraping del proveedor. URL:", url)
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        print("[LOG] HTTP Status:", resp.status_code)
        if resp.status_code == 200:
            sopa = BeautifulSoup(resp.text, "html.parser")
            texto = sopa.get_text()
            truncated = texto[:MAX_SCRAPING_CHARS]
            truncated = _limpiar_caracteres_raros(truncated)
            print("[LOG] Scraping completado. Chars extraídos:", len(truncated))
            return truncated
        else:
            print("[LOG] HTTP != 200, devolvemos '-'.")
            return "-"
    except Exception as e:
        print("[ERROR] Excepción en realizar_scraping:", e)
        return "-"

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
    Retorna un dict con esas claves.
    """
    if client is None:
        print("[ERROR] Cliente ChatGPT es None. Retorno info vacía.")
        return {
            "Nombre de la Empresa": "-",
            "Objetivo": "-",
            "Productos o Servicios": "-",
            "Industrias": "-",
            "Clientes o Casos de Exito": "-"
        }

    prompt = f"""
Eres un asistente que analiza la información de un sitio web de una empresa (texto crudo).
Devuélveme exactamente en formato JSON los siguientes campos:
- Nombre de la Empresa
- Objetivo (o misión o enfoque principal)
- Productos o Servicios
- Industrias (a qué industrias sirve o en cuáles se especializa)
- Clientes o Casos de Exito (si aparecen referencias a clientes o casos)

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

            return {
                "Nombre de la Empresa": nombre,
                "Objetivo": objetivo,
                "Productos o Servicios": prod_serv,
                "Industrias": industrias,
                "Clientes o Casos de Exito": clientes
            }
        except Exception as ex_json:
            print("[ERROR] No se pudo parsear la respuesta de ChatGPT como JSON:", ex_json)
            return {
                "Nombre de la Empresa": "-",
                "Objetivo": "-",
                "Productos o Servicios": "-",
                "Industrias": "-",
                "Clientes o Casos de Exito": "-"
            }
    except Exception as ex:
        print("[ERROR] Al invocar ChatGPT para analizar proveedor:", ex)
        return {
            "Nombre de la Empresa": "-",
            "Objetivo": "-",
            "Productos o Servicios": "-",
            "Industrias": "-",
            "Clientes o Casos de Exito": "-"
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
    title = str(row.get(mapeo_puesto, "-"))
    industry = str(row.get(mapeo_industria, "-"))
    companyName = str(row.get(mapeo_empresa, "-"))
    employee_range = str(row.get(mapeo_empleados, "-"))
    location = str(row.get(mapeo_location, "-"))
    
    

    scrapping_lead = str(row.get("scrapping", "-"))
    scrapping_proveedor = str(row.get("scrapping_proveedor", "-"))

    # PROMPT: asegurarse de que ChatGPT devuelva un JSON con llaves
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
Basado en esta información del cliente y del proveedor, genera los siguientes campos en español:

Personalization: Es una introducción personalizada basada en un hecho reciente o logro dela empresa cliente, el objetivo es captar su atención de inmediato. Empresa Cliente → Se basa en su actividad, logros o contexto.
Your Value Prop. Es la propuesta de valor de tu empresa, lo que ofreces y cómo ayudas a resolver un problema específico. Proveedor → Es nuestro diferenciador y lo que podemos hacer por el cliente.
Your Target Niche (Niche, Subsegment, Location). El segmento de mercado al que queremos llegar, definido por industria, subsegmento y ubicación. Proveedor → Es nuestra audiencia objetivo.
Your Cliente Goal. La meta principal del puesto del cliente. ¿Qué quiere lograr con su negocio o estrategia?. Cliente → Es su necesidad o aspiración.
Your Cliente Value Prop. La propuesta de valor del cliente. ¿Cómo se diferencian ellos en su mercado? ¿Qué buscan potenciar?. Cliente → Es cómo ellos se presentan en su industria.
Cliffhanger Value Prop. Una propuesta intrigante o gancho para motivar la conversación, generalmente una promesa de resultados o insights valiosos. Proveedor → Un beneficio atractivo para generar curiosidad.
CTA (Call to Action). La acción concreta que queremos que tome el cliente, como agendar una reunión o responder al correo. Proveedor → Es nuestra invitación a la acción.


Escríbelos de manera que conecten en un solo mensaje


Información del lead:
- El cliente es: {companyName}
- Contacto: {lead_name}
- Puesto del contácto: {title}
- Industria: {industry}

Información del ICP (Ideal Customer Profile):
- Industrias de Interés: {industrias_interes}
- Área de Interés: {area_interes}

- Contenido del sitio web del cliente(scrapping del cliente): {scrapping_lead}


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
    print(f"[PROMPT] idx={row.name}, lead={lead_name}")
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
    print(base_context)
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": base_context}],
            max_tokens=1000,
            temperature=0.7,
            timeout=30
        )
        content = response.choices[0].message.content.strip()
        print("[RAW RESPONSE EMAILS STRATEGY]:", content)

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
def tabla_html(df: pd.DataFrame, max_filas=10) -> str:
    if df.empty:
        return "<p><em>DataFrame vacío</em></p>"

    # Crear una copia solo para la visualización, eliminando las columnas ocultas
    subset = df.drop(columns=["scrapping_proveedor", "scrapping"], errors="ignore").head(max_filas)
    cols = list(subset.columns)

    anchas = [
        "Personalization", "Your Value Prop", "Target Niche", "Your Targets Goal",
        "Your Targets Value Prop", "Cliffhanger Value Prop", "CTA",
        "Strategy - 25% Reply Rate Email", "Strategy - One Sentence Email",
        "Strategy - Asking for an Introduction", "Strategy - Ask for Permission",
        "Strategy - Loom Video", "Strategy - Free Sample List"
    ]
    thead = "".join(
        f"<th class='col-ancha'>{col}</th>" if col in anchas else f"<th>{col}</th>"
        for col in cols
    )

    rows_html = ""
    for _, row in subset.iterrows():
        row_html = "".join(
            f"<td class='col-ancha'>{str(row[col])}</td>" if col in anchas else f"<td>{str(row[col])}</td>"
            for col in cols
        )
        rows_html += f"<tr>{row_html}</tr>"

    return f"<table><tr>{thead}</tr>{rows_html}</table>"



##########################################
# Rutas Flask
##########################################
@app.route("/", methods=["GET","POST"])
def index():
    global df_leads
    global scrap_proveedor_text
    global info_proveedor_global
    global mapeo_nombre_contacto, mapeo_puesto, mapeo_empresa
    global mapeo_industria, mapeo_website, mapeo_location, mapeo_empleados
    global industrias_interes, area_interes, plan_estrategico



    status_msg = ""
    url_proveedor_global = ""  # Moveremos esto a variable local

    if request.method == "POST":
        accion = request.form.get("accion", "")
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

        #Guardar campo de especificación industria y area buscada
        if accion == "guardar_custom_fields":
            industrias_interes = request.form.get("industrias_interes", "").strip()
            area_interes = request.form.get("area_interes", "").strip()
            plan_estrategico = request.form.get("plan_estrategico", "").strip()
            status_msg += f"Campos personalizados guardados.<br>"
               

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
            # Hacemos scraping
            sc = realizar_scraping(url_proveedor_global)
            scrap_proveedor_text = sc

            # Analizamos con ChatGPT para extraer info
            info_proveedor_global = analizar_proveedor_scraping_con_chatgpt(sc)

            # En df_leads, guardamos el texto crudo (para que se use en la generación)
            if not df_leads.empty:
                df_leads["scrapping_proveedor"] = sc

            status_msg += "Scraping y análisis del proveedor completado.<br>"

        elif accion == "generar_tabla":
            procesar_leads()
            generar_contenido_para_todos()
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
    page_html = f"""
    <html>
    <head>
        <title>ClickerMaker</title>
        <style>
            body {{
                background: url('https://expomatch.com.mx/wp-content/uploads/2025/03/u9969268949_creame_una_pagina_web_que_muestre_unas_bases_de_d_4f30c12d-8f6a-4913-aa47-1d927038ce10_0-1.png') no-repeat center center fixed;
                background-size: cover;
                color: #FFFFFF;
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 0; padding: 0;
                text-align: center;
            }}
            .container {{
                max-width: 460px;
                margin: 40px auto;
                background-color: #1F1F1F;
                padding: 20px 30px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            }}
            .container-wide {{
                max-width: 90%;
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
                border-radius: 10px;
                background-color: #1E90FF;
                color: #fff;
                cursor: pointer;
                margin: 6px;
                font-size: 14px;
            }}
            button:hover {{
                background-color: #00BFFF;
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
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
                }}
            th.col-ancha, td.col-ancha {{
                min-width: 300px;
                max-width: 400px;
                word-wrap: break-word;
                white-space: pre-wrap;
            }}
            
        </style>
    </head>
    <body>
    <div class="container">
        <h1>ClickerMatch</h1>
        <div class="status">{status_msg}</div>

        <!-- Sección 1: Cargar CSV y Mapeo -->
        <form method="POST" enctype="multipart/form-data">
        <h2>Cargar CSV de Leads y Mapeo</h2>
        <label>Base de Datos:</label>
        <input type="file" name="leads_csv"/>
        <label>Fila de inicio:</label>
        <input type="text" name="start_row" placeholder="0" />
        <label>Fila de fin:</label>
        <input type="text" name="end_row" placeholder="(última)" />

        <p>Mapeo de columnas:</p>
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

        <button type="submit">Subir Archivo</button>
        </form>
        <form method="POST">
            <label>Plan Estratégico:</label>
            <textarea name="plan_estrategico" rows="6" style="width:100%;border-radius:10px;">{plan_estrategico or ''}</textarea>

            <label>Industrias de Interés:</label>
            <input type="text" name="industrias_interes" value="{industrias_interes or ''}" placeholder="Ej: Automotriz, Manufactura"/>

            <label>Área de Interés:</label>
            <input type="text" name="area_interes" value="{area_interes or ''}" placeholder="Ej: Finanzas"/>

            <input type="hidden" name="accion" value="guardar_custom_fields"/>
            <button type="submit">Guardar Campos</button>
            <p><strong>Actual:</strong><br>
            Industrias: {industrias_interes}<br>
            Área: {area_interes}</p>      
        </form>
        
        <hr>


        <!-- Lo demás igual -->
        <form method="POST" onsubmit="showLoader()">
        <h2>Generar Tabla de Leads + ChatGPT</h2>
        <input type="hidden" name="accion" value="generar_tabla"/>
        <button type="submit">Generar (Procesar + ChatGPT)</button>
        </form>
        <hr>
        
    
        <form method="POST">
        <h2>Exportar</h2>
        <label>Formato:</label>
        <select name="formato">
            <option value="csv">CSV</option>
            <option value="xlsx">XLSX</option>
        </select>
        <input type="hidden" name="accion" value="exportar_archivo"/>
        <button type="submit">Exportar</button>
        </form>
    </div>

    <div class="container-wide">
        <h2>Base de datos (primeros 10 registros)</h2>
        {tabla_html(df_leads,10)}
    </div>

    <div class="content-block">
        {block_text_es}
    </div>
    </body>
    <div id="loader" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:9999;text-align:center;padding-top:200px;">
    <div style="color:white;font-size:20px;">⏳ Cargando datos... por favor espera</div>
    <div class="spinner"></div>
    </div>

    </html>
    """

    return page_html

if __name__ == "__main__":
    print("[LOG] Inicia la app con la modificación para parsear JSON con llaves.")
    app.run(debug=True, port=5000)