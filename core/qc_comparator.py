# -*- coding: utf-8 -*-

import pandas as pd
import os
import re
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from core.lectores import leer_sps_rps, detectar_tipo_sps_rps, ENCABEZADOS_RPS, ENCABEZADOS_SPS, ENCABEZADOS_XPS, COLUMNAS_RPS, COLUMNAS_XPS, leer_xps_completo

def aplicar_estilo_hoja(ws, color_encabezado, es_diferencias=False):
    """Aplica diseño estético y legibilidad a la hoja usando openpyxl."""
    # Relleno del encabezado (color sólido)
    fill_encabezado = PatternFill(start_color=color_encabezado, end_color=color_encabezado, fill_type='solid')
    font_encabezado = Font(name='Segoe UI', size=11, bold=True, color='FFFFFF')
    align_encabezado = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # Formatear la primera fila (encabezado)
    ws.row_dimensions[1].height = 28
    for col_idx in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = fill_encabezado
        cell.font = font_encabezado
        cell.alignment = align_encabezado
        
    # Si la hoja tiene más de 15,000 filas, desactivamos el estilizado celda por celda
    # para evitar degradación de rendimiento y consumo masivo de memoria.
    limite_filas = 15000
    
    if ws.max_row <= limite_filas:
        # Relleno de filas alternas (cebreado muy tenue)
        fill_cebra = PatternFill(start_color='F9FAFB', end_color='F9FAFB', fill_type='solid')
        # Bordes inferiores finos para separar filas
        borde_inferior = Border(bottom=Side(style='thin', color='E0E0E0'))
        
        # Estilos para celdas de datos
        font_datos = Font(name='Segoe UI', size=10)
        
        # Formatear las filas de datos
        for row_idx in range(2, ws.max_row + 1):
            ws.row_dimensions[row_idx].height = 20
            usar_cebra = (row_idx % 2 == 0)
            
            # Si es la hoja de diferencias, pintamos según el Tipo de Cambio
            fill_fila_dif = None
            if es_diferencias:
                tipo_cambio_val = None
                for c_idx in range(1, ws.max_column + 1):
                    header_val = ws.cell(row=1, column=c_idx).value
                    if header_val == 'Tipo de Cambio':
                        tipo_cambio_val = ws.cell(row=row_idx, column=c_idx).value
                        break
                
                if tipo_cambio_val == 'Eliminado':
                    fill_fila_dif = PatternFill(start_color='FCE4D6', end_color='FCE4D6', fill_type='solid')  # Durazno claro
                elif tipo_cambio_val == 'Nuevo':
                    fill_fila_dif = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')  # Verde claro
                elif tipo_cambio_val == 'Cambio de Coordenada':
                    fill_fila_dif = PatternFill(start_color='FFF2CC', end_color='FFF2CC', fill_type='solid')  # Amarillo claro
            
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.font = font_datos
                cell.border = borde_inferior
                
                # Relleno
                if fill_fila_dif:
                    cell.fill = fill_fila_dif
                elif usar_cebra:
                    cell.fill = fill_cebra
                    
                # Alineación y formatos numéricos basados en el nombre de columna
                header_val = ws.cell(row=1, column=col_idx).value
                
                if header_val:
                    h_lower = str(header_val).lower()
                    if any(x in h_lower for x in ['coordenada x', 'x base', 'x nuevo', 'coordenada y', 'y base', 'y nuevo']):
                        cell.alignment = Alignment(horizontal='right', vertical='center')
                        cell.number_format = '0.0'
                    elif any(x in h_lower for x in ['elevación', 'elevacion']):
                        cell.alignment = Alignment(horizontal='right', vertical='center')
                        cell.number_format = '0.0'
                    elif any(x in h_lower for x in ['línea', 'linea', 'punto', 'desde', 'hasta', 'incremento', 'evento', 'reel', 'carrete', 'estático', 'estatico']):
                        cell.alignment = Alignment(horizontal='right', vertical='center')
                        cell.number_format = '0'
                    elif any(x in h_lower for x in ['tipo de cambio', 'paquete']):
                        cell.alignment = Alignment(horizontal='center', vertical='center')
                    else:
                        cell.alignment = Alignment(horizontal='left', vertical='center')
                else:
                    cell.alignment = Alignment(horizontal='left', vertical='center')
                    
    # Ajustar anchos de columna dinámicamente usando una muestra de las primeras 200 filas
    filas_muestra = min(ws.max_row, 200)
    for col_idx in range(1, ws.max_column + 1):
        max_len = 0
        col_letter = get_column_letter(col_idx)
        for row_idx in range(1, filas_muestra + 1):
            val = ws.cell(row=row_idx, column=col_idx).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)
        
    # Congelar fila superior
    ws.freeze_panes = 'A2'
    
    # Forzar cuadrícula visible
    ws.sheet_view.showGridLines = True

