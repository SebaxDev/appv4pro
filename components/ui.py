"""Componentes de UI reutilizables para una apariencia profesional"""

import streamlit as st
from datetime import datetime  # ← AÑADIR ESTE IMPORT

def card(title, content, icon=None, actions=None):
    """Componente de tarjeta elegante"""
    col1, col2 = st.columns([1, 20])
    
    if icon:
        with col1:
            st.markdown(f"<div style='font-size: 24px; color: var(--primary-color);'>{icon}</div>", unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"<h3 style='margin: 0;'>{title}</h3>", unsafe_allow_html=True)
    
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(content)
    
    if actions:
        col1, col2 = st.columns([3, 1])
        with col2:
            for action in actions:
                st.button(action["label"], key=action["key"])
    
    st.markdown("</div>", unsafe_allow_html=True)

def metric_card(value, label, icon, trend=None, subtitle=None):
    """Tarjeta de métrica elegante mejorada - OPTIMIZADA PARA ANCHO EXPANDIDO"""
    trend_html = ""
    if trend:
        trend_icon = "📈" if trend['value'].startswith('+') else "📉"
        trend_html = f"""
        <div style='color: {trend["color"]}; font-size: 0.8rem; margin-top: 0.25rem;
                    display: flex; align-items: center; gap: 0.25rem;'>
            {trend_icon} {trend['value']}
        </div>
        """
    
    subtitle_html = f"<div style='color: var(--text-muted); font-size: 0.85rem; margin-top: 0.25rem;'>{subtitle}</div>" if subtitle else ""
    
    return f"""
    <div class='card' style='text-align: center; padding: 1.5rem; background: var(--bg-card);
                            border: 1px solid var(--border-color); border-radius: var(--radius-xl);
                            transition: all 0.3s ease; min-height: 180px; display: flex;
                            flex-direction: column; justify-content: center;'>
        <div style='font-size: 2.5rem; color: var(--primary-color); margin-bottom: 0.75rem;
                    background: linear-gradient(135deg, var(--primary-color), var(--primary-light));
                    -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
            {icon}
        </div>
        <div style='font-size: 2rem; font-weight: 700; color: var(--text-primary); 
                    margin-bottom: 0.5rem; line-height: 1.2;'>
            {value}
        </div>
        <div style='color: var(--text-secondary); font-weight: 600; font-size: 1rem;
                    margin-bottom: 0.5rem; line-height: 1.3;'>
            {label}
        </div>
        {subtitle_html}
        {trend_html}
    </div>
    """

def badge(text, type="primary", icon=None):
    """Componente de badge elegante con iconos"""
    color_map = {
        "primary": "var(--primary-color)",
        "success": "var(--success-color)",
        "warning": "var(--warning-color)",
        "danger": "var(--danger-color)",
        "info": "var(--info-color)"
    }
    
    icon_html = f"<span style='margin-right: 0.25rem;'>{icon}</span>" if icon else ""
    
    return f"""
    <span class='badge badge-{type}' style='
        background-color: rgba({color_map[type].replace('var(', '').replace(')', '')}, 0.15); 
        color: {color_map[type]};
        display: inline-flex;
        align-items: center;
        padding: 0.35rem 0.9rem;
        border-radius: var(--radius-xl);
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba({color_map[type].replace('var(', '').replace(')', '')}, 0.3);
    '>
        {icon_html}{text}
    </span>
    """

def breadcrumb(current_page, show_date=True):
    """Componente de breadcrumb elegante mejorado - OPTIMIZADO PARA ANCHO EXPANDIDO"""
    icons = {
        "Inicio": "🏠",
        "Reclamos cargados": "📊", 
        "Gestión de clientes": "👥",
        "Imprimir reclamos": "🖨️",
        "Seguimiento técnico": "🔧",
        "Cierre de Reclamos": "✅"
    }
    
    date_section = ""
    if show_date:
        date_section = f"""
        <div style="flex: 1;"></div>
        <span style="color: var(--text-muted); font-size: 0.85rem;">
            {datetime.now().strftime('%d/%m/%Y %H:%M')}
        </span>
        """
    
    return f"""
    <div style="
        display: flex; 
        align-items: center; 
        gap: 0.75rem; 
        margin: 2rem 0 1.5rem 0; 
        padding: 1.25rem; 
        background: var(--bg-card); 
        border-radius: var(--radius-xl); 
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow-sm);
        font-size: 0.95rem;
    ">
        <span style="color: var(--text-muted); display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.2rem;">📋</span>
            <span>Estás en:</span>
        </span>
        
        <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem;
                    background: linear-gradient(135deg, var(--bg-surface), var(--bg-secondary));
                    border-radius: var(--radius-lg); border: 1px solid var(--border-light);">
            <span style="font-size: 1.1rem; color: var(--primary-color);">
                {icons.get(current_page, '📋')}
            </span>
            <span style="color: var(--primary-color); font-weight: 600;">
                {current_page}
            </span>
        </div>
        
        {date_section}
    </div>
    """

def loading_indicator(message="Cargando datos..."):
    """Indicador de carga elegante para componentes UI"""
    return f"""
    <div style="text-align: center; padding: 2rem;">
        <div style="
            width: 50px;
            height: 50px;
            border: 3px solid rgba(102, 217, 239, 0.3);
            border-top: 3px solid #66D9EF;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        "></div>
        <p style="color: var(--text-secondary); margin: 0; font-size: 0.9rem;">{message}</p>
    </div>
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    </style>
    """

def grid_container(columns=3, gap="1rem"):
    """Contenedor de grid optimizado para diseño expandido"""
    return f"""
    <div style="
        display: grid;
        grid-template-columns: repeat({columns}, 1fr);
        gap: {gap};
        width: 100%;
        margin: 1.5rem 0;
    ">
    """

def grid_item():
    """Item de grid para contenedor"""
    return "<div style='width: 100%;'>"

def grid_end():
    """Cierre del contenedor de grid"""
    return "</div>"

def expandable_section(title, content, expanded=False, icon="📦"):
    """Sección expandible optimizada para ancho completo"""
    expand_icon = "▼" if expanded else "►"
    return f"""
    <div style="
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        margin: 1rem 0;
        overflow: hidden;
    ">
        <div style="
            padding: 1rem 1.5rem;
            background: var(--bg-surface);
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-weight: 600;
            color: var(--text-primary);
        ">
            <span style="font-size: 1.1rem;">{icon}</span>
            <span style="flex: 1;">{title}</span>
            <span style="font-size: 0.9rem;">{expand_icon}</span>
        </div>
        <div style="padding: 1.5rem; display: {'block' if expanded else 'none'};">
            {content}
        </div>
    </div>
    """