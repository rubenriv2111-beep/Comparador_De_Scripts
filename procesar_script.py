#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
from core.lectores import leer_sps_rps, leer_xps_completo, ENCABEZADOS_RPS, ENCABEZADOS_SPS, ENCABEZADOS_XPS
from core.qc_comparator import aplicar_estilo_hoja

def procesar_carpeta(ruta_carpeta):
    archivos = os.listdir(ruta_carpeta)
    rps_path = None
    sps_path = None
    xps_path = None

    # Buscar archivos
    for archivo in archivos:
        path_completo = os.path.join(ruta_carpeta, archivo)
        nombre_lower = archivo.lower()
        if nombre_lower == "script.rps" or nombre_lower.endswith(".rps"):
            rps_path = path_completo
        elif nombre_lower == "script.sps" or nombre_lower.endswith(".sps"):
            sps_path = path_completo
        elif nombre_lower == "script.xps" or nombre_lower.endswith(".xps"):
            xps_path = path_completo

    if not rps_path and not sps_path and not xps_path:
        messagebox.showerror("Error", "No se encontró ningún archivo Script.rps, Script.sps o Script.xps en la carpeta seleccionada.")
        return

    # Leer archivos
    df_rps = leer_sps_rps(rps_path, 'R') if rps_path else pd.DataFrame()
    df_sps = leer_sps_rps(sps_path, 'S') if sps_path else pd.DataFrame()
    df_xps = leer_xps_completo(xps_path) if xps_path else pd.DataFrame()

    nombre_salida = os.path.join(ruta_carpeta, "Reporte_Adquisicion_Estetico.xlsx")
    
    try:
        with pd.ExcelWriter(nombre_salida, engine='openpyxl') as writer:
            # Escribir RPS si existe
            if not df_rps.empty:
                df = df_rps.copy()
                df.rename(columns=ENCABEZADOS_RPS, inplace=True)
                df.to_excel(writer, sheet_name="RPS", index=False)
                aplicar_estilo_hoja(writer.sheets["RPS"], "2F5597")

            # Escribir SPS si existe
            if not df_sps.empty:
                df = df_sps.copy()
                df.rename(columns=ENCABEZADOS_SPS, inplace=True)
                df.to_excel(writer, sheet_name="SPS", index=False)
                aplicar_estilo_hoja(writer.sheets["SPS"], "375623")

            # Escribir XPS si existe
            if not df_xps.empty:
                df = df_xps.copy()
                df.rename(columns=ENCABEZADOS_XPS, inplace=True)
                df.to_excel(writer, sheet_name="XPS", index=False)
                aplicar_estilo_hoja(writer.sheets["XPS"], "595959")

        # Intentar abrir el Excel generado
        try:
            os.startfile(nombre_salida)
        except AttributeError:
            # En otros sistemas
            if sys.platform == "darwin":
                subprocess.call(["open", nombre_salida])
            else:
                subprocess.call(["xdg-open", nombre_salida])
        except Exception:
            pass

        messagebox.showinfo("Éxito", f"Reporte Excel generado con éxito:\n\n{nombre_salida}\n\nSe ha abierto de forma automática.")
    except PermissionError:
        messagebox.showerror("Error", f"No se pudo guardar el archivo porque ya está abierto en Excel.\nCierra '{os.path.basename(nombre_salida)}' y vuelve a intentarlo.")
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error inesperado:\n{str(e)}")

def main():
    root = tk.Tk()
    root.withdraw() # Ocultar ventana principal

    messagebox.showinfo("Selección de Carpeta", "A continuación, selecciona la carpeta donde están ubicados los archivos Script.rps, Script.sps y Script.xps.")
    
    # Abrir el selector de carpeta en la ruta por defecto del usuario
    ruta_defecto = r"C:\Users\Administrador\Desktop\Scripts_Adquisicion"
    if not os.path.exists(ruta_defecto):
        ruta_defecto = os.path.expanduser("~/Desktop")

    carpeta = filedialog.askdirectory(initialdir=ruta_defecto, title="Selecciona la carpeta con tus archivos Script")
    if not carpeta:
        return

    procesar_carpeta(carpeta)

if __name__ == "__main__":
    main()