def comparar_carpetas(lista_carpetas, progreso=None):
    """
    Compara paquetes diarios a partir de una lista de carpetas.
    Cada carpeta debe contener archivos RPS, SPS y/o XPS.
    Retorna un dict con las diferencias y también guarda los datos originales en el Excel.
    """
    if progreso:
        progreso.actualizar(5, "Analizando carpetas...")
    
    carpetas_ordenadas = sorted(lista_carpetas, key=lambda x: os.path.basename(x))
    
    paquetes = {}
    for carpeta in carpetas_ordenadas:
        nombre = os.path.basename(carpeta)
        archivos = os.listdir(carpeta)
        rps_path = None
        sps_path = None
        xps_path = None
        
        # Primero buscar por extensión conocida
        for archivo in archivos:
            ruta_completa = os.path.join(carpeta, archivo)
            ext = os.path.splitext(archivo)[1].lower()
            if ext in ['.rps', '.rcp']:
                rps_path = ruta_completa
            elif ext == '.sps':
                sps_path = ruta_completa
            elif ext == '.xps':
                xps_path = ruta_completa
        
        # Si no se encontraron por extensión, buscar por contenido (archivos .txt o sin extensión)
        if not rps_path and not sps_path and not xps_path:
            for archivo in archivos:
                ruta_completa = os.path.join(carpeta, archivo)
                ext = os.path.splitext(archivo)[1].lower()
                if ext in ['.txt', '']:
                    tipo = detectar_tipo_sps_rps(ruta_completa)
                    if tipo == 'R' and not rps_path:
                        rps_path = ruta_completa
                    elif tipo == 'S' and not sps_path:
                        sps_path = ruta_completa
        
        # Leer archivos (siempre devuelven DataFrames con columnas estándar)
        df_rps = leer_sps_rps(rps_path, 'R') if rps_path else pd.DataFrame(columns=COLUMNAS_RPS)
        df_sps = leer_sps_rps(sps_path, 'S') if sps_path else pd.DataFrame(columns=COLUMNAS_RPS)
        
        # Leer XPS usando slicing exacto
        df_xps = leer_xps_completo(xps_path) if xps_path else pd.DataFrame(columns=COLUMNAS_XPS)
        
        paquetes[nombre] = {
            'carpeta': carpeta,
            'rps': df_rps,
            'sps': df_sps,
            'xps': df_xps,
            'archivos': {
                'rps': os.path.basename(rps_path) if rps_path else None,
                'sps': os.path.basename(sps_path) if sps_path else None,
                'xps': os.path.basename(xps_path) if xps_path else None
            }
        }
    
    if progreso:
        progreso.actualizar(30, f"Datos cargados de {len(paquetes)} paquetes.")
        for nombre, datos in paquetes.items():
            progreso.actualizar(32, f"  {nombre}: RPS={len(datos['rps'])}, SPS={len(datos['sps'])}, XPS={len(datos['xps'])}")
    
    # Comparar paquetes consecutivos
    diferencias = {'RPS': [], 'SPS': [], 'XPS': []}
    
    for i in range(len(carpetas_ordenadas)-1):
        nombre_base = carpetas_ordenadas[i]
        nombre_nuevo = carpetas_ordenadas[i+1]
        base_name = os.path.basename(nombre_base)
        new_name = os.path.basename(nombre_nuevo)
        
        if progreso:
            progreso.actualizar(35 + int(i/(len(carpetas_ordenadas)-1)*40), 
                              f"Comparando {base_name} vs {new_name}")
        
        # RPS
        df_base = paquetes[base_name]['rps']
        df_nuevo = paquetes[new_name]['rps']
        if not df_base.empty or not df_nuevo.empty:
            df_diff = comparar_sin_merge(df_base, df_nuevo, ['linea', 'punto'], ['x', 'y', 'elevacion'])
            if not df_diff.empty:
                df_diff.insert(0, 'Paquete Base', base_name)
                df_diff.insert(1, 'Paquete Nuevo', new_name)
                diferencias['RPS'].append(df_diff)
        
        # SPS
        df_base = paquetes[base_name]['sps']
        df_nuevo = paquetes[new_name]['sps']
        if not df_base.empty or not df_nuevo.empty:
            df_diff = comparar_sin_merge(df_base, df_nuevo, ['linea', 'punto'], ['x', 'y', 'elevacion'])
            if not df_diff.empty:
                df_diff.insert(0, 'Paquete Base', base_name)
                df_diff.insert(1, 'Paquete Nuevo', new_name)
                diferencias['SPS'].append(df_diff)
        
        # XPS
        df_base = paquetes[base_name]['xps']
        df_nuevo = paquetes[new_name]['xps']
        if not df_base.empty or not df_nuevo.empty:
            df_diff = comparar_sin_merge(df_base, df_nuevo, 
                                             ['linea_f', 'punto_f', 'linea_r', 'desde', 'hasta'], None)
            if not df_diff.empty:
                df_diff.insert(0, 'Paquete Base', base_name)
                df_diff.insert(1, 'Paquete Nuevo', new_name)
                diferencias['XPS'].append(df_diff)
    
    # Combinar diferencias
    diferencias_final = {}
    for tipo in ['RPS', 'SPS', 'XPS']:
        if diferencias[tipo]:
            diferencias_final[tipo] = pd.concat(diferencias[tipo], ignore_index=True)
    
    if progreso:
        progreso.actualizar(90, "Generando Excel con datos originales y diferencias...")
    
    # Exportar a Excel incluyendo datos originales con encabezados descriptivos
    exportar_excel_completo(paquetes, diferencias_final)
    
    return {'diferencias': diferencias_final, 'paquetes': paquetes}

