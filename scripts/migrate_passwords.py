import sys
import os
import streamlit as st
import gspread
from google.oauth2 import service_account
from passlib.context import CryptContext
import pandas as pd

# Agrega el directorio raíz al path para poder importar módulos de la aplicación
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import SHEET_ID, WORKSHEET_USUARIOS, COLUMNAS_USUARIOS

# --- Configuración ---
# Asegúrate de que tus secretos están en un lugar accesible para el script.
# Este script asume que lo ejecutas en un entorno donde st.secrets está disponible.
# Si no, deberás cargar los secretos de otra manera (ej. python-dotenv, variables de entorno).

# Contexto de hasheo (debe ser idéntico al de la aplicación)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_google_sheets_client():
    """Conecta con Google Sheets usando las credenciales de st.secrets."""
    try:
        creds_info = st.secrets["gcp_service_account"]
        creds = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"❌ Error de conexión con Google Sheets: {e}")
        return None

def migrate_passwords():
    """
    Script para migrar contraseñas de texto plano a hashes.
    - Lee la hoja de 'usuarios'.
    - Si existe una columna 'password' y una 'password_hash', procede.
    - Itera sobre las filas. Si hay una contraseña en 'password' y 'password_hash' está vacío,
      genera el hash y lo escribe en la columna 'password_hash'.
    """
    print("🚀 Iniciando migración de contraseñas...")

    client = get_google_sheets_client()
    if not client:
        return

    try:
        spreadsheet = client.open_by_key(SHEET_ID)
        worksheet = spreadsheet.worksheet(WORKSHEET_USUARIOS)

        print(f"✅ Conectado a la hoja '{WORKSHEET_USUARIOS}'.")

        headers = worksheet.row_values(1)
        try:
            password_col_index = headers.index('password') + 1
            password_hash_col_index = headers.index('password_hash') + 1
        except ValueError as e:
            print(f"❌ Error: Falta una columna requerida en la hoja: {e}")
            print("Asegúrate de que las columnas 'password' y 'password_hash' existan.")
            return

        users_data = worksheet.get_all_records()
        df_users = pd.DataFrame(users_data)

        updates = []

        for index, row in df_users.iterrows():
            plaintext_password = row.get('password')
            # Usa .get() para evitar errores si la columna no existe para una fila
            hashed_password = row.get('password_hash')

            # Migra solo si hay una contraseña en texto plano y no hay un hash
            if plaintext_password and (not hashed_password or pd.isna(hashed_password)):
                print(f"  - Migrando contraseña para el usuario: {row.get('username')}...")

                new_hash = pwd_context.hash(str(plaintext_password))

                # Prepara la actualización para el batch de forma dinámica
                # +2 porque gspread es 1-based y hay una fila de cabecera
                row_number = index + 2
                # Convierte el índice de columna a la letra de columna (A, B, C...)
                col_letter = gspread.utils.rowcol_to_a1(1, password_hash_col_index).rstrip('1')

                cell_to_update = f'{col_letter}{row_number}'
                updates.append({
                    'range': cell_to_update,
                    'values': [[new_hash]],
                })

        if not updates:
            print("✅ No hay contraseñas nuevas para migrar. ¡Todo está actualizado!")
            return

        print(f"\n✨ Se migrarán {len(updates)} contraseñas. Aplicando cambios...")

        # Actualiza la hoja en un solo batch
        worksheet.batch_update(updates)

        print("\n🎉 ¡Migración completada exitosamente!")
        print("IMPORTANTE: Ahora puedes considerar eliminar la columna 'password' de tu Google Sheet para mayor seguridad.")

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ Error: No se encontró la hoja de cálculo con ID: {SHEET_ID}")
    except gspread.exceptions.WorksheetNotFound:
        print(f"❌ Error: No se encontró la hoja de trabajo '{WORKSHEET_USUARIOS}'.")
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado: {e}")

if __name__ == "__main__":
    # Para ejecutar este script:
    # 1. Asegúrate de tener tus secretos en `.streamlit/secrets.toml`.
    # 2. Instala las dependencias: pip install -r requirements.txt
    # 3. Ejecuta desde la raíz del proyecto: streamlit run scripts/migrate_passwords.py
    st.title("Asistente de Migración de Contraseñas")

    st.warning("Este script modificará tu base de datos de usuarios en Google Sheets. **Haz una copia de seguridad de tu hoja 'usuarios' antes de continuar.**")

    if st.button("🚀 Iniciar Migración de Contraseñas"):
        with st.spinner("Conectando y migrando... por favor, espera."):
            migrate_passwords()
        st.success("¡Proceso finalizado! Revisa la consola para ver los detalles.")
