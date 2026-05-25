# components/reclamos/planificacion.py

import io
import streamlit as st
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import qrcode  # <--- NUEVA LIBRERÍA
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

def generar_id_unico():
    """Genera un ID único para reclamos y clientes"""
    return str(uuid.uuid4())[:8].upper()

def _generar_uuids_faltantes(df_reclamos, df_clientes, sheet_reclamos, sheet_clientes):
    """
    Genera UUIDs para reclamos y clientes que no los tengan.
    Retorna True si se generaron UUIDs, False en caso contrario.
    """
    updates_reclamos = []
    updates_clientes = []
    uuids_generados = False
    
    try:
        # Verificar reclamos sin UUID
        if 'ID Reclamo' in df_reclamos.columns:
            reclamos_sin_uuid = df_reclamos[
                df_reclamos['ID Reclamo'].isna() |
                (df_reclamos['ID Reclamo'] == '') |
                (df_reclamos['ID Reclamo'].astype(str).str.strip() == '')
            ]
            
            if not reclamos_sin_uuid.empty:
                for _, row in reclamos_sin_uuid.iterrows():
                    nuevo_uuid = generar_id_unico()
                    updates_reclamos.append({
                        "range": f"P{row.name + 2}",  # Columna P es ID Reclamo
                        "values": [[nuevo_uuid]]
                    })
        
        # Verificar clientes sin UUID
        if 'ID Cliente' in df_clientes.columns:
            clientes_sin_uuid = df_clientes[
                df_clientes['ID Cliente'].isna() |
                (df_clientes['ID Cliente'] == '') |
                (df_clientes['ID Cliente'].astype(str).str.strip() == '')
            ]
            
            if not clientes_sin_uuid.empty:
                for _, row in clientes_sin_uuid.iterrows():
                    nuevo_uuid = generar_id_unico()
                    updates_clientes.append({
                        "range": f"G{row.name + 2}",  # Columna G es ID Cliente
                        "values": [[nuevo_uuid]]
                    })
        
        # Aplicar actualizaciones
        if updates_reclamos:
            success, error = api_manager.safe_sheet_operation(batch_update_sheet, sheet_reclamos, updates_reclamos, is_batch=True)
            if success: uuids_generados = True
        
        if updates_clientes:
            success, error = api_manager.safe_sheet_operation(batch_update_sheet, sheet_clientes, updates_clientes, is_batch=True)
            if success: uuids_generados = True
            
    except Exception as e:
        st.error(f"❌ Error al verificar/generar UUIDs: {str(e)}")
    
    return uuids_generados

# Mapeo de sectores cercanos por zona
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
    if not grupos or not zonas:
        return {g: [] for g in grupos}
    
    reclamos_por_zona = {}
    for zona in zonas:
        sectores_zona = SECTORES_VECINOS.get(zona, [])
        total_reclamos = len(df_reclamos[
            df_reclamos["Sector"].astype(str).isin(sectores_zona) &
            (df_reclamos["Estado"] == "Pendiente")
        ])
        reclamos_por_zona[zona] = total_reclamos
    
    zonas_ordenadas = sorted(zonas, key=lambda z: reclamos_por_zona[z], reverse=True)
    asignacion = {g: [] for g in grupos}
    carga_actual = {g: 0 for g in grupos}
    
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
                if not _necesita_redistribucion(carga_actual):
                    break
    return asignacion

def _son_zonas_compatibles(zona, zonas_destino):
    if not zonas_destino: return True
    for zona_dest in zonas_destino:
        if (zona in ZONAS_COMPATIBLES.get(zona_dest, []) or zona_dest in ZONAS_COMPATIBLES.get(zona, [])):
            return True
    return False

def distribuir_por_sector_mejorado(df_reclamos, grupos_activos):
    df_reclamos = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()
    grupos = GRUPOS_POSIBLES[:grupos_activos]
    zonas = list(SECTORES_VECINOS.keys())
    zonas_por_grupo = agrupar_zonas_completas(zonas, grupos, df_reclamos)
    
    sector_grupo_map = {}
    for grupo, zonas_asignadas in zonas_por_grupo.items():
        for zona in zonas_asignadas:
            sectores = SECTORES_VECINOS.get(zona, [])
            for sector in sectores:
                sector_grupo_map[str(sector)] = grupo

    asignaciones = {g: [] for g in grupos}
    for _, r in df_reclamos.iterrows():
        sector = str(r.get("Sector", "")).strip()
        grupo = sector_grupo_map.get(sector)
        if grupo:
            asignaciones[grupo].append(r["ID Reclamo"])
    
    return asignaciones

