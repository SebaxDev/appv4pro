# components/reclamos/impresion.py

import io
import streamlit as st
import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from utils.date_utils import format_fecha, parse_fecha
from utils.pdf_utils import agregar_pie_pdf
from utils.date_utils import ahora_argentina
from utils.reporte_diario import *
from config.settings import DEBUG_MODE, MATERIALES_POR_RECLAMO, ROUTER_POR_SECTOR

def render_impresion_reclamos(df_reclamos, df_clientes, user):
    """
    Muestra la sección para imprimir reclamos en formato PDF

    Args:
        df_reclamos (pd.DataFrame): DataFrame con los reclamos
        df_clientes (pd.DataFrame): DataFrame con los clientes
        user (dict): Información del usuario actual

    Returns:
        dict: {
            'needs_refresh': bool,
            'message': str,
            'data_updated': bool
        }
    """
    result = {
        'needs_refresh': False,
        'message': None,
        'data_updated': False
    }

    st.subheader("📨️ Seleccionar reclamos para imprimir (formato técnico compacto)")

    try:
        # Preparar datos con información del usuario
        df_merged = _preparar_datos(df_reclamos, df_clientes, user)

        # Mostrar reclamos pendientes
        _mostrar_reclamos_pendientes(df_merged)

        # Configuración de impresión
        with st.expander("⚙️ Configuración de impresión", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                solo_pendientes = st.checkbox(
                    "📜 Mostrar solo reclamos pendientes",
                    value=True
                )
            with col2:
                incluir_usuario = st.checkbox(
                    "👤 Incluir mi nombre en el PDF",
                    value=True
                )

        # === REORGANIZACIÓN EN GRID 2x3 ===
        st.markdown("### 🖨️ Opciones de Impresión")

        # Fila 1: Dos opciones
        col1, col2 = st.columns(2)

        with col1:
            mensaje_todos = _generar_pdf_todos_pendientes(df_merged, user if incluir_usuario else None)
            if mensaje_todos:
                result['message'] = mensaje_todos

        with col2:
            mensaje_tipo = _generar_pdf_por_tipo(df_merged, solo_pendientes, user if incluir_usuario else None)
            if mensaje_tipo:
                result['message'] = mensaje_tipo

        # Fila 2: Dos opciones
        col3, col4 = st.columns(2)

        with col3:
            mensaje_manual = _generar_pdf_manual(df_merged, solo_pendientes, user if incluir_usuario else None)
            if mensaje_manual:
                result['message'] = mensaje_manual

        with col4:
            mensaje_desconexiones = _generar_pdf_desconexiones(df_merged, user if incluir_usuario else None)
            if mensaje_desconexiones:
                result['message'] = mensaje_desconexiones

        # Fila 3: Dos opciones
        col5, col6 = st.columns(2)

        with col5:
            # Espacio reservado - la opción de en curso se movió a una sección dedicada más abajo
            st.markdown("#### 📊 Estadísticas Rápidas")
            df_en_curso_count = df_reclamos[df_reclamos["Estado"].astype(str).str.strip().str.lower() == "en curso"]
            df_pendientes_count = df_reclamos[df_reclamos["Estado"].astype(str).str.strip().str.lower() == "pendiente"]
            st.metric("🔄 En Curso", len(df_en_curso_count))
            st.metric("⏳ Pendientes", len(df_pendientes_count))

        with col6:
            # Nueva opción: Reporte Diario en el grid
            st.markdown("#### 📄 Reporte Diario")
            if st.button("🖼️ Generar imagen del día", use_container_width=True):
                img_buffer = generar_reporte_diario_imagen(df_reclamos)
                fecha_hoy = ahora_argentina().strftime("%Y-%m-%d")

                st.download_button(
                    label="⬇️ Descargar Reporte",
                    data=img_buffer,
                    file_name=f"reporte_diario_{fecha_hoy}.png",
                    mime="image/png",
                    use_container_width=True
                )

        # === NUEVA FILA: PDF Detallado por Técnico ===
        st.markdown("---")
        st.markdown("### 📋 Reclamos en Curso - PDF Detallado por Técnico")
        st.caption("💡 Esta opción genera un PDF con el mismo formato que el módulo de Planificación, ideal para entregar a los técnicos.")

        col_det1, col_det2 = st.columns(2)

        with col_det1:
            mensaje_detallado = _generar_pdf_en_curso_detallado(df_merged, user if incluir_usuario else None)
            if mensaje_detallado:
                result['message'] = mensaje_detallado

        with col_det2:
            # Versión resumida (la que ya existía)
            st.markdown("#### 📝 Versión Resumida")
            st.caption("Lista compacta de reclamos por técnico")
            mensaje_resumido = _generar_pdf_en_curso_por_tecnico(df_merged, user if incluir_usuario else None)
            if mensaje_resumido:
                result['message'] = mensaje_resumido

        # === NUEVA FILA: Resumen Mensual ===
        st.markdown("---")
        st.markdown("### 🗓️ Resumen de Reclamos Resueltos")
        col7, col8 = st.columns(2)

        with col7:
            st.markdown("#### 📅 Generar Resumen (PDF)")

            # Selector de rango de días
            rango_dias = st.selectbox(
                "Seleccionar período:",
                options=[7, 15, 30, 60, 90],
                index=1,  # 30 días por defecto
                format_func=lambda x: f"Últimos {x} días"
            )

            if st.button("📄 Generar Resumen", use_container_width=True):
                buffer = _generar_pdf_resumen_mensual(
                    df_reclamos,
                    usuario=user if incluir_usuario else None,
                    rango_dias=rango_dias
                )
                fecha_hoy = ahora_argentina().strftime("%Y-%m-%d")

                st.download_button(
                    label="⬇️ Descargar PDF",
                    data=buffer,
                    file_name=f"resumen_{rango_dias}d_{fecha_hoy}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

    except Exception as e:
        st.error(f"❌ Error al generar PDF: {str(e)}")
        result['message'] = f"Error al generar PDF: {str(e)}"
        if DEBUG_MODE:
            st.exception(e)
    finally:
        st.markdown('</div>', unsafe_allow_html=True)

    return result

def _preparar_datos(df_reclamos, df_clientes, user):
    """Prepara y combina los datos para impresión incluyendo info de usuario"""
    df_pdf = df_reclamos.copy()

    # Procesamiento de fechas
    df_pdf["Fecha y hora"] = pd.to_datetime(
        df_pdf["Fecha y hora"],
        dayfirst=True,
        errors='coerce'
    )

    # Agregar información del usuario a los datos
    df_pdf["Usuario_impresion"] = user.get('nombre', 'Sistema')

    # Merge con clientes (optimizado)
    return pd.merge(
        df_pdf,
        df_clientes[["Nº Cliente", "N° de Precinto"]].drop_duplicates(),
        on="Nº Cliente",
        how="left",
        suffixes=("", "_cliente")
    )

def _mostrar_reclamos_pendientes(df_merged):
    """Muestra tabla de reclamos pendientes con mejor formato"""
    with st.expander("🕒 Reclamos pendientes de resolución", expanded=True):
        df_pendientes = df_merged[
            df_merged["Estado"].astype(str).str.strip().str.lower() == "pendiente"
        ]

        if not df_pendientes.empty:
            # Formatear datos para visualización
            df_pendientes_display = df_pendientes.copy()
            df_pendientes_display["Fecha y hora"] = df_pendientes_display["Fecha y hora"].apply(
                lambda f: format_fecha(f, '%d/%m/%Y %H:%M') if not pd.isna(f) else 'Sin fecha'
            )

            # Mostrar tabla con configuración mejorada
            st.dataframe(
                df_pendientes_display[[
                    "Fecha y hora", "Nº Cliente", "Nombre",
                    "Dirección", "Sector", "Tipo de reclamo"
                ]],
                use_container_width=True,
                column_config={
                    "Fecha y hora": st.column_config.DatetimeColumn(
                        "Fecha y hora",
                        format="DD/MM/YYYY HH:mm"
                    ),
                    "Nº Cliente": st.column_config.TextColumn(
                        "N° Cliente",
                        help="Número de cliente"
                    ),
                    "Sector": st.column_config.NumberColumn(
                        "Sector",
                        format="%d"
                    )
                },
                height=400
            )
        else:
            st.success("✅ No hay reclamos pendientes actualmente.")

def _generar_pdf_todos_pendientes(df_merged, usuario=None):
    """Genera PDF con todos los reclamos pendientes, ordenados por tipo o sector"""
    st.markdown("#### 📋 Todos los pendientes")
    
    # Filtrar solo pendientes
    df_pendientes = df_merged[
        df_merged["Estado"].astype(str).str.strip().str.lower() == "pendiente"
    ]

    if df_pendientes.empty:
        st.info("✅ No hay reclamos pendientes.")
        return None

    # Opciones de ordenamiento
    orden = st.radio(
        "Ordenar por:",
        ["Tipo", "Sector"],
        horizontal=True,
        key="orden_todos_pendientes"
    )

    # Ordenar según selección
    if orden == "Tipo":
        df_pendientes = df_pendientes.sort_values("Tipo de reclamo")
        titulo = "TODOS LOS RECLAMOS PENDIENTES (ORDENADOS POR TIPO)"
    else:
        df_pendientes = df_pendientes.sort_values("Sector")
        titulo = "TODOS LOS RECLAMOS PENDIENTES (ORDENADOS POR SECTOR)"

    st.info(f"📋 {len(df_pendientes)} reclamos pendientes")

    if st.button("📄 Generar PDF", key="pdf_todos_pendientes", use_container_width=True):
        buffer = _crear_pdf_reclamos(
            df_pendientes,
            titulo,
            usuario
        )

        nombre_archivo = f"todos_reclamos_pendientes_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            help=f"Descargar {len(df_pendientes)} reclamos pendientes"
        )

        return f"PDF generado con {len(df_pendientes)} reclamos pendientes (ordenados por {orden.lower()})"
    
    return None

def _generar_pdf_por_tipo(df_merged, solo_pendientes, usuario=None):
    """Genera PDF filtrado por tipos de reclamo"""
    st.markdown("#### 📋 Por tipo de reclamo")

    tipos_disponibles = sorted(df_merged["Tipo de reclamo"].dropna().unique())
    tipos_seleccionados = st.multiselect(
        "Seleccionar tipos:",
        tipos_disponibles,
        default=tipos_disponibles[0] if tipos_disponibles else None,
        key="select_tipos_pdf"
    )

    if not tipos_seleccionados:
        return None

    # Aplicar filtros
    df_filtrado = df_merged.copy()
    if solo_pendientes:
        df_filtrado = df_filtrado[
            df_filtrado["Estado"].str.strip().str.lower() == "pendiente"
        ]

    reclamos_filtrados = df_filtrado[
        df_filtrado["Tipo de reclamo"].isin(tipos_seleccionados)
    ]

    if reclamos_filtrados.empty:
        st.info("No hay reclamos para los tipos seleccionados.")
        return None

    st.info(f"📋 {len(reclamos_filtrados)} reclamos encontrados")

    if st.button("📄 Generar PDF", key="pdf_tipo", use_container_width=True):
        buffer = _crear_pdf_reclamos(
            reclamos_filtrados,
            f"RECLAMOS - {', '.join(tipos_seleccionados)}",
            usuario
        )

        nombre_archivo = f"reclamos_{'_'.join(t.lower().replace(' ', '_') for t in tipos_seleccionados)}.pdf"

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            help=f"Descargar {len(reclamos_filtrados)} reclamos"
        )

        return f"PDF generado con {len(reclamos_filtrados)} reclamos de tipo {', '.join(tipos_seleccionados)}"

    return None

