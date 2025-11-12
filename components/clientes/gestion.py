# components/clientes/gestion.py
import streamlit as st
import pandas as pd
import uuid
from utils.date_utils import ahora_argentina, format_fecha, parse_fecha
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet as dm_batch_update_sheet
from config.settings import SECTORES_DISPONIBLES

# --- FUNCIONES HELPER NUEVAS ---
def _validar_telefono(telefono):
    """Acepta cualquier formato de teléfono (libre)."""
    # Teléfono completamente libre: cualquier combinación de caracteres es válida, incluyendo vacío
    return True, ""

def _valores_diferentes(valor1, valor2):
    """Compara valores de forma segura considerando strings y None"""
    str1 = str(valor1).strip() if valor1 is not None else ""
    str2 = str(valor2).strip() if valor2 is not None else ""
    return str1 != str2

def _obtener_indice_sector(sector_actual, sectores_disponibles):
    """Obtiene el índice seguro para el selectbox de sector"""
    if not sector_actual:
        return 0
        
    try:
        sector_str = str(sector_actual).strip()
        return sectores_disponibles.index(sector_str)
    except (ValueError, AttributeError):
        return 0

# --- FUNCIÓN PRINCIPAL CORREGIDA ---
def render_gestion_clientes(df_clientes, df_reclamos, sheet_clientes, user_role):
    """
    Muestra la sección de gestión de clientes
    
    Args:
        df_clientes (pd.DataFrame): DataFrame con los clientes
        df_reclamos (pd.DataFrame): DataFrame con los reclamos
        sheet_clientes: Objeto de conexión a la hoja de clientes
        user_role (str): Rol del usuario actual
    
    Returns:
        dict: Diccionario con estado de cambios y necesidad de recarga
    """
    st.subheader("🛠️ Gestión de Clientes")

    # Normalización de datos - CORREGIDO
    df_clientes["Nº Cliente"] = df_clientes["Nº Cliente"].astype(str).str.strip()

    cambios = False

    if user_role == 'admin':
        cambios = _mostrar_edicion_cliente(df_clientes, df_reclamos, sheet_clientes) or cambios
        st.markdown("---")
        cambios = _mostrar_nuevo_cliente(df_clientes, sheet_clientes) or cambios
    else:
        st.warning("🔒 Solo los administradores pueden editar información de clientes")

    st.markdown('</div>', unsafe_allow_html=True)
    return {
        "cambios": cambios,
        "needs_refresh": cambios
    }

