# app_colorato.py — Gestionale Clienti SHT (layout aggiornato: login prima, dashboard KPI, contratti stile coerente)
from __future__ import annotations

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

# ==========================
# CONFIG / COSTANTI
# ==========================
APP_TITLE = "GESTIONALE CLIENTI – SHT"

STORAGE_DIR = Path(
    st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage"))
)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV     = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV   = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV  = STORAGE_DIR / "preventivi.csv"
TEMPLATES_DIR   = STORAGE_DIR / "templates"

EXTERNAL_PROPOSALS_DIR = Path(
    st.secrets.get("storage", {}).get("proposals_dir") or (STORAGE_DIR / "preventivi")
)
EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

# Logo link statico (come richiesto)
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

# 📂 Base URL OneDrive (rimane com’era)
ONEDRIVE_BASE_URL = "https://shtsrlit-my.sharepoint.com/personal/fabio_scaranello_shtsrl_com/Documents/OFFERTE"

CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]
PREVENTIVI_COLS = ["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"]

TEMPLATE_OPTIONS: Dict[str, str] = {
    "Offerta – Centralino": "Offerta_Centralino.docx",
    "Offerta – Varie": "Offerta_Varie.docx",
    "Offerta – A3": "Offerte_A3.docx",
    "Offerta – A4": "Offerte_A4.docx",
}

DURATE_MESI = ["12", "24", "36", "48", "60", "72"]

# ==========================
# UTILS
# ==========================
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
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%d/%m/%Y")

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

