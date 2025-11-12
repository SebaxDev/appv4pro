# components/notifications.py

import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
from utils.date_utils import ahora_argentina, format_fecha
from utils.api_manager import api_manager
from utils.data_manager import safe_get_sheet_data, batch_update_sheet
from config.settings import NOTIFICATION_TYPES, COLUMNAS_NOTIFICACIONES, MAX_NOTIFICATIONS

@st.cache_data(ttl=10)
def get_cached_notifications(username, unread_only=True, limit=MAX_NOTIFICATIONS):
    return st.session_state.notification_manager.get_for_user(username, unread_only, limit)

class NotificationManager:
    def __init__(self, sheet_notifications):
        self.sheet = sheet_notifications
        self.max_retries = 3

    def _get_next_id(self):
        for _ in range(self.max_retries):
            try:
                df = safe_get_sheet_data(self.sheet, COLUMNAS_NOTIFICACIONES)
                return 1 if df.empty else int(df['ID'].max()) + 1
            except Exception as e:
                st.error(f"Error al obtener ID: {str(e)}")
                time.sleep(1)
        return None

    def add(self, notification_type, message, user_target='all', claim_id=None, action=None):
        """
        Agrega una notificación general para todos los usuarios ('all')
        con límite de 10 en total.
        """
        if notification_type not in NOTIFICATION_TYPES:
            raise ValueError(f"Tipo de notificación no válido: {notification_type}. Opciones: {list(NOTIFICATION_TYPES.keys())}")

        try:
            # Obtener todas las notificaciones actuales dirigidas a 'all'
            df_notif = safe_get_sheet_data(self.sheet, COLUMNAS_NOTIFICACIONES)
            df_all = df_notif[df_notif['Usuario_Destino'] == 'all']

            if len(df_all) >= 10:
                df_all['Fecha_Hora'] = pd.to_datetime(df_all['Fecha_Hora'], errors='coerce')
                mas_antigua = df_all.sort_values('Fecha_Hora').iloc[0]
                row_id = df_all.index[0]
                self._delete_rows([row_id])

            return self._agregar_notificacion_individual(
                notification_type, message, 'all', claim_id, action
            )

        except Exception as e:
            st.error(f"Error al agregar notificación global: {str(e)}")
            return False


    def _agregar_notificacion_individual(self, notification_type, message, user_target, claim_id=None, action=None):
        new_id = self._get_next_id()
        if new_id is None:
            return False

        new_notification = [
            new_id,
            notification_type,
            NOTIFICATION_TYPES[notification_type]['priority'],
            message,
            str(user_target),
            str(claim_id) if claim_id else "",
            format_fecha(ahora_argentina()),
            False,
            action or ""
        ]

        for attempt in range(self.max_retries):
            success, error = api_manager.safe_sheet_operation(
                self.sheet.append_row,
                new_notification
            )
            if success:
                return True
            time.sleep(1)

        st.error(f"Fallo al agregar notificación para {user_target}")
        return False

    def get_for_user(self, username, unread_only=True, limit=MAX_NOTIFICATIONS):
        try:
            df = safe_get_sheet_data(self.sheet, COLUMNAS_NOTIFICACIONES)
            if df.empty:
                return []

            df['Fecha_Hora'] = pd.to_datetime(df['Fecha_Hora'], errors='coerce')
            df['Leída'] = df['Leída'].astype(str).str.strip().str.upper().map({'FALSE': False, 'TRUE': True}).fillna(False)

            mask = (df['Usuario_Destino'] == username) | (df['Usuario_Destino'] == 'all')
            if unread_only:
                mask &= (df['Leída'] == False)

            notifications = (
                df[mask]
                .sort_values('Fecha_Hora', ascending=False)
                .head(limit)
            )

            return notifications.to_dict('records')

        except Exception as e:
            st.error(f"Error al obtener notificaciones: {str(e)}")
            return []

    def get_unread_count(self, username):
        notifications = self.get_for_user(username, unread_only=True)
        return len(notifications)

    def mark_as_read(self, notification_ids):
        if not notification_ids:
            return False

        try:
            df = safe_get_sheet_data(self.sheet, COLUMNAS_NOTIFICACIONES)

            updates = [{
                'range': f"H{int(row['ID']) + 1}",
                'values': [[True]]
            } for _, row in df[df['ID'].isin(notification_ids)].iterrows()]

            if not updates:
                return False

            success, error = api_manager.safe_sheet_operation(
                batch_update_sheet,
                self.sheet,
                updates,
                is_batch=True
            )
            return success

        except Exception as e:
            st.error(f"Error al marcar como leídas: {str(e)}")
            return False

    def clear_old(self, days=30):
        try:
            df = safe_get_sheet_data(self.sheet, COLUMNAS_NOTIFICACIONES)
            if df.empty:
                return True

            df['Fecha_Hora'] = pd.to_datetime(df['Fecha_Hora'], errors='coerce')
            if pd.api.types.is_datetime64tz_dtype(df['Fecha_Hora']):
                df['Fecha_Hora'] = df['Fecha_Hora'].dt.tz_convert(None)

            df_validas = df[df['Fecha_Hora'].notna()].copy()
            cutoff_date = ahora_argentina().replace(tzinfo=None) - timedelta(days=days)
            old_ids = df_validas[df_validas['Fecha_Hora'] < cutoff_date]['ID'].tolist()

            if not old_ids:
                return True

            return self._delete_rows(old_ids)

        except Exception as e:
            st.error(f"Error al limpiar notificaciones: {str(e)}")
            return False

    def _delete_rows(self, row_ids):
        updates = [{
            'delete_dimension': {
                'range': {
                    'sheetId': self.sheet.id,
                    'dimension': 'ROWS',
                    'startIndex': int(row_id),
                    'endIndex': int(row_id) + 1
                }
            }
        } for row_id in row_ids]

        success, _ = api_manager.safe_sheet_operation(
            self.sheet.batch_update,
            {'requests': updates}
        )
        return success

    def delete_notification_by_id(self, notif_id):
        try:
            df = safe_get_sheet_data(self.sheet, COLUMNAS_NOTIFICACIONES)
            fila = df[df['ID'] == notif_id]
            if fila.empty:
                return False

            row_id = int(fila.index[0])
            return self._delete_rows([row_id])
        except Exception as e:
            st.error(f"Error al eliminar notificación: {str(e)}")
            return False


# ✅ FUNCIÓN DE INICIALIZACIÓN — DEBE ESTAR FUERA DE LA CLASE
def init_notification_manager(sheet_notifications):
    if 'notification_manager' not in st.session_state:
        st.session_state.notification_manager = NotificationManager(sheet_notifications)

        user = st.session_state.get('auth', {}).get('user_info', {}).get('username', '')
        if user and st.session_state.get('clear_notifications_job') is None:
            if st.session_state.notification_manager.clear_old():
                st.session_state.clear_notifications_job = True
