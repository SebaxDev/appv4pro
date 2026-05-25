# components/reclamos/planificacion.py

import io
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import qrcode
from utils.date_utils import parse_fecha, format_fecha
from utils.api_manager import api_manager, batch_update_sheet
from utils.pdf_utils import agregar_pie_pdf
from config.settings import (
    SECTORES_DISPONIBLES,
    TECNICOS_DISPONIBLES,
    MATERIALES_POR_RECLAMO,
    ROUTER_POR_SECTOR,
    DEBUG_MODE
)
import uuid

GRUPOS_POSIBLES = [f"Grupo {letra}" for letra in "ABCDE"]

# --- FUNCIONES DE LIMPIEZA DEFINITIVAS ---

def _limpiar_id(val):
    """Convierte cualquier ID (450, 450.0, ' 450 ') en un string limpio '450'"""
    if pd.isna(val) or str(val).strip() == "": return ""
    return str(val).split('.')[0].strip()

def _obtener_coordenada_limpia(val):
    """Limpia texto de lat/lon (quita espacios, cambia coma por punto)"""
    if pd.isna(val): return None
    s = str(val).strip().replace(',', '.')
    try:
        f = float(s)
        if f == 0: return None # Ignorar ceros
        return s
    except:
        return None

def generar_id_unico():
    return str(uuid.uuid4())[:8].upper()

# --- TODA TU LÓGICA ORIGINAL DE DISTRIBUCIÓN (SIN RECORTES) ---

SECTORES_VECINOS = {
    "Zona 1": ["1", "2", "3", "4"],
    "Zona 2": ["5", "6", "7", "8"],
    "Zona 3": ["9", "10"],
    "Zona 4": ["11", "12", "13"],
    "Zona 5": ["14", "15", "16", "17"]
}

ZONAS_COMPATIBLES = {
    "Zona 1": ["Zona 3", "Zona 5"],
    "Zona 2": ["Zona 4"],
    "Zona 3": ["Zona 1", "Zona 2", "Zona 4", "Zona 5"],
    "Zona 4": ["Zona 2"],
    "Zona 5": ["Zona 1", "Zona 3"]
}

def inicializar_estado_grupos():
    if "asignaciones_grupos" not in st.session_state:
        st.session_state.asignaciones_grupos = {g: [] for g in GRUPOS_POSIBLES}
    if "tecnicos_grupos" not in st.session_state:
        st.session_state.tecnicos_grupos = {g: [] for g in GRUPOS_POSIBLES}
    if "vista_simulacion" not in st.session_state:
        st.session_state.vista_simulacion = False
    if "simulacion_asignaciones" not in st.session_state:
        st.session_state.simulacion_asignaciones = {}

def agrupar_zonas_completas(zonas, grupos, df_reclamos, permitir_redistribucion=True):
    if not grupos or not zonas: return {g: [] for g in grupos}
    reclamos_por_zona = {}
    for zona in zonas:
        sectores_zona = SECTORES_VECINOS.get(zona, [])
        total_reclamos = len(df_reclamos[df_reclamos["Sector"].astype(str).isin(sectores_zona) & (df_reclamos["Estado"] == "Pendiente")])
        reclamos_por_zona[zona] = total_reclamos
    zonas_ordenadas = sorted(zonas, key=lambda z: reclamos_por_zona[z], reverse=True)
    asignacion = {g: [] for g in grupos}; carga_actual = {g: 0 for g in grupos}
    for zona in zonas_ordenadas:
        grupo_elegido = min(grupos, key=lambda g: carga_actual[g])
        asignacion[grupo_elegido].append(zona)
        carga_actual[grupo_elegido] += reclamos_por_zona[zona]
    if (permitir_redistribucion and len(grupos) >= 4 and _necesita_redistribucion(carga_actual)):
        asignacion = _redistribuir_inteligente(asignacion, carga_actual, reclamos_por_zona, grupos)
    return asignacion

def _necesita_redistribucion(carga_actual):
    cargas = list(carga_actual.values())
    return max(cargas) - min(cargas) > 2

