# components/reclamos/planificacion.py

import io
import streamlit as st
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
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
        
        # Aplicar actualizaciones si hay alguna
        if updates_reclamos:
            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, 
                sheet_reclamos, 
                updates_reclamos, 
                is_batch=True
            )
            if success:
                uuids_generados = True
                st.success(f"✅ Se generaron {len(updates_reclamos)} UUIDs para reclamos")
            else:
                st.error(f"❌ Error al generar UUIDs para reclamos: {error}")
        
        if updates_clientes:
            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, 
                sheet_clientes, 
                updates_clientes, 
                is_batch=True
            )
            if success:
                uuids_generados = True
                st.success(f"✅ Se generaron {len(updates_clientes)} UUIDs para clientes")
            else:
                st.error(f"❌ Error al generar UUIDs para clientes: {error}")
        
        if not updates_reclamos and not updates_clientes:
            st.info("ℹ️ Todos los reclamos y clientes ya tienen UUIDs asignados")
            
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
    """
    Distribuye ZONAS COMPLETAS entre grupos, con redistribución opcional para muchos grupos
    """
    if not grupos or not zonas:
        return {g: [] for g in grupos}
    
    # Calcular reclamos por zona
    reclamos_por_zona = {}
    for zona in zonas:
        sectores_zona = SECTORES_VECINOS.get(zona, [])
        total_reclamos = len(df_reclamos[
            df_reclamos["Sector"].astype(str).isin(sectores_zona) &
            (df_reclamos["Estado"] == "Pendiente")
        ])
        reclamos_por_zona[zona] = total_reclamos
    
    # Ordenar zonas por cantidad de reclamos (descendente)
    zonas_ordenadas = sorted(zonas, key=lambda z: reclamos_por_zona[z], reverse=True)
    
    # Inicializar
    asignacion = {g: [] for g in grupos}
    carga_actual = {g: 0 for g in grupos}
    
    # Asignar zonas grandes primero
    for zona in zonas_ordenadas:
        # Encontrar el grupo con menor carga ACTUAL
        grupo_elegido = min(grupos, key=lambda g: carga_actual[g])
        
        # Asignar la ZONA COMPLETA a este grupo
        asignacion[grupo_elegido].append(zona)
        carga_actual[grupo_elegido] += reclamos_por_zona[zona]
    
    # VERIFICAR SI NECESITA REDISTRIBUCIÓN (solo para 4+ grupos con desbalance)
    if (permitir_redistribucion and 
        len(grupos) >= 4 and 
        _necesita_redistribucion(carga_actual)):
        
        asignacion = _redistribuir_inteligente(asignacion, carga_actual, reclamos_por_zona, grupos)
    
    return asignacion

def _necesita_redistribucion(carga_actual):
    """Determina si la distribución necesita ajuste"""
    cargas = list(carga_actual.values())
    return max(cargas) - min(cargas) > 2  # Diferencia mayor a 2 reclamos

def _redistribuir_inteligente(asignacion, carga_actual, reclamos_por_zona, grupos):
    """
    Redistribución inteligente para muchos grupos:
    - Solo mueve zonas pequeñas entre grupos vecinos geográficamente
    - Mantiene la integridad de las zonas (no las divide)
    """
    # Encontrar el grupo más cargado y el menos cargado
    grupo_max = max(carga_actual.items(), key=lambda x: x[1])[0]
    grupo_min = min(carga_actual.items(), key=lambda x: x[1])[0]
    
    # Buscar una zona pequeña del grupo max que sea compatible con grupo_min
    for zona in asignacion[grupo_max]:
        if reclamos_por_zona[zona] <= 2:  # Solo zonas muy pequeñas
            # Verificar compatibilidad geográfica
            if _son_zonas_compatibles(zona, asignacion[grupo_min]):
                # Mover la zona
                asignacion[grupo_max].remove(zona)
                asignacion[grupo_min].append(zona)
                carga_actual[grupo_max] -= reclamos_por_zona[zona]
                carga_actual[grupo_min] += reclamos_por_zona[zona]
                
                # Verificar si ya está balanceado
                if not _necesita_redistribucion(carga_actual):
                    break
    
    return asignacion

