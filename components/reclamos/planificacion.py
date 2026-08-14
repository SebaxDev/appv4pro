# components/reclamos/planificacion.py

import io
import streamlit as st
import pandas as pd
import math
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
import qrcode
from reportlab.lib.utils import ImageReader
from PIL import Image

GRUPOS_POSIBLES = [f"Grupo {letra}" for letra in "ABCDEF"]

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
                        "range": f"P{row.name + 2}",
                        "values": [[nuevo_uuid]]
                    })

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
                        "range": f"G{row.name + 2}",
                        "values": [[nuevo_uuid]]
                    })

        if updates_reclamos:
            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, sheet_reclamos, updates_reclamos, is_batch=True
            )
            if success:
                uuids_generados = True
                st.success(f"✅ Se generaron {len(updates_reclamos)} UUIDs para reclamos")
            else:
                st.error(f"❌ Error al generar UUIDs para reclamos: {error}")

        if updates_clientes:
            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet, sheet_clientes, updates_clientes, is_batch=True
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
    "Zona 2": ["6", "7", "8"],
    "Zona 3": ["5", "9", "10"],
    "Zona 4": ["11", "12", "13", "14"],
    "Zona 5": ["15", "16", "17"]
}

ZONAS_COMPATIBLES = {
    "Zona 1": ["Zona 3"],
    "Zona 2": ["Zona 3"],
    "Zona 3": ["Zona 1", "Zona 2", "Zona 4"],
    "Zona 4": ["Zona 3", "Zona 5"],
    "Zona 5": ["Zona 4"],
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

# ============================================================================
# FUNCIONES AUXILIARES DE COMPATIBILIDAD GEOGRÁFICA (CLIQUES)
# ============================================================================

def _sector_a_zona(sector):
    """Dado un sector (string), devuelve su zona."""
    sec = str(sector).strip()
    for zona, sectores in SECTORES_VECINOS.items():
        if sec in sectores:
            return zona
    return None

def _obtener_zonas_de_reclamos(reclamos_ids, df_reclamos):
    """Devuelve el conjunto de zonas presentes en una lista de reclamos."""
    zonas = set()
    for rid in reclamos_ids:
        fila = df_reclamos[df_reclamos["ID Reclamo"] == rid]
        if not fila.empty:
            zona = _sector_a_zona(fila.iloc[0]["Sector"])
            if zona:
                zonas.add(zona)
    return zonas

def _zonas_son_compatibles(zona_a, zona_b):
    """Verifica compatibilidad bidireccional entre dos zonas."""
    if zona_a == zona_b:
        return True
    compat_a = ZONAS_COMPATIBLES.get(zona_a, [])
    compat_b = ZONAS_COMPATIBLES.get(zona_b, [])
    return (zona_b in compat_a) or (zona_a in compat_b)

def _zona_es_compatible_con_conjunto(zona, zonas_conjunto):
    """
    REGLA DE CLIQUE: una zona es compatible con un conjunto de zonas
    solo si es compatible con CADA UNA de las zonas del conjunto.
    """
    if not zonas_conjunto:
        return True
    for z in zonas_conjunto:
        if not _zonas_son_compatibles(zona, z):
            return False
    return True


# ============================================================================
# FASE 1: ASIGNACIÓN DE ZONAS COMPLETAS A GRUPOS
# ============================================================================

def agrupar_zonas_completas(zonas, grupos, df_reclamos, permitir_redistribucion=True):
    """
    Asigna ZONAS COMPLETAS a grupos usando greedy con penalización por incompatibilidad.
    Garantiza que cada grupo reciba zonas que formen un clique geográfico.
    """
    if not grupos or not zonas:
        return {g: [] for g in grupos}

    # Calcular reclamos por zona
    reclamos_por_zona = {}
    for zona in zonas:
        sectores_zona = SECTORES_VECINOS.get(zona, [])
        total = len(df_reclamos[
            df_reclamos["Sector"].astype(str).isin(sectores_zona) &
            (df_reclamos["Estado"] == "Pendiente")
        ])
        reclamos_por_zona[zona] = total

    total_reclamos = sum(reclamos_por_zona.values())
    carga_objetivo = total_reclamos / len(grupos) if grupos else 0

    # Ordenar zonas de mayor a menor
    zonas_ordenadas = sorted(zonas, key=lambda z: reclamos_por_zona[z], reverse=True)

    asignacion = {g: [] for g in grupos}
    carga_actual = {g: 0 for g in grupos}

    for zona in zonas_ordenadas:
        def score(grupo):
            penalizacion = 0
            zonas_grupo = asignacion[grupo]
            # Si la zona no es compatible con TODAS las zonas del grupo, penalizar fuerte
            if not _zona_es_compatible_con_conjunto(zona, zonas_grupo):
                penalizacion += 1000
            return carga_actual[grupo] + penalizacion

        grupo_elegido = min(grupos, key=score)
        asignacion[grupo_elegido].append(zona)
        carga_actual[grupo_elegido] += reclamos_por_zona[zona]

    # Redistribución multi-ronda de ZONAS COMPLETAS
    if permitir_redistribucion:
        for _ in range(10):
            if not _necesita_redistribucion(carga_actual, tolerancia=1):
                break
            asignacion, carga_actual = _redistribuir_zonas(
                asignacion, carga_actual, reclamos_por_zona, grupos, carga_objetivo
            )

    return asignacion

def _necesita_redistribucion(carga_actual, tolerancia=1):
    cargas = list(carga_actual.values())
    if not cargas:
        return False
    return max(cargas) - min(cargas) > tolerancia

def _redistribuir_zonas(asignacion, carga_actual, reclamos_por_zona, grupos, carga_objetivo):
    """Intenta mover una zona completa del grupo más cargado al menos cargado."""
    grupo_max = max(carga_actual.items(), key=lambda x: x[1])[0]
    grupo_min = min(carga_actual.items(), key=lambda x: x[1])[0]

    if carga_actual[grupo_max] - carga_actual[grupo_min] <= 1:
        return asignacion, carga_actual

    umbral = max(2, int(carga_objetivo * 0.7))

    # Ordenar zonas del grupo max de más pequeña a más grande
    candidatas = sorted(
        [(z, reclamos_por_zona.get(z, 0)) for z in asignacion[grupo_max]],
        key=lambda x: x[1]
    )

    for zona, size in candidatas:
        # Verificar que la zona sea compatible con TODAS las zonas del grupo min
        if _zona_es_compatible_con_conjunto(zona, asignacion[grupo_min]):
            if carga_actual[grupo_min] + size <= carga_objetivo + 2:
                asignacion[grupo_max].remove(zona)
                asignacion[grupo_min].append(zona)
                carga_actual[grupo_max] -= size
                carga_actual[grupo_min] += size
                break

    return asignacion, carga_actual


# ============================================================================
# FASE 2: BALANCEO POR RECLAMO INDIVIDUAL (CON CLIQUE ESTRICTO)
# ============================================================================

def _balancear_asignaciones(asignaciones, df_reclamos):
    """
    Rebalancea moviendo UN reclamo a la vez del grupo más cargado al menos cargado.
    CADA movimiento respeta la regla de clique: la zona del reclamo movido debe ser
    compatible con TODAS las zonas ya presentes en el grupo destino.
    """
    carga_por_grupo = {g: len(recs) for g, recs in asignaciones.items()}

    def balanced(cargas):
        return (max(cargas.values()) - min(cargas.values())) <= 1

    intentos = 0
    max_intentos = 1000

    while not balanced(carga_por_grupo) and intentos < max_intentos:
        intentos += 1

        grupos_ordenados = sorted(carga_por_grupo.keys(), key=lambda g: carga_por_grupo[g])
        grupo_menos_cargado = grupos_ordenados[0]
        grupo_mas_cargado = grupos_ordenados[-1]

        if carga_por_grupo[grupo_mas_cargado] - carga_por_grupo[grupo_menos_cargado] <= 1:
            break

        reclamo_a_transferir = _encontrar_reclamo_transferible(
            asignaciones[grupo_mas_cargado],
            grupo_mas_cargado,
            grupo_menos_cargado,
            df_reclamos,
            asignaciones
        )

        if not reclamo_a_transferir:
            break

        asignaciones[grupo_mas_cargado].remove(reclamo_a_transferir)
        asignaciones[grupo_menos_cargado].append(reclamo_a_transferir)

        carga_por_grupo[grupo_mas_cargado] -= 1
        carga_por_grupo[grupo_menos_cargado] += 1

    return asignaciones

def _encontrar_reclamo_transferible(reclamos_grupo_origen, grupo_origen, grupo_destino, df_reclamos, asignaciones):
    """
    Elige el mejor reclamo para mover respetando la REGLA DE CLIQUE:
    la zona del reclamo debe ser compatible con TODAS las zonas del grupo destino.
    """
    zonas_destino = _obtener_zonas_de_reclamos(asignaciones[grupo_destino], df_reclamos)

    mejor_id = None
    mejor_score = float("-inf")

    for reclamo_id in reclamos_grupo_origen:
        fila = df_reclamos[df_reclamos["ID Reclamo"] == reclamo_id]
        if fila.empty:
            continue

        zona_reclamo = _sector_a_zona(fila.iloc[0]["Sector"])
        if not zona_reclamo:
            continue

        # REGLA DE CLIQUE: la zona del reclamo debe ser compatible con TODAS las zonas del destino
        if not _zona_es_compatible_con_conjunto(zona_reclamo, zonas_destino):
            continue

        # Score: priorizar zonas centrales y zonas que ya están en el destino
        centralidad = len(ZONAS_COMPATIBLES.get(zona_reclamo, []))
        score = centralidad * 10

        if zona_reclamo in zonas_destino:
            score += 100  # Misma zona = ideal

        # Priorizar zonas centrales para grupos vacíos
        if not zonas_destino:
            if zona_reclamo == "Zona 3":
                score += 200  # Zona 3 es el hub central
            elif zona_reclamo in ("Zona 2", "Zona 4"):
                score += 50

        if score > mejor_score:
            mejor_score = score
            mejor_id = reclamo_id

    return mejor_id


# ============================================================================
# FASE 3: RED DE SEGURIDAD (CON CLIQUE ESTRICTO)
# ============================================================================

def _forzar_balanceo_final(asignaciones, df_reclamos, grupos_activos):
    """
    Red de seguridad que fuerza el balanceo sin romper la coherencia geográfica.
    NUNCA mezcla zonas incompatibles en el mismo grupo.
    """
    grupos = GRUPOS_POSIBLES[:grupos_activos]

    for _ in range(100):
        carga = {g: len(asignaciones[g]) for g in grupos}
        max_carga = max(carga.values())
        min_carga = min(carga.values())

        if max_carga - min_carga <= 1:
            break

        grupo_max = max(grupos, key=lambda g: carga[g])
        grupo_min = min(grupos, key=lambda g: carga[g])

        # Buscar reclamo compatible estrictamente
        candidato = _encontrar_reclamo_transferible(
            asignaciones[grupo_max],
            grupo_max,
            grupo_min,
            df_reclamos,
            asignaciones
        )

        if not candidato:
            # Si no hay compatible, intentar con otros grupos origen (no solo el más cargado)
            candidato = _buscar_reclamo_compatible_en_otros_grupos(
                asignaciones, grupo_min, df_reclamos, grupos
            )

        if not candidato:
            break

        # Encontrar de qué grupo sacar el candidato
        for g in grupos:
            if candidato in asignaciones[g]:
                asignaciones[g].remove(candidato)
                asignaciones[grupo_min].append(candidato)
                break

    return asignaciones

def _buscar_reclamo_compatible_en_otros_grupos(asignaciones, grupo_destino, df_reclamos, grupos):
    """
    Cuando el grupo más cargado no tiene reclamos compatibles para el destino,
    busca en otros grupos (empezando por los más cargados) un reclamo que sí sea compatible.
    """
    zonas_destino = _obtener_zonas_de_reclamos(asignaciones[grupo_destino], df_reclamos)

    # Ordenar grupos por carga descendente (más cargados primero)
    grupos_ordenados = sorted(grupos, key=lambda g: len(asignaciones[g]), reverse=True)

    for grupo_origen in grupos_ordenados:
        if grupo_origen == grupo_destino:
            continue

        for reclamo_id in asignaciones[grupo_origen]:
            fila = df_reclamos[df_reclamos["ID Reclamo"] == reclamo_id]
            if fila.empty:
                continue

            zona_reclamo = _sector_a_zona(fila.iloc[0]["Sector"])
            if not zona_reclamo:
                continue

            if _zona_es_compatible_con_conjunto(zona_reclamo, zonas_destino):
                return reclamo_id

    return None

# ============================================================================
# FASE 4: ORDENAMIENTO POR RUTA GEOGRÁFICA (HAversine + Nearest Neighbor)
# ============================================================================

def _haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia en kilómetros entre dos puntos (lat, lon) usando la fórmula de Haversine.
    """
    R = 6371.0  # Radio de la Tierra en km

    try:
        lat1_rad = math.radians(float(lat1))
        lon1_rad = math.radians(float(lon1))
        lat2_rad = math.radians(float(lat2))
        lon2_rad = math.radians(float(lon2))
    except (ValueError, TypeError):
        return float('inf')

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def _obtener_coordenadas_reclamo(reclamo_id, df_reclamos, df_clientes):
    """
    Busca latitud y longitud de un reclamo:
    1. Primero en la hoja de reclamos (columnas Plan, etc. no tienen geo)
    2. Luego en la hoja de Clientes buscando por Nº Cliente
    Retorna (lat, lon) o (None, None) si no hay datos.
    """
    try:
        fila_reclamo = df_reclamos[df_reclamos["ID Reclamo"] == reclamo_id]
        if fila_reclamo.empty:
            return None, None

        num_cliente = str(fila_reclamo.iloc[0].get("Nº Cliente", "")).strip()
        if not num_cliente:
            return None, None

        if df_clientes is None or df_clientes.empty:
            return None, None

        cliente = df_clientes[
            df_clientes["Nº Cliente"].astype(str).str.strip() == num_cliente
        ]

        if cliente.empty:
            return None, None

        fila_cliente = cliente.iloc[0]
        lat = str(fila_cliente.get("Latitud", "")).strip()
        lon = str(fila_cliente.get("Longitud", "")).strip()

        if not lat or not lon or lat.lower() in ("nan", "none", "") or lon.lower() in ("nan", "none", ""):
            return None, None

        # Validar que sean números
        float(lat)
        float(lon)

        return lat, lon
    except Exception:
        return None, None

def _ordenar_reclamos_por_ruta(reclamos_ids, df_reclamos, df_clientes):
    """
    Ordena los reclamos de un grupo siguiendo la ruta más corta (Nearest Neighbor).
    Los reclamos SIN geolocalización quedan al final, ordenados por sector.
    Retorna la lista de IDs reordenada.
    """
    if not reclamos_ids or len(reclamos_ids) <= 1:
        return list(reclamos_ids)

    # Separar reclamos con y sin geolocalización
    con_geo = []   # [(id, lat, lon, sector), ...]
    sin_geo = []   # [(id, sector), ...]

    for rid in reclamos_ids:
        lat, lon = _obtener_coordenadas_reclamo(rid, df_reclamos, df_clientes)
        fila = df_reclamos[df_reclamos["ID Reclamo"] == rid]
        sector = str(fila.iloc[0]["Sector"]) if not fila.empty else "99"

        if lat is not None and lon is not None:
            con_geo.append((rid, float(lat), float(lon), sector))
        else:
            sin_geo.append((rid, sector))

    # Si no hay ninguno con geolocalización, ordenar solo por sector
    if not con_geo:
        sin_geo.sort(key=lambda x: x[1])
        return [rid for rid, _ in sin_geo]

    # Nearest Neighbor: empezar por el punto más al norte (mayor latitud)
    # o el más cercano al centroide del grupo
    # Estrategia: empezar por el punto con mayor latitud (más al norte, lógica de recorrido)
    con_geo_sorted = sorted(con_geo, key=lambda x: x[1], reverse=True)

    ruta = [con_geo_sorted[0]]
    pendientes = con_geo_sorted[1:]

    while pendientes:
        _, lat_actual, lon_actual, _ = ruta[-1]

        # Encontrar el más cercano al último punto de la ruta
        mejor_idx = 0
        mejor_dist = float('inf')

        for i, (_, lat, lon, _) in enumerate(pendientes):
            dist = _haversine_distance(lat_actual, lon_actual, lat, lon)
            if dist < mejor_dist:
                mejor_dist = dist
                mejor_idx = i

        ruta.append(pendientes.pop(mejor_idx))

    # Los sin geolocalización van al final, ordenados por sector
    sin_geo.sort(key=lambda x: x[1])

    resultado = [rid for rid, _, _, _ in ruta] + [rid for rid, _ in sin_geo]
    return resultado

def _aplicar_orden_ruta_a_asignaciones(asignaciones, df_reclamos, df_clientes):
    """
    Aplica el ordenamiento por ruta geográfica a TODOS los grupos.
    """
    for grupo in asignaciones:
        if asignaciones[grupo]:
            asignaciones[grupo] = _ordenar_reclamos_por_ruta(
                asignaciones[grupo], df_reclamos, df_clientes
            )
    return asignaciones


def _calcular_distancia_total_ruta(reclamos_ids, df_reclamos, df_clientes):
    """
    Calcula la distancia total de la ruta sugerida (solo informativo).
    """
    coords = []
    for rid in reclamos_ids:
        lat, lon = _obtener_coordenadas_reclamo(rid, df_reclamos, df_clientes)
        if lat is not None and lon is not None:
            coords.append((float(lat), float(lon)))

    if len(coords) < 2:
        return 0.0

    total = 0.0
    for i in range(len(coords) - 1):
        total += _haversine_distance(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])

    return total


# ============================================================================
# DISTRIBUCIÓN PRINCIPAL (4 FASES)
# ============================================================================

def distribuir_por_sector_mejorado(df_reclamos, grupos_activos, df_clientes=None):
    """
    Algoritmo híbrido de 4 fases:
    1. Asigna zonas completas respetando cliques geográficos
    2. Balancea por reclamo individual con regla de clique estricta
    3. Red de seguridad que nunca rompe la coherencia geográfica
    4. Ordena cada grupo por ruta geográfica (Haversine + Nearest Neighbor)
    """
    df_reclamos = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()
    grupos = GRUPOS_POSIBLES[:grupos_activos]
    asignaciones = {g: [] for g in grupos}

    zonas = list(SECTORES_VECINOS.keys())

    # FASE 1: Asignación base por zonas completas
    zonas_por_grupo = agrupar_zonas_completas(zonas, grupos, df_reclamos)

    # Crear mapa sector→grupo y asignar reclamos iniciales
    sector_grupo_map = {}
    for grupo, zonas_asignadas in zonas_por_grupo.items():
        for zona in zonas_asignadas:
            for sector in SECTORES_VECINOS.get(zona, []):
                sector_grupo_map[str(sector)] = grupo

    for _, r in df_reclamos.iterrows():
        sector = str(r.get("Sector", "")).strip()
        grupo = sector_grupo_map.get(sector)
        if grupo:
            asignaciones[grupo].append(r["ID Reclamo"])

    # FASE 2: Balanceo fino por reclamo (con clique estricto)
    asignaciones = _balancear_asignaciones(asignaciones, df_reclamos)

    # FASE 3: Red de seguridad (con clique estricto)
    asignaciones = _forzar_balanceo_final(asignaciones, df_reclamos, grupos_activos)

    # FASE 4: Ordenar cada grupo por ruta geográfica
    asignaciones = _aplicar_orden_ruta_a_asignaciones(asignaciones, df_reclamos, df_clientes)

    return asignaciones


def distribuir_por_tipo(df_reclamos, grupos_activos):
    df_reclamos = df_reclamos[df_reclamos["Estado"] == "Pendiente"].copy()

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

def _mostrar_metricas_asignacion(asignaciones, df_reclamos, df_clientes, grupos_activos):
    """Muestra métricas de calidad de la asignación incluyendo distancia de ruta"""
    grupos = GRUPOS_POSIBLES[:grupos_activos]
    cargas = {g: len(asignaciones[g]) for g in grupos}
    total = sum(cargas.values())

    if total == 0:
        return

    carga_ideal = total / len(grupos)
    desbalance = max(cargas.values()) - min(cargas.values())

    col1, col2, col3 = st.columns(3)
    col1.metric("Total reclamos", total)
    col2.metric("Carga ideal/grupo", f"{carga_ideal:.1f}")
    col3.metric("Desbalance máximo", desbalance, 
                delta="Óptimo" if desbalance <= 1 else "Regular")

    # Detalle por grupo + distancia de ruta
    st.markdown("**Distribución por grupo:**")
    cols = st.columns(len(grupos))
    for i, g in enumerate(grupos):
        pct = (cargas[g] / total * 100) if total > 0 else 0
        distancia = _calcular_distancia_total_ruta(asignaciones[g], df_reclamos, df_clientes)
        if distancia > 0:
            cols[i].metric(g, cargas[g], f"{pct:.0f}% — {distancia:.1f} km")
        else:
            cols[i].metric(g, cargas[g], f"{pct:.0f}%")

def render_planificacion_grupos(df_reclamos, sheet_reclamos, user, df_clientes=None, sheet_clientes=None):
    if user.get('rol') != 'admin':
        st.warning("⚠️ Solo los administradores pueden acceder a esta sección")
        return {'needs_refresh': False}

    st.subheader("📋 Asignación de reclamos a grupos de trabajo")

    try:
        inicializar_estado_grupos()
        _limpiar_asignaciones(df_reclamos)

        grupos_activos = st.slider("🔢 Cantidad de grupos de trabajo activos", 1, 6, 2)

        modo_distribucion = st.selectbox(
            "📊 Elegí el modo de distribución",
            ["Manual", "Automática por sector (mejorada)", "Automática por tipo de reclamo"],
            index=0
        )

        if modo_distribucion != "Manual":
            if st.button("⚙️ Distribuir reclamos ahora"):
                if modo_distribucion == "Automática por sector (mejorada)":
                    st.session_state.simulacion_asignaciones = distribuir_por_sector_mejorado(
                        df_reclamos, grupos_activos, df_clientes
                    )

                    # Mostrar zonas asignadas por grupo
                    zonas_por_grupo = agrupar_zonas_completas(
                        list(SECTORES_VECINOS.keys()),
                        GRUPOS_POSIBLES[:grupos_activos],
                        df_reclamos
                    )
                    st.markdown("### 🗺️ Zonas asignadas por grupo:")
                    for grupo, zonas_asignadas in zonas_por_grupo.items():
                        st.markdown(f"- **{grupo}** cubre: {', '.join(zonas_asignadas)}")

                else:
                    st.session_state.simulacion_asignaciones = distribuir_por_tipo(df_reclamos, grupos_activos)

                st.session_state.vista_simulacion = True
                st.success("✅ Distribución previa generada. Revisala antes de guardar.")

        if st.session_state.get("vista_simulacion"):
            st.subheader("🗂️ Distribución previa de reclamos")

            # Mostrar métricas de calidad de la asignación
            _mostrar_metricas_asignacion(
                st.session_state.simulacion_asignaciones, 
                df_reclamos, 
                df_clientes,
                grupos_activos
            )

            for grupo, reclamos in st.session_state.simulacion_asignaciones.items():
                st.markdown(f"### 📦 {grupo} - {len(reclamos)} reclamos")

                # Mostrar distancia de ruta si hay geolocalización
                distancia = _calcular_distancia_total_ruta(reclamos, df_reclamos, df_clientes)
                if distancia > 0:
                    st.caption(f"🛣️ Ruta sugerida: {distancia:.1f} km")
                else:
                    st.caption("🛣️ Sin datos de geolocalización para calcular ruta")

                for idx, rid in enumerate(reclamos):
                    row = df_reclamos[df_reclamos["ID Reclamo"] == rid]
                    if not row.empty:
                        r = row.iloc[0]
                        lat, lon = _obtener_coordenadas_reclamo(rid, df_reclamos, df_clientes)
                        geo_icon = "📍" if lat else "❓"
                        st.markdown(f"{idx+1}. {geo_icon} {r['Nº Cliente']} | {r['Tipo de reclamo']} | Sector {r['Sector']}")

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
                df_reclamos,
                sheet_reclamos,
                grupos_activos,
                materiales_por_grupo,
                df_pendientes,
                df_clientes
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


def _mostrar_acciones_finales(df_reclamos, sheet_reclamos, grupos_activos, materiales_por_grupo, df_pendientes, df_clientes):
    """Muestra botones de acción final y maneja su lógica"""
    st.markdown("---")
    cambios = False

    col1, col2 = st.columns(2)

    if col1.button("💾 Guardar cambios y pasar a 'En curso'", use_container_width=True):
        cambios = _guardar_cambios(df_reclamos, sheet_reclamos, grupos_activos)

    if col2.button("📄 Generar PDF de asignaciones por grupo", use_container_width=True):
        _generar_pdf_asignaciones(grupos_activos, materiales_por_grupo, df_pendientes, df_clientes)

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

def _obtener_datos_geolocalizacion(df_clientes, numero_cliente):
    """
    Busca latitud y longitud del cliente.
    """

    try:
        if df_clientes is None or df_clientes.empty:
            return None

        cliente = df_clientes[
            df_clientes["Nº Cliente"].astype(str).str.strip()
            == str(numero_cliente).strip()
        ]

        if cliente.empty:
            return None

        fila = cliente.iloc[0]

        latitud = str(fila.get("Latitud", "")).strip()
        longitud = str(fila.get("Longitud", "")).strip()

        if (
            not latitud
            or not longitud
            or latitud.lower() == "nan"
            or longitud.lower() == "nan"
        ):
            return None

        # Validación básica de coordenadas
        float(latitud)
        float(longitud)

        return {
            "latitud": latitud,
            "longitud": longitud,
        }

    except Exception:
        return None



def _generar_qr_google_maps(latitud, longitud):
    """
    Genera un QR con el link de Google Maps.
    """

    try:
        maps_url = f"https://www.google.com/maps?q={latitud},{longitud}"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )

        qr.add_data(maps_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        if not isinstance(img, Image.Image):
            img = img.get_image()

        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        return ImageReader(img_buffer)

    except Exception:
        return None

def _wrap_text(text, font_name, font_size, max_width, canvas_obj):
    """
    Envuelve texto en múltiples líneas que caben dentro de max_width.
    Retorna una lista de strings, cada uno cabe en el ancho especificado.
    """
    if not text or not str(text).strip():
        return ['']

    text = str(text).strip()

    if canvas_obj.stringWidth(text, font_name, font_size) <= max_width:
        return [text]

    words = text.split(' ')
    lines = []
    current_line = ''

    for word in words:
        if current_line:
            test_line = f"{current_line} {word}"
        else:
            test_line = word

        text_width = canvas_obj.stringWidth(test_line, font_name, font_size)

        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)

            if canvas_obj.stringWidth(word, font_name, font_size) > max_width:
                chars = ''
                for char in word:
                    if canvas_obj.stringWidth(chars + char, font_name, font_size) <= max_width:
                        chars += char
                    else:
                        if chars:
                            lines.append(chars)
                        chars = char
                current_line = chars
            else:
                current_line = word

    if current_line:
        lines.append(current_line)

    return lines if lines else ['']

def _generar_pdf_asignaciones(grupos_activos, materiales_por_grupo, df_pendientes, df_clientes):
    """Genera un PDF con las asignaciones de grupos y QR centrado por reclamo"""

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    hoy = datetime.now().strftime('%d/%m/%Y')

    # ============================================================
    # DIMENSIONES
    # ============================================================
    qr_size = 70
    qr_x = width - 45 - qr_size           # QR alineado al margen derecho
    max_text_width = qr_x - 50             # Texto desde x=40 hasta antes del QR

    # Fuentes y alturas de línea
    font_nombre = "Helvetica-Bold"
    font_body = "Helvetica"
    size_nombre = 12
    size_body = 10
    line_h_nombre = 14
    line_h_body = 11

    for grupo in GRUPOS_POSIBLES[:grupos_activos]:
        reclamos_ids = st.session_state.asignaciones_grupos[grupo]

        if not reclamos_ids:
            continue

        tecnicos = st.session_state.tecnicos_grupos[grupo]

        # Calcular distancia total de la ruta para mostrar en el header
        distancia_ruta = _calcular_distancia_total_ruta(reclamos_ids, df_pendientes, df_clientes)

        # Nueva página para cada grupo
        agregar_pie_pdf(c, width, height)
        c.showPage()

        y = height - 40

        # ---- HEADER DEL GRUPO ----
        tipos = df_pendientes[
            df_pendientes["ID Reclamo"].isin(reclamos_ids)
        ]["Tipo de reclamo"].value_counts()

        resumen_tipos = " - ".join([f"{v} {k}" for k, v in tipos.items()])

        c.setFont("Helvetica-Bold", 14)
        header_text = f"{grupo} - Técnicos: {', '.join(tecnicos)} (Asignado el {hoy})"
        c.drawString(40, y, header_text)
        y -= 18

        # Mostrar distancia de ruta en el header del PDF
        if distancia_ruta > 0:
            c.setFont("Helvetica-Oblique", 10)
            c.drawString(40, y, f"Ruta sugerida: {distancia_ruta:.1f} km")
            y -= 14
        else:
            y -= 4

        c.setFont("Helvetica", 11)
        c.drawString(40, y, resumen_tipos)
        y -= 22

        # ---- RECLAMOS ----
        for reclamo_id in reclamos_ids:

            reclamo_data = df_pendientes[
                df_pendientes["ID Reclamo"] == reclamo_id
            ]
            if reclamo_data.empty:
                continue

            reclamo = reclamo_data.iloc[0]

            # ========================================================
            # PRE-COMPUTAR LÍNEAS CON WRAP
            # ========================================================

            # Calcular si tiene más de 48 horas
            sufijo_48 = ""
            if pd.notna(reclamo['Fecha y hora']):
                horas = (datetime.now() - reclamo['Fecha y hora']).total_seconds() / 3600
                if horas > 48:
                    sufijo_48 = " +48"

            nombre_linea = (
                f"{reclamo['Nº Cliente']} - "
                f"{reclamo['Nombre']} "
                f"({reclamo['Sector']}){sufijo_48}"
            )
            nombre_wrapped = _wrap_text(
                nombre_linea, font_nombre, size_nombre, max_text_width, c
            )

            fecha_pdf = (
                reclamo['Fecha y hora'].strftime('%d/%m/%Y %H:%M')
                if not pd.isna(reclamo['Fecha y hora'])
                else 'Sin fecha'
            )

            direccion = str(reclamo.get('Dirección', ''))
            telefono = str(reclamo.get('Teléfono', ''))
            precinto = str(reclamo.get('N° de Precinto', 'N/A'))

            # Obtener plan del cliente (del reclamo o de la hoja Clientes)
            plan_cliente = str(reclamo.get('Plan', '')).strip()
            if not plan_cliente or plan_cliente.lower() in ('nan', 'none', ''):
                if df_clientes is not None and not df_clientes.empty:
                    cliente_match = df_clientes[
                        df_clientes["Nº Cliente"].astype(str).str.strip() == str(reclamo.get('Nº Cliente', '')).strip()
                    ]
                    if not cliente_match.empty:
                        plan_cliente = str(cliente_match.iloc[0].get("Plan", "N/A")).strip() or "N/A"
                else:
                    plan_cliente = "N/A"

            detalles_raw = str(reclamo.get('Detalles', '')).strip()
            if detalles_raw == 'nan':
                detalles_raw = ''
            if len(detalles_raw) > 200:
                detalles_raw = detalles_raw[:200] + "..."

            fecha_wrapped = [f"Fecha: {fecha_pdf}"]
            direccion_wrapped = _wrap_text(
                f"Dirección: {direccion}", font_body, size_body, max_text_width, c
            )
            tel_wrapped = _wrap_text(
                f"Tel: {telefono} - Precinto: {precinto} - Plan: {plan_cliente}",
                font_body, size_body, max_text_width, c
            )
            tipo_wrapped = [f"Tipo: {reclamo['Tipo de reclamo']}"]

            if detalles_raw:
                detalles_wrapped = _wrap_text(
                    f"Detalles: {detalles_raw}", font_body, size_body, max_text_width, c
                )
            else:
                detalles_wrapped = []

            # ========================================================
            # CALCULAR ALTURA DEL BLOQUE DE TEXTO
            # ========================================================

            total_body_lines = (
                len(fecha_wrapped) + len(direccion_wrapped)
                + len(tel_wrapped) + len(tipo_wrapped)
                + len(detalles_wrapped)
            )

            text_height = (
                len(nombre_wrapped) * line_h_nombre
                + total_body_lines * line_h_body
            )

            # Altura total estimada del bloque (texto + separador)
            # Debe ser al menos tan alta como el QR
            block_height = max(text_height, qr_size) + 20

            # Verificar espacio en página
            if y < block_height + 15:
                agregar_pie_pdf(c, width, height)
                c.showPage()
                y = height - 40

                c.setFont("Helvetica-Bold", 14)
                c.drawString(40, y, f"{grupo} (cont.)")
                y -= 22

            inicio_y = y

            # ========================================================
            # DIBUJAR NOMBRE (wrappeado)
            # ========================================================

            c.setFont(font_nombre, size_nombre)
            for nl in nombre_wrapped:
                c.drawString(40, y, nl)
                y -= line_h_nombre

            # ========================================================
            # DIBUJAR DATOS (wrappeados)
            # ========================================================

            c.setFont(font_body, size_body)

            for linea in fecha_wrapped:
                c.drawString(40, y, linea)
                y -= line_h_body

            for linea in direccion_wrapped:
                c.drawString(40, y, linea)
                y -= line_h_body

            for linea in tel_wrapped:
                c.drawString(40, y, linea)
                y -= line_h_body

            for linea in tipo_wrapped:
                c.drawString(40, y, linea)
                y -= line_h_body

            for linea in detalles_wrapped:
                c.drawString(40, y, linea)
                y -= line_h_body

            # Guardar dónde termina el texto
            text_end_y = y

            # ========================================================
            # QR CENTRADO VERTICALMENTE RESPECTO AL TEXTO
            # ========================================================

            qr_center_y = inicio_y - (text_height / 2)
            qr_y = qr_center_y - (qr_size / 2)

            geo_data = _obtener_datos_geolocalizacion(
                df_clientes, reclamo['Nº Cliente']
            )

            if geo_data:
                qr_img = _generar_qr_google_maps(
                    geo_data['latitud'], geo_data['longitud']
                )
                if qr_img:
                    c.drawImage(
                        qr_img, qr_x, qr_y,
                        width=qr_size, height=qr_size,
                        preserveAspectRatio=True, mask='auto'
                    )
                else:
                    c.setFont("Helvetica", 8)
                    c.drawCentredString(
                        qr_x + qr_size / 2,
                        qr_center_y - 3,
                        "QR inválido"
                    )
            else:
                c.setFont("Helvetica", 8)
                c.drawCentredString(
                    qr_x + qr_size / 2,
                    qr_center_y - 3,
                    "Sin georreferencia"
                )

            # ========================================================
            # SEPARADOR PARCIAL
            # ========================================================

            qr_bottom_y = qr_y
            lowest_y = min(text_end_y, qr_bottom_y)

            sep_y = lowest_y - 6
            c.line(40, sep_y, qr_x - 8, sep_y)

            y = sep_y - 14

        # ========================================================
        # MATERIALES MÍNIMOS
        # ========================================================

        materiales = materiales_por_grupo.get(grupo, {})

        if materiales:
            y -= 8
            c.setFont("Helvetica-Bold", 11)
            c.drawString(40, y, "Materiales mínimos estimados:")
            y -= 14
            c.setFont(font_body, size_body)
            for mat, cant in materiales.items():
                c.drawString(
                    40, y,
                    f"- {cant} {mat.replace('_', ' ').title()}"
                )
                y -= line_h_body

        y -= 15

    agregar_pie_pdf(c, width, height)
    c.save()
    buffer.seek(0)

    st.download_button(
        label="📄 Descargar PDF de asignaciones",
        data=buffer,
        file_name="asignaciones_grupos.pdf",
        mime="application/pdf"
    )