def _redistribuir_inteligente(asignacion, carga_actual, reclamos_por_zona, grupos):
    grupo_max = max(carga_actual.items(), key=lambda x: x[1])[0]
    grupo_min = min(carga_actual.items(), key=lambda x: x[1])[0]
    for zona in asignacion[grupo_max]:
        if reclamos_por_zona[zona] <= 2:
            if _son_zonas_compatibles(zona, asignacion[grupo_min]):
                asignacion[grupo_max].remove(zona)
                asignacion[grupo_min].append(zona)
                carga_actual[grupo_max] -= reclamos_por_zona[zona]
                carga_actual[grupo_min] += reclamos_por_zona[zona]
                if not _necesita_redistribucion(carga_actual): break
    return asignacion

def _son_zonas_compatibles(zona, zonas_destino):
    if not zonas_destino: return True
    for zona_dest in zonas_destino:
        if (zona in ZONAS_COMPATIBLES.get(zona_dest, []) or zona_dest in ZONAS_COMPATIBLES.get(zona, [])): return True
    return False

def distribuir_por_sector_mejorado(df_reclamos, grupos_activos):
    df_reclamos = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()
    grupos = GRUPOS_POSIBLES[:grupos_activos]
    zonas_por_grupo = agrupar_zonas_completas(list(SECTORES_VECINOS.keys()), grupos, df_reclamos)
    sector_grupo_map = {}
    for grupo, zonas_asignadas in zonas_por_grupo.items():
        for zona in zonas_asignadas:
            for sector in SECTORES_VECINOS.get(zona, []): sector_grupo_map[str(sector)] = grupo
    asignaciones = {g: [] for g in grupos}
    for _, r in df_reclamos.iterrows():
        grupo = sector_grupo_map.get(str(r.get("Sector", "")).strip())
        if grupo: asignaciones[grupo].append(r["ID Reclamo"])
    return asignaciones

def _balancear_asignaciones(asignaciones, df_reclamos):
    carga_por_grupo = {g: len(recs) for g, recs in asignaciones.items()}
    intentos = 0
    while (max(carga_por_grupo.values()) - min(carga_por_grupo.values())) > 1 and intentos < 1000:
        intentos += 1
        grupos_ordenados = sorted(carga_por_grupo.keys(), key=lambda g: carga_por_grupo[g])
        g_min, g_max = grupos_ordenados[0], grupos_ordenados[-1]
        rid = _encontrar_reclamo_transferible(asignaciones[g_max], g_max, g_min, df_reclamos, asignaciones)
        if not rid: break
        asignaciones[g_max].remove(rid)
        asignaciones[g_min].append(rid)
        carga_por_grupo[g_max] -= 1; carga_por_grupo[g_min] += 1
    return asignaciones

def _encontrar_reclamo_transferible(reclamos_origen, g_origen, g_destino, df_reclamos, asignaciones):
    zonas_dest = []
    recs_d = df_reclamos[df_reclamos["ID Reclamo"].isin(asignaciones[g_destino])]
    for _, r in recs_d.iterrows():
        sec = str(r["Sector"])
        for z, sectores in SECTORES_VECINOS.items():
            if sec in sectores and z not in zonas_dest: zonas_dest.append(z)
    mejor_id, mejor_score = None, float("-inf")
    for rid in reclamos_origen:
        fila = df_reclamos[df_reclamos["ID Reclamo"] == rid]
        if fila.empty: continue
        sector = str(fila.iloc[0]["Sector"])
        zona_r = next((z for z, s in SECTORES_VECINOS.items() if sector in s), None)
        if not zona_r: continue
        score = len(ZONAS_COMPATIBLES.get(zona_r, []))
        if zonas_dest:
            if any(zona_r in ZONAS_COMPATIBLES.get(zd, []) for zd in zonas_dest): score += 100
            if zona_r in zonas_dest: score += 20
        else: score += 10
        if score > mejor_score: mejor_score, mejor_id = score, rid
    return mejor_id or (reclamos_origen[0] if reclamos_origen else None)

def distribuir_por_tipo(df_reclamos, grupos_activos):
    df_r = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()
    grupos = GRUPOS_POSIBLES[:grupos_activos]; asignaciones = {g: [] for g in grupos}
    tipos = {}
    for r in df_r.to_dict("records"):
        tipos.setdefault(r.get("Tipo de reclamo", "Otro"), []).append(r["ID Reclamo"])
    i = 0
    for t, ids in tipos.items():
        for rid in ids: asignaciones[grupos[i % grupos_activos]].append(rid); i += 1
    return asignaciones

