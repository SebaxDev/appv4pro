# components/reclamos/gestion.py

import streamlit as st
import pandas as pd
import unidecode  # al inicio del archivo
from datetime import datetime
from utils.date_utils import format_fecha, parse_fecha
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet as dm_batch_update_sheet
from config.settings import SECTORES_DISPONIBLES, DEBUG_MODE, TECNICOS_DISPONIBLES

def render_gestion_reclamos(df_reclamos, df_clientes, sheet_reclamos, user):
    """
    Dashboard de gestión de reclamos con contadores, dataframe compacto y editor.
    """
    st.subheader("📊 Dashboard de Gestión de Reclamos")
    
    try:
        if df_reclamos.empty:
            st.info("No hay reclamos para mostrar.")
            return

        # Prepara los datos
        df_preparado = _preparar_datos(df_reclamos, df_clientes)
        
        # 1. Mostrar contadores por tipo de reclamo
        _mostrar_contadores_reclamos(df_preparado)
        
        # 2. Mostrar dataframe compacto con filtros
        st.markdown("---")
        st.subheader("📋 Lista Compacta de Reclamos")
        df_filtrado = _mostrar_filtros_y_dataframe(df_preparado)
        
        # 3. Buscador y editor de reclamos (USANDO EL EDITOR MEJORADO)
        st.markdown("---")
        st.subheader("🔍 Buscar y Editar Reclamo")
        cambios_edicion = _mostrar_edicion_reclamo_mejorado(df_filtrado, sheet_reclamos, user)
        
        if cambios_edicion:
            st.success("✅ Reclamo actualizado correctamente.")
            st.rerun()
            return
        
        # 4. Lista de reclamos con estado "Desconexión"
        st.markdown("---")
        st.subheader("🔌 Reclamos con Estado 'Desconexión'")
        _gestionar_desconexiones(df_preparado, sheet_reclamos, user)

    except Exception as e:
        st.error(f"⚠️ Error en la gestión de reclamos: {str(e)}")
        if DEBUG_MODE:
            st.exception(e)

def _preparar_datos(df_reclamos, df_clientes):
    """Prepara y limpia los datos para su visualización."""
    df = df_reclamos.copy()
    df_clientes_norm = df_clientes.copy()

    # Normalización de columnas clave para el merge
    df_clientes_norm["Nº Cliente"] = df_clientes_norm["Nº Cliente"].astype(str).str.strip()
    df["Nº Cliente"] = df["Nº Cliente"].astype(str).str.strip()
    df["ID Reclamo"] = df["ID Reclamo"].astype(str).str.strip()

    # Verificar si la columna Teléfono ya existe en df_reclamos
    if "Teléfono" not in df.columns:
        # Si no existe, hacer el merge con la columna Teléfono de clientes
        df = pd.merge(df, df_clientes_norm[["Nº Cliente", "Teléfono"]], on="Nº Cliente", how="left")
    else:
        # Si ya existe, verificar si hay valores nulos y completar con datos de clientes
        df_telefono_clientes = df_clientes_norm[["Nº Cliente", "Teléfono"]].rename(columns={"Teléfono": "Teléfono_cliente"})
        df = pd.merge(df, df_telefono_clientes, on="Nº Cliente", how="left")
        # Completar teléfonos nulos con los de la base de clientes
        df["Teléfono"] = df["Teléfono"].fillna(df["Teléfono_cliente"])
        df = df.drop(columns=["Teléfono_cliente"])

    # Manejo de fechas
    df["Fecha y hora"] = pd.to_datetime(df["Fecha y hora"], errors='coerce')
    df.sort_values("Fecha y hora", ascending=False, inplace=True)

    return df

def _mostrar_contadores_reclamos(df):
    """Muestra contadores de reclamos por tipo, separando pendientes y en curso."""
    # Filtrar solo reclamos pendientes y en curso
    df_activos = df[df["Estado"].isin(["Pendiente", "En curso"])]
    
    # Obtener tipos de reclamo que tienen al menos un reclamo activo
    tipos_con_reclamos = df_activos["Tipo de reclamo"].value_counts()
    tipos_reclamo = tipos_con_reclamos.index.tolist()
    
    if len(tipos_reclamo) == 0:
        st.info("No hay reclamos pendientes o en curso para mostrar.")
        return
    
    # Crear columnas para los contadores
    cols = st.columns(min(4, len(tipos_reclamo)))
    
    for i, tipo in enumerate(tipos_reclamo):
        col_idx = i % 4
        with cols[col_idx]:
            # Contar reclamos por tipo (solo pendientes y en curso)
            count = len(df_activos[df_activos["Tipo de reclamo"] == tipo])
            
            # Mostrar tarjeta con contador
            st.markdown(f"""
            <div class="card" style="text-align: center; padding: 1rem;">
                <h3 style="margin: 0; color: var(--primary-color);">{count}</h3>
                <p style="margin: 0; color: var(--text-secondary); font-size: 0.9rem;">{tipo}</p>
            </div>
            """, unsafe_allow_html=True)

