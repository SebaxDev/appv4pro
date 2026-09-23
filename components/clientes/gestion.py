# components/clientes/gestion.py
import streamlit as st
import pandas as pd
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet as dm_batch_update_sheet
from utils.date_utils import ahora_argentina, format_fecha
from components.reclamos.nuevo import generar_id_unico
from config.settings import SECTORES_DISPONIBLES, PLANES_DISPONIBLES, DEBUG_MODE


def render_gestion_clientes(df_clientes, df_reclamos, sheet_clientes, user_role, df_cajas=None, sheet_cajas=None):
    """
    Modulo de busqueda, creacion y edicion de clientes + Cajas NAP.
    """
    needs_refresh = False

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

                with col2:
                    nuevo_telefono = st.text_input("📞 Teléfono", placeholder="Número de contacto")
                    nuevo_sector = st.selectbox("🔢 Sector*", options=SECTORES_DISPONIBLES, index=0)

                nuevo_precinto = st.text_input("🔒 N° de Precinto (opcional)", placeholder="Número de precinto")
                nuevo_plan = st.selectbox("📺 Plan", options=PLANES_DISPONIBLES, index=0)

                submit_crear = st.form_submit_button("✅ Crear Nuevo Cliente", use_container_width=True)

                if submit_crear:
                    if not nuevo_nombre.strip() or not nuevo_direccion.strip():
                        st.error("⚠️ El Nombre y la Dirección son campos obligatorios.")
                    else:
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
                                nuevo_plan
                            ]

                            success, error = api_manager.safe_sheet_operation(
                                sheet_clientes.append_row,
                                fila_cliente
                            )

                            if success:
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

            col_r1, col_r2, col_r3, col_r4 = st.columns(4)
            with col_r1:
                st.markdown(f"**👤 Nombre:** {cliente.get('Nombre', 'N/A')}")
            with col_r2:
                st.markdown(f"**📍 Dirección:** {cliente.get('Dirección', 'N/A')}")
            with col_r3:
                st.markdown(f"**📞 Teléfono:** {cliente.get('Teléfono', 'N/A')}")
            with col_r4:
                st.markdown(f"**📺 Plan:** {cliente.get('Plan', 'Sin plan')}")

            st.markdown("---")

            # ACORDEON 1: EDITAR DATOS PRINCIPALES
            with st.expander("✏️ Editar Datos del Cliente (Sector, Nombre, Dirección, Teléfono, Plan)"):
                with st.form("form_editar_datos"):
                    edit_col1, edit_col2 = st.columns(2)

                    with edit_col1:
                        edit_nombre = st.text_input("👤 Nombre", value=cliente.get("Nombre", ""))
                        edit_direccion = st.text_input("📍 Dirección", value=cliente.get("Dirección", ""))

                    with edit_col2:
                        edit_telefono = st.text_input("📞 Teléfono", value=str(cliente.get("Teléfono", "")))
                        sector_actual = str(cliente.get("Sector", "1")).strip()
                        try:
                            sector_idx = SECTORES_DISPONIBLES.index(sector_actual) if sector_actual in SECTORES_DISPONIBLES else 0
                        except ValueError:
                            sector_idx = 0
                        edit_sector = st.selectbox("🔢 Sector", options=SECTORES_DISPONIBLES, index=sector_idx)

                        plan_actual = str(cliente.get("Plan", "")).strip()
                        try:
                            plan_idx = PLANES_DISPONIBLES.index(plan_actual) if plan_actual in PLANES_DISPONIBLES else 0
                        except ValueError:
                            plan_idx = 0
                        edit_plan = st.selectbox("📺 Plan", options=PLANES_DISPONIBLES, index=plan_idx)

                    submit_edit = st.form_submit_button("💾 Guardar Cambios en Datos", use_container_width=True)

                    if submit_edit:
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

                        if updates:
                            fecha_mod = format_fecha(ahora_argentina())
                            updates.append({"range": f"H{row_idx}", "values": [[fecha_mod]]})
                            success, error = dm_batch_update_sheet(sheet_clientes, updates)
                            if success:
                                st.success("✅ Datos del cliente actualizados correctamente.")
                                needs_refresh = True
                            else:
                                st.error(f"❌ Error al actualizar datos: {error}")
                        else:
                            st.info("ℹ️ No se detectaron cambios en los datos del cliente.")

            # ACORDEON 2: GESTION DE PRECINTO
            with st.expander("🔒 Gestión de Precinto"):
                precinto = str(cliente.get("N° de Precinto", "")).strip()
                has_precinto = precinto not in ("", "nan", "None")

                if has_precinto:
                    st.markdown(f"**Precinto actual:** `{precinto}`")
                    with st.form("form_editar_precinto"):
                        new_precinto = st.text_input("Modificar N° de Precinto", value=precinto)
                        submit_precinto = st.form_submit_button("💾 Actualizar Precinto")

                        if submit_precinto:
                            if not new_precinto.strip():
                                st.error("❌ El precinto no puede estar vacío.")
                            elif new_precinto.strip() != precinto:
                                updates = [{"range": f"F{row_idx}", "values": [[new_precinto.strip()]]}]
                                success, error = dm_batch_update_sheet(sheet_clientes, updates)
                                if success:
                                    st.success("✅ Precinto actualizado correctamente.")
                                    needs_refresh = True
                                else:
                                    st.error(f"❌ Error al guardar: {error}")
                            else:
                                st.info("ℹ️ El precinto es el mismo, sin cambios.")
                else:
                    st.warning("Este cliente no tiene precinto registrado.")
                    with st.form("form_cargar_precinto"):
                        new_precinto = st.text_input("Ingresar N° de Precinto")
                        submit_precinto = st.form_submit_button("💾 Guardar Precinto")

                        if submit_precinto:
                            if not new_precinto.strip():
                                st.error("❌ Debés ingresar un número de precinto.")
                            else:
                                updates = [{"range": f"F{row_idx}", "values": [[new_precinto.strip()]]}]
                                success, error = dm_batch_update_sheet(sheet_clientes, updates)
                                if success:
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

                    with st.form("form_editar_geo"):
                        edit_lat = st.text_input("Latitud", value=lat)
                        edit_lon = st.text_input("Longitud", value=lon)
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

                    with st.form("form_cargar_geo"):
                        val_lat = lat if lat not in ("nan", "None", "") else default_lat
                        val_lon = lon if lon not in ("nan", "None", "") else default_lon

                        new_lat = st.text_input("Latitud", value=val_lat)
                        new_lon = st.text_input("Longitud", value=val_lon)
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

            default_cliente_ref = nro_cliente if nro_cliente else ""

            if caja_data.empty:
                # ==========================================
                # LA CAJA NO EXISTE - CREACION
                # ==========================================
                st.info("ℹ️ Esta caja NAP no existe en la base. Completá los datos para crearla.")

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

                    nuevo_obs_caja = st.text_input("📝 Observación", placeholder="Observaciones (opcional)")
                    nuevo_cliente_ref = st.text_input(
                        "👤 Cliente de Referencia",
                        value=default_cliente_ref,
                        placeholder="Nº de cliente de referencia"
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
                                    nuevo_cliente_ref.strip()
                                ]

                                success, error = api_manager.safe_sheet_operation(
                                    sheet_cajas.append_row,
                                    fila_caja
                                )

                                if success:
                                    st.success(f"✅ Caja NAP `{nro_caja}` creada correctamente.")
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

                col_cr1, col_cr2, col_cr3, col_cr4 = st.columns(4)
                with col_cr1:
                    st.markdown(f"**🔢 Sector:** {caja.get('Sector', 'N/A')}")
                with col_cr2:
                    st.markdown(f"**🏘️ Barrio:** {caja.get('Barrio', 'N/A')}")
                with col_cr3:
                    st.markdown(f"**👤 Cliente Ref:** {caja.get('Cliente de Referencia', 'N/A')}")
                with col_cr4:
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
                with st.expander("✏️ Editar Datos de la Caja NAP (Sector, Barrio, Observación, Cliente Ref)"):
                    with st.form("form_editar_caja"):
                        edit_ccol1, edit_ccol2 = st.columns(2)

                        with edit_ccol1:
                            sector_actual_caja = str(caja.get("Sector", "1")).strip()
                            try:
                                sector_idx_caja = SECTORES_DISPONIBLES.index(sector_actual_caja) if sector_actual_caja in SECTORES_DISPONIBLES else 0
                            except ValueError:
                                sector_idx_caja = 0
                            edit_sector_caja = st.selectbox(
                                "🔢 Sector", options=SECTORES_DISPONIBLES, index=sector_idx_caja, key="caja_sector_edit"
                            )
                            edit_barrio = st.text_input(
                                "🏘️ Barrio", value=str(caja.get("Barrio", "")), key="caja_barrio_edit"
                            )

                        with edit_ccol2:
                            edit_obs_caja = st.text_input(
                                "📝 Observación", value=str(caja.get("Observacion", "")), key="caja_obs_edit"
                            )
                            edit_cliente_ref = st.text_input(
                                "👤 Cliente de Referencia",
                                value=str(caja.get("Cliente de Referencia", "")),
                                key="caja_ref_edit"
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

                            if str(caja.get("Cliente de Referencia", "")).strip() != edit_cliente_ref.strip():
                                updates.append({"range": f"G{caja_row_idx}", "values": [[edit_cliente_ref.strip()]]})

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
                with st.expander("🗺️ Georreferencia de Caja NAP"):
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

                        with st.form("form_editar_geo_caja"):
                            edit_lat_caja = st.text_input("Latitud", value=lat_caja, key="caja_lat_edit")
                            edit_lon_caja = st.text_input("Longitud", value=lon_caja, key="caja_lon_edit")
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

                        with st.form("form_cargar_geo_caja"):
                            val_lat_caja = lat_caja if lat_caja not in ("nan", "None", "") else default_lat_caja
                            val_lon_caja = lon_caja if lon_caja not in ("nan", "None", "") else default_lon_caja

                            new_lat_caja = st.text_input("Latitud", value=val_lat_caja, key="caja_lat_new_geo")
                            new_lon_caja = st.text_input("Longitud", value=val_lon_caja, key="caja_lon_new_geo")
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

    return {"needs_refresh": needs_refresh}