def _balancear_asignaciones(asignaciones, df_reclamos):
    carga_por_grupo = {g: len(recs) for g, recs in asignaciones.items()}
    balanced = lambda cargas: (max(cargas.values()) - min(cargas.values())) <= 1
    intentos = 0
    while not balanced(carga_por_grupo) and intentos < 1000:
        intentos += 1
        grupos_ordenados = sorted(carga_por_grupo.keys(), key=lambda g: carga_por_grupo[g])
        grupo_menos_cargado, grupo_mas_cargado = grupos_ordenados[0], grupos_ordenados[-1]
        if carga_por_grupo[grupo_mas_cargado] - carga_por_grupo[grupo_menos_cargado] <= 1: break
        reclamo_a_transferir = _encontrar_reclamo_transferible(asignaciones[grupo_mas_cargado], grupo_mas_cargado, grupo_menos_cargado, df_reclamos, asignaciones)
        if not reclamo_a_transferir: break
        asignaciones[grupo_mas_cargado].remove(reclamo_a_transferir)
        asignaciones[grupo_menos_cargado].append(reclamo_a_transferir)
        carga_por_grupo[grupo_mas_cargado] -= 1
        carga_por_grupo[grupo_menos_cargado] += 1
    return asignaciones

def _encontrar_reclamo_transferible(reclamos_grupo_origen, grupo_origen, grupo_destino, df_reclamos, asignaciones):
    zonas_destino = []
    recs_dest = df_reclamos[df_reclamos["ID Reclamo"].isin(asignaciones[grupo_destino])]
    for _, r in recs_dest.iterrows():
        sec = str(r["Sector"])
        for z, sectores in SECTORES_VECINOS.items():
            if sec in sectores and z not in zonas_destino: zonas_destino.append(z)
    mejor_id, mejor_score = None, float("-inf")
    for rid in reclamos_grupo_origen:
        fila = df_reclamos[df_reclamos["ID Reclamo"] == rid]
        if fila.empty: continue
        sector = str(fila.iloc[0]["Sector"])
        zona_reclamo = next((z for z, s in SECTORES_VECINOS.items() if sector in s), None)
        if not zona_reclamo: continue
        score = len(ZONAS_COMPATIBLES.get(zona_reclamo, []))
        if zonas_destino:
            if any(zona_reclamo in ZONAS_COMPATIBLES.get(zd, []) for zd in zonas_destino): score += 100
            if zona_reclamo in zonas_destino: score += 20
        else: score += 10
        if score > mejor_score: mejor_score, mejor_id = score, rid
    return mejor_id or (reclamos_grupo_origen[0] if reclamos_grupo_origen else None)

def distribuir_por_tipo(df_reclamos, grupos_activos):
    df_reclamos = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()
    grupos = GRUPOS_POSIBLES[:grupos_activos]
    asignaciones = {g: [] for g in grupos}
    reclamos_por_tipo = {}
    for r in df_reclamos.to_dict("records"):
        tipo = r.get("Tipo de reclamo", "Otro")
        reclamos_por_tipo.setdefault(tipo, []).append(r["ID Reclamo"])
    i = 0
    for tipo, ids in reclamos_por_tipo.items():
        for rid in ids:
            asignaciones[grupos[i % grupos_activos]].append(rid)
            i += 1
    return asignaciones

def _mostrar_asignacion_tecnicos(grupos_activos):
    st.markdown("### 👷 Asignar técnicos a cada grupo")
    for grupo in list(st.session_state.tecnicos_grupos.keys())[:grupos_activos]:
        st.session_state.tecnicos_grupos[grupo] = st.multiselect(
            f"{grupo} - Técnicos asignados", TECNICOS_DISPONIBLES,
            default=st.session_state.tecnicos_grupos[grupo], key=f"tecnicos_{grupo}"
        )

