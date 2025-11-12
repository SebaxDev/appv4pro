# components/resumen_jornada.py

import streamlit as st
import pandas as pd
from utils.date_utils import ahora_argentina, format_fecha

def render_resumen_jornada(df_reclamos):
    """Muestra un resumen conciso con los reclamos del día, pendientes y en curso."""
    st.markdown("---")
    st.markdown("### 📊 Resumen General")

    if df_reclamos.empty:
        st.info("No hay datos de reclamos para mostrar.")
        return

    try:
        # Hacemos una copia para evitar modificar el dataframe original
        df = df_reclamos.copy()

        # Asegurar que la columna de fecha y hora esté en formato datetime
        # Usamos errors='coerce' para manejar posibles errores de formato
        df["Fecha y hora"] = pd.to_datetime(df["Fecha y hora"], dayfirst=True, errors='coerce')

        # 1. Reclamos cargados hoy
        # Nos aseguramos de comparar fechas sin tener en cuenta la zona horaria para evitar errores
        hoy = ahora_argentina().date()
        reclamos_hoy = df[df["Fecha y hora"].dt.date == hoy]

        # 2. Reclamos pendientes
        # Usamos .str.strip().str.lower() para una comparación robusta
        pendientes = df[df["Estado"].str.strip().str.lower() == "pendiente"]

        # 3. Reclamos en curso
        en_curso = df[df["Estado"].str.strip().str.lower() == "en curso"]

        # Mostrar las métricas en tres columnas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="📝 Reclamos de Hoy", value=len(reclamos_hoy))
        with col2:
            st.metric(label="⏳ Pendientes", value=len(pendientes))
        with col3:
            st.metric(label="⚙️ En Curso", value=len(en_curso))

        # 👷 SECCIÓN DE TÉCNICOS - INTEGRACIÓN DEL NUEVO CÓDIGO
        st.markdown("### 👷 Reclamos en curso por técnicos")

        if not en_curso.empty and "Técnico" in en_curso.columns:
            en_curso["Técnico"] = en_curso["Técnico"].fillna("").astype(str)
            en_curso = en_curso[en_curso["Técnico"].str.strip() != ""]

            en_curso["tecnicos_set"] = en_curso["Técnico"].apply(
                lambda x: tuple(sorted([t.strip().upper() for t in x.split(",") if t.strip()]))
            )

            conteo_grupos = en_curso.groupby("tecnicos_set").size().reset_index(name="Cantidad")

            if not conteo_grupos.empty:
                st.markdown("#### Distribución de trabajo:")
                for fila in conteo_grupos.itertuples():
                    tecnicos = ", ".join(fila.tecnicos_set)
                    st.markdown(f"- 👥 **{tecnicos}**: {fila.Cantidad} reclamos")

                reclamos_antiguos = en_curso.sort_values("Fecha y hora").head(3)
                if not reclamos_antiguos.empty:
                    st.markdown("#### ⏳ Reclamos más antiguos aún en curso:")
                    for _, row in reclamos_antiguos.iterrows():
                        fecha_formateada = format_fecha(row["Fecha y hora"])
                        st.markdown(
                            f"- **{row['Nombre']}** ({row['Nº Cliente']}) - "
                            f"Desde: {fecha_formateada} - "
                            f"Técnicos: {row['Técnico']}"
                        )
            else:
                st.info("No hay técnicos asignados actualmente a reclamos en curso.")
        else:
            st.info("No hay reclamos en curso en este momento.")

    except Exception as e:
        st.error(f"Ocurrió un error al generar el resumen: {e}")
        st.exception(e)  # Para debugging si es necesario