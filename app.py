import streamlit as st
import pandas as pd
import datetime
import io
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# === NUOVE LIBRERIE ===
from streamlit_option_menu import option_menu
from streamlit_lottie import st_lottie
import hydralit_components as hc
import plotly.express as px
import requests

# === FUNZIONE PER CARICARE LOTTIE ===
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# === LOGIN MANUALE ===
VALID_USERS = st.secrets["users"]

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.set_page_config(page_title="Login", layout="centered")
    st.title("🔒 Login richiesto")

    username = st.text_input("Nome utente")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in VALID_USERS and VALID_USERS[username] == password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("❌ Credenziali non valide.")

    if not st.session_state.authenticated:
        st.stop()

# Siamo autenticati qui in poi

# Bottone logout
if st.button("Logout"):
    st.session_state.authenticated = False
    st.rerun()

# === CONFIGURAZIONE STREAMLIT ===
st.set_page_config(page_title="Dashboard Gestione Esami Open Badge", layout="wide")

# === MENU LATERALE ===
with st.sidebar:
    selected = option_menu(
        "Menu",
        ["Home", "Analisi File", "Statistiche", "Info"],
        icons=["house", "folder", "bar-chart", "info-circle"],
        menu_icon="cast",
        default_index=0,
    )

# === ANIMAZIONE LOTTIE SU HOME ===
if selected == "Home":
    st.title("📋 Dashboard Gestione Esami Open Badge")
    lottie_url = "https://assets1.lottiefiles.com/packages/lf20_jcikwtux.json"
    lottie_json = load_lottieurl(lottie_url)
    if lottie_json:
        st_lottie(lottie_json, height=250, key="lottie-home")
    st.success("Benvenuto nella dashboard interattiva!")

# === CREDENZIALI GOOGLE ===
creds_json_str = st.secrets["google"]["credentials"]
creds_dict = json.loads(creds_json_str)
credentials = service_account.Credentials.from_service_account_info(
    creds_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
)
drive_service = build('drive', 'v3', credentials=credentials)

