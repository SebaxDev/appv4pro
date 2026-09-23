# components/reclamos/gestion.py

import streamlit as st
import pandas as pd
import unidecode
from utils.date_utils import format_fecha, parse_fecha
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet as dm_batch_update_sheet
from config.settings import (
    SECTORES_DISPONIBLES,
    DEBUG_MODE,
    TECNICOS_DISPONIBLES,
    TIPOS_RECLAMO,
    ESTADOS_RECLAMO,
    COLUMNAS_RECLAMOS,
)


# ============================================
# HELPERS
# ============================================

def _col_letter(col_name):
    """Devuelve la letra de columna Excel dinámicamente desde COLUMNAS_RECLAMOS."""
    idx = COLUMNAS_RECLAMOS.index(col_name) + 1  # 1-based
    result = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def _tipos_para_editar():
    """Lista de tipos de reclamo para el editor (sin placeholders)."""
    return [t for t in TIPOS_RECLAMO if not t.startswith("—")]


def _safe_str(val, default=""):
    """Convierte un valor a string de forma segura (maneja NaN/None)."""
    if pd.isna(val) if not isinstance(val, str) else False:
        return default
    s = str(val).strip()
    if s in ("nan", "None", "NaN", "nat"):
        return default
    return s


def _make_selector_label(row):
    """Genera label único y robusto para el selector de reclamos."""
    fecha_str = ""
    if pd.notna(row.get("Fecha y hora")):
        try:
            fecha_str = row["Fecha y hora"].strftime("%d/%m")
        except Exception:
            fecha_str = ""
    return (
        f"{row['Nº Cliente']} - {row.get('Nombre', '')} "
        f"| {row.get('Tipo de reclamo', '')} "
        f"| {row['Estado']} "
        f"| {fecha_str}"
    )


def _actualizar_en_memoria(fila, reclamo_id, campos_actualizados):
    """
    Actualiza el DataFrame local en st.session_state sin necesidad de volver a leer de Google Sheets.
    Busca por 'ID Reclamo' si existe, o por el índice derivado de la fila física (fila - 2).
    """
    if "df_reclamos" not in st.session_state or st.session_state.df_reclamos is None:
        return

    df = st.session_state.df_reclamos
    target_idx = None

    # 1. Intentar localizar por ID Reclamo
    if reclamo_id and "ID Reclamo" in df.columns:
        matching = df[df["ID Reclamo"].astype(str).str.strip() == str(reclamo_id).strip()]
        if not matching.empty:
            target_idx = matching.index[0]

    # 2. Fallback a fila física de Sheet (fila 2 corresponde a index 0)
    if target_idx is None:
        idx_candidato = fila - 2
        if 0 <= idx_candidato < len(df):
            target_idx = idx_candidato

    # 3. Aplicar modificaciones en memoria
    if target_idx is not None:
        for columna, valor in campos_actualizados.items():
            if columna in df.columns:
                df.at[target_idx, columna] = valor


# ============================================
# RENDER PRINCIPAL
# ============================================

def render_gestion_reclamos(df_reclamos, df_clientes, sheet_reclamos, user):
    """
    Dashboard de gestión de reclamos con contadores, dataframe compacto y editor.
    Retorna {"needs_refresh": True/False} indicando si se requiere rerun visual.
    """
    st.subheader("📊 Dashboard de Gestión de Reclamos")
    needs_refresh = False

    try:
        if df_reclamos.empty:
            st.info("No hay reclamos para mostrar.")
            return {"needs_refresh": False}

        df_preparado = _preparar_datos(df_reclamos, df_clientes)

        # 1. Contadores
        _mostrar_contadores_reclamos(df_preparado)

        # 2. Filtros y dataframe
        st.markdown("---")
        st.subheader("📋 Lista Compacta de Reclamos")
        df_filtrado = _mostrar_filtros_y_dataframe(df_preparado)

        # 3. Editor
        st.markdown("---")
        st.subheader("🔍 Buscar y Editar Reclamo")
        if _mostrar_edicion_reclamo(df_filtrado, sheet_reclamos, user):
            needs_refresh = True

        # 4. Desconexiones
        st.markdown("---")
        st.subheader("🔌 Reclamos con Estado 'Desconexión'")
        if _gestionar_desconexiones(df_preparado, sheet_reclamos):
            needs_refresh = True

    except Exception as e:
        st.error(f"⚠️ Error en la gestión de reclamos: {str(e)}")
        if DEBUG_MODE:
            st.exception(e)

    return {"needs_refresh": needs_refresh}


