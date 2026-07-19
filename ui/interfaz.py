# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import webbrowser
import functools
import pandas as pd

from core.generador_mapa import generar_mapa_completo
from core.qc_comparator import comparar_carpetas
from utils.progreso import Progreso
from core.comparador_disparos import run_comparison, export_xlsx, export_txt, export_comparativa

# Paleta de colores ejecutiva y corporativa inspirada en SINOPEC
COLORS = {
    "bg":         "#F4F5F7",   # Gris claro suave
    "surface":    "#FFFFFF",   # Superficie blanca
    "border":     "#E2E8F0",   # Borde gris claro moderno
    "text":       "#1E293B",   # Texto principal gris oscuro
    "muted":      "#64748B",   # Texto secundario/silenciado
    "accent":     "#0F2942",   # Azul SINOPEC (primario corporativo)
    "accent_hover":"#1E3A5F",  # Azul SINOPEC hover
    "red_accent": "#E60012",   # Rojo SINOPEC (resaltado corporativo)
    
    # Colores de estado pasteles profesionales (sin emojis ni colores chillones)
    "ok_row":     "#E2EFDA",   # Verde claro pastel
    "ok_txt":     "#375623",   # Verde oscuro
    "diff_row":   "#FFF2CC",   # Amarillo claro pastel
    "diff_txt":   "#7F6000",   # Dorado oscuro
    "only1_row":  "#D9E1F2",   # Azul claro pastel
    "only1_txt":  "#1F4E78",   # Azul acero oscuro
    "only2_row":  "#F2F2F2",   # Gris claro pastel
    "only2_txt":  "#595959",   # Gris oscuro
    
    "col_hdr":    "#E2E8F0",
    "col_hdr_txt":"#334155",
}

FONT      = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_SM   = ("Segoe UI", 9)
FONT_H1   = ("Segoe UI", 13, "bold")
FONT_MONO = ("Consolas", 9)

# Ancho fijo para la columna Disparo en el comparador de disparos
COL_DISP  = 130


# ─── Selector de archivo corporativo ──────────────────────────────────────────
class FileSelector(tk.Frame):
    def __init__(self, parent, label, **kw):
        super().__init__(parent, bg=COLORS["surface"],
                         highlightthickness=1,
                         highlightbackground=COLORS["border"], **kw)
        self._path = tk.StringVar()
        self._label = label
        self._build()

    def _build(self):
        tk.Label(self, text=self._label, font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(12, 3))
        self._icon = tk.Label(self, text="📁", font=("Segoe UI", 24),
                              bg=COLORS["surface"], fg=COLORS["accent"])
        self._icon.pack()
        self._info = tk.Label(self,
                              text="Haz clic para seleccionar un archivo",
                              font=FONT_SM, bg=COLORS["surface"],
                              fg=COLORS["muted"], wraplength=260)
        self._info.pack(pady=(3, 8))
        
        btn = tk.Button(self, text="Seleccionar archivo",
                        font=FONT_SM, cursor="hand2",
                        bg=COLORS["bg"], fg=COLORS["text"],
                        relief="flat", bd=1,
                        activebackground=COLORS["border"],
                        command=self._pick)
        btn.pack(pady=(0, 12))

    def _pick(self):
        p = filedialog.askopenfilename(
            filetypes=[("Archivos sísmicos (SPS/XPS/RPS)", "*.sps *.xps *.rps *.rcp *.txt"), ("Todos", "*.*")])
        if not p:
            return
        self.set_path(p)

    def set_path(self, path):
        self._path.set(path)
        name = os.path.basename(path)
        try:
            with open(path, "r", errors="replace") as f:
                lcount = sum(1 for _ in f)
            xcount = sum(1 for ln in open(path, "r", errors="replace")
                         if ln.strip().startswith("X"))
        except Exception:
            lcount = xcount = 0
            
        info_text = f"{name}\n{lcount:,} líneas"
        if xcount > 0:
            info_text += f"  ·  {xcount:,} registros X"
            
        self._info.configure(text=info_text, fg=COLORS["accent"])
        self._icon.configure(text="📄", fg=COLORS["ok_txt"])

    def get(self):
        return self._path.get()

    def clear(self):
        self._path.set("")
        self._info.configure(text="Haz clic para seleccionar un archivo", fg=COLORS["muted"])
        self._icon.configure(text="📁", fg=COLORS["accent"])


# ─── Tarjeta de métrica corporativa ───────────────────────────────────────────
class MetricCard(tk.Frame):
    def __init__(self, parent, label, **kw):
        super().__init__(parent, bg=COLORS["surface"],
                         highlightthickness=1,
                         highlightbackground=COLORS["border"], **kw)
        tk.Label(self, text=label, font=("Segoe UI", 8, "bold"),
                 bg=COLORS["surface"], fg=COLORS["muted"]).pack(pady=(10, 2), padx=10)
        self._val = tk.Label(self, text="—", font=("Segoe UI", 16, "bold"),
                             bg=COLORS["surface"], fg=COLORS["text"])
        self._val.pack(pady=(0, 10))

    def set(self, value, color=None):
        self._val.configure(text=str(value), fg=color or COLORS["text"])


