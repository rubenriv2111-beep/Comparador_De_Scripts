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
from core.qc_comparator import comparar_carpetas, comparar_sin_merge, aplicar_estilo_hoja
from utils.progreso import Progreso
from core.comparador_disparos import run_comparison, export_xlsx, export_txt, export_comparativa
from core.lectores import leer_sps_rps

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
        # Dos páginas superpuestas
        draw.rectangle([4, 4, 13, 15], outline=color_rgb, width=2)
        draw.rectangle([11, 9, 20, 20], outline=color_rgb, width=2)
    elif tipo == "mapas":
        # Globo con retícula
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
        # Archivo
        draw.polygon([(4,3), (15,3), (20,8), (20,20), (4,20)], outline=color_rgb, fill=None)
    elif tipo == "lupita":
        # Lente de la lupa (círculo)
        draw.ellipse([4, 4, 14, 14], outline=color_rgb, width=2)
        # Mango de la lupa (línea)
        draw.line([12, 12, 19, 19], fill=color_rgb, width=3)
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


# ─── Selector de Carpetas Moderno (QC) ─────────────────────────────────────────
class CTkFolderSelector(ctk.CTkFrame):
    def __init__(self, parent, label, callback_add=None, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._label = label
        self._callback = callback_add
        self._build()

    def _build(self):
        self.columnconfigure(0, weight=1)
        
        self.lbl_title = ctk.CTkLabel(self, text=self._label, font=FONT_BOLD, anchor="w")
        self.lbl_title.grid(row=0, column=0, sticky="w", pady=(0, 2))
        
        self.entry_path = ctk.CTkEntry(self, placeholder_text="No se ha seleccionado ninguna carpeta...", 
                                      font=FONT_SM, height=32)
        self.entry_path.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        
        icon_folder = crear_icono_diseno("folder", "#FFFFFF")
        self.btn_select = ctk.CTkButton(self, text="Agregar", font=FONT_BOLD, width=95, height=32, 
                                        fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                        image=icon_folder, command=self._pick)
        self.btn_select.grid(row=1, column=1, sticky="e")

    def _pick(self):
        p = filedialog.askdirectory(title="Selecciona la carpeta diaria del paquete sísmico")
        if not p:
            return
        self.entry_path.delete(0, tk.END)
        self.entry_path.insert(0, p)
        if self._callback:
            self._callback(p)


# ─── Lista de Rutas Moderna (Estilo Listbox Avanzado) ─────────────────────────
class CTkPathList(ctk.CTkScrollableFrame):
    def __init__(self, parent, placeholder="No hay elementos agregados.", **kw):
        super().__init__(parent, fg_color="transparent", corner_radius=6, border_width=1, **kw)
        self.paths = []
        self.placeholder = placeholder
        self._update_colors()
        self.render()

    def _update_colors(self):
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            self.configure(border_color=COLORS["border_dark"])
        else:
            self.configure(border_color=COLORS["border_light"])

    def add_path(self, path):
        if path and path not in self.paths:
            self.paths.append(path)
            self.render()

    def add_folder(self, path): 
        # Alias para compatibilidad
        self.add_path(path)

    def remove_path(self, path):
        if path in self.paths:
            self.paths.remove(path)
            self.render()

    def remove_folder(self, path): 
        # Alias para compatibilidad
        self.remove_path(path)

    @property
    def folders(self): 
        # Alias para compatibilidad
        return self.paths

    def clear(self):
        self.paths = []
        self.render()

    def render(self):
        for w in self.winfo_children():
            w.destroy()
            
        if not self.paths:
            lbl_empty = ctk.CTkLabel(self, text=self.placeholder, 
                                     font=FONT_SM, text_color=COLORS["muted_light"])
            lbl_empty.pack(pady=35, expand=True)
            return

        for idx, path in enumerate(self.paths):
            row_bg = COLORS["bg_light"] if ctk.get_appearance_mode() == "Light" else COLORS["surface_dark"]
            row = ctk.CTkFrame(self, fg_color=row_bg, corner_radius=6, height=36)
            row.pack(fill="x", pady=2, padx=2)
            row.pack_propagate(False)
            
            lbl_num = ctk.CTkLabel(row, text=f"  {idx+1}.  ", font=FONT_BOLD, text_color=COLORS["accent"])
            lbl_num.pack(side="left")
            
            # Mostrar solo el nombre del archivo si es archivo, o la ruta completa si es carpeta
            display_text = os.path.basename(path) if os.path.isfile(path) else path
            lbl_path = ctk.CTkLabel(row, text=display_text, font=FONT_MONO, anchor="w")
            lbl_path.pack(side="left", fill="x", expand=True, padx=4)
            
            btn_del = ctk.CTkButton(
                row, text="✕", width=22, height=22, corner_radius=4,
                fg_color="transparent", hover_color="#EF4444" if ctk.get_appearance_mode()=="Light" else "#7F1D1D", 
                text_color="#EF4444",
                font=("Segoe UI", 11, "bold"),
                command=functools.partial(self.remove_path, path)
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


# ─── Formateador de Fila de Coordenadas SPS/RPS ──────────────────────────────
def format_diff_row(row, modo):
    tipo = row.get("Tipo de Cambio", "")
    if tipo == "Eliminado":
        coords = []
        if 'x_base' in row and pd.notna(row['x_base']): coords.append(f"X Base: {row['x_base']:.1f}")
        if 'y_base' in row and pd.notna(row['y_base']): coords.append(f"Y Base: {row['y_base']:.1f}")
        if 'elevacion_base' in row and pd.notna(row['elevacion_base']): coords.append(f"Z Base: {row['elevacion_base']:.1f}")
        return f"Eliminado del Archivo 2. (" + ", ".join(coords) + ")"
    elif tipo == "Nuevo":
        coords = []
        if 'x_nuevo' in row and pd.notna(row['x_nuevo']): coords.append(f"X Nuevo: {row['x_nuevo']:.1f}")
        if 'y_nuevo' in row and pd.notna(row['y_nuevo']): coords.append(f"Y Nuevo: {row['y_nuevo']:.1f}")
        if 'elevacion_nuevo' in row and pd.notna(row['elevacion_nuevo']): coords.append(f"Z Nuevo: {row['elevacion_nuevo']:.1f}")
        return f"Nuevo en Archivo 2. (" + ", ".join(coords) + ")"
    elif tipo == "Cambio de Coordenada":
        diffs = []
        if 'x_base' in row and 'x_nuevo' in row and row['x_base'] != row['x_nuevo']:
            diffs.append(f"X: {row['x_base']:.1f} → {row['x_nuevo']:.1f}")
        if 'y_base' in row and 'y_nuevo' in row and row['y_base'] != row['y_nuevo']:
            diffs.append(f"Y: {row['y_base']:.1f} → {row['y_nuevo']:.1f}")
        if 'elevacion_base' in row and 'elevacion_nuevo' in row and row['elevacion_base'] != row['elevacion_nuevo']:
            diffs.append(f"Z: {row['elevacion_base']:.1f} → {row['elevacion_nuevo']:.1f}")
        return "Cambio: " + ", ".join(diffs)
    return ""


# ─── Aplicación Principal (Dashboard) ─────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.root = self
        
        # Dimensiones y títulos ejecutivos
        self.title("SINOPEC - Monitor de Adquisición y Comparación Script 采集与脚本比对监控系统 ")
        self.geometry("1200x620")
        self.minsize(1050, 720)
        
        # Variables de control
        self.current_screen = "dashboard"
        
        # Rutas de Archivos para Tab 1 (Mapas)
        self.map_rps = ""
        self.map_sps = ""
        self.map_xps = ""
        
        # Datos del comparador individual
        self._result = None
        self._df_result = None
        
        # Imagen del logotipo
        self.logo_image = None
        
        self._build_dashboard_layout()
        self.set_screen("dashboard")

    def _build_dashboard_layout(self):
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
        self.lbl_sys_title = ctk.CTkLabel(self.sidebar, text="SISTEMA DE VALIDACIÓN DE ADQUISICIÓN", font=("Segoe UI", 10, "bold"), text_color="#A5B4FC")
        self.lbl_sys_title.pack(anchor="center", pady=(5, 0))
        self.lbl_sys_title_cn = ctk.CTkLabel(self.sidebar, text="采集验证系统", font=("Segoe UI", 10, "bold"), text_color="#A5B4FC")
        self.lbl_sys_title_cn.pack(anchor="center", pady=(2, 10))
        self.lbl_version = ctk.CTkLabel(self.sidebar, text="Versión 2.3.0", font=("Segoe UI", 8, "italic"), text_color="#64748B")
        self.lbl_version.pack(anchor="center", pady=(0, 20))
        
        # Separador decorativo superior
        line_top = ctk.CTkFrame(self.sidebar, height=2, fg_color=COLORS["red_accent"])
        line_top.pack(fill="x", padx=15, pady=(0, 15))
        
        # Botones de navegación con iconos
        self.nav_buttons = {}
        sections = [
            ("dashboard", "Dashboard Principal", "dashboard"),
            ("comparador", "Comparador Estructural", "comparador"),
            ("boombox", "Analizar Boom Box", "lupita"),
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
            
        # Pie de página
        self.sidebar_footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_footer.pack(side="bottom", fill="x", pady=15, padx=15)
        
        lbl_dev_title = ctk.CTkLabel(self.sidebar_footer, text="INGENIERÍA Y CONTROL", font=("Segoe UI", 7, "bold"), text_color="#64748B")
        lbl_dev_title.pack(anchor="w")
        lbl_developer = ctk.CTkLabel(self.sidebar_footer, text="Adquisicion de Datos Sercel", font=("Segoe UI", 9, "bold"), text_color="#E2E8F0")
        lbl_developer.pack(anchor="w")

        # ── 2. ÁREA PRINCIPAL (MAIN VIEWPORT) ──
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color=COLORS["bg_light"])
        self.main_area.grid(row=0, column=1, sticky="nsew")
        
        self.frames = {
            "dashboard": ctk.CTkFrame(self.main_area, fg_color="transparent"),
            "comparador": ctk.CTkFrame(self.main_area, fg_color="transparent"),
            "boombox": ctk.CTkFrame(self.main_area, fg_color="transparent"),
            "mapas": ctk.CTkFrame(self.main_area, fg_color="transparent"),
            "config": ctk.CTkFrame(self.main_area, fg_color="transparent")
        }
        
        self._build_screen_dashboard()
        self._build_screen_comparador()
        self._build_screen_boombox()
        self._build_screen_mapas()
        self._build_screen_config()

    def set_screen(self, screen_key):
        self.current_screen = screen_key
        
        for k, btn in self.nav_buttons.items():
            if k == screen_key:
                btn.configure(fg_color="#1E3A8A", text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color="#E2E8F0")
                
        for f in self.frames.values():
            f.pack_forget()
            
        self.frames[screen_key].pack(fill="both", expand=True, padx=25, pady=25)
        
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
        
        text_container = ctk.CTkFrame(header, fg_color="transparent")
        text_container.pack(side="left", fill="y")
        
        lbl_title = ctk.CTkLabel(text_container, text="DASHBOARD 仪表板", font=FONT_H1)
        lbl_title.pack(anchor="w")
        lbl_desc = ctk.CTkLabel(text_container, text="Control administrativo del proyecto y métricas clave de adquisición.", font=FONT_SM, text_color=COLORS["muted_light"])
        lbl_desc.pack(anchor="w")
        
        # Fila de tarjetas KPI
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
            "• ANALIZADOR BOOM BOX: Permite procesar archivos logs de Boom Box por lotes (selección múltiple) "
            "y exportar toda la información consolidada en un reporte Excel.\n"
            "• GENERADOR DE MAPAS: Parsea las coordenadas geográficas de los geófonos y fuentes, proyecta la información "
            "a UTM y genera un plano interactivo HTML interactivo de visualización sísmica.\n"
            "• CONFIGURACIÓN Y TEMAS: Ajusta la interfaz visual del sistema (Modo Oscuro, Claro) y los parámetros globales."
        )
        lbl_guia = ctk.CTkLabel(info_card, text=guia_uso, font=FONT, justify="left", text_color=COLORS["text_light"])
        lbl_guia.pack(anchor="w", padx=20, pady=10)

    def recargar_dashboard_kpis(self):
        if os.path.exists("mapa_sismico.html"):
            mod_time = datetime.fromtimestamp(os.path.getmtime("mapa_sismico.html")).strftime("%H:%M:%S")
            self.card_lmaps.set(f"Generado ({mod_time})", COLORS["ok_txt"])
        else:
            self.card_lmaps.set("No generado", COLORS["muted_light"])
            
        if os.path.exists("comparacion_paquetes.xlsx"):
            mod_time = datetime.fromtimestamp(os.path.getmtime("comparacion_paquetes.xlsx")).strftime("%H:%M:%S")
            self.card_lcomp.set(f"Reporte Listo ({mod_time})", COLORS["ok_txt"])
        else:
            self.card_lcomp.set("No disponible", COLORS["muted_light"])
            
        self.card_lfiles.set("SPS, RPS, XPS", COLORS["accent"])


    # ──────────────────────────────────────────────────────────────────────────
    # PANEL 2: COMPARADOR UNIFICADO (INDIVIDUAL Y QC)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_screen_comparador(self):
        f = self.frames["comparador"]
        
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        
        lbl_title = ctk.CTkLabel(header, text="COMPARADOR ESTRUCTURAL DE SCRIPTS 脚本结构比较器 ", font=FONT_H1)
        lbl_title.pack(anchor="w")
        lbl_desc = ctk.CTkLabel(header, text="Módulo de comparación unificado para archivos unitarios y análisis de carpetas diarias (QC).", font=FONT_SM, text_color=COLORS["muted_light"])
        lbl_desc.pack(anchor="w")
        
        # Tarjeta selectora del modo
        selector_card = ctk.CTkFrame(f, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        selector_card.pack(fill="x", pady=5)
        
        lbl_sel_t = ctk.CTkLabel(selector_card, text="TIPO DE COMPARACIÓN", font=FONT_BOLD, text_color=COLORS["accent"])
        lbl_sel_t.pack(anchor="w", padx=15, pady=(12, 4))
        
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
        
        self.ind_f1 = CTkFileSelector(self.files_grid, "Archivo 1 (Línea Base)", callback_change=self._auto_detect_file_type)
        self.ind_f1.pack(fill="x", padx=20, pady=(15, 8))
        
        self.ind_f2 = CTkFileSelector(self.files_grid, "Archivo 2 (Línea Nueva)")
        self.ind_f2.pack(fill="x", padx=20, pady=(8, 15))

        # Subpanel B: Entrada de Directorios en Cola (QC) (Inicialmente oculto)
        self.frame_folders_input = ctk.CTkFrame(self.inputs_container, fg_color="transparent")
        
        self.folders_card = ctk.CTkFrame(self.frame_folders_input, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        self.folders_card.pack(fill="x", pady=2)
        
        # Botón de carga visualmente idéntico en Paquete diario (QC)
        self.qc_folder_selector = CTkFolderSelector(self.folders_card, "Seleccionar Carpeta de Paquete Diario:", callback_add=self._on_qc_add_folder)
        self.qc_folder_selector.pack(fill="x", padx=20, pady=(15, 8))
        
        # Contenedor de cola
        list_controls = ctk.CTkFrame(self.folders_card, fg_color="transparent")
        list_controls.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        btn_box = ctk.CTkFrame(list_controls, fg_color="transparent")
        btn_box.pack(side="left", fill="y", padx=(0, 15))
        
        btn_clr = ctk.CTkButton(btn_box, text=" Limpiar Lista completa", font=FONT_BOLD,
                                fg_color=COLORS["bg_light"], text_color=COLORS["text_light"], hover_color=COLORS["border_light"],
                                width=180, height=34, command=self._on_qc_clear_folders)
        btn_clr.pack(pady=3)
        
        self.folders_list = CTkPathList(list_controls, placeholder="No hay carpetas agregadas a la cola de comparación.", height=120)
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
        self.metrics_bar = ctk.CTkFrame(f, fg_color="transparent")
        self.metrics_bar.pack(fill="x", pady=4)
        
        self.m_d1 = CTkKPICard(self.metrics_bar, "Registros Archivo 1", "—")
        self.m_d1.pack(side="left", expand=True, fill="x", padx=(0, 8))
        
        self.m_d2 = CTkKPICard(self.metrics_bar, "Registros Archivo 2", "—")
        self.m_d2.pack(side="left", expand=True, fill="x", padx=(0, 8))
        
        self.m_diff = CTkKPICard(self.metrics_bar, "Con Diferencias", "—")
        self.m_diff.pack(side="left", expand=True, fill="x", padx=(0, 8))
        
        self.m_miss = CTkKPICard(self.metrics_bar, "Registros Faltantes", "—")
        self.m_miss.pack(side="left", expand=True, fill="x")

        # Banner de diferencias (Cabecera extra)
        self.ind_extra_lbl = ctk.CTkLabel(f, text="", font=FONT_SM, fg_color="#FFF3CD", text_color=COLORS["diff_txt"], height=30, corner_radius=4)
        
        # Leyenda de Colores
        self.legend_bar = ctk.CTkFrame(f, fg_color="transparent")
        self.legend_bar.pack(fill="x", pady=(4, 0))
        for bg_key, fg_key, txt in [
            ("ok_row",    "ok_txt",    "■ Coincidente"),
            ("diff_row",  "diff_txt",  "■ Con diferencias geométricas/estacas"),
            ("only1_row", "only1_txt", "■ Solo en Archivo 1"),
            ("only2_row", "only2_txt", "■ Solo en Archivo 2"),
        ]:
            lf = tk.Frame(self.legend_bar, bg=COLORS[bg_key], highlightthickness=1, highlightbackground=COLORS["border_light"])
            lf.pack(side="left", padx=(0, 6), pady=2)
            tk.Label(lf, text=txt, font=FONT_SM, fg=COLORS[fg_key], bg=COLORS[bg_key], padx=10, pady=3).pack()

        # ── BARRA DE BUSQUEDA, FILTROS Y EXPORTACIONES ──
        self.filters_bar = ctk.CTkFrame(f, fg_color="transparent")
        self.filters_bar.pack(fill="x", pady=6)
        
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
        
        self.v_sep = ctk.CTkFrame(self.filters_bar, width=1, height=28, fg_color=COLORS["border_light"])
        self.v_sep.pack(side="right", padx=10)

        self.search_val_ind = tk.StringVar()
        self.search_val_ind.trace_add("write", lambda *_: self._apply_individual_filter())
        
        self.ent_search = ctk.CTkEntry(self.filters_bar, placeholder_text="Buscar disparo...", textvariable=self.search_val_ind, font=FONT_SM, width=150, height=32)
        self.ent_search.pack(side="right")

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

        # ── CONTENEDOR DE LA TABLA PRINCIPAL (Treeview de alta calidad) ──
        self.list_container = ctk.CTkFrame(f, fg_color="transparent")
        self.list_container.pack(fill="both", expand=True, pady=4)
        
        # Definición del estilo de Treeview
        self.tree_style = ttk.Style()
        self.tree_style.theme_use("clam")
        self.tree_style.configure("Treeview", 
                                  background="#FFFFFF", 
                                  foreground="#0F172A", 
                                  rowheight=28, 
                                  font=("Segoe UI", 9),
                                  fieldbackground="#FFFFFF",
                                  borderwidth=0)
        self.tree_style.configure("Treeview.Heading", 
                                  background="#0F2942", 
                                  foreground="#FFFFFF", 
                                  font=("Segoe UI", 9, "bold"),
                                  borderwidth=0)
        self.tree_style.map("Treeview", 
                            background=[("selected", "#1E3A8A")], 
                            foreground=[("selected", "#FFFFFF")])
        self.tree_style.map("Treeview.Heading",
                            background=[("active", "#1E3A5F")])

        # Crear Treeview
        self.tree_results = ttk.Treeview(self.list_container, show="headings", selectmode="browse")
        
        # Configurar colores de tags de fila en colores pasteles sobrios corporativos
        self.tree_results.tag_configure("ok", background="#E2EFDA", foreground="#375623")
        self.tree_results.tag_configure("diff", background="#FFF2CC", foreground="#7F6000")
        self.tree_results.tag_configure("only1", background="#D9E1F2", foreground="#1F4E78")
        self.tree_results.tag_configure("only2", background="#F2F2F2", foreground="#595959")

        # Scrollbars
        sb_y = ttk.Scrollbar(self.list_container, orient="vertical", command=self.tree_results.yview)
        sb_x = ttk.Scrollbar(self.list_container, orient="horizontal", command=self.tree_results.xview)
        self.tree_results.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.tree_results.pack(side="left", fill="both", expand=True)

        # ── CONTENEDOR QC PROGRESO ──
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
        if value == "Paquete diario (QC)":
            self.frame_files_input.pack_forget()
            self.frame_folders_input.pack(fill="x")
            self.btn_execute_compare.configure(text="EJECUTAR COMPARACIÓN DE PAQUETES (QC)")
            
            self.metrics_bar.pack_forget()
            self.ind_extra_lbl.pack_forget()
            self.legend_bar.pack_forget()
            self.filters_bar.pack_forget()
            self.list_container.pack_forget()
            
            self.qc_progress_container.pack(fill="both", expand=True, pady=4)
        else:
            self.frame_folders_input.pack_forget()
            self.frame_files_input.pack(fill="x")
            self.btn_execute_compare.configure(text="EJECUTAR COMPARACIÓN DE DATOS")
            
            self.qc_progress_container.pack_forget()
            
            self.metrics_bar.pack(fill="x", pady=4)
            self.legend_bar.pack(fill="x", pady=(4, 0))
            self.filters_bar.pack(fill="x", pady=6)
            self.list_container.pack(fill="both", expand=True, pady=4)
            
            # Cambiar títulos de métricas según tipo
            if value == "Individual XPS":
                self.m_d1.lbl_title.configure(text="DISPAROS ARCHIVO 1")
                self.m_d2.lbl_title.configure(text="DISPAROS ARCHIVO 2")
                self.m_diff.lbl_title.configure(text="CON DIFERENCIAS")
                self.m_miss.lbl_title.configure(text="DISPAROS FALTANTES")
                self.ent_search.configure(placeholder_text="Buscar disparo...")
            else:
                self.m_d1.lbl_title.configure(text="TOTAL DIFERENCIAS")
                self.m_d2.lbl_title.configure(text="PUNTOS NUEVOS")
                self.m_diff.lbl_title.configure(text="CAMBIOS COORD.")
                self.m_miss.lbl_title.configure(text="PUNTOS ELIMINADOS")
                self.ent_search.configure(placeholder_text="Buscar línea/punto...")

    def _auto_detect_file_type(self, path):
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

    def _on_qc_add_folder(self, path=None):
        if not path:
            path = filedialog.askdirectory(title="Selecciona la carpeta diaria del paquete sísmico")
        if path:
            # Validar que contenga algún archivo sísmico (.rps, .sps, .xps)
            archivos = os.listdir(path)
            valid = False
            for f in archivos:
                ext = os.path.splitext(f)[1].lower()
                if ext in ['.rps', '.rcp', '.sps', '.xps']:
                    valid = True
                    break
            
            if not valid:
                messagebox.showwarning(
                    "Carpeta inválida",
                    f"La carpeta seleccionada:\n{path}\nno contiene archivos de adquisición válidos (.rps, .sps, .xps)."
                )
                self.qc_folder_selector.entry_path.delete(0, tk.END)
                return
                
            self.folders_list.add_folder(path)

    def _on_qc_clear_folders(self):
        self.folders_list.clear()

    # ──────────────────────────────────────────────────────────────────────────
    # PANEL 3: ANALIZADOR BOOM BOX (MULTIPLE ARCHIVO)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_screen_boombox(self):
        f = self.frames["boombox"]
        
        # Encabezado
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        lbl_title = ctk.CTkLabel(header, text="ANALIZADOR DE LOGS BOOM BOX (LOTES) 💥", font=FONT_H1)
        lbl_title.pack(anchor="w")
        lbl_desc = ctk.CTkLabel(header, text="Módulo de procesamiento por lotes para extracción de metadatos de múltiples logs de Sercel Boom Box.", font=FONT_SM, text_color=COLORS["muted_light"])
        lbl_desc.pack(anchor="w")
        
        # Tarjeta principal
        card = ctk.CTkFrame(f, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        card.pack(fill="both", expand=True, pady=5)
        
        tk.Label(card, text="COLA DE ARCHIVOS LOG DE BOOM BOX", font=FONT_BOLD, bg=COLORS["surface_light"], fg=COLORS["accent"]).pack(anchor="w", padx=25, pady=(20, 5))
        
        # Contenedor de lista
        list_controls = ctk.CTkFrame(card, fg_color="transparent")
        list_controls.pack(fill="both", expand=True, padx=25, pady=10)
        
        btn_box = ctk.CTkFrame(list_controls, fg_color="transparent")
        btn_box.pack(side="left", fill="y", padx=(0, 15))
        
        icon_f = crear_icono_diseno("file", "#FFFFFF")
        btn_add = ctk.CTkButton(btn_box, text=" Agregar Archivos Log", image=icon_f, font=FONT_BOLD, 
                                fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                width=180, height=34, command=self._on_boombox_add_files)
        btn_add.pack(pady=3)
        
        btn_clr = ctk.CTkButton(btn_box, text=" Limpiar Lista completa", font=FONT_BOLD,
                                fg_color=COLORS["bg_light"], text_color=COLORS["text_light"], hover_color=COLORS["border_light"],
                                width=180, height=34, command=self._on_boombox_clear_files)
        btn_clr.pack(pady=3)
        
        self.boombox_files_list = CTkPathList(list_controls, placeholder="No hay archivos logs de Boom Box agregados a la cola.", height=200)
        self.boombox_files_list.pack(side="left", fill="both", expand=True)

        tk.Frame(card, bg=COLORS["border_light"], height=1).pack(fill="x", padx=25, pady=15)

        # Acción y Progreso
        action_f = ctk.CTkFrame(card, fg_color="transparent")
        action_f.pack(fill="x", padx=25, pady=(5, 20))
        
        self.btn_run_boombox = ctk.CTkButton(action_f, text="EJECUTAR ANÁLISIS DE LOGS", font=FONT_H2, 
                                             fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"],
                                             width=300, height=44, command=self._on_execute_boombox_analysis)
        self.btn_run_boombox.pack(side="left")
        
        self.progress_boombox = ttk.Progressbar(action_f, mode='determinate', length=250)
        self.progress_boombox.pack(side="left", padx=20)
        
        self.lbl_estado_boombox = ctk.CTkLabel(action_f, text="Esperando inicio...", font=FONT_SM, text_color=COLORS["muted_light"])
        self.lbl_estado_boombox.pack(side="left")

    def _on_boombox_add_files(self):
        paths = filedialog.askopenfilenames(
            title="Seleccionar archivos log de Boom Box",
            filetypes=[("Todos los archivos", "*.*")]
        )
        if paths:
            for p in paths:
                self.boombox_files_list.add_path(p)

    def _on_boombox_clear_files(self):
        self.boombox_files_list.clear()

    def _on_execute_boombox_analysis(self):
        files = self.boombox_files_list.paths
        if not files:
            messagebox.showwarning("Advertencia", "Selecciona al menos un archivo log de Boom Box para analizar.")
            return

        self.btn_run_boombox.configure(state="disabled")
        self.progress_boombox['value'] = 0
        self.lbl_estado_boombox.configure(text="Procesando archivos...")

        # Guardar reporte consolidado
        default_name = "Reporte_BoomBox_Consolidado.xlsx"
        out_path = filedialog.asksaveasfilename(
            title="Guardar reporte Excel consolidado",
            defaultextension=".xlsx",
            filetypes=[("Archivo Excel (*.xlsx)", "*.xlsx")],
            initialfile=default_name
        )
        if not out_path:
            self.btn_run_boombox.configure(state="normal")
            return

        progreso = Progreso(self.root, self.progress_boombox, self.lbl_estado_boombox)

        def tarea():
            try:
                from core.boom_box_parser import parse_multiple_boom_box_logs, export_multiple_boom_box_xlsx
                
                progreso.actualizar(10, "Cargando archivos logs...")
                results = parse_multiple_boom_box_logs(files)
                
                if not results:
                    self.root.after(0, lambda: messagebox.showwarning("Sin registros", "No se encontraron registros 'Created SP...' válidos en los archivos seleccionados."))
                    self.root.after(0, self._finalizar_boombox_error)
                    return
                    
                progreso.actualizar(50, "Exportando y aplicando estilos a Excel...")
                final_path = export_multiple_boom_box_xlsx(results, out_path)
                
                self.root.after(0, functools.partial(self._finalizar_boombox_ok, final_path))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.root.after(0, functools.partial(self._finalizar_boombox_error_msg, str(e)))

        threading.Thread(target=tarea, daemon=True).start()

    def _finalizar_boombox_ok(self, final_path):
        self.btn_run_boombox.configure(state="normal")
        self.progress_boombox['value'] = 100
        self.lbl_estado_boombox.configure(text="Proceso completado.", text_color=COLORS["ok_txt"])
        messagebox.showinfo("Éxito", f"Los logs de Boom Box han sido procesados y guardados correctamente en:\n{final_path}")
        self.recargar_dashboard_kpis()

    def _finalizar_boombox_error(self):
        self.btn_run_boombox.configure(state="normal")
        self.progress_boombox['value'] = 0
        self.lbl_estado_boombox.configure(text="Sin registros extraídos.", text_color=COLORS["red_accent"])

    def _finalizar_boombox_error_msg(self, msg):
        self.btn_run_boombox.configure(state="normal")
        self.progress_boombox['value'] = 0
        self.lbl_estado_boombox.configure(text="Error de análisis.", text_color=COLORS["red_accent"])
        messagebox.showerror("Error", f"Ocurrió un error al procesar los archivos: {msg}")


    # ──────────────────────────────────────────────────────────────────────────
    # PANEL 4: GENERACIÓN DE MAPAS
    # ──────────────────────────────────────────────────────────────────────────
    def _build_screen_mapas(self):
        f = self.frames["mapas"]
        
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        lbl_title = ctk.CTkLabel(header, text="GENERACIÓN DE MAPAS DE ADQUISICIÓN 采集地图生成 ", font=FONT_H1)
        lbl_title.pack(anchor="w")
        lbl_desc = ctk.CTkLabel(header, text="Mapeo geográfico de los datos cargados y proyección en coordenadas UTM.", font=FONT_SM, text_color=COLORS["muted_light"])
        lbl_desc.pack(anchor="w")
        
        card = ctk.CTkFrame(f, corner_radius=10, border_width=1, fg_color=COLORS["surface_light"], border_color=COLORS["border_light"])
        card.pack(fill="both", expand=True, pady=5)
        
        tk.Label(card, text="1. SELECCIÓN DE ARCHIVOS DEL PROYECTO", font=FONT_BOLD, bg=COLORS["surface_light"], fg=COLORS["accent"]).pack(anchor="w", padx=25, pady=(20, 5))
        
        self.map_f_rps = CTkFileSelector(card, "Archivo RPS (Receptores)")
        self.map_f_rps.pack(fill="x", padx=25, pady=4)
        
        self.map_f_sps = CTkFileSelector(card, "Archivo SPS (Fuentes)")
        self.map_f_sps.pack(fill="x", padx=25, pady=4)
        
        self.map_f_xps = CTkFileSelector(card, "Archivo XPS (Relaciones de Disparo)")
        self.map_f_xps.pack(fill="x", padx=25, pady=4)

        tk.Frame(card, bg=COLORS["border_light"], height=1).pack(fill="x", padx=25, pady=15)

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
    # PANEL 5: CONFIGURACIÓN Y TEMAS
    # ──────────────────────────────────────────────────────────────────────────
    def _build_screen_config(self):
        f = self.frames["config"]
        
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        
        lbl_title = ctk.CTkLabel(header, text="CONFIGURACIÓN GLOBAL Y TEMAS 全局配置与主题", font=FONT_H1)
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

        btn_reset = ctk.CTkButton(card, text="Restablecer Configuración de Fábrica", font=FONT_BOLD, fg_color="#EF4444", hover_color="#DC2626", text_color="white", height=36, command=self._on_reset_settings)
        btn_reset.pack(anchor="w", padx=25, pady=25)

    def _on_theme_changed(self, theme):
        ctk.set_appearance_mode(theme)
        self.root.update()
        
        self.folders_list._update_colors()
        self.folders_list.render()
        
        if hasattr(self, "boombox_files_list"):
            self.boombox_files_list._update_colors()
            self.boombox_files_list.render()
        
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            self.main_area.configure(fg_color=COLORS["bg_dark"])
            self.sidebar.configure(fg_color=COLORS["sidebar_dark"])
            self.card_lmaps.update_theme()
            self.card_lcomp.update_theme()
            self.card_lfiles.update_theme()
            self.m_d1.update_theme()
            self.m_d2.update_theme()
            self.m_diff.update_theme()
            self.m_miss.update_theme()
            
            self.tree_style.configure("Treeview", 
                                      background="#1E293B", 
                                      foreground="#F8FAFC", 
                                      fieldbackground="#1E293B")
            self.tree_style.configure("Treeview.Heading", 
                                      background="#0F172A", 
                                      foreground="#FFFFFF")
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
            
            self.tree_style.configure("Treeview", 
                                      background="#FFFFFF", 
                                      foreground="#0F172A", 
                                      fieldbackground="#FFFFFF")
            self.tree_style.configure("Treeview.Heading", 
                                      background="#0F2942", 
                                      foreground="#FFFFFF")

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
    def validar_archivo_contenido(self, path, modo):
        ext = os.path.splitext(path)[1].lower()
        if modo == "Individual SPS":
            if ext not in [".sps", ".txt"]:
                return False, "El archivo no tiene la extensión .sps o .txt requerida para SPS."
            tipo_letra = "S"
        elif modo == "Individual RPS":
            if ext not in [".rps", ".rcp", ".txt"]:
                return False, "El archivo no tiene la extensión .rps, .rcp o .txt requerida para RPS."
            tipo_letra = "R"
        elif modo == "Individual XPS":
            if ext not in [".xps", ".txt"]:
                return False, "El archivo no tiene la extensión .xps o .txt requerida para XPS."
            tipo_letra = "X"
        else:
            return True, ""

        try:
            with open(path, "r", errors="replace") as f:
                for _ in range(50):
                    line = f.readline()
                    if not line: break
                    line = line.strip()
                    if not line: continue
                    if line.startswith("H"):
                        continue
                    if line.startswith(tipo_letra):
                        return True, ""
            
            return False, f"El archivo no contiene registros válidos que comiencen con la letra '{tipo_letra}' correspondiente al modo '{modo}'."
        except Exception as e:
            return False, f"Error al leer el archivo: {str(e)}"

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
            
        else: # Comparación Individual
            p1 = self.ind_f1.get()
            p2 = self.ind_f2.get()
            if not p1 or not p2:
                messagebox.showwarning("Faltan archivos", "Selecciona los dos archivos antes de comparar.")
                return
                
            # Validar archivos
            ok1, msg1 = self.validar_archivo_contenido(p1, mode)
            if not ok1:
                messagebox.showwarning("Archivo 1 incorrecto", f"Archivo 1 inválido:\n{msg1}")
                return
                
            ok2, msg2 = self.validar_archivo_contenido(p2, mode)
            if not ok2:
                messagebox.showwarning("Archivo 2 incorrecto", f"Archivo 2 inválido:\n{msg2}")
                return
                
            self.lbl_bottom_status.configure(text="Comparando archivos...")
            self.root.update()
            
            try:
                if mode == "Individual XPS":
                    self._df_result = None
                    self._result = run_comparison(p1, p2)
                else: # SPS o RPS
                    self._result = None
                    df1 = leer_sps_rps(p1, 'S' if mode == "Individual SPS" else 'R')
                    df2 = leer_sps_rps(p2, 'S' if mode == "Individual SPS" else 'R')
                    self._df_result = comparar_sin_merge(df1, df2, ['linea', 'punto'], ['x', 'y', 'elevacion'])
                
                self._render_individual_results()
            except Exception as ex:
                import traceback
                traceback.print_exc()
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
        mode = self.segmented_selector.get()
        
        # Limpiar listado de filas del Treeview
        self.tree_results.delete(*self.tree_results.get_children())
        
        if mode == "Individual XPS":
            r = self._result
            if not r:
                return
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

            # Configurar columnas del Treeview para XPS
            self.tree_results.configure(columns=("disparo", "archivo1", "archivo2", "status"), show="headings")
            self.tree_results.heading("disparo", text="Disparo / Línea")
            self.tree_results.heading("archivo1", text=f"Archivo 1 (Base): {r['name1']}")
            self.tree_results.heading("archivo2", text=f"Archivo 2 (Nuevo): {r['name2']}")
            self.tree_results.heading("status", text="Estado")
            
            self.tree_results.column("disparo", width=180, anchor="w")
            self.tree_results.column("archivo1", width=250, anchor="center")
            self.tree_results.column("archivo2", width=250, anchor="center")
            self.tree_results.column("status", width=150, anchor="center")

            # Aplicar filtro
            filt   = self.filter_val_ind.get()
            search = self.search_val_ind.get().strip().lower()

            for shot in r["results"]:
                s_status = shot["status"]
                
                # Filtrar
                show = True
                if filt == "diff"    and s_status != "diff":              show = False
                if filt == "ok"      and s_status != "ok":                show = False
                if filt == "missing" and s_status not in ("only1","only2"): show = False
                if show and search and search not in shot["disparo"].lower():    show = False
                
                if not show:
                    continue

                # Formatear filas parent
                a1_text = ""
                a2_text = ""
                status_text = ""
                tag = ""
                
                if s_status == "ok":
                    a1_text = f"{shot.get('n_lineas1', '—')} líneas"
                    a2_text = f"{shot.get('n_lineas2', '—')} líneas"
                    status_text = "Idéntico"
                    tag = "ok"
                elif s_status == "only1":
                    a1_text = f"{shot.get('n_lineas1', '—')} líneas (presente)"
                    a2_text = "—"
                    status_text = "Solo en Archivo 1"
                    tag = "only1"
                elif s_status == "only2":
                    a1_text = "—"
                    a2_text = f"{shot.get('n_lineas2', '—')} líneas (presente)"
                    status_text = "Solo en Archivo 2"
                    tag = "only2"
                else: # diff
                    nd = sum(1 for lr in shot["lineas"] if lr["status"] != "ok")
                    nk = sum(1 for lr in shot["lineas"] if lr["status"] == "ok")
                    a1_text = f"{shot.get('n_lineas1', '—')} líneas ({nk} ok · {nd} difs)"
                    a2_text = f"{shot.get('n_lineas2', '—')} líneas ({nk} ok · {nd} difs)"
                    status_text = "Con diferencias"
                    tag = "diff"

                item_id = self.tree_results.insert("", "end", values=(shot["disparo"], a1_text, a2_text, status_text), tags=(tag,))
                
                # Insertar detalles (hijos) si es con diferencias
                if s_status == "diff":
                    for lr in shot["lineas"]:
                        lr_status = lr["status"]
                        child_a1 = ""
                        child_a2 = ""
                        
                        def fmt_estacas(lst):
                            if not lst: return "—"
                            def _n(x): return float(x) if x.lstrip("-").replace(".","").isdigit() else 0
                            ini = min((e[0] for e in lst), key=_n)
                            fin = max((e[1] for e in lst), key=_n)
                            return f"{ini} → {fin}" if len(lst) == 1 else f"{ini} → {fin}  ({len(lst)} rangos)"

                        if lr_status == "only2":
                            child_a1 = "—"
                            child_a2 = fmt_estacas(lr["estacas2"])
                        elif lr_status == "only1":
                            child_a1 = fmt_estacas(lr["estacas1"])
                            child_a2 = "—"
                        else:
                            child_a1 = fmt_estacas(lr["estacas1"])
                            child_a2 = fmt_estacas(lr["estacas2"])
                            
                        child_tag = "only2" if lr_status == "only2" else ("only1" if lr_status == "only1" else ("ok" if lr_status == "ok" else "diff"))
                        child_status = "Línea Solo en Archivo 2" if lr_status == "only2" else ("Línea Solo en Archivo 1" if lr_status == "only1" else ("Línea Idéntica" if lr_status == "ok" else "Diferencias en Estacas"))
                        
                        self.tree_results.insert(item_id, "end", values=(f"  Línea {lr['linea']}", child_a1, child_a2, child_status), tags=(child_tag,))

            total = len(r["results"])
            ok    = len(r["disparos_ok"])
            self.lbl_bottom_status.configure(
                text=(f"✔  {total} disparos  ·  {ok} idénticos  ·  "
                      f"{ndiff} con diferencias  ·  {nmiss} faltantes"))

        else: # SPS o RPS
            df_diff = self._df_result
            if df_diff is None:
                return
                
            n_nuevos = len(df_diff[df_diff['Tipo de Cambio'] == 'Nuevo'])
            n_elim = len(df_diff[df_diff['Tipo de Cambio'] == 'Eliminado'])
            ndiff = len(df_diff[df_diff['Tipo de Cambio'] == 'Cambio de Coordenada'])
            total = len(df_diff)

            self.m_d1.set(total)
            self.m_d2.set(n_nuevos, COLORS["diff_txt"] if n_nuevos else None)
            self.m_diff.set(ndiff, COLORS["diff_txt"] if ndiff else COLORS["ok_txt"])
            self.m_miss.set(n_elim, COLORS["only1_txt"] if n_elim else COLORS["ok_txt"])

            # Configurar columnas del Treeview para SPS/RPS
            self.tree_results.configure(columns=("linea", "punto", "tipo_cambio", "detalles"), show="headings")
            self.tree_results.heading("linea", text="Línea")
            self.tree_results.heading("punto", text="Punto")
            self.tree_results.heading("tipo_cambio", text="Tipo de Cambio")
            self.tree_results.heading("detalles", text="Detalles de Coordenadas (X, Y, Z)")
            
            self.tree_results.column("linea", width=120, anchor="center")
            self.tree_results.column("punto", width=120, anchor="center")
            self.tree_results.column("tipo_cambio", width=180, anchor="center")
            self.tree_results.column("detalles", width=450, anchor="w")

            filt   = self.filter_val_ind.get()
            search = self.search_val_ind.get().strip().lower()

            for _, row in df_diff.iterrows():
                tipo_cambio = row['Tipo de Cambio']
                
                show = True
                if filt == "diff"    and tipo_cambio != "Cambio de Coordenada": show = False
                if filt == "ok"      and tipo_cambio != "":                     show = False
                if filt == "missing" and tipo_cambio not in ("Nuevo", "Eliminado"): show = False
                
                search_text = f"{row.get('linea', '')} {row.get('punto', '')}".lower()
                if show and search and search not in search_text:
                    show = False
                    
                if not show:
                    continue

                tag = "diff" if tipo_cambio == "Cambio de Coordenada" else ("only1" if tipo_cambio == "Eliminado" else "only2")
                detalles_str = format_diff_row(row, mode)
                
                self.tree_results.insert("", "end", values=(row['linea'], row['punto'], tipo_cambio, detalles_str), tags=(tag,))

            self.lbl_bottom_status.configure(
                text=f"✔  {total} diferencias encontradas  ·  {n_nuevos} nuevos  ·  {n_elim} eliminados  ·  {ndiff} cambios coord.")

    def _apply_individual_filter(self):
        self._render_individual_results()

    def _on_export_excel_individual(self):
        mode = self.segmented_selector.get()
        if mode == "Individual XPS":
            if not self._result:
                messagebox.showwarning("Sin datos", "Ejecuta una comparación primero.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile="comparativa_xps.xlsx")
            if path:
                try:
                    export_xlsx(self._result, path)
                    self.lbl_bottom_status.configure(text=f"Reporte Excel guardado: {os.path.basename(path)}")
                    messagebox.showinfo("Exportación Exitosa", f"El archivo Excel ha sido generado con éxito:\n{path}")
                except ImportError as e:
                    messagebox.showerror("Módulo faltante", str(e))
        else: # SPS o RPS
            if self._df_result is None:
                messagebox.showwarning("Sin datos", "Ejecuta una comparación primero.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile=f"comparativa_{mode.split()[-1].lower()}.xlsx")
            if path:
                try:
                    with pd.ExcelWriter(path, engine='openpyxl') as writer:
                        self._df_result.to_excel(writer, sheet_name="Diferencias", index=False)
                        ws = writer.sheets["Diferencias"]
                        aplicar_estilo_hoja(ws, "0F2942")
                    self.lbl_bottom_status.configure(text=f"Reporte Excel guardado: {os.path.basename(path)}")
                    messagebox.showinfo("Exportación Exitosa", f"El archivo Excel ha sido generado con éxito:\n{path}")
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo guardar el archivo Excel: {str(e)}")

    def _on_export_txt_completo(self):
        mode = self.segmented_selector.get()
        if mode == "Individual XPS":
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
        else:
            messagebox.showinfo("Información", "La exportación completa de TXT solo está disponible para comparaciones estructurales XPS.")

    def _on_export_txt_diff(self):
        mode = self.segmented_selector.get()
        if mode == "Individual XPS":
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
        else:
            if self._df_result is None:
                messagebox.showwarning("Sin datos", "Ejecuta una comparación primero.")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Texto", "*.txt")],
                initialfile=f"diferencias_{mode.split()[-1].lower()}.txt")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"REPORTE DE DIFERENCIAS {mode.split()[-1]}\n")
                    f.write("=" * 72 + "\n\n")
                    for _, row in self._df_result.iterrows():
                        f.write(f"Línea {row['linea']}  Punto {row['punto']}: {row['Tipo de Cambio']}\n")
                        f.write(f"  {format_diff_row(row, mode)}\n\n")
                self.lbl_bottom_status.configure(text=f"Reporte de diferencias guardado: {os.path.basename(path)}")