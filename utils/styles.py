# styles.py - Versión con modo oscuro Monokai y ancho expandido
"""Estilos CSS profesionales tipo CRM con diseño expandido"""

def get_main_styles_v2(dark_mode=True):
    """Devuelve estilos CSS profesionales para modo claro/oscuro con ancho expandido"""
    
    if dark_mode:
        # PALETA MONOKAI (modo oscuro gris)
        theme_vars = """
            --primary-color: #66D9EF;     /* Azul verdoso Monokai */
            --primary-light: #78C6E9;     /* Azul más claro */
            --secondary-color: #F92672;   /* Magenta Monokai */
            --success-color: #A6E22E;     /* Verde Monokai */
            --warning-color: #FD971F;     /* Naranja Monokai */
            --danger-color: #FF6188;      /* Rosa-rojo Monokai */
            --info-color: #AE81FF;        /* Púrpura Monokai */
            
            --bg-primary: #272822;        /* Fondo principal Monokai */
            --bg-secondary: #2D2E27;      /* Fondo secundario */
            --bg-surface: #3E3D32;        /* Superficie de elementos */
            --bg-card: #383830;           /* Tarjetas */
            
            --text-primary: #F8F8F2;      /* Texto principal */
            --text-secondary: #CFCFC2;    /* Texto secundario */
            --text-muted: #75715E;        /* Texto atenuado */
            
            --border-color: #49483E;      /* Color de bordes */
            --border-light: #5E5D56;      /* Bordes claros */
            
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.2);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.3), 0 2px 4px -1px rgba(0,0,0,0.2);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.4), 0 4px 6px -2px rgba(0,0,0,0.25);
            
            --radius-sm: 0.25rem;
            --radius-md: 0.375rem;
            --radius-lg: 0.5rem;
            --radius-xl: 0.75rem;
        """
    else:
        # --- NUEVO TEMA CLARO ESTILO MONOKAI ---
        theme_vars = """
            --primary-color: #F92672;   /* Magenta Monokai */
            --primary-light: #ff79c6;   /* Rosa más claro para hover */
            --secondary-color: #AE81FF; /* Púrpura Monokai */
            --success-color: #50fa7b;   /* Verde Dracula/Monokai brillante */
            --warning-color: #FD971F;   /* Naranja Monokai */
            --danger-color: #ff5555;    /* Rojo Dracula */
            --info-color: #66D9EF;      /* Cian Monokai */
            
            --bg-primary: #FDFDFD;
            --bg-secondary: #F8FAFC;
            --bg-surface: #F1F5F9;
            --bg-card: #FFFFFF;
            
            --text-primary: #282a36;    /* Texto oscuro (Dracula bg) */
            --text-secondary: #44475a;  /* Texto gris (Dracula comment) */
            --text-muted: #999999;
            
            --border-color: #E2E8F0;
            --border-light: #F1F5F9;
            
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
            --shadow-md: 0 3px 6px rgba(0,0,0,0.06);
            --shadow-lg: 0 8px 16px rgba(0,0,0,0.08);
            
            --radius-sm: 0.25rem;
            --radius-md: 0.375rem;
            --radius-lg: 0.5rem;
            --radius-xl: 0.75rem;
        """
    
    return f"""
    <style>
    :root {{
        {theme_vars}
    }}
    
    /* Fuentes modernas */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }}
    
    body, .stApp {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        background-color: var(--bg-primary);
        color: var(--text-primary);
        line-height: 1.6;
    }}
    
    /* MEJORAS PARA CONTENEDORES PRINCIPALES - ANCHO AJUSTADO */
    .main .block-container {{
        max-width: 1300px !important;
        margin: 0 auto !important;
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
    }}
    
    /* Cuando el sidebar está colapsado, expandimos el ancho */
    [data-testid="stSidebarCollapsed"] ~ .main .block-container {{
        max-width: 90% !important;
        padding-left: 5%;
        padding-right: 5%;
    }}
    
    /* Ajustar el ancho de los elementos internos */
    [data-testid="stSidebarCollapsed"] ~ .main .stButton > button {{
        min-width: auto;
    }}
    
    /* Mejorar la visualización de formularios en modo expandido */
    [data-testid="stSidebarCollapsed"] ~ .main .stTextInput > div > div,
    [data-testid="stSidebarCollapsed"] ~ .main .stSelectbox > div > div,
    [data-testid="stSidebarCollapsed"] ~ .main .stTextArea > div > div {{
        width: 100% !important;
        max-width: none !important;
    }}
    
    /* Mejoras específicas para formularios en modo de pantalla completa */
    [data-testid="stSidebarCollapsed"] ~ .main .element-container {{
        max-width: 100% !important;
    }}

    [data-testid="stSidebarCollapsed"] ~ .main .stTextInput > div > div > input {{
        width: 100% !important;
        max-width: none !important;
    }}

    [data-testid="stSidebarCollapsed"] ~ .main .stSelectbox > div > div > select {{
        width: 100% !important;
        max-width: none !important;
    }}

    [data-testid="stSidebarCollapsed"] ~ .main .stTextArea > div > div > textarea {{
        width: 100% !important;
        max-width: none !important;
    }}

    /* Ajustar columnas en grid */
    [data-testid="stSidebarCollapsed"] ~ .main .stHorizontalBlock > div {{
        gap: 1.5rem;
    }}

    [data-testid="stSidebarCollapsed"] ~ .main .stColumn {{
        min-width: auto !important;
    }}
    
    /* Para pantallas muy grandes */
    @media (min-width: 1600px) {{
        .main .block-container {{
            max-width: 2000px !important;
            padding-left: 5rem;
            padding-right: 5rem;
        }}
        
        .card {{
            padding: 2rem;
        }}
        
        /* Grid de 4 columnas en lugar de 3 */
        .stHorizontalBlock > div {{
            grid-template-columns: repeat(4, 1fr) !important;
        }}
    }}
    
    /* HEADERS MODERNOS */
    h1, h2, h3, h4, h5, h6 {{
        font-weight: 600;
        margin-bottom: 0.75rem;
        color: var(--text-primary);
        letter-spacing: -0.025em;
    }}
    
    h1 {{
        font-size: 2.25rem;
        line-height: 2.5rem;
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-light) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1.5rem;
    }}
    
    h2 {{
        font-size: 1.875rem;
        line-height: 2.25rem;
        color: var(--text-primary);
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--border-color);
        margin-top: 2rem;
    }}
    
    h3 {{
        font-size: 1.5rem;
        line-height: 2rem;
        color: var(--text-primary);
    }}
    
    /* BOTONES MODERNOS */
    .stButton > button {{
        border: none;
        border-radius: var(--radius-lg);
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
        cursor: pointer;
        box-shadow: var(--shadow-md);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
    }}
    
    .stButton > button:focus {{
        outline: none;
        box-shadow: 0 0 0 3px rgba(102, 217, 239, 0.3);
    }}
    
    /* Botón primario */
    .stButton > button:first-child {{
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-light) 100%);
        color: #272822;
        font-weight: 600;
        border: none;
    }}
    
    .stButton > button:first-child:hover {{
        background: linear-gradient(135deg, var(--primary-light) 0%, var(--primary-color) 100%);
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
    }}
    
    /* Botón secundario */
    .stButton > button:not(:first-child) {{
        background: transparent;
        color: var(--primary-color);
        border: 1px solid var(--primary-color);
    }}
    
    .stButton > button:not(:first-child):hover {{
        background: var(--primary-color);
        color: #272822;
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
    }}
    
    /* TARJETAS Y CONTENEDORES ELEGANTES */
    .card {{
        background: var(--bg-card);
        border-radius: var(--radius-xl);
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: var(--shadow-md);
        border: 1px solid var(--border-color);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    .card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2);
        border-color: var(--primary-color);
    }}
    
    .card-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-color);
    }}
    
    .card-title {{
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
    }}
    
    /* FORMULARIOS ELEGANTES */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {{
        background-color: var(--bg-surface);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: 0.75rem;
        color: var(--text-primary);
        font-size: 0.875rem;
        transition: all 0.2s ease;
    }}
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus,
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus {{
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(102, 217, 239, 0.2);
        outline: none;
    }}
    
    /* LABELS MEJORADOS */
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stNumberInput label,
    .stDateInput label {{
        font-weight: 500;
        color: var(--text-primary);
        margin-bottom: 0.5rem;
        display: block;
    }}
    
    /* SIDEBAR PROFESIONAL */
    .css-1d391kg {{
        background: var(--bg-secondary) !important;
        border-right: 1px solid var(--border-color);
    }}
    
    .css-1d391kg .stButton > button {{
        width: 100%;
        justify-content: flex-start;
        margin-bottom: 0.5rem;
        border-radius: var(--radius-md);
        background: transparent;
        color: var(--text-primary);
        border: 1px solid transparent;
    }}
    
    .css-1d391kg .stButton > button:hover {{
        background: var(--bg-surface);
        border-color: var(--primary-color);
    }}
    
    /* MEJORAS PARA TABLAS */
    .dataframe {{
        border-radius: var(--radius-lg);
        overflow: hidden;
        box-shadow: var(--shadow-md);
        border: 1px solid var(--border-color);
        margin: 1rem 0;
        min-width: 100% !important;
    }}
    
    .dataframe thead th {{
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-light) 100%);
        color: #272822;
        font-weight: 600;
        padding: 1rem;
        text-align: left;
        border: none;
    }}
    
    .dataframe tbody td {{
        padding: 0.875rem 1rem;
        border-bottom: 1px solid var(--border-light);
        background-color: var(--bg-surface);
        color: var(--text-primary);
        transition: all 0.2s ease;
    }}
    
    .dataframe tbody tr:hover td {{
        background-color: var(--bg-secondary);
        transform: scale(1.02);
    }}
    
    /* Mejorar visualización de tablas en modo expandido */
    .dataframe th, .dataframe td {{
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    
    /* Asegurar que los charts ocupen todo el ancho */
    [data-testid="stSidebarCollapsed"] ~ .main .stPlotlyChart {{
        width: 100% !important;
    }}
    
    /* NOTIFICACIONES Y ALERTAS MEJORADAS */
    .stAlert {{
        border-radius: var(--radius-lg);
        border: none;
        box-shadow: var(--shadow-md);
        padding: 1rem 1.5rem;
        margin-bottom: 1rem;
    }}

    .stAlert[data-baseweb="notification"] {{
        background-color: var(--bg-surface);
        border-left: 4px solid var(--info-color);
    }}
    
    .stAlert[data-baseweb="notification"].success {{
        border-left-color: var(--success-color);
    }}

    .stAlert[data-baseweb="notification"].warning {{
        border-left-color: var(--warning-color);
    }}

    .stAlert[data-baseweb="notification"].error {{
        border-left-color: var(--danger-color);
    }}

    /* BADGES Y ETIQUETAS */
    .badge {{
        display: inline-flex;
        align-items: center;
        padding: 0.35rem 0.9rem;
        border-radius: var(--radius-xl);
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(102, 217, 239, 0.3);
    }}
    
    .badge-primary {{
        background-color: rgba(102, 217, 239, 0.15);
        color: var(--primary-color);
    }}
    
    .badge-success {{
        background-color: rgba(166, 226, 46, 0.15);
        color: var(--success-color);
    }}
    
    .badge-warning {{
        background-color: rgba(253, 151, 31, 0.15);
        color: var(--warning-color);
    }}
    
    .badge-danger {{
        background-color: rgba(255, 97, 136, 0.15);
        color: var(--danger-color);
    }}
    
    .badge-info {{
        background-color: rgba(174, 129, 255, 0.15);
        color: var(--info-color);
    }}
    
    /* GRID SYSTEM MEJORADO */
    .stHorizontalBlock > div {{
        gap: 1rem;
    }}
    
    /* SCROLLBAR PERSONALIZADO */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    
    ::-webkit-scrollbar-track {{
        background: var(--bg-surface);
        border-radius: var(--radius-md);
    }}
    
    ::-webkit-scrollbar-thumb {{
        background: var(--border-color);
        border-radius: var(--radius-md);
    }}
    
    ::-webkit-scrollbar-thumb:hover {{
        background: var(--text-muted);
    }}
    
    /* EFECTO DE CARGA SKELETON */
    .skeleton {{
        background: linear-gradient(90deg, var(--bg-surface) 25%, var(--bg-secondary) 50%, var(--bg-surface) 75%);
        background-size: 200% 100%;
        animation: loading 1.5s infinite;
        border-radius: var(--radius-md);
    }}
    
    @keyframes loading {{
        0% {{ background-position: 200% 0; }}
        100% {{ background-position: -200% 0; }}
    }}
    
    /* RESPONSIVE DESIGN */
    @media (max-width: 768px) {{
        .main .block-container {{
            padding: 1rem;
            max-width: 100% !important;
        }}
        
        [data-testid="stSidebarCollapsed"] ~ .main .block-container {{
            padding-left: 1rem;
            padding-right: 1rem;
            max-width: 100% !important;
        }}
        
        .card {{
            padding: 1rem;
            margin-bottom: 1rem;
        }}
        
        h1 {{
            font-size: 1.875rem;
            line-height: 2.25rem;
        }}
        
        h2 {{
            font-size: 1.5rem;
            line-height: 2rem;
        }}
        
        /* Ajustar grid para móviles */
        .stHorizontalBlock > div {{
            grid-template-columns: 1fr !important;
            gap: 1rem;
        }}
    }}
    
    /* Botón para toggle sidebar */
    .sidebar-toggle {{
        position: fixed;
        top: 10px;
        left: 10px;
        z-index: 9999;
        background: var(--primary-color);
        color: white;
        border: none;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        box-shadow: var(--shadow-md);
    }}
    
    .sidebar-toggle:hover {{
        transform: scale(1.1);
    }}
    </style>
    """

def get_loading_spinner():
    """Spinner de carga moderno con estilo Monokai mejorado"""
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
        background-color: rgba(39, 40, 34, 0.95);
        z-index: 9999;
        backdrop-filter: blur(8px);
    ">
        <div style="text-align: center;">
            <div style="
                width: 80px;
                height: 80px;
                border: 4px solid rgba(73, 72, 62, 0.3);
                border-radius: 50%;
                border-top-color: #66D9EF;
                border-right-color: #F92672;
                border-bottom-color: #A6E22E;
                animation: spin 1.5s ease-in-out infinite;
                margin-bottom: 1rem;
            "></div>
            <p style="color: #F8F8F2; font-size: 1.1rem; font-weight: 500; margin: 0;">
                Cargando Fusion CRM...
            </p>
            <p style="color: #75715E; font-size: 0.9rem; margin: 0.5rem 0 0 0;">
                ⚡ Optimizado para rendimiento
            </p>
        </div>
        <style>
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        </style>
    </div>
    """

def loading_indicator(message="Cargando datos..."):
    """Indicador de carga elegante"""
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