# --- UI Y GESTIÓN ---

def _mostrar_asignacion_tecnicos(grupos_activos):
    st.markdown("### 👷 Asignar técnicos a cada grupo")
    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        st.session_state.tecnicos_grupos[grupo] = st.multiselect(
            f"{grupo} - Técnicos", TECNICOS_DISPONIBLES,
            default=st.session_state.tecnicos_grupos[grupo], key=f"tecs_{grupo}"
        )

def _mostrar_reclamos_disponibles(df_reclamos, grupos_activos):
    st.markdown("---")
    st.markdown("### 📋 Reclamos pendientes para asignar")
    df_reclamos["ID Reclamo"] = df_reclamos["ID Reclamo"].astype(str).str.strip()
    df_pendientes = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()
    
    col1, col2 = st.columns(2)
    with col1: f_sec = st.selectbox("Filtrar sector", ["Todos"] + sorted(SECTORES_DISPONIBLES))
    with col2: f_tip = st.selectbox("Filtrar tipo", ["Todos"] + sorted(df_pendientes["Tipo de reclamo"].dropna().unique()))
    
    if f_sec != "Todos": df_pendientes = df_pendientes[df_pendientes["Sector"] == str(f_sec)]
    if f_tip != "Todos": df_pendientes = df_pendientes[df_pendientes["Tipo de reclamo"] == f_tip]
    
    orden = st.selectbox("🔃 Ordenar reclamos por:", ["Fecha más reciente", "Sector", "Tipo de reclamo"])
    df_pendientes = df_pendientes.sort_values("Fecha y hora" if orden=="Fecha más reciente" else orden, ascending=(orden!="Fecha más reciente"))
    
    asignados = [r for recs in st.session_state.asignaciones_grupos.values() for r in recs]
    df_disp = df_pendientes[~df_pendientes["ID Reclamo"].isin(asignados)]
    
    if df_disp.empty: st.info("🎉 No hay reclamos pendientes disponibles.")
    else:
        for idx, row in df_disp.iterrows():
            with st.container():
                c1, *c_gr = st.columns([4] + [1] * grupos_activos)
                c1.markdown(f"**📍 Sector {row['Sector']} - {row['Tipo de reclamo']} - {row['Nombre']}**")
                for i, g in enumerate(GRUPOS_POSIBLES[:grupos_activos]):
                    if c_gr[i].button(f"➡️{g[-1]}", key=f"add_{g}_{row['ID Reclamo']}"):
                        st.session_state.asignaciones_grupos[g].append(row["ID Reclamo"])
                        st.rerun()
            with c1.expander("🔍 Ver detalles"):
                st.markdown(f"**Nº Cliente:** {row['Nº Cliente']} | **Dirección:** {row['Dirección']} | **Tel:** {row['Teléfono']}")
    return df_pendientes

def render_planificacion_grupos(df_reclamos, sheet_reclamos, user, df_clientes=None, sheet_clientes=None):
    if user.get('rol') != 'admin':
        st.warning("⚠️ Acceso restringido")
        return {'needs_refresh': False}

    st.subheader("📋 Asignación de reclamos a grupos de trabajo")
    inicializar_estado_grupos()
    
    grupos_activos = st.slider("🔢 Cantidad de grupos activos", 1, 5, 2)
    modo = st.selectbox("📊 Modo de distribución", ["Manual", "Automática por sector (mejorada)", "Automática por tipo"])
    
    if modo != "Manual" and st.button("⚙️ Distribuir ahora"):
        if modo == "Automática por sector (mejorada)":
            st.session_state.simulacion_asignaciones = distribuir_por_sector_mejorado(df_reclamos, grupos_activos)
        else:
            st.session_state.simulacion_asignaciones = distribuir_por_tipo(df_reclamos, grupos_activos)
        st.session_state.vista_simulacion = True

    if st.session_state.get("vista_simulacion"):
        if st.button("💾 Confirmar y guardar esta asignación"):
            st.session_state.asignaciones_grupos = st.session_state.simulacion_asignaciones
            st.session_state.vista_simulacion = False
            st.rerun()

    _mostrar_asignacion_tecnicos(grupos_activos)
    df_pendientes = _mostrar_reclamos_disponibles(df_reclamos, grupos_activos)

    if df_pendientes is not None:
        mats = _mostrar_reclamos_asignados(df_pendientes, grupos_activos)
        # PASO DE DATOS CRUCIAL: df_clientes viaja aquí
        cambios = _mostrar_acciones_finales(df_reclamos, sheet_reclamos, grupos_activos, mats, df_pendientes, df_clientes)
        return {'needs_refresh': cambios}
    return {'needs_refresh': False}

