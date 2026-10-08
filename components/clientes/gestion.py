# components/clientes/gestion.py
import streamlit as st
import pandas as pd
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet as dm_batch_update_sheet
from utils.date_utils import ahora_argentina, format_fecha
from components.reclamos.nuevo import generar_id_unico
from config.settings import SECTORES_DISPONIBLES, PLANES_DISPONIBLES, SPLITTERS_DISPONIBLES, MARCAS_EQUIPO, DEBUG_MODE

def verificar_precinto_duplicado(df_clientes, precinto, cliente_id_ignorar=None):
    """
    Busca si un precinto ya está asignado a otro cliente.
    Retorna la fila del cliente si existe, de lo contrario None.
    """
    if not precinto or pd.isna(precinto) or str(precinto).strip() == "":
        return None
    
    df_filtro = df_clientes[df_clientes["N° de Precinto"].astype(str).str.strip() == str(precinto).strip()]
    
    if cliente_id_ignorar:
        df_filtro = df_filtro[df_filtro["Nº Cliente"].astype(str).str.strip() != str(cliente_id_ignorar).strip()]
        
    if not df_filtro.empty:
        return df_filtro.iloc[0]
    return None

# =====================================================================
# FUNCIONES HELPER BIDIRECCIONALES (CLIENTE -> CAJA)
# =====================================================================
def _obtener_info_caja(df_cajas, nombre_caja):
    if df_cajas is None or df_cajas.empty or not nombre_caja or str(nombre_caja).strip() == "":
        return None
    caja_data = df_cajas[df_cajas["N De Caja"].astype(str).str.strip() == str(nombre_caja).strip()]
    if caja_data.empty:
        return None
    return caja_data.iloc[0]

def _buscar_puerto_vacio(caja_row):
    splitter = str(caja_row.get("Splitter", "1/4")).strip()
    num_puertos = 4
    if splitter == "1/8": num_puertos = 8
    elif splitter == "1/16": num_puertos = 16

    letras = ["I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X"]

    for i in range(num_puertos):
        val = str(caja_row.get(f"Precinto {i+1}", "")).strip()
        if val in ("", "nan", "None"):
            return letras[i]
    return None

def _buscar_puerto_ocupado(caja_row, precinto):
    if not precinto or str(precinto).strip() == "":
        return None
    splitter = str(caja_row.get("Splitter", "1/4")).strip()
    num_puertos = 4
    if splitter == "1/8": num_puertos = 8
    elif splitter == "1/16": num_puertos = 16

    letras = ["I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X"]

    for i in range(num_puertos):
        val = str(caja_row.get(f"Precinto {i+1}", "")).strip()
        if val == str(precinto).strip():
            return letras[i]
    return None
# =====================================================================

