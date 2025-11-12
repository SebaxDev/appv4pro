"""
Componente de navegación para la interfaz principal.
"""
import streamlit as st
from utils.permissions import has_permission

MENU_ITEMS = [
    {"icon": "🏠", "label": "Inicio", "key": "Inicio", "permiso": "inicio"},
    {"icon": "📊", "label": "Reclamos", "key": "Reclamos cargados", "permiso": "reclamos_cargados"},
    {"icon": "👥", "label": "Clientes", "key": "Gestión de clientes", "permiso": "gestion_clientes"},
    {"icon": "🖨️", "label": "Impresiones", "key": "Imprimir reclamos", "permiso": "imprimir_reclamos"},
    {"icon": "🔧", "label": "Planificacion", "key": "Seguimiento técnico", "permiso": "seguimiento_tecnico"},
    {"icon": "✅", "label": "Cierre", "key": "Cierre de Reclamos", "permiso": "cierre_reclamos"}
]

def render_main_navigation():
    """Renderiza la navegación principal horizontal con botones."""
    visible_items = [item for item in MENU_ITEMS if has_permission(item["permiso"])]

    if not visible_items:
        return

    cols = st.columns(len(visible_items))

    for i, item in enumerate(visible_items):
        with cols[i]:
            if st.button(
                f"{item['icon']} {item['label']}",
                key=f"main_nav_{item['key'].replace(' ', '_').lower()}",
                use_container_width=True,
                help=f"Ir a {item['label']}"
            ):
                st.session_state.current_page = item["key"]
                st.rerun()

    st.markdown("---")


def render_user_info():
    """Renderiza información del usuario logueado (componente para header)."""
    if st.session_state.auth.get("logged_in", False):
        user_info = st.session_state.auth.get('user_info', {})

        st.markdown(f"""
        <div style="text-align: right;">
            <div>{user_info.get('nombre', 'Usuario')}</div>
            <div style="font-size: 0.8rem; color: var(--text-secondary);">{user_info.get('rol', 'N/A')}</div>
        </div>
        """, unsafe_allow_html=True)