def comparar_sin_merge(df_base, df_nuevo, key_cols, coord_cols=None):
    """
    Compara dos DataFrames sin usar pandas.merge (solo diccionarios).
    """
    if df_base.empty and df_nuevo.empty:
        return pd.DataFrame()
    
    # Asegurar columnas clave
    for col in key_cols:
        if col not in df_base.columns:
            df_base[col] = ''
        if col not in df_nuevo.columns:
            df_nuevo[col] = ''
    
    # Convertir a listas de diccionarios
    base_records = df_base.to_dict('records')
    new_records = df_nuevo.to_dict('records')
    
    # Crear diccionarios clave -> fila completa
    base_dict = {}
    for rec in base_records:
        key = tuple(str(rec.get(col, '')) for col in key_cols)
        base_dict[key] = rec
    
    new_dict = {}
    for rec in new_records:
        key = tuple(str(rec.get(col, '')) for col in key_cols)
        new_dict[key] = rec
    
    base_keys = set(base_dict.keys())
    new_keys = set(new_dict.keys())
    
    eliminados = base_keys - new_keys
    nuevos = new_keys - base_keys
    comunes = base_keys & new_keys
    
    diferencias = []
    
    # Procesar eliminados
    for key in eliminados:
        fila = base_dict[key]
        dif = {col: fila.get(col, '') for col in key_cols}
        dif['Tipo de Cambio'] = 'Eliminado'
        if coord_cols:
            for col in coord_cols:
                if col in fila:
                    dif[col + '_base'] = fila[col]
        diferencias.append(dif)
    
    # Procesar nuevos
    for key in nuevos:
        fila = new_dict[key]
        dif = {col: fila.get(col, '') for col in key_cols}
        dif['Tipo de Cambio'] = 'Nuevo'
        if coord_cols:
            for col in coord_cols:
                if col in fila:
                    dif[col + '_nuevo'] = fila[col]
        diferencias.append(dif)
    
    # Procesar cambios de coordenadas
    if coord_cols and comunes:
        for key in comunes:
            fila_base = base_dict[key]
            fila_nuevo = new_dict[key]
            cambio = False
            for col in coord_cols:
                base_val = fila_base.get(col)
                nuevo_val = fila_nuevo.get(col)
                if pd.isna(base_val) and pd.isna(nuevo_val):
                    continue
                if base_val != nuevo_val:
                    cambio = True
                    break
            if cambio:
                dif = {col: fila_base.get(col, '') for col in key_cols}
                dif['Tipo de Cambio'] = 'Cambio de Coordenada'
                for col in coord_cols:
                    dif[col + '_base'] = fila_base.get(col)
                    dif[col + '_nuevo'] = fila_nuevo.get(col)
                diferencias.append(dif)
    
    if not diferencias:
        return pd.DataFrame()
    return pd.DataFrame(diferencias)