# ==========================
# I/O DATI (ripristinato per correggere il NameError)
# ==========================
def load_clienti() -> pd.DataFrame:
    path = CLIENTI_CSV
    if not path.exists():
        st.warning("⚠️ File clienti.csv non trovato, esegui prima estrai_clienti_contratti.py")
        return pd.DataFrame(columns=CLIENTI_COLS + ["NoteCliente"])
    df = pd.read_csv(path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    if "NoteCliente" not in df.columns:
        df["NoteCliente"] = ""
    return df

def save_clienti(df: pd.DataFrame):
    path = CLIENTI_CSV
    df.to_csv(path, index=False, encoding="utf-8-sig")

def load_contratti() -> pd.DataFrame:
    path = CONTRATTI_CSV
    if not path.exists():
        st.warning("⚠️ File contratti_clienti.csv non trovato, esegui prima estrai_clienti_contratti.py")
        return pd.DataFrame(columns=CONTRATTI_COLS)
    df = pd.read_csv(path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio", "DataFine"]:
        df[c] = to_date_series(df[c])
    return df

def save_contratti(df: pd.DataFrame):
    path = CONTRATTI_CSV
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(path, index=False, encoding="utf-8-sig")

# ==========================
# FUNZIONI DI SUPPORTO PREVENTIVI (lasciate come in origine)
# ==========================
def _replace_docx_placeholders(doc: Document, mapping: dict):
    for p in doc.paragraphs:
        for key, val in mapping.items():
            token = f"<<{key}>>"
            if token in p.text:
                inline = p.runs
                for i in range(len(inline)):
                    if token in inline[i].text:
                        inline[i].text = inline[i].text.replace(token, str(val))
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for key, val in mapping.items():
                        token = f"<<{key}>>"
                        if token in p.text:
                            inline = p.runs
                            for i in range(len(inline)):
                                if token in inline[i].text:
                                    inline[i].text = inline[i].text.replace(token, str(val))

def _gen_offerta_number(df_prev: pd.DataFrame, cliente_id: str, ragione_sociale: str) -> str:
    year = datetime.now().year
    safe_name = "".join(ch if ch.isalnum() else "" for ch in str(ragione_sociale))[:8].upper()
    subset = df_prev[df_prev["ClienteID"].astype(str) == str(cliente_id)]
    seq = len(subset) + 1
    numero = f"OFF-{year}-{safe_name}-{seq:03d}"
    return numero

# ==========================
# AUTH
# ==========================
def do_login_fullscreen():
    """Schermata di login a pagina intera, con logo SHT e credenziali centralizzate."""
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    st.markdown(
        f"""
        <div style='display:flex; flex-direction:column; align-items:center; justify-content:center;
                    height:90vh; text-align:center;'>
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

    if "auth_user" in st.session_state:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))
    return ("", "")


# ==========================
# DASHBOARD (layout aggiornato)
# ==========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # Header con logo + titolo
    cols_header = st.columns([0.18, 0.82])
    with cols_header[0]:
        st.image(LOGO_URL, width=120)
    with cols_header[1]:
        st.markdown("<h1 style='margin-top:0;'>SHT – CRM Dashboard</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:grey; margin-top:-10px;'>Panoramica KPI e stato contratti</p>", unsafe_allow_html=True)

    st.divider()

    # KPI
    now = pd.Timestamp.now().normalize()
    total_clients = len(df_cli)
    # uniforma colonna Stato
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())

    # Nuovi contratti nell’anno in corso (da DataInizio)
    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    start_year = pd.Timestamp(year=now.year, month=1, day=1)
    new_contracts = df_ct[(df_ct["DataInizio"].notna()) & (df_ct["DataInizio"] >= start_year) & (df_ct["DataInizio"] <= now)]
    count_new = len(new_contracts)

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

           # Contratti in scadenza (6 mesi) — versione con finestra scrollabile
    st.subheader("📅 Contratti in Scadenza (entro 6 mesi)")

    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    scadenza = df_ct[
        (df_ct["DataFine"].notna()) &
        (df_ct["DataFine"] >= now) &
        (df_ct["DataFine"] <= now + pd.DateOffset(months=6)) &
        (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]

    if scadenza.empty:
        st.info("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        scadenza = scadenza.sort_values("DataFine").merge(
            df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left"
        )
        scadenza["DataFine"] = scadenza["DataFine"].dt.strftime("%d/%m/%Y")

        # container scrollabile
        with st.container():
            st.markdown("""
            <style>
            .scroll-box {
                max-height: 350px;
                overflow-y: scroll;
                border: 1px solid #ddd;
                padding: 8px;
                border-radius: 8px;
                background-color: #fafafa;
            }
            .scad-head {font-weight:600; background:#f0f0f0; padding:6px 10px; border-radius:6px;}
            </style>
            """, unsafe_allow_html=True)

            st.markdown("<div class='scad-head'>Cliente | Contratto | Scadenza | Stato | </div>", unsafe_allow_html=True)
            st.markdown("<div class='scroll-box'>", unsafe_allow_html=True)

            for i, row in scadenza.iterrows():
                col1, col2, col3, col4, col5 = st.columns([0.35, 0.25, 0.2, 0.15, 0.1])
                col1.write(f"**{row['RagioneSociale']}**")
                col2.write(row["NumeroContratto"])
                col3.write(row["DataFine"])
                col4.write(row["Stato"])
                if col5.button("➡️", key=f"open_{i}_{row['ClienteID']}"):
                    st.session_state["selected_client_id"] = row["ClienteID"]
                    st.session_state["nav_target"] = "Contratti"
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    st.divider()



    # Contratti senza data fine (da oggi in poi)
    st.subheader("⏰ Promemoria: Contratti Senza Data Fine (da oggi in poi)")
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

# Helpers Dashboard
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
    # Genera una chiave univoca anche se NumeroContratto o ClienteID sono vuoti o duplicati
    unique_key = f"open_client_{str(row.get('ClienteID'))}_{str(row.get('NumeroContratto'))}_{hash(str(row))}"

    st.markdown(
        f"""
        <div style="
            border: 1px solid #e4e4e4;
            border-radius: 10px;
            padding: 10px 14px;
            margin-bottom: 8px;
            background-color: #fafafa;
        ">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:16px;">
            <div>
              <div style="font-weight:600;">{row.get('RagioneSociale', '')}</div>
              <div style="font-size:13px;">Contratto: {row.get('NumeroContratto', '')}</div>
              <div style="font-size:13px;">Data Inizio: {fmt_date(row.get('DataInizio', ''))} — Data Fine: {fmt_date(row.get('DataFine', ''))}</div>
            </div>
            <div>
              <span style="font-size:12px; color:#666;">Stato: {row.get('Stato','')}</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("🔎 Apri Cliente", key=unique_key):
        st.session_state["selected_client_id"] = row.get("ClienteID")
        st.session_state["nav_target"] = "Contratti"
        st.rerun()


# ==========================
# CLIENTI (come tuo, invariato)
# ==========================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Clienti")

    # Ricerca
    st.markdown("### 🔍 Cerca Cliente")
    search_query = st.text_input("Cerca cliente per nome:")

    if search_query:
        filtered = df_cli[df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)]
    else:
        filtered = df_cli

    if filtered.empty:
        st.warning("Nessun cliente trovato.")
        st.stop()

    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox("Seleziona Cliente", options)
    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    # Anagrafica
    st.markdown(f"### 🏢 {cliente.get('RagioneSociale', '')}")
    st.caption(f"ClienteID: {sel_id}")

    def safe_date_str(val):
        if not val or pd.isna(val):
            return ""
        try:
            return pd.to_datetime(val, dayfirst=True).strftime("%d/%m/%Y")
        except Exception:
            return str(val)

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Indirizzo:** {cliente.get('Indirizzo','')} — {cliente.get('Citta','')} {cliente.get('CAP','')}")
        st.write(f"**Telefono:** {cliente.get('Telefono','')}")
        st.write(f"**Email:** {cliente.get('Email','')}")
        st.write(f"**Partita IVA:** {cliente.get('PartitaIVA','')}")
        st.write(f"**IBAN:** {cliente.get('IBAN','')}")
    with col2:
        st.write(f"**Persona Riferimento 1:** {cliente.get('PersonaRiferimento','')}")
        st.write(f"**Persona Riferimento 2:** {cliente.get('PersonaRiferimento2','')}")
        st.write(f"**Cellulare:** {cliente.get('Cellulare','')}")
        st.write(f"**SDI:** {cliente.get('SDI','')}")
        st.write(f"**Ultimo Recall:** {safe_date_str(cliente.get('UltimoRecall',''))}")
        st.write(f"**Ultima Visita:** {safe_date_str(cliente.get('UltimaVisita',''))}")

    st.divider()

    # Recall e visite
    curr_ult_recall = _parse_italian_date(cliente.get("UltimoRecall", ""))
    curr_ult_visita = _parse_italian_date(cliente.get("UltimaVisita", ""))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        new_ult_recall = st.date_input("Ultimo Recall",
                                       curr_ult_recall.date() if curr_ult_recall else None,
                                       format="DD/MM/YYYY",
                                       key=f"ur_{sel_id}")
    with c3:
        new_ult_visita = st.date_input("Ultima Visita",
                                       curr_ult_visita.date() if curr_ult_visita else None,
                                       format="DD/MM/YYYY",
                                       key=f"uv_{sel_id}")

    next_recall = (pd.to_datetime(new_ult_recall) + timedelta(days=30)).date() if new_ult_recall else None
    next_visita = (pd.to_datetime(new_ult_visita) + timedelta(days=180)).date() if new_ult_visita else None

    with c2:
        st.date_input("Prossimo Recall (auto)", value=next_recall, format="DD/MM/YYYY",
                      key=f"pr_{sel_id}", disabled=True)
    with c4:
        st.date_input("Prossima Visita (auto)", value=next_visita, format="DD/MM/YYYY",
                      key=f"pv_{sel_id}", disabled=True)

    if st.button("💾 Aggiorna Recall/Visite"):
        try:
            idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
            df_cli.loc[idx_row, "UltimoRecall"] = _format_italian_date(pd.to_datetime(new_ult_recall))
            df_cli.loc[idx_row, "UltimaVisita"] = _format_italian_date(pd.to_datetime(new_ult_visita))
            df_cli.loc[idx_row, "ProssimoRecall"] = _format_italian_date(pd.to_datetime(next_recall))
            df_cli.loc[idx_row, "ProssimaVisita"] = _format_italian_date(pd.to_datetime(next_visita))
            save_clienti(df_cli)
            st.success("✅ Recall e Visite aggiornati con successo.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Errore durante aggiornamento Recall/Visite: {e}")

    st.divider()

    # Modifica anagrafica
    st.markdown("### 🧾 Modifica Anagrafica")
    with st.expander("Modifica i dati anagrafici del cliente", expanded=False):
        with st.form("frm_anagrafica"):
            col1, col2, col3 = st.columns(3)
            with col1:
                rag = st.text_input("Ragione Sociale", cliente.get("RagioneSociale", ""))
                ref1 = st.text_input("Persona Riferimento 1", cliente.get("PersonaRiferimento", ""))
                ref2 = st.text_input("Persona Riferimento 2", cliente.get("PersonaRiferimento2", ""))
            with col2:
                indir = st.text_input("Indirizzo", cliente.get("Indirizzo", ""))
                citta = st.text_input("Città", cliente.get("Citta", ""))
                cap = st.text_input("CAP", cliente.get("CAP", ""))
                tel = st.text_input("Telefono", cliente.get("Telefono", ""))
            with col3:
                cell = st.text_input("Cellulare", cliente.get("Cellulare", ""))
                piva = st.text_input("Partita IVA", cliente.get("PartitaIVA", ""))
                sdi = st.text_input("SDI", cliente.get("SDI", ""))
                mail = st.text_input("Email", cliente.get("Email", ""))
                iban = st.text_input("IBAN", cliente.get("IBAN", ""))

            salva_btn = st.form_submit_button("💾 Salva Anagrafica")
            if salva_btn:
                err = False
                if cap and (not cap.isdigit() or len(cap) != 5):
                    st.error("❌ CAP non valido: deve contenere 5 cifre.")
                    err = True
                if piva and (not piva.isdigit() or len(piva) != 11):
                    st.error("❌ Partita IVA non valida: deve contenere 11 cifre.")
                    err = True
                if mail and "@" not in mail:
                    st.error("❌ Email non valida.")
                    err = True

                if not err:
                    idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                    df_cli.loc[idx_row, [
                        "RagioneSociale", "PersonaRiferimento", "PersonaRiferimento2",
                        "Indirizzo", "Citta", "CAP", "Telefono", "Cellulare",
                        "PartitaIVA", "Email", "SDI", "IBAN"
                    ]] = [rag, ref1, ref2, indir, citta, cap, tel, cell, piva, mail, sdi, iban]
                    save_clienti(df_cli)
                    st.success("✅ Anagrafica aggiornata con successo.")
                    st.rerun()

    st.divider()

    # Note cliente
    st.markdown("### 📝 Note Cliente")
    note_attuali = cliente.get("NoteCliente", "")
    nuove_note = st.text_area("Modifica note cliente:", note_attuali, height=180, key=f"note_{sel_id}")
    if st.button("💾 Salva Note"):
        idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx_row, "NoteCliente"] = nuove_note
        save_clienti(df_cli)
        st.success("✅ Note aggiornate.")
        st.rerun()

    st.divider()

    # === Preventivi (identico alla tua logica) ===
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

    def genera_numero_offerta(cliente_nome: str) -> str:
        anno = datetime.now().year
        nome_sicuro = "".join(c for c in cliente_nome if c.isalnum())[:6].upper()
        subset = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
        seq = len(subset) + 1
        return f"OFF-{anno}-{nome_sicuro}-{seq:03d}"

    next_num = genera_numero_offerta(cliente.get("RagioneSociale", ""))

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

                    # sostituzione robusta
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
                                run.font.size = Pt(9 if template == "Offerta A4" else 10)
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
        def _fmt_date_(date_str):
            try:
                return pd.to_datetime(date_str, errors="coerce", dayfirst=True).strftime("%d/%m/%Y")
            except Exception:
                return date_str

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
                    f"<div class='preventivo-info'>Creato il {_fmt_date_(r['DataCreazione'])}</div>"
                    f"</div>", unsafe_allow_html=True
                )
            with col2:
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        st.download_button("⬇️ Scarica", data=f.read(), file_name=file_path.name,
                                           mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                           key=f"dl_{r['NumeroOfferta']}", use_container_width=True)
                else:
                    st.error("❌ File mancante")
            with col3:
                if role == "admin":
                    elimina_key = f"del_{r['NumeroOfferta']}_{i}"
                    if st.button("🗑 Elimina", key=elimina_key, type="secondary", use_container_width=True):
                        try:
                            if file_path.exists():
                                file_path.unlink()
                            df_prev = df_prev.drop(i)
                            df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")
                            st.success(f"🗑 Preventivo '{r['NumeroOfferta']}' eliminato con successo.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Errore durante eliminazione: {e}")

        st.divider()

# Helpers clienti (come avevi)
def _parse_italian_date(value):
    if pd.isna(value) or value == "":
        return None
    try:
        return datetime.strptime(str(value), "%d/%m/%Y")
    except Exception:
        try:
            return pd.to_datetime(value, dayfirst=True)
        except Exception:
            return None

def _format_italian_date(date_val):
    return date_val.strftime("%d/%m/%Y") if pd.notna(date_val) and date_val else ""

# ==========================
# CONTRATTI (Soluzione 2: AgGrid + stile coerente)
# ==========================
def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # Header coerente
    st.markdown("""
    <style>
      .btn-primary {background:#2196F3; color:#fff; padding:6px 10px; border-radius:8px; font-size:14px;}
      .btn-danger  {background:#F44336; color:#fff; padding:6px 10px; border-radius:8px; font-size:14px;}
      .btn-success {background:#009688; color:#fff; padding:6px 10px; border-radius:8px; font-size:14px;}
      .section-hdr {font-size:20px; font-weight:700; margin:6px 0 8px 0;}
    </style>
    """, unsafe_allow_html=True)
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # Preselezione da session_state (quando arrivi da Dashboard → Apri Cliente)
    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str) == str(pre)][0])
        except:
            idx = 0

    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = df_cli.iloc[labels[labels == sel_label].index[0]]["ClienteID"]
    rag_soc = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]["RagioneSociale"]

    # Nuovo contratto (identico nella logica, solo etichette)
    with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            with c1:
                num = st.text_input("Numero Contratto")
            with c2:
                din = st.date_input("Data inizio", format="DD/MM/YYYY")
            with c3:
                durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto", height=100)
            col_nf, col_ni, col_tot = st.columns(3)
            with col_nf:
                nf = st.text_input("NOL_FIN")
            with col_ni:
                ni = st.text_input("NOL_INT")
            with col_tot:
                tot = st.text_input("TotRata")
            if st.form_submit_button("💾 Crea contratto"):
                row = {
                    "ClienteID": str(sel_id),
                    "NumeroContratto": num,
                    "DataInizio": pd.to_datetime(din),
                    "DataFine": pd.to_datetime(din) + pd.DateOffset(months=int(durata)),
                    "Durata": durata,
                    "DescrizioneProdotto": desc,
                    "NOL_FIN": nf,
                    "NOL_INT": ni,
                    "TotRata": tot,
                    "Stato": "aperto"
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([row])], ignore_index=True)
                save_contratti(df_ct)
                st.success("✅ Contratto creato.")
                st.rerun()

    # Tabella contratti (AgGrid) — invariata nella logica, con colori coerenti
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp["TotRata"] = disp["TotRata"].apply(money)
    disp = disp.drop(columns=["ClienteID"], errors="ignore")

    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True)

    # Stile righe in base allo stato (come avevi) + leggero ritocco
    js_code = JsCode("""
    function(params) {
        if (!params.data.Stato) return {};
        const stato = params.data.Stato.toLowerCase();
        if (stato === 'chiuso') {
            return { 'backgroundColor': '#ffebee', 'color': '#b71c1c', 'fontWeight': 'bold' };
        } else if (stato === 'attivo' || stato === 'aperto') {
            return { 'backgroundColor': '#e8f5e9', 'color': '#1b5e20' };
        } else if (stato === 'nuovo') {
            return { 'backgroundColor': '#fff8e1', 'color': '#8a6d00' };
        } else {
            return {};
        }
    }
    """)
    gb.configure_grid_options(getRowStyle=js_code)
    grid_opts = gb.build()

    st.markdown("<div class='section-hdr'>📑 Lista contratti</div>", unsafe_allow_html=True)
    grid_resp = AgGrid(
        disp,
        gridOptions=grid_opts,
        theme="balham",
        height=380,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True
    )

    selected = grid_resp.get("selected_rows", [])
    if isinstance(selected, list) and len(selected) > 0:
        sel = selected[0]
        st.markdown("### 📝 Descrizione completa")
        st.info(sel.get("DescrizioneProdotto", ""), icon="🪶")

    # Gestione stato contratti (pulsanti coerenti)
    st.divider()
    st.markdown("<div class='section-hdr'>⚙️ Stato contratti</div>", unsafe_allow_html=True)
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
        with c2:
            st.caption(f"{r['NumeroContratto']} — {str(r.get('DescrizioneProdotto',''))[:60]}")
        curr = (r["Stato"] or "aperto").lower()
        with c3:
            if curr == "chiuso":
                if st.button("🔓 Riapri", key=f"open_{i}"):
                    df_ct.loc[i, "Stato"] = "aperto"; save_contratti(df_ct); st.rerun()
            else:
                if st.button("❌ Chiudi", key=f"close_{i}"):
                    df_ct.loc[i, "Stato"] = "chiuso"; save_contratti(df_ct); st.rerun()

    # Esportazioni (invariato, con etichette allineate)
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        csv = disp.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📄 Esporta CSV", csv, f"contratti_{rag_soc}.csv", "text/csv")
    with c2:
        try:
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", size=9)
            pdf.cell(0, 8, safe_text(f"Contratti - {rag_soc}"), ln=1, align="C")
            for _, row in disp.iterrows():
                pdf.cell(35, 6, safe_text(row["NumeroContratto"]), 1)
                pdf.cell(25, 6, safe_text(row["DataInizio"]), 1)
                pdf.cell(25, 6, safe_text(row["DataFine"]), 1)
                pdf.cell(20, 6, safe_text(row["Durata"]), 1)
                pdf.cell(80, 6, safe_text(row["DescrizioneProdotto"])[:60], 1)
                pdf.cell(20, 6, safe_text(row["TotRata"]), 1)
                pdf.cell(20, 6, safe_text(row["Stato"]), 1)
                pdf.ln()
            pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
            st.download_button("📘 Esporta PDF", pdf_bytes, f"contratti_{rag_soc}.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Errore PDF: {e}")
