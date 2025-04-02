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
mapeo_location = "location"

# Configuraciones
MAX_SCRAPING_CHARS = 6000
OPENAI_MODEL = "gpt-3.5-turbo"
OPENAI_MAX_TOKENS = 1000

###############################
# Funciones auxiliares
###############################

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
    location = str(row.get(mapeo_location, "-"))

    scrapping_lead = str(row.get("scrapping", "-"))
    scrapping_proveedor = str(row.get("scrapping_proveedor", "-"))

    # PROMPT: asegurarse de que ChatGPT devuelva un JSON con llaves
    prompt = f"""
INSTRUCCIONES:
- Devuelve la respuesta SOLO como un objeto JSON (usando llaves).
- No incluyas texto adicional antes o después del JSON.
- Utiliza únicamente estas claves: 
  "Personalization",
  "Your Value Prop",
  "Target Niche",
  "Your Targets Goal",
  "Your Targets Value Prop",
  "Cliffhanger Value Prop",
  "CTA".

CONTEXTO:
somos (En base al scrapping del proveedor pon nos un nombre, allí viene)
Harás un correo eléctronico, no vendas, usa "llegar" en vez de "vender", socializa, pero en realidad solo me daras las siguientes partes, cada parte es un renglón del mensaje:

Tenemos un cliente llamado {companyName}.
Basado en esta información del cliente y del proveedor, genera los siguientes campos en español:

1. Personalization (usa el nombre del contacto, no te presentes, nin a nosotros, una introducción personalizada basada exclusivamente en la información del sitio web del cliente. El objetivo es captar su atención de inmediato. Escribe un mensaje breve, pero emocionante reconocimiento de su empresa "Hola {lead_name} (sigue, aqui no digas nada de nosotros ni que hacemos)" breve)
2. Your Value Prop (Propuesta de valor del proveedor, basado en su web. breve)
3. Target Niche (El segmento de mercado al que el proveedor llega, definido por industria, subsegmento y ubicación del cliente. No vas a mencionar estos datos, pero si algo ejemplo: "Somos y nos dedicamos a tal cosa, (del scrapping del proveedor pero orientado a scrapping del cliente) en (Mencionar la ubicación cliente)")
4. Your Targets Goal (La meta principal de {lead_name} considerando que es {title}. Qué quiere lograr con su negocio o estrategia. "Veo que aportas (hacer observación de a que se dedica el contácto)" breve)
5. Your Targets Value Prop (La propuesta de valor de {companyName}. Cómo se diferencian en su mercado. "Parece que ustedes buscan... (decir algo en base al scrapping del cliente)" breve)
6. Cliffhanger Value Prop (Propuesta intrigante o gancho para motivar la conversación. ejemplo "me encantaría mostrarte mi plan para... (crea algo breve en lo que ambos podamos trabajar juntos comparando scrapping proveedor y scrapping cliente)" breve)
7. CTA (Acción concreta que queremos que tome el cliente, como agendar una reunión.)

escribelos de manera que conecten en un solo mensaje

Información del lead:
- Contacto: {lead_name}
- Puesto: {title}
- Industria: {industry}
- El cliente es: {companyName}
- Contenido del sitio web del cliente(scrapping del cliente): {scrapping_lead}
- La ubicación de la empresa es: {location} (si no te doy una ubicación, ignóralo)

Información del proveedor:
- Contenido extraído del sitio web del proveedor: {scrapping_proveedor}

SOLICITUD:
Genera cada uno de estos campos en español y de forma breve:
1) Personalization
2) Your Value Prop
3) Target Niche
4) Your Targets Goal
5) Your Targets Value Prop
6) Cliffhanger Value Prop
7) CTA

Recuerda: la respuesta debe ser válido JSON con llaves y comillas en cada clave-valor, sin texto adicional.
    """

    prompt = _limpiar_caracteres_raros(prompt)

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
            target_niche = parsed.get("Target Niche", "-")
            targets_goal = parsed.get("Your Targets Goal", "-")
            targets_value_prop = parsed.get("Your Targets Value Prop", "-")
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
        "Cliffhanger Value Prop", "CTA"
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

    thead = "".join(f"<th>{col}</th>" for col in cols)
    rows_html = ""
    for _, row in subset.iterrows():
        row_html = "".join(f"<td>{str(row[col])}</td>" for col in cols)
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
    global mapeo_industria, mapeo_website, mapeo_location

    status_msg = ""
    url_proveedor_global = ""  # Moveremos esto a variable local

    if request.method == "POST":
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

        # Mapeo de columnas (por si el usuario quiere sobreescribir manualmente)
        col_nombre = request.form.get("col_nombre", "").strip()
        col_puesto = request.form.get("col_puesto", "").strip()
        col_empresa = request.form.get("col_empresa", "").strip()
        col_industria = request.form.get("col_industria", "").strip()
        col_website = request.form.get("col_website", "").strip()
        col_location = request.form.get("col_location", "").strip()

        if col_nombre:
            mapeo_nombre_contacto = col_nombre
            status_msg += f"Mapeo Nombre del contacto = '{col_nombre}'<br>"
        if col_puesto:
            mapeo_puesto = col_puesto
            status_msg += f"Mapeo Puesto = '{col_puesto}'<br>"
        if col_empresa:
            mapeo_empresa = col_empresa
            status_msg += f"Mapeo Empresa = '{col_empresa}'<br>"
        if col_industria:
            mapeo_industria = col_industria
            status_msg += f"Mapeo Industria = '{col_industria}'<br>"
        if col_website:
            mapeo_website = col_website
            status_msg += f"Mapeo Website = '{col_website}'<br>"
        if col_location:
            mapeo_location = col_location
            status_msg += f"Mapeo Ubicación = '{col_location}'<br>"

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
        <title>Campaign Maker: Sin corchetes, sin NaN</title>
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
        </style>
    </head>
    <body>
      <div class="container">
        <h1>ClickerMatch</h1>
        <div class="status">{status_msg}</div>

        <form method="POST" enctype="multipart/form-data">
          <h2>1) Cargar CSV de Leads</h2>
          <label>Base de Datos:</label>
          <input type="file" name="leads_csv"/>

          <label>Fila de inicio:</label>
          <input type="text" name="start_row" placeholder="0" />
          <label>Fila de fin:</label>
          <input type="text" name="end_row" placeholder="(última)" />

          <button type="submit">Subir Archivo</button>
        </form>
        <hr>

        <form method="POST">
          <h2>2) Parámetros</h2>
          <label>Tu sitio web (Proveedor)</label>
          <input type="text" name="url_proveedor"/>

          <p>Mapeo de columnas:</p>
          <label>Nombre del contacto:</label>
          <select name="col_nombre">
            {build_select_options(mapeo_nombre_contacto, df_leads.columns if not df_leads.empty else [])}
          </select>

          <label>Puesto/Title:</label>
          <select name="col_puesto">
            {build_select_options(mapeo_puesto, df_leads.columns if not df_leads.empty else [])}
          </select>

          <label>Nombre de la empresa:</label>
          <select name="col_empresa">
            {build_select_options(mapeo_empresa, df_leads.columns if not df_leads.empty else [])}
          </select>

          <label>Industria:</label>
          <select name="col_industria">
            {build_select_options(mapeo_industria, df_leads.columns if not df_leads.empty else [])}
          </select>

          <label>Website:</label>
          <select name="col_website">
            {build_select_options(mapeo_website, df_leads.columns if not df_leads.empty else [])}
          </select>

          <label>Ubicación:</label>
          <select name="col_location">
            {build_select_options(mapeo_location, df_leads.columns if not df_leads.empty else [])}
          </select>

          <input type="hidden" name="accion" value="scrap_proveedor"/>
          <button type="submit">Analizar Proveedor</button>
        </form>
        
        <div class="scrap-container">
          <strong>Información del proveedor (resumen ChatGPT):</strong><br>
          <p><b>Nombre de la Empresa:</b> {info_proveedor_global["Nombre de la Empresa"]}</p>
          <p><b>Objetivo:</b> {info_proveedor_global["Objetivo"]}</p>
          <p><b>Productos o Servicios:</b> {info_proveedor_global["Productos o Servicios"]}</p>
          <p><b>Industrias:</b> {info_proveedor_global["Industrias"]}</p>
          <p><b>Clientes o Casos de Exito:</b> {info_proveedor_global["Clientes o Casos de Exito"]}</p>
        </div>
        <hr>

        <form method="POST">
          <h2>3) Generar Tabla de Leads + ChatGPT</h2>
          <input type="hidden" name="accion" value="generar_tabla"/>
          <button type="submit">Generar (Procesar + ChatGPT)</button>
        </form>
        <hr>

        <form method="POST">
          <h2>4) Exportar</h2>
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
    </html>
    """

    return page_html

if __name__ == "__main__":
    print("[LOG] Inicia la app con la modificación para parsear JSON con llaves.")
    app.run(debug=True, port=5000)