def _son_zonas_compatibles(zona, zonas_destino):
    """
    Verifica si una zona es compatible geográficamente con un conjunto de zonas
    """
    if not zonas_destino:
        return True  # Siempre compatible con grupo vacío
    
    for zona_dest in zonas_destino:
        if (zona in ZONAS_COMPATIBLES.get(zona_dest, []) or 
            zona_dest in ZONAS_COMPATIBLES.get(zona, [])):
            return True
    return False

def distribuir_por_sector_mejorado(df_reclamos, grupos_activos):
    """
    Distribución que respeta zonas completas
    """
    df_reclamos = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()
    grupos = GRUPOS_POSIBLES[:grupos_activos]
    asignaciones = {g: [] for g in grupos}

    zonas = list(SECTORES_VECINOS.keys())
    
    # Usar algoritmo que no divide zonas
    zonas_por_grupo = agrupar_zonas_completas(zonas, grupos, df_reclamos)
    
    # Crear mapa: sector → grupo (ahora todos los sectores de una zona van al mismo grupo)
    sector_grupo_map = {}
    for grupo, zonas_asignadas in zonas_por_grupo.items():
        for zona in zonas_asignadas:
            sectores = SECTORES_VECINOS.get(zona, [])
            for sector in sectores:
                sector_grupo_map[str(sector)] = grupo

    # Asignar reclamos
    for _, r in df_reclamos.iterrows():
        sector = str(r.get("Sector", "")).strip()
        grupo = sector_grupo_map.get(sector)
        if grupo:
            asignaciones[grupo].append(r["ID Reclamo"])
    
    return asignaciones

def _balancear_asignaciones(asignaciones, df_reclamos):
    """
    Rebalancea hasta lograr equidad fuerte:
    - Todos los grupos tendrán carga floor(N/G) o ceil(N/G).
    - Condición de corte: max(cargas) - min(cargas) <= 1
    """
    # Cargas iniciales
    carga_por_grupo = {g: len(recs) for g, recs in asignaciones.items()}

    def balanced(cargas):
        return (max(cargas.values()) - min(cargas.values())) <= 1

    # Repetir hasta que la distribución cumpla la condición
    intentos = 0
    max_intentos = 1000  # guarda por si hubiera un caso degenerado

    while not balanced(carga_por_grupo) and intentos < max_intentos:
        intentos += 1
        # Ordenar grupos por carga (menor → mayor)
        grupos_ordenados = sorted(carga_por_grupo.keys(), key=lambda g: carga_por_grupo[g])
        grupo_menos_cargado = grupos_ordenados[0]
        grupo_mas_cargado = grupos_ordenados[-1]

        # Si ya estamos a 1 de diferencia, cortar
        if carga_por_grupo[grupo_mas_cargado] - carga_por_grupo[grupo_menos_cargado] <= 1:
            break

        # Elegir un reclamo candidato del grupo más cargado que sea compatible con el menos cargado
        reclamo_a_transferir = _encontrar_reclamo_transferible(
            asignaciones[grupo_mas_cargado],
            grupo_mas_cargado,
            grupo_menos_cargado,
            df_reclamos,
            asignaciones
        )

        if not reclamo_a_transferir:
            # No encontramos uno compatible; salimos para evitar bucle infinito
            break

        # Transferir
        asignaciones[grupo_mas_cargado].remove(reclamo_a_transferir)
        asignaciones[grupo_menos_cargado].append(reclamo_a_transferir)

        # Actualizar cargas
        carga_por_grupo[grupo_mas_cargado] -= 1
        carga_por_grupo[grupo_menos_cargado] += 1

    return asignaciones