def _mostrar_reclamos_disponibles(df_reclamos, grupos_activos):
    st.markdown("---")
    st.markdown("### 📋 Reclamos pendientes para asignar")
    df_reclamos["ID Reclamo"] = df_reclamos["ID Reclamo"].astype(str).str.strip()
    df_reclamos["Fecha y hora"] = pd.to_datetime(df_reclamos["Fecha y hora"], dayfirst=True, errors='coerce')
    df_pendientes = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()
    col1, col2 = st.columns(2)
    with col1: filtro_sector = st.selectbox("Filtrar sector", ["Todos"] + sorted(SECTORES_DISPONIBLES))
    with col2: filtro_tipo = st.selectbox("Filtrar tipo", ["Todos"] + sorted(df_pendientes["Tipo de reclamo"].dropna().unique()))
    if filtro_sector != "Todos": df_pendientes = df_pendientes[df_pendientes["Sector"] == str(filtro_sector)]
    if filtro_tipo != "Todos": df_pendientes = df_pendientes[df_pendientes["Tipo de reclamo"] == filtro_tipo]
    orden = st.selectbox("🔃 Ordenar por:", ["Fecha más reciente", "Sector", "Tipo de reclamo"])
    df_pendientes = df_pendientes.sort_values("Fecha y hora" if orden=="Fecha más reciente" else orden, ascending=(orden!="Fecha más reciente"))
    asignados = [r for reclamos in st.session_state.asignaciones_grupos.values() for r in reclamos]
    df_disponibles = df_pendientes[~df_pendientes["ID Reclamo"].isin(asignados)]
    if df_disponibles.empty: st.info("🎉 No hay reclamos disponibles.")
    else:
        for idx, row in df_disponibles.iterrows():
            with st.container():
                col1, *cols_grupo = st.columns([4] + [1] * grupos_activos)
                col1.markdown(f"**📍 Sector {row['Sector']} - {row['Tipo de reclamo']} - {row['Nombre']}**")
                for i, grupo in enumerate(GRUPOS_POSIBLES[:grupos_activos]):
                    if cols_grupo[i].button(f"➡️{grupo[-1]}", key=f"btn_{grupo}_{row['ID Reclamo']}"):
                        st.session_state.asignaciones_grupos[grupo].append(row["ID Reclamo"])
                        st.rerun()
            with col1.expander("🔍 Ver detalles"): _mostrar_detalles_reclamo(row)
    return df_pendientes

def _mostrar_detalles_reclamo(reclamo):
    st.markdown(f"**🔢 Nº Cliente:** {reclamo['Nº Cliente']} | **👤 Nombre:** {reclamo['Nombre']}\n\n**📍 Dirección:** {reclamo['Dirección']} | **📞 Tel:** {reclamo['Teléfono']}\n\n**📝 Detalles:** {reclamo.get('Detalles', '')}")

def _format_fecha_reclamo(fecha):
    return fecha.strftime('%d/%m/%Y') if pd.notna(fecha) else "Sin fecha"

def _limpiar_asignaciones(df_reclamos):
    ids_validos = set(df_reclamos["ID Reclamo"].astype(str).unique())
    for g in st.session_state.asignaciones_grupos:
        st.session_state.asignaciones_grupos[g] = [rid for rid in st.session_state.asignaciones_grupos[g] if str(rid) in ids_validos]

def render_planificacion_grupos(df_reclamos, sheet_reclamos, user, df_clientes=None, sheet_clientes=None):
    if user.get('rol') != 'admin':
        st.warning("⚠️ Acceso denegado")
        return {'needs_refresh': False}
    st.subheader("📋 Asignación de reclamos a grupos")
    try:
        inicializar_estado_grupos()
        _limpiar_asignaciones(df_reclamos)
        grupos_activos = st.slider("🔢 Grupos activos", 1, 5, 2)
        modo = st.selectbox("📊 Modo de distribución", ["Manual", "Automática por sector (mejorada)", "Automática por tipo"])
        if modo != "Manual" and st.button("⚙️ Distribuir ahora"):
            if modo == "Automática por sector (mejorada)":
                st.session_state.simulacion_asignaciones = distribuir_por_sector_mejorado(df_reclamos, grupos_activos)
            else:
                st.session_state.simulacion_asignaciones = distribuir_por_tipo(df_reclamos, grupos_activos)
            st.session_state.vista_simulacion = True
        if st.session_state.get("vista_simulacion"):
            if st.button("💾 Confirmar asignación"):
                st.session_state.asignaciones_grupos = st.session_state.simulacion_asignaciones
                st.session_state.vista_simulacion = False
                st.rerun()
        if st.button("🔄 Refrescar"):
            _generar_uuids_faltantes(df_reclamos, df_clientes, sheet_reclamos, sheet_clientes)
            return {'needs_refresh': True}
        _mostrar_asignacion_tecnicos(grupos_activos)
        df_pendientes = _mostrar_reclamos_disponibles(df_reclamos, grupos_activos)
        if df_pendientes is not None:
            mats = _mostrar_reclamos_asignados(df_pendientes, grupos_activos)
            # IMPORTANTE: Pasamos df_clientes aquí
            cambios = _mostrar_acciones_finales(df_reclamos, sheet_reclamos, grupos_activos, mats, df_pendientes, df_clientes)
            return {'needs_refresh': cambios}
    except Exception as e:
        st.error(f"Error: {e}")
    return {'needs_refresh': False}

