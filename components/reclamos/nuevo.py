# components/reclamos/nuevo.py
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.date_utils import ahora_argentina, format_fecha
from utils.api_manager import api_manager
from utils.data_manager import batch_update_sheet
from config.settings import (
    SECTORES_DISPONIBLES,
    TIPOS_RECLAMO,
    DEBUG_MODE
)

# --- FUNCIONES HELPER NUEVAS ---
def _normalizar_datos(df_clientes, df_reclamos, nro_cliente):
    """Normaliza datos solo cuando es necesario"""
    if not nro_cliente:
        return df_clientes, df_reclamos
    
    df_clientes_normalizado = df_clientes.copy()
    df_reclamos_normalizado = df_reclamos.copy()
    
    df_clientes_normalizado["Nº Cliente"] = df_clientes_normalizado["Nº Cliente"].astype(str).str.strip()
    df_reclamos_normalizado["Nº Cliente"] = df_reclamos_normalizado["Nº Cliente"].astype(str).str.strip()
    
    return df_clientes_normalizado, df_reclamos_normalizado

def _validar_y_normalizar_sector(sector_input):
    """Valida y normaliza el sector ingresado"""
    try:
        sector_limpio = str(sector_input).strip()
        sector_num = int(sector_limpio)
        
        if 1 <= sector_num <= 17:
            return str(sector_num), None
        else:
            return None, f"⚠️ El sector debe estar entre 1 y 17. Se ingresó: {sector_num}"
            
    except ValueError:
        return None, f"⚠️ El sector debe ser un número válido. Se ingresó: {sector_input}"

def _verificar_reclamos_activos(nro_cliente, df_reclamos):
    """Verifica reclamos activos de forma eficiente"""
    if nro_cliente not in df_reclamos["Nº Cliente"].values:
        return pd.DataFrame()
    
    reclamos_cliente = df_reclamos[df_reclamos["Nº Cliente"] == nro_cliente]
    
    # Convertir estados a minúsculas para comparación case-insensitive
    estados_activos = ["pendiente", "en curso"]
    reclamos_activos = reclamos_cliente[
        reclamos_cliente["Estado"].str.strip().str.lower().isin(estados_activos) |
        (reclamos_cliente["Tipo de reclamo"].str.strip().str.lower() == "desconexion a pedido")
    ]
    
    return reclamos_activos

def generar_id_unico():
    """Genera un ID único para reclamos"""
    import uuid
    return str(uuid.uuid4())[:8].upper()

def _validar_campos_obligatorios(nombre, direccion, sector, tipo_reclamo, atendido_por):
    """Valida campos obligatorios y devuelve errores"""
    errores = []
    
    if not nombre.strip():
        errores.append("Nombre")
    
    if not direccion.strip():
        errores.append("Dirección")
    
    if not str(sector).strip():
        errores.append("Sector")
    
    if not tipo_reclamo.strip():
        errores.append("Tipo de reclamo")
    
    if not atendido_por.strip():
        errores.append("Atendido por")
    
    return errores

def _reset_formulario():
    """Resetea completamente el estado del formulario"""
    if 'nuevo_reclamo' in st.session_state:
        st.session_state.nuevo_reclamo = {
            'nro_cliente': '',
            'cliente_existente': None,
            'formulario_bloqueado': False,
            'reclamo_guardado': False,
            'cliente_nuevo': False
        }
    # Limpiar también el input del número de cliente
    if 'nro_cliente_input' in st.session_state:
        st.session_state.nro_cliente_input = ''

