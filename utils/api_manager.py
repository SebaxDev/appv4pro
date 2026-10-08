"""
Módulo para gestión segura de datos con Google Sheets
Versión 4.0 - Con manejo robusto de errores y reintentos automáticos (Tenacity)
"""
import streamlit as st
import time
from typing import List, Dict, Union, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

class ApiManager:
    def __init__(self):
        self.total_calls = 0
        self.error_count = 0
        self.last_call = 0

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _execute_with_retry(self, func, *args, **kwargs):
        """Ejecuta la función de gspread con reintentos automáticos si la API falla"""
        return func(*args, **kwargs)

    def safe_sheet_operation(self, func, *args, is_batch=False, **kwargs):
        """
        Ejecuta una operación segura sobre la API de Google Sheets
        
        Args:
            func: función de gspread a ejecutar
            *args: argumentos posicionales para la función
            is_batch: bool, si es operación por lote (sólo informativo)
            **kwargs: argumentos clave
        
        Returns:
            tuple: (resultado, error) donde error es None si fue exitoso
        """
        try:
            self.total_calls += 1
            self.last_call = time.time()
            
            # Llamamos a la función a través de nuestro blindaje de reintentos
            result = self._execute_with_retry(func, *args, **kwargs)
            return result, None
            
        except Exception as e:
            self.error_count += 1
            return None, str(e)

    def get_api_stats(self):
        """
        Devuelve estadísticas de uso de la API actual
        """
        return {
            "total_calls": self.total_calls,
            "error_count": self.error_count,
            "last_call": self.last_call
        }

@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=10))
def _execute_batch_update_with_retry(worksheet, updates):
    """Ejecuta un batch_update con reintentos automáticos"""
    worksheet.batch_update(updates)

def batch_update_sheet(worksheet, updates: List[Dict[str, Union[str, List[List[str]]]]]) -> bool:
    """
    Realiza actualizaciones por lotes en una hoja de cálculo
    
    Args:
        worksheet: objeto de hoja de cálculo de gspread
        updates: lista de diccionarios con formato:
            [{"range": "A1:B2", "values": [["val1", "val2"], ["val3", "val4"]]}]
    
    Returns:
        bool: True si la operación fue exitosa
    """
    if not updates:
        return True
        
    try:
        # Llamamos al batch update a través de nuestro blindaje
        _execute_batch_update_with_retry(worksheet, updates)
        return True
    except Exception as e:
        st.error(f"Error en batch_update: {str(e)}")
        return False

# Instancia única global
api_manager = ApiManager()

def init_api_session_state():
    """
    Inicializa api_manager en st.session_state si no existe aún
    """
    if "api_stats" not in st.session_state:
        st.session_state.api_stats = api_manager.get_api_stats()