# --- FUNCIÓN DE EDICIÓN MEJORADA ---
def _mostrar_edicion_cliente(df_clientes, df_reclamos, sheet_clientes):
    """Muestra el formulario para editar un cliente existente"""
    cambios = False

    # Filtrar solo clientes con número válido
    clientes_validos = df_clientes[
        df_clientes["Nº Cliente"].astype(str).str.strip() != ""
    ]
    
    if clientes_validos.empty:
        st.info("📝 No hay clientes registrados para editar")
        return cambios

    clientes_lista = clientes_validos["Nº Cliente"].astype(str).tolist()
    
    cliente_seleccionado = st.selectbox(
        "🔍 Seleccionar cliente", 
        clientes_lista,
        help="Elegí el cliente que querés editar"
    )

    if not cliente_seleccionado:
        return cambios

    # Búsqueda robusta del cliente
    cliente_actual = df_clientes[
        df_clientes["Nº Cliente"].astype(str).str.strip() == str(cliente_seleccionado).strip()
    ]
    
    if cliente_actual.empty:
        st.error(f"❌ No se encontró el cliente {cliente_seleccionado}")
        return cambios

    cliente_actual = cliente_actual.iloc[0]
    st.info(f"📋 Editando: Cliente {cliente_seleccionado} - {cliente_actual.get('Nombre', '')}")
    
    _mostrar_reclamos_cliente(cliente_seleccionado, df_reclamos)

    # Formulario de edición con índice seguro - CORREGIDO
    with st.form("form_editar_cliente"):
        col1, col2 = st.columns(2)

        with col1:
            # USAR FUNCIÓN HELPER PARA ÍNDICE SEGURO
            indice_sector = _obtener_indice_sector(
                cliente_actual.get("Sector"), 
                SECTORES_DISPONIBLES
            )
            
            nuevo_sector = st.selectbox(
                "🏢 Sector",
                SECTORES_DISPONIBLES,
                index=indice_sector
            )

            nuevo_nombre = st.text_input(
                "👤 Nombre *",
                value=cliente_actual.get("Nombre", ""),
                help="Campo obligatorio"
            )

            nueva_direccion = st.text_input(
                "📍 Dirección *",
                value=cliente_actual.get("Dirección", ""),
                help="Campo obligatorio"
            )

        with col2:
            nuevo_telefono = st.text_input(
                "📞 Teléfono",
                value=cliente_actual.get("Teléfono", ""),
                help="Opcional - formato libre"
            )

            nuevo_precinto = st.text_input(
                "🔒 Nº de Precinto",
                value=cliente_actual.get("N° de Precinto", ""),
                help="Opcional"
            )

        submitted = st.form_submit_button("💾 Guardar cambios")

    if submitted:
        # Validaciones
        if not nuevo_nombre.strip():
            st.error("❌ El nombre del cliente es obligatorio")
            return cambios
            
        if not nueva_direccion.strip():
            st.error("❌ La dirección del cliente es obligatoria")
            return cambios

        # Validación de teléfono: formato libre, no se bloquea
        _validar_telefono(nuevo_telefono)

        # Verificar consistencia con reclamos
        _verificar_cambios_desde_reclamos(
            cliente_seleccionado, 
            df_reclamos, 
            nueva_direccion.strip(), 
            nuevo_telefono.strip(), 
            nuevo_precinto.strip()
        )

        # USAR FUNCIÓN HELPER PARA COMPARACIÓN
        hubo_cambios = any([
            _valores_diferentes(nuevo_sector, cliente_actual.get("Sector")),
            _valores_diferentes(nuevo_nombre, cliente_actual.get("Nombre")),
            _valores_diferentes(nueva_direccion, cliente_actual.get("Dirección")),
            _valores_diferentes(nuevo_telefono, cliente_actual.get("Teléfono")),
            _valores_diferentes(nuevo_precinto, cliente_actual.get("N° de Precinto"))
        ])

        if not hubo_cambios:
            st.info("ℹ️ No se detectaron cambios en los datos del cliente.")
            return cambios

        # MOSTRAR PREVIEW DE CAMBIOS
        st.info("📋 Resumen de cambios:")
        cambios_data = {
            "Campo": ["Sector", "Nombre", "Dirección", "Teléfono", "Precinto"],
            "Valor anterior": [
                cliente_actual.get("Sector", ""),
                cliente_actual.get("Nombre", ""), 
                cliente_actual.get("Dirección", ""),
                cliente_actual.get("Teléfono", "") or "No tiene",
                cliente_actual.get("N° de Precinto", "") or "No tiene"
            ],
            "Valor nuevo": [
                nuevo_sector,
                nuevo_nombre.strip(),
                nueva_direccion.strip(),
                nuevo_telefono.strip() or "No tiene",
                nuevo_precinto.strip() or "No tiene"
            ]
        }
        
        df_cambios = pd.DataFrame(cambios_data)
        # Filtrar solo los campos que cambiaron
        df_cambios = df_cambios[df_cambios["Valor anterior"] != df_cambios["Valor nuevo"]]
        
        if not df_cambios.empty:
            st.table(df_cambios)
            # Guardar inmediatamente al enviar el formulario
            cambios = _actualizar_cliente(
                df_clientes[df_clientes["Nº Cliente"].astype(str) == str(cliente_seleccionado)],
                sheet_clientes,
                nuevo_sector,
                nuevo_nombre.strip(),
                nueva_direccion.strip(),
                nuevo_telefono.strip(),
                nuevo_precinto.strip()
            )
        else:
            st.info("ℹ️ No se detectaron cambios")
            return cambios

    return cambios

def _mostrar_reclamos_cliente(nro_cliente, df_reclamos):
    """Muestra los últimos reclamos del cliente"""
    df_reclamos_cliente = df_reclamos[
        df_reclamos["Nº Cliente"] == nro_cliente
    ].copy()
    
    df_reclamos_cliente["Fecha y hora"] = df_reclamos_cliente["Fecha y hora"].apply(
        parse_fecha
    )
    
    df_reclamos_cliente = df_reclamos_cliente.sort_values(
        "Fecha y hora", 
        ascending=False
    ).head(3)
    
    with st.expander("📄 Últimos reclamos"):
        for _, recl in df_reclamos_cliente.iterrows():
            st.markdown(
                f"📅 {format_fecha(recl['Fecha y hora'], '%d/%m/%Y')} | "
                f"📌 {recl['Tipo de reclamo']} | "
                f"👷 {recl.get('Técnico', 'N/A')}"
            )
    
    return False

