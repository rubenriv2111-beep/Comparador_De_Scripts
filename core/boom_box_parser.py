# -*- coding: utf-8 -*-
import re
import os
import pandas as pd
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from core.qc_comparator import aplicar_estilo_hoja

def parse_boom_box_log(file_path):
    """
    Parsea un archivo log de Boom Box y extrae los registros de SP, FFID, Chans, etc.
    Retorna el nombre del Script y un DataFrame con los registros.
    """
    script_name = "BoomBox_Report"
    records = []
    
    # Regex para extraer el script name del bloque:
    # file_name: "/export/home/.../SCRIPT B-VI (Z-V-S) 010626/SCRIPT B-VI (Z-V-S) 010626/Script.xps"
    re_script = re.compile(r'file_name\s*:\s*"([^"]+)"')
    
    # Regex para extraer registros:
    # Created SP 10585.00:1641.00,FFID 106213 starting Mon Jun 1 14:07:56 2026 0us (GPS TB 1464358094000000) with 49490 chans
    re_record = re.compile(
        r'Created\s+SP\s+([\d\.]+):[\d\.]+,?\s*FFID\s+(\d+)\s+starting\s+(.*?)\s+\d+us\s+\(GPS\s+TB\s+(\d+)\)\s+with\s+(\d+)\s+chans'
    )
    
    # Regex alternativa por si el formato varía ligeramente (e.g. espacios o comas)
    re_record_alt = re.compile(
        r'Created\s+SP\s+([\d\.]+).*?FFID\s+(\d+).*?starting\s+(.*?)\s+\d+us.*?GPS\s+TB\s+(\d+).*?with\s+(\d+)\s+chans'
    )

    try:
        with open(file_path, "r", errors="replace") as f:
            content = f.read()
            
            # Buscar el nombre del script
            scripts_found = re_script.findall(content)
            for sf in scripts_found:
                dir_name = os.path.dirname(sf)
                folder_name = os.path.basename(dir_name)
                if folder_name and folder_name != "Script.xps":
                    script_name = folder_name
                    break
            
            # Fallback en caso de que no venga en file_name pero esté en la carga de scripts
            if script_name == "BoomBox_Report":
                re_sps_load = re.compile(r'SPS Scripts based on\s+([^\s]+)\s+loaded')
                load_found = re_sps_load.findall(content)
                for lf in load_found:
                    dir_name = os.path.dirname(lf)
                    folder_name = os.path.basename(dir_name)
                    if folder_name:
                        script_name = folder_name
                        break
            
            # Procesar línea por línea
            f.seek(0)
            for line in f:
                match = re_record.search(line)
                if not match:
                    match = re_record_alt.search(line)
                
                if match:
                    sp = match.group(1)
                    ffid = match.group(2)
                    fecha_hora = match.group(3)
                    gps_tb = match.group(4)
                    chans = match.group(5)
                    
                    records.append({
                        "SP": sp,
                        "FFID": ffid,
                        "Chans": chans,
                        "Fecha/Hora": fecha_hora,
                        "GPS TB": gps_tb
                    })
    except Exception as e:
        print(f"Error parsing Boom Box log: {e}")
        
    df = pd.DataFrame(records)
    return script_name, df

def export_boom_box_xlsx(df, script_name, output_path):
    """
    Exporta el DataFrame de Boom Box a un archivo Excel estilizado con la hoja nombrada como el Script.
    """
    sheet_name = script_name[:31] # Límite de openpyxl de 31 caracteres
    
    # Si el archivo ya existe y está abierto, buscar alternativa de nombre
    base, ext = os.path.splitext(output_path)
    contador = 1
    nombre_final = output_path
    while True:
        try:
            with pd.ExcelWriter(nombre_final, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                ws = writer.sheets[sheet_name]
                aplicar_estilo_hoja(ws, "0F2942")
            break
        except PermissionError:
            nombre_final = f"{base}_{contador}{ext}"
            contador += 1
            
    return nombre_final

def parse_multiple_boom_box_logs(file_paths):
    """
    Parsea múltiples archivos log de Boom Box y retorna un diccionario de {script_name: DataFrame}.
    """
    results = {}
    for path in file_paths:
        script_name, df = parse_boom_box_log(path)
        if not df.empty:
            # Evitar colisión de nombres de hoja de Excel
            base_name = script_name
            counter = 1
            while script_name in results:
                script_name = f"{base_name}_{counter}"
                counter += 1
            results[script_name] = df
    return results

def export_multiple_boom_box_xlsx(results, output_path):
    """
    Exporta un diccionario de {script_name: DataFrame} a un único archivo Excel,
    creando una hoja por cada script y aplicando los estilos de SINOPEC.
    """
    base, ext = os.path.splitext(output_path)
    contador = 1
    nombre_final = output_path
    while True:
        try:
            with pd.ExcelWriter(nombre_final, engine='openpyxl') as writer:
                for script_name, df in results.items():
                    sheet_name = script_name[:31]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    ws = writer.sheets[sheet_name]
                    aplicar_estilo_hoja(ws, "0F2942")
            break
        except PermissionError:
            nombre_final = f"{base}_{contador}{ext}"
            contador += 1
            if contador > 100:
                raise RuntimeError("No se puede escribir el archivo Excel. Cierra el archivo abierto.")
    return nombre_final