def _generar_pdf_manual(df_merged, solo_pendientes, usuario=None):
    """Genera PDF con selección manual de reclamos"""
    st.markdown("#### 📋 Selección manual")

    df_filtrado = df_merged.copy()
    if solo_pendientes:
        df_filtrado = df_filtrado[
            df_filtrado["Estado"].astype(str).str.strip().str.lower() == "pendiente"
        ]

    # Selector mejorado con más información
    selected = st.multiselect(
        "Seleccionar reclamos:",
        df_filtrado.index,
        format_func=lambda x: (
            f"{df_filtrado.at[x, 'Nº Cliente']} - "
            f"{df_filtrado.at[x, 'Nombre']} - "
            f"Sector {df_filtrado.at[x, 'Sector']} - "
            f"{df_filtrado.at[x, 'Tipo de reclamo']}"
        ),
        key="multiselect_reclamos"
    )

    if not selected:
        st.info("ℹ️ Seleccionar al menos un reclamo")
        return None

    st.info(f"📋 {len(selected)} reclamos seleccionados")

    if st.button("📄 Generar PDF", key="pdf_manual", use_container_width=True):
        buffer = _crear_pdf_reclamos(
            df_filtrado.loc[selected],
            f"RECLAMOS SELECCIONADOS",
            usuario
        )

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name="reclamos_seleccionados.pdf",
            mime="application/pdf",
            use_container_width=True,
            help=f"Descargar {len(selected)} reclamos seleccionados"
        )

        return f"PDF generado con {len(selected)} reclamos seleccionados"
    
    return None

