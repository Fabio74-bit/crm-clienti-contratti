
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

st.set_page_config(page_title="CRM Clienti & Contratti — v3 FIX4", layout="wide")

DATE_FMT = "%d/%m/%Y"

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

# --- NUMERIC NORMALIZER (handles '1.234,56', '€ 123,45', spaces, etc.) ---
def numify(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return 0.0
    # remove euro and spaces
    s = s.replace("€","").replace(" ", "")
    # thousand sep . and decimal , -> convert to dot
    if "," in s and "." in s:
        # assume '.' thousands, ',' decimals
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        # european decimal
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def status_class(s):
    s = str(s or "").strip().lower()
    if s == "chiuso": return "closed"
    if s == "aperto": return "open"
    if s == "sospeso": return "suspended"
    return "unknown"

def euro(x):
    v = numify(x)
    if v == 0: return ""
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    return f"€ {s}"

EXPECTED_CLIENTI_COLS = ["ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]
def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df)==0:
        return pd.DataFrame(columns=EXPECTED_CLIENTI_COLS)
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df

def valid_cap(s):  return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ", "").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

@st.cache_data
def load_csv_with_fallback(main_path, fallbacks):
    p = Path(main_path)
    if p.exists(): return pd.read_csv(p)
    for fb in fallbacks:
        if Path(fb).exists():
            return pd.read_csv(fb)
    return pd.DataFrame()

@st.cache_data
def load_data():
    clienti = load_csv_with_fallback("clienti.csv", ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    clienti = ensure_clienti_cols(clienti)
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")
    clienti = clienti[EXPECTED_CLIENTI_COLS]

    ctr_cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    contratti = load_csv_with_fallback("contratti.csv", ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    for c in ctr_cols:
        if c not in contratti.columns: contratti[c] = None
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    # normalize money columns robustly
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = contratti[col].apply(numify)
    contratti["Stato"] = contratti["Stato"].astype(str).replace({"nan":""})
    contratti = contratti[ctr_cols]
    return clienti, contratti

USERS = {"admin":{"password":"admin","role":"Admin"},"op":{"password":"op","role":"Operatore"},"view":{"password":"view","role":"Viewer"}}
def do_login():
    st.title("Accesso CRM")
    u = st.text_input("Utente", value="admin")
    p = st.text_input("Password", type="password", value="admin")
    if st.button("Entra"):
        if u in USERS and USERS[u]["password"]==p:
            st.session_state["auth_user"]=u; st.session_state["auth_role"]=USERS[u]["role"]; st.rerun()
        else:
            st.error("Credenziali non valide.")

if "auth_user" not in st.session_state:
    do_login(); st.stop()
role = st.session_state.get("auth_role","Viewer")

clienti, contratti = load_data()
st.session_state.setdefault("clienti", clienti.copy())
st.session_state.setdefault("contratti", contratti.copy())

# --------------- UI ---------------
st.sidebar.title("CRM")
page = st.sidebar.radio("Naviga", ["Clienti","Contratti"])

def monthly_revenue_open_client(contratti, cid):
    df = contratti[(contratti["ClienteID"]==int(cid)) & (contratti["Stato"].str.lower()=="aperto")]
    # sum robust with numify
    return float(sum(df["TotRata"].apply(numify)))

if page=="Clienti":
    st.title("👥 Clienti")
    dfc = st.session_state["clienti"]
    if len(dfc)==0:
        st.info("Nessun cliente caricato."); st.stop()
    cid = st.number_input("Apri scheda ClienteID", min_value=int(dfc["ClienteID"].min()), max_value=int(dfc["ClienteID"].max()), step=1, value=int(dfc["ClienteID"].min()))
    row = dfc[dfc["ClienteID"]==int(cid)].iloc[0]

    # --- ANAGRAFICA (include Persona di riferimento) ---
    st.markdown(f"### {row['RagioneSociale']}")
    a1,a2 = st.columns(2)
    with a1:
        st.write(f"**Persona di riferimento:** {row['NomeCliente'] or ''}")
        st.write(f"**Indirizzo:** {row['Indirizzo'] or ''}")
        st.write(f"**Città:** {row['Città'] or ''}  **CAP:** {row['CAP'] or ''}")
        st.write(f"**Telefono:** {row['Telefono'] or ''}")
        st.write(f"**Email:** {row['Email'] or ''}")
    with a2:
        st.write(f"**Partita IVA:** {row['PartitaIVA'] or ''}")
        st.write(f"**IBAN:** {row['IBAN'] or ''}")
        st.write(f"**SDI:** {row['SDI'] or ''}")
        st.write(f"**Ultimo Recall:** {row['UltimoRecall'] or ''}")
        st.write(f"**Prossimo Recall:** {row['ProssimoRecall'] or ''}")
        st.write(f"**Ultima Visita:** {row['UltimaVisita'] or ''}")
        st.write(f"**Prossima Visita:** {row['ProssimaVisita'] or ''}")
    if (row["Note"] or "") != "":
        st.info(row["Note"])

    # metriche corrette
    ct = st.session_state["contratti"]
    st.metric("Rata mensile (aperti)", euro(monthly_revenue_open_client(ct, cid)))

else:
    st.title("📃 Contratti per cliente")
    name_map = dict(zip(clienti["ClienteID"], clienti["RagioneSociale"]))
    opts = [(int(cid), nm) for cid,nm in zip(clienti["ClienteID"], clienti["RagioneSociale"])]
    labels = [f"{cid} — {nm}" for cid,nm in opts]
    sel = st.selectbox("Seleziona cliente", labels)
    sel_cid = int(sel.split(" — ")[0])
    df = st.session_state["contratti"]
    df = df[df["ClienteID"]==sel_cid].copy()
    df_display = df.copy()
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        df_display[col] = df_display[col].apply(lambda x: euro(x))
    st.dataframe(df_display, use_container_width=True)
