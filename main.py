import time
import os
import io
import re
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from flask import Flask, request, render_template_string, redirect, url_for, make_response

#########################################
# Se supone que tu entorno define:
# from openai import OpenAI
# client = OpenAI(api_key="...")
# Y se usa client.chat.completions.create(...)
#########################################
try:
    from openai import OpenAI
except ImportError:
    print("[ERROR] No se encontró 'from openai import OpenAI'. Asegúrate de usar la librería/wrapper adecuada.")
    OpenAI = None

client = None  # Se crea cuando se recibe la API Key

app = Flask(__name__)
app.secret_key = "CLAVE_SECRETA_PARA_SESSION"  # si deseas usar session

# DataFrame principal
df_leads = pd.DataFrame()

# Parámetros
scrap_proveedor_text = ""
api_key_global = ""
url_proveedor_global = ""

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

def _asegurar_https(url: str) -> str:
    """Si la URL no empieza con http(s)://, antepone https://."""
    url = url.strip()
    if not url:
        return ""
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = "https://" + url
    return url

def realizar_scraping(url: str) -> str:
    """Scrapea la URL (hasta MAX_SCRAPING_CHARS) y devuelve texto plano."""
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
            print("[LOG] Scraping completado. Chars extraídos:", len(truncated))
            return truncated
        else:
            print("[LOG] HTTP != 200, devolvemos '-'.")
            return "-"
    except Exception as e:
        print("[ERROR] Excepción en realizar_scraping:", e)
        return "-"

def generar_contenido_chatgpt_por_fila(row: pd.Series) -> dict:
    """
    Genera las columnas definidas: Personalization, Your Value Prop, etc.
    usando client.chat.completions.create(...).
    """
    if client is None:
        print("[ERROR] 'client' es None, no se puede llamar la API.")
        return {
            "Personalization":"-",
            "Your Value Prop":"-",
            "Target Niche":"-",
            "Your Targets Goal":"-",
            "Your Targets Value Prop":"-",
            "Cliffhanger Value Prop":"-",
            "CTA":"-"
        }

    # Extraer nombre de contacto
    lead_name = str(row.get(mapeo_nombre_contacto, "-"))

    # Extraer puesto/title
    title = str(row.get(mapeo_puesto, "-"))

    # Extraer industria
    industry = str(row.get(mapeo_industria, "-"))

    # Extraer empresa
    companyName = str(row.get(mapeo_empresa, "-"))
    
    # Extraer Ubicación
    location = str(row.get(mapeo_location, "-"))

    scrapping_lead = str(row.get("scrapping", "-"))
    scrapping_proveedor = str(row.get("scrapping_proveedor", "-"))

    # Prompt: sin corchetes, con datos reales
    prompt = f"""No uses corchetes ni placeholders. Usa los datos reales.
(Con “no uses corchetes” nos referimos a no usar nada como [NOMBRE] o [TEXTO], pero sí debes usar llaves para devolver tu respuesta en formato JSON.)

Eres un experto en comercial que se acerca estratégicamente a los clientes.

Tenemos un cliente llamado {companyName}.
Basado en esta información del cliente y del proveedor, genera los siguientes campos en español:

1. Personalization (usa el nombre del contacto, no te presentes, una introducción personalizada basada exclusivamente en la información del sitio web del cliente. El objetivo es captar su atención de inmediato.)
2. Your Value Prop (Propuesta de valor del proveedor, basado en su web.)
3. Target Niche (El segmento de mercado al que el proveedor llega, definido por industria, subsegmento, tamaño de empresa y ubicación del cliente.)
4. Your Targets Goal (La meta principal de {lead_name} considerando que es {title}. Qué quiere lograr con su negocio o estrategia.)
5. Your Targets Value Prop (La propuesta de valor de {companyName}. Cómo se diferencian en su mercado.)
6. Cliffhanger Value Prop (Propuesta intrigante o gancho para motivar la conversación.)
7. CTA (Acción concreta que queremos que tome el cliente, como agendar una reunión.)

Información del lead:
- Contacto: {lead_name}
- Puesto: {title}
- Industria: {industry}
- El cliente es: {companyName}
- Contenido del sitio web (scrapping del lead): {scrapping_lead}
- La ubicación de la empresa es: {location} (si no te doy una ubicación, ignóralo)

Información del proveedor:
- Contenido extraído del sitio web del proveedor: {scrapping_proveedor}

Responde solo en formato JSON, con las claves exactas (y en español):
"Personalization", 
"Your Value Prop", 
"Target Niche", 
"Your Targets Goal",
"Your Targets Value Prop", 
"Cliffhanger Value Prop", 
"CTA".

Dentro de cada clave, escribe el texto que corresponda, sin usar corchetes ni placeholders.

"""

    try:
        print("[LOG] Llamando ChatGPT con 'client.chat.completions.create(...)'")
        respuesta = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=OPENAI_MAX_TOKENS,
            temperature=0.7,
            timeout=30
        )
        content = respuesta.choices[0].message.content
        print("[LOG] Respuesta recibida. Parseamos JSON...")

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
            print("[ERROR] No se pudo parsear JSON:")
            print("Contenido recibido:")
            print(content if 'content' in locals() else "(content no definido)")
            print("Excepción:", ex)

            # Fallback en caso de fallo
            personalization = content if 'content' in locals() else "-"
            value_prop = "-"
            target_niche = "-"
            targets_goal = "-"
            targets_value_prop = "-"
            cliffhanger = "-"
            cta = "-"


        except Exception as ex:
            print("[ERROR] No se pudo parsear JSON:")
            print("Contenido recibido:")
            print(content)
            print("Excepción:", ex)

    
            # Guardamos todo en "Personalization"
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
        print("[ERROR] Al invocar ChatGPT:", e)
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
    """Scrapea website y asegura columnas necesarias en df_leads."""
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

