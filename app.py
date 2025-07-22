import streamlit as st
import streamlit_authenticator as stauth
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pandas as pd
import yaml
from yaml.loader import SafeLoader

# ---------- AUTENTICAZIONE ----------
# Configurazione utenti caricata da secrets
config = {
    "credentials": {
        "usernames": {
            "utente1": {
                "name": "Utente Uno",
                "password": st.secrets["AUTH_PASSWORD1"]  # da secrets
            },
            "utente2": {
                "name": "Utente Due",
                "password": st.secrets["AUTH_PASSWORD2"]
            }
        }
    },
    "cookie": {
        "name": "streamlit_auth",
        "key": st.secrets["COOKIE_KEY"],
        "expiry_days": 1
    },
    "preauthorized": {}
}

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"]
)

name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status is False:
    st.error("Nome utente o password errati")
elif authentication_status is None:
    st.warning("Inserisci nome utente e password")
elif authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"Accesso effettuato come {name}")

    # ---------- ACCESSO A GOOGLE DRIVE ----------
    st.title("Gestione Dati da Google Drive")

    # Caricamento credenziali dal secrets
    google_creds = json.loads(st.secrets["GOOGLE_CREDENTIALS"])

    # Autenticazione Google Drive/Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
    client = gspread.authorize(creds)

    # ---------- ESEMPIO: CARICA UN FILE GOOGLE SHEET ----------
    try:
        sheet = client.open("NOME_DEL_TUO_FILE").sheet1  # cambia nome file
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        st.subheader("Contenuto del file:")
        st.dataframe(df)
    except Exception as e:
        st.error(f"Errore nel caricamento del file: {e}")
