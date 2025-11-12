"""
Módulo centralizado para el manejo de fechas en la aplicación
Incluye funciones para parsing, formateo y operaciones con zonas horarias
"""
from datetime import datetime
import pytz
import pandas as pd
from typing import Union, Optional

# Configuración de zona horaria (constante global)
ARGENTINA_TZ = pytz.timezone("America/Argentina/Buenos_Aires")

def ahora_argentina() -> datetime:
    """Devuelve la fecha y hora actual en zona horaria Argentina"""
    return datetime.now(ARGENTINA_TZ)

def parse_fecha(
    fecha_str: Union[str, float, pd.Timestamp, datetime, None], 
    dayfirst: bool = True
) -> Union[datetime, pd.NaT]:
    """
    Convierte un string/objeto a datetime con zona horaria Argentina.
    Maneja múltiples formatos y casos especiales.
    
    Args:
        fecha_str: String u objeto que representa una fecha
        dayfirst: Si True, interpreta el primer número como día (default True para formato argentino)
    
    Returns:
        datetime con zona horaria o pd.NaT si no se puede parsear
    """
    if pd.isna(fecha_str) or fecha_str in (None, "", "NaT"):
        return pd.NaT
    
    # Si ya es un datetime con timezone, lo devolvemos tal cual
    if isinstance(fecha_str, datetime) and fecha_str.tzinfo is not None:
        return fecha_str.astimezone(ARGENTINA_TZ)
    
    # Si es datetime sin timezone, le asignamos la zona horaria
    if isinstance(fecha_str, datetime):
        return ARGENTINA_TZ.localize(fecha_str)
    
    # Si es un Timestamp de pandas
    if isinstance(fecha_str, pd.Timestamp):
        return fecha_str.to_pydatetime().astimezone(ARGENTINA_TZ)
    
    # Convertimos a string y limpiamos
    fecha_str = str(fecha_str).strip()
    if not fecha_str:
        return pd.NaT
    
    # Lista de formatos compatibles (ordenados por probabilidad de uso)
    formatos = [
        '%d/%m/%Y %H:%M:%S',  # 25/12/2023 14:30:45
        '%d-%m-%Y %H:%M:%S',  # 25-12-2023 14:30:45
        '%d/%m/%Y %H:%M',     # 25/12/2023 14:30
        '%d-%m-%Y %H:%M',     # 25-12-2023 14:30
        '%Y-%m-%d %H:%M:%S',  # 2023-12-25 14:30:45 (ISO)
        '%Y/%m/%d %H:%M:%S',  # 2023/12/25 14:30:45
        '%d/%m/%Y',           # 25/12/2023
        '%d-%m-%Y',           # 25-12-2023
        '%Y%m%d %H:%M:%S',    # 20231225 14:30:45
        '%Y%m%d',             # 20231225
    ]
    
    # Intentar con cada formato
    for fmt in formatos:
        try:
            dt = datetime.strptime(fecha_str, fmt)
            # Si el formato no incluye hora, establecer medianoche
            if '%H' not in fmt:
                dt = dt.replace(hour=0, minute=0, second=0)
            return ARGENTINA_TZ.localize(dt)
        except ValueError:
            continue
    
    # Si ningún formato funcionó, intentar con pandas (más flexible)
    try:
        dt = pd.to_datetime(fecha_str, dayfirst=dayfirst, errors='coerce')
        if pd.notna(dt):
            if isinstance(dt, pd.Timestamp):
                dt = dt.to_pydatetime()
            if dt.tzinfo is None:
                return ARGENTINA_TZ.localize(dt)
            return dt.astimezone(ARGENTINA_TZ)
    except Exception:
        pass
    
    return pd.NaT

def format_fecha(
    fecha: Union[datetime, pd.Timestamp, str, None], 
    formato: str = '%d/%m/%Y %H:%M',
    default_text: str = "Fecha no disponible"
) -> str:
    """
    Formatea una fecha a string según el formato especificado.
    
    Args:
        fecha: Objeto fecha a formatear (datetime, str, pd.Timestamp o None)
        formato: String de formato (default: '%d/%m/%Y %H:%M')
        default_text: Texto a devolver si la fecha es inválida
    
    Returns:
        String con la fecha formateada o default_text si no se puede formatear
    """
    if pd.isna(fecha) or fecha is None:
        return default_text
    
    try:
        # Si es string, primero parsear
        if isinstance(fecha, str):
            fecha = parse_fecha(fecha)
            if pd.isna(fecha):
                return default_text
        
        # Convertir a datetime con zona horaria si es necesario
        if isinstance(fecha, pd.Timestamp):
            fecha = fecha.to_pydatetime()
        
        if isinstance(fecha, datetime):
            if fecha.tzinfo is None:
                fecha = ARGENTINA_TZ.localize(fecha)
            else:
                fecha = fecha.astimezone(ARGENTINA_TZ)
            return fecha.strftime(formato)
    except Exception:
        pass
    
    return default_text

def es_fecha_valida(fecha: Union[datetime, str, pd.Timestamp, None]) -> bool:
    """Verifica si una fecha es válida y puede ser parseada"""
    if pd.isna(fecha) or fecha is None:
        return False
    try:
        parsed = parse_fecha(fecha)
        return not pd.isna(parsed)
    except Exception:
        return False

def diferencia_fechas(
    fecha1: Union[datetime, str], 
    fecha2: Union[datetime, str],
    unidad: str = 'horas'
) -> Optional[float]:
    """
    Calcula la diferencia entre dos fechas en la unidad especificada.
    
    Args:
        fecha1: Primera fecha (puede ser string o datetime)
        fecha2: Segunda fecha (puede ser string o datetime)
        unidad: Unidad de retorno ('horas', 'minutos', 'dias', 'segundos')
    
    Returns:
        Diferencia en la unidad especificada o None si hay error
    """
    try:
        dt1 = parse_fecha(fecha1)
        dt2 = parse_fecha(fecha2)
        
        if pd.isna(dt1) or pd.isna(dt2):
            return None
            
        diff = dt2 - dt1 if dt2 > dt1 else dt1 - dt2
        segundos = diff.total_seconds()
        
        unidades = {
            'horas': segundos / 3600,
            'minutos': segundos / 60,
            'dias': segundos / 86400,
            'segundos': segundos
        }
        
        return unidades.get(unidad.lower(), segundos / 3600)
    except Exception:
        return None