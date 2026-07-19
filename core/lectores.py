# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import os
import re
from collections import defaultdict

# Definición de encabezados estándar SPS para RPS (con rangos de columnas)
ENCABEZADOS_RPS = {
    'linea': 'Línea (2-17)',
    'punto': 'Punto/Estaca (18-25)',
    'x': 'Coordenada X (Este) (47-55)',
    'y': 'Coordenada Y (Norte) (56-65)',
    'elevacion': 'Elevación Z (66-71)'
}

ENCABEZADOS_SPS = {
    'linea': 'Línea de Fuente (2-17)',
    'punto': 'Punto de Fuente (18-25)',
    'x': 'Coordenada X (Este) (47-55)',
    'y': 'Coordenada Y (Norte) (56-65)',
    'elevacion': 'Elevación Z (66-71)'
}

ENCABEZADOS_XPS = {
    'reel': 'Carrete/Reel (2-7)',
    'evento': 'Evento (8-17)',
    'linea_f': 'Línea Fuente (18-27)',
    'punto_f': 'Punto Fuente (28-35)',
    'punto_f_idx': 'Índice Fuente (36)',
    'desde': 'Desde Canal (37-41)',
    'hasta': 'Hasta Canal (42-47)',
    'incremento': 'Incremento (48)',
    'linea_r': 'Línea Receptora (49-59)',
    'punto_r': 'Punto Receptor (60-67)',
    'punto_r_idx': 'Índice Receptor (68)',
    'estatico_f': 'Estático Fuente (69-72)',
    'estatico_r': 'Estático Receptor (73-76)'
}

# Columnas estándar para SPS/RPS
COLUMNAS_RPS = ['linea', 'punto', 'x', 'y', 'elevacion']
COLUMNAS_XPS = [
    'reel', 'evento', 'linea_f', 'punto_f', 'punto_f_idx', 
    'desde', 'hasta', 'incremento', 'linea_r', 'punto_r', 
    'punto_r_idx', 'estatico_f', 'estatico_r'
]

def leer_sps_rps(ruta, tipo):
    """
    Lee archivo SPS/RPS usando slicing exacto por posiciones.
    Siempre devuelve un DataFrame con las columnas ['linea', 'punto', 'x', 'y', 'elevacion'].
    """
    if not ruta or not os.path.exists(ruta):
        return pd.DataFrame(columns=COLUMNAS_RPS)
    
    datos = []
    with open(ruta, 'r', encoding='utf-8-sig', errors='ignore') as f:
        for linea in f:
            linea_limpia = linea.rstrip('\n\r')
            if not linea_limpia or len(linea_limpia) < 71:
                continue
            
            # Saltar líneas de encabezado (empiezan con H)
            if linea_limpia.startswith('H'):
                continue
            
            # Saltar líneas que no empiezan con el tipo solicitado (R o S)
            if not linea_limpia.startswith(tipo):
                continue
            
            try:
                # Extraer por posiciones exactas (1-based → 0-based)
                # Línea: col 2-11 (índice 1-11)
                linea_str = linea_limpia[1:11].strip()
                # Punto/Estaca: col 12-21 (índice 11-21)
                punto_str = linea_limpia[11:21].strip()
                # Coordenada X: col 47-55 (índice 46-55)
                x_str = linea_limpia[46:55].strip()
                # Coordenada Y: col 56-65 (índice 55-65)
                y_str = linea_limpia[55:65].strip()
                # Elevación Z: col 66-71 (índice 65-71)
                elev_str = linea_limpia[65:71].strip()
                
                # Convertir de manera robusta
                try:
                    linea_val = int(float(linea_str)) if linea_str else 0
                except ValueError:
                    linea_val = 0
                    
                try:
                    punto_val = int(float(punto_str)) if punto_str else 0
                except ValueError:
                    punto_val = 0
                    
                try:
                    x_val = float(x_str) if x_str else 0.0
                except ValueError:
                    x_val = 0.0
                    
                try:
                    y_val = float(y_str) if y_str else 0.0
                except ValueError:
                    y_val = 0.0
                    
                try:
                    elev_val = float(elev_str) if elev_str else 0.0
                except ValueError:
                    elev_val = 0.0
                
                datos.append([linea_val, punto_val, x_val, y_val, elev_val])
            except (ValueError, IndexError):
                # Si falla una línea, la saltamos
                continue
    
    if datos:
        return pd.DataFrame(datos, columns=COLUMNAS_RPS)
    return pd.DataFrame(columns=COLUMNAS_RPS)