def _mostrar_filtros_y_dataframe(df):
    """Muestra filtros y el dataframe compacto de reclamos."""
    # Filtros
    col1, col2, col3 = st.columns(3)
    
    with col1:
        estado = st.selectbox("Filtrar por Estado", 
                             ["Todos"] + sorted(df["Estado"].dropna().unique()),
                             key="filtro_estado")
    
    with col2:
        sector = st.selectbox("Filtrar por Sector", 
                             ["Todos"] + SECTORES_DISPONIBLES,
                             key="filtro_sector")
    
    with col3:
        tipo_reclamo = st.selectbox("Filtrar por Tipo", 
                                   ["Todos"] + sorted(df["Tipo de reclamo"].dropna().unique()),
                                   key="filtro_tipo")
    
    # Aplicar filtros
    df_filtrado = df.copy()
    
    if estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Estado"] == estado]
    
    if sector != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Sector"] == sector]
    
    if tipo_reclamo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Tipo de reclamo"] == tipo_reclamo]
    
    # Limitar a los últimos 100 reclamos
    df_filtrado = df_filtrado.head(100)
    
    # Seleccionar columnas específicas para mostrar
    columnas_mostrar = ["Fecha y hora", "Nº Cliente", "Nombre", "Sector", "Tipo de reclamo", "Teléfono", "Estado"]
    
    # Verificar que todas las columnas existan en el DataFrame
    columnas_disponibles = [col for col in columnas_mostrar if col in df_filtrado.columns]
    
    df_mostrar = df_filtrado[columnas_disponibles].copy()
    
    # Formatear fecha
    if "Fecha y hora" in df_mostrar.columns:
        df_mostrar["Fecha y hora"] = df_mostrar["Fecha y hora"].apply(
            lambda x: format_fecha(x, "%d/%m/%Y %H:%M") if pd.notna(x) else "N/A"
        )
    
    # Mostrar dataframe con estilo
    st.dataframe(
        df_mostrar,
        use_container_width=True,
        height=400,
        hide_index=True,
        column_config={
            "Fecha y hora": st.column_config.TextColumn("Fecha/Hora", width="small"),
            "Nº Cliente": st.column_config.TextColumn("N° Cliente", width="small"),
            "Nombre": st.column_config.TextColumn("Nombre", width="medium"),
            "Sector": st.column_config.TextColumn("Sector", width="small"),
            "Tipo de reclamo": st.column_config.TextColumn("Tipo Reclamo", width="medium"),
            "Teléfono": st.column_config.TextColumn("Teléfono", width="medium"),
            "Estado": st.column_config.TextColumn("Estado", width="small"),
        }
    )
    
    st.caption(f"Mostrando {len(df_mostrar)} de {len(df_filtrado)} reclamos filtrados")
    
    return df_filtrado

