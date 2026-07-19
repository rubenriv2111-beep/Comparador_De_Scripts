# -*- coding: utf-8 -*-

import folium
import numpy as np
import pandas as pd
import json
from core.lectores import leer_sps_rps, leer_xps_intervalos_fuente, construir_intervalos_receptor, es_activo
from core.transformador import TransformadorUTM

def generar_mapa_completo(ruta_rps, ruta_sps, ruta_xps, epsg_code, muestreo, progreso):
    """
    Genera mapa interactivo sin heatmap.
    - Receptores: verde=activo, azul=inactivo
    - Fuentes: rojas. Al hacer clic, resalta sus receptores.
    """
    progreso.actualizar(5, "Leyendo RPS...")
    df_rec = leer_sps_rps(ruta_rps, 'R') if ruta_rps else pd.DataFrame(columns=['linea', 'punto', 'x', 'y', 'elevacion'])
    df_fu = leer_sps_rps(ruta_sps, 'S') if ruta_sps else pd.DataFrame(columns=['linea', 'punto', 'x', 'y', 'elevacion'])
    
    progreso.actualizar(15, f"Receptores: {len(df_rec)}, Fuentes: {len(df_fu)}")
    
    # Leer XPS como intervalos por fuente
    intervalos_fuente = {}
    receptor_intervalos = {}
    if ruta_xps:
        progreso.actualizar(20, "Leyendo XPS (intervalos)...")
        intervalos_fuente = leer_xps_intervalos_fuente(ruta_xps)
        receptor_intervalos = construir_intervalos_receptor(intervalos_fuente)
        progreso.actualizar(25, f"Fuentes con intervalos: {len(intervalos_fuente)}")
    
    # Muestreo para marcadores
    MAX_REC_ACTIVOS = 3000
    MAX_REC_INACTIVOS = 1000
    MAX_FUENTES = 500
    
    # Marcar activos/inactivos
    if not df_rec.empty:
        df_rec['activo'] = df_rec.apply(
            lambda row: es_activo(row['linea'], row['punto'], receptor_intervalos), axis=1
        )
    else:
        df_rec['activo'] = False
    
    # Separar y muestrear
    df_activos = df_rec[df_rec['activo']] if not df_rec.empty else pd.DataFrame()
    df_inactivos = df_rec[~df_rec['activo']] if not df_rec.empty else pd.DataFrame()
    
    if len(df_activos) > MAX_REC_ACTIVOS:
        df_activos = df_activos.sample(n=MAX_REC_ACTIVOS, random_state=42)
    if len(df_inactivos) > MAX_REC_INACTIVOS:
        df_inactivos = df_inactivos.sample(n=MAX_REC_INACTIVOS, random_state=42)
    
    df_rec_markers = pd.concat([df_activos, df_inactivos]) if not df_activos.empty and not df_inactivos.empty else (df_activos if not df_activos.empty else df_inactivos)
    if df_rec_markers.empty:
        df_rec_markers = pd.DataFrame(columns=['linea', 'punto', 'x', 'y', 'elevacion'])
    
    if len(df_fu) > MAX_FUENTES:
        df_fu_markers = df_fu.sample(n=MAX_FUENTES, random_state=42)
    else:
        df_fu_markers = df_fu.copy()
    
    progreso.actualizar(30, f"Marcadores: {len(df_rec_markers)} receptores, {len(df_fu_markers)} fuentes")
    
    # Transformar coordenadas
    trans = TransformadorUTM(epsg_code)
    
    if not df_rec_markers.empty:
        puntos_rec = [(x, y) for x, y in zip(df_rec_markers['x'], df_rec_markers['y'])]
        lons_lats = trans.transformar_lote(puntos_rec)
        df_rec_markers['lon'] = [p[0] for p in lons_lats]
        df_rec_markers['lat'] = [p[1] for p in lons_lats]
    
    if not df_fu_markers.empty:
        puntos_fu = [(x, y) for x, y in zip(df_fu_markers['x'], df_fu_markers['y'])]
        lons_lats = trans.transformar_lote(puntos_fu)
        df_fu_markers['lon'] = [p[0] for p in lons_lats]
        df_fu_markers['lat'] = [p[1] for p in lons_lats]
    
    progreso.actualizar(55, "Coordenadas transformadas")
    
    # Centro del mapa
    todas_lons = []
    todas_lats = []
    if not df_rec_markers.empty:
        todas_lons.extend(df_rec_markers['lon'])
        todas_lats.extend(df_rec_markers['lat'])
    if not df_fu_markers.empty:
        todas_lons.extend(df_fu_markers['lon'])
        todas_lats.extend(df_fu_markers['lat'])
    
    if todas_lons:
        lon_centro = np.mean(todas_lons)
        lat_centro = np.mean(todas_lats)
    else:
        lon_centro, lat_centro = -96.1342, 19.1738
    
    # Crear mapa base
    m = folium.Map(location=[lat_centro, lon_centro], zoom_start=12)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Satélite Esri'
    ).add_to(m)
    folium.TileLayer('OpenStreetMap', name='OpenStreetMap').add_to(m)
    
    # --- Preparar datos para JavaScript (intervalos por fuente) ---
    intervalos_fuente_js = {}
    for idx, row in df_fu_markers.iterrows():
        clave = (row['linea'], row['punto'])
        if clave in intervalos_fuente:
            intervalos_fuente_js[f"{row['linea']}_{row['punto']}"] = intervalos_fuente[clave]
    
    # --- Añadir marcadores ---
    # Receptores
    for _, row in df_rec_markers.iterrows():
        color = 'green' if row.get('activo', False) else 'blue'
        popup = f"Receptor {row['linea']}-{row['punto']} {'Activo' if row.get('activo', False) else 'Inactivo'}"
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=3,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=popup,
            id=f"rec_{row['linea']}_{row['punto']}",
            className="receptor"
        ).add_to(m)
    
    # Fuentes con popup interactivo
    for _, row in df_fu_markers.iterrows():
        clave = (row['linea'], row['punto'])
        popup_text = f"<b>Fuente {row['linea']}-{row['punto']}</b><br>"
        if clave in intervalos_fuente:
            num_intervalos = len(intervalos_fuente[clave])
            popup_text += f"Intervalos asociados: {num_intervalos}<br>"
            popup_text += f"""
            <button onclick="resaltarFuente('{row['linea']}', '{row['punto']}')">Resaltar receptores</button>
            <button onclick="restaurarColores()">Restaurar</button>
            """
        else:
            popup_text += "Sin receptores asociados"
        
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=6,
            color='red',
            fill=True,
            fill_color='red',
            fill_opacity=0.9,
            popup=folium.Popup(popup_text, max_width=300),
            id=f"fuente_{row['linea']}_{row['punto']}",
            className="fuente"
        ).add_to(m)
    
    # --- Inyectar JavaScript con intervalos ---
    js_script = f"""
    <script>
    window.intervalosFuente = {json.dumps(intervalos_fuente_js)};
    window.coloresOriginales = {{}};
    
    function resaltarFuente(linea, punto) {{
        var clave = linea + '_' + punto;
        var intervalos = window.intervalosFuente[clave] || [];
        var activosSet = new Set();
        intervalos.forEach(function(intervalo) {{
            var lineaR = intervalo[0];
            var desde = intervalo[1];
            var hasta = intervalo[2];
            for (var p = desde; p <= hasta; p++) {{
                activosSet.add(lineaR + '_' + p);
            }}
        }});
        
        document.querySelectorAll('.receptor').forEach(function(el) {{
            var id = el.id;
            if (!window.coloresOriginales[id]) {{
                window.coloresOriginales[id] = {{
                    color: el.getAttribute('stroke') || 'blue',
                    fillColor: el.getAttribute('fill') || 'blue'
                }};
            }}
            var partes = id.replace('rec_', '').split('_');
            var recLinea = partes[0];
            var recPunto = partes[1];
            var recClave = recLinea + '_' + recPunto;
            if (activosSet.has(recClave)) {{
                el.setAttribute('fill', 'yellow');
                el.setAttribute('stroke', 'yellow');
                el.style.opacity = '1';
            }} else {{
                el.setAttribute('fill', 'gray');
                el.setAttribute('stroke', 'gray');
                el.style.opacity = '0.3';
            }}
        }});
    }}
    
    function restaurarColores() {{
        document.querySelectorAll('.receptor').forEach(function(el) {{
            var id = el.id;
            if (window.coloresOriginales[id]) {{
                el.setAttribute('fill', window.coloresOriginales[id].fillColor);
                el.setAttribute('stroke', window.coloresOriginales[id].color);
                el.style.opacity = '1';
            }}
        }});
    }}
    </script>
    """
    m.get_root().html.add_child(folium.Element(js_script)) # type: ignore
    
    folium.LayerControl().add_to(m)
    m.save("mapa_sismico.html")
    progreso.actualizar(100, "¡Mapa generado con interactividad!")