def _verificar_cambios_desde_reclamos(nro_cliente, df_reclamos, nueva_direccion, nuevo_telefono, nuevo_precinto):
    """Verifica diferencias entre datos actuales y reclamos recientes con sugerencias"""
    df_reclamos_cliente = df_reclamos[
        df_reclamos["Nº Cliente"] == nro_cliente
    ].copy()
    
    if df_reclamos_cliente.empty:
        return False  # No hay reclamos para comparar
    
    cambios_detectados = []
    sugerencias = []
    
    campos = ["Dirección", "Teléfono", "N° de Precinto"]
    nuevos_valores = [nueva_direccion.strip(), nuevo_telefono.strip(), nuevo_precinto.strip()]
    
    for campo, nuevo_valor in zip(campos, nuevos_valores):
        if not nuevo_valor:  # Si el nuevo valor está vacío, skip
            continue
            
        # Obtener valores históricos (últimos 5 reclamos)
        valores_historicos = df_reclamos_cliente.head(5)[campo].dropna().astype(str).str.strip().unique()
        
        if len(valores_historicos) > 0 and nuevo_valor not in valores_historicos:
            cambios_detectados.append(campo)
            # Sugerir el valor más común histórico
            valor_comun = df_reclamos_cliente[campo].mode()
            if not valor_comun.empty:
                sugerencias.append(f"**{campo}**: Históricamente suele ser '{valor_comun.iloc[0]}'")
    
    if cambios_detectados:
        st.warning("⚠️ **Posible inconsistencia detectada**")
        st.info(f"Los campos {', '.join(cambios_detectados)} difieren de los registrados en reclamos recientes.")
        
        if sugerencias:
            with st.expander("💡 Sugerencias basadas en histórico"):
                for sugerencia in sugerencias:
                    st.markdown(sugerencia)
        
        st.markdown("**Verificá que los datos sean correctos antes de guardar.**")
    
    return bool(cambios_detectados)

def _actualizar_cliente(cliente_row, sheet_clientes, nuevo_sector, nuevo_nombre, 
                       nueva_direccion, nuevo_telefono, nuevo_precinto):
    """Actualiza los datos del cliente en la hoja de cálculo"""
    
    # VALIDACIÓN 1: Verificar que el cliente existe
    if cliente_row.empty:
        st.error("❌ Error: No se pudo encontrar el cliente para actualizar")
        return False
        
    # VALIDACIÓN 2: Verificar que hay solo un cliente (evitar duplicados)
    if len(cliente_row) > 1:
        st.warning("⚠️ Advertencia: Se encontraron múltiples clientes con el mismo número. Se actualizará el primero.")
    
    # Tomar el primer cliente
    cliente_actual = cliente_row.iloc[0]
    
    with st.spinner("Actualizando cliente..."):
        try:
            # VALIDACIÓN 3: Verificar que tenemos un índice válido
            if cliente_row.index.empty:
                st.error("❌ Error: No se pudo determinar la posición del cliente en la hoja")
                return False
                
            # Nos aseguramos que el índice sea numérico y válido para Google Sheets
            index = int(cliente_row.index[0]) + 2

            # Convertimos todos los valores a string para evitar problemas
            updates = [
                {"range": f"B{index}", "values": [[str(nuevo_sector)]]},
                {"range": f"C{index}", "values": [[str(nuevo_nombre).upper()]]},
                {"range": f"D{index}", "values": [[str(nueva_direccion).upper()]]},
                {"range": f"E{index}", "values": [[str(nuevo_telefono)]]},
                {"range": f"F{index}", "values": [[str(nuevo_precinto)]]},
                {"range": f"H{index}", "values": [[format_fecha(ahora_argentina())]]}
            ]

            # Ejecutar actualización por lotes con manejo de errores
            success, error = dm_batch_update_sheet(sheet_clientes, updates)

            if not success:
                # Fallback: intentar actualización individual celda por celda
                errores = []
                for upd in updates:
                    try:
                        result, err = api_manager.safe_sheet_operation(
                            sheet_clientes.update, upd["range"], upd["values"]
                        )
                        if err:
                            errores.append(f"{upd['range']}: {err}")
                    except Exception as e:
                        errores.append(f"{upd['range']}: {str(e)}")

                if errores:
                    st.error("❌ Error al actualizar algunas celdas:")
                    for er in errores:
                        st.write(f"- {er}")
                    return False
                else:
                    success = True

            if success:
                st.success("✅ Cliente actualizado correctamente.")
                
                if 'notification_manager' in st.session_state:
                    num_cliente = str(cliente_actual['Nº Cliente'])
                    nombre_cliente = str(nuevo_nombre).upper()
                    mensaje = f"✏️ Se actualizaron los datos del cliente N° {num_cliente} - {nombre_cliente}."
                    st.session_state.notification_manager.add(
                        notification_type="cliente_actualizado",
                        message=mensaje,
                        user_target="all"
                    )
                return True

        except ValueError:
            st.error("❌ Error: Índice del cliente no es válido")
            return False
        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")
            return False

