# utils/styles.py - Estilo CRM Clean & Enterprise (Optimizado para rendimiento)

def get_crm_styles(dark_mode=False):
    """Estilo CRM moderno, limpio y ultrarrápido."""
    
    # CONFIGURACIÓN DE VARIABLES (Tokens de Diseño)
    if dark_mode:
        # Tema Oscuro Profesional (Slate/Navy)
        theme_vars = """
            --bg-app: #0f172a;          /* Fondo principal oscuro */
            --bg-surface: #1e293b;      /* Fondo de tarjetas/barras */
            --bg-input: #334155;        /* Inputs */
            
            --text-primary: #f1f5f9;    /* Texto blanco humo */
            --text-secondary: #94a3b8;  /* Texto grisáceo */
            
            --primary: #3b82f6;         /* Azul estándar moderno */
            --primary-hover: #2563eb;   
            --primary-light: rgba(59, 130, 246, 0.1);
            
            --accent: #0ea5e9;          /* Cyan para detalles */
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            
            --border: #334155;
            --radius: 8px;              /* Bordes redondeados consistentes */
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        """
    else:
        # Tema Claro CRM (Enterprise Standard)
        theme_vars = """
            --bg-app: #f1f5f9;          /* Fondo general gris muy suave */
            --bg-surface: #ffffff;      /* Fondo blanco puro para contenido */
            --bg-input: #f8fafc;        /* Inputs casi blancos */
            
            --text-primary: #1e293b;    /* Texto gris oscuro (casi negro) */
            --text-secondary: #64748b;  /* Texto gris medio */
            
            --primary: #2563eb;         /* Azul Royal (Color corporativo por excelencia) */
            --primary-hover: #1d4ed8;
            --primary-light: #eff6ff;   /* Fondo azul muy claro para hovers */
            
            --accent: #0ea5e9;          
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            
            --border: #e2e8f0;
            --radius: 8px;
            --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05);
        """

    return f"""
    <style>
    /* --- 1. RESET Y BASE --- */
    :root {{ {theme_vars} }}
    
    /* Fuente del sistema (Más rápido que cargar de Google Fonts) */
    .stApp {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: var(--bg-app);
        color: var(--text-primary);
    }}
    
    /* Ajuste de ancho máximo para enfocar el contenido (CRM Look) */
    .main .block-container {{
        max-width: 1200px !important;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }}

    /* --- 2. TIPOGRAFÍA --- */
    h1, h2, h3 {{
        color: var(--text-primary);
        font-weight: 700;
        letter-spacing: -0.025em;
    }}
    
    h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
    h2 {{ font-size: 1.5rem; margin-top: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }}
    
    /* --- 3. TARJETAS (Cards) --- */
    /* Clase helper para envolver contenido en tarjetas blancas */
    .crm-card {{
        background-color: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1.5rem;
        box-shadow: var(--shadow);
        margin-bottom: 1rem;
        height: 100%;
        transition: transform 0.1s ease, box-shadow 0.1s ease;
    }}
    
    /* Efecto hover sutil */
    .crm-card:hover {{
        border-color: var(--primary);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }}

    /* --- 4. BOTONES MODERNOS --- */
    .stButton > button {{
        border-radius: var(--radius);
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.2s;
        border: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }}

    /* Botón Primario */
    .stButton > button[kind="primary"] {{
        background-color: var(--primary);
        color: white;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: var(--primary-hover);
        transform: translateY(-1px);
    }}

    /* Botón Secundario */
    .stButton > button:not([kind="primary"]) {{
        background-color: transparent;
        color: var(--text-secondary);
        border: 1px solid var(--border);
    }}
    .stButton > button:not([kind="primary"]):hover {{
        background-color: var(--bg-input);
        color: var(--text-primary);
        border-color: var(--text-secondary);
    }}

    /* --- 5. INPUTS Y FORMULARIOS --- */
    /* Estilo limpio para inputs tipo "Fluent UI" o "Tailwind" */
    div[data-baseweb="input"], 
    div[data-baseweb="select"], 
    div[data-baseweb="textarea"] {{
        background-color: var(--bg-input) !important;
        border-radius: var(--radius) !important;
        border: 1px solid var(--border) !important;
    }}
    
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="select"]:focus-within {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px var(--primary-light) !important;
    }}

    label {{
        color: var(--text-secondary) !important;
        font-weight: 500 !important;
        font-size: 0.9rem !important;
    }}

    /* --- 6. TABLAS (DataFrames) - CRÍTICO PARA CRM --- */
    .dataframe {{
        border: none !important;
        border-radius: var(--radius) !important;
        overflow: hidden !important;
        font-size: 0.95rem;
    }}
    
    /* Encabezados de tabla */
    .dataframe thead th {{
        background-color: var(--bg-input);
        color: var(--text-secondary);
        font-weight: 600;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
        border-bottom: 2px solid var(--border);
        padding: 1rem;
        text-align: left !important;
    }}
    
    /* Celdas de tabla */
    .dataframe td {{
        padding: 0.75rem 1rem;
        border-bottom: 1px solid var(--border);
        color: var(--text-primary);
        vertical-align: middle;
    }}
    
    /* Filas alternas (Zebra striping sutil) */
    .dataframe tbody tr:nth-child(even) {{
        background-color: rgba(0,0,0,0.01);
    }}
    
    /* Hover en filas */
    .dataframe tbody tr:hover td {{
        background-color: var(--primary-light);
        color: var(--primary-hover);
    }}

    /* --- 7. SIDEBAR --- */
    section[data-testid="stSidebar"] {{
        background-color: var(--bg-surface);
        border-right: 1px solid var(--border);
    }}
    
    /* --- 8. MÉTRICAS --- */
    [data-testid="stMetric"] {{
        background-color: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1rem;
        box-shadow: var(--shadow);
    }}
    [data-testid="stMetricValue"] {{
        color: var(--primary) !important;
        font-weight: 700 !important;
    }}

    /* --- 9. HELPERS DE ESTADO (BADGES) --- */
    .badge {{
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }}
    .badge-success {{ background: rgba(16, 185, 129, 0.1); color: var(--success); }}
    .badge-warning {{ background: rgba(245, 158, 11, 0.1); color: var(--warning); }}
    .badge-danger {{ background: rgba(239, 68, 68, 0.1); color: var(--danger); }}

    /* --- 10. OCULTAR UI DE STREAMLIT --- */
    #MainMenu {{visibility: hidden;}}
    header {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    
    /* Eliminar el espacio vacío que deja el header al ocultarse */
    .stApp > header {{
        background-color: transparent;
    }}

    /* --- 11. PESTAÑAS (TABS) MODERNAS --- */
    div[data-baseweb="tab-list"] {{
        gap: 0.5rem;
        background-color: var(--bg-surface);
        padding: 0.5rem;
        border-radius: var(--radius);
        border: 1px solid var(--border);
        box-shadow: var(--shadow);
    }}
    
    div[data-baseweb="tab"] {{
        background-color: transparent !important;
        border: none !important;
        border-radius: calc(var(--radius) - 2px) !important;
        padding: 0.5rem 1rem !important;
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
        transition: all 0.2s ease;
    }}
    
    div[data-baseweb="tab"]:hover {{
        background-color: var(--bg-input) !important;
        color: var(--text-primary) !important;
    }}
    
    div[aria-selected="true"] {{
        background-color: var(--primary-light) !important;
        color: var(--primary) !important;
    }}

    /* --- 12. ACORDEONES (EXPANDERS) --- */
    div[data-testid="stExpander"] {{
        background-color: var(--bg-surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        overflow: hidden;
    }}
    
    div[data-testid="stExpander"] summary {{
        background-color: var(--bg-surface);
        padding: 1rem;
        font-weight: 600;
        color: var(--text-primary);
    }}
    
    div[data-testid="stExpander"] summary:hover {{
        color: var(--primary);
    }}

    </style>
    """