def _mostrar_reclamos_asignados(df_pendientes, grupos_activos):
    st.markdown("---")
    st.markdown("### 📌 Reclamos asignados por grupo")
    materiales_por_grupo = {}
    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        ids = st.session_state.asignaciones_grupos[grupo]
        tecs = st.session_state.tecnicos_grupos[grupo]
        st.markdown(f"#### 🔢 {grupo} - {', '.join(tecs) or 'Sin técnicos'} ({len(ids)} reclamos)")
        recs_g = df_pendientes[df_pendientes["ID Reclamo"].isin(ids)]
        mats = _calcular_materiales_grupo(recs_g)
        materiales_por_grupo[grupo] = mats
        for rid in ids:
            if st.button(f"❌ Quitar {rid}", key=f"q_{grupo}_{rid}"):
                st.session_state.asignaciones_grupos[grupo].remove(rid)
                st.rerun()
    return materiales_por_grupo

def _calcular_materiales_grupo(recs):
    total = {}
    for _, row in recs.iterrows():
        tipo, sector = row["Tipo de reclamo"], str(row["Sector"])
        for mat, cant in MATERIALES_POR_RECLAMO.get(tipo, {}).items():
            key = f"router_{ROUTER_POR_SECTOR.get(sector, 'vsol')}" if "router" in mat else mat
            total[key] = total.get(key, 0) + cant
    return total

def _mostrar_acciones_finales(df_reclamos, sheet_reclamos, grupos_activos, materiales_por_grupo, df_pendientes, df_clientes):
    st.markdown("---")
    col1, col2 = st.columns(2)
    if col1.button("💾 Guardar cambios y pasar a 'En curso'", use_container_width=True):
        return _guardar_cambios(df_reclamos, sheet_reclamos, grupos_activos)
    
    if col2.button("📄 Generar PDF de asignaciones", use_container_width=True):
        if df_clientes is None:
            st.error("❌ No se pudo acceder a la base de clientes.")
        else:
            _generar_pdf_asignaciones(grupos_activos, materiales_por_grupo, df_pendientes, df_clientes)
    return False

def _guardar_cambios(df_reclamos, sheet_reclamos, grupos_activos):
    updates = []
    for g in GRUPOS_POSIBLES[:grupos_activos]:
        t_str = ", ".join(st.session_state.tecnicos_grupos[g]).upper()
        for rid in st.session_state.asignaciones_grupos[g]:
            fila = df_reclamos[df_reclamos["ID Reclamo"] == rid]
            if not fila.empty:
                idx = fila.index[0] + 2
                updates.append({"range": f"I{idx}", "values": [["En curso"]]})
                updates.append({"range": f"J{idx}", "values": [[t_str]]})
    if updates:
        success, _ = api_manager.safe_sheet_operation(batch_update_sheet, sheet_reclamos, updates, is_batch=True)
        if success: st.success("✅ Guardado"); return True
    return False

# =================================================================
# SOLUCIÓN DEFINITIVA PDF + QR
# =================================================================

