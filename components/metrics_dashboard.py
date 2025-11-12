"""
Componente del dashboard de métricas profesional
Versión 3.0 - Diseño tipo CRM con tarjetas elegantes
"""
import streamlit as st
import pandas as pd
from datetime import datetime

def metric_card(value, label, icon, trend=None, delta=None):
    """Componente de tarjeta de métrica profesional"""
    
    trend_html = f"""
    <div style='display: flex; align-items: center; justify-content: center; gap: 0.25rem; font-size: 0.8rem; margin-top: 0.25rem;'>
        <span style='color: {"var(--success-color)" if (delta or 0) >= 0 else "var(--danger-color)"}'>
            {"↗️" if (delta or 0) >= 0 else "↘️"} {abs(delta or 0)}%
        </span>
    </div>
    """ if trend and delta is not None else ""
    
    return f"""
    <div class='card' style='text-align: center; padding: 1.5rem 1rem; margin: 0;'>
        <div style='font-size: 2.5rem; margin-bottom: 0.5rem; color: var(--primary-color);'>{icon}</div>
        <div style='font-size: 2rem; font-weight: 700; color: var(--text-primary); line-height: 1;'>{value}</div>
        <div style='color: var(--text-secondary); font-size: 0.9rem; margin: 0.5rem 0;'>{label}</div>
        {trend_html}
    </div>
    """

def status_badge(status, count):
    """Badge de estado para métricas"""
    status_config = {
        "Pendiente": {"color": "var(--warning-color)", "icon": "⏳"},
        "En curso": {"color": "var(--info-color)", "icon": "🔧"},
        "Resuelto": {"color": "var(--success-color)", "icon": "✅"},
        "Desconexión": {"color": "var(--danger-color)", "icon": "🔌"},
        "Cerrado": {"color": "var(--text-muted)", "icon": "🔒"}
    }
    
    config = status_config.get(status, {"color": "var(--text-muted)", "icon": "❓"})
    
    return f"""
    <div style='display: flex; align-items: center; justify-content: space-between; padding: 0.75rem; background: {config["color"]}15; border-radius: var(--radius-md); border: 1px solid {config["color"]}30; margin: 0.25rem 0;'>
        <span style='display: flex; align-items: center; gap: 0.5rem;'>
            <span style='color: {config["color"]};'>{config["icon"]}</span>
            <span style='color: var(--text-primary);'>{status}</span>
        </span>
        <span style='font-weight: 600; color: {config["color"]};'>{count}</span>
    </div>
    """

def render_metrics_dashboard(df_reclamos, is_mobile=False):
    """Renderiza el dashboard de métricas profesional"""
    try:
        if df_reclamos.empty:
            st.warning("No hay datos de reclamos para mostrar")
            return

        df_metricas = df_reclamos.copy()

        # Procesamiento de datos
        df_activos = df_metricas[df_metricas["Estado"].isin(["Pendiente", "En curso"])]
        total_activos = len(df_activos)
        pendientes = len(df_activos[df_activos["Estado"] == "Pendiente"])
        en_curso = len(df_activos[df_activos["Estado"] == "En curso"])
        resueltos = len(df_metricas[df_metricas["Estado"] == "Resuelto"])
        desconexiones = df_metricas["Estado"].str.strip().str.lower().eq("desconexión").sum()
        
        # Calcular porcentajes para tendencias
        total_reclamos = len(df_metricas)
        porcentaje_activos = (total_activos / total_reclamos * 100) if total_reclamos > 0 else 0
        porcentaje_resueltos = (resueltos / total_reclamos * 100) if total_reclamos > 0 else 0

        # Header del dashboard
        st.markdown("""
        <div style="margin: 2rem 0 1.5rem 0;">
            <h2 style="display: flex; align-items: center; gap: 0.5rem; margin: 0;">
                <span>📈</span> Dashboard de Métricas
            </h2>
            <p style="color: var(--text-secondary); margin: 0.5rem 0 0 0;">
                Resumen general de la gestión de reclamos
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Diseño responsive
        if is_mobile:
            # Diseño para móviles (2 columnas)
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(metric_card(total_activos, "Activos", "📄", delta=12), unsafe_allow_html=True)
                st.markdown(metric_card(en_curso, "En Curso", "🔧"), unsafe_allow_html=True)
                
            with col2:
                st.markdown(metric_card(pendientes, "Pendientes", "⏳", delta=-5), unsafe_allow_html=True)
                st.markdown(metric_card(resueltos, "Resueltos", "✅", delta=8), unsafe_allow_html=True)
                
            # Sección de estados
            st.markdown("""
            <div style="margin-top: 1.5rem;">
                <h4 style="margin: 0 0 1rem 0; color: var(--text-primary);">📊 Distribución por Estado</h4>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(status_badge("Pendiente", pendientes), unsafe_allow_html=True)
            st.markdown(status_badge("En curso", en_curso), unsafe_allow_html=True)
            st.markdown(status_badge("Resuelto", resueltos), unsafe_allow_html=True)
            if desconexiones > 0:
                st.markdown(status_badge("Desconexión", desconexiones), unsafe_allow_html=True)
                
        else:
            # Diseño para desktop (4 columnas)
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(metric_card(total_activos, "Reclamos Activos", "📄", delta=12), unsafe_allow_html=True)
            with col2:
                st.markdown(metric_card(pendientes, "Pendientes", "⏳", delta=-5), unsafe_allow_html=True)
            with col3:
                st.markdown(metric_card(en_curso, "En Curso", "🔧"), unsafe_allow_html=True)
            with col4:
                st.markdown(metric_card(resueltos, "Resueltos", "✅", delta=8), unsafe_allow_html=True)
            
            # Segunda fila de métricas
            col5, col6, col7, col8 = st.columns(4)
            
            with col5:
                st.markdown(metric_card(f"{porcentaje_activos:.1f}%", "Tasa de Activos", "📊"), unsafe_allow_html=True)
            with col6:
                st.markdown(metric_card(f"{porcentaje_resueltos:.1f}%", "Tasa de Resolución", "🎯"), unsafe_allow_html=True)
            with col7:
                st.markdown(metric_card(desconexiones, "Desconexiones", "🔌"), unsafe_allow_html=True)
            with col8:
                st.markdown(metric_card(total_reclamos, "Total Reclamos", "📋"), unsafe_allow_html=True)
            
            # Sección de estados en columnas
            st.markdown("""
            <div style="margin: 2rem 0 1rem 0;">
                <h4 style="margin: 0 0 1rem 0; color: var(--text-primary);">📊 Distribución por Estado</h4>
            </div>
            """, unsafe_allow_html=True)
            
            estado_col1, estado_col2, estado_col3, estado_col4 = st.columns(4)
            
            with estado_col1:
                st.markdown(status_badge("Pendiente", pendientes), unsafe_allow_html=True)
            with estado_col2:
                st.markdown(status_badge("En curso", en_curso), unsafe_allow_html=True)
            with estado_col3:
                st.markdown(status_badge("Resuelto", resueltos), unsafe_allow_html=True)
            with estado_col4:
                if desconexiones > 0:
                    st.markdown(status_badge("Desconexión", desconexiones), unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div style='padding: 0.75rem; background: var(--bg-surface); border-radius: var(--radius-md); border: 1px solid var(--border-color); text-align: center; color: var(--text-muted);'>
                        No hay desconexiones
                    </div>
                    """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error al mostrar métricas: {str(e)}")
        if st.session_state.get('DEBUG_MODE', False):
            st.exception(e)