# --- FUNCIÓN PRINCIPAL OPTIMIZADA ---
def render_nuevo_reclamo(df_reclamos, df_clientes, sheet_reclamos, sheet_clientes, current_user=None):
    """
    Muestra la sección para cargar nuevos reclamos
    """
    st.subheader("📝 Cargar nuevo reclamo")

    # Inicializar estado en session_state
    if 'nuevo_reclamo' not in st.session_state:
        st.session_state.nuevo_reclamo = {
            'nro_cliente': '',
            'cliente_existente': None,
            'formulario_bloqueado': False,
            'reclamo_guardado': False,
            'cliente_nuevo': False
        }

    estado = st.session_state.nuevo_reclamo

    # Input de número de cliente
    nro_cliente_actual = st.text_input(
        "🔢 N° de Cliente", 
        value=estado['nro_cliente'],
        placeholder="Ingresa el número de cliente",
        key="nro_cliente_input"
    ).strip()

    # Actualizar estado si cambió el número de cliente
    if nro_cliente_actual != estado['nro_cliente']:
        estado['nro_cliente'] = nro_cliente_actual
        estado['cliente_existente'] = None
        estado['cliente_nuevo'] = False
        estado['formulario_bloqueado'] = False
        estado['reclamo_guardado'] = False

    if estado['nro_cliente']:
        # Normalizar datos solo cuando sea necesario
        df_clientes_norm, df_reclamos_norm = _normalizar_datos(
            df_clientes, df_reclamos, estado['nro_cliente']
        )
        
        # Buscar cliente
        match = df_clientes_norm[df_clientes_norm["Nº Cliente"] == estado['nro_cliente']]
        
        if not match.empty:
            estado['cliente_existente'] = match.iloc[0].to_dict()
            st.success("✅ Cliente reconocido, datos auto-cargados.")

        else:
            estado['cliente_nuevo'] = True
            st.info("ℹ️ Este cliente no existe en la base y se cargará como cliente nuevo.")
        
        # Verificar reclamos activos
        reclamos_activos = _verificar_reclamos_activos(estado['nro_cliente'], df_reclamos_norm)
        
        if not reclamos_activos.empty:
            estado['formulario_bloqueado'] = True
            st.error("⚠️ Este cliente ya tiene un reclamo sin resolver o una desconexión activa.")
            
            # Mostrar reclamos activos
            for _, reclamo in reclamos_activos.iterrows():
                with st.expander(f"🔍 Reclamo activo - {format_fecha(reclamo['Fecha y hora'], '%d/%m/%Y %H:%M')}"):
                    st.markdown(f"**👤 Cliente:** {reclamo.get('Nombre', 'N/A')}")
                    st.markdown(f"**📌 Tipo:** {reclamo.get('Tipo de reclamo', 'N/A')}")
                    st.markdown(f"**📝 Detalles:** {reclamo.get('Detalles', 'N/A')[:200]}...")
                    st.markdown(f"**⚙️ Estado:** {reclamo.get('Estado', 'Sin estado')}")
                    
                    # Mostrar técnico asignado si existe
                    tecnico_asignado = reclamo.get('Técnico', '').strip()
                    if tecnico_asignado:
                        st.markdown(f"**👷 Técnico asignado:** {tecnico_asignado}")
                    else:
                        st.markdown("**👷 Técnico asignado:** Sin asignar")

    if estado['reclamo_guardado']:
        st.success("✅ Reclamo registrado correctamente.")
        
        # Verificar si el cliente tiene reclamos activos después de guardar
        df_clientes_norm, df_reclamos_norm = _normalizar_datos(
            df_clientes, df_reclamos, estado['nro_cliente']
        )
        reclamos_activos = _verificar_reclamos_activos(estado['nro_cliente'], df_reclamos_norm)
        
        if not reclamos_activos.empty:
            st.warning("⚠️ Este cliente ya tiene un reclamo activo. No es posible crear otro hasta que se resuelva o cambie de número de cliente.")
            
            # Mostrar reclamos activos
            for _, reclamo in reclamos_activos.iterrows():
                with st.expander(f"🔍 Reclamo activo - {format_fecha(reclamo['Fecha y hora'], '%d/%m/%Y %H:%M')}"):
                    st.markdown(f"**👤 Cliente:** {reclamo.get('Nombre', 'N/A')}")
                    st.markdown(f"**📌 Tipo:** {reclamo.get('Tipo de reclamo', 'N/A')}")
                    st.markdown(f"**📝 Detalles:** {reclamo.get('Detalles', 'N/A')[:200]}...")
                    st.markdown(f"**⚙️ Estado:** {reclamo.get('Estado', 'Sin estado')}")
                    
                    # Mostrar técnico asignado si existe
                    tecnico_asignado = reclamo.get('Técnico', '').strip()
                    if tecnico_asignado:
                        st.markdown(f"**👷 Técnico asignado:** {tecnico_asignado}")
                    else:
                        st.markdown("**👷 Técnico asignado:** Sin asignar")
        
        # Botón para crear nuevo reclamo después de guardar exitosamente
        if st.button("📝 Crear nuevo reclamo", type="primary"):
            _reset_formulario()
            st.rerun()
            
    elif not estado['formulario_bloqueado']:
        _mostrar_formulario_reclamo(estado, df_clientes, sheet_reclamos, sheet_clientes, current_user)

    # Actualizar session_state
    st.session_state.nuevo_reclamo = estado