def _encontrar_reclamo_transferible(reclamos_grupo_origen, grupo_origen, grupo_destino, df_reclamos, asignaciones):
    """
    Elige el mejor reclamo para mover del grupo origen al destino:
    - Compatible con zonas del destino (prioridad alta)
    - Zonas más "centrales" (mayor conectividad) tienen más prioridad
    - Si el destino aún no tiene zonas, prioriza centralidad
    """
    # 1) Armar zonas actuales del destino
    zonas_destino = []
    reclamos_destino = df_reclamos[df_reclamos["ID Reclamo"].isin(asignaciones[grupo_destino])]
    for _, r in reclamos_destino.iterrows():
        sec = str(r["Sector"])
        for z, sectores in SECTORES_VECINOS.items():
            if sec in sectores and z not in zonas_destino:
                zonas_destino.append(z)

    # 2) Evaluar candidatos del origen
    mejor_id = None
    mejor_score = float("-inf")

    for reclamo_id in reclamos_grupo_origen:
        fila = df_reclamos[df_reclamos["ID Reclamo"] == reclamo_id]
        if fila.empty:
            continue

        sector = str(fila.iloc[0]["Sector"])
        zona_reclamo = None
        for z, sectores in SECTORES_VECINOS.items():
            if sector in sectores:
                zona_reclamo = z
                break

        if not zona_reclamo:
            continue

        # Puntaje base por centralidad (cuántas zonas son compatibles con esta zona)
        centralidad = len(ZONAS_COMPATIBLES.get(zona_reclamo, []))
        score = centralidad  # base

        if zonas_destino:
            # Compatible con al menos una zona del destino
            compatible = any(zona_reclamo in ZONAS_COMPATIBLES.get(zd, []) for zd in zonas_destino)
            if compatible:
                score += 100
            # Match exacto (misma zona) también suma
            if zona_reclamo in zonas_destino:
                score += 20
        else:
            # Sin zonas destino aún → priorizar centralidad pura
            score += 10  # pequeño empuje para desbloquear

        if score > mejor_score:
            mejor_score = score
            mejor_id = reclamo_id

    # 3) Fallback si no encontramos nada
    return mejor_id if mejor_id is not None else (reclamos_grupo_origen[0] if reclamos_grupo_origen else None)

def distribuir_por_tipo(df_reclamos, grupos_activos):
    df_reclamos = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()  # <--- agregado

    grupos = GRUPOS_POSIBLES[:grupos_activos]
    asignaciones = {g: [] for g in grupos}
    reclamos = df_reclamos.to_dict("records")
    reclamos_por_tipo = {}

    for r in reclamos:
        tipo = r.get("Tipo de reclamo", "Otro")
        reclamos_por_tipo.setdefault(tipo, []).append(r["ID Reclamo"])

    i = 0
    for tipo, ids in reclamos_por_tipo.items():
        for rid in ids:
            grupo = grupos[i % grupos_activos]
            asignaciones[grupo].append(rid)
            i += 1

    return asignaciones

def _mostrar_asignacion_tecnicos(grupos_activos):
    """Muestra la interfaz para asignar técnicos a grupos"""
    st.markdown("### 👷 Asignar técnicos a cada grupo")
    for grupo in list(st.session_state.tecnicos_grupos.keys())[:grupos_activos]:
        st.session_state.tecnicos_grupos[grupo] = st.multiselect(
            f"{grupo} - Técnicos asignados",
            TECNICOS_DISPONIBLES,
            default=st.session_state.tecnicos_grupos[grupo],
            key=f"tecnicos_{grupo}"
        )


