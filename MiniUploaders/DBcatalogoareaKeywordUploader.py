import pandas as pd
from tkinter import Tk, Button, Label, filedialog, messagebox
import os

def limpiar_y_convertir(path):
    try:
        # Leer Excel
        df = pd.read_excel(path)

        # Eliminar columnas tipo "Unnamed"
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]

        # Mantener solo las primeras 7 columnas
        df = df.iloc[:, :7]

        # Crear nombre de salida
        nombre_salida = os.path.splitext(os.path.basename(path))[0] + "_limpio.csv"
        ruta_salida = os.path.join(os.path.dirname(path), nombre_salida)

        # Guardar como CSV en UTF-8 sin BOM
        df.to_csv(ruta_salida, index=False, encoding="utf-8")

        messagebox.showinfo("Éxito", f"✅ Archivo generado:\n{ruta_salida}")
        print(f"✅ CSV guardado en: {ruta_salida}")

    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error:\n{e}")

def seleccionar_archivo():
    ruta = filedialog.askopenfilename(
        title="Selecciona el archivo Excel",
        filetypes=[("Archivos Excel", "*.xlsx *.xls")]
    )
    if ruta:
        limpiar_y_convertir(ruta)

# Interfaz
app = Tk()
app.title("Convertidor XLSX a CSV limpio (UTF-8)")
app.geometry("460x200")

Label(app, text="Convierte .xlsx a .csv UTF-8 (solo primeras 7 columnas)").pack(pady=20)
Button(app, text="Seleccionar archivo", command=seleccionar_archivo, bg="#4CAF50", fg="white", padx=12, pady=6).pack()
Button(app, text="Salir", command=app.quit, bg="#f44336", fg="white", padx=12, pady=6).pack(pady=10)

app.mainloop()
