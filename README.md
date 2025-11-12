# 📋 Fusion Reclamos App

Sistema integral para la gestión de reclamos técnicos, clientes y operaciones de soporte para empresas de cable e internet.

## 🚀 Características principales

- 📥 **Carga rápida de reclamos técnicos**.
- 🧑‍💻 **Gestión completa de clientes**.
- 📊 **Panel de métricas y visualización de actividad**.
- 🔔 **Notificaciones internas para el personal**.
- 🧾 **Impresión de partes de reclamos en PDF**.
- 📆 **Planificación y seguimiento técnico**.
- ✅ **Cierre de reclamos y seguimiento del historial**.
- 🔐 **Sistema de login con control de permisos por rol**.
- 🌙 **Modo claro / oscuro con persistencia de preferencia**.
- 📲 **Optimizado para uso móvil**.

---

## 🧠 Tecnologías utilizadas

- [Streamlit](https://streamlit.io/) — para la creación de la interfaz interactiva.
- [Google Sheets](https://www.google.com/sheets/about/) — como base de datos en la nube.
- [gspread](https://github.com/burnash/gspread) — para manipular hojas de cálculo de Google.
- [ReportLab](https://www.reportlab.com/) — para generación de PDFs.
- [Pandas](https://pandas.pydata.org/) — para manipulación eficiente de datos.
- [Tenacity](https://tenacity.readthedocs.io/) — para manejo de reintentos automáticos.
- [Streamlit-Lottie](https://github.com/andfanilo/streamlit-lottie) — para animaciones SVG.

---

## ⚙️ Estructura general del sistema

- `app.py`: archivo principal que gestiona la autenticación, el enrutamiento, la interfaz y la carga de datos.
- `components/`: contiene los módulos de cada sección funcional (reclamos, clientes, cierre, notificaciones, etc.).
- `config/settings.py`: variables globales y nombres de hojas/configuraciones del sistema.
- `utils/`: funciones auxiliares como manejo de fechas, generación de PDFs, estilos y APIs.

---

## 🔐 Roles y autenticación

El sistema utiliza control de acceso basado en roles (`admin`, `operador`, etc.). Algunas funciones como la migración de UUIDs solo están disponibles para administradores.

---

## 💾 Persistencia de datos

Toda la información se guarda automáticamente en hojas de cálculo de Google a través de la API de Google Sheets.

Los siguientes datos son gestionados:
- Reclamos técnicos
- Datos de clientes
- Usuarios autorizados
- Notificaciones internas

---

## ✨ Detalles adicionales

- 📱 **Adaptable a pantallas móviles**: el sistema detecta dispositivos móviles y cambia la navegación automáticamente.
- 🔁 **Actualización automática de UUIDs**: permite generar identificadores únicos para reclamos/clientes sin ID.
- 📥 **Caché optimizada y actualizaciones con `st.rerun()`**.
- 🔔 **Campanita de notificaciones** en el sidebar para ver alertas internas.

---

## 🧑‍💻 Autor

Hecho con amor por:  
**[Sebastián Andrés](https://instagram.com/mellamansebax)** 💜

---

## 📌 Notas finales

- Versión actual: `2.3.0`
- Última actualización: `{{AUTO_TIMESTAMP}}`  
- Proyecto en desarrollo interno, no distribuido públicamente.

---

## 📄 Licencia

Este proyecto es de uso interno y no tiene licencia pública por el momento.
