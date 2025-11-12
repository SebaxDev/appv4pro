# components/notification_bell.py

import streamlit as st
import uuid
from utils.date_utils import format_fecha
from config.settings import NOTIFICATION_TYPES
from components.notifications import get_cached_notifications

def render_notification_bell():
    """Muestra el ícono de notificaciones y el panel"""
    if 'notification_manager' not in st.session_state:
        return

    user = st.session_state.auth.get('user_info', {}).get('username')
    if not user:
        return

    notifications = get_cached_notifications(user)
    unread_count = len(notifications)

    # Ícono en el sidebar
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        col1.markdown(f"🔔 **{unread_count}**" if unread_count > 0 else "🔔")

        if col2.button("Ver notificaciones"):
            st.session_state.show_notifications = not st.session_state.get('show_notifications', False)

        if st.session_state.get('show_notifications'):
            with st.expander("Notificaciones", expanded=True):
                if not notifications:
                    st.info("No tienes notificaciones nuevas")
                    return

                for idx, notification in enumerate(notifications[:10]):  # Mostrar las 10 más recientes
                    icon = NOTIFICATION_TYPES.get(notification.get('Tipo'), {}).get('icon', '✉️')

                    with st.container():
                        cols = st.columns([1, 10])
                        cols[0].markdown(f"**{icon}**")

                        with cols[1]:
                            mensaje = notification.get('Mensaje', '[Sin mensaje]')
                            fecha = format_fecha(notification.get('Fecha_Hora'))
                            st.markdown(f"**{mensaje}**")
                            st.caption(fecha)

                            # Generar clave única incluso si hay IDs duplicados o ausentes
                            notif_id = notification.get("ID", "unknown")
                            unique_suffix = uuid.uuid4().hex[:8]
                            key = f"read_{notif_id}_{idx}_{unique_suffix}"

                            if st.button("Marcar como leída", key=key):
                                if notif_id != "unknown":
                                    st.session_state.notification_manager.mark_as_read([int(notif_id)])
                                    st.cache_data.clear()  # ⚠️ limpia el cache para que no vuelva a aparecer
                                    st.experimental_rerun()

                    st.divider()
