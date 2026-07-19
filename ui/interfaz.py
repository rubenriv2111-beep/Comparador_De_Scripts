# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import webbrowser
import functools
import math
from PIL import Image, ImageDraw, ImageTk
import customtkinter as ctk
from datetime import datetime
import pandas as pd

from core.generador_mapa import generar_mapa_completo
from core.qc_comparator import comparar_carpetas
from utils.progreso import Progreso
from core.comparador_disparos import run_comparison, export_xlsx, export_txt, export_comparativa

# Configuración inicial del tema CustomTkinter
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# Colores ejecutivos e industriales inspirados en SINOPEC (SAP Fiori, ArcGIS style)
COLORS = {
    "bg_light":      "#F1F5F9",   # Slate 100
    "bg_dark":       "#0F172A",   # Slate 900
    "sidebar_light": "#0F2942",   # Azul SINOPEC
    "sidebar_dark":  "#0A192F",   # Azul SINOPEC oscuro
    "surface_light": "#FFFFFF",
    "surface_dark":  "#1E293B",   # Slate 800
    "border_light":  "#E2E8F0",   # Slate 200
    "border_dark":   "#334155",   # Slate 700
    "text_light":    "#0F172A",
    "text_dark":     "#F8FAFC",
    "muted_light":   "#64748B",   # Slate 500
    "muted_dark":    "#94A3B8",   # Slate 400
    "accent":        "#0F2942",   # Azul primario
    "accent_hover":  "#1E3A5F",   # Azul primario hover
    "red_accent":    "#E60012",   # Rojo SINOPEC
    
    # Estados de comparación - Pasteles ejecutivos sobrios
    "ok_row":        "#E2EFDA",   # Verde claro
    "ok_txt":        "#375623",
    "diff_row":      "#FFF2CC",   # Amarillo claro
    "diff_txt":      "#7F6000",
    "only1_row":     "#D9E1F2",   # Azul claro
    "only1_txt":     "#1F4E78",
    "only2_row":     "#F2F2F2",   # Gris claro
    "only2_txt":     "#595959",
    
    "col_hdr":       "#E2E8F0",
    "col_hdr_txt":   "#334155",
}

# Fuentes ejecutivas modernas
FONT      = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_SM   = ("Segoe UI", 9)
FONT_H1   = ("Segoe UI", 14, "bold")
FONT_H2   = ("Segoe UI", 12, "bold")
FONT_MONO = ("Consolas", 9)

# Ancho fijo para la columna de disparos en el listado
COL_DISP  = 130


# ─── Generador Dinámico de Iconos PIL ─────────────────────────────────────────
def crear_icono_diseno(tipo, color_hex="#FFFFFF"):
    """
    Dibuja iconos vectoriales minimalistas en un lienzo transparente usando PIL.
    Evita la necesidad de dependencias de internet o archivos externos.
    """
    h = color_hex.lstrip('#')
    color_rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    
    img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    if tipo == "dashboard":
        # Gráfico de barras
        draw.rectangle([3, 13, 7, 20], fill=color_rgb)
        draw.rectangle([9, 6, 13, 20], fill=color_rgb)
        draw.rectangle([15, 10, 19, 20], fill=color_rgb)
    elif tipo == "comparador":
        # Dos páginas superpuestas con flechas o líneas
        draw.rectangle([4, 4, 13, 15], outline=color_rgb, width=2)
        draw.rectangle([11, 9, 20, 20], outline=color_rgb, width=2)
    elif tipo == "mapas":
        # Globo con retícula o brújula
        draw.ellipse([3, 3, 20, 20], outline=color_rgb, width=2)
        draw.line([3, 11, 20, 11], fill=color_rgb, width=2)
        draw.line([11, 3, 11, 20], fill=color_rgb, width=2)
    elif tipo == "config":
        # Engrane
        draw.ellipse([6, 6, 17, 17], outline=color_rgb, width=2)
        center = (11.5, 11.5)
        for i in range(8):
            angle = i * (math.pi / 4)
            x1 = center[0] + 5 * math.cos(angle)
            y1 = center[1] + 5 * math.sin(angle)
            x2 = center[0] + 9 * math.cos(angle)
            y2 = center[1] + 9 * math.sin(angle)
            draw.line([x1, y1, x2, y2], fill=color_rgb, width=2)
    elif tipo == "folder":
        # Carpeta abierta
        draw.polygon([(3,6), (8,6), (10,8), (20,8), (20,19), (3,19)], outline=color_rgb, fill=None)
    elif tipo == "file":
        # Archivo con esquina doblada
        draw.polygon([(4,3), (15,3), (20,8), (20,20), (4,20)], outline=color_rgb, fill=None)
    else:
        # Por defecto un cuadro
        draw.rectangle([4, 4, 19, 19], outline=color_rgb, width=2)
        
    return ctk.CTkImage(light_image=img, dark_image=img, size=(18, 18))