# --- FUNCIÓN DE FORMULARIO MEJORADA ---
def _mostrar_formulario_reclamo(estado, df_clientes, sheet_reclamos, sheet_clientes, current_user):
    """Muestra y procesa el formulario de nuevo reclamo con anotaciones previas"""
    
    # Mostrar anotaciones previas si el cliente existe y tiene anotaciones
    if estado['cliente_existente']:
        anotaciones_previas = estado['cliente_existente'].get("Anotaciones", "")
        if anotaciones_previas and anotaciones_previas.strip():
            # Mejoramos el formato de visualización
            st.markdown("### 📋 Anotación anterior del cliente")
            st.info(f"**{anotaciones_previas}**")
    
    with st.form("reclamo_formulario", clear_on_submit=False):
        col1, col2 = st.columns(2)

        # Datos del cliente (existe o nuevo)
        if estado['cliente_existente']:
            cliente_data = estado['cliente_existente']
            
            with col1:
                nombre = st.text_input(
                    "👤 Nombre del Cliente",
                    value=cliente_data.get("Nombre", "")
                )
                direccion = st.text_input(
                    "📍 Dirección",
                    value=cliente_data.get("Dirección", "")
                )

            with col2:
                telefono = st.text_input(
                    "📞 Teléfono",
                    value=cliente_data.get("Teléfono", "")
                )
                
                # Sector con validación mejorada
                sector_existente = cliente_data.get("Sector", "1")
                sector_normalizado, error_sector = _validar_y_normalizar_sector(sector_existente)
                
                if error_sector:
                    st.warning(error_sector)
                    sector = st.text_input("🔢 Sector (1-17)", value="1")
                else:
                    sector = st.text_input("🔢 Sector (1-17)", value=sector_normalizado)

        else:
            with col1:
                nombre = st.text_input("👤 Nombre del Cliente", placeholder="Nombre completo")
                direccion = st.text_input("📍 Dirección", placeholder="Dirección completa")
            
            with col2:
                telefono = st.text_input("📞 Teléfono", placeholder="Número de contacto")
                sector = st.text_input("🔢 Sector (1-17)", placeholder="Ej: 5")

        # Campos del reclamo
        tipo_reclamo = st.selectbox("📌 Tipo de Reclamo", TIPOS_RECLAMO)
        detalles = st.text_area("📝 Detalles del Reclamo", placeholder="Describe el problema...", height=100)

        col3, col4 = st.columns(2)
        with col3:
            precinto = st.text_input(
                "🔒 N° de Precinto (opcional)",
                value=estado['cliente_existente'].get("N° de Precinto", "") if estado['cliente_existente'] else "",
                placeholder="Número de precinto"
            )
        
        with col4:
            atendido_por = st.text_input(
                "👤 Atendido por", 
                placeholder="Nombre de quien atiende", 
                value=current_user or ""
            )

        enviado = st.form_submit_button("✅ Guardar Reclamo", use_container_width=True)

    if enviado:
        _procesar_envio_formulario(
            estado, nombre, direccion, telefono, sector, 
            tipo_reclamo, detalles, precinto, atendido_por,
            df_clientes, sheet_reclamos, sheet_clientes
        )

# --- FUNCIÓN DE PROCESAMIENTO OPTIMIZADA ---
def _procesar_envio_formulario(estado, nombre, direccion, telefono, sector, tipo_reclamo, 
                              detalles, precinto, atendido_por, df_clientes, sheet_reclamos, sheet_clientes):
    """Procesa el envío del formulario de manera optimizada"""
    
    # Validar campos obligatorios
    campos_vacios = _validar_campos_obligatorios(nombre, direccion, sector, tipo_reclamo, atendido_por)
    
    if campos_vacios:
        st.error(f"⚠️ Campos obligatorios vacíos: {', '.join(campos_vacios)}")
        return

    # Validar y normalizar sector
    sector_normalizado, error_sector = _validar_y_normalizar_sector(sector)
    if error_sector:
        st.error(error_sector)
        return

    with st.spinner("Guardando reclamo..."):
        try:
            # --- Preparación de Datos del Reclamo ---
            fecha_hora = ahora_argentina()
            # Condición especial para el tipo de reclamo "Desconexion a Pedido"
            if tipo_reclamo.strip().lower() == "desconexion a pedido":
                estado_reclamo = "Desconexión"
            else:
                estado_reclamo = "Pendiente"

            id_reclamo = generar_id_unico()

            # Construcción de la fila de datos para la hoja de cálculo
            fila_reclamo = [
                format_fecha(fecha_hora),       # Fecha y hora
                estado['nro_cliente'],          # Nº Cliente
                sector_normalizado,             # Sector
                nombre.upper().strip(),         # Nombre
                direccion.upper().strip(),      # Dirección
                telefono.strip(),               # Teléfono
                tipo_reclamo,                   # Tipo de reclamo
                detalles.upper().strip(),       # Detalles
                estado_reclamo,                 # Estado (Pendiente o Desconexión)
                "",                             # Técnico (se asigna después)
                precinto.strip(),               # N° de Precinto
                atendido_por.upper().strip(),   # Atendido por
                "",                             # Fecha_formateada (se llena al cerrar)
                "",                             # N: Anotaciones (vacío al crear)
                id_reclamo                      # ID Reclamo
            ]

            # --- Interacción con Google Sheets ---
            success, error = api_manager.safe_sheet_operation(
                sheet_reclamos.append_row,
                fila_reclamo
            )

            if success:
                estado.update({
                    'reclamo_guardado': True,
                    'formulario_bloqueado': True
                })
                
                st.success(f"✅ Reclamo guardado - ID: {id_reclamo}")
                
                # Gestionar cliente (nuevo o actualización)
                _gestionar_cliente(
                    estado['nro_cliente'], sector_normalizado, nombre, 
                    direccion, telefono, precinto, df_clientes, sheet_clientes
                )
                
                st.cache_data.clear()
                
                # 🔄 Forzar recarga para limpiar el formulario y mostrar reclamo activo
                st.rerun()

            else:
                st.error(f"❌ Error al guardar: {error}")

        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")
            if DEBUG_MODE:
                st.exception(e)