if selected == "Analisi File":
    st.info("📁 Inserisci l'ID della cartella Google Drive che contiene i file Excel.")
    folder_id = st.text_input("ID Cartella Drive", help="L'ID è la parte finale dell'URL della cartella condivisa.")

    files = []
    if folder_id:
        try:
            results = drive_service.files().list(
                q=f"'{folder_id}' in parents and mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'",
                fields="files(id, name)"
            ).execute()
            files = results.get('files', [])
            if not files:
                st.warning("⚠️ Nessun file Excel trovato nella cartella.")
        except Exception as e:
            st.error(f"Errore nell'accesso alla cartella: {e}")

    if files:
        file_names = [f['name'] for f in files]
        selected_files = st.multiselect("Seleziona i file Excel da analizzare", file_names)

        if selected_files:
            excel_dfs = {}
            for f in files:
                if f['name'] in selected_files:
                    file_id = f['id']
                    fh = io.BytesIO()
                    request = drive_service.files().get_media(fileId=file_id)
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                    fh.seek(0)
                    try:
                        df = pd.read_excel(fh)
                        excel_dfs[f['name']] = df
                    except Exception as e:
                        st.error(f"Errore nel leggere il file {f['name']}: {e}")

            badge_file = next((name for name in excel_dfs if name.startswith("open_badge")), None)
            booking_file = next((name for name in excel_dfs if name.startswith("BookingsReportingData")), None)

            if badge_file is None or booking_file is None:
                st.error("⚠️ Devi selezionare almeno un file che inizia con 'open_badge' e uno che inizia con 'BookingsReportingData'")
                st.stop()

            df_badge = excel_dfs[badge_file]
            df_booking = excel_dfs[booking_file]

            df_badge.columns = df_badge.columns.astype(str).str.strip().str.upper()
            df_booking.columns = df_booking.columns.astype(str).str.strip()

            st.subheader(f"📄 Anteprima {badge_file}")
            st.dataframe(df_badge.head())

            st.subheader(f"📄 Anteprima {booking_file}")
            st.dataframe(df_booking.head())

            needed_badge_cols = ["NOME", "COGNOME", "COD_STATO", "TIPOLOGIA", "CATEGORIA"]
            for c in needed_badge_cols:
                if c not in df_badge.columns:
                    st.error(f"⚠️ Colonna '{c}' mancante nel file {badge_file}")
                    st.stop()

            needed_booking_cols = ["Customer Name", "Service", "Date Time"]
            for c in needed_booking_cols:
                if c not in df_booking.columns:
                    st.error(f"⚠️ Colonna '{c}' mancante nel file {booking_file}")
                    st.stop()

            df_badge["NOME_COGNOME"] = (
                df_badge["NOME"].astype(str).str.strip() + " " + df_badge["COGNOME"].astype(str).str.strip()
            ).str.lower()

            df_booking["CUSTOMER_NAME_KEY"] = df_booking["Customer Name"].astype(str).str.strip().str.lower()
            df_booking_filtered = df_booking[df_booking["CUSTOMER_NAME_KEY"] != ""]

            df_join = pd.merge(
                df_badge,
                df_booking_filtered,
                left_on="NOME_COGNOME",
                right_on="CUSTOMER_NAME_KEY",
                how="inner",
                suffixes=('_badge', '_booking')
            )

            df_non_pagati_iscritti = df_join[
                df_join["COD_STATO"].astype(str).str.upper().str.strip() == "NON PAGATO"
            ]

            df_pagati_iscritti = df_join[
                df_join["COD_STATO"].astype(str).str.upper().str.strip() == "PAGATO"
            ]

            # === CARD RIASSUNTIVE (Hydralit) ===
            card_data = [
                {"title": "Non Pagati Iscritti", "content": len(df_non_pagati_iscritti), "icon": "❌"},
                {"title": "Pagati Iscritti", "content": len(df_pagati_iscritti), "icon": "✅"},
                {"title": "Totale Iscritti", "content": len(df_join), "icon": "📊"},
            ]
            hc.info_card(card_data, columns=3)

            st.subheader("❌ Utenti NON pagati ma iscritti")
            st.dataframe(df_non_pagati_iscritti[[
                "NOME", "COGNOME", "COD_STATO", "TIPOLOGIA", "CATEGORIA", "Customer Name", "Service", "Date Time"
            ]])

            st.subheader("✅ Utenti pagati e iscritti (con TIPOLOGIA e CATEGORIA)")
            st.dataframe(df_pagati_iscritti[[
                "NOME", "COGNOME", "TIPOLOGIA", "CATEGORIA", "Customer Name", "Service", "Date Time"
            ]])

            # === SEZIONE STATISTICHE ===
            if selected == "Statistiche":
                st.subheader("📊 Statistiche personalizzate")
                all_cols = list(df_join.columns)
                exclude_cols = ["NOME_COGNOME", "CUSTOMER_NAME_KEY"]
                selectable_cols = [c for c in all_cols if c not in exclude_cols]

                st.markdown("Seleziona le colonne da includere nel report delle statistiche:")

                selected_stats_cols = []
                cols_per_row = 6
                num_rows = (len(selectable_cols) + cols_per_row - 1) // cols_per_row

                for row_i in range(num_rows):
                    cols = st.columns(cols_per_row)
                    for col_i in range(cols_per_row):
                        idx = row_i * cols_per_row + col_i
                        if idx >= len(selectable_cols):
                            break
                        col_name = selectable_cols[idx]
                        checked = cols[col_i].checkbox(f"{col_name}", key=f"stat_{col_name}")
                        if checked:
                            selected_stats_cols.append(col_name)

                if not selected_stats_cols:
                    st.info("Seleziona almeno una colonna per visualizzare la tabella delle statistiche.")
                    stats_table = pd.DataFrame()
                else:
                    stats_table = df_join[selected_stats_cols]
                    st.dataframe(stats_table)

                    # === GRAFICO PLOTLY ===
                    if len(selected_stats_cols) >= 2:
                        fig = px.histogram(df_join, x=selected_stats_cols[0], color=selected_stats_cols[1])
                        st.plotly_chart(fig, use_container_width=True)

                # Download report Excel
                def to_excel():
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df_non_pagati_iscritti.to_excel(writer, sheet_name="Non Pagati Iscritti", index=False)
                        df_pagati_iscritti.to_excel(writer, sheet_name="Pagati Iscritti", index=False)
                        if not stats_table.empty:
                            stats_table.to_excel(writer, sheet_name="Statistiche", index=False)
                        else:
                            pd.DataFrame().to_excel(writer, sheet_name="Statistiche")
                    return output.getvalue()

                excel_data = to_excel()

                st.download_button(
                    label="📥 Scarica Report Excel",
                    data=excel_data,
                    file_name=f"Report_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

if selected == "Info":
    st.info("🔎 Inserisci l'ID di una cartella Drive pubblica contenente file .xlsx e seleziona i file da analizzare")

# Firma
st.markdown(
    """
    <div style='position: fixed; bottom: 0; left: 0; padding: 10px; font-size: 0.8em; color: gray;'>
        V.3.0.0 Created By <span style='color: red;'>Giorgio Sangiorgi</span><br>
        V.2.0.0 Powered by Google Drive API
    </div>
    """,
    unsafe_allow_html=True
)