def _generar_pdf_asignaciones(grupos_activos, materiales_por_grupo, df_pendientes, df_clientes):
    """Genera PDF con QR. Cruza datos usando IDs normalizados para evitar fallos de formato."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    hoy = datetime.now().strftime('%d/%m/%Y')

    # 1. Normalización de base de clientes para búsqueda infalible
    df_c = df_clientes.copy()
    df_c["Nº Cliente_Clean"] = df_c["Nº Cliente"].apply(_limpiar_id)

    # Diagnóstico en consola de Streamlit (ayuda a ver si hay datos)
    con_gps = df_c[df_c["Latitud"].notna()].shape[0]
    st.toast(f"Procesando {con_gps} clientes con georeferencia...")

    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        ids = st.session_state.asignaciones_grupos[grupo]
        if not ids: continue
        tecs = st.session_state.tecnicos_grupos[grupo]
        
        agregar_pie_pdf(c, width, height)
        c.showPage()
        y = height - 40
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, f"{grupo} - {', '.join(tecs)} ({hoy})")
        y -= 30

        for rid in ids:
            r_data = df_pendientes[df_pendientes["ID Reclamo"] == rid]
            if r_data.empty: continue
            reclamo = r_data.iloc[0]

            # 2. Búsqueda del cliente con ID Limpio
            id_reclamo_clean = _limpiar_id(reclamo['Nº Cliente'])
            match = df_c[df_c["Nº Cliente_Clean"] == id_reclamo_clean]
            
            lat_final, lon_final = None, None
            if not match.empty:
                lat_raw = match.iloc[0].get("Latitud")
                lon_raw = match.iloc[0].get("Longitud")
                lat_final = _obtener_coordenada_limpia(lat_raw)
                lon_final = _obtener_coordenada_limpia(lon_raw)

            # Dibujar Encabezado Reclamo
            c.setFont("Helvetica-Bold", 13)
            c.drawString(40, y, f"{reclamo['Nº Cliente']} - {reclamo['Nombre']} (Sect. {reclamo['Sector']})")
            
            # 3. GENERAR QR SOLO SI HAY COORDENADAS LIMPIAS
            if lat_final and lon_final:
                try:
                    url = f"https://www.google.com/maps?q={lat_final},{lon_final}"
                    qr = qrcode.QRCode(version=1, box_size=10, border=1)
                    qr.add_data(url); qr.make(fit=True)
                    img = qr.make_image(fill="black", back="white")
                    
                    q_buf = io.BytesIO()
                    img.save(q_buf, format='PNG')
                    q_buf.seek(0)
                    
                    # Dibujar QR a la derecha
                    c.drawImage(q_buf, width - 110, y - 55, width=70, height=70)
                    c.setFont("Helvetica-Oblique", 7)
                    c.drawRightString(width - 40, y - 62, "UBICACIÓN GPS")
                except Exception as e:
                    pass 
            else:
                # Aviso visual en el PDF si no hay coordenadas
                c.setFont("Helvetica-Oblique", 8)
                c.setFillColorRGB(0.5, 0.5, 0.5)
                c.drawRightString(width - 40, y, "Sin georeferencia")
                c.setFillColorRGB(0, 0, 0)

            # Info del Reclamo
            y -= 15; c.setFont("Helvetica", 10)
            c.drawString(40, y, f"Dirección: {reclamo['Dirección']}")
            y -= 12; c.drawString(40, y, f"Tel: {reclamo['Teléfono']} - Precinto: {reclamo.get('N° de Precinto', 'N/A')}")
            y -= 12; c.drawString(40, y, f"Tipo: {reclamo['Tipo de reclamo']}")
            y -= 12; d_txt = str(reclamo['Detalles'])[:90] + "..." if len(str(reclamo['Detalles'])) > 90 else str(reclamo['Detalles'])
            c.drawString(40, y, f"Detalles: {d_txt}")
            
            y -= 20; c.line(40, y, width - 40, y); y -= 25

            if y < 140:
                agregar_pie_pdf(c, width, height)
                c.showPage(); y = height - 40

        # Materiales al final
        m_g = materiales_por_grupo.get(grupo, {})
        if m_g:
            y -= 10; c.setFont("Helvetica-Bold", 12); c.drawString(40, y, "Materiales estimados:"); y -= 15
            c.setFont("Helvetica", 11)
            for m, cant in m_g.items():
                c.drawString(40, y, f"- {cant} {m.replace('_', ' ').title()}"); y -= 12

    c.save(); buffer.seek(0)
    st.download_button(label="📄 Descargar PDF de asignaciones", data=buffer, file_name=f"Plan_{hoy}.pdf", mime="application/pdf")