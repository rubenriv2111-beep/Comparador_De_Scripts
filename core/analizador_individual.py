# -*- coding: utf-8 -*-

import os
import time
import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from core.lectores import (
    leer_sps_rps, leer_xps_completo, detectar_tipo_sps_rps,
    ENCABEZADOS_RPS, ENCABEZADOS_SPS, ENCABEZADOS_XPS,
    COLUMNAS_RPS, COLUMNAS_XPS
)
from core.qc_comparator import aplicar_estilo_hoja

def detectar_tipo_archivo_individual(path):
    """
    Detecta automáticamente el tipo de archivo sísmico (SPS, RPS, XPS).
    """
    if not path or not os.path.exists(path):
        return "UNKNOWN"
        
    ext = os.path.splitext(path)[1].lower()
    
    if ext == ".sps":
        return "SPS"
    elif ext in [".rps", ".rcp"]:
        return "RPS"
    elif ext == ".xps":
        return "XPS"
        
    # Si es .txt o extensión desconocida, inspeccionar primeras 1000 líneas
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            count_r, count_s, count_x = 0, 0, 0
            for i, line in enumerate(f):
                if i > 1000:
                    break
                line_str = line.strip()
                if not line_str:
                    continue
                if line_str.startswith("R"):
                    count_r += 1
                elif line_str.startswith("S"):
                    count_s += 1
                elif line_str.startswith("X"):
                    count_x += 1
                    
            counts = {"RPS": count_r, "SPS": count_s, "XPS": count_x}
            max_type = max(counts, key=counts.get) # type: ignore
            if counts[max_type] > 0:
                return max_type
    except Exception:
        pass
        
    return "SPS" if ext == ".txt" else "UNKNOWN"


