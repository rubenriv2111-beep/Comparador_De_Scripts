# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import webbrowser
import functools
from core.generador_mapa import generar_mapa_completo
from core.qc_comparator import comparar_carpetas
from utils.progreso import Progreso

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Mapa de Actividad - Interactivo")
        self.root.geometry("600x850")
        self.root.resizable(True, True)

        self.ruta_rps = ""
        self.ruta_sps = ""
        self.ruta_xps = ""

        style = ttk.Style()
        style.theme_use('clam')

        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Generador de Mapa Interactivo",
                  font=("Arial", 12, "bold")).pack(pady=(0, 20))

        # ---- Archivos ----
        ttk.Label(main_frame, text="1. Archivos:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        btn_rps = ttk.Button(main_frame, text="Seleccionar RPS", command=self.seleccionar_rps)
        btn_rps.pack(fill=tk.X, pady=(10, 2))
        self.lbl_rps = ttk.Label(main_frame, text="No seleccionado", foreground="gray")
        self.lbl_rps.pack(anchor=tk.W)

        btn_sps = ttk.Button(main_frame, text="Seleccionar SPS (opcional)", command=self.seleccionar_sps)
        btn_sps.pack(fill=tk.X, pady=(10, 2))
        self.lbl_sps = ttk.Label(main_frame, text="No seleccionado", foreground="gray")
        self.lbl_sps.pack(anchor=tk.W)

        btn_xps = ttk.Button(main_frame, text="Seleccionar XPS (opcional)", command=self.seleccionar_xps)
        btn_xps.pack(fill=tk.X, pady=(10, 2))
        self.lbl_xps = ttk.Label(main_frame, text="No seleccionado", foreground="gray")
        self.lbl_xps.pack(anchor=tk.W)

        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=20)

        # ---- Configuración ----
        ttk.Label(main_frame, text="2. Configuración:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        frame_utm = ttk.Frame(main_frame)
        frame_utm.pack(fill=tk.X, pady=5)
        ttk.Label(frame_utm, text="Zona UTM:").pack(side=tk.LEFT)
        self.combo_zona = ttk.Combobox(frame_utm, values=["Zona 14N (Q14)", "Zona 15N (Q15)"],
                                       state="readonly", width=20)
        self.combo_zona.current(0)
        self.combo_zona.pack(side=tk.LEFT, padx=10)

        frame_muestreo = ttk.Frame(main_frame)
        frame_muestreo.pack(fill=tk.X, pady=5)
        ttk.Label(frame_muestreo, text="Muestreo (1 de cada N):").pack(side=tk.LEFT)
        self.spin_muestreo = ttk.Spinbox(frame_muestreo, from_=1, to=200, width=5)
        self.spin_muestreo.set(30)
        self.spin_muestreo.pack(side=tk.LEFT, padx=10)

        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=20)

        # ---- Botones principales ----
        self.btn_generar = ttk.Button(main_frame, text="GENERAR MAPA", command=self.procesar)
        self.btn_generar.pack(fill=tk.X, pady=10, ipady=10)

        self.btn_qc = ttk.Button(main_frame, text="Comparar Paquetes Diarios (QC)", 
                                  command=self.comparar_paquetes_callback)
        self.btn_qc.pack(fill=tk.X, pady=10, ipady=10)

        # ---- Progreso ----
        self.progress = ttk.Progressbar(main_frame, mode='determinate', length=200)
        self.progress.pack(pady=5)

        self.lbl_estado = ttk.Label(main_frame, text="Listo", foreground="blue")
        self.lbl_estado.pack(pady=10)

        # ---- Info ----
        info = """INTERACTIVIDAD:
- Haz clic en una fuente (roja) → popup con botón "Resaltar receptores".
- Los receptores asociados se ponen AMARILLOS, los demás se atenúan.
- Botón "Restaurar" para volver a colores originales.

QC - COMPARACIÓN DE PAQUETES:
- Selecciona múltiples carpetas (cada carpeta = un día).
- El script ordena por nombre y compara días consecutivos.
- Genera Excel con diferencias entre paquetes."""
        ttk.Label(main_frame, text=info, justify=tk.LEFT, foreground="gray", font=("Arial", 8)).pack(pady=10)

    def seleccionar_rps(self):
        ruta = filedialog.askopenfilename(filetypes=[("RPS", "*.rps *.rcp *.txt"), ("Todos", "*.*")])
        if ruta:
            self.ruta_rps = ruta
            self.lbl_rps.config(text=os.path.basename(ruta))

    def seleccionar_sps(self):
        ruta = filedialog.askopenfilename(filetypes=[("SPS", "*.sps *.txt"), ("Todos", "*.*")])
        if ruta:
            self.ruta_sps = ruta
            self.lbl_sps.config(text=os.path.basename(ruta))

    def seleccionar_xps(self):
        ruta = filedialog.askopenfilename(filetypes=[("XPS", "*.xps"), ("Todos", "*.*")])
        if ruta:
            self.ruta_xps = ruta
            self.lbl_xps.config(text=os.path.basename(ruta))

    def procesar(self):
        if not self.ruta_rps and not self.ruta_sps:
            messagebox.showwarning("Error", "Selecciona al menos RPS o SPS.")
            return

        self.btn_generar.config(state="disabled")
        self.btn_qc.config(state="disabled")
        self.progress['value'] = 0
        self.lbl_estado.config(text="Procesando...")

        epsg = 32614 if self.combo_zona.get() == "Zona 14N (Q14)" else 32615
        muestreo = int(self.spin_muestreo.get())

        progreso = Progreso(self.root, self.progress, self.lbl_estado)

        def tarea():
            try:
                generar_mapa_completo(
                    self.ruta_rps, self.ruta_sps, self.ruta_xps,
                    epsg, muestreo, progreso
                )
                self.root.after(0, self._ok)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, functools.partial(self._error, str(e)))

        threading.Thread(target=tarea, daemon=True).start()

    def _ok(self):
        self.btn_generar.config(state="normal")
        self.btn_qc.config(state="normal")
        self.progress['value'] = 100
        self.lbl_estado.config(text="Mapa listo")
        webbrowser.open('file://' + os.path.realpath("mapa_sismico.html"))
        messagebox.showinfo("Éxito", "Mapa generado con interactividad.")

    def _error(self, msg):
        self.btn_generar.config(state="normal")
        self.btn_qc.config(state="normal")
        self.progress['value'] = 0
        self.lbl_estado.config(text="Error")
        messagebox.showerror("Error", msg)

    def comparar_paquetes_callback(self):
        carpetas = []
        while True:
            carpeta = filedialog.askdirectory(
                title="Selecciona una carpeta (paquete diario). Presiona Cancelar para finalizar."
            )
            if not carpeta:
                break
            carpetas.append(carpeta)
            if not messagebox.askyesno("Agregar carpeta", "¿Quieres seleccionar otra carpeta?"):
                break
        
        if len(carpetas) < 2:
            messagebox.showwarning("Advertencia", "Selecciona al menos 2 carpetas diferentes para comparar.")
            return
        
        mensaje = "Carpetas seleccionadas:\n" + "\n".join([f"- {os.path.basename(c)}" for c in carpetas])
        messagebox.showinfo("Carpetas seleccionadas", mensaje)

        self.btn_generar.config(state="disabled")
        self.btn_qc.config(state="disabled")
        self.progress['value'] = 0
        self.lbl_estado.config(text="Comparando carpetas...")

        progreso = Progreso(self.root, self.progress, self.lbl_estado)

        def tarea():
            try:
                resultados = comparar_carpetas(carpetas, progreso)
                self.root.after(0, self._finalizar_qc, resultados)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, functools.partial(self._error, str(e)))

        threading.Thread(target=tarea, daemon=True).start()

    def _finalizar_qc(self, resultados):
        self.btn_generar.config(state="normal")
        self.btn_qc.config(state="normal")
        self.progress['value'] = 100
        
        if resultados and any(not df.empty for df in resultados.get('diferencias', {}).values()):
            total_diff = sum(len(df) for df in resultados['diferencias'].values())
            self.lbl_estado.config(text=f"QC completado. {total_diff} diferencias encontradas.")
            messagebox.showinfo("QC Completado", 
                              f"Se generó 'comparacion_paquetes.xlsx' con {total_diff} diferencias.\n\n"
                              "Revísalo en la carpeta del programa.")
        else:
            self.lbl_estado.config(text="No se encontraron diferencias entre carpetas.")
            messagebox.showinfo("QC Completado", 
                              "Todas las carpetas comparadas son idénticas (sin diferencias).")