def _generar_pdf_desconexiones(df_merged, usuario=None):
    """Genera un PDF con desconexiones a pedido (estado = desconexión)"""
    st.markdown("#### 🔌 Desconexiones a pedido")

    df_desconexiones = df_merged[
        (df_merged["Tipo de reclamo"].str.strip().str.lower() == "desconexion a pedido") &
        (df_merged["Estado"].str.strip().str.lower() == "desconexión")
    ]

    if df_desconexiones.empty:
        st.info("✅ No hay desconexiones pendientes")
        return None

    st.info(f"📋 {len(df_desconexiones)} desconexiones encontradas")

    if st.button("📄 Generar PDF", key="pdf_desconexiones", use_container_width=True):
        buffer = _crear_pdf_reclamos(
            df_desconexiones,
            "LISTADO DE CLIENTES PARA DESCONEXIÓN",
            usuario
        )
        nombre_archivo = f"desconexiones_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            help=f"Descargar {len(df_desconexiones)} desconexiones"
        )

        return f"PDF generado con {len(df_desconexiones)} desconexiones pendientes"

    return None

def _generar_pdf_en_curso_por_tecnico(df_merged, usuario=None):
    """Genera un PDF con reclamos en curso agrupados por técnico"""
    st.markdown("#### 👷 En curso por técnico")

    df_en_curso = df_merged[
        df_merged["Estado"].astype(str).str.strip().str.lower() == "en curso"
    ].copy()

    if df_en_curso.empty:
        st.info("✅ No hay reclamos en curso")
        return None

    st.info(f"📋 {len(df_en_curso)} reclamos en curso")

    if st.button("📄 Generar PDF", key="pdf_en_curso_tecnico", use_container_width=True):
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        import io

        df_en_curso["Técnico"] = df_en_curso["Técnico"].fillna("Sin técnico").str.upper()
        reclamos_por_tecnico = df_en_curso.groupby("Técnico")

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        y = height - 40
        hoy = datetime.now().strftime('%d/%m/%Y')

        c.setFont("Helvetica-Bold", 16)
        c.drawString(40, y, f"RECLAMOS EN CURSO - {hoy}")
        if usuario:
            c.setFont("Helvetica", 10)
            c.drawString(width - 200, y, f"Por: {usuario.get('nombre', 'Sistema')}")
        y -= 30

        for tecnico, reclamos in reclamos_por_tecnico:
            if y < 100:
                agregar_pie_pdf(c, width, height)
                c.showPage()
                y = height - 40
                c.setFont("Helvetica-Bold", 16)
                c.drawString(40, y, f"RECLAMOS EN CURSO - {hoy}")
                y -= 30

            c.setFont("Helvetica-Bold", 13)
            c.drawString(40, y, f"👷 Técnico: {tecnico} ({len(reclamos)})")
            y -= 20

            c.setFont("Helvetica", 11)
            for _, row in reclamos.iterrows():
                texto = f"{row['Nº Cliente']} - {row['Tipo de reclamo']} - Sector {row['Sector']}"
                c.drawString(50, y, texto)
                y -= 15
                if y < 60:
                    agregar_pie_pdf(c, width, height)
                    c.showPage()
                    y = height - 40

            # Línea divisoria después de los reclamos de cada técnico
            c.setFont("Helvetica", 10)
            c.drawString(40, y, "-" * 80)
            y -= 20

        agregar_pie_pdf(c, width, height)
        c.save()
        buffer.seek(0)

        st.download_button(
            label="⬇️ Descargar PDF",
            data=buffer,
            file_name=f"reclamos_en_curso_tecnicos_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            help="Reclamos agrupados por técnico"
        )

        return "PDF generado con reclamos en curso por técnico"

    return None

