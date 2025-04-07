import os
from cryptography.fernet import Fernet
import tkinter as tk
from tkinter import filedialog, messagebox

# Clave de cifrado (misma que usas para descifrar)
ENCRYPTION_KEY = b'yMybaWCe4meeb3v4LWNI4Sxz7oS54Gn0Fo9yJovqVN0='

def encrypt_api_key(api_key: str) -> bytes:
    f = Fernet(ENCRYPTION_KEY)
    return f.encrypt(api_key.encode("utf-8"))

def browse_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        output_path_var.set(os.path.join(folder_selected, "api.txt"))

def encrypt_and_save():
    api_key = api_key_entry.get("1.0", tk.END).strip()
    output_path = output_path_var.get()

    if not api_key:
        messagebox.showerror("Error", "Por favor, introduce una API key.")
        return

    if not output_path.endswith("api.txt"):
        messagebox.showerror("Error", "La ruta debe terminar en 'api.txt'")
        return

    try:
        encrypted = encrypt_api_key(api_key)
        with open(output_path, "wb") as file:
            file.write(encrypted)
        messagebox.showinfo("Éxito", f"API key encriptada guardada en:\n{output_path}")
    except PermissionError:
        messagebox.showerror("Permiso denegado", f"No tienes permiso para escribir en:\n{output_path}")
    except Exception as e:
        messagebox.showerror("Error", str(e))

# Interfaz
root = tk.Tk()
root.title("Encriptador de API Key")
root.geometry("500x300")
root.resizable(False, False)

tk.Label(root, text="Introduce tu API Key:", font=("Arial", 11)).pack(pady=10)
api_key_entry = tk.Text(root, height=4, width=60)
api_key_entry.pack()

tk.Label(root, text="Ruta de guardado (incluye 'api.txt'):", font=("Arial", 11)).pack(pady=10)
output_path_var = tk.StringVar()
tk.Entry(root, textvariable=output_path_var, width=60).pack()
tk.Button(root, text="Seleccionar carpeta", command=browse_folder).pack(pady=5)

tk.Button(root, text="Encriptar y guardar", command=encrypt_and_save, bg="green", fg="white").pack(pady=15)

root.mainloop()
