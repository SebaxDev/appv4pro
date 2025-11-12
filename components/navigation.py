"""
Componente de navegación profesional con iconos y estados activos
Versión 3.0 - Diseño CRM profesional
"""
import streamlit as st
from utils.styles import get_main_styles_v2, get_loading_spinner, loading_indicator
from utils.permissions import has_permission

def render_sidebar_navigation():
    """Renderiza la navegación lateral profesional con iconos"""
    
    menu_items = [
        {"icon": "🏠", "label": "Inicio", "key": "Inicio", "permiso": "inicio"},
        {"icon": "📊", "label": "Reclamos cargados", "key": "Reclamos cargados", "permiso": "reclamos_cargados"},
        {"icon": "👥", "label": "Gestión de clientes", "key": "Gestión de clientes", "permiso": "gestion_clientes"},
        {"icon": "🖨️", "label": "Imprimir reclamos", "key": "Imprimir reclamos", "permiso": "imprimir_reclamos"},
        {"icon": "🔧", "label": "Seguimiento técnico", "key": "Seguimiento técnico", "permiso": "seguimiento_tecnico"},
        {"icon": "✅", "label": "Cierre de Reclamos", "key": "Cierre de Reclamos", "permiso": "cierre_reclamos"}
    ]
    
    # Header de navegación
    st.sidebar.markdown("""
    <div style="padding: 1rem 0; border-bottom: 1px solid var(--border-color); margin-bottom: 1rem;">
        <h3 style="margin: 0; color: var(--primary-color); display: flex; align-items: center; gap: 0.5rem;">
            <span>🧭</span> Navegación
        </h3>
    </div>
    """, unsafe_allow_html=True)
    
    # Botones de navegación
    for item in menu_items:
        if not has_permission(item["permiso"]):
            continue
            
        is_active = st.session_state.get('current_page') == item["key"]
        
        button_style = """
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-light) 100%) !important;
            color: #272822 !important;
            font-weight: 600 !important;
            border: 1px solid var(--primary-color) !important;
        """ if is_active else """
            background: transparent !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-color) !important;
        """
        
        if st.sidebar.button(
            f"{item['icon']} {item['label']}", 
            key=f"nav_{item['key'].replace(' ', '_').lower()}",
            use_container_width=True,
            help=f"Ir a {item['label']}"
        ):
            st.session_state.current_page = item["key"]
            st.rerun()
    
    st.sidebar.markdown("---")

def render_user_info():
    """Renderiza información del usuario logueado con diseño mejorado"""
    if st.session_state.auth.get("logged_in", False):
        user_info = st.session_state.auth.get('user_info', {})
        
        st.sidebar.markdown("""
        <div style="padding: 1rem; background: var(--bg-surface); border-radius: var(--radius-lg); border: 1px solid var(--border-color); margin: 1rem 0;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <div style="font-size: 1.5rem;">👋</div>
                <div>
                    <div style="font-weight: 600; color: var(--text-primary);">Bienvenido</div>
                    <div style="color: var(--primary-color); font-size: 0.9rem;">{nombre}</div>
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--text-secondary); font-size: 0.8rem;">
                <span style="background: var(--primary-color); color: #272822; padding: 0.1rem 0.5rem; border-radius: var(--radius-md); font-weight: 500;">{rol}</span>
            </div>
        </div>
        """.format(
            nombre=user_info.get('nombre', 'Usuario'),
            rol=user_info.get('rol', 'Usuario')
        ), unsafe_allow_html=True)
        
        if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state.auth["logged_in"] = False
            st.session_state.auth["user_info"] = {}
            st.rerun()

# Función original mantenida para compatibilidad
def render_navigation():
    """Renderiza el menú de navegación horizontal (compatibilidad)"""
    st.markdown("""
    <div style="margin: 1.5rem 0; padding: 1rem; background: var(--bg-surface); border-radius: var(--radius-lg); border: 1px solid var(--border-color);">
        <h3 style="margin: 0; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
            <span>🧭</span> Navegación
        </h3>
    </div>
    """, unsafe_allow_html=True)
    
    opciones = [
        "🏠 Inicio", 
        "📊 Reclamos cargados", 
        "👥 Gestión de clientes",  
        "🖨️ Imprimir reclamos", 
        "🔧 Seguimiento técnico", 
        "✅ Cierre de Reclamos"
    ]
    
    # Crear navegación con iconos
    opcion = st.radio(
        "Selecciona una sección:",
        opciones,
        horizontal=True,
        label_visibility="collapsed"
    )
    
    # Extraer solo el nombre sin emoji para compatibilidad
    return opcion.split(" ", 1)[1] if " " in opcion else opcion