
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

st.set_page_config(page_title="CRM Clienti & Contratti — v3 FIX8", layout="wide")

# =========================
# Helpers
# =========================
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

def numify(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return 0.0
    s = s.replace("€", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def euro(x):
    v = numify(x)
    if v == 0: return ""
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"

def status_class(s):
    s = str(s or "").strip().lower()
    if s == "chiuso": return "closed"
    if s == "aperto": return "open"
    if s == "sospeso": return "suspended"
    return "unknown"

EXPECTED_CLIENTI_COLS = ["ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]
def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df)==0:
        return pd.DataFrame(columns=EXPECTED_CLIENTI_COLS)
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns: df[c] = None
    return df

# =========================
# Data loading
# =========================
@st.cache_data
def load_csv_with_fallback(main_path, fallbacks):
    p = Path(main_path)
    if p.exists(): return pd.read_csv(p)
    for fb in fallbacks:
        if Path(fb).exists():
            return pd.read_csv(fb)
    return pd.DataFrame()

def compute_tot(row):
    return round(numify(row.get("NOL_FIN")) + numify(row.get("NOL_INT")), 2)

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
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = contratti[col].apply(numify)
    contratti["Stato"] = contratti["Stato"].astype(str).replace({"nan":""})

    # ricalcolo TotRata (se mancante o diverso dal calcolato)
    contratti["TotRataCalc"] = contratti.apply(compute_tot, axis=1)
    diff = (contratti["TotRata"] - contratti["TotRataCalc"]).abs().fillna(0)
    contratti.loc[(contratti["TotRata"].isna()) | (diff > 0.01), "TotRata"] = contratti["TotRataCalc"]
    contratti = contratti[ctr_cols]

    q_cols = ["ClienteID","Numero","Data","Template","FileName"]
    preventivi = load_csv_with_fallback("preventivi.csv", [])
    if preventivi.empty:
        preventivi = pd.DataFrame(columns=q_cols)
    for c in q_cols:
        if c not in preventivi.columns: preventivi[c] = None
    preventivi = preventivi[q_cols]

    return clienti, contratti, preventivi

def save_csv(df, path):
    df.to_csv(path, index=False)

# =========================
# Auth
# =========================
USERS = {"admin":{"password":"admin","role":"Admin"},
         "op":{"password":"op","role":"Operatore"},
         "view":{"password":"view","role":"Viewer"}}

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

# bootstrap session
clienti, contratti, preventivi = load_data()
st.session_state.setdefault("clienti", clienti.copy())
st.session_state.setdefault("contratti", contratti.copy())
st.session_state.setdefault("preventivi", preventivi.copy())

# =========================
# Sidebar
# =========================
st.sidebar.title("CRM")
page = st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti","Impostazioni"])

# =========================
# Dashboard
# =========================
def monthly_revenue_open_client(contratti, cid):
    df = contratti[(contratti["ClienteID"]==int(cid)) & (contratti["Stato"].str.lower()=="aperto")]
    return float(df["TotRata"].sum())

def monthly_revenue_all_client(contratti, cid):
    df = contratti[contratti["ClienteID"]==int(cid)]
    return float(df["TotRata"].sum())

def monthly_revenue_open_all(contratti):
    df = contratti[contratti["Stato"].str.lower()=="aperto"]
    return float(df["TotRata"].sum())

def render_dashboard():
    st.title("📊 Dashboard")
    c1,c2,c3 = st.columns(3)
    c1.metric("Clienti", len(st.session_state["clienti"]))
    c2.metric("Contratti", len(st.session_state["contratti"]))
    c3.metric("Rata mensile (aperti)", euro(monthly_revenue_open_all(st.session_state["contratti"])))

    st.subheader("Prossimi promemoria")
    cli = ensure_clienti_cols(st.session_state["clienti"])
    rem = cli[["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]].copy()
    st.dataframe(rem, use_container_width=True)

# =========================
# Clienti
# =========================
def render_clienti():
    clienti = ensure_clienti_cols(st.session_state["clienti"])
    contratti = st.session_state["contratti"]

    st.title("👥 Clienti")
    if len(clienti)==0:
        st.info("Nessun cliente caricato.")
        return

    det_id = st.number_input("Apri scheda ClienteID", min_value=int(clienti["ClienteID"].min()), max_value=int(clienti["ClienteID"].max()), step=1, value=int(clienti["ClienteID"].min()))
    dettaglio = clienti[clienti["ClienteID"] == int(det_id)]
    if dettaglio.empty:
        st.info("Cliente non trovato."); return
    c = dettaglio.iloc[0]

    st.markdown(f"### {c['RagioneSociale']}")
    a1,a2 = st.columns(2)
    with a1:
        st.write(f"**Persona di riferimento:** {c['NomeCliente'] or ''}")
        st.write(f"**Indirizzo:** {c['Indirizzo'] or ''}")
        st.write(f"**Città:** {c['Città'] or ''}  **CAP:** {c['CAP'] or ''}")
        st.write(f"**Telefono:** {c['Telefono'] or ''}")
        st.write(f"**Email:** {c['Email'] or ''}")
    with a2:
        st.write(f"**Partita IVA:** {c['PartitaIVA'] or ''}")
        st.write(f"**IBAN:** {c['IBAN'] or ''}")
        st.write(f"**SDI:** {c['SDI'] or ''}")
        st.write(f"**Ultimo Recall:** {c['UltimoRecall'] or ''}")
        st.write(f"**Prossimo Recall:** {c['ProssimoRecall'] or ''}")
        st.write(f"**Ultima Visita:** {c['UltimaVisita'] or ''}")
        st.write(f"**Prossima Visita:** {c['ProssimaVisita'] or ''}")
    if (c["Note"] or "") != "":
        st.info(c["Note"])

    ct = st.session_state["contratti"]
    ct_cli = ct[ct["ClienteID"]==int(det_id)]
    # metriche complete
    m1,m2,m3 = st.columns(3)
    m1.metric("Contratti", len(ct_cli))
    m2.metric("Rata mensile (Tutti)", euro(monthly_revenue_all_client(ct, det_id)))
    m3.metric("Rata mensile (Aperti)", euro(monthly_revenue_open_client(ct, det_id)))

    # Tabella contratti (TotRata IN CHIARO)
    st.write("### Contratti (rosso = chiusi)")
    df = ct_cli.copy().fillna("")
    # format euro
    df["NOL_FIN"] = df["NOL_FIN"].apply(euro)
    df["NOL_INT"] = df["NOL_INT"].apply(euro)
    df["TotRata"] = df["TotRata"].apply(euro)
    show = df[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]]
    st.dataframe(show, use_container_width=True)

# =========================
# Contratti (per cliente) 
# =========================
def render_contratti():
    clienti = ensure_clienti_cols(st.session_state["clienti"])
    contratti = st.session_state["contratti"]
    st.title("📃 Contratti per cliente")

    if len(clienti)==0:
        st.info("Nessun cliente caricato."); return

    opts = [(int(cid), nm if pd.notna(nm) else "") for cid,nm in zip(clienti["ClienteID"], clienti["RagioneSociale"])]
    labels = [f"{cid} — {nm}" for cid, nm in opts]
    choice = st.selectbox("Seleziona cliente", ["(seleziona)"] + labels, index=0)
    if choice == "(seleziona)":
        st.info("Seleziona un cliente per vedere i suoi contratti."); return
    try:
        sel_cid = int(str(choice).split(" — ")[0])
    except Exception:
        st.warning("Selezione non valida."); return

    df = contratti[contratti["ClienteID"]==sel_cid].copy().fillna("")
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        df[col] = df[col].apply(euro)
    # ordine colonne esplicito con TotRata presente
    cols = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    st.dataframe(df[cols], use_container_width=True)

# =========================
# Impostazioni (load/save)
# =========================
def render_settings():
    role = st.session_state.get("auth_role","Viewer")
    st.title("⚙️ Impostazioni & Salvataggio")
    c1,c2,c3 = st.columns(3)
    if c1.button("💾 Salva clienti.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["clienti"], "clienti.csv"); st.toast("clienti.csv salvato.", icon="✅")
    if c2.button("💾 Salva contratti.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["contratti"], "contratti.csv"); st.toast("contratti.csv salvato.", icon="✅")
    if c3.button("💾 Salva preventivi.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["preventivi"], "preventivi.csv"); st.toast("preventivi.csv salvato.", icon="✅")

    st.write("---")
    colA, colB, colC = st.columns(3)
    uc = colA.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None and role != "Viewer":
        tmp = pd.read_csv(uc)
        st.session_state["clienti"] = ensure_clienti_cols(tmp)
        st.toast("Clienti caricati (ricordati di salvare).", icon="✅")
    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None and role != "Viewer":
        tmp = pd.read_csv(ut)
        # normalizza e ricalcola TotRata
        if "DataInizio" in tmp.columns: tmp["DataInizio"] = tmp["DataInizio"].apply(fmt_date)
        if "DataFine" in tmp.columns: tmp["DataFine"] = tmp["DataFine"].apply(fmt_date)
        for col in ["NOL_FIN","NOL_INT","TotRata"]:
            if col in tmp.columns: tmp[col] = tmp[col].apply(numify)
        if "NOL_FIN" in tmp.columns and "NOL_INT" in tmp.columns:
            calc = (tmp["NOL_FIN"].apply(numify) + tmp["NOL_INT"].apply(numify)).round(2)
            if "TotRata" in tmp.columns:
                mask = tmp["TotRata"].isna() | (tmp["TotRata"] - calc).abs().fillna(0) > 0.01
                tmp.loc[mask, "TotRata"] = calc
            else:
                tmp["TotRata"] = calc
        if "Stato" in tmp.columns: tmp["Stato"] = tmp["Stato"].astype(str).replace({"nan":""})
        st.session_state["contratti"] = tmp
        st.toast("Contratti caricati (ricordati di salvare).", icon="✅")

    st.subheader("📄 Template preventivi (Word .docx)")
    tpls = colC.file_uploader("Carica template (.docx) con {{NUMERO}}, {{CLIENTE}}, {{DATA}}", type=["docx"], accept_multiple_files=True)
    if tpls:
        st.session_state["quote_templates"] = [(f.name, f.read()) for f in tpls]
        st.toast(f"{len(tpls)} template caricati (temporanei).", icon="✅")

# =========================
# Router
# =========================
if page == "Dashboard":
    render_dashboard()
elif page == "Clienti":
    render_clienti()
elif page == "Contratti":
    render_contratti()
else:
    render_settings()