def _mostrar_reclamos_asignados(df_pendientes, grupos_activos):
    st.markdown("---")
    st.markdown("### 📌 Reclamos asignados")
    materiales_por_grupo = {}
    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        ids = st.session_state.asignaciones_grupos[grupo]
        tecs = st.session_state.tecnicos_grupos[grupo]
        st.markdown(f"#### 🔢 {grupo} - {', '.join(tecs) or 'Sin asignar'} ({len(ids)} reclamos)")
        recs_g = df_pendientes[df_pendientes["ID Reclamo"].isin(ids)]
        mats = _calcular_materiales_grupo(recs_g)
        materiales_por_grupo[grupo] = mats
        for rid in ids:
            if st.button(f"❌ Quitar {rid}", key=f"q_{grupo}_{rid}"):
                st.session_state.asignaciones_grupos[grupo].remove(rid)
                st.rerun()
    return materiales_por_grupo

def _calcular_materiales_grupo(reclamos_grupo):
    total = {}
    for _, row in reclamos_grupo.iterrows():
        tipo, sector = row["Tipo de reclamo"], str(row["Sector"])
        for mat, cant in MATERIALES_POR_RECLAMO.get(tipo, {}).items():
            key = f"router_{ROUTER_POR_SECTOR.get(sector, 'vsol')}" if "router" in mat else mat
            total[key] = total.get(key, 0) + cant
    return total

def _mostrar_acciones_finales(df_reclamos, sheet_reclamos, grupos_activos, materiales_por_grupo, df_pendientes, df_clientes):
    st.markdown("---")
    col1, col2 = st.columns(2)
    if col1.button("💾 Guardar y pasar a 'En curso'", use_container_width=True):
        return _guardar_cambios(df_reclamos, sheet_reclamos, grupos_activos)
    if col2.button("📄 Generar PDF de asignaciones", use_container_width=True):
        # LLAMADA A LA FUNCIÓN DE PDF CON DF_CLIENTES
        _generar_pdf_asignaciones(grupos_activos, materiales_por_grupo, df_pendientes, df_clientes)
    return False

def _guardar_cambios(df_reclamos, sheet_reclamos, grupos_activos):
    updates = []
    for g in GRUPOS_POSIBLES[:grupos_activos]:
        tecs = ", ".join(st.session_state.tecnicos_grupos[g]).upper()
        for rid in st.session_state.asignaciones_grupos[g]:
            fila = df_reclamos[df_reclamos["ID Reclamo"] == rid]
            if not fila.empty:
                idx = fila.index[0] + 2
                updates.append({"range": f"I{idx}", "values": [["En curso"]]})
                updates.append({"range": f"J{idx}", "values": [[tecs]]})
    if updates:
        success, _ = api_manager.safe_sheet_operation(batch_update_sheet, sheet_reclamos, updates, is_batch=True)
        if success:
            st.success("✅ Guardado")
            return True
    return False

