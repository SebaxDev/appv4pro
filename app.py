# --------------------------------------------------
# Aplicación principal de gestión de reclamos optimizada
# Versión 2.6 - Interfaz Moderna
# --------------------------------------------------

# Standard library
import streamlit as st
import pandas as pd
import time
from google.oauth2 import service_account
import gspread
from tenacity import retry, wait_exponential, stop_after_attempt

# Config
from config.settings import (
    SHEET_ID,
    WORKSHEET_RECLAMOS,
    WORKSHEET_CLIENTES, 
    WORKSHEET_USUARIOS,
    COLUMNAS_RECLAMOS,
    COLUMNAS_CLIENTES,
    COLUMNAS_USUARIOS,
    DEBUG_MODE,
)

# Local components
from components.reclamos.nuevo import render_nuevo_reclamo
from components.reclamos.gestion import render_gestion_reclamos
from components.clientes.gestion import render_gestion_clientes
from components.reclamos.impresion import render_impresion_reclamos
from components.reclamos.planificacion import render_planificacion_grupos
from components.reclamos.cierre import render_cierre_reclamos
from components.resumen_jornada import render_resumen_jornada
from components.auth import check_authentication, render_login
from components.new_navigation import render_main_navigation, render_user_info

# Utils
from utils.styles import get_main_styles_v2
from utils.data_manager import safe_get_sheet_data, batch_update_sheet
from utils.permissions import has_permission
from utils.date_utils import ahora_argentina
from utils.api_manager import api_manager
from components.reclamos.nuevo import generar_id_unico

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Fusion Reclamos App",
    page_icon="📋",
    layout="wide",
    menu_items={
        'About': "Sistema de gestión de reclamos - Fusion Reclamos App v3.0"
    }
)

# --- CONEXIÓN CON GOOGLE SHEETS ---
@st.cache_resource(show_spinner="Conectando a la base de datos...")
def init_google_sheets():
    """Conexión optimizada a Google Sheets con retry automático."""
    @retry(wait=wait_exponential(multiplier=1, min=2, max=6), stop=stop_after_attempt(3))
    def _connect():
        creds = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        return (
            client.open_by_key(SHEET_ID).worksheet(WORKSHEET_RECLAMOS),
            client.open_by_key(SHEET_ID).worksheet(WORKSHEET_CLIENTES),
            client.open_by_key(SHEET_ID).worksheet(WORKSHEET_USUARIOS),
        )
    try:
        return _connect()
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        st.stop()

# --- Carga de Datos ---
def cargar_datos_principales(sheet_reclamos, sheet_clientes, sheet_usuarios):
    """Carga los dataframes principales desde las hojas de cálculo."""
    with st.spinner("Cargando datos..."):
        df_r = safe_get_sheet_data(sheet_reclamos, COLUMNAS_RECLAMOS)
        df_c = safe_get_sheet_data(sheet_clientes, COLUMNAS_CLIENTES)
        df_u = safe_get_sheet_data(sheet_usuarios, COLUMNAS_USUARIOS)
    return df_r, df_c, df_u