# ==========================
# LISTA CLIENTI (nuova pagina con filtri)
# ==========================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Contratti")

    # --- Filtro rapido ---
    st.markdown("### 🔍 Filtra Clienti")
    col1, col2 = st.columns(2)
    with col1:
        filtro_nome = st.text_input("Cerca per nome cliente")
    with col2:
        filtro_citta = st.text_input("Cerca per città")

    # --- Merge Clienti + Contratti ---
    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]], on="ClienteID", how="left")

    # Filtraggio dinamico
    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]

    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")

    merged = merged[["RagioneSociale", "Citta", "NumeroContratto", "DataInizio", "DataFine", "Stato"]].fillna("")

    # --- Conteggio dinamico ---
    st.caption(f"Totale clienti trovati: **{len(merged)}**")

    # --- Visualizzazione tabella ---
    st.dataframe(merged, use_container_width=True, hide_index=True)

    # --- Esportazione CSV ---
    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_clienti_contratti.csv", "text/csv")


# ==========================
# MAIN APP
# ==========================
def main():
    # === LOGIN PRIMA DI TUTTO ===
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    st.sidebar.success(f"Utente: {user} — Ruolo: {role}")

    # Pagine principali + nuova pagina Lista Clienti
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📋 Lista Clienti": page_lista_clienti
    }

    # Imposta pagina predefinita e navigazione
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio(
        "Menu",
        list(PAGES.keys()),
        index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0
    )

    # Caricamento dati
    df_cli = load_clienti()
    df_ct = load_contratti()

    # Routing verso la pagina selezionata
    PAGES[page](df_cli, df_ct, role)


if __name__ == "__main__":
    main()
