# components/clientes/gestion.py
import streamlit as st
import pandas as pd
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet as dm_batch_update_sheet

def render_gestion_clientes(df_clientes, df_reclamos, sheet_clientes, user_role):
    """
    Módulo de búsqueda de clientes por número.
    - Si existe y tiene georef: muestra datos + link a Google Maps.
    - Si existe y NO tiene georef: muestra datos + campos para cargar coordenadas.
    - Si no existe: muestra "Cliente No Existe".
    """
    st.subheader("🔍 Búsqueda de Clientes")

    # Normalizar Nº Cliente para la búsqueda
    df_clientes["Nº Cliente"] = df_clientes["Nº Cliente"].astype(str).str.strip()

    nro_cliente = st.text_input(
        "Ingresá el Número de Cliente", 
        placeholder="Ej: 9944",
        key="search_nro_cliente"
    )

    if nro_cliente.strip():
        nro_cliente = nro_cliente.strip()
        
        # Buscar cliente
        cliente_data = df_clientes[df_clientes["Nº Cliente"] == nro_cliente]

        if cliente_data.empty:
            # ==========================================
            # CASO 3: El cliente NO EXISTE
            # ==========================================
            st.warning("Cliente No Existe")
            
        else:
            # ==========================================
            # CASO 1 y 2: El cliente SÍ EXISTE
            # ==========================================
            cliente = cliente_data.iloc[0]
            
            # Mostrar datos básicos
            st.markdown(f"**👤 Nombre:** {cliente.get('Nombre', 'N/A')}")
            st.markdown(f"**📍 Dirección:** {cliente.get('Dirección', 'N/A')}")
            st.markdown(f"**📞 Teléfono:** {cliente.get('Teléfono', 'N/A')}")
            
            st.markdown("---")
            
            # Verificar Geolocalización (Columnas J y K -> Latitud y Longitud)
            lat = str(cliente.get("Latitud", "")).strip()
            lon = str(cliente.get("Longitud", "")).strip()
            
            has_geo = False
            if lat not in ("", "nan", "None") and lon not in ("", "nan", "None"):
                try:
                    # Validamos que sean coordenadas parseables para Google Maps
                    float(lat.replace(',', '.'))
                    float(lon.replace(',', '.'))
                    has_geo = True
                except (ValueError, TypeError):
                    has_geo = False

            if has_geo:
                # ==========================================
                # CASO 1: TIENE Georreferencia -> Link Maps
                # ==========================================
                st.success("✅ Georreferencia registrada")
                # Usamos el texto original tal cual está en la columna
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                st.markdown(f"🗺️ [Ver ubicación en Google Maps]({maps_url})")
                
            else:
                # ==========================================
                # CASO 2: NO TIENE Georreferencia -> Cargarla
                # ==========================================
                st.info("ℹ️ Este cliente no tiene georreferencia cargada. Ingresá las coordenadas:")
                
                # Prefijos por defecto de la zona para acelerar la carga
                default_lat = "-26."
                default_lon = "-59."

                with st.form("form_cargar_geo"):
                    # Si había datos previos (aunque sean inválidos), mostrarlos. Si no, poner el prefijo.
                    val_lat = lat if lat not in ("nan", "None", "") else default_lat
                    val_lon = lon if lon not in ("nan", "None", "") else default_lon

                    new_lat = st.text_input(
                        "Latitud (Columna J)", 
                        value=val_lat
                    )
                    new_lon = st.text_input(
                        "Longitud (Columna K)", 
                        value=val_lon
                    )
                    submitted = st.form_submit_button("💾 Guardar Coordenadas")
                    
                    if submitted:
                        if not new_lat.strip() or not new_lon.strip():
                            st.error("❌ Debés completar ambos campos para guardar.")
                        else:
                            try:
                                # Validamos que sirvan para Google Maps (aceptamos coma o punto decimal)
                                float(new_lat.strip().replace(',', '.'))
                                float(new_lon.strip().replace(',', '.'))
                                
                                # Fila en Google Sheets (índice de pandas + 2 por header y base-1)
                                row_idx = cliente.name + 2
                                
                                # Guardar EXACTAMENTE como texto sin formato
                                updates = [
                                    {"range": f"J{row_idx}", "values": [[new_lat.strip()]]},
                                    {"range": f"K{row_idx}", "values": [[new_lon.strip()]]}
                                ]
                                
                                success, error = dm_batch_update_sheet(sheet_clientes, updates)
                                
                                if success:
                                    st.success("✅ Georreferencia guardada correctamente como texto.")
                                    return {"needs_refresh": True}
                                else:
                                    st.error(f"❌ Error al guardar en la hoja: {error}")
                                    
                            except ValueError:
                                st.error("❌ Las coordenadas deben ser valores numéricos (ej: -26.123456 o -26,123456).")

    return {"needs_refresh": False}