def render_metric_card(title, value, subtitle="", color="blue", icon="📊"):
    """Tarjeta de métrica mejorada con icono."""
    color_map = {
        "blue": "var(--primary)",
        "green": "var(--success)",
        "red": "var(--danger)",
        "orange": "var(--warning)"
    }
    c = color_map.get(color, "var(--primary)")
    
    return f"""
    <div class="crm-card" style="padding: 1.25rem; display: flex; align-items: center; gap: 1rem;">
        <div style="background-color: {c}; opacity: 0.9; color: white; min-width: 3.5rem; height: 3.5rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            {icon}
        </div>
        <div>
            <div style="color: var(--text-secondary); font-size: 0.875rem; font-weight: 500; margin-bottom: 0.25rem;">{title}</div>
            <div style="color: var(--text-primary); font-size: 1.75rem; font-weight: 700; line-height: 1;">{value}</div>
            {f'<div style="color: {c}; font-size: 0.75rem; margin-top: 0.35rem; font-weight: 600;">{subtitle}</div>' if subtitle else ''}
        </div>
    </div>
    """

def status_dot(status="active", text=""):
    """
    Genera un indicador de estado con un punto que palpita.
    status: 'active' (verde), 'warning' (naranja), 'danger' (rojo), 'offline' (gris)
    """
    color_map = {
        "active": "var(--success)",
        "warning": "var(--warning)",
        "danger": "var(--danger)",
        "offline": "var(--text-secondary)"
    }
    color = color_map.get(status, "var(--success)")
    
    return f"""
    <div style="display: flex; align-items: center; gap: 0.6rem;">
        <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 12px; height: 12px;">
            <div style="position: absolute; width: 100%; height: 100%; background-color: {color}; border-radius: 50%; opacity: 0.6; animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;"></div>
            <div style="position: relative; width: 8px; height: 8px; background-color: {color}; border-radius: 50%;"></div>
        </div>
        <span style="color: var(--text-primary); font-size: 0.9rem; font-weight: 600;">{text}</span>
    </div>
    <style>
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: .3; transform: scale(1.5); }}
    }}
    </style>
    """

# --- FUNCIONES RESTAURADAS PARA COMPATIBILIDAD ---

def get_loading_spinner():
    """Spinner de carga moderno con estilo CRM (restaurado para compatibilidad)"""
    return """
    <div style="
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        background-color: var(--bg-app);
        z-index: 9999;
        opacity: 0.95;
    ">
        <div style="text-align: center;">
            <div style="
                width: 50px;
                height: 50px;
                border: 4px solid var(--bg-input);
                border-top: 4px solid var(--primary);
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 0 auto 1rem;
            "></div>
            <p style="color: var(--text-primary); font-weight: 600;">Cargando Fusion CRM...</p>
        </div>
        <style>
        @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
        }}
        </style>
    </div>
    """

def loading_indicator(message="Cargando datos..."):
    """Indicador de carga elegante (restaurado para compatibilidad)"""
    return f"""
    <div style="text-align: center; padding: 2rem;">
        <div style="
            width: 40px;
            height: 40px;
            border: 3px solid var(--bg-input);
            border-top: 3px solid var(--primary);
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