def _mostrar_reclamos_disponibles(df_reclamos, grupos_activos):
    """Muestra reclamos disponibles para asignar"""
    st.markdown("---")
    st.markdown("### 📋 Reclamos pendientes para asignar")

    df_reclamos.columns = df_reclamos.columns.str.strip()
    df_reclamos["ID Reclamo"] = df_reclamos["ID Reclamo"].astype(str).str.strip()
    df_reclamos["Fecha y hora"] = pd.to_datetime(df_reclamos["Fecha y hora"], dayfirst=True, errors='coerce')

    # Verificamos si hay IDs vacíos
    if df_reclamos["ID Reclamo"].eq("").any():
        st.error("❌ Hay reclamos con ID vacío. Por favor, corregílos en la hoja antes de continuar.")
        return None

    df_pendientes = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()

    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        filtro_sector = st.selectbox("Filtrar por sector", ["Todos"] + sorted(SECTORES_DISPONIBLES),
                                     format_func=lambda x: f"Sector {x}" if x != "Todos" else x)
    with col2:
        filtro_tipo = st.selectbox("Filtrar por tipo de reclamo", ["Todos"] + sorted(df_pendientes["Tipo de reclamo"].dropna().unique()))

    if filtro_sector != "Todos":
        df_pendientes = df_pendientes[df_pendientes["Sector"] == str(filtro_sector)]
    if filtro_tipo != "Todos":
        df_pendientes = df_pendientes[df_pendientes["Tipo de reclamo"] == filtro_tipo]

    orden = st.selectbox("🔃 Ordenar reclamos por:", ["Fecha más reciente", "Sector", "Tipo de reclamo"])
    if orden == "Fecha más reciente":
        df_pendientes = df_pendientes.sort_values("Fecha y hora", ascending=False)
    elif orden == "Sector":
        df_pendientes = df_pendientes.sort_values("Sector")
    elif orden == "Tipo de reclamo":
        df_pendientes = df_pendientes.sort_values("Tipo de reclamo")

    asignados = [r for reclamos in st.session_state.asignaciones_grupos.values() for r in reclamos]
    df_disponibles = df_pendientes[~df_pendientes["ID Reclamo"].isin(asignados)]

    if df_disponibles.empty:
        st.info("🎉 No hay reclamos pendientes disponibles.")
    else:
        for idx, row in df_disponibles.iterrows():
            with st.container():
                col1, *cols_grupo = st.columns([4] + [1] * grupos_activos)
                resumen = f"📍 Sector {row['Sector']} - {row['Tipo de reclamo'].capitalize()} - {_format_fecha_reclamo(row['Fecha y hora'])}"
                col1.markdown(f"**{resumen}**")

            for i, grupo in enumerate(GRUPOS_POSIBLES[:grupos_activos]):
                tecnicos = st.session_state.tecnicos_grupos[grupo]
                tecnicos_str = ", ".join(tecnicos[:2]) + ("..." if len(tecnicos) > 2 else "") if tecnicos else "Sin técnicos"
                button_key = f"asignar_{grupo}_{row['ID Reclamo']}_{idx}"
                if cols_grupo[i].button(f"➡️{grupo[-1]} ({tecnicos_str})", key=button_key):
                    if row["ID Reclamo"] not in asignados:
                        st.session_state.asignaciones_grupos[grupo].append(row["ID Reclamo"])
                        st.rerun()

            with col1.expander("🔍 Ver detalles"):
                _mostrar_detalles_reclamo(row)

        st.divider()

    return df_pendientes


def _mostrar_detalles_reclamo(reclamo):
    """Muestra los detalles de un reclamo"""
    st.markdown(f"""
    **🔢 Nº Cliente:** {reclamo['Nº Cliente']}  
    **👤 Nombre:** {reclamo['Nombre']}  
    **📍 Dirección:** {reclamo['Dirección']}  
    **📞 Teléfono:** {reclamo['Teléfono']}  
    **📅 Fecha completa:** {reclamo['Fecha y hora'].strftime('%d/%m/%Y %H:%M') if not pd.isna(reclamo['Fecha y hora']) else 'Sin fecha'}  
    """)
    if reclamo.get("Detalles"):
        st.markdown(f"**📝 Detalles:** {reclamo['Detalles'][:250]}{'...' if len(reclamo['Detalles']) > 250 else ''}")


def _format_fecha_reclamo(fecha):
    """Formatea la fecha del reclamo para visualización"""
    if pd.isna(fecha):
        return "Sin fecha"
    try:
        return fecha.strftime('%d/%m/%Y')
    except:
        return "Fecha inválida"

def _limpiar_asignaciones(df_reclamos):
    ids_validos = set(df_reclamos["ID Reclamo"].astype(str).unique())
    for grupo in st.session_state.asignaciones_grupos:
        st.session_state.asignaciones_grupos[grupo] = [
            id for id in st.session_state.asignaciones_grupos[grupo] 
            if str(id) in ids_validos
        ]