# =================================================================
# FUNCIÓN DE PDF MODIFICADA CON CÓDIGO QR
# =================================================================
def _generar_pdf_asignaciones(grupos_activos, materiales_por_grupo, df_pendientes, df_clientes):
    """Genera un PDF con las asignaciones de grupos e integra Código QR de ubicación"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    hoy = datetime.now().strftime('%d/%m/%Y')

    # Normalizar df_clientes para búsqueda rápida por Nº Cliente
    df_c = df_clientes.copy()
    df_c["Nº Cliente"] = df_c["Nº Cliente"].astype(str).str.strip()

    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        reclamos_ids = st.session_state.asignaciones_grupos[grupo]
        if not reclamos_ids: continue

        tecnicos = st.session_state.tecnicos_grupos[grupo]
        agregar_pie_pdf(c, width, height)
        c.showPage()
        y = height - 40

        # Encabezado del grupo
        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, f"{grupo} - Técnicos: {', '.join(tecnicos)} ({hoy})")
        y -= 30

        for reclamo_id in reclamos_ids:
            reclamo_data = df_pendientes[df_pendientes["ID Reclamo"] == reclamo_id]
            if reclamo_data.empty: continue
            reclamo = reclamo_data.iloc[0]

            # --- Lógica de Búsqueda de Ubicación ---
            nro_cliente = str(reclamo['Nº Cliente']).strip()
            cliente_info = df_c[df_c["Nº Cliente"] == nro_cliente]
            
            lat, lon = None, None
            if not cliente_info.empty:
                lat = cliente_info.iloc[0].get("Latitud")
                lon = cliente_info.iloc[0].get("Longitud")

            # Dibujar Título del Reclamo
            c.setFont("Helvetica-Bold", 14)
            c.drawString(40, y, f"{reclamo['Nº Cliente']} - {reclamo['Nombre']} (Sect. {reclamo['Sector']})")
            
            # --- GENERAR QR SI HAY COORDENADAS ---
            if lat and lon and str(lat).strip() != "" and str(lon).strip() != "":
                try:
                    maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                    qr = qrcode.QRCode(version=1, box_size=10, border=1)
                    qr.add_data(maps_url)
                    qr.make(fit=True)
                    img_qr = qr.make_image(fill_color="black", back_color="white")
                    
                    qr_img_buffer = io.BytesIO()
                    img_qr.save(qr_img_buffer, format='PNG')
                    qr_img_buffer.seek(0)
                    
                    # Dibujar QR a la derecha (Margen derecho)
                    c.drawImage(qr_img_buffer, width - 110, y - 55, width=70, height=70)
                    c.setFont("Helvetica-Oblique", 7)
                    c.drawRightString(width - 40, y - 62, "UBICACIÓN GPS")
                except:
                    pass
            else:
                c.setFont("Helvetica-Oblique", 8)
                c.setFillColorRGB(0.5, 0.5, 0.5)
                c.drawRightString(width - 40, y, "Sin georeferencia")
                c.setFillColorRGB(0, 0, 0)

            # Datos del Reclamo
            y -= 15
            c.setFont("Helvetica", 11)
            f_p = reclamo['Fecha y hora'].strftime('%d/%m/%Y %H:%M') if pd.notna(reclamo['Fecha y hora']) else 'S/F'
            c.drawString(40, y, f"Fecha: {f_p}")
            y -= 12
            c.drawString(40, y, f"Dirección: {reclamo['Dirección']}")
            y -= 12
            c.drawString(40, y, f"Tel: {reclamo['Teléfono']} - Precinto: {reclamo.get('N° de Precinto', 'N/A')}")
            y -= 12
            c.drawString(40, y, f"Tipo: {reclamo['Tipo de reclamo']}")
            y -= 12
            det = str(reclamo['Detalles'])[:90] + "..." if len(str(reclamo['Detalles'])) > 90 else str(reclamo['Detalles'])
            c.drawString(40, y, f"Detalles: {det}")

            y -= 20
            c.line(40, y, width - 40, y)
            y -= 25

            if y < 130:
                agregar_pie_pdf(c, width, height)
                c.showPage()
                y = height - 40

        # Materiales al final
        mats = materiales_por_grupo.get(grupo, {})
        if mats:
            y -= 10
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, "Materiales estimados:")
            y -= 15
            c.setFont("Helvetica", 11)
            for m, cant in mats.items():
                c.drawString(40, y, f"- {cant} {m.replace('_', ' ').title()}")
                y -= 12

    c.save()
    buffer.seek(0)
    st.download_button(label="📄 Descargar PDF de asignaciones", data=buffer, file_name="asignaciones.pdf", mime="application/pdf")