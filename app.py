# ============================================================
# CRM SHT CLIENTI - v6
# Autore: Fabio Scaranello / SHT srl
# Gestione Clienti, Contratti e Preventivi
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

# ------------------------------------------------------------
# CONFIGURAZIONE E STILE
# ------------------------------------------------------------
st.set_page_config(page_title="CRM SHT CLIENTI", layout="wide")
PRIMARY_COLOR = "#0078A0"

st.markdown(f"""
    <style>
    h1, h2, h3, h4, h5, h6 {{ color: {PRIMARY_COLOR} !important; }}
    div.stButton > button:first-child {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.4em 1em;
    }}
    div.stButton > button:hover {{
        background-color: #005f80;
        color: white;
    }}
    .metric-label, .stMetricLabel {{ color: {PRIMARY_COLOR} !important; }}
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# COLONNE CLIENTI
# ------------------------------------------------------------
EXPECTED_CLIENTI_COLS = [
    "ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","UltimaVisita","Note"
]

def ensure_clienti_cols(df):
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df

# ------------------------------------------------------------
# FUNZIONI DI SUPPORTO
# ------------------------------------------------------------
DATE_FMT = "%d/%m/%Y"

def fmt_date(d):
    if pd.isna(d) or d in [None, ""]:
        return ""
    if isinstance(d, str):
        for f in ["%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%m/%d/%Y"]:
            try:
                return datetime.strptime(d,f).strftime(DATE_FMT)
            except:
                pass
        return d
    if isinstance(d,(datetime,date)):
        return d.strftime(DATE_FMT)
    return str(d)

def parse_date_str(s):
    if not s:
        return None
    for f in ["%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%m/%d/%Y"]:
        try:
            return datetime.strptime(s.strip(),f).date()
        except:
            pass
    return None

def euro(x):
    try:
        v = float(x)
    except:
        return "-"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    return f"€ {s}"

def parse_money(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("€","").replace(" ","")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return np.nan

def valid_cap(s): return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ", "").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

# ------------------------------------------------------------
# NUMERAZIONE PREVENTIVI
# ------------------------------------------------------------
def next_quote_number(df_quotes):
    today = date.today()
    yy = today.strftime("%Y")
    if df_quotes.empty:
        return f"PRE-{yy}-0001"
    mask = df_quotes["Numero"].fillna("").str.startswith(f"PRE-{yy}-")
    last = df_quotes[mask]["Numero"].sort_values().iloc[-1] if mask.any() else None
    if not last:
        return f"PRE-{yy}-0001"
    n = int(last.split("-")[-1])
    return f"PRE-{yy}-{n+1:04d}"

# ------------------------------------------------------------
# CARICAMENTO / SALVATAGGIO CSV
# ------------------------------------------------------------
@st.cache_data
def load_csv_with_fallback(main_path, fallbacks):
    p = Path(main_path)
    if p.exists():
        return pd.read_csv(p)
    for fb in fallbacks:
        if Path(fb).exists():
            return pd.read_csv(fb)
    return pd.DataFrame()

@st.cache_data
def load_data():
    clienti = load_csv_with_fallback("clienti.csv", [])
    clienti = ensure_clienti_cols(clienti)
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")

    contratti = load_csv_with_fallback("contratti.csv", [])
    for c in ["ClienteID","NumeroContratto","DataInizio","DataFine",
              "Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]:
        if c not in contratti.columns:
            contratti[c] = None
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = contratti[col].apply(parse_money)

    preventivi = load_csv_with_fallback("preventivi.csv", [])
    if preventivi.empty:
        preventivi = pd.DataFrame(columns=["ClienteID","Numero","Data","Template","FileName"])
    return clienti, contratti, preventivi

def save_csv(df, path):
    df.to_csv(path, index=False)

# ------------------------------------------------------------
# AUTENTICAZIONE
# ------------------------------------------------------------
USERS = {
    "admin": {"password": "admin", "role": "Admin"},
    "op": {"password": "op", "role": "Operatore"},
    "view": {"password": "view", "role": "Viewer"},
}

def do_login():
    st.title("Accesso CRM SHT CLIENTI")
    u = st.text_input("Utente", value="admin")
    p = st.text_input("Password", type="password", value="admin")
    if st.button("Entra"):
        if u in USERS and USERS[u]["password"] == p:
            st.session_state["auth_user"] = u
            st.session_state["auth_role"] = USERS[u]["role"]
            st.success(f"Benvenuto, {u}!")
            st.rerun()
        else:
            st.error("Credenziali non valide.")

# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------
def sidebar(role):
    st.sidebar.title("CRM SHT CLIENTI")
    st.sidebar.caption("Gestione Clienti, Contratti e Preventivi • v6")
    return st.sidebar.radio(
        "Naviga",
        ["Dashboard","Scheda Cliente","Contratti","Impostazioni"]
    )

# ------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------
def monthly_revenue_open(contratti: pd.DataFrame) -> float:
    df = contratti.copy()
    open_mask = df["Stato"].astype(str).str.lower().eq("aperto")
    tot = df.loc[open_mask, "TotRata"]
    fallback = df.loc[open_mask, "NOL_FIN"].fillna(0) + df.loc[open_mask, "NOL_INT"].fillna(0)
    tot = tot.where(~tot.isna(), fallback)
    return float(tot.fillna(0).sum())

def render_dashboard(clienti, contratti):
    st.title("🧭 CRM SHT CLIENTI")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clienti", len(clienti))
    c2.metric("Contratti", len(contratti))
    c3.metric("Aperti", int((contratti["Stato"].fillna('').str.lower()=="aperto").sum()))
    c4.metric("Rata mensile (aperti)", euro(monthly_revenue_open(contratti)))

    st.markdown("### 🔍 Ricerca cliente per Ragione Sociale o Città")
    query = st.text_input("Cerca cliente", placeholder="Es. Rossi SRL o Verona")
    if query:
        ql = query.lower()
        risultati = clienti[
            clienti.fillna("").apply(
                lambda r: ql in str(r["RagioneSociale"]).lower() or ql in str(r["Città"]).lower(),
                axis=1
            )
        ]
        if risultati.empty:
            st.warning("Nessun cliente trovato.")
        else:
            sel = st.selectbox("Seleziona cliente", risultati["RagioneSociale"].tolist())
            scelto = risultati[risultati["RagioneSociale"] == sel].iloc[0]
            if st.button("Apri scheda cliente"):
                st.session_state["open_client"] = int(scelto["ClienteID"])
                st.session_state["next_page"] = "Scheda Cliente"
                st.rerun()

# ------------------------------------------------------------
# SCHEDA CLIENTE
# ------------------------------------------------------------
def render_scheda_cliente(clienti, contratti, preventivi, role):
    st.title("👤 Scheda Cliente")
    if "open_client" not in st.session_state:
        st.info("Seleziona un cliente dalla Dashboard.")
        return
    det_id = int(st.session_state["open_client"])
    if det_id not in clienti["ClienteID"].values:
        st.warning("Cliente non trovato.")
        return
    c = clienti.loc[clienti["ClienteID"] == det_id].iloc[0]
    st.markdown(f"### 🏢 {c['RagioneSociale']}")
    st.caption(f"{c['Città'] or ''}  ·  📞 {c['Telefono'] or '-'}  ·  📧 {c['Email'] or '-'}")
    st.write(f"**P.IVA:** {c['PartitaIVA'] or '-'}  ·  **IBAN:** {c['IBAN'] or '-'}  ·  **SDI:** {c['SDI'] or '-'}")
    st.info(c["Note"] or "–")
    ct = contratti[contratti["ClienteID"] == det_id].copy().fillna("")
    st.markdown("### 📃 Contratti del cliente")
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        st.dataframe(ct, use_container_width=True, height=350)

# ------------------------------------------------------------
# IMPOSTAZIONI
# ------------------------------------------------------------
def render_settings(clienti, contratti, preventivi, role):
    st.title("⚙️ Impostazioni e salvataggio dati")

    c1, c2, c3 = st.columns(3)
    if c1.button("💾 Salva clienti.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["clienti"], "clienti.csv")
        st.toast("clienti.csv salvato.", icon="✅")
    if c2.button("💾 Salva contratti.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["contratti"], "contratti.csv")
        st.toast("contratti.csv salvato.", icon="✅")
    if c3.button("💾 Salva preventivi.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["preventivi"], "preventivi.csv")
        st.toast("preventivi.csv salvato.", icon="✅")

    st.markdown("---")
    st.subheader("📂 Carica file CSV aggiornati")
    colA, colB = st.columns(2)
    uc = colA.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None and role != "Viewer":
        df = pd.read_csv(uc)
        df = ensure_clienti_cols(df)
        st.session_state["clienti"] = df
        st.toast(f"{len(df)} clienti caricati.", icon="✅")
        st.rerun()
    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None and role != "Viewer":
        df = pd.read_csv(ut)
        for c in ["NOL_FIN","NOL_INT","TotRata"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["DataInizio"] = df["DataInizio"].apply(fmt_date)
        df["DataFine"] = df["DataFine"].apply(fmt_date)
        st.session_state["contratti"] = df
        st.toast(f"{len(df)} contratti caricati.", icon="✅")
        st.rerun()

    st.markdown("---")
    st.subheader("📄 Template preventivi (Word .docx)")
    tpls = st.file_uploader("Carica template .docx", type=["docx"], accept_multiple_files=True)
    if tpls:
        st.session_state["quote_templates"] = [(f.name, f.read()) for f in tpls]
        st.toast(f"{len(tpls)} template caricati.", icon="✅")

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if "auth_user" not in st.session_state:
    do_login()
    st.stop()

role = st.session_state.get("auth_role", "Viewer")
clienti, contratti, preventivi = load_data()
clienti = ensure_clienti_cols(clienti)
if "clienti" not in st.session_state:
    st.session_state["clienti"] = clienti.copy()
if "contratti" not in st.session_state:
    st.session_state["contratti"] = contratti.copy()
if "preventivi" not in st.session_state:
    st.session_state["preventivi"] = preventivi.copy()

page = sidebar(role)
if "next_page" in st.session_state:
    page = st.session_state["next_page"]
    del st.session_state["next_page"]

if page == "Dashboard":
    render_dashboard(st.session_state["clienti"], st.session_state["contratti"])
elif page == "Scheda Cliente":
    render_scheda_cliente(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
elif page == "Contratti":
    st.dataframe(st.session_state["contratti"], use_container_width=True)
else:
    render_settings(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
