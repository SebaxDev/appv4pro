# helpers.py - Funciones utilitarias para la aplicación

import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

def show_warning(message):
    """Muestra un warning elegante"""
    st.warning(f"⚠️ {message}")

def show_error(message):
    """Muestra un error elegante"""
    st.error(f"❌ {message}")

def show_success(message):
    """Muestra un mensaje de éxito elegante"""
    st.success(f"✅ {message}")

def show_info(message):
    """Muestra un mensaje informativo elegante"""
    st.info(f"ℹ️ {message}")

def format_phone_number(phone):
    """Formatea un número de teléfono argentino"""
    if pd.isna(phone) or phone == '':
        return ''
    
    phone_str = str(phone).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    if phone_str.startswith('54'):
        phone_str = phone_str[2:]
    
    if phone_str.startswith('0'):
        phone_str = phone_str[1:]
    
    if len(phone_str) == 10:
        return f"+54 {phone_str[:3]} {phone_str[3:7]} {phone_str[7:]}"
    elif len(phone_str) == 8:
        return f"+54 11 {phone_str[:4]} {phone_str[4:]}"
    else:
        return phone_str

def format_dni(dni):
    """Formatea un DNI con puntos"""
    if pd.isna(dni) or dni == '':
        return ''
    
    dni_str = str(dni).strip().replace('.', '')
    if len(dni_str) > 3:
        return f"{dni_str[:-3]}.{dni_str[-3:]}"
    return dni_str

def get_current_datetime():
    """Obtiene la fecha y hora actual de Argentina"""
    return datetime.now(pytz.timezone('America/Argentina/Buenos_Aires'))

def format_datetime(dt, format_str='%d/%m/%Y %H:%M'):
    """Formatea un datetime object"""
    if pd.isna(dt):
        return ''
    return dt.strftime(format_str)

def truncate_text(text, max_length=50):
    """Trunca texto muy largo"""
    if pd.isna(text) or text == '':
        return ''
    text_str = str(text)
    return text_str[:max_length] + '...' if len(text_str) > max_length else text_str

def is_valid_email(email):
    """Valida formato básico de email"""
    if pd.isna(email) or email == '':
        return False
    return '@' in str(email) and '.' in str(email)

def safe_float_conversion(value, default=0.0):
    """Convierte seguro a float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int_conversion(value, default=0):
    """Convierte seguro a int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def get_status_badge(status):
    """Devuelve un badge colorizado según el estado"""
    status_colors = {
        'Pendiente': 'warning',
        'En Proceso': 'info',
        'Resuelto': 'success',
        'Cerrado': 'success',
        'Cancelado': 'danger',
        'Derivado': 'primary'
    }
    return status, status_colors.get(status, 'secondary')

def format_currency(amount):
    """Formatea un monto como currency argentino"""
    try:
        amount_float = safe_float_conversion(amount)
        return f"${amount_float:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except:
        return str(amount)

def get_breadcrumb_icon(page_name):
    """Devuelve el icono correspondiente para el breadcrumb"""
    icons = {
        "Inicio": "🏠",
        "Reclamos cargados": "📊",
        "Gestión de clientes": "👥",
        "Imprimir reclamos": "🖨️",
        "Seguimiento técnico": "🔧",
        "Cierre de Reclamos": "✅"
    }
    return icons.get(page_name, "📋")