# ============================================
# PREPARACIÓN DE DATOS
# ============================================

def _preparar_datos(df_reclamos, df_clientes):
    """Prepara y limpia los datos para su visualización."""
    df = df_reclamos.copy()

    # Mapeo a fila de Google Sheets ANTES de cualquier operación que altere índices
    df["_sheet_row"] = df.index + 2

    # Normalización para merge
    df_clientes_norm = df_clientes.copy()
    df_clientes_norm["Nº Cliente"] = df_clientes_norm["Nº Cliente"].astype(str).str.strip()
    df["Nº Cliente"] = df["Nº Cliente"].astype(str).str.strip()
    df["ID Reclamo"] = df["ID Reclamo"].astype(str).str.strip()

    # Merge Teléfono
    if "Teléfono" not in df.columns:
        df = pd.merge(
            df,
            df_clientes_norm[["Nº Cliente", "Teléfono"]],
            on="Nº Cliente",
            how="left",
        )
    else:
        df_tel = df_clientes_norm[["Nº Cliente", "Teléfono"]].rename(
            columns={"Teléfono": "Teléfono_cliente"}
        )
        df = pd.merge(df, df_tel, on="Nº Cliente", how="left")
        df["Teléfono"] = df["Teléfono"].fillna(df["Teléfono_cliente"])
        df = df.drop(columns=["Teléfono_cliente"])

    # Fechas
    df["Fecha y hora"] = pd.to_datetime(df["Fecha y hora"], errors="coerce")
    df.sort_values("Fecha y hora", ascending=False, inplace=True)

    return df


# ============================================
# CONTADORES
# ============================================

def _mostrar_contadores_reclamos(df):
    """Contadores de reclamos por tipo usando st.metric (nativo Streamlit)."""
    df_activos = df[df["Estado"].isin(["Pendiente", "En curso"])]
    tipos_con_reclamos = df_activos["Tipo de reclamo"].value_counts()

    if tipos_con_reclamos.empty:
        st.info("No hay reclamos pendientes o en curso para mostrar.")
        return

    tipos_reclamo = tipos_con_reclamos.index.tolist()
    num_cols = min(4, len(tipos_reclamo))
    cols = st.columns(num_cols)

    for i, tipo in enumerate(tipos_reclamo):
        with cols[i % num_cols]:
            st.metric(label=tipo, value=tipos_con_reclamos[tipo])


# ============================================
# FILTROS Y DATAFRAME
# ============================================

def _mostrar_filtros_y_dataframe(df):
    """Filtros y dataframe compacto. Retorna el df filtrado completo (para el editor)."""
    col1, col2, col3 = st.columns(3)

    with col1:
        estado = st.selectbox(
            "Filtrar por Estado",
            ["Todos"] + sorted(df["Estado"].dropna().unique()),
            key="filtro_estado",
        )

    with col2:
        sector = st.selectbox(
            "Filtrar por Sector",
            ["Todos"] + SECTORES_DISPONIBLES,
            key="filtro_sector",
        )

    with col3:
        tipo_reclamo = st.selectbox(
            "Filtrar por Tipo",
            ["Todos"] + sorted(df["Tipo de reclamo"].dropna().unique()),
            key="filtro_tipo",
        )

    # Aplicar filtros
    df_filtrado = df.copy()

    if estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Estado"] == estado]
    if sector != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Sector"] == sector]
    if tipo_reclamo != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Tipo de reclamo"] == tipo_reclamo]

    # Límite con aviso claro
    total_filtrados = len(df_filtrado)
    mostrar_todos = False

    if total_filtrados > 100:
        mostrar_todos = st.checkbox(
            f"⚠️ Se encontraron {total_filtrados} reclamos. ¿Mostrar todos?",
            value=False,
            key="mostrar_todos_reclamos",
        )

    df_display = df_filtrado if (mostrar_todos or total_filtrados <= 100) else df_filtrado.head(100)

    # Columnas a mostrar (sin internas como _sheet_row)
    columnas_mostrar = [
        "Fecha y hora", "Nº Cliente", "Nombre", "Sector",
        "Tipo de reclamo", "Teléfono", "Estado",
    ]
    columnas_disponibles = [c for c in columnas_mostrar if c in df_display.columns]

    df_mostrar = df_display[columnas_disponibles].copy()

    # Formatear fecha
    if "Fecha y hora" in df_mostrar.columns:
        df_mostrar["Fecha y hora"] = df_mostrar["Fecha y hora"].apply(
            lambda x: format_fecha(x, "%d/%m/%Y %H:%M") if pd.notna(x) else "N/A"
        )

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
        },
    )

    # Caption informativo
    if total_filtrados > 100 and not mostrar_todos:
        st.caption(f"Mostrando 100 de {total_filtrados} reclamos filtrados")
    else:
        st.caption(f"Mostrando {total_filtrados} reclamos filtrados")

    return df_filtrado