def render_planificacion_grupos(df_reclamos, sheet_reclamos, user, df_clientes=None, sheet_clientes=None):
    if user.get('rol') != 'admin':
        st.warning("⚠️ Solo los administradores pueden acceder a esta sección")
        return {'needs_refresh': False}

    st.subheader("📋 Asignación de reclamos a grupos de trabajo")

    try:
        inicializar_estado_grupos()
        _limpiar_asignaciones(df_reclamos)

        grupos_activos = st.slider("🔢 Cantidad de grupos de trabajo activos", 1, 5, 2)

        modo_distribucion = st.selectbox(
            "📊 Elegí el modo de distribución",
            ["Manual", "Automática por sector (mejorada)", "Automática por tipo de reclamo"],
            index=0
        )

        if modo_distribucion != "Manual":
            if st.button("⚙️ Distribuir reclamos ahora"):
                if modo_distribucion == "Automática por sector (mejorada)":
                    st.session_state.simulacion_asignaciones = distribuir_por_sector_mejorado(df_reclamos, grupos_activos)

                    # Mostrar zonas asignadas por grupo con el algoritmo mejorado
                    zonas_por_grupo = agrupar_zonas_completas(
                        list(SECTORES_VECINOS.keys()),
                        GRUPOS_POSIBLES[:grupos_activos],
                        df_reclamos
                    )
                    st.markdown("### 🗺️ Zonas asignadas por grupo (mejorado):")
                    for grupo, zonas_asignadas in zonas_por_grupo.items():
                        st.markdown(f"- **{grupo}** cubre: {', '.join(zonas_asignadas)}")

                else:
                    st.session_state.simulacion_asignaciones = distribuir_por_tipo(df_reclamos, grupos_activos)

                st.session_state.vista_simulacion = True
                st.success("✅ Distribución previa generada. Revisala antes de guardar.")

        if st.session_state.get("vista_simulacion"):
            st.subheader("🗂️ Distribución previa de reclamos")
            for grupo, reclamos in st.session_state.simulacion_asignaciones.items():
                st.markdown(f"### 📦 {grupo} - {len(reclamos)} reclamos")
                for rid in reclamos:
                    row = df_reclamos[df_reclamos["ID Reclamo"] == rid]
                    if not row.empty:
                        r = row.iloc[0]
                        st.markdown(f"- {r['Nº Cliente']} | {r['Tipo de reclamo']} | Sector {r['Sector']}")

            # Solo opción de confirmar, sin generar PDF en la simulación
            if st.button("💾 Confirmar y guardar esta asignación"):
                for g in GRUPOS_POSIBLES:
                    st.session_state.asignaciones_grupos[g] = []
                        
                st.session_state.asignaciones_grupos = st.session_state.simulacion_asignaciones
                st.session_state.vista_simulacion = False
                st.success("✅ Asignaciones aplicadas.")
                st.rerun()

        if st.button("🔄 Refrescar reclamos"):
            st.cache_data.clear()
            
            # Generar UUIDs faltantes si se tienen los datos necesarios
            if df_clientes is not None and sheet_clientes is not None:
                with st.spinner("Verificando y generando UUIDs faltantes..."):
                    _generar_uuids_faltantes(df_reclamos, df_clientes, sheet_reclamos, sheet_clientes)
            
            return {'needs_refresh': True}

        _mostrar_asignacion_tecnicos(grupos_activos)
        df_pendientes = _mostrar_reclamos_disponibles(df_reclamos, grupos_activos)

        if df_pendientes is not None:
            materiales_por_grupo = _mostrar_reclamos_asignados(df_pendientes, grupos_activos)
            cambios = _mostrar_acciones_finales(
                df_reclamos, sheet_reclamos, 
                grupos_activos, materiales_por_grupo, df_pendientes
            )
            return {'needs_refresh': cambios}

        return {'needs_refresh': False}

    except Exception as e:
        st.error(f"❌ Error en la planificación: {str(e)}")
        if 'DEBUG_MODE' in globals() and DEBUG_MODE:
            st.exception(e)
        return {'needs_refresh': False}