def _calcular_materiales_tecnico(reclamos_tecnico):
    """Calcula los materiales necesarios para los reclamos de un técnico"""
    materiales_total = {}
    for _, row in reclamos_tecnico.iterrows():
        tipo = row.get("Tipo de reclamo", "")
        sector = str(row.get("Sector", ""))
        materiales_tipo = MATERIALES_POR_RECLAMO.get(tipo, {})
        for mat, cant in materiales_tipo.items():
            key = mat
            if "router" in mat:
                marca = ROUTER_POR_SECTOR.get(sector, "vsol")
                key = f"router_{marca}"
            materiales_total[key] = materiales_total.get(key, 0) + cant
    return materiales_total

def _generar_pdf_en_curso_detallado(df_merged, usuario=None):
    """
    Genera un PDF DETALLADO con reclamos en curso agrupados por técnico.
    Este es el formato completo igual al de planificación, para entregar a los técnicos.
    
    IMPORTANTE: Agrupa técnicos que tienen los MISMOS reclamos asignados (trabajan juntos).
    """
    st.markdown("#### 📄 En curso por técnico (Formato Completo)")
    st.caption("📋 PDF detallado con todos los datos del cliente para entregar a cada técnico")

    df_en_curso = df_merged[
        df_merged["Estado"].astype(str).str.strip().str.lower() == "en curso"
    ].copy()

    if df_en_curso.empty:
        st.info("✅ No hay reclamos en curso")
        return None

    # Normalizar técnicos
    df_en_curso["Técnico"] = df_en_curso["Técnico"].fillna("").astype(str).str.upper().str.strip()
    
    # === AGRUPAR TÉCNICOS QUE TIENEN LOS MISMOS RECLAMOS ===
    # Crear un diccionario: set de reclamos -> lista de técnicos que los comparten
    from collections import defaultdict
    
    tecnicos_por_reclamos = defaultdict(list)
    
    for idx, row in df_en_curso.iterrows():
        reclamo_id = row.get("ID Reclamo", idx)
        tecnicos_str = row.get("Técnico", "")
        # Obtener lista de técnicos para este reclamo
        tecnicos_lista = [t.strip() for t in tecnicos_str.split(",") if t.strip()]
        if tecnicos_lista:
            # Crear una clave única basada en el reclamo
            tecnicos_por_reclamos[reclamo_id].extend(tecnicos_lista)
    
    # Ahora agrupar: encontrar qué técnicos comparten TODOS los mismos reclamos
    # Mapa: técnico -> set de IDs de reclamos
    tecnico_a_reclamo = defaultdict(set)
    for idx, row in df_en_curso.iterrows():
        reclamo_id = row.get("ID Reclamo", idx)
        tecnicos_str = row.get("Técnico", "")
        tecnicos_lista = [t.strip() for t in tecnicos_str.split(",") if t.strip()]
        for tecnico in tecnicos_lista:
            tecnico_a_reclamo[tecnico].add(reclamo_id)
    
    # Agrupar técnicos que tienen el MISMO set de reclamos
    grupos_tecnicos = defaultdict(list)  # frozenset de reclamos -> lista de técnicos
    for tecnico, reclamos_set in tecnico_a_reclamo.items():
        grupos_tecnicos[frozenset(reclamos_set)].append(tecnico)
    
    # Crear lista de grupos: (nombres_tecnicos, set_reclamos)
    lista_grupos = []
    for reclamos_set, tecnicos in grupos_tecnicos.items():
        tecnicos_ordenados = sorted(set(tecnicos))
        lista_grupos.append({
            "tecnicos": tecnicos_ordenados,
            "tecnicos_str": ", ".join(tecnicos_ordenados),
            "reclamos_ids": reclamos_set,
            "cantidad": len(reclamos_set)
        })
    
    # Ordenar grupos por cantidad de reclamos (descendente)
    lista_grupos.sort(key=lambda x: x["cantidad"], reverse=True)

    if not lista_grupos:
        st.info("⚠️ Hay reclamos en curso pero sin técnicos asignados")
        return None

    total_reclamos = sum(g["cantidad"] for g in lista_grupos)
    st.info(f"📋 {len(df_en_curso)} reclamos en curso - {len(lista_grupos)} grupo(s) de trabajo")

    if st.button("📄 Generar PDF Detallado", key="pdf_en_curso_detallado", use_container_width=True):
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        margen_izq = 40
        margen_der = 40
        y = height - 40
        hoy = ahora_argentina().strftime('%d/%m/%Y')
        max_line_width = width - margen_izq - margen_der

        def wrap_text(texto, fuente="Helvetica", tam=11):
            """Envuelve texto para que quepa en el ancho disponible"""
            if not texto:
                return []
            palabras = str(texto).split()
            lineas = []
            actual = ""
            for p in palabras:
                candidata = (actual + (" " if actual else "") + p)
                if c.stringWidth(candidata, fuente, tam) <= max_line_width:
                    actual = candidata
                else:
                    if actual:
                        lineas.append(actual)
                    actual = p
            if actual:
                lineas.append(actual)
            return lineas

        def salto_pagina_si_necesario(altura_necesaria=100):
            nonlocal y
            if y < altura_necesaria:
                agregar_pie_pdf(c, width, height)
                c.showPage()
                y = height - 40
                return True
            return False

        # Procesar cada GRUPO de técnicos
        for grupo_info in lista_grupos:
            tecnicos_str = grupo_info["tecnicos_str"]
            reclamos_ids = grupo_info["reclamos_ids"]
            
            # Filtrar reclamos de este grupo
            reclamos_grupo = df_en_curso[
                df_en_curso["ID Reclamo"].isin(reclamos_ids) | 
                df_en_curso.index.isin(reclamos_ids)
            ].copy()

            if reclamos_grupo.empty:
                continue

            # Nueva página para cada grupo
            agregar_pie_pdf(c, width, height)
            c.showPage()
            y = height - 40

            # Encabezado del grupo
            c.setFont("Helvetica-Bold", 16)
            etiqueta_tecnico = "Técnico:" if len(grupo_info["tecnicos"]) == 1 else "Técnicos:"
            c.drawString(margen_izq, y, f"👷 {etiqueta_tecnico} {tecnicos_str}")
            y -= 18
            c.setFont("Helvetica", 12)
            c.drawString(margen_izq, y, f"📅 Asignación del {hoy} | {len(reclamos_grupo)} reclamo(s)")
            y -= 15

            # Resumen de tipos de reclamo
            tipos_resumen = reclamos_grupo["Tipo de reclamo"].value_counts()
            resumen_tipos = " - ".join([f"{v} {k}" for k, v in tipos_resumen.items()])
            
            # Wrap del resumen si es muy largo
            c.setFont("Helvetica", 10)
            for linea in wrap_text(resumen_tipos, tam=10):
                c.drawString(margen_izq, y, linea)
                y -= 12
            
            # Sectores cubiertos
            sectores = ", ".join(sorted(set(reclamos_grupo["Sector"].astype(str))))
            c.drawString(margen_izq, y, f"Sectores: {sectores}")
            y -= 25

            # Lista detallada de reclamos
            for _, row in reclamos_grupo.iterrows():
                salto_pagina_si_necesario(120)

                # Encabezado del reclamo
                c.setFont("Helvetica-Bold", 13)
                num_cliente = str(row.get("Nº Cliente", "")).strip()
                nombre = str(row.get("Nombre", "")).strip()
                sector = str(row.get("Sector", "")).strip()
                
                nombre_linea = f"{num_cliente} - {nombre} ({sector})"
                for l in wrap_text(nombre_linea, fuente="Helvetica-Bold", tam=13):
                    c.drawString(margen_izq, y, l)
                    y -= 15

                # Datos del reclamo
                c.setFont("Helvetica", 11)
                
                # Fecha
                fecha_val = row.get("Fecha y hora")
                try:
                    if pd.notna(fecha_val) and not isinstance(fecha_val, pd.Timestamp):
                        fecha_val = pd.to_datetime(fecha_val, dayfirst=True, errors='coerce')
                except:
                    fecha_val = None
                fecha_pdf = format_fecha(fecha_val, '%d/%m/%Y %H:%M') if pd.notna(fecha_val) else 'Sin fecha'

                direccion = str(row.get("Dirección", "")).strip()
                telefono = str(row.get("Teléfono", "")).strip()
                precinto = str(row.get("N° de Precinto", "")).strip()
                tipo = str(row.get("Tipo de reclamo", "")).strip()
                detalles = str(row.get("Detalles", "")).strip()

                lineas = [
                    f"Fecha: {fecha_pdf}",
                    f"Dirección: {direccion}",
                    f"Tel: {telefono} - Precinto: {precinto}" if telefono or precinto else "Precinto: " + precinto,
                    f"Tipo: {tipo}",
                ]

                for linea in lineas:
                    for l in wrap_text(linea, tam=11):
                        c.drawString(margen_izq, y, l)
                        y -= 12

                # Detalles (con wrap)
                if detalles:
                    detalles_lineas = wrap_text(detalles, tam=11)
                    for i, l in enumerate(detalles_lineas):
                        if i == 0:
                            c.drawString(margen_izq, y, f"Detalles: {l}")
                        else:
                            c.drawString(margen_izq + 55, y, l)  # Indent para líneas siguientes
                        y -= 12
                        salto_pagina_si_necesario(60)

                # Separador
                y -= 5
                c.line(margen_izq, y, width - margen_der, y)
                y -= 15

            # Materiales estimados para este grupo
            materiales = _calcular_materiales_tecnico(reclamos_grupo)
            if materiales:
                salto_pagina_si_necesario(80)
                y -= 10
                c.setFont("Helvetica-Bold", 12)
                c.drawString(margen_izq, y, "🛠️ Materiales mínimos estimados:")
                y -= 15
                c.setFont("Helvetica", 11)
                for mat, cant in materiales.items():
                    c.drawString(margen_izq, y, f"  • {cant} {mat.replace('_', ' ').title()}")
                    y -= 12
                y -= 15

        agregar_pie_pdf(c, width, height)
        c.save()
        buffer.seek(0)

        nombre_archivo = f"reclamos_en_curso_detallado_{ahora_argentina().strftime('%Y%m%d_%H%M')}.pdf"

        st.download_button(
            label="⬇️ Descargar PDF Detallado",
            data=buffer,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True,
            help="PDF con todos los datos de los reclamos para entregar a los técnicos"
        )

        return f"PDF detallado generado con {len(df_en_curso)} reclamos para {len(lista_grupos)} grupo(s) de trabajo"

    return None