# ─── Selector de Archivos Moderno ─────────────────────────────────────────────
class CTkFileSelector(ctk.CTkFrame):
    def __init__(self, parent, label, callback_change=None, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._path = ""
        self._label = label
        self._callback = callback_change
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        
        self.lbl_title = ctk.CTkLabel(self, text=self._label, font=FONT_BOLD, anchor="w")
        self.lbl_title.grid(row=0, column=0, sticky="w", pady=(0, 2))
        
        self.entry_path = ctk.CTkEntry(self, placeholder_text="No se ha seleccionado ningún archivo...", 
                                      font=FONT_SM, height=32)
        self.entry_path.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        
        icon_file = crear_icono_diseno("file", "#0F2942")
        self.btn_select = ctk.CTkButton(self, text="Examinar", font=FONT_BOLD, width=95, height=32, 
                                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                        image=icon_file, command=self._pick)
        self.btn_select.grid(row=1, column=1, sticky="e")

    def _pick(self):
        p = filedialog.askopenfilename(
            filetypes=[("Archivos sísmicos (SPS/XPS/RPS)", "*.sps *.xps *.rps *.rcp *.txt"), ("Todos", "*.*")])
        if not p:
            return
        self.set_path(p)
        if self._callback:
            self._callback(p)

    def set_path(self, path):
        self._path = path
        self.entry_path.delete(0, tk.END)
        self.entry_path.insert(0, path)

    def get(self):
        return self._path

    def clear(self):
        self._path = ""
        self.entry_path.delete(0, tk.END)


# ─── Lista de Carpetas Moderna (Estilo Listbox Avanzado) ─────────────────────
class CTkFolderList(ctk.CTkScrollableFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color="transparent", corner_radius=6, border_width=1, **kw)
        self.folders = []
        self._update_colors()
        self.render()

    def _update_colors(self):
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            self.configure(border_color=COLORS["border_dark"])
        else:
            self.configure(border_color=COLORS["border_light"])

    def add_folder(self, path):
        if path and path not in self.folders:
            self.folders.append(path)
            self.render()

    def remove_folder(self, path):
        if path in self.folders:
            self.folders.remove(path)
            self.render()

    def clear(self):
        self.folders = []
        self.render()

    def render(self):
        # Limpiar hijos
        for w in self.winfo_children():
            w.destroy()
            
        if not self.folders:
            lbl_empty = ctk.CTkLabel(self, text="No hay carpetas agregadas a la cola de comparación.", 
                                     font=FONT_SM, text_color=COLORS["muted_light"])
            lbl_empty.pack(pady=35, expand=True)
            return

        for idx, path in enumerate(self.folders):
            row_bg = COLORS["bg_light"] if ctk.get_appearance_mode() == "Light" else COLORS["surface_dark"]
            row = ctk.CTkFrame(self, fg_color=row_bg, corner_radius=6, height=36)
            row.pack(fill="x", pady=2, padx=2)
            row.pack_propagate(False)
            
            lbl_num = ctk.CTkLabel(row, text=f"  {idx+1}.  ", font=FONT_BOLD, text_color=COLORS["accent"])
            lbl_num.pack(side="left")
            
            lbl_path = ctk.CTkLabel(row, text=path, font=FONT_MONO, anchor="w")
            lbl_path.pack(side="left", fill="x", expand=True, padx=4)
            
            btn_del = ctk.CTkButton(
                row, text="✕", width=22, height=22, corner_radius=4,
                fg_color="transparent", hover_color="#EF4444" if ctk.get_appearance_mode()=="Light" else "#7F1D1D", 
                text_color="#EF4444",
                font=("Segoe UI", 11, "bold"),
                command=functools.partial(self.remove_folder, path)
            )
            btn_del.pack(side="right", padx=6)


# ─── Tarjeta de Métricas Dashboard (KPI Card) ─────────────────────────────────
class CTkKPICard(ctk.CTkFrame):
    def __init__(self, parent, label, value="—", color=None, **kw):
        super().__init__(parent, corner_radius=8, border_width=1, **kw)
        self.label = label
        self.value = value
        self.color = color
        self._build()
        self.update_theme()

    def _build(self):
        self.lbl_title = ctk.CTkLabel(self, text=self.label.upper(), font=("Segoe UI", 9, "bold"))
        self.lbl_title.pack(anchor="w", padx=12, pady=(12, 2))
        
        self.lbl_val = ctk.CTkLabel(self, text=self.value, font=("Segoe UI", 20, "bold"))
        self.lbl_val.pack(anchor="w", padx=12, pady=(0, 12))

    def update_theme(self):
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            self.configure(fg_color=COLORS["surface_dark"], border_color=COLORS["border_dark"])
            self.lbl_title.configure(text_color=COLORS["muted_dark"])
            self.lbl_val.configure(text_color=self.color or COLORS["text_dark"])
        else:
            self.configure(fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
            self.lbl_title.configure(text_color=COLORS["muted_light"])
            self.lbl_val.configure(text_color=self.color or COLORS["text_light"])

    def set(self, val, color=None):
        self.lbl_val.configure(text=str(val))
        if color:
            self.lbl_val.configure(text_color=color)


# ─── Fila de Disparo Expandible para Listado ──────────────────────────────────
class CTkDisparoRow(ctk.CTkFrame):
    def __init__(self, parent, r: dict, **kw):
        super().__init__(parent, corner_radius=6, **kw)
        self._r = r
        self._open = False
        self._detail = None
        self._build_header()

    def _meta(self):
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

        # Contenedor cabecera
        self._hdr = tk.Frame(self, bg=bg, cursor="hand2")
        self._hdr.pack(fill="x")
        self._hdr.bind("<Button-1>", self._toggle)

        # 1. DISPARO
        disp_cell = tk.Frame(self._hdr, bg=bg, width=COL_DISP)
        disp_cell.pack(side="left", fill="y")
        disp_cell.pack_propagate(False)
        lbl_disp = tk.Label(disp_cell, text=f"Disparo\n{r['disparo']}", font=FONT_BOLD, bg=bg, fg=fg, justify="center")
        lbl_disp.pack(expand=True)
        disp_cell.bind("<Button-1>", self._toggle)
        lbl_disp.bind("<Button-1>", self._toggle)

        # Separador
        tk.Frame(self._hdr, bg=COLORS["border_light"], width=1).pack(side="left", fill="y")

        # 2. ARCHIVO 1 (Base)
        a1_cell = tk.Frame(self._hdr, bg=bg)
        a1_cell.pack(side="left", fill="both", expand=True)
        self._a1_lbl = tk.Label(a1_cell, font=FONT_SM, bg=bg, fg=fg, anchor="center")
        self._a1_lbl.pack(expand=True, fill="both", padx=6, pady=6)
        a1_cell.bind("<Button-1>", self._toggle)
        self._a1_lbl.bind("<Button-1>", self._toggle)

        # Separador
        tk.Frame(self._hdr, bg=COLORS["border_light"], width=1).pack(side="left", fill="y")

        # 3. ARCHIVO 2 (Nuevo)
        a2_cell = tk.Frame(self._hdr, bg=bg)
        a2_cell.pack(side="left", fill="both", expand=True)
        self._a2_lbl = tk.Label(a2_cell, font=FONT_SM, bg=bg, fg=fg, anchor="center")
        self._a2_lbl.pack(expand=True, fill="both", padx=6, pady=6)
        a2_cell.bind("<Button-1>", self._toggle)
        self._a2_lbl.bind("<Button-1>", self._toggle)

        # Flecha indicadora si tiene discrepancias
        if r["status"] == "diff":
            self._arrow = tk.Label(self._hdr, text=" ▾ ", font=FONT_SM, bg=bg, fg=fg)
            self._arrow.pack(side="right", padx=12)
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
        else: # diff
            ndiff = sum(1 for lr in r["lineas"] if lr["status"] != "ok")
            nok   = sum(1 for lr in r["lineas"] if lr["status"] == "ok")
            self._a1_lbl.configure(text=f"{r.get('n_lineas1','—')} líneas\n{nok} ok · {ndiff} difs.")
            self._a2_lbl.configure(text=f"{r.get('n_lineas2','—')} líneas\n{nok} ok · {ndiff} difs.")

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
        self._detail = tk.Frame(self, bg=COLORS["surface_light"], highlightthickness=1, highlightbackground=COLORS["border_light"])
        self._detail.pack(fill="x", padx=1, pady=(0, 2))

        # Cabecera de tabla interna
        hdr = tk.Frame(self._detail, bg=COLORS["col_hdr"])
        hdr.pack(fill="x")
        for txt, w, side in [("Línea", 100, "left"), ("Estacas Archivo 1", 0, "left"), ("Estacas Archivo 2", 0, "left")]:
            kw = {"width": w} if w else {}
            tk.Label(hdr, text=txt, font=FONT_BOLD, bg=COLORS["col_hdr"], fg=COLORS["col_hdr_txt"],
                     anchor="center", padx=6, pady=4, **kw).pack(side=side, fill="both", expand=(w == 0))

        # Detalle de líneas
        for i, lr in enumerate(self._r["lineas"]):
            s = lr["status"]
            row_bg = COLORS.get(STATUS_META_ROW.get(s, "surface_light"), "#FFFFFF")
            row_fg = COLORS.get(STATUS_META_TXT.get(s, "text_light"), "#1E293B")
            alt_bg = self._lighten(row_bg) if i % 2 == 0 else row_bg

            row = tk.Frame(self._detail, bg=alt_bg)
            row.pack(fill="x")

            # Columna Línea
            lin_cell = tk.Frame(row, bg=alt_bg, width=100)
            lin_cell.pack(side="left", fill="y")
            lin_cell.pack_propagate(False)
            tk.Label(lin_cell, text=lr["linea"], font=FONT_MONO, bg=alt_bg, fg=row_fg, anchor="center").pack(expand=True, fill="both")

            tk.Frame(row, bg=COLORS["border_light"], width=1).pack(side="left", fill="y")

            def fmt_cell(linea_r, arch):
                if arch == 1:
                    if linea_r["status"] == "only2": return "—"
                    lst = linea_r["estacas1"]
                else:
                    if linea_r["status"] == "only1": return "—"
                    lst = linea_r["estacas2"]
                if not lst: return "—"
                def _n(x): return float(x) if x.lstrip("-").replace(".","").isdigit() else 0
                ini = min((e[0] for e in lst), key=_n)
                fin = max((e[1] for e in lst), key=_n)
                return f"{ini} → {fin}" if len(lst) == 1 else f"{ini} → {fin}  ({len(lst)} rangos)"

            for arch in (1, 2):
                cell_txt = fmt_cell(lr, arch)
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
                tk.Label(a_cell, text=cell_txt + extra, font=FONT_MONO, bg=alt_bg, fg=row_fg,
                         anchor="center", justify="center", padx=6, pady=3).pack(fill="both", expand=True)
                
                if arch == 1:
                    tk.Frame(row, bg=COLORS["border_light"], width=1).pack(side="left", fill="y")

            tk.Frame(self._detail, bg=COLORS["border_light"], height=1).pack(fill="x")

    @staticmethod
    def _lighten(hex_color):
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            r = min(255, r + (255 - r) // 3)
            g = min(255, g + (255 - g) // 3)
            b = min(255, b + (255 - b) // 3)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color


STATUS_META_ROW = {"ok": "ok_row", "diff": "diff_row", "only1": "only1_row", "only2": "only2_row"}
STATUS_META_TXT = {"ok": "ok_txt", "diff": "diff_txt", "only1": "only1_txt", "only2": "only2_txt"}


# ─── Aplicación Principal (Dashboard) ─────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.root = self
        
        # Dimensiones y títulos ejecutivos
        self.title("SINOPEC - Monitor Sísmico de Adquisición y Comparación Estructural")
        self.geometry("1200x820")
        self.minsize(1050, 720)
        
        # Variables de control
        self.current_screen = "dashboard"
        
        # Rutas de Archivos para Tab 1 (Mapas)
        self.map_rps = ""
        self.map_sps = ""
        self.map_xps = ""
        
        # Datos del comparador individual
        self._result = None
        self._disp_frames = []
        
        # Imagen del logotipo
        self.logo_image = None
        
        self._build_dashboard_layout()
        self.set_screen("dashboard")

    def _build_dashboard_layout(self):
        # Configurar retícula principal
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # ── 1. BARRA LATERAL (SIDEBAR DE NAVEGACIÓN) ──
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color=COLORS["sidebar_light"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        # Panel del Logo superior
        logo_panel = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_panel.pack(fill="x", padx=10, pady=(20, 10))
        
        logo_path = r"C:\Users\Administrador\Desktop\Scripts_Adquisicion\resources\LOGO.PNG"
        if os.path.exists(logo_path):
            try:
                pil_img = Image.open(logo_path)
                h_target = 48
                w_target = int(pil_img.width * (h_target / pil_img.height))
                self.logo_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w_target, h_target))
                
                self.lbl_logo = ctk.CTkLabel(logo_panel, image=self.logo_image, text="")
                self.lbl_logo.pack(anchor="center")
            except Exception as e:
                print("Error loading logo:", e)
                
        if not self.logo_image:
            self.lbl_logo_fallback = ctk.CTkLabel(logo_panel, text="SINOPEC", font=("Segoe UI", 22, "bold"), text_color="white")
            self.lbl_logo_fallback.pack(anchor="center")
            
        # Títulos y metadatos de versión
        self.lbl_sys_title = ctk.CTkLabel(self.sidebar, text="SISTEMA SÍSMICO ADQUISICIÓN", font=("Segoe UI", 10, "bold"), text_color="#A5B4FC")
        self.lbl_sys_title.pack(anchor="center", pady=(5, 0))
        self.lbl_version = ctk.CTkLabel(self.sidebar, text="Versión 2.2.0 (Estable)", font=("Segoe UI", 8, "italic"), text_color="#64748B")
        self.lbl_version.pack(anchor="center", pady=(0, 20))
        
        # Separador decorativo superior
        line_top = ctk.CTkFrame(self.sidebar, height=2, fg_color=COLORS["red_accent"])
        line_top.pack(fill="x", padx=15, pady=(0, 15))
        
        # Botones de navegación con iconos PIL vectoriales dibujados en tiempo de ejecución
        self.nav_buttons = {}
        sections = [
            ("dashboard", "Dashboard Principal", "dashboard"),
            ("comparador", "Comparador Estructural", "comparador"),
            ("mapas", "Generador de Mapas", "mapas"),
            ("config", "Configuración y Temas", "config")
        ]
        
        for key, text, icon_type in sections:
            icon = crear_icono_diseno(icon_type, "#A5B4FC")
            btn = ctk.CTkButton(
                self.sidebar, text=f"  {text}", image=icon, font=FONT_BOLD,
                fg_color="transparent", text_color="#E2E8F0",
                hover_color="#1E3A8A", anchor="w", height=42, corner_radius=6,
                command=functools.partial(self.set_screen, key)
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn
            
        # Franja inferior en el sidebar para metadatos del desarrollador
        self.sidebar_footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_footer.pack(side="bottom", fill="x", pady=15, padx=15)
        
        lbl_dev_title = ctk.CTkLabel(self.sidebar_footer, text="INGENIERÍA Y CONTROL", font=("Segoe UI", 7, "bold"), text_color="#64748B")
        lbl_dev_title.pack(anchor="w")
        lbl_developer = ctk.CTkLabel(self.sidebar_footer, text="Adquisicion de Datos Sercel", font=("Segoe UI", 9, "bold"), text_color="#E2E8F0")
        lbl_developer.pack(anchor="w")

        # ── 2. ÁREA PRINCIPAL (MAIN VIEWPORT) ──
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color=COLORS["bg_light"])
        self.main_area.grid(row=0, column=1, sticky="nsew")
        
        # Instanciar las vistas de pantalla en frames ocultos
        self.frames = {
            "dashboard": ctk.CTkFrame(self.main_area, fg_color="transparent"),
            "comparador": ctk.CTkFrame(self.main_area, fg_color="transparent"),
            "mapas": ctk.CTkFrame(self.main_area, fg_color="transparent"),
            "config": ctk.CTkFrame(self.main_area, fg_color="transparent")
        }
        
        self._build_screen_dashboard()
        self._build_screen_comparador()
        self._build_screen_mapas()
        self._build_screen_config()

    def set_screen(self, screen_key):
        """Cambia el foco del dashboard al panel seleccionado."""
        self.current_screen = screen_key
        
        # Desactivar visualmente botones no activos y colorear el activo
        for k, btn in self.nav_buttons.items():
            if k == screen_key:
                btn.configure(fg_color="#1E3A8A", text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color="#E2E8F0")
                
        # Ocultar todos los paneles y empaquetar el actual
        for f in self.frames.values():
            f.pack_forget()
            
        self.frames[screen_key].pack(fill="both", expand=True, padx=25, pady=25)
        
        # Actualizaciones dinámicas
        if screen_key == "dashboard":
            self.recargar_dashboard_kpis()

    # ──────────────────────────────────────────────────────────────────────────
    # PANEL 1: DASHBOARD
    # ──────────────────────────────────────────────────────────────────────────
    def _build_screen_dashboard(self):
        f = self.frames["dashboard"]
        
        # Encabezado del dashboard
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        lbl_title = ctk.CTkLabel(header, text="DASHBOARD DE OPERACIONES SÍSMICAS", font=FONT_H1)
        lbl_title.pack(anchor="w")
        lbl_desc = ctk.CTkLabel(header, text="Control administrativo del proyecto y métricas clave de adquisición.", font=FONT_SM, text_color=COLORS["muted_light"])
        lbl_desc.pack(anchor="w")
        
        # Fila de tarjetas KPI principales
        self.kpi_container = ctk.CTkFrame(f, fg_color="transparent")
        self.kpi_container.pack(fill="x", pady=5)
        
        self.card_lmaps = CTkKPICard(self.kpi_container, "Último Mapa Generado", "Ninguno", color=COLORS["accent"])
        self.card_lmaps.pack(side="left", expand=True, fill="x", padx=(0, 10))
        
        self.card_lcomp = CTkKPICard(self.kpi_container, "Última Comparativa", "Ninguna", color=COLORS["accent"])
        self.card_lcomp.pack(side="left", expand=True, fill="x", padx=(0, 10))
        
        self.card_lfiles = CTkKPICard(self.kpi_container, "Archivos de Adquisición", "0", color=COLORS["accent"])
        self.card_lfiles.pack(side="left", expand=True, fill="x")
        
        # Tarjeta informativa central
        info_card = ctk.CTkFrame(f, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        info_card.pack(fill="both", expand=True, pady=15)
        
        lbl_info_title = ctk.CTkLabel(info_card, text="SINOPEC GEOPHYSICAL SYSTEM", font=FONT_H2, text_color=COLORS["accent"])
        lbl_info_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        guia_uso = (
            "Bienvenido al entorno unificado de control de calidad sísmico. Desde este panel principal "
            "podrá supervisar la correctitud de las relaciones geométricas del levantamiento.\n\n"
            "MÓDULOS DE NAVEGACIÓN DISPONIBLES:\n"
            "• COMPARADOR ESTRUCTURAL: Permite comparar archivos de disparos SPS, receptores RPS o relaciones XPS "
            "de forma manual e individual, o realizar análisis secuenciales en carpetas de producción diaria (QC).\n"
            "• GENERADOR DE MAPAS: Parsea las coordenadas geográficas de los geófonos y fuentes, proyecta la información "
            "a UTM y genera un plano interactivo HTML interactivo de visualización sísmica.\n"
            "• CONFIGURACIÓN Y TEMAS: Ajusta la interfaz visual del sistema (Modo Oscuro, Claro) y los parámetros globales."
        )
        lbl_guia = ctk.CTkLabel(info_card, text=guia_uso, font=FONT, justify="left", text_color=COLORS["text_light"])
        lbl_guia.pack(anchor="w", padx=20, pady=10)

    def recargar_dashboard_kpis(self):
        """Actualiza dinámicamente las métricas que se muestran en las tarjetas del panel principal."""
        # Último mapa
        if os.path.exists("mapa_sismico.html"):
            mod_time = datetime.fromtimestamp(os.path.getmtime("mapa_sismico.html")).strftime("%H:%M:%S")
            self.card_lmaps.set(f"Generado ({mod_time})", COLORS["ok_txt"])
        else:
            self.card_lmaps.set("No generado", COLORS["muted_light"])
            
        # Última comparativa
        if os.path.exists("comparacion_paquetes.xlsx"):
            mod_time = datetime.fromtimestamp(os.path.getmtime("comparacion_paquetes.xlsx")).strftime("%H:%M:%S")
            self.card_lcomp.set(f"Reporte Listo ({mod_time})", COLORS["ok_txt"])
        else:
            self.card_lcomp.set("No disponible", COLORS["muted_light"])
            
        # Archivos leídos
        self.card_lfiles.set("SPS, RPS, XPS", COLORS["accent"])

    # ──────────────────────────────────────────────────────────────────────────
    # PANEL 2: COMPARADOR UNIFICADO (INDIVIDUAL Y QC)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_screen_comparador(self):
        f = self.frames["comparador"]
        
        # Encabezado
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        
        lbl_title = ctk.CTkLabel(header, text="COMPARADOR ESTRUCTURAL SÍSMICO", font=FONT_H1)
        lbl_title.pack(anchor="w")
        lbl_desc = ctk.CTkLabel(header, text="Módulo de comparación unificado para archivos unitarios y análisis de carpetas diarias (QC).", font=FONT_SM, text_color=COLORS["muted_light"])
        lbl_desc.pack(anchor="w")
        
        # Tarjeta blanca para el selector del tipo de comparación
        selector_card = ctk.CTkFrame(f, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        selector_card.pack(fill="x", pady=5)
        
        lbl_sel_t = ctk.CTkLabel(selector_card, text="TIPO DE COMPARACIÓN", font=FONT_BOLD, text_color=COLORS["accent"])
        lbl_sel_t.pack(anchor="w", padx=15, pady=(12, 4))
        
        # Segmented button para seleccionar modo de forma moderna (SAP Fiori Style)
        self.comp_mode_var = ctk.StringVar(value="Individual XPS")
        self.segmented_selector = ctk.CTkSegmentedButton(
            selector_card,
            values=["Individual SPS", "Individual RPS", "Individual XPS", "Paquete diario (QC)"],
            font=FONT_BOLD, height=36,
            command=self._on_comp_mode_changed
        )
        self.segmented_selector.pack(fill="x", padx=15, pady=(0, 15))
        self.segmented_selector.set("Individual XPS")

        # ── CONTENEDOR MÓVIL: ENTRADA DE DATOS DINÁMICA ──
        self.inputs_container = ctk.CTkFrame(f, fg_color="transparent")
        self.inputs_container.pack(fill="x", pady=6)
        
        # Subpanel A: Entrada de Archivos Individuales
        self.frame_files_input = ctk.CTkFrame(self.inputs_container, fg_color="transparent")
        self.frame_files_input.pack(fill="x")
        
        self.files_grid = ctk.CTkFrame(self.frame_files_input, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        self.files_grid.pack(fill="x", pady=2)
        
        # File selector 1
        self.ind_f1 = CTkFileSelector(self.files_grid, "Archivo 1 (Línea Base)", callback_change=self._auto_detect_file_type)
        self.ind_f1.pack(fill="x", padx=20, pady=(15, 8))
        
        # File selector 2
        self.ind_f2 = CTkFileSelector(self.files_grid, "Archivo 2 (Línea Nueva)")
        self.ind_f2.pack(fill="x", padx=20, pady=(8, 15))

        # Subpanel B: Entrada de Directorios en Cola (QC) (Inicialmente oculto)
        self.frame_folders_input = ctk.CTkFrame(self.inputs_container, fg_color="transparent")
        
        self.folders_card = ctk.CTkFrame(self.frame_folders_input, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        self.folders_card.pack(fill="x", pady=2)
        
        lbl_folders_t = ctk.CTkLabel(self.folders_card, text="COLA DE RESTRICCIONES DIARIAS", font=FONT_BOLD, text_color=COLORS["accent"])
        lbl_folders_t.pack(anchor="w", padx=20, pady=(15, 4))
        
        # Contenedor de botones del listbox
        list_controls = ctk.CTkFrame(self.folders_card, fg_color="transparent")
        list_controls.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        btn_box = ctk.CTkFrame(list_controls, fg_color="transparent")
        btn_box.pack(side="left", fill="y", padx=(0, 15))
        
        icon_f = crear_icono_diseno("folder", "#FFFFFF")
        btn_add = ctk.CTkButton(btn_box, text=" Agregar Carpeta", image=icon_f, font=FONT_BOLD, 
                                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                width=180, height=34, command=self._on_qc_add_folder)
        btn_add.pack(pady=3)
        
        btn_clr = ctk.CTkButton(btn_box, text=" Limpiar Lista", font=FONT_BOLD,
                                fg_color=COLORS["bg_light"], text_color=COLORS["text_light"], hover_color=COLORS["border_light"],
                                width=180, height=34, command=self._on_qc_clear_folders)
        btn_clr.pack(pady=3)
        
        self.folders_list = CTkFolderList(list_controls, height=130)
        self.folders_list.pack(side="left", fill="both", expand=True)

        # ── BOTÓN GENERAL DE EJECUCIÓN ──
        self.action_container = ctk.CTkFrame(f, fg_color="transparent")
        self.action_container.pack(fill="x", pady=6)
        
        self.btn_execute_compare = ctk.CTkButton(
            self.action_container, text="EJECUTAR COMPARACIÓN DE DATOS", font=FONT_H2,
            fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
            height=46, corner_radius=8, command=self._on_execute_comparison
        )
        self.btn_execute_compare.pack(fill="x")

        # ── CONTENEDOR DE RESULTADOS Y METRICAS ──
        # Métrica individual KPI row
        self.metrics_bar = ctk.CTkFrame(f, fg_color="transparent")
        self.metrics_bar.pack(fill="x", pady=4)
        
        self.m_d1 = CTkKPICard(self.metrics_bar, "Disparos Archivo 1", "—")
        self.m_d1.pack(side="left", expand=True, fill="x", padx=(0, 8))
        
        self.m_d2 = CTkKPICard(self.metrics_bar, "Disparos Archivo 2", "—")
        self.m_d2.pack(side="left", expand=True, fill="x", padx=(0, 8))
        
        self.m_diff = CTkKPICard(self.metrics_bar, "Disparos con Diferencias", "—")
        self.m_diff.pack(side="left", expand=True, fill="x", padx=(0, 8))
        
        self.m_miss = CTkKPICard(self.metrics_bar, "Disparos Faltantes", "—")
        self.m_miss.pack(side="left", expand=True, fill="x")

        # Banner de diferencias de disparo (Cabecera extra)
        self.ind_extra_lbl = ctk.CTkLabel(f, text="", font=FONT_SM, fg_color="#FFF3CD", text_color=COLORS["diff_txt"], height=30, corner_radius=4)
        
        # Leyenda de Colores
        self.legend_bar = ctk.CTkFrame(f, fg_color="transparent")
        self.legend_bar.pack(fill="x", pady=(4, 0))
        for bg_key, fg_key, txt in [
            ("ok_row",    "ok_txt",    "■ Idéntico"),
            ("diff_row",  "diff_txt",  "■ Con diferencias de línea/estaca"),
            ("only1_row", "only1_txt", "■ Solo en Archivo 1"),
            ("only2_row", "only2_txt", "■ Solo en Archivo 2"),
        ]:
            lf = tk.Frame(self.legend_bar, bg=COLORS[bg_key], highlightthickness=1, highlightbackground=COLORS["border_light"])
            lf.pack(side="left", padx=(0, 6), pady=2)
            tk.Label(lf, text=txt, font=FONT_SM, fg=COLORS[fg_key], bg=COLORS[bg_key], padx=10, pady=3).pack()

        # Cabecera de columnas para el listado individual
        self.list_col_hdr = ctk.CTkFrame(f, height=32, corner_radius=0, fg_color=COLORS["col_hdr"])
        self.list_col_hdr.pack(fill="x", pady=(8, 0))

        # ── BARRA DE BUSQUEDA, FILTROS Y EXPORTACIONES ──
        self.filters_bar = ctk.CTkFrame(f, fg_color="transparent")
        self.filters_bar.pack(fill="x", pady=6)
        
        # Botones exportar (Derecha)
        self.btn_exp_xlsx = ctk.CTkButton(self.filters_bar, text="Exportar Excel (.xlsx)", font=FONT_SM, width=150, height=32,
                                          fg_color=COLORS["ok_row"], text_color=COLORS["ok_txt"], hover_color="#C2DFB9",
                                          command=self._on_export_excel_individual)
        self.btn_exp_xlsx.pack(side="right", padx=(4, 0))
        
        self.btn_exp_txt_c = ctk.CTkButton(self.filters_bar, text="TXT Completo", font=FONT_SM, width=120, height=32,
                                           fg_color=COLORS["col_hdr"], text_color=COLORS["text_light"], hover_color="#CBD5E1",
                                           command=self._on_export_txt_completo)
        self.btn_exp_txt_c.pack(side="right", padx=(4, 0))
        
        self.btn_exp_txt_d = ctk.CTkButton(self.filters_bar, text="TXT Diferencias", font=FONT_SM, width=120, height=32,
                                           fg_color=COLORS["diff_row"], text_color=COLORS["diff_txt"], hover_color="#FEDFA4",
                                           command=self._on_export_txt_diff)
        self.btn_exp_txt_d.pack(side="right", padx=(8, 0))
        
        # Separador vertical
        self.v_sep = ctk.CTkFrame(self.filters_bar, width=1, height=28, fg_color=COLORS["border_light"])
        self.v_sep.pack(side="right", padx=10)

        # Entrada de búsqueda
        self.search_val_ind = tk.StringVar()
        self.search_val_ind.trace_add("write", lambda *_: self._apply_individual_filter())
        
        self.ent_search = ctk.CTkEntry(self.filters_bar, placeholder_text="Buscar disparo...", textvariable=self.search_val_ind, font=FONT_SM, width=150, height=32)
        self.ent_search.pack(side="right")

        # Filtros radio-button
        self.filter_val_ind = ctk.StringVar(value="all")
        
        self.lbl_filt_label = ctk.CTkLabel(self.filters_bar, text="Filtrar:", font=FONT_BOLD)
        self.lbl_filt_label.pack(side="left", padx=5)
        
        self.radios = []
        for lbl, val in [("Todos","all"), ("Con diferencias","diff"),
                          ("Idénticos","ok"), ("Faltantes","missing")]:
            rb = ctk.CTkRadioButton(self.filters_bar, text=lbl, value=val, variable=self.filter_val_ind,
                                    font=FONT_SM, width=100, height=28, command=self._apply_individual_filter)
            rb.pack(side="left", padx=2)
            self.radios.append(rb)

        # ── CONTENEDOR LISTADO DE DISPAROS ──
        self.list_container = ctk.CTkFrame(f, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True, pady=4)
        
        self.scroll_list = ctk.CTkScrollableFrame(self.list_container, fg_color="transparent")
        self.scroll_list.pack(fill="both", expand=True)
        
        self.lbl_welcome_ind = ctk.CTkLabel(self.scroll_list, text="Carga dos archivos XPS o SPS y pulsa «Ejecutar comparación» para comenzar.",
                                            font=FONT, text_color=COLORS["muted_light"])
        self.lbl_welcome_ind.pack(pady=40, expand=True)

        # ── CONTENEDOR QC PROGRESO (Reemplaza al listado si es modo QC) ──
        self.qc_progress_container = ctk.CTkFrame(f, fg_color="transparent")
        
        self.qc_progress_card = ctk.CTkFrame(self.qc_progress_container, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        self.qc_progress_card.pack(fill="both", expand=True, pady=10)
        
        self.lbl_qc_status_title = ctk.CTkLabel(self.qc_progress_card, text="ESTADO DE LA OPERACIÓN DIARIA", font=FONT_BOLD, text_color=COLORS["accent"])
        self.lbl_qc_status_title.pack(anchor="w", padx=20, pady=(20, 5))
        
        self.progress_qc = ttk.Progressbar(self.qc_progress_card, mode='determinate', length=400)
        self.progress_qc.pack(anchor="w", padx=20, pady=10)
        
        self.lbl_qc_log = ctk.CTkLabel(self.qc_progress_card, text="Cola de carpetas vacía. Esperando inicio...", font=FONT_SM, text_color=COLORS["muted_light"])
        self.lbl_qc_log.pack(anchor="w", padx=20, pady=(0, 20))

        # Barra de estado inferior del panel
        self.ind_bottom_bar = ctk.CTkFrame(f, height=30, corner_radius=4, border_width=1)
        self.ind_bottom_bar.pack(fill="x", side="bottom", pady=(5, 0))
        self.ind_bottom_bar.pack_propagate(False)
        
        self.lbl_bottom_status = ctk.CTkLabel(self.ind_bottom_bar, text="Listo.", font=FONT_SM, text_color=COLORS["muted_light"])
        self.lbl_bottom_status.pack(side="left", padx=10)

    def _on_comp_mode_changed(self, value):
        """Alterna visualmente los widgets de entrada según el modo seleccionado (Individual vs QC)."""
        if value == "Paquete diario (QC)":
            self.frame_files_input.pack_forget()
            self.frame_folders_input.pack(fill="x")
            self.btn_execute_compare.configure(text="EJECUTAR COMPARACIÓN DE PAQUETES (QC)")
            
            # Ocultar listado y mostrar barra de progreso
            self.metrics_bar.pack_forget()
            self.ind_extra_lbl.pack_forget()
            self.legend_bar.pack_forget()
            self.list_col_hdr.pack_forget()
            self.filters_bar.pack_forget()
            self.list_container.pack_forget()
            
            self.qc_progress_container.pack(fill="both", expand=True, pady=4)
        else:
            self.frame_folders_input.pack_forget()
            self.frame_files_input.pack(fill="x")
            self.btn_execute_compare.configure(text="EJECUTAR COMPARACIÓN DE DATOS")
            
            # Ocultar barra de progreso y mostrar listado
            self.qc_progress_container.pack_forget()
            
            self.metrics_bar.pack(fill="x", pady=4)
            self.legend_bar.pack(fill="x", pady=(4, 0))
            self.list_col_hdr.pack(fill="x", pady=(8, 0))
            self.filters_bar.pack(fill="x", pady=6)
            self.list_container.pack(fill="both", expand=True, pady=4)

    def _auto_detect_file_type(self, path):
        """Determina de forma inteligente el tipo de archivo cargado y cambia el segmented button."""
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xps":
            self.segmented_selector.set("Individual XPS")
            self._on_comp_mode_changed("Individual XPS")
        elif ext == ".sps":
            self.segmented_selector.set("Individual SPS")
            self._on_comp_mode_changed("Individual SPS")
        elif ext in [".rps", ".rcp"]:
            self.segmented_selector.set("Individual RPS")
            self._on_comp_mode_changed("Individual RPS")
        elif ext == ".txt":
            # Escanear primeras líneas para detectar formato
            try:
                with open(path, "r", errors="replace") as f:
                    for _ in range(15):
                        line = f.readline()
                        if not line: break
                        if line.startswith("X"):
                            self.segmented_selector.set("Individual XPS")
                            self._on_comp_mode_changed("Individual XPS")
                            break
                        elif line.startswith("S"):
                            self.segmented_selector.set("Individual SPS")
                            self._on_comp_mode_changed("Individual SPS")
                            break
                        elif line.startswith("R"):
                            self.segmented_selector.set("Individual RPS")
                            self._on_comp_mode_changed("Individual RPS")
                            break
            except:
                pass

    def _on_qc_add_folder(self):
        carpeta = filedialog.askdirectory(title="Selecciona la carpeta diaria del paquete sísmico")
        if carpeta:
            self.folders_list.add_folder(carpeta)

    def _on_qc_clear_folders(self):
        self.folders_list.clear()

    # ──────────────────────────────────────────────────────────────────────────
    # PANEL 3: GENERACIÓN DE MAPAS
    # ──────────────────────────────────────────────────────────────────────────
    def _build_screen_mapas(self):
        f = self.frames["mapas"]
        
        # Encabezado
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        lbl_title = ctk.CTkLabel(header, text="GENERACIÓN DE MAPAS SÍSMICOS", font=FONT_H1)
        lbl_title.pack(anchor="w")
        lbl_desc = ctk.CTkLabel(header, text="Mapeo geográfico de los datos cargados y proyección en coordenadas UTM.", font=FONT_SM, text_color=COLORS["muted_light"])
        lbl_desc.pack(anchor="w")
        
        card = ctk.CTkFrame(f, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        card.pack(fill="both", expand=True, pady=5)
        
        # 1. Selección de archivos
        tk.Label(card, text="1. SELECCIÓN DE ARCHIVOS DEL PROYECTO", font=FONT_BOLD, bg=COLORS["surface_light"], fg=COLORS["accent"]).pack(anchor="w", padx=25, pady=(20, 5))
        
        # Selectores usando nuestro nuevo componente CTkFileSelector
        self.map_f_rps = CTkFileSelector(card, "Archivo RPS (Receptores)")
        self.map_f_rps.pack(fill="x", padx=25, pady=4)
        
        self.map_f_sps = CTkFileSelector(card, "Archivo SPS (Fuentes)")
        self.map_f_sps.pack(fill="x", padx=25, pady=4)
        
        self.map_f_xps = CTkFileSelector(card, "Archivo XPS (Relaciones de Disparo)")
        self.map_f_xps.pack(fill="x", padx=25, pady=4)

        tk.Frame(card, bg=COLORS["border_light"], height=1).pack(fill="x", padx=25, pady=15)

        # 2. Configuración
        tk.Label(card, text="2. PARÁMETROS SÍSMICOS Y UTM", font=FONT_BOLD, bg=COLORS["surface_light"], fg=COLORS["accent"]).pack(anchor="w", padx=25, pady=(5, 5))
        
        grid_config = ctk.CTkFrame(card, fg_color="transparent")
        grid_config.pack(fill="x", padx=25, pady=5)
        
        lbl_utm = ctk.CTkLabel(grid_config, text="Zona de proyección UTM:", font=FONT)
        lbl_utm.grid(row=0, column=0, sticky="w", pady=5)
        
        self.combo_utm_map = ctk.CTkOptionMenu(grid_config, values=["Zona 14N (Q14)", "Zona 15N (Q15)"], font=FONT_BOLD, width=200, height=32, fg_color=COLORS["accent"], button_color=COLORS["accent"], button_hover_color=COLORS["accent_hover"])
        self.combo_utm_map.set("Zona 14N (Q14)")
        self.combo_utm_map.grid(row=0, column=1, sticky="w", padx=15, pady=5)
        
        lbl_muestreo = ctk.CTkLabel(grid_config, text="Muestreo de visualización (1 de cada N):", font=FONT)
        lbl_muestreo.grid(row=1, column=0, sticky="w", pady=5)
        
        self.ent_muestreo_map = ctk.CTkEntry(grid_config, font=FONT_SM, width=80, height=32)
        self.ent_muestreo_map.insert(0, "30")
        self.ent_muestreo_map.grid(row=1, column=1, sticky="w", padx=15, pady=5)

        tk.Frame(card, bg=COLORS["border_light"], height=1).pack(fill="x", padx=25, pady=15)

        # 3. Acciones
        btn_action_f = ctk.CTkFrame(card, fg_color="transparent")
        btn_action_f.pack(fill="x", padx=25, pady=(5, 20))
        
        self.btn_gen_map = ctk.CTkButton(btn_action_f, text="GENERAR MAPA INTERACTIVO", font=FONT_H2, 
                                         fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                         width=300, height=44, command=self._on_generate_map)
        self.btn_gen_map.pack(side="left")
        
        self.progress_map = ttk.Progressbar(btn_action_f, mode='determinate', length=250)
        self.progress_map.pack(side="left", padx=20)
        
        self.lbl_estado_map = ctk.CTkLabel(btn_action_f, text="Esperando inicio...", font=FONT_SM, text_color=COLORS["muted_light"])
        self.lbl_estado_map.pack(side="left")

    # ──────────────────────────────────────────────────────────────────────────
    # PANEL 4: CONFIGURACIÓN Y TEMAS
    # ──────────────────────────────────────────────────────────────────────────
    def _build_screen_config(self):
        f = self.frames["config"]
        
        # Encabezado
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        lbl_title = ctk.CTkLabel(header, text="CONFIGURACIÓN GLOBAL Y TEMAS", font=FONT_H1)
        lbl_title.pack(anchor="w")
        lbl_desc = ctk.CTkLabel(header, text="Ajustes de la interfaz de usuario, personalización de colores y parámetros predeterminados.", font=FONT_SM, text_color=COLORS["muted_light"])
        lbl_desc.pack(anchor="w")
        
        card = ctk.CTkFrame(f, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        card.pack(fill="both", expand=True, pady=5)
        
        # 1. Configuración de Apariencia
        tk.Label(card, text="1. APARIENCIA VISUAL Y TEMA", font=FONT_BOLD, bg=COLORS["surface_light"], fg=COLORS["accent"]).pack(anchor="w", padx=25, pady=(20, 5))
        
        theme_frame = ctk.CTkFrame(card, fg_color="transparent")
        theme_frame.pack(fill="x", padx=25, pady=5)
        
        lbl_theme = ctk.CTkLabel(theme_frame, text="Tema de la aplicación:", font=FONT)
        lbl_theme.pack(side="left", padx=(0, 15))
        
        self.theme_selector = ctk.CTkSegmentedButton(
            theme_frame,
            values=["Light", "Dark", "System"],
            font=FONT_BOLD, height=32,
            command=self._on_theme_changed
        )
        self.theme_selector.pack(side="left")
        self.theme_selector.set("Light")

        tk.Frame(card, bg=COLORS["border_light"], height=1).pack(fill="x", padx=25, pady=20)

        # 2. Configuración predeterminada del sistema
        tk.Label(card, text="2. PARÁMETROS GENERALES SÍSMICOS", font=FONT_BOLD, bg=COLORS["surface_light"], fg=COLORS["accent"]).pack(anchor="w", padx=25, pady=(5, 5))
        
        params_frame = ctk.CTkFrame(card, fg_color="transparent")
        params_frame.pack(fill="x", padx=25, pady=10)
        
        lbl_params_desc = ctk.CTkLabel(params_frame, text="Zona UTM de arranque por defecto:  Zona 14N (Q14)\nMuestreo predeterminado de puntos:  30", font=FONT, justify="left")
        lbl_params_desc.pack(anchor="w")

        # Botón para limpiar cache / estados
        btn_reset = ctk.CTkButton(card, text="Restablecer Configuración de Fábrica", font=FONT_BOLD, fg_color="#EF4444", hover_color="#DC2626", text_color="white", height=36, command=self._on_reset_settings)
        btn_reset.pack(anchor="w", padx=25, pady=25)

    def _on_theme_changed(self, theme):
        """Cambia dinámicamente el aspecto gráfico de CustomTkinter."""
        ctk.set_appearance_mode(theme)
        
        # Forzar actualización de colores en nuestras tarjetas de métricas
        self.root.update()
        
        # Actualizar colores en widgets personalizados
        self.folders_list._update_colors()
        self.folders_list.render()
        
        # Cambiar el color de fondo de las áreas principales de control
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            self.main_area.configure(fg_color=COLORS["bg_dark"])
            self.sidebar.configure(fg_color=COLORS["sidebar_dark"])
            # Actualizar tarjetas de KPI
            self.card_lmaps.update_theme()
            self.card_lcomp.update_theme()
            self.card_lfiles.update_theme()
            self.m_d1.update_theme()
            self.m_d2.update_theme()
            self.m_diff.update_theme()
            self.m_miss.update_theme()
        else:
            self.main_area.configure(fg_color=COLORS["bg_light"])
            self.sidebar.configure(fg_color=COLORS["sidebar_light"])
            self.card_lmaps.update_theme()
            self.card_lcomp.update_theme()
            self.card_lfiles.update_theme()
            self.m_d1.update_theme()
            self.m_d2.update_theme()
            self.m_diff.update_theme()
            self.m_miss.update_theme()

    def _on_reset_settings(self):
        self.theme_selector.set("Light")
        self._on_theme_changed("Light")
        messagebox.showinfo("Configuración", "La configuración ha sido restablecida con éxito.")

    # ──────────────────────────────────────────────────────────────────────────
    # MÉTODOS DE GENERACIÓN DE MAPAS
    # ──────────────────────────────────────────────────────────────────────────
    def _on_generate_map(self):
        rps_path = self.map_f_rps.get()
        sps_path = self.map_f_sps.get()
        xps_path = self.map_f_xps.get()
        
        if not rps_path and not sps_path:
            messagebox.showwarning("Error", "Selecciona al menos RPS o SPS.")
            return

        self.btn_gen_map.configure(state="disabled")
        self.progress_map['value'] = 0
        self.lbl_estado_map.configure(text="Procesando datos...")
        
        epsg = 32614 if self.combo_utm_map.get() == "Zona 14N (Q14)" else 32615
        try:
            muestreo = int(self.ent_muestreo_map.get())
        except ValueError:
            muestreo = 30
            self.ent_muestreo_map.delete(0, tk.END)
            self.ent_muestreo_map.insert(0, "30")

        # Usar la clase de control de barra de progreso existente
        progreso = Progreso(self.root, self.progress_map, self.lbl_estado_map)

        def tarea():
            try:
                generar_mapa_completo(
                    rps_path, sps_path, xps_path,
                    epsg, muestreo, progreso
                )
                self.root.after(0, self._ok_mapa)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, functools.partial(self._error_mapa, str(e)))

        threading.Thread(target=tarea, daemon=True).start()

    def _ok_mapa(self):
        self.btn_gen_map.configure(state="normal")
        self.progress_map['value'] = 100
        self.lbl_estado_map.configure(text="Mapa generado correctamente.", text_color=COLORS["ok_txt"])
        webbrowser.open('file://' + os.path.realpath("mapa_sismico.html"))
        messagebox.showinfo("Éxito", "El mapa interactivo se ha generado y abierto en su navegador.")
        self.recargar_dashboard_kpis()

    def _error_mapa(self, msg):
        self.btn_gen_map.configure(state="normal")
        self.progress_map['value'] = 0
        self.lbl_estado_map.configure(text="Error de generación.", text_color=COLORS["red_accent"])
        messagebox.showerror("Error", msg)

    # ──────────────────────────────────────────────────────────────────────────
    # MÉTODOS DEL COMPARADOR ESTRUCTURAL
    # ──────────────────────────────────────────────────────────────────────────
    def _on_execute_comparison(self):
        mode = self.segmented_selector.get()
        
        if mode == "Paquete diario (QC)":
            carpetas = self.folders_list.folders
            if len(carpetas) < 2:
                messagebox.showwarning("Advertencia", "Selecciona al menos 2 carpetas de paquetes diarios para comparar.")
                return

            self.btn_execute_compare.configure(state="disabled")
            self.progress_qc['value'] = 0
            self.lbl_qc_log.configure(text="Comparando carpetas diarias...")
            self.lbl_bottom_status.configure(text="Procesando QC...")

            progreso = Progreso(self.root, self.progress_qc, self.lbl_qc_log)

            def tarea():
                try:
                    resultados = comparar_carpetas(carpetas, progreso)
                    self.root.after(0, self._finalizar_qc, resultados)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    self.root.after(0, functools.partial(self._error_qc, str(e)))

            threading.Thread(target=tarea, daemon=True).start()
            
        else: # Comparación Individual (SPS, RPS, XPS)
            p1 = self.ind_f1.get()
            p2 = self.ind_f2.get()
            if not p1 or not p2:
                messagebox.showwarning("Faltan archivos", "Selecciona los dos archivos antes de comparar.")
                return
                
            self.lbl_bottom_status.configure(text="Comparando archivos...")
            self.root.update()
            
            try:
                self._result = run_comparison(p1, p2)
                self._render_individual_results()
            except Exception as ex:
                messagebox.showerror("Error", str(ex))
                self.lbl_bottom_status.configure(text="Error en la comparación.")

    def _finalizar_qc(self, resultados):
        self.btn_execute_compare.configure(state="normal")
        self.progress_qc['value'] = 100
        
        difs_encontradas = False
        if resultados:
            difs = resultados.get('diferencias', {})
            xps_difs = resultados.get('xps_comparaciones', [])
            
            if any(not df.empty for df in difs.values() if isinstance(df, pd.DataFrame)):
                difs_encontradas = True
            for item in xps_difs:
                res = item.get('resultado', {})
                if len(res.get('disparos_diff', [])) > 0 or len(res.get('disparos_solo1', [])) > 0 or len(res.get('disparos_solo2', [])) > 0:
                    difs_encontradas = True
                    break
        
        if difs_encontradas:
            self.lbl_qc_log.configure(text="Comparativa QC completada con diferencias.", text_color=COLORS["red_accent"])
            self.lbl_bottom_status.configure(text="Diferencias encontradas.")
            messagebox.showinfo("QC Completado", 
                              "Se generó 'comparacion_paquetes.xlsx' con las diferencias de coordenadas (RPS/SPS) y el comparador estructural de disparos (XPS).\n\n"
                              "Revísalo en la carpeta del programa.")
        else:
            self.lbl_qc_log.configure(text="QC completado. Sin diferencias.", text_color=COLORS["ok_txt"])
            self.lbl_bottom_status.configure(text="Proceso limpio (sin diferencias).")
            messagebox.showinfo("QC Completado", "Todas las carpetas comparadas son idénticas.")
        self.recargar_dashboard_kpis()

    def _error_qc(self, msg):
        self.btn_execute_compare.configure(state="normal")
        self.progress_qc['value'] = 0
        self.lbl_qc_log.configure(text="Error en la comparación.", text_color=COLORS["red_accent"])
        self.lbl_bottom_status.configure(text="Error de proceso QC.")
        messagebox.showerror("Error", msg)

    def _render_individual_results(self):
        r = self._result
        n1, n2 = r["n_disparos1"], r["n_disparos2"]
        ndiff  = len(r["disparos_diff"])
        nmiss  = len(r["disparos_solo1"]) + len(r["disparos_solo2"])

        self.m_d1.set(n1)
        self.m_d2.set(n2, COLORS["diff_txt"] if n1 != n2 else None)
        self.m_diff.set(ndiff, COLORS["diff_txt"] if ndiff else COLORS["ok_txt"])
        self.m_miss.set(nmiss, COLORS["only1_txt"] if nmiss else COLORS["ok_txt"])

        if n1 != n2:
            diff  = abs(n1 - n2)
            which = "Archivo 1" if n1 > n2 else "Archivo 2"
            self.ind_extra_lbl.configure(text=f"  ⚠  El {which} tiene {diff} disparo(s) adicional(es) sin correspondencia.")
            self.ind_extra_lbl.pack(fill="x", pady=(0, 4))
        else:
            self.ind_extra_lbl.pack_forget()

        # Re-dibujar cabeceras de tabla
        for w in self.list_col_hdr.winfo_children():
            w.destroy()

        d_cell = tk.Frame(self.list_col_hdr, bg=COLORS["col_hdr"], width=COL_DISP)
        d_cell.pack(side="left", fill="y")
        d_cell.pack_propagate(False)
        tk.Label(d_cell, text="DISPARO", font=FONT_BOLD, bg=COLORS["col_hdr"], fg=COLORS["col_hdr_txt"], anchor="center").pack(expand=True, fill="both")

        tk.Frame(self.list_col_hdr, bg=COLORS["border_light"], width=1).pack(side="left", fill="y")

        for txt in (f"ARCHIVO 1: {r['name1']}", f"ARCHIVO 2: {r['name2']}"):
            cell = tk.Frame(self.list_col_hdr, bg=COLORS["col_hdr"])
            cell.pack(side="left", fill="both", expand=True)
            tk.Label(cell, text=txt, font=FONT_BOLD, bg=COLORS["col_hdr"], fg=COLORS["col_hdr_txt"], anchor="center").pack(fill="both", pady=5)
            tk.Frame(self.list_col_hdr, bg=COLORS["border_light"], width=1).pack(side="left", fill="y")

        # Limpiar listado de filas
        for w in self.scroll_list.winfo_children():
            w.destroy()
        self._disp_frames = []

        for shot in r["results"]:
            row = CTkDisparoRow(self.scroll_list, shot)
            row.pack(fill="x", pady=2)
            self._disp_frames.append((row, shot))

        self._apply_individual_filter()

        total = len(r["results"])
        ok    = len(r["disparos_ok"])
        self.lbl_bottom_status.configure(
            text=(f"✔  {total} disparos  ·  {ok} idénticos  ·  "
                  f"{ndiff} con diferencias  ·  {nmiss} faltantes"))

    def _apply_individual_filter(self):
        if not self._disp_frames:
            return
        filt   = self.filter_val_ind.get()
        search = self.search_val_ind.get().strip().lower()
        for row, s in self._disp_frames:
            show = True
            if filt == "diff"    and s["status"] != "diff":              show = False
            if filt == "ok"      and s["status"] != "ok":                show = False
            if filt == "missing" and s["status"] not in ("only1","only2"): show = False
            if show and search and search not in s["disparo"].lower():    show = False
            if show: row.pack(fill="x", pady=2)
            else:    row.pack_forget()

    def _on_export_excel_individual(self):
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
                self.lbl_bottom_status.configure(text=f"Reporte Excel guardado: {os.path.basename(path)}")
                messagebox.showinfo("Exportación Exitosa", f"El archivo Excel ha sido generado con éxito:\n{path}")
            except ImportError as e:
                messagebox.showerror("Módulo faltante", str(e))

    def _on_export_txt_completo(self):
        if not self._result:
            messagebox.showwarning("Sin datos", "Ejecuta una comparación primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile="comparativa_completa.txt")
        if path:
            export_comparativa(self._result, path)
            self.lbl_bottom_status.configure(text=f"Comparativa completa guardada: {os.path.basename(path)}")

    def _on_export_txt_diff(self):
        if not self._result:
            messagebox.showwarning("Sin datos", "Ejecuta una comparación primero.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile="reporte_diferencias.txt")
        if path:
            export_txt(self._result, path)
            self.lbl_bottom_status.configure(text=f"Reporte de diferencias guardado: {os.path.basename(path)}")