def _mostrar_reclamos_asignados(df_pendientes, grupos_activos):
    """Muestra los reclamos asignados por grupo"""
    st.markdown("---")
    st.markdown("### 📌 Reclamos asignados por grupo")

    materiales_por_grupo = {}

    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        reclamos_ids = st.session_state.asignaciones_grupos[grupo]
        tecnicos = st.session_state.tecnicos_grupos[grupo]

        st.markdown(f"#### 🔢 {grupo} - Técnicos: {', '.join(tecnicos) if tecnicos else 'Sin asignar'} ({len(reclamos_ids)} reclamos)")
        reclamos_grupo = df_pendientes[df_pendientes["ID Reclamo"].isin(reclamos_ids)]

        if not reclamos_grupo.empty:
            resumen_tipos = " - ".join([f"{v} {k}" for k, v in reclamos_grupo["Tipo de reclamo"].value_counts().items()])
            sectores = ", ".join(sorted(set(reclamos_grupo["Sector"].astype(str))))
            st.markdown(resumen_tipos)
            st.markdown(f"Sectores: {sectores}")

        materiales_total = _calcular_materiales_grupo(reclamos_grupo)
        materiales_por_grupo[grupo] = materiales_total

        if materiales_total:
            st.markdown("🛠️ **Materiales mínimos estimados:**")
            for mat, cant in materiales_total.items():
                st.markdown(f"- {cant} {mat.replace('_', ' ').title()}")

        for idx, reclamo_id in enumerate(reclamos_ids):
            reclamo_data = df_pendientes[df_pendientes["ID Reclamo"] == reclamo_id]
            col1, col2 = st.columns([5, 1])

            if not reclamo_data.empty:
                row = reclamo_data.iloc[0]
                resumen = f"📍 Sector {row['Sector']} - {row['Tipo de reclamo'].capitalize()} - {_format_fecha_reclamo(row['Fecha y hora'])}"
                col1.markdown(f"**{resumen}**")
            else:
                col1.markdown(f"**Reclamo ID: {reclamo_id} (ya no está pendiente)**")

            if col2.button("❌ Quitar", key=f"quitar_{grupo}_{reclamo_id}_{idx}"):
                st.session_state.asignaciones_grupos[grupo].remove(reclamo_id)
                st.rerun()

            st.divider()

    return materiales_por_grupo


def _calcular_materiales_grupo(reclamos_grupo):
    """Calcula los materiales necesarios para un grupo de trabajo"""
    materiales_total = {}
    for _, row in reclamos_grupo.iterrows():
        tipo = row["Tipo de reclamo"]
        sector = str(row["Sector"])
        materiales_tipo = MATERIALES_POR_RECLAMO.get(tipo, {})
        for mat, cant in materiales_tipo.items():
            key = mat
            if "router" in mat:
                marca = ROUTER_POR_SECTOR.get(sector, "vsol")
                key = f"router_{marca}"
            materiales_total[key] = materiales_total.get(key, 0) + cant
    return materiales_total


def _mostrar_acciones_finales(df_reclamos, sheet_reclamos, grupos_activos, materiales_por_grupo, df_pendientes):
    """Muestra botones de acción final y maneja su lógica"""
    st.markdown("---")
    cambios = False

    col1, col2 = st.columns(2)

    if col1.button("💾 Guardar cambios y pasar a 'En curso'", use_container_width=True):
        cambios = _guardar_cambios(df_reclamos, sheet_reclamos, grupos_activos)

    if col2.button("📄 Generar PDF de asignaciones por grupo", use_container_width=True):
        _generar_pdf_asignaciones(grupos_activos, materiales_por_grupo, df_pendientes)

    return cambios


def _guardar_cambios(df_reclamos, sheet_reclamos, grupos_activos):
    """Guarda los cambios en la hoja de cálculo"""
    errores = []
    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        if st.session_state.asignaciones_grupos[grupo] and not st.session_state.tecnicos_grupos[grupo]:
            errores.append(grupo)

    if errores:
        st.warning(f"⚠️ Los siguientes grupos tienen reclamos asignados pero sin técnicos: {', '.join(errores)}")
        return False

    with st.spinner("Actualizando reclamos..."):
        updates = []
        notificaciones = []

        for grupo in GRUPOS_POSIBLES[:grupos_activos]:
            tecnicos = st.session_state.tecnicos_grupos[grupo]
            reclamos_ids = st.session_state.asignaciones_grupos[grupo]
            tecnicos_str = ", ".join(tecnicos).upper() if tecnicos else ""

            if reclamos_ids:
                for reclamo_id in reclamos_ids:
                    fila = df_reclamos[df_reclamos["ID Reclamo"] == reclamo_id]
                    if not fila.empty:
                        index = fila.index[0] + 2
                        updates.append({"range": f"I{index}", "values": [["En curso"]]})
                        updates.append({"range": f"J{index}", "values": [[tecnicos_str]]})

                notificaciones.append({
                    "grupo": grupo,
                    "tecnicos": tecnicos_str,
                    "cantidad": len(reclamos_ids)
                })

        if updates:
            success, error = api_manager.safe_sheet_operation(batch_update_sheet, sheet_reclamos, updates, is_batch=True)
            if success:
                st.success("✅ Reclamos actualizados correctamente en la hoja.")
                if 'notification_manager' in st.session_state:
                    for n in notificaciones:
                        mensaje = f"📋 Se asignaron {n['cantidad']} reclamos a {n['grupo']} (Técnicos: {n['tecnicos']})."
                        st.session_state.notification_manager.add(
                            notification_type="reclamo_asignado",
                            message=mensaje,
                            user_target="all"
                        )
                return True
            else:
                st.error("❌ Error al actualizar: " + str(error))

    return False