# ==============================
# Utilidad central para crear PDF
# ==============================
def _generar_pdf_resumen_mensual(df_reclamos, usuario=None, rango_dias=30):
    """Genera un PDF con el resumen de reclamos resueltos dentro de un rango de días elegido."""
    import io
    from datetime import datetime, timedelta
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margen_izq = 50
    y = height - 50
    hoy = ahora_argentina()
    fecha_inicio = hoy - timedelta(days=rango_dias)

    # Filtrar solo los reclamos resueltos en el rango seleccionado
    df = df_reclamos.copy()
    df["Fecha y hora"] = pd.to_datetime(df["Fecha y hora"], dayfirst=True, errors='coerce')
    df_filtrado = df[
        (df["Estado"].astype(str).str.strip().str.lower() == "resuelto") &
        (df["Fecha y hora"].dt.date >= fecha_inicio.date())
    ]

    c.setFont("Helvetica-Bold", 16)
    c.drawString(margen_izq, y, f"📅 RESUMEN DE RECLAMOS RESUELTOS - ÚLTIMOS {rango_dias} DÍAS")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(margen_izq, y, f"Período: {fecha_inicio.strftime('%d/%m/%Y')} - {hoy.strftime('%d/%m/%Y')}")
    if usuario:
        c.drawString(width - 200, y, f"Por: {usuario.get('nombre', 'Sistema')}")
    y -= 30

    if df_filtrado.empty:
        c.setFont("Helvetica", 12)
        c.drawString(margen_izq, y, f"No se encontraron reclamos resueltos en los últimos {rango_dias} días.")
        agregar_pie_pdf(c, width, height)
        c.save()
        buffer.seek(0)
        return buffer

    # --- Sección 1: Totales por tipo de reclamo ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margen_izq, y, "📊 Reclamos resueltos por tipo:")
    y -= 20

    totales_tipo = (
        df_filtrado["Tipo de reclamo"].fillna("Sin tipo")
        .str.strip()
        .value_counts()
        .sort_index()
    )

    c.setFont("Helvetica", 12)
    for tipo, cantidad in totales_tipo.items():
        c.drawString(margen_izq + 20, y, f"- {tipo}: {cantidad}")
        y -= 15
        if y < 60:
            agregar_pie_pdf(c, width, height)
            c.showPage()
            y = height - 50
            c.setFont("Helvetica", 12)

    y -= 20

    # --- Sección 2: Totales por técnico ---
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margen_izq, y, "👷 Reclamos resueltos por técnico:")
    y -= 20

    if "Técnico" in df_filtrado.columns:
        df_filtrado["Técnico"] = df_filtrado["Técnico"].fillna("").astype(str)
        df_filtrado["tecnicos_set"] = df_filtrado["Técnico"].apply(
            lambda x: tuple(sorted([t.strip().upper() for t in x.split(",") if t.strip()]))
        )
        conteo_tecnicos = (
            df_filtrado.groupby("tecnicos_set").size().reset_index(name="Cantidad")
        )

        if conteo_tecnicos.empty:
            c.setFont("Helvetica", 12)
            c.drawString(margen_izq + 20, y, "No hay técnicos asignados en los reclamos resueltos.")
        else:
            c.setFont("Helvetica", 12)
            for _, row in conteo_tecnicos.iterrows():
                tecnicos = ", ".join(row["tecnicos_set"]) if row["tecnicos_set"] else "Sin técnico"
                c.drawString(margen_izq + 20, y, f"- {tecnicos}: {row['Cantidad']}")
                y -= 15
                if y < 60:
                    agregar_pie_pdf(c, width, height)
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 12)
    else:
        c.drawString(margen_izq + 20, y, "Columna 'Técnico' no encontrada en los datos.")

    agregar_pie_pdf(c, width, height)
    c.save()
    buffer.seek(0)
    return buffer