# ─── Fila de disparo (3 columnas) ────────────────────────────────────────────
class DisparoRow(tk.Frame):
    def __init__(self, parent, r: dict, **kw):
        super().__init__(parent, bg=COLORS["bg"], **kw)
        self._r = r
        self._open = False
        self._detail = None
        self._build_header()

    def _meta(self):
        # Mapea estados a los colores pasteles corporativos
        meta_dict = {
            "ok":    ("Idéntico",          "ok_row",    "ok_txt"),
            "diff":  ("Con diferencias",   "diff_row",  "diff_txt"),
            "only1": ("Solo en Archivo 1", "only1_row", "only1_txt"),
            "only2": ("Solo en Archivo 2", "only2_row", "only2_txt"),
        }
        return meta_dict.get(self._r["status"], meta_dict["diff"])

    def _build_header(self):
        r = self._r
        lbl, bg_key, fg_key = self._meta()
        bg = COLORS[bg_key]
        fg = COLORS[fg_key]

        self._hdr = tk.Frame(self, bg=bg, cursor="hand2")
        self._hdr.pack(fill="x")
        self._hdr.bind("<Button-1>", self._toggle)

        # ── Columna DISPARO (izquierda) ──
        disp_cell = tk.Frame(self._hdr, bg=bg, width=COL_DISP)
        disp_cell.pack(side="left", fill="y")
        disp_cell.pack_propagate(False)
        tk.Label(disp_cell, text=f"Disparo\n{r['disparo']}",
                 font=FONT_BOLD, bg=bg, fg=fg,
                 justify="center").pack(expand=True)
        disp_cell.bind("<Button-1>", self._toggle)

        # ── Separador ──
        tk.Frame(self._hdr, bg=COLORS["border"], width=1).pack(side="left", fill="y")

        # ── Columna ARCHIVO 1 (centro) ──
        a1_cell = tk.Frame(self._hdr, bg=bg)
        a1_cell.pack(side="left", fill="both", expand=True)
        self._a1_lbl = tk.Label(a1_cell, font=FONT_SM, bg=bg, fg=fg,
                                anchor="center", justify="center")
        self._a1_lbl.pack(expand=True, fill="both", padx=6, pady=6)
        a1_cell.bind("<Button-1>", self._toggle)
        self._a1_lbl.bind("<Button-1>", self._toggle)

        # ── Separador ──
        tk.Frame(self._hdr, bg=COLORS["border"], width=1).pack(side="left", fill="y")

        # ── Columna ARCHIVO 2 (derecha) ──
        a2_cell = tk.Frame(self._hdr, bg=bg)
        a2_cell.pack(side="left", fill="both", expand=True)
        self._a2_lbl = tk.Label(a2_cell, font=FONT_SM, bg=bg, fg=fg,
                                anchor="center", justify="center")
        self._a2_lbl.pack(expand=True, fill="both", padx=6, pady=6)
        a2_cell.bind("<Button-1>", self._toggle)
        self._a2_lbl.bind("<Button-1>", self._toggle)

        # ── Flecha (solo si tiene detalles/diferencias) ──
        if r["status"] == "diff":
            self._arrow = tk.Label(self._hdr, text=" ▾ ", font=FONT_SM,
                                   bg=bg, fg=fg)
            self._arrow.pack(side="right", padx=10)
            self._arrow.bind("<Button-1>", self._toggle)

        self._fill_cells()

    def _fill_cells(self):
        r = self._r
        s = r["status"]

        if s == "ok":
            n1 = r.get("n_lineas1", "—")
            self._a1_lbl.configure(text=f"{n1} líneas")
            self._a2_lbl.configure(text=f"{r.get('n_lineas2','—')} líneas")

        elif s == "only1":
            self._a1_lbl.configure(text=f"{r.get('n_lineas1','—')} líneas\n(presente)")
            self._a2_lbl.configure(text="—\n(ausente)")

        elif s == "only2":
            self._a1_lbl.configure(text="—\n(ausente)")
            self._a2_lbl.configure(text=f"{r.get('n_lineas2','—')} líneas\n(presente)")

        else:  # diff
            ndiff = sum(1 for lr in r["lineas"] if lr["status"] != "ok")
            nok   = sum(1 for lr in r["lineas"] if lr["status"] == "ok")
            self._a1_lbl.configure(
                text=f"{r.get('n_lineas1','—')} líneas\n{nok} ok · {ndiff} con difs.")
            self._a2_lbl.configure(
                text=f"{r.get('n_lineas2','—')} líneas\n{nok} ok · {ndiff} con difs.")

    def _toggle(self, _=None):
        if self._r["status"] != "diff":
            return
        self._open = not self._open
        if self._open:
            self._arrow.configure(text=" ▴ ")
            self._show_detail()
        else:
            self._arrow.configure(text=" ▾ ")
            if self._detail:
                self._detail.destroy()
                self._detail = None

    def _show_detail(self):
        """Panel de detalle: tabla de líneas con 3 columnas."""
        self._detail = tk.Frame(self, bg=COLORS["surface"],
                                highlightthickness=1,
                                highlightbackground=COLORS["border"])
        self._detail.pack(fill="x", padx=2, pady=(0, 4))

        # Cabecera de la tabla interna
        hdr = tk.Frame(self._detail, bg=COLORS["col_hdr"])
        hdr.pack(fill="x")
        for txt, w, side in [
            ("Línea",     100, "left"),
            ("Estacas Archivo 1", 0,   "left"),
            ("Estacas Archivo 2", 0,   "left"),
        ]:
            kw = {"width": w} if w else {}
            lbl = tk.Label(hdr, text=txt, font=FONT_BOLD,
                           bg=COLORS["col_hdr"], fg=COLORS["col_hdr_txt"],
                           anchor="center", padx=6, pady=4, **kw)
            lbl.pack(side=side, fill="both", expand=(w == 0))

        # Filas de líneas
        for i, lr in enumerate(self._r["lineas"]):
            s = lr["status"]
            row_bg = COLORS.get(STATUS_META_ROW.get(s, "surface"), COLORS["surface"])
            row_fg = COLORS.get(STATUS_META_TXT.get(s, "text"), COLORS["text"])
            alt_bg = self._lighten(row_bg) if i % 2 == 0 else row_bg

            row = tk.Frame(self._detail, bg=alt_bg)
            row.pack(fill="x")

            # Celda línea
            lin_cell = tk.Frame(row, bg=alt_bg, width=100)
            lin_cell.pack(side="left", fill="y")
            lin_cell.pack_propagate(False)
            tk.Label(lin_cell, text=lr["linea"], font=FONT_MONO,
                     bg=alt_bg, fg=row_fg, anchor="center").pack(
                expand=True, fill="both", pady=3)

            tk.Frame(row, bg=COLORS["border"], width=1).pack(side="left", fill="y")

            # Celdas de contenido por archivo
            def fmt_cell(linea_r, arch):
                if arch == 1:
                    s_ = linea_r["status"]
                    if s_ == "only2": return "—"
                    lst = linea_r["estacas1"]
                else:
                    s_ = linea_r["status"]
                    if s_ == "only1": return "—"
                    lst = linea_r["estacas2"]
                if not lst: return "—"
                def _n(x): return float(x) if x.lstrip("-").replace(".","").isdigit() else 0
                ini = min((e[0] for e in lst), key=_n)
                fin = max((e[1] for e in lst), key=_n)
                return f"{ini} → {fin}" if len(lst) == 1 else f"{ini} → {fin}  ({len(lst)} rangos)"

            for arch in (1, 2):
                cell_txt = fmt_cell(lr, arch)
                # Marcar diferencias de estacas
                extra = ""
                if s == "diff":
                    missing = [ed for ed in lr["estaca_diffs"]
                               if (arch == 1 and ed["tipo"] == "solo_arch2") or
                                  (arch == 2 and ed["tipo"] == "solo_arch1")]
                    if missing:
                        extra = "\n⚠ " + "  ".join(f"{e['ini']}→{e['fin']}" for e in missing[:3])
                        if len(missing) > 3:
                            extra += f" +{len(missing)-3}"

                a_cell = tk.Frame(row, bg=alt_bg)
                a_cell.pack(side="left", fill="both", expand=True)
                tk.Label(a_cell, text=cell_txt + extra,
                         font=FONT_MONO, bg=alt_bg, fg=row_fg,
                         anchor="center", justify="center",
                         padx=6, pady=3).pack(fill="both", expand=True)
                if arch == 1:
                    tk.Frame(row, bg=COLORS["border"], width=1).pack(side="left", fill="y")

            # Separador entre filas
            tk.Frame(self._detail, bg=COLORS["border"], height=1).pack(fill="x")

    @staticmethod
    def _lighten(hex_color):
        """Aclara un color hexadecimal mezclándolo con blanco."""
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            r = min(255, r + (255 - r) // 3)
            g = min(255, g + (255 - g) // 3)
            b = min(255, b + (255 - b) // 3)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color


STATUS_META_ROW = {
    "ok":    "ok_row",
    "diff":  "diff_row",
    "only1": "only1_row",
    "only2": "only2_row",
}
STATUS_META_TXT = {
    "ok":    "ok_txt",
    "diff":  "diff_txt",
    "only1": "only1_txt",
    "only2": "only2_txt",
}


# ─── Aplicación Principal ─────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("SINOPEC - Herramientas Sísmicas de Adquisición")
        
        # Geometría ejecutiva y moderna
        self.root.geometry("1100x820")
        self.root.minsize(1050, 720)
        self.root.configure(bg=COLORS["bg"])
        
        # Rutas de mapa
        self.ruta_rps = ""
        self.ruta_sps = ""
        self.ruta_xps = ""
        
        # Resultados de comparación individual
        self._result = None
        self._disp_frames = []
        
        self._build_interface()

    def _build_interface(self):
        # ── Estilos generales del Notebook y ttk widgets ──
        style = ttk.Style(self.root)
        style.theme_use("clam")
        
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0, highlightthickness=0)
        style.configure("TNotebook.Tab", background="#CBD5E1", foreground="#334155", 
                        font=("Segoe UI", 10, "bold"), padding=[20, 8])
        style.map("TNotebook.Tab", 
                  background=[("selected", COLORS["accent"])], 
                  foreground=[("selected", "#FFFFFF")])
                  
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["surface"], relief="flat")
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONT)
        style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground=COLORS["accent"])
        style.configure("TSeparator", background=COLORS["border"])
        
        # ── 1. LOGO Y HEADER CORPORATIVO (Siempre visible arriba) ──
        header_frame = tk.Frame(self.root, bg="white", height=85)
        header_frame.pack(fill="x", side="top")
        header_frame.pack_propagate(False)
        
        # Agregar una línea inferior roja (Rojo corporativo SINOPEC)
        linea_roja = tk.Frame(self.root, bg=COLORS["red_accent"], height=4)
        linea_roja.pack(fill="x", side="top")

        # Cargar logotipo SINOPEC
        logo_path = r"C:\Users\Administrador\Desktop\Scripts_Adquisicion\resources\LOGO.PNG"
        if os.path.exists(logo_path):
            try:
                self.logo_img = tk.PhotoImage(file=logo_path)
                h = self.logo_img.height()
                if h > 65: # Redimensionar si es muy alto
                    scale = int(h / 65) + 1
                    self.logo_img = self.logo_img.subsample(scale, scale)
                
                logo_lbl = tk.Label(header_frame, image=self.logo_img, bg="white")
                logo_lbl.pack(pady=5, expand=True)
            except Exception as e:
                print("Error loading logo image:", e)
                # Fallback texto corporativo
                lbl = tk.Label(header_frame, text="SINOPEC GEOPHYSICAL", font=("Segoe UI", 18, "bold"), fg=COLORS["accent"], bg="white")
                lbl.pack(expand=True)
        else:
            lbl = tk.Label(header_frame, text="SINOPEC GEOPHYSICAL SERVICES", font=("Segoe UI", 18, "bold"), fg=COLORS["accent"], bg="white")
            lbl.pack(expand=True)

        # ── 2. CONTENEDOR PRINCIPAL: NOTEBOOK ──
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=15, pady=(15, 10))

        # Crear las pestañas
        self.tab_mapa = ttk.Frame(self.notebook)
        self.tab_individual = ttk.Frame(self.notebook)
        self.tab_paquetes = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_mapa, text=" Generador de Mapa Sísmico ")
        self.notebook.add(self.tab_individual, text=" Comparador Individual SPS / XPS ")
        self.notebook.add(self.tab_paquetes, text=" Comparador de Paquetes Diarios (QC) ")

        # Construir cada pestaña
        self._build_tab_mapa()
        self._build_tab_individual()
        self._build_tab_paquetes()

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 1: GENERACIÓN DE MAPA SÍSMICO
    # ──────────────────────────────────────────────────────────────────────────
    def _build_tab_mapa(self):
        main_frame = ttk.Frame(self.tab_mapa, padding="25")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Contenedor central (tarjeta blanca corporativa)
        card = ttk.Frame(main_frame, style="Card.TFrame", padding="20")
        card.pack(fill=tk.BOTH, expand=True)

        # Título
        tk.Label(card, text="GENERACIÓN DE MAPA DE ACTIVIDAD INTERACTIVO", 
                 font=FONT_H1, bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w", pady=(0, 15))

        # ── Sección 1: Selección de Archivos ──
        tk.Label(card, text="1. Selección de archivos del proyecto", font=FONT_BOLD, 
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w", pady=(10, 5))

        # Selector RPS
        frame_rps = tk.Frame(card, bg=COLORS["surface"])
        frame_rps.pack(fill="x", pady=4)
        btn_rps = tk.Button(frame_rps, text="Seleccionar RPS", font=FONT_SM, bg=COLORS["accent"], fg="white",
                            activebackground=COLORS["accent_hover"], relief="flat", width=18, command=self.seleccionar_rps)
        btn_rps.pack(side="left")
        self.lbl_rps = tk.Label(frame_rps, text="No seleccionado", font=FONT_SM, bg=COLORS["surface"], fg=COLORS["muted"])
        self.lbl_rps.pack(side="left", padx=15)

        # Selector SPS
        frame_sps = tk.Frame(card, bg=COLORS["surface"])
        frame_sps.pack(fill="x", pady=4)
        btn_sps = tk.Button(frame_sps, text="Seleccionar SPS (opcional)", font=FONT_SM, bg=COLORS["bg"], fg=COLORS["text"],
                            activebackground=COLORS["border"], relief="flat", width=18, command=self.seleccionar_sps)
        btn_sps.pack(side="left")
        self.lbl_sps = tk.Label(frame_sps, text="No seleccionado", font=FONT_SM, bg=COLORS["surface"], fg=COLORS["muted"])
        self.lbl_sps.pack(side="left", padx=15)

        # Selector XPS
        frame_xps = tk.Frame(card, bg=COLORS["surface"])
        frame_xps.pack(fill="x", pady=4)
        btn_xps = tk.Button(frame_xps, text="Seleccionar XPS (opcional)", font=FONT_SM, bg=COLORS["bg"], fg=COLORS["text"],
                            activebackground=COLORS["border"], relief="flat", width=18, command=self.seleccionar_xps)
        btn_xps.pack(side="left")
        self.lbl_xps = tk.Label(frame_xps, text="No seleccionado", font=FONT_SM, bg=COLORS["surface"], fg=COLORS["muted"])
        self.lbl_xps.pack(side="left", padx=15)

        tk.Frame(card, bg=COLORS["border"], height=1).pack(fill="x", pady=15)

        # ── Sección 2: Configuración del Proyecto ──
        tk.Label(card, text="2. Parámetros de geolocalización y muestreo", font=FONT_BOLD, 
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w", pady=(5, 5))

        config_frame = tk.Frame(card, bg=COLORS["surface"])
        config_frame.pack(fill="x", pady=5)

        tk.Label(config_frame, text="Zona UTM:", font=FONT, bg=COLORS["surface"]).grid(row=0, column=0, sticky="w", pady=5)
        self.combo_zona = ttk.Combobox(config_frame, values=["Zona 14N (Q14)", "Zona 15N (Q15)"],
                                       state="readonly", width=22)
        self.combo_zona.current(0)
        self.combo_zona.grid(row=0, column=1, sticky="w", padx=15, pady=5)

        tk.Label(config_frame, text="Muestreo (1 de cada N puntos):", font=FONT, bg=COLORS["surface"]).grid(row=1, column=0, sticky="w", pady=5)
        self.spin_muestreo = ttk.Spinbox(config_frame, from_=1, to=200, width=8)
        self.spin_muestreo.set(30)
        self.spin_muestreo.grid(row=1, column=1, sticky="w", padx=15, pady=5)

        tk.Frame(card, bg=COLORS["border"], height=1).pack(fill="x", pady=15)

        # ── Sección 3: Generación ──
        tk.Label(card, text="3. Procesar y visualizar mapa", font=FONT_BOLD, 
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w", pady=(5, 5))

        btn_f = tk.Frame(card, bg=COLORS["surface"])
        btn_f.pack(fill="x", pady=10)
        
        self.btn_generar = tk.Button(btn_f, text="GENERAR MAPA DE ACTIVIDAD INTERACTIVO", font=FONT_BOLD,
                                     bg=COLORS["accent"], fg="white", activebackground=COLORS["accent_hover"],
                                     relief="flat", cursor="hand2", padx=20, pady=10, command=self.procesar_mapa)
        self.btn_generar.pack(side="left")

        # Barra de progreso y estado
        self.progress_map = ttk.Progressbar(card, mode='determinate', length=300)
        self.progress_map.pack(anchor="w", pady=(15, 2))
        self.lbl_estado_map = tk.Label(card, text="Listo.", font=FONT_SM, bg=COLORS["surface"], fg=COLORS["muted"])
        self.lbl_estado_map.pack(anchor="w")

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 2: COMPARADOR INDIVIDUAL SPS / XPS
    # ──────────────────────────────────────────────────────────────────────────
    def _build_tab_individual(self):
        main_frame = ttk.Frame(self.tab_individual, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ── PARTE SUPERIOR: Selector de Archivos ──
        sel_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        sel_frame.pack(fill="x", pady=(0, 6))
        
        self._ind_f1 = FileSelector(sel_frame, "Archivo 1 (Base)")
        self._ind_f1.pack(side="left", expand=True, fill="both", padx=(0, 6))
        
        self._ind_f2 = FileSelector(sel_frame, "Archivo 2 (Nuevo)")
        self._ind_f2.pack(side="left", expand=True, fill="both")

        # ── BOTÓN ACCION ──
        btn_f = tk.Frame(main_frame, bg=COLORS["bg"])
        btn_f.pack(fill="x", pady=6)
        self.btn_individual_comparar = tk.Button(btn_f, text=" ⇄  Comparar Archivos ",
                                                  font=FONT_BOLD, cursor="hand2",
                                                  bg=COLORS["accent"], fg="#FFF",
                                                  relief="flat", bd=0, padx=20, pady=8,
                                                  activebackground=COLORS["accent_hover"],
                                                  command=self._on_individual_compare)
        self.btn_individual_comparar.pack(side="right")

        # ── METRICAS ──
        met_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        met_frame.pack(fill="x", pady=4)
        self._m_d1   = MetricCard(met_frame, "DISPAROS ARCHIVO 1")
        self._m_d2   = MetricCard(met_frame, "DISPAROS ARCHIVO 2")
        self._m_diff = MetricCard(met_frame, "DISPAROS CON DIFERENCIAS")
        self._m_miss = MetricCard(met_frame, "DISPAROS FALTANTES")
        for m in (self._m_d1, self._m_d2, self._m_diff, self._m_miss):
            m.pack(side="left", expand=True, fill="x", padx=(0, 6), pady=4)

        # Banner de aviso extra
        self._extra_lbl = tk.Label(main_frame, text="", font=FONT_SM,
                                   bg="#FFF3CD", fg=COLORS["diff_txt"],
                                   anchor="w", padx=12, pady=4)

        # Leyenda de estados
        leg_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        leg_frame.pack(fill="x", pady=(4, 0))
        for bg_key, fg_key, txt in [
            ("ok_row",    "ok_txt",    "■ Idéntico"),
            ("diff_row",  "diff_txt",  "■ Con diferencias de línea/estaca"),
            ("only1_row", "only1_txt", "■ Solo en Archivo 1"),
            ("only2_row", "only2_txt", "■ Solo en Archivo 2"),
        ]:
            f = tk.Frame(leg_frame, bg=COLORS[bg_key],
                         highlightthickness=1,
                         highlightbackground=COLORS["border"])
            f.pack(side="left", padx=(0, 6), pady=2)
            tk.Label(f, text=txt, font=FONT_SM,
                     fg=COLORS[fg_key], bg=COLORS[bg_key],
                     padx=10, pady=3).pack()

        # Cabecera de columnas para el listado
        self._col_hdr = tk.Frame(main_frame, bg=COLORS["col_hdr"],
                                 highlightthickness=1,
                                 highlightbackground=COLORS["border"])
        self._col_hdr.pack(fill="x", pady=(8, 0))

        # ── FILTROS Y EXPORTAR ──
        filt_frame = tk.Frame(main_frame, bg=COLORS["bg"])
        filt_frame.pack(fill="x", pady=(6, 4))

        # Botones exportar (Derecha)
        for txt, cmd, bg_c, fg_c in [
            ("Exportar Excel (.xlsx)", self._export_xlsx,       COLORS["ok_row"],   COLORS["ok_txt"]),
            ("Exportar TXT Completo",  self._export_comparativa, COLORS["col_hdr"],  COLORS["text"]),
            ("Exportar TXT Difs.",     self._export_txt,         COLORS["diff_row"], COLORS["diff_txt"]),
        ]:
            tk.Button(filt_frame, text=txt, font=FONT_SM, cursor="hand2",
                      relief="flat", bd=1, padx=12, pady=5,
                      bg=bg_c, fg=fg_c,
                      activebackground=COLORS["border"],
                      command=cmd).pack(side="right", padx=(4, 0))

        # Separador visual
        tk.Frame(filt_frame, bg=COLORS["border"], width=1).pack(side="right", fill="y", padx=8)

        # Entrada de búsqueda
        self._svar = tk.StringVar()
        self._svar.trace_add("write", lambda *_: self._apply_filter())
        
        search_entry = tk.Entry(filt_frame, textvariable=self._svar, font=FONT_SM, width=18,
                                relief="flat", bd=1, highlightthickness=1, highlightbackground=COLORS["border"])
        search_entry.pack(side="right")
        
        tk.Label(filt_frame, text="Buscar disparo:", font=FONT_SM,
                 bg=COLORS["bg"], fg=COLORS["muted"]).pack(side="right", padx=(4, 4))

        # Radio botones de filtro (Izquierda)
        tk.Label(filt_frame, text="Filtrar por:", font=FONT_SM,
                 bg=COLORS["bg"], fg=COLORS["muted"]).pack(side="left")
        self._fvar = tk.StringVar(value="all")
        for lbl, val in [("Todos","all"), ("Con diferencias","diff"),
                          ("Idénticos","ok"), ("Faltantes","missing")]:
            tk.Radiobutton(filt_frame, text=lbl, value=val, variable=self._fvar,
                           font=FONT_SM, bg=COLORS["bg"], fg=COLORS["text"],
                           activebackground=COLORS["bg"],
                           command=self._apply_filter).pack(side="left", padx=6)

        # ── LISTA CON SCROLLBAR ──
        list_outer = tk.Frame(main_frame, bg=COLORS["bg"])
        list_outer.pack(fill="both", expand=True, pady=(2, 0))

        self._canvas = tk.Canvas(list_outer, bg=COLORS["bg"], highlightthickness=0)
        vsb = ttk.Scrollbar(list_outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=COLORS["bg"])
        self._win = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(self._win, width=e.width))
        self._canvas.bind_all("<MouseWheel>", lambda e: self._canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Mensaje de bienvenida inicial en el listado
        self.lbl_welcome_ind = tk.Label(self._inner, text="Carga dos archivos XPS o SPS y pulsa «Comparar archivos» para analizar la estructura.",
                                         font=FONT, bg=COLORS["bg"], fg=COLORS["muted"])
        self.lbl_welcome_ind.pack(pady=40)

        # Barra de estado inferior de la pestaña
        bot_bar = tk.Frame(main_frame, bg=COLORS["surface"], highlightthickness=1, highlightbackground=COLORS["border"])
        bot_bar.pack(fill="x", side="bottom", pady=(5, 0))
        self._status_lbl = tk.Label(bot_bar, text="Listo para comparar.", font=FONT_SM,
                                    bg=COLORS["surface"], fg=COLORS["muted"], anchor="w")
        self._status_lbl.pack(side="left", padx=12, pady=5)

    # ──────────────────────────────────────────────────────────────────────────
    # TAB 3: COMPARADOR DE PAQUETES DIARIOS (QC)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_tab_paquetes(self):
        main_frame = ttk.Frame(self.tab_paquetes, padding="25")
        main_frame.pack(fill=tk.BOTH, expand=True)

        card = ttk.Frame(main_frame, style="Card.TFrame", padding="20")
        card.pack(fill=tk.BOTH, expand=True)

        tk.Label(card, text="CONTROL DE CALIDAD (QC) - COMPARATIVA DIARIA DE PAQUETES", 
                 font=FONT_H1, bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w", pady=(0, 15))

        # Explicación
        desc = ("Esta herramienta realiza un análisis secuencial y cronológico de carpetas de producción.\n"
                "Selecciona múltiples directorios (cada carpeta representa un día de trabajo).\n"
                "La aplicación ordenará las carpetas por nombre y comparará de forma consecutiva la estructura sísmica "
                "de los disparos (XPS), así como cambios de coordenadas en receptores (RPS) y fuentes (SPS).\n"
                "Genera un reporte Excel unificado con la información de control y diferencias.")
        tk.Label(card, text=desc, justify="left", font=FONT_SM, bg=COLORS["surface"], fg=COLORS["muted"]).pack(anchor="w", pady=(0, 15))

        # Frame de selección y lista
        list_frame = tk.Frame(card, bg=COLORS["surface"])
        list_frame.pack(fill="both", expand=True, pady=10)

        btn_box = tk.Frame(list_frame, bg=COLORS["surface"])
        btn_box.pack(side="left", fill="y", padx=(0, 15))

        # Botón Agregar
        btn_add = tk.Button(btn_box, text="Agregar carpeta diaria", font=FONT_SM, bg=COLORS["accent"], fg="white",
                            activebackground=COLORS["accent_hover"], relief="flat", width=22, pady=4, command=self.agregar_carpeta_qc)
        btn_add.pack(pady=4)

        # Botón Eliminar Seleccionada
        btn_del = tk.Button(btn_box, text="Eliminar seleccionada", font=FONT_SM, bg=COLORS["bg"], fg=COLORS["text"],
                            activebackground=COLORS["border"], relief="flat", width=22, pady=4, command=self.eliminar_carpeta_qc)
        btn_del.pack(pady=4)

        # Botón Limpiar Todo
        btn_clr = tk.Button(btn_box, text="Limpiar lista completa", font=FONT_SM, bg=COLORS["bg"], fg=COLORS["text"],
                            activebackground=COLORS["border"], relief="flat", width=22, pady=4, command=self.limpiar_carpetas_qc)
        btn_clr.pack(pady=4)

        # Lista visual de carpetas
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self.lst_carpetas = tk.Listbox(list_frame, font=FONT_MONO, relief="flat", bd=1, selectbackground=COLORS["accent"],
                                       highlightthickness=1, highlightcolor=COLORS["border"], yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.lst_carpetas.yview)
        scrollbar.pack(side="right", fill="y")
        self.lst_carpetas.pack(side="left", fill="both", expand=True)

        tk.Frame(card, bg=COLORS["border"], height=1).pack(fill="x", pady=15)

        # Botón Comparar Paquetes (QC)
        btn_qc_f = tk.Frame(card, bg=COLORS["surface"])
        btn_qc_f.pack(fill="x", pady=5)
        
        self.btn_qc_ejecutar = tk.Button(btn_qc_f, text="EJECUTAR COMPARACIÓN DE PAQUETES (QC)", font=FONT_BOLD,
                                          bg=COLORS["accent"], fg="white", activebackground=COLORS["accent_hover"],
                                          relief="flat", cursor="hand2", padx=20, pady=10, command=self.procesar_qc_carpetas)
        self.btn_qc_ejecutar.pack(side="left")

        # Barra de progreso y estado
        self.progress_qc = ttk.Progressbar(card, mode='determinate', length=300)
        self.progress_qc.pack(anchor="w", pady=(15, 2))
        
        self.lbl_estado_qc = tk.Label(card, text="Listo.", font=FONT_SM, bg=COLORS["surface"], fg=COLORS["muted"])
        self.lbl_estado_qc.pack(anchor="w")

    # ──────────────────────────────────────────────────────────────────────────
    # MÉTODOS DE LA PESTAÑA 1: MAPA SÍSMICO
    # ──────────────────────────────────────────────────────────────────────────
    def seleccionar_rps(self):
        ruta = filedialog.askopenfilename(filetypes=[("RPS", "*.rps *.rcp *.txt"), ("Todos", "*.*")])
        if ruta:
            self.ruta_rps = ruta
            self.lbl_rps.config(text=os.path.basename(ruta), fg=COLORS["accent"])

    def seleccionar_sps(self):
        ruta = filedialog.askopenfilename(filetypes=[("SPS", "*.sps *.txt"), ("Todos", "*.*")])
        if ruta:
            self.ruta_sps = ruta
            self.lbl_sps.config(text=os.path.basename(ruta), fg=COLORS["accent"])

    def seleccionar_xps(self):
        ruta = filedialog.askopenfilename(filetypes=[("XPS", "*.xps"), ("Todos", "*.*")])
        if ruta:
            self.ruta_xps = ruta
            self.lbl_xps.config(text=os.path.basename(ruta), fg=COLORS["accent"])

    def procesar_mapa(self):
        if not self.ruta_rps and not self.ruta_sps:
            messagebox.showwarning("Error", "Selecciona al menos RPS o SPS.")
            return

        self.btn_generar.config(state="disabled")
        self.btn_qc_ejecutar.config(state="disabled")
        self.btn_individual_comparar.config(state="disabled")
        self.progress_map['value'] = 0
        self.lbl_estado_map.config(text="Procesando datos...")

        epsg = 32614 if self.combo_zona.get() == "Zona 14N (Q14)" else 32615
        muestreo = int(self.spin_muestreo.get())

        progreso = Progreso(self.root, self.progress_map, self.lbl_estado_map)

        def tarea():
            try:
                generar_mapa_completo(
                    self.ruta_rps, self.ruta_sps, self.ruta_xps,
                    epsg, muestreo, progreso
                )
                self.root.after(0, self._ok_mapa)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, functools.partial(self._error_mapa, str(e)))

        threading.Thread(target=tarea, daemon=True).start()

    def _ok_mapa(self):
        self.btn_generar.config(state="normal")
        self.btn_qc_ejecutar.config(state="normal")
        self.btn_individual_comparar.config(state="normal")
        self.progress_map['value'] = 100
        self.lbl_estado_map.config(text="Mapa sísmico generado con éxito.", fg=COLORS["ok_txt"])
        webbrowser.open('file://' + os.path.realpath("mapa_sismico.html"))
        messagebox.showinfo("Éxito", "Mapa de actividad generado con interactividad.")

    def _error_mapa(self, msg):
        self.btn_generar.config(state="normal")
        self.btn_qc_ejecutar.config(state="normal")
        self.btn_individual_comparar.config(state="normal")
        self.progress_map['value'] = 0
        self.lbl_estado_map.config(text="Error en generación del mapa.", fg=COLORS["red_accent"])
        messagebox.showerror("Error", msg)

    # ──────────────────────────────────────────────────────────────────────────
    # MÉTODOS DE LA PESTAÑA 2: COMPARADOR INDIVIDUAL
    # ──────────────────────────────────────────────────────────────────────────
    def _on_individual_compare(self):
        p1, p2 = self._ind_f1.get(), self._ind_f2.get()
        if not p1 or not p2:
            messagebox.showwarning("Faltan archivos",
                                   "Selecciona los dos archivos antes de comparar.")
            return
        self._status_lbl.configure(text="Comparando archivos...")
        self.root.update()
        try:
            self._result = run_comparison(p1, p2)
            self._render_individual_results()
        except Exception as ex:
            messagebox.showerror("Error", str(ex))
            self._status_lbl.configure(text="Error en la comparación.")

    def _render_individual_results(self):
        r = self._result
        n1, n2 = r["n_disparos1"], r["n_disparos2"]
        ndiff  = len(r["disparos_diff"])
        nmiss  = len(r["disparos_solo1"]) + len(r["disparos_solo2"])

        self._m_d1.set(n1)
        self._m_d2.set(n2, COLORS["diff_txt"] if n1 != n2 else COLORS["text"])
        self._m_diff.set(ndiff, COLORS["diff_txt"] if ndiff else COLORS["ok_txt"])
        self._m_miss.set(nmiss, COLORS["only1_txt"] if nmiss else COLORS["ok_txt"])

        if n1 != n2:
            diff  = abs(n1 - n2)
            which = "Archivo 1" if n1 > n2 else "Archivo 2"
            self._extra_lbl.configure(
                text=f"  ⚠  El {which} tiene {diff} disparo(s) adicional(es) sin correspondencia.")
            self._extra_lbl.pack(fill="x", pady=(0, 4))
        else:
            self._extra_lbl.pack_forget()

        # Dibujar cabeceras de tabla
        for w in self._col_hdr.winfo_children():
            w.destroy()

        d_cell = tk.Frame(self._col_hdr, bg=COLORS["col_hdr"], width=COL_DISP)
        d_cell.pack(side="left", fill="y")
        d_cell.pack_propagate(False)
        tk.Label(d_cell, text="DISPARO", font=FONT_BOLD,
                 bg=COLORS["col_hdr"], fg=COLORS["col_hdr_txt"],
                 anchor="center").pack(expand=True, fill="both", pady=5)

        tk.Frame(self._col_hdr, bg=COLORS["border"], width=1).pack(side="left", fill="y")

        for txt in (f"ARCHIVO 1: {r['name1']}", f"ARCHIVO 2: {r['name2']}"):
            cell = tk.Frame(self._col_hdr, bg=COLORS["col_hdr"])
            cell.pack(side="left", fill="both", expand=True)
            tk.Label(cell, text=txt, font=FONT_BOLD,
                     bg=COLORS["col_hdr"], fg=COLORS["col_hdr_txt"],
                     anchor="center").pack(fill="both", pady=5)
            tk.Frame(self._col_hdr, bg=COLORS["border"], width=1).pack(side="left", fill="y")

        # Limpiar listado de filas
        for w in self._inner.winfo_children():
            w.destroy()
        self._disp_frames = []

        for shot in r["results"]:
            row = DisparoRow(self._inner, shot)
            row.pack(fill="x", pady=(0, 2))
            self._disp_frames.append((row, shot))

        self._apply_filter()

        total = len(r["results"])
        ok    = len(r["disparos_ok"])
        self._status_lbl.configure(
            text=(f"✔  {total} disparos  ·  {ok} idénticos  ·  "
                  f"{ndiff} con diferencias  ·  {nmiss} faltantes"))

    def _apply_filter(self):
        if not self._disp_frames:
            return
        filt   = self._fvar.get()
        search = self._svar.get().strip().lower()
        for row, s in self._disp_frames:
            show = True
            if filt == "diff"    and s["status"] != "diff":              show = False
            if filt == "ok"      and s["status"] != "ok":                show = False
            if filt == "missing" and s["status"] not in ("only1","only2"): show = False
            if show and search and search not in s["disparo"].lower():    show = False
            if show: row.pack(fill="x", pady=(0, 2))
            else:    row.pack_forget()

    def _export_txt(self):
        if not self._result:
            messagebox.showwarning("Sin datos", "Ejecuta una comparación primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile="reporte_diferencias.txt")
        if path:
            export_txt(self._result, path)
            self._status_lbl.configure(text=f"Reporte de diferencias guardado: {os.path.basename(path)}")

    def _export_xlsx(self):
        if not self._result:
            messagebox.showwarning("Sin datos", "Ejecuta una comparación primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="comparativa.xlsx")
        if path:
            try:
                export_xlsx(self._result, path)
                self._status_lbl.configure(
                    text=f"Reporte Excel guardado: {os.path.basename(path)}")
                messagebox.showinfo("Exportación Exitosa", f"El archivo Excel ha sido generado con éxito:\n{path}")
            except ImportError as e:
                messagebox.showerror("Módulo faltante", str(e))

    def _export_comparativa(self):
        if not self._result:
            messagebox.showwarning("Sin datos", "Ejecuta una comparación primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile="comparativa_completa.txt")
        if path:
            export_comparativa(self._result, path)
            self._status_lbl.configure(text=f"Comparativa completa guardada: {os.path.basename(path)}")

    # ──────────────────────────────────────────────────────────────────────────
    # MÉTODOS DE LA PESTAÑA 3: COMPARADOR DE PAQUETES (QC)
    # ──────────────────────────────────────────────────────────────────────────
    def agregar_carpeta_qc(self):
        carpeta = filedialog.askdirectory(title="Selecciona la carpeta de producción del día")
        if carpeta:
            # Evitar duplicados
            existentes = self.lst_carpetas.get(0, tk.END)
            if carpeta not in existentes:
                self.lst_carpetas.insert(tk.END, carpeta)

    def eliminar_carpeta_qc(self):
        selected_idx = self.lst_carpetas.curselection()
        if selected_idx:
            self.lst_carpetas.delete(selected_idx)

    def limpiar_carpetas_qc(self):
        self.lst_carpetas.delete(0, tk.END)

    def procesar_qc_carpetas(self):
        carpetas = list(self.lst_carpetas.get(0, tk.END))
        if len(carpetas) < 2:
            messagebox.showwarning("Advertencia", "Selecciona al menos 2 carpetas de paquetes diarios para comparar.")
            return

        self.btn_generar.config(state="disabled")
        self.btn_qc_ejecutar.config(state="disabled")
        self.btn_individual_comparar.config(state="disabled")
        self.progress_qc['value'] = 0
        self.lbl_estado_qc.config(text="Comparando carpetas diarias...")

        progreso = Progreso(self.root, self.progress_qc, self.lbl_estado_qc)

        def tarea():
            try:
                resultados = comparar_carpetas(carpetas, progreso)
                self.root.after(0, self._finalizar_qc, resultados)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, functools.partial(self._error_qc, str(e)))

        threading.Thread(target=tarea, daemon=True).start()

    def _finalizar_qc(self, resultados):
        self.btn_generar.config(state="normal")
        self.btn_qc_ejecutar.config(state="normal")
        self.btn_individual_comparar.config(state="normal")
        self.progress_qc['value'] = 100
        
        # Verificar diferencias en cualquiera de las salidas
        difs_encontradas = False
        if resultados:
            difs = resultados.get('diferencias', {})
            xps_difs = resultados.get('xps_comparaciones', [])
            
            # Chequear diferencias en RPS o SPS
            if any(not df.empty for df in difs.values() if isinstance(df, pd.DataFrame)):
                difs_encontradas = True
            # Chequear diferencias en la lógica estructural de XPS
            for item in xps_difs:
                res = item.get('resultado', {})
                if len(res.get('disparos_diff', [])) > 0 or len(res.get('disparos_solo1', [])) > 0 or len(res.get('disparos_solo2', [])) > 0:
                    difs_encontradas = True
                    break
        
        if difs_encontradas:
            self.lbl_estado_qc.config(text="Comparativa QC completada con diferencias encontradas.", fg=COLORS["red_accent"])
            messagebox.showinfo("QC Completado", 
                              "Se generó 'comparacion_paquetes.xlsx' con las diferencias de coordenadas (RPS/SPS) y el comparador estructural de disparos (XPS).\n\n"
                              "Revísalo en la carpeta del programa.")
        else:
            self.lbl_estado_qc.config(text="QC completado. No se encontraron diferencias.", fg=COLORS["ok_txt"])
            messagebox.showinfo("QC Completado", 
                              "Todas las carpetas comparadas son idénticas en coordenadas y relaciones de disparo.")

    def _error_qc(self, msg):
        self.btn_generar.config(state="normal")
        self.btn_qc_ejecutar.config(state="normal")
        self.btn_individual_comparar.config(state="normal")
        self.progress_qc['value'] = 0
        self.lbl_estado_qc.config(text="Error en la comparación de paquetes.", fg=COLORS["red_accent"])
        messagebox.showerror("Error", msg)