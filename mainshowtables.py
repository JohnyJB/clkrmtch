from flask import Flask, request, make_response
import pandas as pd
import os
import time

app = Flask(__name__)

df_user_csv = pd.DataFrame()
df_enriched_csv = pd.DataFrame()

def tabla_html(df: pd.DataFrame, max_filas=20) -> str:
    if df.empty:
        return "<p><em>Archivo CSV no encontrado o vacío</em></p>"

    cols = list(df.columns)
    anchas = ["ICP Job Titles", "ICP Job Titles Result", "LinkedIn Profile Analysis", 
              "Scrape Website", "Company Services", "Company Services Result"]
    thead = "".join(
        f"<th class='col-ancha'>{col}</th>" if col in anchas else f"<th>{col}</th>"
        for col in cols
    )

    rows_html = ""
    for _, row in df.head(max_filas).iterrows():
        row_html = "".join(
            f"<td class='col-ancha'>{str(row[col])}</td>" if col in anchas else f"<td>{str(row[col])}</td>"
            for col in cols
        )
        rows_html += f"<tr>{row_html}</tr>"

    return f"<table><tr>{thead}</tr>{rows_html}</table>"

@app.route("/", methods=["GET", "POST"])
def index():
    global df_user_csv, df_enriched_csv
    tabla = ""
    status = ""

    if request.method == "POST":
        accion = request.form.get("accion", "")

        if accion == "cargar_csv":
            archivo = request.files.get("csvfile")
            if archivo and archivo.filename:
                df_user_csv = pd.read_csv(archivo)
                status = f"Se cargaron {len(df_user_csv)} filas."

        elif accion == "mostrar_base":
            time.sleep(2)
            tabla = tabla_html(df_user_csv)

        elif accion == "enriquecer_ia":
            time.sleep(5)
            if not df_user_csv.empty:
                enriched_path = "archivo2.csv"
                if os.path.exists(enriched_path):
                    df_enriched_csv = pd.read_csv(enriched_path)
                    tabla = tabla_html(df_enriched_csv)
                    status = "Mostrando base enriquecida con IA."
                else:
                    status = "No se encontró archivo enriquecido (archivo2.csv)."
            else:
                status = "Primero carga un archivo CSV."

    return f"""
    <html>
    <head>
        <title>Enriquecedor IA</title>
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
                max-width: 90%;
                margin: 40px auto;
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
            input[type="file"] {{
                padding: 10px;
                margin: 10px;
                background: #2A2A2A;
                color: white;
                border-radius: 10px;
                border: 1px solid #555;
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
            <h1>Enriquecimiento de Datos con IA</h1>
            <form method="POST" enctype="multipart/form-data">
                <input type="file" name="csvfile" required />
                <input type="hidden" name="accion" value="cargar_csv" />
                <button type="submit">Subir Base de Datos CSV</button>
            </form>

            <form method="POST">
                <input type="hidden" name="accion" value="mostrar_base" />
                <button type="submit">Mostrar Base Cargada</button>
            </form>

            <form method="POST">
                <input type="hidden" name="accion" value="enriquecer_ia" />
                <button type="submit">Enriquecer con IA</button>
            </form>

            <p>{status}</p>
            <div>{tabla}</div>
        </div>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True, port=5001)