def _mostrar_nuevo_cliente(df_clientes, sheet_clientes):
    """Muestra el formulario para crear nuevo cliente"""
    st.subheader("🆕 Cargar nuevo cliente")
    cambios = False

    with st.form("form_nuevo_cliente", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            nuevo_nro = st.text_input(
                "🔢 N° de Cliente (nuevo)", 
                placeholder="Número único"
            ).strip()
            
            nuevo_sector = st.selectbox(
                "🔢 Sector (1-17)",
                options=SECTORES_DISPONIBLES,
                index=0,
                key="new_sector"
            )
        
        with col2:
            nuevo_nombre = st.text_input(
                "👤 Nombre", 
                placeholder="Nombre completo"
            )
            
            nueva_direccion = st.text_input(
                "📍 Dirección", 
                placeholder="Dirección completa"
            )

        nuevo_telefono = st.text_input(
            "📞 Teléfono", 
            placeholder="Número de contacto",
            help="Opcional - formato libre"
        )
        
        nuevo_precinto = st.text_input(
            "🔒 N° de Precinto (opcional)", 
            placeholder="Número de precinto",
            help="Opcional"
        )

        guardar_cliente = st.form_submit_button(
            "💾 Guardar nuevo cliente", 
            use_container_width=True
        )

    if guardar_cliente:
        cambios = _guardar_nuevo_cliente(
            df_clientes, sheet_clientes,
            nuevo_nro, nuevo_sector, nuevo_nombre,
            nueva_direccion, nuevo_telefono, nuevo_precinto
        )

    return cambios

def _guardar_nuevo_cliente(df_clientes, sheet_clientes, nuevo_nro, nuevo_sector, 
                          nuevo_nombre, nueva_direccion, nuevo_telefono, nuevo_precinto):
    """Guarda un nuevo cliente en la hoja de cálculo"""
    
    # Validación de campos obligatorios (teléfono es opcional)
    if not nuevo_nombre.strip():
        st.error("⚠️ El nombre del cliente es obligatorio.")
        return False
        
    if not nueva_direccion.strip():
        st.error("⚠️ La dirección del cliente es obligatoria.")
        return False
    
    # Validar que el número de cliente no esté vacío
    if not nuevo_nro.strip():
        st.error("⚠️ El número de cliente no puede estar vacío.")
        return False
        
    # Validar que el número de cliente sea único (comparación robusta)
    clientes_existentes = df_clientes["Nº Cliente"].astype(str).str.strip()
    if str(nuevo_nro).strip() in clientes_existentes.values:
        st.error("⚠️ Este número de cliente ya existe. Usá otro número.")
        return False

    # Validar formato del teléfono (si se ingresó)
    # Teléfono de formato libre: no se bloquea por formato
    _validar_telefono(nuevo_telefono)
    # No return False, sin advertencias

    with st.spinner("Guardando nuevo cliente..."):
        try:
            nuevo_id = str(uuid.uuid4())

            # Preparar datos (teléfono puede estar vacío)
            nueva_fila = [
                nuevo_nro.strip(), 
                str(nuevo_sector),
                nuevo_nombre.strip().upper(),
                nueva_direccion.strip().upper(), 
                nuevo_telefono.strip(),  # Puede estar vacío
                nuevo_precinto.strip(), 
                nuevo_id,
                format_fecha(ahora_argentina())
            ]

            success, error = api_manager.safe_sheet_operation(
                sheet_clientes.append_row,
                nueva_fila
            )

            if success:
                st.success("✅ Nuevo cliente agregado correctamente.")
                st.info(f"📋 Cliente: {nuevo_nombre.strip().upper()} - N° {nuevo_nro.strip()}")

                if 'notification_manager' in st.session_state:
                    mensaje = f"🆕 Se agregó el cliente N° {nuevo_nro.strip()} - {nuevo_nombre.strip().upper()} al sistema."
                    st.session_state.notification_manager.add(
                        notification_type="cliente_nuevo",
                        message=mensaje,
                        user_target="all"
                    )

                return True
            else:
                st.error(f"❌ Error al guardar: {error}")
                return False

        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")
            return False