def exportar_excel_completo(paquetes, diferencias, nombre_salida="comparacion_paquetes.xlsx"):
    """Exporta a Excel: resumen, datos originales de cada paquete (con encabezados descriptivos) y diferencias."""
    # Si el archivo está abierto, agregar un número al nombre
    base, ext = os.path.splitext(nombre_salida)
    contador = 1
    nombre_final = nombre_salida
    while True:
        try:
            with pd.ExcelWriter(nombre_final, engine='openpyxl') as writer:
                # Hoja de resumen
                resumen = []
                for nombre, datos in paquetes.items():
                    rps_len = len(datos['rps'])
                    sps_len = len(datos['sps'])
                    xps_len = len(datos['xps'])
                    
                    status_parts = []
                    if rps_len > 100000:
                        status_parts.append("RPS omitido (>100k)")
                    if sps_len > 100000:
                        status_parts.append("SPS omitido (>100k)")
                    if xps_len > 100000:
                        status_parts.append("XPS omitido (>100k)")
                        
                    export_status = "Completo" if not status_parts else "Parcial (" + ", ".join(status_parts) + ")"
                    
                    resumen.append({
                        'Paquete': nombre,
                        'Carpeta': datos['carpeta'],
                        'Archivo RPS': datos['archivos']['rps'] or 'No encontrado',
                        'Archivo SPS': datos['archivos']['sps'] or 'No encontrado',
                        'Archivo XPS': datos['archivos']['xps'] or 'No encontrado',
                        'Total RPS': rps_len,
                        'Total SPS': sps_len,
                        'Total XPS': xps_len,
                        'Exportación Originales': export_status
                    })
                df_resumen = pd.DataFrame(resumen)
                df_resumen.to_excel(writer, sheet_name='Resumen Paquetes', index=False)
                aplicar_estilo_hoja(writer.sheets['Resumen Paquetes'], '1F4E78')
                
                # Datos originales de cada paquete (por tipo) con encabezados descriptivos (si no exceden el límite de filas)
                for nombre, datos in paquetes.items():
                    limite_export = 100000
                    # RPS
                    if not datos['rps'].empty and len(datos['rps']) <= limite_export:
                        df = datos['rps'].copy()
                        df.rename(columns=ENCABEZADOS_RPS, inplace=True)
                        sheet_name = f"{nombre}_RPS"[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        aplicar_estilo_hoja(writer.sheets[sheet_name], '2F5597')
                    # SPS
                    if not datos['sps'].empty and len(datos['sps']) <= limite_export:
                        df = datos['sps'].copy()
                        df.rename(columns=ENCABEZADOS_SPS, inplace=True)
                        sheet_name = f"{nombre}_SPS"[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        aplicar_estilo_hoja(writer.sheets[sheet_name], '375623')
                    # XPS
                    if not datos['xps'].empty and len(datos['xps']) <= limite_export:
                        df = datos['xps'].copy()
                        df.rename(columns=ENCABEZADOS_XPS, inplace=True)
                        sheet_name = f"{nombre}_XPS"[:31]
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        aplicar_estilo_hoja(writer.sheets[sheet_name], '595959')
                
                # Hojas de diferencias con encabezados descriptivos
                for tipo, df in diferencias.items():
                    if tipo == 'RPS':
                        sheet_name = 'Diferencias RPS'
                        rename_map = {
                            'Paquete Base': 'Paquete Base',
                            'Paquete Nuevo': 'Paquete Nuevo',
                            'Tipo de Cambio': 'Tipo de Cambio',
                            'linea': 'Línea (2-17)',
                            'punto': 'Punto (18-25)',
                            'x_base': 'X Base (47-55)',
                            'x_nuevo': 'X Nuevo (47-55)',
                            'y_base': 'Y Base (56-65)',
                            'y_nuevo': 'Y Nuevo (56-65)',
                            'elevacion_base': 'Elevación Base (66-71)',
                            'elevacion_nuevo': 'Elevación Nuevo (66-71)'
                        }
                    elif tipo == 'SPS':
                        sheet_name = 'Diferencias SPS'
                        rename_map = {
                            'Paquete Base': 'Paquete Base',
                            'Paquete Nuevo': 'Paquete Nuevo',
                            'Tipo de Cambio': 'Tipo de Cambio',
                            'linea': 'Línea Fuente (2-17)',
                            'punto': 'Punto Fuente (18-25)',
                            'x_base': 'X Base (47-55)',
                            'x_nuevo': 'X Nuevo (47-55)',
                            'y_base': 'Y Base (56-65)',
                            'y_nuevo': 'Y Nuevo (56-65)',
                            'elevacion_base': 'Elevación Base (66-71)',
                            'elevacion_nuevo': 'Elevación Nuevo (66-71)'
                        }
                    elif tipo == 'XPS':
                        sheet_name = 'Diferencias XPS'
                        rename_map = {
                            'Paquete Base': 'Paquete Base',
                            'Paquete Nuevo': 'Paquete Nuevo',
                            'Tipo de Cambio': 'Tipo de Cambio',
                            'linea_f': 'Línea Fuente (18-27)',
                            'punto_f': 'Punto Fuente (28-37)',
                            'linea_r': 'Línea Receptora (48-57)',
                            'desde': 'Desde Geófono (58-67)',
                            'hasta': 'Hasta Geófono (68-77)'
                        }
                    else:
                        continue
                    
                    if not df.empty:
                        df_renamed = df.rename(columns=rename_map)
                        # Reordenar columnas
                        cols = ['Paquete Base', 'Paquete Nuevo', 'Tipo de Cambio'] + [c for c in df_renamed.columns if c not in ['Paquete Base', 'Paquete Nuevo', 'Tipo de Cambio']]
                        df_renamed = df_renamed[cols]
                        df_renamed.to_excel(writer, sheet_name=sheet_name, index=False)
                        aplicar_estilo_hoja(writer.sheets[sheet_name], 'C00000', es_diferencias=True)
                break  # salir del while si se pudo escribir
        except PermissionError:
            # Si está abierto, cambiar nombre
            nombre_final = f"{base}_{contador}{ext}"
            contador += 1
            if contador > 100:
                raise RuntimeError("No se puede escribir el archivo Excel. Cierra el archivo abierto.")
    
    print(f" Excel generado: {nombre_final}")