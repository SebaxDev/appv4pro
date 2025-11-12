"""
Componente de autenticación profesional estilo CRM
Versión mejorada con diseño elegante y compatible con Streamlit Cloud
"""
import streamlit as st
from utils.data_manager import safe_get_sheet_data
from config.settings import (
    WORKSHEET_USUARIOS,
    COLUMNAS_USUARIOS,
    PERMISOS_POR_ROL
)
import time
from utils.styles import get_loading_spinner
from passlib.context import CryptContext

# Configura el contexto de hasheo de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_auth_session():
    """Inicializa las variables de sesión"""
    if 'auth' not in st.session_state:
        st.session_state.auth = {
            'logged_in': False,
            'user_info': None
        }

def logout():
    """Cierra la sesión del usuario"""
    st.session_state.auth = {'logged_in': False, 'user_info': None}
    st.cache_data.clear()  # Limpiar caché de datos

def verify_credentials(username, password, sheet_usuarios):
    """Verifica las credenciales del usuario usando password en texto plano (Google Sheets)."""
    try:
        df_usuarios = safe_get_sheet_data(sheet_usuarios, COLUMNAS_USUARIOS)

        # Normalización de datos
        df_usuarios["username"] = df_usuarios["username"].astype(str).str.strip().str.lower()
        df_usuarios["password"] = df_usuarios["password"].astype(str).str.strip()
        df_usuarios["rol"] = df_usuarios["rol"].astype(str).str.strip().str.lower()
        df_usuarios["nombre"] = df_usuarios["nombre"].astype(str).str.strip()

        # Manejo flexible de campo 'activo'
        df_usuarios["activo"] = df_usuarios["activo"].astype(str).str.upper().isin(
            ["SI", "TRUE", "1", "SÍ", "VERDADERO"]
        )

        # Buscar el usuario válido
        usuario = df_usuarios[
            (df_usuarios["username"] == username.strip().lower()) &
            (df_usuarios["password"] == password.strip()) &
            (df_usuarios["activo"])
        ]

        if not usuario.empty:
            u = usuario.iloc[0]
            return {
                "username": u["username"],
                "nombre": u["nombre"],
                "rol": u["rol"],
                "modo_oscuro": u.get("modo_oscuro", "FALSE"),
                "permisos": PERMISOS_POR_ROL.get(u["rol"], {}).get("permisos", [])
            }
    except Exception as e:
        st.error(f"Error en autenticación: {str(e)}")
    return None

def render_login_simple(sheet_usuarios):
    """Versión simple del login para máxima compatibilidad con Streamlit Cloud"""
    
    # Centrar el contenido
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align: center; margin: 2rem 0;">
            <h1 style="color: #66D9EF; margin-bottom: 0.5rem;">⚡ Fusion Reclamos</h1>
            <p style="color: #CFCFC2; margin-bottom: 2rem;">Sistema de gestión profesional</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Formulario de login simple
        with st.form("login_form"):
            username = st.text_input("👤 Usuario", placeholder="Ingresa tu usuario")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="Ingresa tu contraseña")
            
            if st.form_submit_button("🚀 Ingresar al sistema", use_container_width=True):
                if username and password:
                    user_info = verify_credentials(username, password, sheet_usuarios)
                    if user_info:
                        st.session_state.auth = {
                            'logged_in': True,
                            'user_info': user_info
                        }
                        st.success(f"✅ Bienvenido, {user_info['nombre']}!")
                        st.rerun()
                    else:
                        st.error("❌ Credenciales incorrectas o usuario inactivo")
                else:
                    st.error("⚠️ Usuario y contraseña son requeridos")
        
        st.markdown("""
        <div style="text-align: center; margin-top: 2rem; color: #75715E; font-size: 0.8rem;">
            <p>© 2025 Fusion Reclamos • v3.0</p>
            <p>Sistema optimizado para gestión eficiente</p>
        </div>
        """, unsafe_allow_html=True)

def render_login(sheet_usuarios):
    """Formulario de login con diseño profesional CRM optimizado para una sola pantalla"""
    
    # Usar la versión simple por defecto para evitar problemas en Streamlit Cloud
    render_login_simple(sheet_usuarios)

def check_authentication():
    """Verifica si el usuario está autenticado"""
    init_auth_session()
    return st.session_state.auth['logged_in']

def has_permission(required_permission):
    """Verifica permisos del usuario"""
    if not check_authentication():
        return False
        
    user_info = st.session_state.auth.get('user_info')
    if not user_info:
        return False
        
    # Admin tiene acceso completo
    if user_info['rol'] == 'admin':
        return True
        
    return required_permission in user_info.get('permisos', [])

def render_user_info():
    """Versión mejorada con iconos y estilo siguiendo las pautas de styles.py"""
    if not check_authentication():
        return
        
    user_info = st.session_state.auth['user_info']
    role_config = {
        'admin': {'icon': '👑', 'color': 'var(--danger-color)', 'badge': 'Administrador'},
        'oficina': {'icon': '💼', 'color': 'var(--info-color)', 'badge': 'Oficina'},
        'tecnico': {'icon': '🔧', 'color': 'var(--success-color)', 'badge': 'Técnico'},
        'supervisor': {'icon': '👔', 'color': 'var(--secondary-color)', 'badge': 'Supervisor'}
    }
    
    config = role_config.get(user_info['rol'].lower(), {'icon': '👤', 'color': 'var(--text-muted)', 'badge': 'Usuario'})
    
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 1.5rem; padding: 1rem; background: var(--bg-card); border-radius: var(--radius-lg); border: 1px solid var(--border-color);">
            <div style="font-size: 2.5rem; margin-bottom: 0.75rem; background: linear-gradient(135deg, {config['color']}, var(--primary-color)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));">
                {config['icon']}
            </div>
            <h3 style="margin: 0; color: var(--text-primary); font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem;">{user_info['nombre']}</h3>
            <div style="background: rgba(102, 217, 239, 0.15); 
                      color: var(--primary-color); 
                      padding: 0.25rem 0.75rem; 
                      border-radius: var(--radius-xl); 
                      font-size: 0.75rem; 
                      font-weight: 600;
                      margin: 0.5rem 0;
                      display: inline-block;
                      border: 1px solid rgba(102, 217, 239, 0.3);">
                {config['badge']}
            </div>
            <p style="color: var(--text-secondary); margin: 0.25rem 0; font-size: 0.8rem; font-weight: 500;">
                @{user_info['username']}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪 Cerrar sesión", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()
        st.markdown("---")