# ============================================
# EDITOR DE RECLAMO
# ============================================

def _mostrar_edicion_reclamo(df, sheet_reclamos, user):
    """Editor de reclamo puntual con selector robusto y búsqueda por ID."""
    st.markdown("### ✏️ Editar un reclamo puntual")

    df["_selector"] = df.apply(_make_selector_label, axis=1)

    busqueda = st.text_input(
        "🔍 Buscar por cliente, nombre o ID de reclamo",
        key="busqueda_editor",
    )

    opciones = df["_selector"].tolist()
    if busqueda:
        busqueda_lower = busqueda.lower()
        mask = (
            df["_selector"].str.lower().str.contains(busqueda_lower, na=False)
            | df["ID Reclamo"].astype(str).str.lower().str.contains(busqueda_lower, na=False)
        )
        opciones = df.loc[mask, "_selector"].tolist()

    seleccion = st.selectbox(
        "Seleccioná un reclamo para editar",
        [""] + opciones,
        index=0,
        key="select_reclamo_editar",
    )

    if not seleccion:
        return False

    reclamo_actual = df[df["_selector"] == seleccion].iloc[0]
    reclamo_id = _safe_str(reclamo_actual["ID Reclamo"])
    fila = int(reclamo_actual["_sheet_row"])

    with st.expander("📄 Información del reclamo", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**📅 Fecha:** {format_fecha(reclamo_actual['Fecha y hora'])}")
            st.markdown(f"**👤 Cliente:** {reclamo_actual.get('Nombre', 'N/A')}")
            st.markdown(f"**📍 Sector:** {reclamo_actual.get('Sector', 'N/A')}")
        with col2:
            st.markdown(f"**📌 Tipo:** {reclamo_actual.get('Tipo de reclamo', 'N/A')}")
            st.markdown(f"**⚙️ Estado:** {reclamo_actual.get('Estado', 'N/A')}")
            st.markdown(f"**👷 Técnico:** {_safe_str(reclamo_actual.get('Técnico', ''), 'No asignado')}")

    tipos_edit = _tipos_para_editar()

    with st.form(f"form_editar_{reclamo_id}"):
        col1, col2 = st.columns(2)

        with col1:
            direccion = st.text_input(
                "Dirección",
                value=_safe_str(reclamo_actual.get("Dirección", "")),
            )
            telefono = st.text_input(
                "Teléfono",
                value=_safe_str(reclamo_actual.get("Teléfono", "")),
            )

        with col2:
            tipo_actual = _safe_str(reclamo_actual.get("Tipo de reclamo", ""))
            try:
                tipo_idx = tipos_edit.index(tipo_actual) if tipo_actual in tipos_edit else 0
            except ValueError:
                tipo_idx = 0
            tipo_reclamo = st.selectbox("Tipo de reclamo", tipos_edit, index=tipo_idx)

            try:
                sector_norm = str(int(str(reclamo_actual.get("Sector", "")).strip()))
                sector_idx = (
                    SECTORES_DISPONIBLES.index(sector_norm)
                    if sector_norm in SECTORES_DISPONIBLES
                    else 0
                )
            except Exception:
                sector_idx = 0
            sector_edit = st.selectbox("Sector", options=SECTORES_DISPONIBLES, index=sector_idx)

        detalles = st.text_area(
            "Detalles",
            value=_safe_str(reclamo_actual.get("Detalles", "")),
            height=100,
        )

        col_p, col_e = st.columns(2)
        with col_p:
            precinto = st.text_input(
                "N° de Precinto",
                value=_safe_str(reclamo_actual.get("N° de Precinto", "")),
            )
        with col_e:
            estado_actual = _safe_str(reclamo_actual.get("Estado", ""))
            try:
                estado_idx = (
                    ESTADOS_RECLAMO.index(estado_actual)
                    if estado_actual in ESTADOS_RECLAMO
                    else 0
                )
            except ValueError:
                estado_idx = 0
            estado_nuevo = st.selectbox("Nuevo estado", ESTADOS_RECLAMO, index=estado_idx)

        anotaciones = st.text_area(
            "📝 Anotaciones",
            value=_safe_str(reclamo_actual.get("Anotaciones", "")),
            height=80,
        )

        col1, col2 = st.columns(2)
        guardar_cambios = col1.form_submit_button(
            "💾 Guardar todos los cambios", use_container_width=True
        )
        cambiar_estado = col2.form_submit_button(
            "🔄 Cambiar solo estado", use_container_width=True
        )

    if guardar_cambios:
        if not direccion.strip() or not detalles.strip():
            st.warning("⚠️ Dirección y detalles no pueden estar vacíos.")
            return False
        return _actualizar_reclamo(
            fila=fila,
            reclamo_id=reclamo_id,
            sheet_reclamos=sheet_reclamos,
            updates={
                "direccion": direccion,
                "telefono": telefono,
                "tipo_reclamo": tipo_reclamo,
                "detalles": detalles,
                "precinto": precinto,
                "sector": sector_edit,
                "estado": estado_nuevo,
                "anotaciones": anotaciones,
            },
            full_update=True,
        )

    if cambiar_estado:
        return _actualizar_reclamo(
            fila=fila,
            reclamo_id=reclamo_id,
            sheet_reclamos=sheet_reclamos,
            updates={"estado": estado_nuevo},
            full_update=False,
        )

    return False


# ============================================
# ACTUALIZACIÓN EN SHEET Y MEMORIA
# ============================================

def _actualizar_reclamo(fila, reclamo_id, sheet_reclamos, updates, full_update=False):
    """Actualiza en Google Sheets y sincroniza st.session_state sin recargar de la API."""
    with st.spinner("Actualizando reclamo..."):
        try:
            updates_list = []
            memoria_updates = {}

            if full_update:
                if "sector" in updates:
                    val = str(updates["sector"])
                    updates_list.append({
                        "range": f"{_col_letter('Sector')}{fila}",
                        "values": [[val]],
                    })
                    memoria_updates["Sector"] = val

                if "direccion" in updates:
                    val = updates["direccion"].upper().strip()
                    updates_list.append({
                        "range": f"{_col_letter('Dirección')}{fila}",
                        "values": [[val]],
                    })
                    memoria_updates["Dirección"] = val

                if "telefono" in updates:
                    val = str(updates["telefono"]).strip()
                    updates_list.append({
                        "range": f"{_col_letter('Teléfono')}{fila}",
                        "values": [[val]],
                    })
                    memoria_updates["Teléfono"] = val

                if "tipo_reclamo" in updates:
                    val = updates["tipo_reclamo"]
                    updates_list.append({
                        "range": f"{_col_letter('Tipo de reclamo')}{fila}",
                        "values": [[val]],
                    })
                    memoria_updates["Tipo de reclamo"] = val

                if "detalles" in updates:
                    val = updates["detalles"]
                    updates_list.append({
                        "range": f"{_col_letter('Detalles')}{fila}",
                        "values": [[val]],
                    })
                    memoria_updates["Detalles"] = val

                if "precinto" in updates:
                    val = str(updates["precinto"]).strip()
                    updates_list.append({
                        "range": f"{_col_letter('N° de Precinto')}{fila}",
                        "values": [[val]],
                    })
                    memoria_updates["N° de Precinto"] = val

                if "anotaciones" in updates:
                    val = updates["anotaciones"].strip()
                    updates_list.append({
                        "range": f"{_col_letter('Anotaciones')}{fila}",
                        "values": [[val]],
                    })
                    memoria_updates["Anotaciones"] = val

            # Estado (presente en ambos modos)
            if "estado" in updates and updates["estado"] is not None:
                val_estado = updates["estado"]
                updates_list.append({
                    "range": f"{_col_letter('Estado')}{fila}",
                    "values": [[val_estado]],
                })
                memoria_updates["Estado"] = val_estado

                # Si vuelve a Pendiente, limpiar técnico asignado
                if str(val_estado).strip().lower() == "pendiente":
                    updates_list.append({
                        "range": f"{_col_letter('Técnico')}{fila}",
                        "values": [[""]],
                    })
                    memoria_updates["Técnico"] = ""

            if not updates_list:
                st.warning("⚠️ No hay cambios para enviar.")
                return False

            # Escritura en Google Sheets
            success, error = api_manager.safe_sheet_operation(
                dm_batch_update_sheet,
                sheet_reclamos,
                updates_list,
                is_batch=True,
            )

            if success:
                # Actualización directa en memoria RAM (sin consumir cuotas de lectura de Sheets)
                _actualizar_en_memoria(fila, reclamo_id, memoria_updates)
                st.success("✅ Reclamo actualizado correctamente.")
                if DEBUG_MODE:
                    st.json({"fila": fila, "updates_sent": updates_list})
                return True
            else:
                st.error(f"❌ Error al actualizar: {error}")
                return False

        except Exception as e:
            st.error(f"❌ Error inesperado: {e}")
            if DEBUG_MODE:
                st.exception(e)
            return False


# ============================================
# GESTIÓN DE DESCONEXIONES
# ============================================

def _gestionar_desconexiones(df, sheet_reclamos):
    """
    Gestiona desconexiones a pedido pendientes.
    Escribe el cambio en Sheets y actualiza en memoria sin volver a consultar toda la planilla.
    """
    st.markdown("### 🔌 Desconexiones a Pedido Pendientes")

    desconexiones = df[
        (
            df["Tipo de reclamo"].apply(
                lambda x: unidecode.unidecode(str(x)).strip().lower()
            )
            == "desconexion a pedido"
        )
        & (
            df["Estado"].apply(
                lambda x: unidecode.unidecode(str(x)).strip().lower()
            )
            == "desconexion"
        )
    ]

    if desconexiones.empty:
        st.success("✅ No hay desconexiones pendientes.")
        return False

    st.info(f"📄 Hay {len(desconexiones)} desconexiones cargadas. Marcá las completadas como resueltas.")

    cambios = False

    for idx, row in desconexiones.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(
                    f"**👤 {row.get('Nº Cliente', '')} - {row.get('Nombre', 'Sin nombre')}**"
                )
                st.markdown(f"🏠 {row.get('Dirección', 'Sin dirección')}")
                st.markdown(
                    f"📅 {format_fecha(row.get('Fecha y hora'))} - Sector {row.get('Sector', 'N/D')}"
                )
                st.markdown(f"🆔 ID: `{row.get('ID Reclamo', idx)}`")

            with col2:
                if st.button(
                    "✅ Resuelto",
                    key=f"resuelto_{idx}",
                    use_container_width=True,
                ):
                    fila = int(row["_sheet_row"])
                    reclamo_id = _safe_str(row.get("ID Reclamo", ""))
                    updates_list = [
                        {
                            "range": f"{_col_letter('Estado')}{fila}",
                            "values": [["Resuelto"]],
                        }
                    ]

                    success, error = api_manager.safe_sheet_operation(
                        dm_batch_update_sheet,
                        sheet_reclamos,
                        updates_list,
                        is_batch=True,
                    )

                    if success:
                        # Reflejar de inmediato en memoria
                        _actualizar_en_memoria(fila, reclamo_id, {"Estado": "Resuelto"})
                        st.success(
                            f"✅ Desconexión de {row.get('Nombre', 'Cliente')} marcada como resuelta."
                        )
                        cambios = True
                    else:
                        st.error(f"❌ Error al actualizar: {error}")

        st.divider()

    return cambios