def generar_contenido_para_todos():
    """Itera sobre df_leads y llama a ChatGPT para generar las columnas."""
    global df_leads
    if df_leads.empty:
        print("[LOG] df_leads vacío, no generamos contenido.")
        return

    for idx, row in df_leads.iterrows():
        try:
            print(f"[LOG] Generando ChatGPT para lead idx={idx}...")
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

        df_leads.at[idx, "Personalization"] = result["Personalization"]
        df_leads.at[idx, "Your Value Prop"] = result["Your Value Prop"]
        df_leads.at[idx, "Target Niche"] = result["Target Niche"]
        df_leads.at[idx, "Your Targets Goal"] = result["Your Targets Goal"]
        df_leads.at[idx, "Your Targets Value Prop"] = result["Your Targets Value Prop"]
        df_leads.at[idx, "Cliffhanger Value Prop"] = result["Cliffhanger Value Prop"]
        df_leads.at[idx, "CTA"] = result["CTA"]
        time.sleep(1.5) 

    # Tras generarlo, hacemos limpieza de "NaN"/"nan" y quitamos corchetes.
    cleanup_leads()

def cleanup_leads():
    """Reemplaza NaN, nan, None con '-' y quita corchetes [ ] en las columnas."""
    global df_leads
    if df_leads.empty:
        return
    # Columnas a limpiar
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
            df_leads[col] = df_leads[col].replace(r"\[|\]", "", regex=True)

def tabla_html(df: pd.DataFrame, max_filas=5) -> str:
    """Convierte las primeras 'max_filas' filas del DF en tabla HTML."""
    if df.empty:
        return "<p><em>DataFrame vacío</em></p>"
    subset = df.head(max_filas)
    cols = list(subset.columns)
    thead = "".join(f"<th>{col}</th>" for col in cols)
    rows_html = ""
    for _, row in subset.iterrows():
        row_html = "".join(f"<td>{str(row[col])}</td>" for col in cols)
        rows_html += f"<tr>{row_html}</tr>"
    return f"<table><tr>{thead}</tr>{rows_html}</table>"