# --- UTILIDAD: Migración de UUIDs existentes ---
def migrar_uuids_existentes(sheet_reclamos, sheet_clientes):
    """Genera UUIDs para registros existentes que no los tengan"""
    try:
        if not sheet_reclamos or not sheet_clientes:
            st.error("No se pudo conectar a las hojas de cálculo")
            return False

        updates_reclamos = []
        updates_clientes = []

        # Validaciones de columnas
        if 'ID Reclamo' not in st.session_state.df_reclamos.columns:
            st.error("La columna 'ID Reclamo' no existe en los datos de reclamos")
            return False

        if 'ID Cliente' not in st.session_state.df_clientes.columns:
            st.error("La columna 'ID Cliente' no existe en los datos de clientes")
            return False

        # Reclamos sin UUID
        reclamos_sin_uuid = st.session_state.df_reclamos[
            st.session_state.df_reclamos['ID Reclamo'].isna() |
            (st.session_state.df_reclamos['ID Reclamo'] == '')
        ]

        if not reclamos_sin_uuid.empty:
            with st.status("Generando UUIDs para reclamos...", expanded=True) as status:
                st.write(f"📋 {len(reclamos_sin_uuid)} reclamos sin UUID encontrados")

                # Calcular letra de columna para "ID Reclamo" dinámicamente
                def _excel_col_letter(n: int) -> str:
                    letters = ""
                    while n:
                        n, rem = divmod(n - 1, 26)
                        letters = chr(65 + rem) + letters
                    return letters

                idx_id_reclamo = COLUMNAS_RECLAMOS.index("ID Reclamo") + 1
                col_id_letter = _excel_col_letter(idx_id_reclamo)

                for _, row in reclamos_sin_uuid.iterrows():
                    nuevo_uuid = generar_id_unico()
                    updates_reclamos.append({
                        "range": f"{col_id_letter}{row.name + 2}",
                        "values": [[nuevo_uuid]]
                    })

                batch_size = 50
                for i in range(0, len(updates_reclamos), batch_size):
                    batch = updates_reclamos[i:i + batch_size]
                    progress = min((i + batch_size) / max(len(updates_reclamos), 1), 1.0)
                    status.update(label=f"Actualizando reclamos... {progress:.0%}", state="running")

                    success, error = api_manager.safe_sheet_operation(
                        batch_update_sheet,
                        sheet_reclamos,
                        batch,
                        is_batch=True
                    )
                    if not success:
                        st.error(f"Error al actualizar lote de reclamos: {error}")
                        return False

                status.update(label="✅ UUIDs para reclamos completados", state="complete", expanded=False)

        # Clientes sin UUID
        clientes_sin_uuid = st.session_state.df_clientes[
            st.session_state.df_clientes['ID Cliente'].isna() |
            (st.session_state.df_clientes['ID Cliente'] == '')
        ]

        if not clientes_sin_uuid.empty:
            with st.status("Generando UUIDs para clientes...", expanded=True) as status:
                st.write(f"👥 {len(clientes_sin_uuid)} clientes sin UUID encontrados")

                for _, row in clientes_sin_uuid.iterrows():
                    nuevo_uuid = generar_id_unico()
                    updates_clientes.append({
                        "range": f"G{row.name + 2}",
                        "values": [[nuevo_uuid]]
                    })

                batch_size = 50
                for i in range(0, len(updates_clientes), batch_size):
                    batch = updates_clientes[i:i + batch_size]
                    progress = min((i + batch_size) / max(len(updates_clientes), 1), 1.0)
                    status.update(label=f"Actualizando clientes... {progress:.0%}", state="running")

                    success, error = api_manager.safe_sheet_operation(
                        batch_update_sheet,
                        sheet_clientes,
                        batch,
                        is_batch=True
                    )
                    if not success:
                        st.error(f"Error al actualizar lote de clientes: {error}")
                        return False

                status.update(label="✅ UUIDs para clientes completados", state="complete", expanded=False)

        if not updates_reclamos and not updates_clientes:
            st.info("ℹ️ Todos los registros ya tienen UUIDs asignados")
            return False

        # Refrescar DataFrames en caché
        st.session_state.df_reclamos = safe_get_sheet_data(sheet_reclamos, COLUMNAS_RECLAMOS)
        st.session_state.df_clientes = safe_get_sheet_data(sheet_clientes, COLUMNAS_CLIENTES)

        return True

    except Exception as e:
        st.error(f"❌ Error en la migración de UUIDs: {str(e)}")
        if DEBUG_MODE:
            st.exception(e)
        return False

# --- INICIO DE LA APP ---
sheet_reclamos, sheet_clientes, sheet_usuarios = init_google_sheets()

if not check_authentication():
    render_login(sheet_usuarios)
    st.stop()

# --- CARGA Y CACHEO DE DATOS ---
df_reclamos, df_clientes, df_usuarios = cargar_datos_principales(sheet_reclamos, sheet_clientes, sheet_usuarios)
st.session_state.df_reclamos = df_reclamos
st.session_state.df_clientes = df_clientes
st.session_state.df_usuarios = df_usuarios

# --- OBTENER INFORMACIÓN DEL USUARIO AUTENTICADO ---
user_info = st.session_state.auth.get('user_info', {})
opcion = st.session_state.get('current_page', 'Inicio')

# --- ESTADO DE LA PÁGINA Y UI ---
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Inicio'
if 'modo_oscuro' not in st.session_state:
    st.session_state.modo_oscuro = False

st.markdown(get_main_styles_v2(dark_mode=st.session_state.modo_oscuro), unsafe_allow_html=True)

