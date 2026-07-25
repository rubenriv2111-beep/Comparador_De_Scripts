# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import os
import re
from collections import defaultdict

# Definición de encabezados estándar SPS para RPS (con rangos de columnas SPS 2.1)
ENCABEZADOS_RPS = {
    'linea': 'Línea Receptora (2-17)',
    'punto': 'Estaca / Receptor (18-25)',
    'x': 'Coordenada X (Este) (47-55)',
    'y': 'Coordenada Y (Norte) (56-65)',
    'elevacion': 'Elevación Z (66-71)'
}

ENCABEZADOS_SPS = {
    'linea': 'Línea Fuente (2-17)',
    'punto': 'Punto Fuente (18-25)',
    'x': 'Coordenada X (Este) (47-55)',
    'y': 'Coordenada Y (Norte) (56-65)',
    'elevacion': 'Elevación Z (66-71)'
}

ENCABEZADOS_XPS = {
    'reel': 'Carrete / Tape (2-7)',
    'evento': 'Evento / FFID (8-17)',
    'linea_f': 'Línea Fuente (18-27)',
    'punto_f': 'Punto Fuente (28-37)',
    'punto_f_idx': 'Índice Fuente (38)',
    'desde': 'Canal Desde (39-43)',
    'hasta': 'Canal Hasta (44-48)',
    'incremento': 'Incremento Canal (49)',
    'linea_r': 'Línea Receptora (50-59)',
    'punto_r': 'Punto Receptor (60-69)',
    'punto_r_idx': 'Índice Receptor (70)',
    'estatico_f': 'Estático Fuente (71-75)',
    'estatico_r': 'Estático Receptor (76-80)'
}

# Columnas estándar para SPS/RPS/XPS
COLUMNAS_RPS = ['linea', 'punto', 'x', 'y', 'elevacion']
COLUMNAS_XPS = [
    'reel', 'evento', 'linea_f', 'punto_f', 'punto_f_idx', 
    'desde', 'hasta', 'incremento', 'linea_r', 'punto_r', 
    'punto_r_idx', 'estatico_f', 'estatico_r'
]

def leer_sps_rps(ruta, tipo):
    """
    Lee archivo SPS/RPS usando slicing exacto optimizado a alto rendimiento (Nivel Sr.).
    Siempre devuelve un DataFrame con las columnas ['linea', 'punto', 'x', 'y', 'elevacion'].
    """
    if not ruta or not os.path.exists(ruta):
        return pd.DataFrame(columns=COLUMNAS_RPS)
    
    datos = []
    with open(ruta, 'r', encoding='utf-8-sig', errors='ignore') as f:
        for linea in f:
            if len(linea) >= 71 and linea[0] == tipo:
                try:
                    l_str = linea[1:11]
                    p_str = linea[11:21]
                    x_str = linea[46:55]
                    y_str = linea[55:65]
                    z_str = linea[65:71]
                    
                    linea_val = int(float(l_str)) if l_str.strip() else 0
                    punto_val = int(float(p_str)) if p_str.strip() else 0
                    x_val = float(x_str) if x_str.strip() else 0.0
                    y_val = float(y_str) if y_str.strip() else 0.0
                    z_val = float(z_str) if z_str.strip() else 0.0
                    
                    datos.append((linea_val, punto_val, x_val, y_val, z_val))
                except (ValueError, IndexError):
                    continue
    
    if datos:
        return pd.DataFrame(datos, columns=COLUMNAS_RPS)
    return pd.DataFrame(columns=COLUMNAS_RPS)

def leer_xps_completo(ruta):
    """
    Lee archivo XPS usando slicing exacto SPS 2.1 corregido a alto rendimiento (Nivel Sr.).
    Devuelve un DataFrame con todas las columnas detalladas de la relación.
    """
    if not ruta or not os.path.exists(ruta):
        return pd.DataFrame(columns=COLUMNAS_XPS)
    
    datos = []
    with open(ruta, 'r', encoding='utf-8-sig', errors='ignore') as f:
        for linea in f:
            if len(linea) >= 70 and linea[0] == 'X':
                try:
                    reel_s = linea[1:7]
                    ev_s   = linea[7:17]
                    lf_s   = linea[17:27]
                    pf_s   = linea[27:37]
                    pfi_s  = linea[37:38]
                    des_s  = linea[38:43]
                    has_s  = linea[43:48]
                    inc_s  = linea[48:49]
                    lr_s   = linea[49:59]
                    pr_s   = linea[59:69]
                    pri_s  = linea[69:70]
                    
                    stf_s  = linea[70:75] if len(linea) >= 75 else ""
                    str_s  = linea[75:80] if len(linea) >= 80 else ""
                    
                    reel_val  = int(float(reel_s)) if reel_s.strip() else 0
                    event_val = int(float(ev_s))   if ev_s.strip()   else 0
                    linea_f_val = int(float(lf_s)) if lf_s.strip()   else 0
                    punto_f_val = int(float(pf_s)) if pf_s.strip()   else 0
                    punto_f_idx_val = int(float(pfi_s)) if pfi_s.strip() else 0
                    desde_val = int(float(des_s)) if des_s.strip()  else 0
                    hasta_val = int(float(has_s)) if has_s.strip()  else 0
                    inc_val   = int(float(inc_s)) if inc_s.strip()  else 0
                    linea_r_val = int(float(lr_s)) if lr_s.strip()   else 0
                    punto_r_val = int(float(pr_s)) if pr_s.strip()   else 0
                    punto_r_idx_val = int(float(pri_s)) if pri_s.strip() else 0
                    
                    static_f_val = int(float(stf_s)) if stf_s.strip() else 0
                    static_r_val = int(float(str_s)) if str_s.strip() else 0
                    
                    datos.append((
                        reel_val, event_val, linea_f_val, punto_f_val, punto_f_idx_val,
                        desde_val, hasta_val, inc_val, linea_r_val, punto_r_val,
                        punto_r_idx_val, static_f_val, static_r_val
                    ))
                except (ValueError, IndexError):
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
                if len(linea) > 0:
                    ch = linea[0]
                    if ch == 'R':
                        count_r += 1
                    elif ch == 'S':
                        count_s += 1
            if count_r > count_s:
                return 'R'
            elif count_s > count_r:
                return 'S'
            else:
                return None
    except Exception:
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
            if len(linea) >= 70 and linea[0] == 'X':
                try:
                    lf_s  = linea[17:27]
                    pf_s  = linea[27:37]
                    lr_s  = linea[49:59]
                    des_s = linea[38:43]
                    has_s = linea[43:48]
                    
                    linea_f = int(float(lf_s)) if lf_s.strip() else 0
                    punto_f = int(float(pf_s)) if pf_s.strip() else 0
                    linea_r = int(float(lr_s)) if lr_s.strip() else 0
                    desde   = int(float(des_s)) if des_s.strip() else 0
                    hasta   = int(float(has_s)) if has_s.strip() else 0
                    
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