# --- EDITOR MEJORADO (REEMPLAZANDO EL ANTERIOR) ---
def _mostrar_edicion_reclamo_mejorado(df, sheet_reclamos, user):
    """Muestra la interfaz para editar reclamos (versión mejorada de gestion2.py)"""
    st.markdown("### ✏️ Editar un reclamo puntual")
    
    # Crear selector mejorado (sin UUID visible)
    df["selector"] = df.apply(
        lambda x: f"{x['Nº Cliente']} - {x['Nombre']} ({x['Estado']})", 
        axis=1
    )
    
    # Añadir búsqueda por número de cliente o nombre
    busqueda = st.text_input("🔍 Buscar por número de cliente o nombre")
    
    # Filtrar opciones basadas en la búsqueda
    opciones_filtradas = [""] + df["selector"].tolist()
    if busqueda:
        opciones_filtradas = [""] + [
            opc for opc in df["selector"].tolist() 
            if busqueda.lower() in opc.lower()
        ]
    
    seleccion = st.selectbox(
        "Seleccioná un reclamo para editar", 
        opciones_filtradas,
        index=0
    )

    if not seleccion:
        return False

    # Obtener el ID del reclamo
    numero_cliente = seleccion.split(" - ")[0]
    reclamo_actual = df[df["Nº Cliente"] == numero_cliente].iloc[0]
    reclamo_id = reclamo_actual["ID Reclamo"]

    # Mostrar información del reclamo
    with st.expander("📄 Información del reclamo", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**📅 Fecha:** {format_fecha(reclamo_actual['Fecha y hora'])}")
            st.markdown(f"**👤 Cliente:** {reclamo_actual['Nombre']}")
            st.markdown(f"**📍 Sector:** {reclamo_actual['Sector']}")
        with col2:
            st.markdown(f"**📌 Tipo:** {reclamo_actual['Tipo de reclamo']}")
            st.markdown(f"**⚙️ Estado actual:** {reclamo_actual['Estado']}")
            st.markdown(f"**👷 Técnico:** {reclamo_actual.get('Técnico', 'No asignado')}")

    # Formulario de edición
    with st.form(f"form_editar_{reclamo_id}"):
        col1, col2 = st.columns(2)
        
        with col1:
            direccion = st.text_input(
                "Dirección", 
                value=reclamo_actual.get("Dirección", ""),
                help="Dirección completa del cliente"
            )
            telefono = st.text_input(
                "Teléfono", 
                value=reclamo_actual.get("Teléfono", ""),
                help="Número de contacto del cliente"
            )
        
        with col2:
            tipo_reclamo = st.selectbox(
                "Tipo de reclamo", 
                sorted(df["Tipo de reclamo"].unique()),
                index=sorted(df["Tipo de reclamo"].unique()).index(
                    reclamo_actual["Tipo de reclamo"]
                ) if reclamo_actual["Tipo de reclamo"] in sorted(df["Tipo de reclamo"].unique()) else 0
            )
            
            try:
                sector_normalizado = str(int(str(reclamo_actual.get("Sector", "")).strip()))
                index_sector = SECTORES_DISPONIBLES.index(sector_normalizado) if sector_normalizado in SECTORES_DISPONIBLES else 0
            except Exception:
                index_sector = 0

            sector_edit = st.selectbox(
                "Sector",
                options=SECTORES_DISPONIBLES,
                index=index_sector
            )
        
        detalles = st.text_area(
            "Detalles", 
            value=reclamo_actual.get("Detalles", ""), 
            height=100
        )
        
        precinto = st.text_input(
            "N° de Precinto", 
            value=reclamo_actual.get("N° de Precinto", ""),
            help="Número de precinto del medidor"
        )

        # Estados disponibles (incluyendo "Desconexión")
        estados_disponibles = ["Pendiente", "En curso", "Desconexión", "Resuelto"]
        
        # Determinar índice inicial
        estado_actual = reclamo_actual["Estado"]
        index_estado = estados_disponibles.index(estado_actual) if estado_actual in estados_disponibles else 0

        estado_nuevo = st.selectbox(
            "Nuevo estado", 
            estados_disponibles,
            index=index_estado
        )

        # Botones de acción
        col1, col2 = st.columns(2)
        
        guardar_cambios = col1.form_submit_button(
            "💾 Guardar todos los cambios",
            use_container_width=True
        )
        
        cambiar_estado = col2.form_submit_button(
            "🔄 Cambiar solo estado",
            use_container_width=True
        )

    # Procesar acciones
    if guardar_cambios:
        if not direccion.strip() or not detalles.strip():
            st.warning("⚠️ Dirección y detalles no pueden estar vacíos.")
            return False
        
        return _actualizar_reclamo_mejorado(
            df, sheet_reclamos, reclamo_id,
            {
                "direccion": direccion,
                "telefono": telefono,
                "tipo_reclamo": tipo_reclamo,
                "detalles": detalles,
                "precinto": precinto,
                "sector": sector_edit,
                "estado": estado_nuevo,
                "nombre": reclamo_actual.get("Nombre", "")
            },
            full_update=True
        )

    if cambiar_estado:
        return _actualizar_reclamo_mejorado(
            df, sheet_reclamos, reclamo_id,
            {"estado": estado_nuevo},
            full_update=False
        )
    
    return False

def _actualizar_reclamo_mejorado(df, sheet_reclamos, reclamo_id, updates, full_update=False):
    """Actualiza el reclamo en la hoja de cálculo (versión mejorada y más tolerante)."""
    with st.spinner("Actualizando reclamo..."):
        try:
            # Normalizar reclamo_id a string sin espacios
            reclamo_id_str = str(reclamo_id).strip()

            # Buscar la fila del reclamo en varias columnas posibles (tolerante a nombres distintos)
            df_ids = df.copy()
            # Asegurarnos de que las columnas que vamos a buscar existan
            posible_cols = [col for col in ["ID Reclamo", "ID", "Id", "id_reclamo"] if col in df_ids.columns]
            filas_encontradas = pd.Index([])

            for col in posible_cols:
                try:
                    matches = df_ids[df_ids[col].astype(str).str.strip() == reclamo_id_str].index
                    if not matches.empty:
                        filas_encontradas = matches
                        break
                except Exception:
                    continue

            # Si no lo encontró exacto, intentar búsqueda parcial (por si el id fue cortado o tiene prefijo)
            if filas_encontradas.empty:
                for col in posible_cols:
                    try:
                        matches = df_ids[df_ids[col].astype(str).str.strip().str.contains(reclamo_id_str, na=False)].index
                        if not matches.empty:
                            filas_encontradas = matches
                            break
                    except Exception:
                        continue

            if filas_encontradas.empty:
                st.error(f"❌ No se encontró el reclamo con ID '{reclamo_id_str}' en el DataFrame (busqué en {posible_cols}).")
                if DEBUG_MODE:
                    st.info(f"Columnas disponibles: {list(df.columns)}")
                return False

            fila = int(filas_encontradas[0]) + 2  # +2 para mapear al índice de Google Sheets (cabecera)

            updates_list = []
            # Guardar estado anterior para debug
            try:
                estado_anterior = df.loc[filas_encontradas[0], "Estado"]
            except Exception:
                estado_anterior = None

            # Si es full_update, mapear todos los campos que correspondan
            if full_update:
                # Sólo agregamos si están presentes en 'updates'
                if 'nombre' in updates:
                    updates_list.append({"range": f"D{fila}", "values": [[updates['nombre'].upper()]]})
                if 'direccion' in updates:
                    updates_list.append({"range": f"E{fila}", "values": [[updates['direccion'].upper()]]})
                if 'telefono' in updates:
                    updates_list.append({"range": f"F{fila}", "values": [[str(updates['telefono'])]]})
                if 'tipo_reclamo' in updates:
                    updates_list.append({"range": f"G{fila}", "values": [[updates['tipo_reclamo']]]})
                if 'detalles' in updates:
                    updates_list.append({"range": f"H{fila}", "values": [[updates['detalles']]]})
                if 'precinto' in updates:
                    updates_list.append({"range": f"K{fila}", "values": [[updates['precinto']]]})
                if 'sector' in updates:
                    updates_list.append({"range": f"C{fila}", "values": [[str(updates['sector'])]]})

            # Asegurarse de que 'estado' esté presente en updates
            if 'estado' in updates and updates['estado'] is not None:
                updates_list.append({"range": f"I{fila}", "values": [[updates['estado']]]})
            else:
                # Por seguridad, si no hay estado en updates, no alteramos este campo.
                pass

            # Si quiere volver a "Pendiente" limpiamos técnico (J)
            if 'estado' in updates and str(updates['estado']).strip().lower() == "pendiente":
                updates_list.append({"range": f"J{fila}", "values": [[""]]})

            # Si por alguna razón la lista queda vacía (no hay campos para actualizar),
            # al menos intentamos escribir el estado si viene en updates.
            if not updates_list and 'estado' in updates:
                updates_list.append({"range": f"I{fila}", "values": [[updates['estado']]]})

            if not updates_list:
                st.warning("⚠️ No hay cambios para enviar a la hoja (updates_list vacío).")
                return False

            # Ejecutar la operación en batch (usa tu api_manager)
            success, error = api_manager.safe_sheet_operation(
                dm_batch_update_sheet,
                sheet_reclamos,
                updates_list,
                is_batch=True
            )

            if success:
                # Limpiar cache para que una nueva carga traiga los datos actualizados
                try:
                    st.cache_data.clear()
                except Exception:
                    pass

                st.success("✅ Reclamo actualizado correctamente.")
                # DEBUG: mostrar qué se envió
                if DEBUG_MODE:
                    st.info(f"Fila actualizada: {fila}")
                    st.json({"updates_sent": updates_list, "estado_anterior": estado_anterior})
                return True
            else:
                st.error(f"❌ Error al actualizar en Google Sheets: {error}")
                if DEBUG_MODE:
                    st.exception(error)
                return False

        except Exception as e:
            st.error(f"❌ Error inesperado al actualizar reclamo: {e}")
            if DEBUG_MODE:
                st.exception(e)
            return False

def _gestionar_desconexiones(df, sheet_reclamos, user):
    """
    Gestiona las desconexiones a pedido (permite marcarlas como resueltas).
    """
    st.markdown("---")
    st.markdown("### 🔌 Desconexiones a Pedido Pendientes")

    # Filtrar solo las desconexiones con estado "Desconexión"
    import unidecode  # al inicio del archivo

    desconexiones = df[
        (df["Tipo de reclamo"].apply(lambda x: unidecode.unidecode(str(x)).strip().lower()) == "desconexion a pedido") &
        (df["Estado"].apply(lambda x: unidecode.unidecode(str(x)).strip().lower()) == "desconexion")
    ]

    if desconexiones.empty:
        st.success("✅ No hay desconexiones pendientes de marcar como resueltas.")
        return False

    st.info(f"📄 Hay {len(desconexiones)} desconexiones cargadas. Marcá las completadas como resueltas.")

    cambios = False

    for i, row in desconexiones.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(f"**👤 {row.get('Nº Cliente', '')} - {row.get('Nombre', 'Sin nombre')}**")
                st.markdown(f"🏠 {row.get('Dirección', 'Sin dirección')}")
                st.markdown(f"📅 {format_fecha(row.get('Fecha y hora'))} - Sector {row.get('Sector', 'N/D')}")
                st.markdown(f"🆔 ID: `{row.get('ID Reclamo', row.name)}`")

            with col2:
                if st.button("✅ Marcar como resuelto", key=f"resuelto_{i}", use_container_width=True):
                    if _marcar_desconexion_como_resuelta(row, sheet_reclamos):
                        cambios = True
                        st.rerun()

        st.divider()

    return cambios

def _marcar_desconexion_como_resuelta(row, sheet_reclamos):
    """
    Marca una desconexión como resuelta en la hoja (columna Estado = 'Resuelto').
    """
    with st.spinner("Actualizando estado..."):
        try:
            reclamo_id = str(row.get("ID Reclamo", "")).strip()

            if not reclamo_id:
                st.error("⚠️ No se encontró el ID del reclamo para actualizar.")
                return False

            # Buscar la fila correspondiente en la hoja
            df_sheet = sheet_reclamos.get_all_records()
            df_aux = pd.DataFrame(df_sheet)

            if "ID Reclamo" not in df_aux.columns:
                st.error("❌ No se encontró la columna 'ID Reclamo' en la hoja.")
                return False

            match = df_aux[df_aux["ID Reclamo"].astype(str).str.strip() == reclamo_id]
            if match.empty:
                st.error(f"❌ No se encontró el reclamo con ID {reclamo_id} en la hoja.")
                return False

            fila = int(match.index[0]) + 2  # +2 por cabecera

            updates_list = [{"range": f"I{fila}", "values": [["Resuelto"]]}]

            success, error = api_manager.safe_sheet_operation(
                dm_batch_update_sheet,
                sheet_reclamos,
                updates_list,
                is_batch=True
            )

            if success:
                try:
                    st.cache_data.clear()
                except Exception:
                    pass

                st.success(f"✅ Desconexión de {row.get('Nombre', 'Cliente')} marcada como resuelta.")
                return True
            else:
                st.error(f"❌ Error al actualizar: {error}")
                return False

        except Exception as e:
            st.error(f"❌ Error inesperado al actualizar desconexión: {e}")
            if DEBUG_MODE:
                st.exception(e)
            return False

def _actualizar_reclamo(df, sheet_reclamos, reclamo_id, updates, user, full_update=False):
    """Función original de actualización (mantenida por compatibilidad)"""
    # Esta función se mantiene para compatibilidad con otras partes del código
    # pero ahora usa la versión mejorada internamente
    return _actualizar_reclamo_mejorado(df, sheet_reclamos, reclamo_id, updates, full_update)