# --- HEADER Y NAVEGACIÓN PRINCIPAL ---
st.markdown("""<h1 style="text-align: center; margin-bottom: 2rem;">Fusion Reclamos App</h1>""", unsafe_allow_html=True)

# Métricas compactas para el header (hoy y pendientes)
try:
    df_header = df_reclamos.copy()
    df_header["Fecha y hora"] = pd.to_datetime(df_header["Fecha y hora"], dayfirst=True, errors='coerce')
    hoy = ahora_argentina().date()
    reclamos_hoy_count = int((df_header["Fecha y hora"].dt.date == hoy).sum())
    pendientes_count = int((df_header["Estado"].astype(str).str.strip().str.lower() == "pendiente").sum())
except Exception:
    reclamos_hoy_count = 0
    pendientes_count = 0

header_cols = st.columns([4, 3, 1, 1])
with header_cols[0]:
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        st.metric(label="📝 Hoy", value=reclamos_hoy_count)
    with mcol2:
        st.metric(label="⏳ Pendientes", value=pendientes_count)
with header_cols[1]:
    render_user_info()
with header_cols[2]:
    def toggle_dark_mode():
        st.session_state.modo_oscuro = st.session_state.dark_mode_toggle
    st.checkbox("🌙 Modo Oscuro", value=st.session_state.modo_oscuro, key="dark_mode_toggle", on_change=toggle_dark_mode)
with header_cols[3]:
    if st.button("Salir 🚪", use_container_width=True):
        st.session_state.auth['logged_in'] = False
        st.session_state.auth['user_info'] = {}
        st.rerun()

render_main_navigation()

# --------------------------
# RUTEO DE COMPONENTES
# --------------------------

COMPONENTES = {
    "Inicio": {
        "render": render_nuevo_reclamo,
        "permiso": "inicio",
        "params": {
            "df_reclamos": df_reclamos,
            "df_clientes": df_clientes,
            "sheet_reclamos": sheet_reclamos,
            "sheet_clientes": sheet_clientes,
            "current_user": user_info.get('nombre', '')
        }
    },
    "Reclamos cargados": {
        "render": render_gestion_reclamos,
        "permiso": "reclamos_cargados",
        "params": {
            "df_reclamos": df_reclamos,
            "df_clientes": df_clientes,
            "sheet_reclamos": sheet_reclamos,
            "user": user_info
        }
    },
    "Gestión de clientes": {
        "render": render_gestion_clientes,
        "permiso": "gestion_clientes",
        "params": {
            "df_clientes": df_clientes,
            "df_reclamos": df_reclamos,
            "sheet_clientes": sheet_clientes,
            "user_role": user_info.get('rol', '')
        }
    },
    "Imprimir reclamos": {
        "render": render_impresion_reclamos,
        "permiso": "imprimir_reclamos",
        "params": {
            "df_clientes": df_clientes,
            "df_reclamos": df_reclamos,
            "user": user_info
        }
    },
    "Seguimiento técnico": {
        "render": render_planificacion_grupos,
        "permiso": "seguimiento_tecnico",
        "params": {
            "df_reclamos": df_reclamos,
            "sheet_reclamos": sheet_reclamos,
            "user": user_info,
            "df_clientes": df_clientes,
            "sheet_clientes": sheet_clientes
        }
    },
    "Cierre de Reclamos": {
        "render": render_cierre_reclamos,
        "permiso": "cierre_reclamos",
        "params": {
            "df_reclamos": df_reclamos,
            "df_clientes": df_clientes,
            "sheet_reclamos": sheet_reclamos,
            "sheet_clientes": sheet_clientes,
            "user": user_info
        }
    }
}

# Renderizar componente seleccionado
if opcion in COMPONENTES and has_permission(COMPONENTES[opcion]["permiso"]):
    with st.container():
        st.markdown("---")
        resultado = COMPONENTES[opcion]["render"](**COMPONENTES[opcion]["params"])
        
        if resultado and resultado.get('needs_refresh'):
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()

# --- FOOTER Y RESUMEN ---
with st.container():
    render_resumen_jornada(df_reclamos)

st.markdown(f"""<div style="text-align:center; font-size:1rem; color: var(--text-muted); padding-top: 2rem;">Desarrollado con 💜 por Sebastián Andrés (v3.0)</div>""", unsafe_allow_html=True)
