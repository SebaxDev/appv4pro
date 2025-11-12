"""Utilidades de permisos para evitar importación circular"""

def has_permission(permiso):
    """Verifica permisos del usuario"""
    import streamlit as st
    
    user_info = st.session_state.auth.get('user_info', {})
    user_role = user_info.get('rol', '')
    
    permisos = {
        'admin': ['inicio', 'reclamos_cargados', 'gestion_clientes', 'imprimir_reclamos', 'seguimiento_tecnico', 'cierre_reclamos'],
        'tecnico': ['inicio', 'reclamos_cargados', 'seguimiento_tecnico', 'cierre_reclamos'],
        'usuario': ['inicio', 'reclamos_cargados', 'imprimir_reclamos']
    }
    
    return permiso in permisos.get(user_role, [])