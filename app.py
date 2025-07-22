import streamlit as st
import pandas as pd
import datetime
import io
import streamlit_authenticator as stauth
import json

# --- Caricamento credenziali Google da secrets ---
google_creds = json.loads(st.secrets["google"]["credentials"])
# Puoi usare google_creds nel codice per l'accesso a Google Drive, qui solo info demo
st.write("Google Project ID:", google_creds["project_id"])

# --- Configurazione autenticazione ---
auth_config = st.secrets["auth"]

usernames = auth_config["usernames"]
names = auth_config["names"]
passwords = auth_config["passwords"]

authenticator = stauth.Authenticate(
    names,
    usernames,
    passwords,
    "cookie_name_xyz",       # personalizza il nome del cookie
    "signature_key_abc",     # personalizza la firma (stringhe lunghe e casuali)
    cookie_expiry_days=1
)

# --- Login ---
name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status:
    st.sidebar.write(f"Benvenuto, {name}!")

    # Bottone logout nella sidebar
    if st.sidebar.button("Logout"):
        authenticator.logout("Logout", "sidebar")
        st.experimental_rerun()

    # Inizio codice principale (solo dopo login)
    st.set_page_config(page_title="Dashboard Gestione Esami Open Badge", layout="wide")
    st.title("📋 Dashboard Gestione Esami Open Badge")

    uploaded_files = st.file_uploader(
        "Carica i file Excel (open_badge + BookingsReportingData)",
        type=["xlsx", "xls"],
        accept_multiple_files=True
    )

    if uploaded_files and len(uploaded_files) >= 2:
        badge_file = next((f for f in uploaded_files if f.name.startswith("open_badge")), None)
        booking_file = next((f for f in uploaded_files if f.name.startswith("BookingsReportingData")), None)

        if badge_file is None or booking_file is None:
            st.error("⚠️ Carica un file che inizia con 'open_badge' e uno con 'BookingsReportingData'")
            st.stop()

        df_badge = pd.read_excel(badge_file)
        df_booking = pd.read_excel(booking_file)

        # Normalizza colonne
        df_badge.columns = df_badge.columns.astype(str).str.strip().str.upper()
        df_booking.columns = df_booking.columns.astype(str).str.strip()

        st.subheader("📄 Anteprima open_badge")
        st.dataframe(df_badge.head())

        st.subheader("📄 Anteprima BookingsReportingData")
        st.dataframe(df_booking.head())

        needed_badge_cols = ["NOME", "COGNOME", "COD_STATO", "TIPOLOGIA", "CATEGORIA"]
        for c in needed_badge_cols:
            if c not in df_badge.columns:
                st.error(f"⚠️ Colonna '{c}' mancante nel file open_badge")
                st.stop()

        needed_booking_cols = ["Customer Name", "Service", "Date Time"]
        for c in needed_booking_cols:
            if c not in df_booking.columns:
                st.error(f"⚠️ Colonna '{c}' mancante nel file BookingsReportingData")
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

        st.subheader("❌ Utenti NON pagati ma iscritti")
        st.dataframe(df_non_pagati_iscritti[[
            "NOME", "COGNOME", "COD_STATO", "TIPOLOGIA", "CATEGORIA", "Customer Name", "Service", "Date Time"
        ]])

        st.subheader("✅ Utenti pagati e iscritti (con TIPOLOGIA e CATEGORIA)")
        st.dataframe(df_pagati_iscritti[[
            "NOME", "COGNOME", "TIPOLOGIA", "CATEGORIA", "Customer Name", "Service", "Date Time"
        ]])

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

    else:
        st.info("📂 Carica almeno due file Excel: uno 'open_badge...' e uno 'BookingsReportingData...'")

elif authentication_status is False:
    st.error("Username o password errati")
else:
    st.warning("Per favore inserisci nome utente e password")
