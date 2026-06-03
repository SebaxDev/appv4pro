# components/clientes/gestion.py
import streamlit as st
import pandas as pd
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet as dm_batch_update_sheet
from utils.date_utils import ahora_argentina, format_fecha
from components.reclamos.nuevo import generar_id_unico
from config.settings import SECTORES_DISPONIBLES, DEBUG_MODE

def render_gestion_clientes(df_clientes, df_reclamos, sheet_clientes, user_role):
    """
    Módulo de búsqueda, creación y edición de clientes.
    - Si no existe: permite crearlo con todos sus datos.
    - Si existe: permite editar datos principales, cargar precinto y georreferencia.
    """
    st.subheader("🔍 Búsqueda y Gestión de Clientes")

    # Normalizar Nº Cliente para la búsqueda
    df_clientes["Nº Cliente"] = df_clientes["Nº Cliente"].astype(str).str.strip()

    nro_cliente = st.text_input(
        "Ingresá el Número de Cliente", 
        placeholder="Ej: 9944",
        key="search_nro_cliente"
    ).strip()

    if not nro_cliente:
        return {"needs_refresh": False}

    # Buscar cliente
    cliente_data = df_clientes[df_clientes["Nº Cliente"] == nro_cliente]

    if cliente_data.empty:
        # ==========================================
        # CASO 1: EL CLIENTE NO EXISTE - CREACIÓN
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
            
            submit_crear = st.form_submit_button("✅ Crear Nuevo Cliente", use_container_width=True)
            
            if submit_crear:
                if not nuevo_nombre.strip() or not nuevo_direccion.strip():
                    st.error("⚠️ El Nombre y la Dirección son campos obligatorios.")
                else:
                    try:
                        id_cliente = generar_id_unico()
                        ultima_mod = format_fecha(ahora_argentina())
                        
                        # Estructura exacta del tab Clientes (A a K)
                        fila_cliente = [
                            nro_cliente,                   # A: Nº Cliente
                            nuevo_sector,                  # B: Sector
                            nuevo_nombre.upper().strip(),  # C: Nombre
                            nuevo_direccion.upper().strip(),# D: Dirección
                            nuevo_telefono.strip(),        # E: Teléfono
                            nuevo_precinto.strip(),        # F: N° de Precinto
                            id_cliente,                    # G: ID Cliente
                            ultima_mod,                    # H: Última Modificación
                            "",                            # I: Anotaciones (vacío por defecto)
                            "",                            # J: Latitud
                            ""                             # K: Longitud
                        ]
                        
                        success, error = api_manager.safe_sheet_operation(
                            sheet_clientes.append_row,
                            fila_cliente
                        )
                        
                        if success:
                            st.success(f"✅ Cliente {nro_cliente} creado correctamente (ID: {id_cliente}).")
                            st.cache_data.clear()
                            return {"needs_refresh": True}
                        else:
                            st.error(f"❌ Error al crear el cliente: {error}")
                            
                    except Exception as e:
                        st.error(f"❌ Error inesperado: {str(e)}")
                        if DEBUG_MODE:
                            st.exception(e)

    else:
        # ==========================================
        # CASO 2: EL CLIENTE SÍ EXISTE - EDICIÓN
        # ==========================================
        cliente = cliente_data.iloc[0]
        row_idx = cliente.name + 2  # Fila en Google Sheets

        # Resumen rápido superior
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            st.markdown(f"**👤 Nombre:** {cliente.get('Nombre', 'N/A')}")
        with col_r2:
            st.markdown(f"**📍 Dirección:** {cliente.get('Dirección', 'N/A')}")
        with col_r3:
            st.markdown(f"**📞 Teléfono:** {cliente.get('Teléfono', 'N/A')}")

        st.markdown("---")

        # ------------------------------------------
        # ACORDEÓN 1: EDITAR DATOS PRINCIPALES
        # ------------------------------------------
        with st.expander("✏️ Editar Datos del Cliente (Sector, Nombre, Dirección, Teléfono)"):
            with st.form("form_editar_datos"):
                edit_col1, edit_col2 = st.columns(2)
                
                with edit_col1:
                    edit_nombre = st.text_input("👤 Nombre", value=cliente.get("Nombre", ""))
                    edit_direccion = st.text_input("📍 Dirección", value=cliente.get("Dirección", ""))
                
                with edit_col2:
                    edit_telefono = st.text_input("📞 Teléfono", value=str(cliente.get("Teléfono", "")))
                    # Pre-seleccionar el sector actual en el selectbox
                    sector_actual = str(cliente.get("Sector", "1")).strip()
                    try:
                        sector_idx = SECTORES_DISPONIBLES.index(sector_actual) if sector_actual in SECTORES_DISPONIBLES else 0
                    except ValueError:
                        sector_idx = 0
                    edit_sector = st.selectbox("🔢 Sector", options=SECTORES_DISPONIBLES, index=sector_idx)

                submit_edit = st.form_submit_button("💾 Guardar Cambios en Datos", use_container_width=True)

                if submit_edit:
                    updates = []
                    # Comparar y preparar actualizaciones (todo a UPPER y strip como en nuevo.py)
                    if str(cliente.get("Sector", "")).strip() != edit_sector:
                        updates.append({"range": f"B{row_idx}", "values": [[edit_sector]]})
                    
                    if str(cliente.get("Nombre", "")).strip() != edit_nombre.upper().strip():
                        updates.append({"range": f"C{row_idx}", "values": [[edit_nombre.upper().strip()]]})
                    
                    if str(cliente.get("Dirección", "")).strip() != edit_direccion.upper().strip():
                        updates.append({"range": f"D{row_idx}", "values": [[edit_direccion.upper().strip()]]})
                    
                    if str(cliente.get("Teléfono", "")).strip() != edit_telefono.strip():
                        updates.append({"range": f"E{row_idx}", "values": [[edit_telefono.strip()]]})

                    if updates:
                        # Siempre actualizamos la fecha de última modificación (Columna H)
                        fecha_mod = format_fecha(ahora_argentina())
                        updates.append({"range": f"H{row_idx}", "values": [[fecha_mod]]})
                        
                        success, error = dm_batch_update_sheet(sheet_clientes, updates)
                        if success:
                            st.success("✅ Datos del cliente actualizados correctamente.")
                            st.cache_data.clear()
                            return {"needs_refresh": True}
                        else:
                            st.error(f"❌ Error al actualizar datos: {error}")
                    else:
                        st.info("ℹ️ No se detectaron cambios en los datos del cliente.")

        # ------------------------------------------
        # ACORDEÓN 2: GESTIÓN DE PRECINTO (COLUMNA F)
        # ------------------------------------------
        with st.expander("🔒 Gestión de Precinto"):
            precinto = str(cliente.get("N° de Precinto", "")).strip()
            has_precinto = precinto not in ("", "nan", "None")
            
            if has_precinto:
                st.markdown(f"**Precinto actual:** `{precinto}`")
                # Permitir cambiarlo si está mal cargado
                with st.form("form_editar_precinto"):
                    new_precinto = st.text_input("Modificar N° de Precinto", value=precinto)
                    submit_precinto = st.form_submit_button("💾 Actualizar Precinto")
                    
                    if submit_precinto:
                        if not new_precinto.strip():
                            st.error("❌ El precinto no puede estar vacío. Si desea eliminarlo, hágalo desde la planilla.")
                        elif new_precinto.strip() != precinto:
                            updates = [{"range": f"F{row_idx}", "values": [[new_precinto.strip()]]}]
                            success, error = dm_batch_update_sheet(sheet_clientes, updates)
                            if success:
                                st.success("✅ Precinto actualizado correctamente.")
                                return {"needs_refresh": True}
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
                                return {"needs_refresh": True}
                            else:
                                st.error(f"❌ Error al guardar en la hoja: {error}")

        # ------------------------------------------
        # ACORDEÓN 3: GEOREFERENCIA (COLUMNAS J y K)
        # ------------------------------------------
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
                
                # Permitir editar si está mal cargada
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
                                return {"needs_refresh": True}
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
                                    return {"needs_refresh": True}
                                else:
                                    st.error(f"❌ Error al guardar en la hoja: {error}")
                                    
                            except ValueError:
                                st.error("❌ Las coordenadas deben ser valores numéricos (ej: -26.123456 o -26,123456).")

    return {"needs_refresh": False}