def _generar_pdf_asignaciones(grupos_activos, materiales_por_grupo, df_pendientes):
    """Genera un PDF con las asignaciones de grupos"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40
    hoy = datetime.now().strftime('%d/%m/%Y')

    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        reclamos_ids = st.session_state.asignaciones_grupos[grupo]
        if not reclamos_ids:
            continue

        tecnicos = st.session_state.tecnicos_grupos[grupo]
        agregar_pie_pdf(c, width, height)
        c.showPage()
        y = height - 40

        tipos = df_pendientes[df_pendientes["ID Reclamo"].isin(reclamos_ids)]["Tipo de reclamo"].value_counts()
        resumen_tipos = " - ".join([f"{v} {k}" for k, v in tipos.items()])

        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, f"{grupo} - Técnicos: {', '.join(tecnicos)} (Asignado el {hoy})")
        y -= 20
        c.setFont("Helvetica", 12)
        c.drawString(40, y, resumen_tipos)
        y -= 25

        for reclamo_id in reclamos_ids:
            reclamo_data = df_pendientes[df_pendientes["ID Reclamo"] == reclamo_id]
            if not reclamo_data.empty:
                reclamo = reclamo_data.iloc[0]
                c.setFont("Helvetica-Bold", 14)
                
                # Nueva línea: Nombre del cliente con sector entre paréntesis
                nombre_linea = f"{reclamo['Nº Cliente']} - {reclamo['Nombre']} ({reclamo['Sector']})"
                c.drawString(40, y, nombre_linea)
                y -= 15
                
                c.setFont("Helvetica", 11)

                fecha_pdf = reclamo['Fecha y hora'].strftime('%d/%m/%Y %H:%M') if not pd.isna(reclamo['Fecha y hora']) else 'Sin fecha'
                
                # Líneas modificadas según el formato solicitado
                lineas = [
                    f"Fecha: {fecha_pdf}",
                    f"Dirección: {reclamo['Dirección']}",
                    f"Tel: {reclamo['Teléfono']} - Precinto: {reclamo.get('N° de Precinto', 'N/A')}",
                    f"Tipo: {reclamo['Tipo de reclamo']}",
                    f"Detalles: {reclamo['Detalles'][:100]}..." if len(reclamo['Detalles']) > 100 else f"Detalles: {reclamo['Detalles']}",
                ]
                for linea in lineas:
                    c.drawString(40, y, linea)
                    y -= 12

                y -= 8
                c.line(40, y, width - 40, y)
                y -= 15

                if y < 100:
                    agregar_pie_pdf(c, width, height)
                    c.showPage()
                    y = height - 40
                    c.setFont("Helvetica-Bold", 16)
                    c.drawString(40, y, f"{grupo} (cont.)")
                    y -= 25

        materiales = materiales_por_grupo.get(grupo, {})
        if materiales:
            y -= 10
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, "Materiales mínimos estimados:")
            y -= 15
            c.setFont("Helvetica", 11)
            for mat, cant in materiales.items():
                c.drawString(40, y, f"- {cant} {mat.replace('_', ' ').title()}")
                y -= 12

        y -= 20

    agregar_pie_pdf(c, width, height)
    c.save()
    buffer.seek(0)

    st.download_button(
        label="📄 Descargar PDF de asignaciones",
        data=buffer,
        file_name="asignaciones_grupos.pdf",
        mime="application/pdf"
    )
    