def _gestionar_cliente(nro_cliente, sector, nombre, direccion, telefono, precinto, df_clientes, sheet_clientes):
    """Gestiona la creación o actualización del cliente, preservando anotaciones existentes"""
    cliente_existente = df_clientes[df_clientes["Nº Cliente"] == nro_cliente]
    
    if cliente_existente.empty:
        # Crear nuevo cliente con UUID y última modificación
        id_cliente = generar_id_unico()
        ultima_mod = format_fecha(ahora_argentina())
        fila_cliente = [
            nro_cliente,           # A: Nº Cliente
            sector,                # B: Sector
            nombre.upper(),        # C: Nombre
            direccion.upper(),     # D: Dirección
            telefono.strip(),      # E: Teléfono
            precinto.strip(),      # F: N° de Precinto
            id_cliente,            # G: ID Cliente
            ultima_mod,            # H: Última Modificación
            ""                     # I: Anotaciones (vacío para nuevo cliente)
        ]
        success, _ = api_manager.safe_sheet_operation(sheet_clientes.append_row, fila_cliente)
        if success:
            st.info("ℹ️ Nuevo cliente registrado con ID asignado")
    else:
        # Actualizar cliente existente pero preservar anotaciones
        anotaciones_existentes = cliente_existente.iloc[0].get("Anotaciones", "")
        
        updates = []
        idx = cliente_existente.index[0] + 2
        
        # Mapeo correcto de columnas (A=1, B=2, C=3, D=4, E=5, F=6, G=7, H=8, I=9)
        campos_actualizar = {
            "B": sector,                    # Columna B: Sector
            "C": nombre.upper(),            # Columna C: Nombre
            "D": direccion.upper(),         # Columna D: Dirección
            "E": telefono.strip(),          # Columna E: Teléfono
            "F": precinto.strip(),          # Columna F: N° de Precinto
            "I": anotaciones_existentes     # Columna I: Preservar anotaciones existentes
        }
        
        # Actualizar solo los campos que han cambiado
        if str(cliente_existente.iloc[0].get("Sector", "")).strip() != str(sector).strip():
            updates.append({"range": f"B{idx}", "values": [[sector]]})
        
        if str(cliente_existente.iloc[0].get("Nombre", "")).strip() != nombre.upper().strip():
            updates.append({"range": f"C{idx}", "values": [[nombre.upper()]]})
        
        if str(cliente_existente.iloc[0].get("Dirección", "")).strip() != direccion.upper().strip():
            updates.append({"range": f"D{idx}", "values": [[direccion.upper()]]})
        
        if str(cliente_existente.iloc[0].get("Teléfono", "")).strip() != telefono.strip():
            updates.append({"range": f"E{idx}", "values": [[telefono.strip()]]})
        
        if str(cliente_existente.iloc[0].get("N° de Precinto", "")).strip() != precinto.strip():
            updates.append({"range": f"F{idx}", "values": [[precinto.strip()]]})
        
        if updates:
            success, _ = api_manager.safe_sheet_operation(
                batch_update_sheet, sheet_clientes, updates, is_batch=True
            )
            if success:
                st.info("🔁 Datos del cliente actualizados")