def render_gestion_clientes(df_clientes, df_reclamos, sheet_clientes, user_role, df_cajas=None, sheet_cajas=None):
    """
    Modulo de busqueda, creacion y edicion de clientes + Cajas NAP + Buscador de Precintos.
    """
    needs_refresh = False

    # Extraer opciones dinámicas de Cajas para los menús desplegables
    opciones_cajas = [""]
    if df_cajas is not None and not df_cajas.empty and "N De Caja" in df_cajas.columns:
        cajas_validas = [str(c).strip() for c in df_cajas["N De Caja"].dropna().tolist() if str(c).strip() not in ("", "nan", "None")]
        cajas_validas = sorted(list(set(cajas_validas)))
        opciones_cajas.extend(cajas_validas)

    # ==========================================
    # SECCION 1: GESTION DE CLIENTES
    # ==========================================
    st.subheader("🔍 Búsqueda y Gestión de Clientes")

    df_clientes["Nº Cliente"] = df_clientes["Nº Cliente"].astype(str).str.strip()

    nro_cliente = st.text_input(
        "Ingresá el Número de Cliente",
        placeholder="Ej: 9944",
        key="search_nro_cliente"
    ).strip()

    if nro_cliente:
        cliente_data = df_clientes[df_clientes["Nº Cliente"] == nro_cliente]

        if cliente_data.empty:
            # ==========================================
            # CASO 1: EL CLIENTE NO EXISTE - CREACION
            # ==========================================
            st.info("ℹ️ Este cliente no existe en la base. Completá los datos para crearlo.")

            with st.form("form_crear_cliente"):
                col1, col2 = st.columns(2)

                with col1:
                    nuevo_nombre = st.text_input("👤 Nombre*", placeholder="Nombre completo")
                    nuevo_direccion = st.text_input("📍 Dirección*", placeholder="Dirección completa")
                    nuevo_plan = st.selectbox("📺 Plan", options=PLANES_DISPONIBLES, index=0)

                with col2:
                    nuevo_telefono = st.text_input("📞 Teléfono", placeholder="Número de contacto")
                    nuevo_sector = st.selectbox("🔢 Sector*", options=SECTORES_DISPONIBLES, index=0)
                    nuevo_caja_nap = st.selectbox("📦 Caja NAP (opcional)", options=opciones_cajas, index=0)

                nuevo_precinto = st.text_input("🔒 N° de Precinto (opcional)", placeholder="Número de precinto")

                submit_crear = st.form_submit_button("✅ Crear Nuevo Cliente", use_container_width=True)

                if submit_crear:
                    if not nuevo_nombre.strip() or not nuevo_direccion.strip():
                        st.error("⚠️ El Nombre y la Dirección son campos obligatorios.")
                    else:
                        # Validar si el precinto ya existe
                        duplicado = verificar_precinto_duplicado(df_clientes, nuevo_precinto)
                        if duplicado is not None:
                            st.error(f"❌ Error: El precinto '{nuevo_precinto}' ya está en uso por el cliente: {duplicado['Nº Cliente']} - {duplicado['Nombre']}.")
                        else:
                            # -------- LOGICA BIDIRECCIONAL: Verificar Caja ANTES de guardar --------
                            caja_llena = False
                            updates_caja_creacion = []
                            if nuevo_caja_nap.strip() and nuevo_precinto.strip():
                                caja_row = _obtener_info_caja(df_cajas, nuevo_caja_nap)
                                if caja_row is not None:
                                    puerto_vacio = _buscar_puerto_vacio(caja_row)
                                    if not puerto_vacio:
                                        caja_llena = True
                                        st.error(f"❌ La Caja NAP '{nuevo_caja_nap}' ya está llena. Elegí otra caja libre o dejá el campo vacío.")
                                    else:
                                        idx_caja = caja_row.name + 2
                                        updates_caja_creacion.append({"range": f"{puerto_vacio}{idx_caja}", "values": [[nuevo_precinto.strip()]]})

                            if not caja_llena:
                                try:
                                    id_cliente = generar_id_unico()
                                    ultima_mod = format_fecha(ahora_argentina())

                                    fila_cliente = [
                                        nro_cliente,
                                        nuevo_sector,
                                        nuevo_nombre.upper().strip(),
                                        nuevo_direccion.upper().strip(),
                                        nuevo_telefono.strip(),
                                        nuevo_precinto.strip(),
                                        id_cliente,
                                        ultima_mod,
                                        "",
                                        "",
                                        "",
                                        nuevo_plan,
                                        nuevo_caja_nap.strip()
                                    ]

                                    success, error = api_manager.safe_sheet_operation(
                                        sheet_clientes.append_row,
                                        fila_cliente
                                    )

                                    if success:
                                        # -------- LOGICA BIDIRECCIONAL: Impactar Caja --------
                                        if updates_caja_creacion and sheet_cajas is not None:
                                            dm_batch_update_sheet(sheet_cajas, updates_caja_creacion)
                                            
                                        st.success(f"✅ Cliente {nro_cliente} creado correctamente (ID: {id_cliente}).")
                                        needs_refresh = True
                                    else:
                                        st.error(f"❌ Error al crear el cliente: {error}")

                                except Exception as e:
                                    st.error(f"❌ Error inesperado: {str(e)}")
                                    if DEBUG_MODE:
                                        st.exception(e)

        else:
            # ==========================================
            # CASO 2: EL CLIENTE SI EXISTE - EDICION
            # ==========================================
            cliente = cliente_data.iloc[0]
            row_idx = cliente.name + 2

            col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
            with col_r1:
                st.markdown(f"**👤 Nombre:** {cliente.get('Nombre', 'N/A')}")
            with col_r2:
                st.markdown(f"**📍 Dirección:** {cliente.get('Dirección', 'N/A')}")
            with col_r3:
                st.markdown(f"**📞 Teléfono:** {cliente.get('Teléfono', 'N/A')}")
            with col_r4:
                st.markdown(f"**📺 Plan:** {cliente.get('Plan', 'Sin plan')}")
            with col_r5:
                val_caja = cliente.get('Caja NAP', 'Sin Caja')
                if str(val_caja) in ('nan', 'None', ''): val_caja = 'Sin Caja'
                st.markdown(f"**📦 Caja NAP:** {val_caja}")

            st.markdown("---")

            # ACORDEON 1: EDITAR DATOS PRINCIPALES
            with st.expander("✏️ Editar Datos del Cliente (Sector, Nombre, Dirección, Teléfono, Plan, Caja)"):
                with st.form(f"form_editar_datos_{row_idx}"):
                    edit_col1, edit_col2 = st.columns(2)

                    with edit_col1:
                        edit_nombre = st.text_input("👤 Nombre", value=cliente.get("Nombre", ""), key=f"cli_nom_{row_idx}")
                        edit_direccion = st.text_input("📍 Dirección", value=cliente.get("Dirección", ""), key=f"cli_dir_{row_idx}")
                        
                        # Precargar la caja correcta en el selectbox
                        caja_actual_cli = str(cliente.get("Caja NAP", "")).strip().replace("nan", "")
                        if caja_actual_cli == "None": caja_actual_cli = ""
                        opciones_cajas_edit = opciones_cajas.copy()
                        if caja_actual_cli and caja_actual_cli not in opciones_cajas_edit:
                            opciones_cajas_edit.append(caja_actual_cli)
                        try:
                            caja_idx = opciones_cajas_edit.index(caja_actual_cli)
                        except ValueError:
                            caja_idx = 0
                        edit_caja_nap = st.selectbox("📦 Caja NAP", options=opciones_cajas_edit, index=caja_idx, key=f"cli_caja_{row_idx}")

                    with edit_col2:
                        edit_telefono = st.text_input("📞 Teléfono", value=str(cliente.get("Teléfono", "")), key=f"cli_tel_{row_idx}")
                        sector_actual = str(cliente.get("Sector", "1")).strip()
                        try:
                            sector_idx = SECTORES_DISPONIBLES.index(sector_actual) if sector_actual in SECTORES_DISPONIBLES else 0
                        except ValueError:
                            sector_idx = 0
                        edit_sector = st.selectbox("🔢 Sector", options=SECTORES_DISPONIBLES, index=sector_idx, key=f"cli_sec_{row_idx}")

                        plan_actual = str(cliente.get("Plan", "")).strip()
                        try:
                            plan_idx = PLANES_DISPONIBLES.index(plan_actual) if plan_actual in PLANES_DISPONIBLES else 0
                        except ValueError:
                            plan_idx = 0
                        edit_plan = st.selectbox("📺 Plan", options=PLANES_DISPONIBLES, index=plan_idx, key=f"cli_plan_{row_idx}")

                    submit_edit = st.form_submit_button("💾 Guardar Cambios en Datos", use_container_width=True)

                    if submit_edit:
                        # -------- LOGICA BIDIRECCIONAL: Mover precinto si se cambia la caja --------
                        caja_vieja = str(cliente.get("Caja NAP", "")).strip().replace("nan", "")
                        if caja_vieja == "None": caja_vieja = ""
                        caja_nueva = edit_caja_nap.strip()
                        precinto_actual = str(cliente.get("N° de Precinto", "")).strip().replace("nan", "")
                        if precinto_actual == "None": precinto_actual = ""

                        caja_llena_error = False
                        updates_caja_edicion = []

                        # Solo actuamos si la caja cambió y el cliente TIENE un precinto físico para mover
                        if caja_vieja != caja_nueva and precinto_actual:
                            # 1. Verificar si hay espacio en la NUEVA caja
                            if caja_nueva:
                                caja_row_nueva = _obtener_info_caja(df_cajas, caja_nueva)
                                if caja_row_nueva is not None:
                                    puerto_vacio = _buscar_puerto_vacio(caja_row_nueva)
                                    if not puerto_vacio:
                                        caja_llena_error = True
                                        st.error(f"❌ La Caja NAP '{caja_nueva}' ya está llena. Elegí otra caja o liberá un puerto primero.")
                                    else:
                                        idx_nueva = caja_row_nueva.name + 2
                                        updates_caja_edicion.append({"range": f"{puerto_vacio}{idx_nueva}", "values": [[precinto_actual]]})

                            # 2. Si todo va bien, quitar el precinto de la VIEJA caja
                            if not caja_llena_error and caja_vieja:
                                caja_row_vieja = _obtener_info_caja(df_cajas, caja_vieja)
                                if caja_row_vieja is not None:
                                    puerto_ocupado = _buscar_puerto_ocupado(caja_row_vieja, precinto_actual)
                                    if puerto_ocupado:
                                        idx_vieja = caja_row_vieja.name + 2
                                        updates_caja_edicion.append({"range": f"{puerto_ocupado}{idx_vieja}", "values": [[""]]})

                        # Si hubo un error de caja llena, abortamos todo el guardado
                        if not caja_llena_error:
                            updates = []
                            if str(cliente.get("Sector", "")).strip() != edit_sector:
                                updates.append({"range": f"B{row_idx}", "values": [[edit_sector]]})
                            if str(cliente.get("Nombre", "")).strip() != edit_nombre.upper().strip():
                                updates.append({"range": f"C{row_idx}", "values": [[edit_nombre.upper().strip()]]})
                            if str(cliente.get("Dirección", "")).strip() != edit_direccion.upper().strip():
                                updates.append({"range": f"D{row_idx}", "values": [[edit_direccion.upper().strip()]]})
                            if str(cliente.get("Teléfono", "")).strip() != edit_telefono.strip():
                                updates.append({"range": f"E{row_idx}", "values": [[edit_telefono.strip()]]})
                            if str(cliente.get("Plan", "")).strip() != edit_plan:
                                updates.append({"range": f"L{row_idx}", "values": [[edit_plan]]})
                            if str(cliente.get("Caja NAP", "")).strip() != edit_caja_nap.strip():
                                updates.append({"range": f"M{row_idx}", "values": [[edit_caja_nap.strip()]]})

                            if updates:
                                fecha_mod = format_fecha(ahora_argentina())
                                updates.append({"range": f"H{row_idx}", "values": [[fecha_mod]]})
                                success, error = dm_batch_update_sheet(sheet_clientes, updates)
                                if success:
                                    # -------- APLICAR IMPACTO EN CAJAS --------
                                    if updates_caja_edicion and sheet_cajas is not None:
                                        dm_batch_update_sheet(sheet_cajas, updates_caja_edicion)
                                        
                                    st.success("✅ Datos del cliente y Cajas NAP actualizados correctamente.")
                                    needs_refresh = True
                                else:
                                    st.error(f"❌ Error al actualizar datos: {error}")
                            else:
                                st.info("ℹ️ No se detectaron cambios en los datos del cliente.")

            # ACORDEON 2: GESTION DE PRECINTO
            with st.expander("🔒 Gestión de Precinto"):
                precinto_actual = str(cliente.get("N° de Precinto", "")).strip()
                has_precinto = precinto_actual not in ("", "nan", "None")

                if has_precinto:
                    st.markdown(f"**Precinto actual:** `{precinto_actual}`")
                    with st.form(f"form_editar_precinto_{row_idx}"):
                        new_precinto = st.text_input("Modificar N° de Precinto", value=precinto_actual, key=f"cli_prec_edit_{row_idx}")
                        submit_precinto = st.form_submit_button("💾 Actualizar Precinto")

                        if submit_precinto:
                            if not new_precinto.strip():
                                st.error("❌ El precinto no puede estar vacío.")
                            elif new_precinto.strip() != precinto_actual:
                                duplicado = verificar_precinto_duplicado(df_clientes, new_precinto.strip(), nro_cliente)
                                if duplicado is not None:
                                    st.error(f"❌ Error: El precinto '{new_precinto}' ya lo tiene el cliente: {duplicado['Nº Cliente']} - {duplicado['Nombre']}.")
                                else:
                                    # -------- LOGICA BIDIRECCIONAL: Reemplazar precinto en la caja actual --------
                                    caja_actual_cli = str(cliente.get("Caja NAP", "")).strip().replace("nan", "")
                                    if caja_actual_cli == "None": caja_actual_cli = ""
                                    
                                    updates_caja_precinto = []
                                    caja_llena_error = False

                                    if caja_actual_cli:
                                        caja_row = _obtener_info_caja(df_cajas, caja_actual_cli)
                                        if caja_row is not None:
                                            # Buscamos donde estaba el viejo para pisarlo con el nuevo
                                            puerto_ocupado = _buscar_puerto_ocupado(caja_row, precinto_actual)
                                            if puerto_ocupado:
                                                idx_caja = caja_row.name + 2
                                                updates_caja_precinto.append({"range": f"{puerto_ocupado}{idx_caja}", "values": [[new_precinto.strip()]]})
                                            else:
                                                # Raro, estaba asignada la caja pero no estaba su puerto. Le damos uno libre.
                                                puerto_vacio = _buscar_puerto_vacio(caja_row)
                                                if puerto_vacio:
                                                    idx_caja = caja_row.name + 2
                                                    updates_caja_precinto.append({"range": f"{puerto_vacio}{idx_caja}", "values": [[new_precinto.strip()]]})
                                                else:
                                                    caja_llena_error = True
                                                    st.error(f"❌ La Caja NAP '{caja_actual_cli}' está llena. Resolvé esto desde el Editor de Cajas.")

                                    if not caja_llena_error:
                                        updates = [{"range": f"F{row_idx}", "values": [[new_precinto.strip()]]}]
                                        success, error = dm_batch_update_sheet(sheet_clientes, updates)
                                        if success:
                                            if updates_caja_precinto and sheet_cajas is not None:
                                                dm_batch_update_sheet(sheet_cajas, updates_caja_precinto)
                                            st.success("✅ Precinto actualizado correctamente.")
                                            needs_refresh = True
                                        else:
                                            st.error(f"❌ Error al guardar: {error}")
                            else:
                                st.info("ℹ️ El precinto es el mismo, sin cambios.")
                else:
                    st.warning("Este cliente no tiene precinto registrado.")
                    with st.form(f"form_cargar_precinto_{row_idx}"):
                        new_precinto = st.text_input("Ingresar N° de Precinto", key=f"cli_prec_new_{row_idx}")
                        submit_precinto = st.form_submit_button("💾 Guardar Precinto")

                        if submit_precinto:
                            if not new_precinto.strip():
                                st.error("❌ Debés ingresar un número de precinto.")
                            else:
                                duplicado = verificar_precinto_duplicado(df_clientes, new_precinto.strip())
                                if duplicado is not None:
                                    st.error(f"❌ Error: El precinto '{new_precinto}' ya lo tiene el cliente: {duplicado['Nº Cliente']} - {duplicado['Nombre']}.")
                                else:
                                    # -------- LOGICA BIDIRECCIONAL: Si no tenía precinto y se le agrega, buscar espacio --------
                                    caja_actual_cli = str(cliente.get("Caja NAP", "")).strip().replace("nan", "")
                                    if caja_actual_cli == "None": caja_actual_cli = ""
                                    
                                    updates_caja_precinto = []
                                    caja_llena_error = False

                                    if caja_actual_cli:
                                        caja_row = _obtener_info_caja(df_cajas, caja_actual_cli)
                                        if caja_row is not None:
                                            puerto_vacio = _buscar_puerto_vacio(caja_row)
                                            if puerto_vacio:
                                                idx_caja = caja_row.name + 2
                                                updates_caja_precinto.append({"range": f"{puerto_vacio}{idx_caja}", "values": [[new_precinto.strip()]]})
                                            else:
                                                caja_llena_error = True
                                                st.error(f"❌ La Caja NAP '{caja_actual_cli}' está llena. No se puede asignar el nuevo precinto a esta caja.")

                                    if not caja_llena_error:
                                        updates = [{"range": f"F{row_idx}", "values": [[new_precinto.strip()]]}]
                                        success, error = dm_batch_update_sheet(sheet_clientes, updates)
                                        if success:
                                            if updates_caja_precinto and sheet_cajas is not None:
                                                dm_batch_update_sheet(sheet_cajas, updates_caja_precinto)
                                            st.success("✅ Precinto guardado correctamente.")
                                            needs_refresh = True
                                        else:
                                            st.error(f"❌ Error al guardar en la hoja: {error}")

            # ACORDEON 3: GEOREFERENCIA
            with st.expander("🗺️ Georreferencia"):
                lat = str(cliente.get("Latitud", "")).strip()
                lon = str(cliente.get("Longitud", "")).strip()

                has_geo = False
                if lat not in ("", "nan", "None") and lon not in ("", "nan", "None"):
                    try:
                        float(lat.replace(',', '.'))
                        float(lon.replace(',', '.'))
                        has_geo = True
                    except (ValueError, TypeError):
                        has_geo = False

                if has_geo:
                    st.success("✅ Georreferencia registrada")
                    maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                    st.markdown(f"🗺️ [Ver ubicación en Google Maps]({maps_url})")

                    with st.form(f"form_editar_geo_{row_idx}"):
                        edit_lat = st.text_input("Latitud", value=lat, key=f"cli_lat_edit_{row_idx}")
                        edit_lon = st.text_input("Longitud", value=lon, key=f"cli_lon_edit_{row_idx}")
                        submit_edit_geo = st.form_submit_button("💾 Actualizar Coordenadas")

                        if submit_edit_geo:
                            try:
                                float(edit_lat.strip().replace(',', '.'))
                                float(edit_lon.strip().replace(',', '.'))
                                updates = [
                                    {"range": f"J{row_idx}", "values": [[edit_lat.strip()]]},
                                    {"range": f"K{row_idx}", "values": [[edit_lon.strip()]]}
                                ]
                                success, error = dm_batch_update_sheet(sheet_clientes, updates)
                                if success:
                                    st.success("✅ Coordenadas actualizadas.")
                                    needs_refresh = True
                                else:
                                    st.error(f"❌ Error: {error}")
                            except ValueError:
                                st.error("❌ Las coordenadas deben ser valores numéricos.")
                else:
                    st.info("ℹ️ Este cliente no tiene georreferencia cargada. Ingresá las coordenadas:")
                    default_lat = "-26."
                    default_lon = "-59."

                    with st.form(f"form_cargar_geo_{row_idx}"):
                        val_lat = lat if lat not in ("nan", "None", "") else default_lat
                        val_lon = lon if lon not in ("nan", "None", "") else default_lon

                        new_lat = st.text_input("Latitud", value=val_lat, key=f"cli_lat_new_{row_idx}")
                        new_lon = st.text_input("Longitud", value=val_lon, key=f"cli_lon_new_{row_idx}")
                        submitted = st.form_submit_button("💾 Guardar Coordenadas")

                        if submitted:
                            if not new_lat.strip() or not new_lon.strip():
                                st.error("❌ Debés completar ambos campos para guardar.")
                            else:
                                try:
                                    float(new_lat.strip().replace(',', '.'))
                                    float(new_lon.strip().replace(',', '.'))
                                    updates = [
                                        {"range": f"J{row_idx}", "values": [[new_lat.strip()]]},
                                        {"range": f"K{row_idx}", "values": [[new_lon.strip()]]}
                                    ]
                                    success, error = dm_batch_update_sheet(sheet_clientes, updates)
                                    if success:
                                        st.success("✅ Georreferencia guardada correctamente.")
                                        needs_refresh = True
                                    else:
                                        st.error(f"❌ Error al guardar en la hoja: {error}")
                                except ValueError:
                                    st.error("❌ Las coordenadas deben ser valores numéricos.")

            # ACORDEON 4: HISTORIAL DE RECLAMOS
            with st.expander("📜 Historial de Reclamos"):
                if df_reclamos is not None and not df_reclamos.empty:
                    df_reclamos["Nº Cliente"] = df_reclamos["Nº Cliente"].astype(str).str.strip()
                    reclamos_cliente = df_reclamos[df_reclamos["Nº Cliente"] == nro_cliente]
                    
                    if reclamos_cliente.empty:
                        st.info("ℹ️ No hay reclamos registrados para este cliente.")
                    else:
                        ultimos_reclamos = reclamos_cliente.tail(5).iloc[::-1]
                        
                        for _, rec in ultimos_reclamos.iterrows():
                            fecha = str(rec.get("Fecha y hora", "S/F")).strip()
                            if fecha in ("nan", "None", ""): fecha = "S/F"
                                
                            tipo = str(rec.get("Tipo de reclamo", "S/T")).strip()
                            if tipo in ("nan", "None", ""): tipo = "S/T"
                                
                            estado = str(rec.get("Estado", "S/E")).strip()
                            if estado in ("nan", "None", ""): estado = "S/E"
                                
                            tecnico = str(rec.get("Técnico", "S/T")).strip()
                            if tecnico in ("nan", "None", ""): tecnico = "S/T"
                            
                            st.markdown(f"- **{fecha}** | {tipo} | Estado: *{estado}* | Técnico: *{tecnico}*")
                else:
                    st.warning("⚠️ Base de reclamos no disponible.")

    # ==========================================
    # SECCION 2: EDITOR DE CAJAS NAP
    # ==========================================
    if df_cajas is not None and sheet_cajas is not None:
        st.markdown("---")
        st.subheader("📦 Editor de Cajas NAP")

        df_cajas_norm = df_cajas.copy()
        df_cajas_norm["N De Caja"] = df_cajas_norm["N De Caja"].astype(str).str.strip()

        nro_caja = st.text_input(
            "Ingresá el N° de Caja NAP",
            placeholder="Ej: NAP-001",
            key="search_nro_caja"
        ).strip()

        if nro_caja:
            caja_data = df_cajas_norm[df_cajas_norm["N De Caja"] == nro_caja]

            if caja_data.empty:
                # ==========================================
                # LA CAJA NO EXISTE - CREACION
                # ==========================================
                st.info("ℹ Esta caja NAP no existe en la base. Completá los datos para crearla.")

                with st.form("form_crear_caja"):
                    col_c1, col_c2 = st.columns(2)

                    with col_c1:
                        nuevo_sector_caja = st.selectbox(
                            "🔢 Sector*", options=SECTORES_DISPONIBLES, index=0, key="caja_sector_new"
                        )
                        nuevo_barrio = st.text_input("🏘️ Barrio*", placeholder="Nombre del barrio")

                    with col_c2:
                        nuevo_lat_caja = st.text_input("📍 Latitud", value="-26.", key="caja_lat_new")
                        nuevo_lon_caja = st.text_input("📍 Longitud", value="-59.", key="caja_lon_new")

                    col_c3, col_c4 = st.columns(2)
                    with col_c3:
                        nuevo_obs_caja = st.text_input("📝 Observación", placeholder="Observaciones (opcional)")
                        nueva_marca = st.selectbox("🏷️ Marca Equipo", options=MARCAS_EQUIPO, index=0, key="caja_marca_new")
                    with col_c4:
                        nuevo_splitter = st.selectbox(
                            "🔀 Splitter*",
                            options=SPLITTERS_DISPONIBLES,
                            index=1,
                            key="caja_splitter_new"
                        )

                    submit_crear_caja = st.form_submit_button("✅ Crear Nueva Caja NAP", use_container_width=True)

                    if submit_crear_caja:
                        if not nuevo_barrio.strip():
                            st.error("⚠️ El Barrio es un campo obligatorio.")
                        else:
                            try:
                                float(nuevo_lat_caja.strip().replace(',', '.'))
                                float(nuevo_lon_caja.strip().replace(',', '.'))

                                fila_caja = [
                                    nro_caja,
                                    nuevo_sector_caja,
                                    nuevo_barrio.upper().strip(),
                                    nuevo_lat_caja.strip(),
                                    nuevo_lon_caja.strip(),
                                    nuevo_obs_caja.strip(),
                                    nueva_marca.strip(),
                                    nuevo_splitter.strip()
                                ]

                                success, error = api_manager.safe_sheet_operation(
                                    sheet_cajas.append_row,
                                    fila_caja
                                )

                                if success:
                                    st.success(f"✅ Caja NAP `{nro_caja}` creada correctamente. Podés buscarla ahora para cargar los puertos.")
                                    needs_refresh = True
                                else:
                                    st.error(f"❌ Error al crear la caja NAP: {error}")

                            except ValueError:
                                st.error("❌ Las coordenadas deben ser valores numéricos (ej: -26.123456).")
                            except Exception as e:
                                st.error(f"❌ Error inesperado: {str(e)}")
                                if DEBUG_MODE:
                                    st.exception(e)

            else:
                # ==========================================
                # LA CAJA SI EXISTE - EDICION
                # ==========================================
                caja = caja_data.iloc[0]
                caja_row_idx = caja.name + 2

                col_cr1, col_cr2, col_cr3, col_cr4, col_cr5 = st.columns(5)
                with col_cr1:
                    st.markdown(f"**🔢 Sector:** {caja.get('Sector', 'N/A')}")
                with col_cr2:
                    st.markdown(f"**🏘️ Barrio:** {caja.get('Barrio', 'N/A')}")
                with col_cr3:
                    st.markdown(f"**🏷️ Marca Equipo:** {caja.get('Marca Equipo', 'N/A')}")
                with col_cr4:
                    splitter_val = caja.get('Splitter', '')
                    splitter_display = splitter_val if splitter_val and str(splitter_val).strip() not in ('', 'nan', 'None') else 'Sin asignar'
                    st.markdown(f"**🔀 Splitter:** `{splitter_display}`")
                with col_cr5:
                    lat_c = str(caja.get('Latitud', '')).strip()
                    lon_c = str(caja.get('Longitud', '')).strip()
                    if lat_c not in ("", "nan", "None") and lon_c not in ("", "nan", "None"):
                        try:
                            float(lat_c.replace(',', '.'))
                            float(lon_c.replace(',', '.'))
                            maps_url_caja = f"https://www.google.com/maps?q={lat_c},{lon_c}"
                            st.markdown(f"**🗺️** [Ver en Maps]({maps_url_caja})")
                        except (ValueError, TypeError):
                            st.markdown("**🗺️** Geo. inválida")
                    else:
                        st.markdown("**🗺️** Sin georef.")

                st.markdown("---")

                # ACORDEON CAJA 1: EDITAR DATOS PRINCIPALES
                with st.expander("✏️ Editar Datos de la Caja NAP (Sector, Barrio, Observación, Marca, Splitter)"):
                    with st.form(f"form_editar_caja_{caja_row_idx}"):
                        edit_ccol1, edit_ccol2 = st.columns(2)

                        with edit_ccol1:
                            sector_actual_caja = str(caja.get("Sector", "1")).strip()
                            try:
                                sector_idx_caja = SECTORES_DISPONIBLES.index(sector_actual_caja) if sector_actual_caja in SECTORES_DISPONIBLES else 0
                            except ValueError:
                                sector_idx_caja = 0
                            edit_sector_caja = st.selectbox(
                                "🔢 Sector", options=SECTORES_DISPONIBLES, index=sector_idx_caja, key=f"caja_sec_{caja_row_idx}"
                            )
                            edit_barrio = st.text_input(
                                "🏘️ Barrio", value=str(caja.get("Barrio", "")), key=f"caja_barrio_{caja_row_idx}"
                            )
                            edit_obs_caja = st.text_input(
                                "📝 Observación", value=str(caja.get("Observacion", "")), key=f"caja_obs_{caja_row_idx}"
                            )

                        with edit_ccol2:
                            marca_actual = str(caja.get("Marca Equipo", "Huawei")).strip()
                            try:
                                marca_idx = MARCAS_EQUIPO.index(marca_actual) if marca_actual in MARCAS_EQUIPO else 0
                            except ValueError:
                                marca_idx = 0
                            edit_marca = st.selectbox(
                                "🏷️ Marca Equipo", options=MARCAS_EQUIPO, index=marca_idx, key=f"caja_marca_{caja_row_idx}"
                            )

                            splitter_actual = str(caja.get("Splitter", "")).strip()
                            try:
                                splitter_idx = SPLITTERS_DISPONIBLES.index(splitter_actual) if splitter_actual in SPLITTERS_DISPONIBLES else 1
                            except ValueError:
                                splitter_idx = 1
                            edit_splitter = st.selectbox(
                                "🔀 Splitter",
                                options=SPLITTERS_DISPONIBLES,
                                index=splitter_idx,
                                key=f"caja_splitter_{caja_row_idx}"
                            )

                        submit_edit_caja = st.form_submit_button("💾 Guardar Cambios en Caja NAP", use_container_width=True)

                        if submit_edit_caja:
                            updates = []

                            if str(caja.get("Sector", "")).strip() != edit_sector_caja:
                                updates.append({"range": f"B{caja_row_idx}", "values": [[edit_sector_caja]]})

                            if str(caja.get("Barrio", "")).strip() != edit_barrio.upper().strip():
                                updates.append({"range": f"C{caja_row_idx}", "values": [[edit_barrio.upper().strip()]]})

                            if str(caja.get("Observacion", "")).strip() != edit_obs_caja.strip():
                                updates.append({"range": f"F{caja_row_idx}", "values": [[edit_obs_caja.strip()]]})

                            if str(caja.get("Marca Equipo", "")).strip() != edit_marca.strip():
                                updates.append({"range": f"G{caja_row_idx}", "values": [[edit_marca.strip()]]})

                            if str(caja.get("Splitter", "")).strip() != edit_splitter.strip():
                                updates.append({"range": f"H{caja_row_idx}", "values": [[edit_splitter.strip()]]})

                            if updates:
                                success, error = dm_batch_update_sheet(sheet_cajas, updates)
                                if success:
                                    st.success("✅ Datos de la caja NAP actualizados correctamente.")
                                    needs_refresh = True
                                else:
                                    st.error(f"❌ Error al actualizar datos: {error}")
                            else:
                                st.info("ℹ️ No se detectaron cambios en los datos de la caja NAP.")

                # ACORDEON CAJA 2: GEOREFERENCIA
                with st.expander("🗺 Georreferencia de Caja NAP"):
                    lat_caja = str(caja.get("Latitud", "")).strip()
                    lon_caja = str(caja.get("Longitud", "")).strip()

                    has_geo_caja = False
                    if lat_caja not in ("", "nan", "None") and lon_caja not in ("", "nan", "None"):
                        try:
                            float(lat_caja.replace(',', '.'))
                            float(lon_caja.replace(',', '.'))
                            has_geo_caja = True
                        except (ValueError, TypeError):
                            has_geo_caja = False

                    if has_geo_caja:
                        st.success("✅ Georreferencia registrada")
                        maps_url_caja = f"https://www.google.com/maps?q={lat_caja},{lon_caja}"
                        st.markdown(f"🗺️ [Ver ubicación en Google Maps]({maps_url_caja})")

                        with st.form(f"form_editar_geo_caja_{caja_row_idx}"):
                            edit_lat_caja = st.text_input("Latitud", value=lat_caja, key=f"caja_lat_edit_{caja_row_idx}")
                            edit_lon_caja = st.text_input("Longitud", value=lon_caja, key=f"caja_lon_edit_{caja_row_idx}")
                            submit_edit_geo_caja = st.form_submit_button("💾 Actualizar Coordenadas")

                            if submit_edit_geo_caja:
                                try:
                                    float(edit_lat_caja.strip().replace(',', '.'))
                                    float(edit_lon_caja.strip().replace(',', '.'))

                                    updates = [
                                        {"range": f"D{caja_row_idx}", "values": [[edit_lat_caja.strip()]]},
                                        {"range": f"E{caja_row_idx}", "values": [[edit_lon_caja.strip()]]}
                                    ]
                                    success, error = dm_batch_update_sheet(sheet_cajas, updates)
                                    if success:
                                        st.success("✅ Coordenadas de caja NAP actualizadas.")
                                        needs_refresh = True
                                    else:
                                        st.error(f"❌ Error: {error}")
                                except ValueError:
                                    st.error("❌ Las coordenadas deben ser valores numéricos.")
                    else:
                        st.info("ℹ️ Esta caja NAP no tiene georreferencia cargada. Ingresá las coordenadas:")
                        default_lat_caja = "-26."
                        default_lon_caja = "-59."

                        with st.form(f"form_cargar_geo_caja_{caja_row_idx}"):
                            val_lat_caja = lat_caja if lat_caja not in ("nan", "None", "") else default_lat_caja
                            val_lon_caja = lon_caja if lon_caja not in ("nan", "None", "") else default_lon_caja

                            new_lat_caja = st.text_input("Latitud", value=val_lat_caja, key=f"caja_lat_new_{caja_row_idx}")
                            new_lon_caja = st.text_input("Longitud", value=val_lon_caja, key=f"caja_lon_new_{caja_row_idx}")
                            submitted_caja_geo = st.form_submit_button("💾 Guardar Coordenadas")

                            if submitted_caja_geo:
                                if not new_lat_caja.strip() or not new_lon_caja.strip():
                                    st.error("❌ Debés completar ambos campos para guardar.")
                                else:
                                    try:
                                        float(new_lat_caja.strip().replace(',', '.'))
                                        float(new_lon_caja.strip().replace(',', '.'))

                                        updates = [
                                            {"range": f"D{caja_row_idx}", "values": [[new_lat_caja.strip()]]},
                                            {"range": f"E{caja_row_idx}", "values": [[new_lon_caja.strip()]]}
                                        ]
                                        success, error = dm_batch_update_sheet(sheet_cajas, updates)
                                        if success:
                                            st.success("✅ Georreferencia de caja NAP guardada correctamente.")
                                            needs_refresh = True
                                        else:
                                            st.error(f"❌ Error al guardar en la hoja: {error}")
                                    except ValueError:
                                        st.error("❌ Las coordenadas deben ser valores numéricos (ej: -26.123456).")

                # ACORDEON CAJA 3: GESTION DE PUERTOS (PRECINTOS) - (DIVIDIDO EN 2 COLUMNAS)
                with st.expander("🔌 Gestión de Puertos (Precintos)"):
                    splitter_actual = str(caja.get('Splitter', '1/4')).strip()
                    num_puertos = 4
                    if splitter_actual == "1/8":
                        num_puertos = 8
                    elif splitter_actual == "1/16":
                        num_puertos = 16

                    letras_columnas = ["I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X"]

                    with st.form(f"form_puertos_caja_{caja_row_idx}"):
                        st.markdown(f"**Splitter {splitter_actual}** — Se han habilitado **{num_puertos}** puertos.")
                        
                        inputs_puertos = []
                        mitad_puertos = num_puertos // 2
                        
                        col_p1, col_p2 = st.columns(2)
                        
                        # Generar dinámicamente los campos según el splitter en 2 columnas
                        for i in range(num_puertos):
                            col_precinto = f"Precinto {i+1}"
                            val_actual_puerto = str(caja.get(col_precinto, "")).strip()
                            if val_actual_puerto in ("nan", "None"): val_actual_puerto = ""

                            # Buscar a quién pertenece este precinto actualmente
                            info_cliente = ""
                            if val_actual_puerto:
                                asociado = verificar_precinto_duplicado(df_clientes, val_actual_puerto)
                                if asociado is not None:
                                    info_cliente = f" (🟢 {asociado['Nº Cliente']} - {asociado['Nombre']})"
                                else:
                                    info_cliente = " (🔴 Libre/Sin cliente)"
                            
                            # Decidir columna de destino
                            target_col = col_p1 if i < mitad_puertos else col_p2
                            
                            with target_col:
                                nuevo_val_puerto = st.text_input(
                                    f"Puerto {i+1}{info_cliente}", 
                                    value=val_actual_puerto, 
                                    key=f"puerto_{caja_row_idx}_{i}"
                                )
                                inputs_puertos.append(nuevo_val_puerto)

                        submit_puertos = st.form_submit_button("💾 Guardar Puertos y Asignar Caja a Clientes", use_container_width=True)

                        if submit_puertos:
                            updates_caja = []
                            updates_clientes = []

                            for i in range(num_puertos):
                                val_actual = str(caja.get(f"Precinto {i+1}", "")).strip()
                                if val_actual in ("nan", "None"): val_actual = ""
                                nuevo_val = inputs_puertos[i].strip()

                                if val_actual != nuevo_val:
                                    letra = letras_columnas[i]
                                    updates_caja.append({"range": f"{letra}{caja_row_idx}", "values": [[nuevo_val]]})

                                if nuevo_val:
                                    cli_asociado = verificar_precinto_duplicado(df_clientes, nuevo_val)
                                    if cli_asociado is not None:
                                        cli_idx = cli_asociado.name + 2
                                        caja_actual_cli = str(cli_asociado.get("Caja NAP", "")).strip()
                                        if caja_actual_cli != nro_caja:
                                            updates_clientes.append({"range": f"M{cli_idx}", "values": [[nro_caja]]})

                            for i in range(num_puertos, 16):
                                val_actual = str(caja.get(f"Precinto {i+1}", "")).strip()
                                if val_actual and val_actual not in ("nan", "None"):
                                    letra = letras_columnas[i]
                                    updates_caja.append({"range": f"{letra}{caja_row_idx}", "values": [[""]]})

                            exito = True
                            
                            if updates_caja:
                                success_c, error_c = dm_batch_update_sheet(sheet_cajas, updates_caja)
                                if not success_c:
                                    st.error(f"❌ Error al guardar puertos de caja: {error_c}")
                                    exito = False
                            
                            if updates_clientes:
                                success_cl, error_cl = dm_batch_update_sheet(sheet_clientes, updates_clientes)
                                if not success_cl:
                                    st.error(f"❌ Error al actualizar cajas en clientes: {error_cl}")
                                    exito = False
                                else:
                                    st.success(f"✅ Se asignó automáticamente la Caja {nro_caja} a {len(updates_clientes)} cliente(s).")

                            if exito and (updates_caja or updates_clientes):
                                st.success("✅ Actualización completada correctamente.")
                                needs_refresh = True
                            elif not updates_caja and not updates_clientes:
                                st.info("ℹ️ No se detectaron cambios en los puertos.")

    # ==========================================
    # SECCION 3: BUSCADOR DE PRECINTOS
    # ==========================================
    st.markdown("---")
    st.subheader("🔎 Buscador Rápido de Precinto")
    
    busqueda_precinto = st.text_input(
        "Ingresá el N° de Precinto para ver su información:",
        placeholder="Ej: 4653289",
        key="search_precinto_global"
    ).strip()
    
    if busqueda_precinto:
        cliente_encontrado = verificar_precinto_duplicado(df_clientes, busqueda_precinto)
        
        if cliente_encontrado is not None:
            nro_cli = str(cliente_encontrado.get("Nº Cliente", "N/A"))
            nom_cli = str(cliente_encontrado.get("Nombre", "N/A"))
            plan_cli = str(cliente_encontrado.get("Plan", "S/D")).replace("nan", "S/D")
            
            # Limpieza del dato de la Caja NAP
            caja_cli = str(cliente_encontrado.get("Caja NAP", "Sin Caja Asignada")).replace("nan", "Sin Caja Asignada")
            if not caja_cli.strip() or caja_cli == "None":
                caja_cli = "Sin Caja Asignada"
            
            st.success("✅ Precinto encontrado y asociado a un cliente.")
            st.markdown(f"- **Nº de Cliente:** {nro_cli}")
            st.markdown(f"- **Nombre:** {nom_cli}")
            st.markdown(f"- **Plan:** {plan_cli}")
            st.markdown(f"- **Caja NAP:** {caja_cli}")
        else:
            st.warning(f"⚠️ El precinto '{busqueda_precinto}' no está asignado a ningún cliente en la base de datos.")

    return {"needs_refresh": needs_refresh}