@app.route("/", methods=["GET","POST"])
def index():
    global client
    global df_leads
    global scrap_proveedor_text
    global api_key_global, url_proveedor_global

    # Variables globales para mapeo
    global mapeo_nombre_contacto
    global mapeo_puesto
    global mapeo_empresa
    global mapeo_industria
    global mapeo_website
    global mapeo_location

    status_msg = ""

    if request.method == "POST":
        # Subir CSV de leads
        leadf = request.files.get("leads_csv")
        if leadf and leadf.filename:
            df_leads = pd.read_csv(leadf)
            status_msg += f"Leads CSV cargado, filas={len(df_leads)}<br>"

        # Parámetros
        new_api = request.form.get("api_key", "").strip()
        if new_api:
            api_key_global = new_api
            status_msg += "API Key actualizada.<br>"
            if OpenAI:
                client = OpenAI(api_key=new_api)
            else:
                status_msg += "[ERROR] 'OpenAI' no disponible.<br>"

        new_urlp = request.form.get("url_proveedor", "").strip()
        if new_urlp:
            url_proveedor_global = new_urlp
            status_msg += f"URL Proveedor={url_proveedor_global}<br>"

        # Mapeo de columnas
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
            status_msg += f"Mapeo Website = '{col_location}'<br>"

        # Acción
        accion = request.form.get("accion", "")
        if accion == "scrap_proveedor" and url_proveedor_global:
            # Scrape
            sc = realizar_scraping(url_proveedor_global)
            scrap_proveedor_text = sc
            if not df_leads.empty:
                df_leads["scrapping_proveedor"] = sc
            status_msg += "Scraping del proveedor asignado a df_leads.<br>"

        elif accion == "generar_tabla":
            procesar_leads()
            generar_contenido_para_todos()
            status_msg += "Leads procesados y ChatGPT aplicado. Revisa la tabla abajo.<br>"

        elif accion == "exportar_archivo":
            formato = request.form.get("formato", "csv")
            if df_leads.empty:
                status_msg += "No hay leads para exportar.<br>"
            else:
                if formato == "csv":
                    csv_output = io.StringIO()
                    df_leads.to_csv(csv_output, index=False, encoding="utf-8-sig")
                    csv_output.seek(0)
                    resp = make_response(csv_output.getvalue())
                    resp.headers["Content-Disposition"] = "attachment; filename=leads_final.csv"
                    resp.headers["Content-Type"] = "text/csv"
                    return resp
                else:
                    # XLSX
                    from openpyxl import Workbook
                    bio = io.BytesIO()
                    df_leads.to_excel(bio, index=False, engine="openpyxl")
                    bio.seek(0)
                    resp = make_response(bio.getvalue())
                    resp.headers["Content-Disposition"] = "attachment; filename=leads_final.xlsx"
                    resp.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    return resp

    # Bloque final en español (Cold Email Strategy)
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

    # Generación del HTML principal
    # Se eliminó cualquier mención a segment/clicker ni "caso de éxito".
    page_html = f"""
    <html>
    <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}">
    <head>
        <title>Campaign Maker: Sin corchetes, sin NaN, con Nombre real</title>
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
            }}
            table th {{
                background-color: #1E90FF;
                color: #fff;
            }}
            table td {{
                color: #000;
            }}
            table tr:hover {{
                background-color: #2A2A2A;
                color: #fff;
                transition: background-color 0.3s;
            }}
            table th, td {{
                vertical-align: middle;
                padding: 8px;
                border: 1px solid #444;
            }}
            input[type="file"],
            input[type="text"],
            input[type="password"],
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
                max-height: 150px;
                overflow-y: auto;
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
            .content-block table {{
                width: 100%;
                border-collapse: collapse;
                background:#fff;
                color: #000;
            }}
            .content-block th, .content-block td {{
                border: 1px solid #444;
                padding: 8px;
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
          <button type="submit">Subir Archivo</button>
        </form>
        <hr>

        <form method="POST">
          <h2>2) Parámetros</h2>
          <label>API Key ChatGPT:</label>
          <input type="password"name="api_key" value="{api_key_global}"/>
          <label>Tu sitio WEB</label>
          <input type="text" name="url_proveedor" value="{url_proveedor_global}"/>

          <p>Mapeo de columnas (si tu CSV usa nombres distintos):</p>
          <label>Nombre del contacto:</label>
          <select name="col_nombre">
            <option value="">(Sin cambio)</option>
            {"".join([f"<option value='{c}'>{c}</option>" for c in df_leads.columns])}
          </select>

          <label>Puesto/Title:</label>
          <select name="col_puesto">
            <option value="">(Sin cambio)</option>
            {"".join([f"<option value='{c}'>{c}</option>" for c in df_leads.columns])}
          </select>
        

          <label>Nombre de la empresa:</label>
          <select name="col_empresa">
            <option value="">(Sin cambio)</option>
            {"".join([f"<option value='{c}'>{c}</option>" for c in df_leads.columns])}
          </select>

          <label>Industria:</label>
          <select name="col_industria">
            <option value="">(Sin cambio)</option>
            {"".join([f"<option value='{c}'>{c}</option>" for c in df_leads.columns])}
          </select>

          <label>Website:</label>
          <select name="col_website">
            <option value="">(Sin cambio)</option>
            {"".join([f"<option value='{c}'>{c}</option>" for c in df_leads.columns])}
          </select>
          
          <label>Ubicación:</label>
          <select name="col_location">
            <option value="">(Sin cambio)</option>
            {"".join([f"<option value='{c}'>{c}</option>" for c in df_leads.columns])}
          </select>

          <input type="hidden" name="accion" value="scrap_proveedor"/>
          <button type="submit">Obtener Información del proveedor</button>
        </form>

        <div class="scrap-container">
          <strong>Información Proveedor:</strong><br>
          {scrap_proveedor_text.replace("<","&lt;").replace(">","&gt;")}
        </div>
        <hr>

        <form method="POST">
          <h2>3) Generar Tabla</h2>
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
        <h2>Base de datos</h2>
        {tabla_html(df_leads,7)}
      </div>

      <div class="content-block">
        {block_text_es}
      </div>
    </body>
    </html>
    """

    return page_html

if __name__ == "__main__":
    print("[LOG] Inicia la app: sin corchetes, sin NaN, mapeo de columnas y sin segment/clicker.")
    app.run(debug=True, port=5000)