def leer_xps_completo(ruta):
    """
    Lee archivo XPS usando slicing exacto por posiciones.
    Devuelve un DataFrame con todas las columnas detalladas de la relación.
    """
    if not ruta or not os.path.exists(ruta):
        return pd.DataFrame(columns=COLUMNAS_XPS)
    
    datos = []
    with open(ruta, 'r', encoding='utf-8-sig', errors='ignore') as f:
        for linea in f:
            linea_limpia = linea.rstrip('\n\r')
            if not linea_limpia or len(linea_limpia) < 70:
                continue
            
            # Saltar líneas de encabezado (empiezan con H)
            if linea_limpia.startswith('H'):
                continue
            
            # Saltar líneas que no empiezan con X
            if not linea_limpia.startswith('X'):
                continue
            
            try:
                # Extraer por posiciones exactas corregidas (1-based → 0-based)
                reel_str = linea_limpia[1:7].strip()
                event_str = linea_limpia[7:17].strip()
                linea_f_str = linea_limpia[17:27].strip()
                punto_f_str = linea_limpia[27:37].strip()
                punto_f_idx_str = linea_limpia[37:38].strip()
                desde_str = linea_limpia[36:41].strip()
                hasta_str = linea_limpia[41:46].strip()
                inc_str = linea_limpia[46:47].strip()
                linea_r_str = linea_limpia[47:59].strip()
                punto_r_str = linea_limpia[59:69].strip()
                punto_r_idx_str = linea_limpia[69:70].strip()
                
                # Campos opcionales de correcciones estáticas
                static_f_str = linea_limpia[70:75].strip() if len(linea_limpia) >= 75 else ""
                static_r_str = linea_limpia[75:80].strip() if len(linea_limpia) >= 80 else ""
                
                # Convertir a enteros de manera robusta
                reel_val = int(reel_str) if reel_str and reel_str.replace('-', '').isdigit() else 0
                event_val = int(event_str) if event_str and event_str.replace('-', '').isdigit() else 0
                linea_f_val = int(linea_f_str) if linea_f_str and linea_f_str.replace('-', '').isdigit() else 0
                punto_f_val = int(punto_f_str) if punto_f_str and punto_f_str.replace('-', '').isdigit() else 0
                punto_f_idx_val = int(punto_f_idx_str) if punto_f_idx_str and punto_f_idx_str.replace('-', '').isdigit() else 0
                desde_val = int(desde_str) if desde_str and desde_str.replace('-', '').isdigit() else 0
                hasta_val = int(hasta_str) if hasta_str and hasta_str.replace('-', '').isdigit() else 0
                inc_val = int(inc_str) if inc_str and inc_str.replace('-', '').isdigit() else 0
                linea_r_val = int(linea_r_str) if linea_r_str and linea_r_str.replace('-', '').isdigit() else 0
                punto_r_val = int(punto_r_str) if punto_r_str and punto_r_str.replace('-', '').isdigit() else 0
                punto_r_idx_val = int(punto_r_idx_str) if punto_r_idx_str and punto_r_idx_str.replace('-', '').isdigit() else 0
                
                static_f_val = int(static_f_str) if static_f_str and static_f_str.replace('-', '').isdigit() else 0
                static_r_val = int(static_r_str) if static_r_str and static_r_str.replace('-', '').isdigit() else 0
                
                datos.append([
                    reel_val, event_val, linea_f_val, punto_f_val, punto_f_idx_val,
                    desde_val, hasta_val, inc_val, linea_r_val, punto_r_val,
                    punto_r_idx_val, static_f_val, static_r_val
                ])
            except (ValueError, IndexError):
                # Si falla una línea, la saltamos
                continue
    
    if datos:
        return pd.DataFrame(datos, columns=COLUMNAS_XPS)
    return pd.DataFrame(columns=COLUMNAS_XPS)

def detectar_tipo_sps_rps(ruta):
    """Detecta si un archivo es RPS o SPS contando líneas que empiezan con R o S."""
    try:
        with open(ruta, 'r', encoding='utf-8-sig', errors='ignore') as f:
            count_r = 0
            count_s = 0
            for i, linea in enumerate(f):
                if i > 1000:
                    break
                linea_limpia = linea.strip()
                if linea_limpia.startswith('R'):
                    count_r += 1
                elif linea_limpia.startswith('S'):
                    count_s += 1
            if count_r > count_s:
                return 'R'
            elif count_s > count_r:
                return 'S'
            else:
                return None
    except:
        return None

def leer_xps_intervalos_fuente(ruta):
    """
    Lee XPS y retorna intervalos por fuente: {(linea_f, punto_f): [(linea_r, desde, hasta), ...]}
    Usa slicing exacto para extraer los datos.
    """
    if not ruta or not os.path.exists(ruta):
        return {}
    
    intervalos_fuente = defaultdict(list)
    
    with open(ruta, 'r', encoding='utf-8-sig', errors='ignore') as f:
        for linea in f:
            linea_limpia = linea.rstrip('\n\r')
            if not linea_limpia or len(linea_limpia) < 70:
                continue
            if linea_limpia.startswith('H'):
                continue
            if not linea_limpia.startswith('X'):
                continue
            
            try:
                # Extraer por posiciones exactas corregidas
                linea_f_str = linea_limpia[17:27].strip()
                punto_f_str = linea_limpia[27:37].strip()  # excluir índice de punto
                linea_r_str = linea_limpia[47:59].strip()
                desde_str = linea_limpia[36:41].strip()
                hasta_str = linea_limpia[41:46].strip()
                
                linea_f = int(linea_f_str) if linea_f_str and linea_f_str.replace('-', '').isdigit() else 0
                punto_f = int(punto_f_str) if punto_f_str and punto_f_str.replace('-', '').isdigit() else 0
                linea_r = int(linea_r_str) if linea_r_str and linea_r_str.replace('-', '').isdigit() else 0
                desde = int(desde_str) if desde_str and desde_str.replace('-', '').isdigit() else 0
                hasta = int(hasta_str) if hasta_str and hasta_str.replace('-', '').isdigit() else 0
                
                intervalos_fuente[(linea_f, punto_f)].append((linea_r, desde, hasta))
            except (ValueError, IndexError):
                continue
    
    return dict(intervalos_fuente)

def construir_intervalos_receptor(intervalos_fuente):
    receptor_intervalos = defaultdict(list)
    for intervalos in intervalos_fuente.values():
        for linea_r, desde, hasta in intervalos:
            receptor_intervalos[linea_r].append((desde, hasta))
    for linea in receptor_intervalos:
        receptor_intervalos[linea] = list(set(receptor_intervalos[linea]))
    return dict(receptor_intervalos)

def es_activo(linea, punto, receptor_intervalos):
    if linea not in receptor_intervalos:
        return False
    for desde, hasta in receptor_intervalos[linea]:
        if desde <= punto <= hasta:
            return True
    return False