def analizar_archivo_individual(path, tipo_forzado=None):
    """
    Realiza un análisis estructurado de un solo archivo sísmico (SPS, RPS, XPS) sin comparar.
    Devuelve un diccionario estructurado con métricas, DataFrames, resumen por líneas y patrón de disparos XPS.
    """
    t_start = time.time()
    
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"El archivo especificado no existe: {path}")
        
    file_size_bytes = os.path.getsize(path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    file_name = os.path.basename(path)
    
    tipo = tipo_forzado if (tipo_forzado and tipo_forzado not in ["Automático", None]) else detectar_tipo_archivo_individual(path)
    
    total_lines = 0
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        for _ in f:
            total_lines += 1

    df_data = pd.DataFrame()
    stats = {}
    df_line_summary = pd.DataFrame()
    df_xps_pattern = pd.DataFrame()
    
    if tipo in ["SPS", "RPS"]:
        t_letter = "S" if tipo == "SPS" else "R"
        df_data = leer_sps_rps(path, t_letter)
        total_records = len(df_data)
        
        if not df_data.empty:
            total_puntos = total_records
            lineas_unicas = int(df_data['linea'].nunique())
            
            x_min, x_max, x_mean = float(df_data['x'].min()), float(df_data['x'].max()), float(df_data['x'].mean())
            y_min, y_max, y_mean = float(df_data['y'].min()), float(df_data['y'].max()), float(df_data['y'].mean())
            z_min, z_max, z_mean = float(df_data['elevacion'].min()), float(df_data['elevacion'].max()), float(df_data['elevacion'].mean())
            
            # Resumen Agregado por Línea
            df_line_summary = df_data.groupby('linea').agg(
                Puntos=('punto', 'count'),
                Punto_Inicio=('punto', 'min'),
                Punto_Fin=('punto', 'max'),
                X_Min=('x', 'min'),
                X_Max=('x', 'max'),
                Y_Min=('y', 'min'),
                Y_Max=('y', 'max'),
                Z_Promedio=('elevacion', 'mean')
            ).reset_index()
            
            stats = {
                "total_registros": total_records,
                "total_lineas": lineas_unicas,
                "x_min": x_min, "x_max": x_max, "x_range": x_max - x_min,
                "y_min": y_min, "y_max": y_max, "y_range": y_max - y_min,
                "z_min": z_min, "z_max": z_max, "z_mean": z_mean
            }
        else:
            stats = {
                "total_registros": 0, "total_lineas": 0,
                "x_min": 0, "x_max": 0, "x_range": 0,
                "y_min": 0, "y_max": 0, "y_range": 0,
                "z_min": 0, "z_max": 0, "z_mean": 0
            }
            
    elif tipo == "XPS":
        df_data = leer_xps_completo(path)
        total_records = len(df_data)
        
        if not df_data.empty:
            disparos_unicos = int(df_data[['linea_f', 'punto_f']].drop_duplicates().shape[0])
            lineas_f_unicas = int(df_data['linea_f'].nunique())
            lineas_r_unicas = int(df_data['linea_r'].nunique())
            
            canal_min = int(df_data['desde'].min())
            canal_max = int(df_data['hasta'].max())
            canales_prom = float((df_data['hasta'] - df_data['desde'] + 1).mean())
            
            # Resumen por Línea Fuente
            df_line_summary = df_data.groupby('linea_f').agg(
                Relaciones_X=('evento', 'count'),
                Disparos_Unicos=('punto_f', 'nunique'),
                Punto_F_Min=('punto_f', 'min'),
                Punto_F_Max=('punto_f', 'max'),
                Lineas_R_Conectadas=('linea_r', 'nunique')
            ).reset_index().rename(columns={'linea_f': 'linea'})
            
            # Tabla Única Patrón XPS por Disparo (Cálculo de Líneas Receptoras Activadas por evento de Canal 1 a Canal Final)
            df_xps_pattern = df_data.groupby(['linea_f', 'punto_f', 'evento'], sort=False).agg(
                Lineas_Receptoras_Activadas=('linea_r', 'nunique'),
                Primera_Linea_Receptora=('linea_r', 'first'),
                Ultima_Linea_Receptora=('linea_r', 'last'),
                Canal_Inicial=('desde', 'min'),
                Canal_Final=('hasta', 'max'),
                Primera_Estaca_Receptora=('punto_r', 'first'),
                Ultima_Estaca_Receptora=('estatico_r', 'last')
            ).reset_index().rename(columns={
                'linea_f': 'Línea Fuente',
                'punto_f': 'Punto Fuente',
                'evento': 'FFID / Evento',
                'Lineas_Receptoras_Activadas': 'Líneas R Activadas',
                'Primera_Linea_Receptora': 'Primera Línea R',
                'Ultima_Linea_Receptora': 'Última Línea R',
                'Canal_Inicial': 'Canal Inicial (1)',
                'Canal_Final': 'Canal Final',
                'Primera_Estaca_Receptora': 'Primera Estaca R',
                'Ultima_Estaca_Receptora': 'Última Estaca R'
            })
            
            stats = {
                "total_registros": total_records,
                "disparos_unicos": disparos_unicos,
                "lineas_f_unicas": lineas_f_unicas,
                "lineas_r_unicas": lineas_r_unicas,
                "canal_min": canal_min,
                "canal_max": canal_max,
                "canales_promedio": canales_prom
            }
        else:
            stats = {
                "total_registros": 0, "disparos_unicos": 0,
                "lineas_f_unicas": 0, "lineas_r_unicas": 0,
                "canal_min": 0, "canal_max": 0, "canales_promedio": 0
            }

    t_elapsed_ms = (time.time() - t_start) * 1000
    
    return {
        "file_name": file_name,
        "file_path": path,
        "file_size_mb": file_size_mb,
        "total_lines": total_lines,
        "tipo_detectado": tipo,
        "parse_time_ms": t_elapsed_ms,
        "stats": stats,
        "df_data": df_data,
        "df_line_summary": df_line_summary,
        "df_xps_pattern": df_xps_pattern
    }


def exportar_analisis_excel(res_analisis, path_salida):
    """
    Exporta el reporte del Análisis Individual a un libro Excel profesional.
    """
    file_name = res_analisis["file_name"]
    tipo = res_analisis["tipo_detectado"]
    stats = res_analisis["stats"]
    df_data = res_analisis["df_data"]
    df_summary = res_analisis["df_line_summary"]
    df_pattern = res_analisis.get("df_xps_pattern", pd.DataFrame())
    
    base, ext = os.path.splitext(path_salida)
    contador = 1
    final_path = path_salida
    
    while True:
        try:
            with pd.ExcelWriter(final_path, engine='openpyxl') as writer:
                # ── Hoja 1: Resumen y Métricas ──
                info_list = [
                    {"Métrica / Parámetro": "Nombre de Archivo", "Valor": file_name},
                    {"Métrica / Parámetro": "Ruta Completa", "Valor": res_analisis["file_path"]},
                    {"Métrica / Parámetro": "Formato de Archivo", "Valor": tipo},
                    {"Métrica / Parámetro": "Tamaño (MB)", "Valor": f"{res_analisis['file_size_mb']:.2f} MB"},
                    {"Métrica / Parámetro": "Total Líneas en Archivo", "Valor": res_analisis["total_lines"]},
                    {"Métrica / Parámetro": "Total Registros Procesados", "Valor": stats.get("total_registros", 0)},
                    {"Métrica / Parámetro": "Tiempo de Lectura", "Valor": f"{res_analisis['parse_time_ms']:.1f} ms"}
                ]
                
                if tipo in ["SPS", "RPS"]:
                    info_list.extend([
                        {"Métrica / Parámetro": "Total Líneas Únicas", "Valor": stats.get("total_lineas", 0)},
                        {"Métrica / Parámetro": "Rango Coord X (Este)", "Valor": f"{stats.get('x_min', 0):.1f} a {stats.get('x_max', 0):.1f}"},
                        {"Métrica / Parámetro": "Rango Coord Y (Norte)", "Valor": f"{stats.get('y_min', 0):.1f} a {stats.get('y_max', 0):.1f}"},
                        {"Métrica / Parámetro": "Rango Elevación Z", "Valor": f"{stats.get('z_min', 0):.1f}m a {stats.get('z_max', 0):.1f}m (Prom: {stats.get('z_mean', 0):.1f}m)"}
                    ])
                elif tipo == "XPS":
                    info_list.extend([
                        {"Métrica / Parámetro": "Disparos Únicos", "Valor": stats.get("disparos_unicos", 0)},
                        {"Métrica / Parámetro": "Líneas Fuentes Únicas", "Valor": stats.get("lineas_f_unicas", 0)},
                        {"Métrica / Parámetro": "Líneas Receptoras Únicas", "Valor": stats.get("lineas_r_unicas", 0)},
                        {"Métrica / Parámetro": "Rango de Canales", "Valor": f"{stats.get('canal_min', 0)} a {stats.get('canal_max', 0)} (Prom: {stats.get('canales_promedio', 0):.1f})"}
                    ])
                    
                df_info = pd.DataFrame(info_list)
                df_info.to_excel(writer, sheet_name="Resumen_Metricas", index=False)
                aplicar_estilo_hoja(writer.sheets["Resumen_Metricas"], "0F2942")
                
                # ── Hoja 2: Resumen por Línea ──
                if not df_summary.empty:
                    df_summary.to_excel(writer, sheet_name="Resumen_por_Linea", index=False)
                    aplicar_estilo_hoja(writer.sheets["Resumen_por_Linea"], "1F4E78")
                    
                # ── Hoja 3: Patrón de Disparos XPS (si es XPS) ──
                if tipo == "XPS" and not df_pattern.empty:
                    df_pattern.to_excel(writer, sheet_name="Patron_Disparos_XPS", index=False)
                    aplicar_estilo_hoja(writer.sheets["Patron_Disparos_XPS"], "005B94")
                    
                # ── Hoja 4: Datos Transcritos Completos ──
                if not df_data.empty and len(df_data) <= 1040000:
                    df_exp = df_data.copy()
                    if tipo == "RPS":
                        df_exp.rename(columns=ENCABEZADOS_RPS, inplace=True)
                    elif tipo == "SPS":
                        df_exp.rename(columns=ENCABEZADOS_SPS, inplace=True)
                    elif tipo == "XPS":
                        df_exp.rename(columns=ENCABEZADOS_XPS, inplace=True)
                        
                    sheet_data_name = f"Datos_{tipo}"[:31]
                    df_exp.to_excel(writer, sheet_name=sheet_data_name, index=False)
                    aplicar_estilo_hoja(writer.sheets[sheet_data_name], "2F5597")
                    
            break
        except PermissionError:
            final_path = f"{base}_{contador}{ext}"
            contador += 1
            if contador > 100:
                raise RuntimeError("No se puede escribir el archivo Excel. Asegúrate de cerrar el archivo si está abierto.")
                
    return final_path


def exportar_analisis_txt(res_analisis, path_salida):
    """
    Exporta el reporte del Análisis Individual a un archivo de texto ejecutivo.
    """
    with open(path_salida, "w", encoding="utf-8") as f:
        f.write("========================================================================\n")
        f.write(f"           SINOPEC GEOPHYSICAL - REPORTE DE ANÁLISIS INDIVIDUAL          \n")
        f.write("========================================================================\n\n")
        
        f.write(f"Archivo        : {res_analisis['file_name']}\n")
        f.write(f"Ruta           : {res_analisis['file_path']}\n")
        f.write(f"Formato        : {res_analisis['tipo_detectado']}\n")
        f.write(f"Tamaño         : {res_analisis['file_size_mb']:.2f} MB\n")
        f.write(f"Líneas Totales : {res_analisis['total_lines']}\n")
        f.write(f"Parse Time     : {res_analisis['parse_time_ms']:.1f} ms\n\n")
        
        f.write("------------------------------------------------------------------------\n")
        f.write("MÉTRICAS Y ESTADÍSTICAS CLAVE\n")
        f.write("------------------------------------------------------------------------\n")
        for k, v in res_analisis["stats"].items():
            f.write(f"  {k:<24} : {v}\n")
            
        f.write("\n========================================================================\n")