def _crear_pdf_reclamos(df, titulo, usuario=None):
    """Crea un PDF con el mismo estilo de impresión que planificación.

    Para cada reclamo imprime un bloque:
    - Título de cliente en negrita: "Nº Cliente - Nombre (Sector)"
    - Líneas: Fecha, Dirección, Tel/Precinto, Tipo, Detalles (con wrap)
    - Separador y manejo de salto de página
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margen_izq = 40
    margen_der = 40
    y = height - 40
    hoy = ahora_argentina().strftime('%d/%m/%Y')

    max_line_width = width - margen_izq - margen_der

    def wrap_text(texto, fuente="Helvetica", tam=11):
        """Envuelve `texto` para que quepa en el ancho disponible."""
        if not texto:
            return []
        palabras = str(texto).split()
        lineas = []
        actual = ""
        for p in palabras:
            candidata = (actual + (" " if actual else "") + p)
            if c.stringWidth(candidata, fuente, tam) <= max_line_width:
                actual = candidata
            else:
                if actual:
                    lineas.append(actual)
                actual = p
        if actual:
            lineas.append(actual)
        return lineas

    def iniciar_pagina():
        nonlocal y
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margen_izq, y, titulo)
        c.setFont("Helvetica", 10)
        c.drawString(width - 160, y, f"Fecha: {hoy}")
        if usuario:
            c.drawString(width - 160, y - 12, f"Por: {usuario.get('nombre', 'Sistema')}")
        y -= 30

    def salto_pagina_si_necesario(altura_necesaria=80):
        nonlocal y
        if y < altura_necesaria:
            agregar_pie_pdf(c, width, height)
            c.showPage()
            y = height - 40
            iniciar_pagina()

    iniciar_pagina()

    columnas = df.columns

    for _, row in df.iterrows():
        # Normalizar/leer campos
        num_cliente = str(row.get("Nº Cliente", "")).strip()
        nombre = str(row.get("Nombre", "")).strip()
        sector = str(row.get("Sector", "")).strip()
        direccion = str(row.get("Dirección", "")).strip()
        telefono = str(row.get("Teléfono", "")).strip() if "Teléfono" in columnas else ""
        detalles = str(row.get("Detalles", "")).strip()
        tipo = str(row.get("Tipo de reclamo", "")).strip()
        tecnico = str(row.get("Técnico", "")).strip()
        precinto = str(row.get("N° de Precinto", "")).strip()

        # Fecha
        fecha_val = row.get("Fecha y hora") if "Fecha y hora" in columnas else None
        try:
            if pd.notna(fecha_val) and not isinstance(fecha_val, pd.Timestamp):
                fecha_val = pd.to_datetime(fecha_val, dayfirst=True, errors='coerce')
        except Exception:
            fecha_val = None
        fecha_pdf = format_fecha(fecha_val, '%d/%m/%Y %H:%M') if pd.notna(fecha_val) else 'Sin fecha'

        # Altura estimada del bloque (simple): 5 líneas base + detalles envueltos
        detalles_lineas = wrap_text(detalles, tam=11)
        altura_bloque = 15 + 12*4 + 12*max(1, len(detalles_lineas)) + 20
        salto_pagina_si_necesario(altura_bloque)

        # Encabezado del reclamo
        c.setFont("Helvetica-Bold", 14)
        nombre_linea = f"{num_cliente} - {nombre} ({sector})"
        for l in wrap_text(nombre_linea, fuente="Helvetica-Bold", tam=14):
            c.drawString(margen_izq, y, l)
            y -= 15

        # Líneas de contenido
        c.setFont("Helvetica", 11)
        for linea in [
            f"Fecha: {fecha_pdf}",
            f"Dirección: {direccion}",
            f"Tel: {telefono} - Precinto: {precinto}".strip(" - "),
            f"Tipo: {tipo}" + (f" - Tec: {tecnico}" if tecnico else ""),
        ]:
            for l in wrap_text(linea, tam=11):
                c.drawString(margen_izq, y, l)
                y -= 12

        # Detalles (pueden ocupar varias líneas)
        if detalles:
            c.setFont("Helvetica", 11)
            for l in detalles_lineas:
                c.drawString(margen_izq, y, f"Detalles: {l}" if l == detalles_lineas[0] else l)
                y -= 12
        else:
            c.drawString(margen_izq, y, "Detalles: ")
            y -= 12

        # Separador
        y -= 6
        c.line(margen_izq, y, width - margen_der, y)
        y -= 15

    agregar_pie_pdf(c, width, height)
    c.save()
    buffer.seek(0)
    return buffer
