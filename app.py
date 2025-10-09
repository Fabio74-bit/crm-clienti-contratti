import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

st.set_page_config(page_title="CRM Clienti & Contratti — v3", layout="wide")

# =========================
# Column Expectations
# =========================
EXPECTED_CLIENTI_COLS = [
    "ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]

def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Garantisce che tutte le colonne cliente esistano, anche se i CSV sono vuoti."""
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df

# =========================
# Helpers & Config
# =========================
DATE_FMT = "%d/%m/%Y"  # dd/mm/yyyy

def fmt_date(d):
    if pd.isna(d) or d is None or d == "":
        return ""
    if isinstance(d, str):
        for f in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]:
            try:
                return datetime.strptime(d, f).strftime(DATE_FMT)
            except Exception:
                pass
        return d
    if isinstance(d, (datetime, date)):
        return d.strftime(DATE_FMT)
    return str(d)

def parse_date_str(s):
    if not s:
        return None
    s = s.strip()
    for f in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"]:
        try:
            return datetime.strptime(s, f).date()
        except Exception:
            pass
    return None

def status_class(s):
    s = (s or "").strip().lower()
    if s == "chiuso":
        return "closed"
    if s == "aperto":
        return "open"
    if s == "sospeso":
        return "suspended"
    return "unknown"

def status_chip(s):
    m = status_class(s)
    color = {"open":"#16a34a","closed":"#b91c1c","suspended":"#d97706","unknown":"#64748b"}[m]
    return f"<span style='background:{color}22;color:{color};padding:2px 8px;border-radius:999px;font-size:12px'>{s or '-'}</span>"

def euro(x):
    try:
        v = float(x)
    except Exception:
        return "-"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    return f"€ {s}"

# =========================
# Validators
# =========================
def valid_cap(s): return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ", "").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

# =========================
# Quote numbering
# =========================
def next_quote_number(df_quotes: pd.DataFrame) -> str:
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

# =========================
# Data Loading
# =========================
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
    cli_cols = EXPECTED_CLIENTI_COLS
    clienti = load_csv_with_fallback("clienti.csv", ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    clienti = ensure_clienti_cols(clienti)
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")

    ctr_cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    contratti = load_csv_with_fallback("contratti.csv", ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    for c in ctr_cols:
        if c not in contratti.columns:
            contratti[c] = None
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = pd.to_numeric(contratti[col], errors="coerce")

    q_cols = ["ClienteID","Numero","Data","Template","FileName"]
    preventivi = load_csv_with_fallback("preventivi.csv", [])
    if preventivi.empty:
        preventivi = pd.DataFrame(columns=q_cols)
    for c in q_cols:
        if c not in preventivi.columns:
            preventivi[c] = None
    preventivi = preventivi[q_cols]

    return clienti, contratti, preventivi

def save_csv(df, path):
    df.to_csv(path, index=False)

# =========================
# Auth
# =========================
USERS = {
    "admin": {"password": "admin", "role": "Admin"},
    "op": {"password": "op", "role": "Operatore"},
    "view": {"password": "view", "role": "Viewer"},
}

def do_login():
    st.title("Accesso CRM")
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

# =========================
# Attachments
# =========================
if "attachments" not in st.session_state:
    st.session_state["attachments"] = {}

# =========================
# Sidebar
# =========================
def sidebar(role):
    st.sidebar.title("CRM")
    st.sidebar.caption("v3 • validazioni, allegati, preventivi, Excel/print")
    return st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti","Impostazioni"])

# =========================
# Pages
# =========================
def monthly_revenue_open(contratti: pd.DataFrame) -> float:
    df = contratti.copy()
    return float(df[df["Stato"].fillna("").str.lower()=="aperto"]["TotRata"].fillna(0).sum())

def render_dashboard(clienti, contratti):
    clienti = ensure_clienti_cols(clienti)
    st.title("📊 Dashboard")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Clienti", len(clienti))
    c2.metric("Contratti", len(contratti))
    c3.metric("Aperti", int((contratti["Stato"].fillna("").str.lower()=="aperto").sum()))
    c4.metric("Rata mensile (aperti)", euro(monthly_revenue_open(contratti)))
    st.subheader("Prossimi promemoria")
    rem = clienti[["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]].copy()
    st.dataframe(rem, use_container_width=True)

def render_clienti(clienti, contratti, preventivi, role):
    clienti = ensure_clienti_cols(clienti)
    st.title("👥 Clienti")
    editable = role in ["Admin","Operatore"]
    list_tab, new_tab, edit_tab = st.tabs(["📄 Elenco", "➕ Nuovo", "✏️ Modifica / ❌ Elimina"])

    # --- Elenco clienti ---
    with list_tab:
        q = st.text_input("Cerca (ragione sociale / città / telefono / P.IVA / SDI)")
        df = clienti.copy()
        if q:
            ql = q.lower()
            cols = ["RagioneSociale","Città","Telefono","PartitaIVA","SDI"]
            df = df[df.fillna("").apply(lambda r: any(ql in str(r[c]).lower() for c in cols), axis=1)]
        st.dataframe(
            df[["ClienteID","RagioneSociale","Città","Telefono","PartitaIVA","SDI"]]
            .sort_values("RagioneSociale"),
            use_container_width=True,
            height=380
        )

    # ... (continua con il resto del tuo codice, invariato)
    # Tutte le altre funzioni (nuovo cliente, modifica, contratti, impostazioni, ecc.)
    # rimangono identiche: non serve toccarle.
    # L’importante è aver aggiunto ensure_clienti_cols() nei punti chiave.

# =========================
# Main
# =========================
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
if page == "Dashboard":
    render_dashboard(st.session_state["clienti"], st.session_state["contratti"])
elif page == "Clienti":
    render_clienti(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
elif page == "Contratti":
    render_contratti(st.session_state["clienti"], st.session_state["contratti"], role)
else:
    render_settings(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
