# =====================================
# app.py — Gestionale Clienti SHT (2025)
# Layout aggiornato: login a pagina intera, dashboard KPI, contratti coerenti
# =====================================
from __future__ import annotations
import streamlit as st
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")
# stile globale per allargare la pagina
st.markdown("""
<style>
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}
</style>
""", unsafe_allow_html=True)
import os
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple, Dict

import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# =====================================
# CONFIG / COSTANTI
# =====================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"

STORAGE_DIR = Path(
    st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage"))
)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"
TEMPLATES_DIR = STORAGE_DIR / "templates"

# Logo statico
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

# Directory preventivi esterna
EXTERNAL_PROPOSALS_DIR = STORAGE_DIR / "preventivi"
EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "NoteCliente"
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]

DURATE_MESI = ["12", "24", "36", "48", "60", "72"]

# =====================================
# UTILS
# =====================================
def as_date(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    if isinstance(x, (pd.Timestamp, pd.NaT.__class__)):
        return x
    s = str(x).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return pd.NaT
    d = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(d):
        d = pd.to_datetime(s, errors="coerce")
    return d

def to_date_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series([], dtype="datetime64[ns]")
    return s.map(as_date)

def fmt_date(d) -> str:
    """Restituisce una data in formato DD/MM/YYYY, qualunque sia il tipo di input."""
    import datetime as dt
    if d is None or d == "" or (isinstance(d, float) and pd.isna(d)):
        return ""
    try:
        if isinstance(d, (dt.date, dt.datetime, pd.Timestamp)):
            return pd.to_datetime(d).strftime("%d/%m/%Y")
        parsed = pd.to_datetime(str(d), errors="coerce", dayfirst=True)
        if pd.isna(parsed):
            return ""
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return ""


def money(x):
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        return f"{v:,.2f} €"
    except Exception:
        return ""

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def s(x) -> str:
    try:
        return "" if pd.isna(x) else str(x)
    except Exception:
        return "" if x is None else str(x)

def date_input_opt(label: str, current, *, key: str):
    d = as_date(current)
    try:
        if pd.isna(d):
            return st.date_input(label, key=key, format="DD/MM/YYYY")
        else:
            return st.date_input(label, value=d.to_pydatetime().date(), key=key, format="DD/MM/YYYY")
    except TypeError:
        if pd.isna(d):
            return st.date_input(label, key=key)
        else:
            return st.date_input(label, value=d.to_pydatetime().date(), key=key)

# =====================================
# I/O DATI
# =====================================
def load_clienti() -> pd.DataFrame:
    path = CLIENTI_CSV
    if not path.exists():
        st.warning("⚠️ File clienti.csv non trovato.")
        return pd.DataFrame(columns=CLIENTI_COLS)

    # Legge il CSV come testo
    df = pd.read_csv(path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    df.columns = [c.strip() for c in df.columns]

    # Normalizza i nomi delle colonne
    # CORREZIONE: Mappa 'ultima visita' (minuscolo) e 'Ultimo Recall' con lo spazio
    rename_map = {
        "ultima visita": "UltimaVisita", # CORREZIONE
        "Ultimo Recall": "UltimoRecall", # CORREZIONE: Assicura che la colonna con lo spazio sia mappata
        "Città": "Citta",
        "Prossimo Recall": "ProssimoRecall",
        "Prossima Visita": "ProssimaVisita",
        # Lascio gli altri nomi mappati dal CSV come 'UltimoRecall' e 'UltimaVisita'
    }
    df = df.rename(columns=rename_map)
    df = ensure_columns(df, CLIENTI_COLS)

    # 🔧 Conversione pulita e tollerante per le colonne data
    def parse_date_safe(val):
        if not isinstance(val, str) or val.strip() == "":
            return pd.NaT
        val = val.strip()
        # ignora simboli o testo non interpretabile
        if any(x in val.lower() for x in ["*", "?", "vedi", "stia", "null", "none", "nan", "nat"]):
            return pd.NaT
        
        # Tenta prima la conversione standard (gestisce AAAA-MM-GG HH:MM:SS)
        d = pd.to_datetime(val, errors="coerce")
        
        # Se fallisce, tenta con il formato Giorno/Mese/Anno
        if pd.isna(d):
            d = pd.to_datetime(val, errors="coerce", dayfirst=True)
            
        return d

    # CORREZIONE: Applico il parsing alle colonne rinominate
    for col in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        if col in df.columns:
            df[col] = df[col].map(parse_date_safe)
            # Rimuove l'orario, mantiene solo la data
            df[col] = df[col].dt.date

    return df




def save_clienti(df: pd.DataFrame):
    df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti() -> pd.DataFrame:
    path = CONTRATTI_CSV
    if not path.exists():
        st.warning("⚠️ File contratti_clienti.csv non trovato.")
        return pd.DataFrame(columns=CONTRATTI_COLS)
    df = pd.read_csv(path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio", "DataFine"]:
        df[c] = to_date_series(df[c])
    return df

def save_contratti(df: pd.DataFrame):
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
def read_raw_client_date(cliente_id: str, column: str) -> str:
    """Legge la data dal file clienti.csv e la restituisce in formato DD/MM/YYYY (senza orario)."""
    try:
        df_raw = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
        df_raw.columns = [c.strip() for c in df_raw.columns]
        # CORREZIONE: Includi i nomi delle colonne grezze dal CSV
        alias = {
            "UltimoRecall": ["Ultimo Recall", "UltimoRecall"], # Nome originale e rinominato
            "UltimaVisita": ["ultima visita", "Ultima Visita", "UltimaVisita"] # Nome originale (minuscolo) e rinominati
        }
        target_cols = alias.get(column, [column])
        # La logica di read_raw_client_date è corretta se i nomi sono corretti
        # Uso Nome Foglio come fallback per ClienteID se non c'è ClienteID
        id_col = "ClienteID" if "ClienteID" in df_raw.columns else "Nome Foglio"
        row = df_raw[df_raw[id_col].astype(str) == str(cliente_id)]
        if row.empty:
            # Riprova con Nome Foglio se non ha funzionato con ClienteID
            if "ClienteID" in df_raw.columns and id_col == "ClienteID":
                try:
                    nome_foglio = df_raw[df_raw["Nome Foglio"].astype(str) == str(cliente_id)].iloc[0]["Nome Foglio"]
                    row = df_raw[df_raw["Nome Foglio"].astype(str) == str(nome_foglio)]
                except:
                    pass
                    
        if row.empty:
            return ""
            
        for colname in target_cols:
            if colname in row.columns:
                val = str(row.iloc[0][colname]).strip()
                if not val:
                    return ""
                d = pd.to_datetime(val, errors="coerce", dayfirst=True)
                if pd.isna(d):
                    d = pd.to_datetime(val, errors="coerce") # Tentativo senza dayfirst
                    if pd.isna(d):
                        return val
                return d.strftime("%d/%m/%Y")
        return ""
    except Exception:
        return ""


# =====================================
# LOGIN (pagina intera)
# =====================================
def do_login_fullscreen():
    """Login a schermo intero — scompare dopo l'accesso."""
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    # ✅ Se l'utente è già loggato, NON mostrare il form
    if "auth_user" in st.session_state and st.session_state["auth_user"]:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))

    # --- Mostra solo se non loggato ---
    st.markdown(
        f"""
        <div style='display:flex; flex-direction:column; align-items:center; justify-content:center;
                    height:100vh; text-align:center;'>
            <img src="{LOGO_URL}" width="220" style="margin-bottom:25px;">
            <h2 style='margin-bottom:10px;'>🔐 Accesso al Gestionale SHT</h2>
            <p style='color:grey; font-size:14px;'>Inserisci le tue credenziali per continuare</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    username = st.text_input("👤 Utente", key="login_user")
    password = st.text_input("🔒 Password", type="password", key="login_pwd")
    col1, col2, col3 = st.columns([0.4, 0.2, 0.4])
    with col2:
        login_btn = st.button("Entra", use_container_width=True)

    if login_btn:
        if username in users and password == users[username].get("password"):
            st.session_state["auth_user"] = username
            st.session_state["auth_role"] = users[username].get("role", "viewer")
            st.success("✅ Accesso effettuato!")
            st.rerun()
        else:
            st.error("❌ Credenziali errate o utente inesistente.")

    # Se non autenticato, blocca tutto qui
    st.stop()


# =====================================
# DASHBOARD (con KPI + Recall/Visite TMK)
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # Header con logo e titolo
    cols_header = st.columns([0.18, 0.82])
    with cols_header[0]:
        st.image(LOGO_URL, width=120)
    with cols_header[1]:
        st.markdown("<h1 style='margin-top:0;'>SHT – CRM Dashboard</h1>", unsafe_allow_html=True)
       

    st.divider()

    # === DATI BASE ===
    now = pd.Timestamp.now().normalize()
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())

    # Nuovi contratti nell’anno corrente
    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    start_year = pd.Timestamp(year=now.year, month=1, day=1)
    new_contracts = df_ct[
        (df_ct["DataInizio"].notna())
        & (df_ct["DataInizio"] >= start_year)
        & (df_ct["DataInizio"] <= now)
    ]
    count_new = len(new_contracts)

    # === KPI BOX ===
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#2196F3"), unsafe_allow_html=True)
    with col2:
        st.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#009688"), unsafe_allow_html=True)
    with col3:
        st.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#F44336"), unsafe_allow_html=True)
    with col4:
        st.markdown(kpi_card("Nuovi contratti (anno corrente)", count_new, "⭐", "#FFC107"), unsafe_allow_html=True)

    st.divider()

  
       # === TMK: Recall e Visite ===
    st.subheader("📞 Attività TMK (Recall e Visite)")

    # ✅ Conversione date (formato italiano)
    # Le date sono già in formato `date` dopo load_clienti, ma le convertiamo in datetime
    # per poter usare DateOffset nel filtraggio.
    df_cli["ProssimoRecall"] = pd.to_datetime(df_cli["ProssimoRecall"], errors="coerce")
    df_cli["ProssimaVisita"] = pd.to_datetime(df_cli["ProssimaVisita"], errors="coerce")
    df_cli["UltimoRecall"]   = pd.to_datetime(df_cli["UltimoRecall"], errors="coerce")
    df_cli["UltimaVisita"]   = pd.to_datetime(df_cli["UltimaVisita"], errors="coerce")



    recall_prossimi = df_cli[
        (df_cli["ProssimoRecall"].notna()) &
        (df_cli["ProssimoRecall"] >= now) &
        (df_cli["ProssimoRecall"] <= now + pd.DateOffset(days=7))
    ].sort_values("ProssimoRecall")

    visite_prossime = df_cli[
        (df_cli["ProssimaVisita"].notna()) &
        (df_cli["ProssimaVisita"] >= now) &
        (df_cli["ProssimaVisita"] <= now + pd.DateOffset(days=30))
    ].sort_values("ProssimaVisita")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### 🔁 Recall in scadenza (entro 7 giorni)")
        if recall_prossimi.empty:
            st.info("✅ Nessun recall programmato nei prossimi 7 giorni.")
        else:
            for _, row in recall_prossimi.iterrows():
                cliente = row.get("RagioneSociale", "")
                data_r = fmt_date(row.get("ProssimoRecall", ""))
                if st.button(f"📞 {cliente} – {data_r}", key=f"rec_{row['ClienteID']}"):
                    st.session_state["selected_client_id"] = row["ClienteID"]
                    st.session_state["nav_target"] = "Clienti"
                    st.rerun()

    with c2:
        st.markdown("### 👥 Visite programmate (entro 30 giorni)")
        if visite_prossime.empty:
            st.info("✅ Nessuna visita programmata nei prossimi 30 giorni.")
        else:
            for _, row in visite_prossime.iterrows():
                cliente = row.get("RagioneSociale", "")
                data_v = fmt_date(row.get("ProssimaVisita", ""))
                if st.button(f"🗓 {cliente} – {data_v}", key=f"vis_{row['ClienteID']}"):
                    st.session_state["selected_client_id"] = row["ClienteID"]
                    st.session_state["nav_target"] = "Clienti"
                    st.rerun()

    st.divider()

    # === CONTRATTI IN SCADENZA ===
    st.subheader("📅 Contratti in Scadenza (entro 6 mesi)")
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    scadenza = df_ct[
        (df_ct["DataFine"].notna())
        & (df_ct["DataFine"] >= now)
        & (df_ct["DataFine"] <= now + pd.DateOffset(months=6))
        & (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]

    if scadenza.empty:
        st.info("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        scadenza = scadenza.sort_values("DataFine").merge(
            df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left"
        )
        scadenza["DataFine"] = scadenza["DataFine"].dt.strftime("%d/%m/%Y")

        # Stile migliorato
        st.markdown("""
        <style>
        .scroll-box { max-height: 380px; overflow-y: auto; border: 1px solid #ddd;
                      border-radius: 8px; background: #fafafa; padding: 8px; }
        .scad-header { display: grid; grid-template-columns: 38% 22% 20% 12% 8%;
                       font-weight: 600; background: #f0f0f0; border-radius: 6px;
                       padding: 6px 10px; margin-bottom: 6px; font-size: 15px; }
        .scad-row { display: grid; grid-template-columns: 38% 22% 20% 12% 8%;
                    align-items: center; padding: 6px 10px; border-bottom: 1px solid #eee;
                    font-size: 14px; }
        .scad-row:hover { background-color: #f9f9f9; }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("<div class='scad-header'><div>Cliente</div><div>Contratto</div><div>Scadenza</div><div>Stato</div><div style='text-align:center;'>Apri</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='scroll-box'>", unsafe_allow_html=True)

        for i, row in scadenza.iterrows():
            st.markdown(
                f"""
                <div class='scad-row'>
                    <div><b>{row['RagioneSociale']}</b></div>
                    <div>{row['NumeroContratto'] or '-'}</div>
                    <div>{row['DataFine']}</div>
                    <div>{row['Stato']}</div>
                    <div style='text-align:center;'>➡️</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("Apri", key=f"open_{i}_{row['ClienteID']}"):
                st.session_state["selected_client_id"] = row["ClienteID"]
                st.session_state["nav_target"] = "Contratti"
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # === CONTRATTI SENZA DATA FINE ===
    st.subheader("⏰ Promemoria: Contratti Senza Data Fine (da oggi in poi)")
    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce") # Converti per il filtraggio
    senza_fine = df_ct[
        (df_ct["DataInizio"].notna())
        & (df_ct["DataInizio"] >= now)
        & (df_ct["DataFine"].isna())
        & (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]
    if senza_fine.empty:
        st.info("✅ Nessun nuovo contratto senza data fine.")
    else:
        senza_fine = senza_fine.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        for _, row in senza_fine.iterrows():
            create_contract_card(row)


# =====================================
# HELPER CARD / KPI
# =====================================
def kpi_card(label, value, icon, bg_color):
    return f"""
    <div style="
        background-color: {bg_color};
        padding: 18px;
        border-radius: 12px;
        text-align: center;
        color: white;
    ">
        <div style="font-size: 26px; margin-bottom: 6px;">{icon}</div>
        <div style="font-size: 22px; font-weight: 700;">{value}</div>
        <div style="font-size: 14px;">{label}</div>
    </div>
    """

def create_contract_card(row):
    unique_key = f"open_client_{str(row.get('ClienteID'))}_{str(row.get('NumeroContratto'))}_{hash(str(row))}"
    st.markdown(
        f"""
        <div style="border: 1px solid #e4e4e4; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; background-color: #fafafa;">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:16px;">
            <div>
              <div style="font-weight:600;">{row.get('RagioneSociale', '')}</div>
              <div style="font-size:13px;">Contratto: {row.get('NumeroContratto', '')}</div>
              <div style="font-size:13px;">Data Inizio: {fmt_date(row.get('DataInizio', ''))} — Data Fine: {fmt_date(row.get('DataFine', ''))}</div>
            </div>
            <div><span style="font-size:12px; color:#666;">Stato: {row.get('Stato','')}</span></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    if st.button("🔎 Apri Cliente", key=unique_key):
        st.session_state["selected_client_id"] = row.get("ClienteID")
        st.session_state["nav_target"] = "Contratti"
        st.rerun()
# =====================================
# CLIENTI
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Clienti")

    st.markdown("### 🔍 Cerca Cliente")
    search_query = st.text_input("Cerca cliente per nome:")
    if search_query:
        filtered = df_cli[df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)]
    else:
        filtered = df_cli

    if filtered.empty:
        st.warning("Nessun cliente trovato.")
        return

    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox("Seleziona Cliente", options)
    # Aggiungi la logica per trovare il ClienteID basato sul nome, presupponendo che sia unico
    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]


    st.markdown(f"## 🏢 {cliente.get('RagioneSociale', '')}")
    st.caption(f"ClienteID: {sel_id}")

    # === BLOCCO INFO RAPIDE (visibile sempre) ===
    indirizzo = cliente.get("Indirizzo", "")
    citta = cliente.get("Citta", "")
    cap = cliente.get("CAP", "")
    persona = cliente.get("PersonaRiferimento", "")
    telefono = cliente.get("Telefono", "")
    cell = cliente.get("Cell", "")

    # Date correttamente formattate
    ult_rec = fmt_date(as_date(cliente.get("UltimoRecall", "")))
    pross_rec = fmt_date(as_date(cliente.get("ProssimoRecall", "")))
    ult_vis = fmt_date(as_date(cliente.get("UltimaVisita", "")))
    pross_vis = fmt_date(as_date(cliente.get("ProssimaVisita", "")))

    # --- Info anagrafiche principali ---
    st.markdown(
        f"""
        <div style='font-size:15px; line-height:1.7;'>
            <b>📍 Indirizzo:</b> {indirizzo} – {citta} {cap}<br>
            <b>🧑‍💼 Referente:</b> {persona}<br>
            <b>📞 Telefono:</b> {telefono} — <b>📱 Cell:</b> {cell}
        </div>
        """,
        unsafe_allow_html=True
    )

    # --- RIGA DATE: Ultimo / Prossimo Recall e Visita ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"**⏰ Ultimo Recall:** {ult_rec or '—'}")
    with col2:
        st.markdown(f"**📅 Prossimo Recall:** {pross_rec or '—'}")
    with col3:
        st.markdown(f"**👣 Ultima Visita:** {ult_vis or '—'}")
    with col4:
        st.markdown(f"**🗓️ Prossima Visita:** {pross_vis or '—'}")

    st.divider()

    # ===== EXPANDER ANAGRAFICA EDITABILE =====
    with st.expander("✏️ Modifica anagrafica completa"):
        with st.form(key=f"frm_anagrafica_{sel_id}_{hash(sel_rag)}"):

            def safe_date(val):
                d = as_date(val)
                if pd.isna(d):
                    return None
                return d.date()

            col1, col2 = st.columns(2)
            with col1:
                indirizzo = st.text_input("📍 Indirizzo", cliente.get("Indirizzo", ""))
                citta = st.text_input("🏙️ Città", cliente.get("Citta", ""))
                cap = st.text_input("📮 CAP", cliente.get("CAP", ""))
                telefono = st.text_input("📞 Telefono", cliente.get("Telefono", ""))
                cell = st.text_input("📱 Cellulare", cliente.get("Cell", ""))
                email = st.text_input("✉️ Email", cliente.get("Email", ""))
                persona = st.text_input("👤 Persona Riferimento", cliente.get("PersonaRiferimento", ""))
            with col2:
                piva = st.text_input("💼 Partita IVA", cliente.get("PartitaIVA", ""))
                iban = st.text_input("🏦 IBAN", cliente.get("IBAN", ""))
                sdi = st.text_input("📡 SDI", cliente.get("SDI", ""))
                # Uso safe_date(..) con l'input corretto (None per data non selezionata)
                ultimo_recall = st.date_input("⏰ Ultimo Recall", value=safe_date(cliente.get("UltimoRecall")), format="DD/MM/YYYY")
                prossimo_recall = st.date_input("📅 Prossimo Recall", value=safe_date(cliente.get("ProssimoRecall")), format="DD/MM/YYYY")
                ultima_visita = st.date_input("👣 Ultima Visita", value=safe_date(cliente.get("UltimaVisita")), format="DD/MM/YYYY")
                prossima_visita = st.date_input("🗓️ Prossima Visita", value=safe_date(cliente.get("ProssimaVisita")), format="DD/MM/YYYY")


            salva_btn = st.form_submit_button("💾 Salva modifiche")
            if salva_btn:
                idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx, "Indirizzo"] = indirizzo
                df_cli.loc[idx, "Citta"] = citta
                df_cli.loc[idx, "CAP"] = cap
                df_cli.loc[idx, "Telefono"] = telefono
                df_cli.loc[idx, "Cell"] = cell
                df_cli.loc[idx, "Email"] = email
                df_cli.loc[idx, "PersonaRiferimento"] = persona
                df_cli.loc[idx, "PartitaIVA"] = piva
                df_cli.loc[idx, "IBAN"] = iban
                df_cli.loc[idx, "SDI"] = sdi
                # Qui salviamo il campo data come oggetto date/None, che poi fmt_date() formatterà o lascerà vuoto.
                # E' importante che le colonne del DF contengano oggetti date o pd.NaT per consistenza.
                df_cli.loc[idx, "UltimoRecall"] = ultimo_recall
                df_cli.loc[idx, "ProssimoRecall"] = prossimo_recall
                df_cli.loc[idx, "UltimaVisita"] = ultima_visita
                df_cli.loc[idx, "ProssimaVisita"] = prossima_visita
                save_clienti(df_cli)
                st.success("✅ Anagrafica aggiornata.")
                st.rerun()

    st.divider()

    # ===== NOTE CLIENTE =====
    st.markdown("### 📝 Note Cliente")
    note_attuali = cliente.get("NoteCliente", "")
    nuove_note = st.text_area("Modifica note cliente:", note_attuali, height=180, key=f"note_{sel_id}")
    if st.button("💾 Salva Note"):
        idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx_row, "NoteCliente"] = nuove_note
        save_clienti(df_cli)
        st.success("✅ Note aggiornate.")
        st.rerun()



    # =======================================================
    # SEZIONE PREVENTIVI DOCX
    # =======================================================
    st.divider()
    st.markdown("### 🧾 Crea Nuovo Preventivo")

    from docx.shared import Pt
    TEMPLATES_DIR = STORAGE_DIR / "templates"
    EXTERNAL_PROPOSALS_DIR = STORAGE_DIR / "preventivi"
    EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

    TEMPLATE_OPTIONS_LOCAL = {
        "Offerta A4": "Offerte_A4.docx",
        "Offerta A3": "Offerte_A3.docx",
        "Centralino": "Offerta_Centralino.docx",
        "Varie": "Offerta_Varie.docx",
    }

    prev_path = STORAGE_DIR / "preventivi.csv"
    if prev_path.exists():
        df_prev = pd.read_csv(prev_path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])

    # === Funzione per generare numero preventivo sequenziale ===
    def genera_numero_offerta(cliente_nome: str, cliente_id: str) -> str:
        anno = datetime.now().year
        nome_sicuro = "".join(c for c in cliente_nome if c.isalnum())[:6].upper()
        subset = df_prev[df_prev["ClienteID"].astype(str) == str(cliente_id)]
        seq = len(subset) + 1
        return f"OFF-{anno}-{nome_sicuro}-{seq:03d}"

    next_num = genera_numero_offerta(cliente.get("RagioneSociale", ""), sel_id)

    with st.form("frm_new_prev"):
        num = st.text_input("Numero Offerta", next_num)
        nome_file = st.text_input("Nome File (es. Offerta_ACME.docx)")
        template = st.selectbox("Template", list(TEMPLATE_OPTIONS_LOCAL.keys()))
        submitted = st.form_submit_button("💾 Genera Preventivo")

        if submitted:
            try:
                template_path = TEMPLATES_DIR / TEMPLATE_OPTIONS_LOCAL[template]
                if not nome_file.strip():
                    nome_file = f"{num}.docx"
                if not nome_file.lower().endswith(".docx"):
                    nome_file += ".docx"

                output_path = EXTERNAL_PROPOSALS_DIR / nome_file

                if not template_path.exists():
                    st.error(f"❌ Template non trovato: {template_path}")
                else:
                    doc = Document(template_path)
                    mapping = {
                        "CLIENTE": cliente.get("RagioneSociale", ""),
                        "INDIRIZZO": cliente.get("Indirizzo", ""),
                        "CITTA": cliente.get("Citta", "") or cliente.get("Città", ""),
                        "NUMERO_OFFERTA": num,
                        "DATA": datetime.now().strftime("%d/%m/%Y"),
                    }

                    # Sostituzione dei segnaposto <<CHIAVE>>
                    for p in doc.paragraphs:
                        full_text = "".join(run.text for run in p.runs)
                        modified = False
                        for key, val in mapping.items():
                            token = f"<<{key}>>"
                            if token in full_text:
                                full_text = full_text.replace(token, str(val))
                                modified = True
                        if modified:
                            for run in p.runs:
                                run.text = ""
                            p.runs[0].text = full_text
                            for run in p.runs:
                                run.font.size = Pt(10)
                            p.alignment = 0

                    doc.save(output_path)
                    st.success(f"✅ Preventivo salvato: {output_path.name}")

                    nuovo = {
                        "ClienteID": sel_id,
                        "NumeroOfferta": num,
                        "Template": TEMPLATE_OPTIONS_LOCAL[template],
                        "NomeFile": nome_file,
                        "Percorso": str(output_path),
                        "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([nuovo])], ignore_index=True)
                    df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")

                    st.toast("✅ Preventivo aggiunto al database", icon="📄")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante la creazione del preventivo: {e}")

    st.divider()
    st.markdown("### 📂 Elenco Preventivi Cliente")

    prev_cli = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        prev_cli = prev_cli.sort_values(by="DataCreazione", ascending=False)

        st.markdown("""
        <style>
         .preventivo-card {border:1px solid #ddd; border-radius:10px; padding:8px 14px; margin-bottom:8px; background:#f9f9f9;}
         .preventivo-header {font-weight:600; color:#222;}
         .preventivo-info {font-size:0.9rem; color:#444;}
        </style>""", unsafe_allow_html=True)

        for i, r in prev_cli.iterrows():
            file_path = Path(r["Percorso"])
            col1, col2, col3 = st.columns([0.5, 0.3, 0.2])
            with col1:
                st.markdown(
                    f"<div class='preventivo-card'>"
                    f"<div class='preventivo-header'>{r['NumeroOfferta']}</div>"
                    f"<div class='preventivo-info'>{r['Template']}</div>"
                    f"<div class='preventivo-info'>Creato il {r['DataCreazione']}</div>"
                    f"</div>", unsafe_allow_html=True
                )
            with col2:
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "⬇️ Scarica",
                            data=f.read(),
                            file_name=file_path.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{r['NumeroOfferta']}",
                            use_container_width=True
                        )
                else:
                    st.error("❌ File mancante")
            with col3:
                if role == "admin":
                    if st.button("🗑 Elimina", key=f"del_{r['NumeroOfferta']}_{i}"):
                        try:
                            if file_path.exists():
                                file_path.unlink()
                            df_prev = df_prev.drop(i)
                            df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")
                            st.success(f"🗑 Preventivo '{r['NumeroOfferta']}' eliminato.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Errore eliminazione: {e}")


# =====================================
# CONTRATTI (AgGrid + gestione coerente)
# =====================================
def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str) == str(pre)][0])
        except:
            idx = 0

    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    # Correzione: assicurati che l'indice sia valido per loc
    sel_idx_df = labels[labels == sel_label].index
    if sel_idx_df.empty:
        st.warning("Cliente non trovato nel DataFrame.")
        return

    sel_id = df_cli.loc[sel_idx_df[0], "ClienteID"]
    rag_soc = df_cli.loc[sel_idx_df[0], "RagioneSociale"]

    with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
        with st.form("frm_new_co"):
            # Inserisci qui il resto del codice della funzione page_contratti
            pass
