# =====================================
# app.py — Gestionale Clienti SHT (VERSIONE FULL 2025 OTTIMIZZATA)
# =====================================
from __future__ import annotations
import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder
from docx import Document
from docx.shared import Pt

# =====================================
# CONFIGURAZIONE BASE E STILE STREAMLIT
# =====================================
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide
# =====================================
# 🎨 BLOCCO A – STILE UI E CSS AVANZATO
# =====================================
# Inseriscilo subito dopo st.set_page_config(...)
# Aggiunge colori, layout più eleganti e pulsanti coerenti con la versione originale.

st.markdown("""
<style>
/* === LAYOUT GENERALE === */
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}
section.main > div:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* === CARD E KPI === */
.kpi-card {
    border-radius: 12px;
    padding: 18px;
    color: white;
    text-align: center;
    box-shadow: 0 3px 10px rgba(0,0,0,0.1);
    transition: transform 0.15s ease;
}
.kpi-card:hover { transform: scale(1.03); }
.kpi-icon { font-size: 26px; }
.kpi-value { font-size: 22px; font-weight: 700; margin-top: 4px; }
.kpi-label { font-size: 14px; opacity: 0.9; }

/* === BOTTONE COLORATI === */
.btn-blue > button {
    background-color:#e3f2fd !important;
    color:#0d47a1 !important;
    border:none !important;
    border-radius:6px !important;
    font-weight:500 !important;
}
.btn-yellow > button {
    background-color:#fff8e1 !important;
    color:#ef6c00 !important;
    border:none !important;
    border-radius:6px !important;
    font-weight:500 !important;
}
.btn-red > button {
    background-color:#ffebee !important;
    color:#b71c1c !important;
    border:none !important;
    border-radius:6px !important;
    font-weight:500 !important;
}

/* === INFO BOX === */
.info-box {
    background:#fff;
    border-radius:12px;
    box-shadow:0 3px 10px rgba(0,0,0,0.06);
    padding:1.3rem 1.6rem;
    margin-top:0.8rem;
    margin-bottom:1.5rem;
    font-size:15px;
    line-height:1.7;
    border-left:5px solid #2563eb;
}
.info-title {
    color:#2563eb;
    font-size:17px;
    font-weight:600;
    margin-bottom:0.6rem;
}
.info-item { margin-bottom:0.3rem; }
.info-label { font-weight:600; color:#0d1117; }

/* === EXPANDER + DIVIDER === */
.streamlit-expanderHeader {
    font-weight:600 !important;
    color:#2563eb !important;
}
hr { border: none; border-top: 1px solid #e0e0e0; margin: 1rem 0; }

/* === STILI CONTRATTI === */
.pill-open {
    background:#e8f5e9;
    color:#1b5e20;
    padding:2px 8px;
    border-radius:8px;
    font-weight:600;
}
.pill-closed {
    background:#ffebee;
    color:#b71c1c;
    padding:2px 8px;
    border-radius:8px;
    font-weight:600;
}
.card {
    background:#fff;
    border-radius:12px;
    box-shadow:0 2px 10px rgba(0,0,0,.06);
    padding:1.2rem 1.4rem;
    margin-bottom:1rem;
}
.card h3 { color:#2563eb; margin:0 0 .8rem 0; }

/* === LOGIN PERSONALIZZATO === */
div[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
.login-card {
    background:#fff;
    border:1px solid #e5e7eb;
    border-radius:12px;
    box-shadow:0 4px 16px rgba(0,0,0,0.08);
    padding:2rem 2.5rem;
    width:360px;
    text-align:center;
}
.login-title {
    font-size:1.3rem;
    font-weight:600;
    color:#2563eb;
    margin:1rem 0 1.4rem;
}
.stButton>button {
    font-size:0.9rem;
    border-radius:6px;
    padding:0.5rem 0;
}

/* === SCROLLBAR E SFONDI === */
::-webkit-scrollbar { width: 10px; }
::-webkit-scrollbar-thumb { background:#2563eb; border-radius:6px; }
::-webkit-scrollbar-track { background:#f0f2f5; }

/* === HOVER LISTA CLIENTI === */
.row-hover:hover {
    background:#f0f7ff !important;
    cursor:pointer;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.block-container{padding-left:2rem;padding-right:2rem;max-width:100%!important;}
section.main>div:first-child{margin-top:0!important;padding-top:0!important;}
</style>
""", unsafe_allow_html=True)
st.markdown("<script>window.addEventListener('load',()=>{window.scrollTo(0,0);});</script>", unsafe_allow_html=True)

# =====================================
# PERCORSI E COSTANTI GLOBALI
# =====================================
APP_TITLE="GESTIONALE CLIENTI – SHT"
LOGO_URL="https://www.shtsrl.com/template/images/logo.png"
STORAGE_DIR=Path("storage"); STORAGE_DIR.mkdir(parents=True, exist_ok=True)
CLIENTI_CSV=STORAGE_DIR/"clienti.csv"
CONTRATTI_CSV=STORAGE_DIR/"contratti_clienti.csv"
PREVENTIVI_CSV=STORAGE_DIR/"preventivi.csv"
PREVENTIVI_DIR=STORAGE_DIR/"preventivi"; PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR=STORAGE_DIR/"templates"; TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE_OPTIONS={
  "Offerta A4":"Offerta_A4.docx",
  "Offerta A3":"Offerta_A3.docx",
  "Centralino":"Offerta_Centralino.docx",
  "Varie":"Offerta_Varie.docx",
}
DURATE_MESI=["12","24","36","48","60","72"]

CLIENTI_COLS=[
 "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
 "Telefono","Cell","Email","PartitaIVA","IBAN","SDI",
 "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","TMK","NoteCliente"
]
CONTRATTI_COLS=[
 "ClienteID","RagioneSociale","NumeroContratto","DataInizio","DataFine","Durata",
 "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata",
 "CopieBN","EccBN","CopieCol","EccCol","Stato"
]

# =====================================
# FUNZIONI UTILITY
# =====================================
def fmt_date(d)->str:
    import datetime as dt
    if d in (None,"","nan","NaN"): return ""
    try:
        if isinstance(d,(dt.date,dt.datetime,pd.Timestamp)):
            return pd.to_datetime(d).strftime("%d/%m/%Y")
        parsed=pd.to_datetime(str(d),errors="coerce",dayfirst=True)
        return "" if pd.isna(parsed) else parsed.strftime("%d/%m/%Y")
    except Exception: return ""

def money(x):
    try:
        v=float(pd.to_numeric(x,errors="coerce"))
        if pd.isna(v): return ""
        return f"{v:,.2f} €"
    except Exception: return ""

def safe_text(txt):
    if pd.isna(txt) or txt is None: return ""
    s=str(txt)
    repl={"€":"EUR","–":"-","—":"-","“":'"',"”":'"',"‘":"'", "’":"'"}
    for k,v in repl.items(): s=s.replace(k,v)
    return s.encode("latin-1","replace").decode("latin-1")

def ensure_columns(df,cols):
    for c in cols:
        if c not in df.columns: df[c]=pd.NA
    return df[cols]

# =====================================
# CACHE E SALVATAGGI OTTIMIZZATI
# =====================================
@st.cache_data(ttl=90)
def load_csv(path:Path,cols:list[str])->pd.DataFrame:
    """Carica CSV con cache (90 s) e colonne garantite."""
    if path.exists():
        df=pd.read_csv(path,dtype=str,encoding="utf-8-sig").fillna("")
    else:
        df=pd.DataFrame(columns=cols)
        df.to_csv(path,index=False,encoding="utf-8-sig")
    return ensure_columns(df,cols)

def save_csv(df:pd.DataFrame,path:Path,date_cols=None):
    out=df.copy()
    if date_cols:
        for c in date_cols: out[c]=out[c].apply(fmt_date)
    out.to_csv(path,index=False,encoding="utf-8-sig")
    load_csv.clear()

def save_if_changed(df_new,path:Path,original_df):
    try:
        if not original_df.equals(df_new):
            df_new.to_csv(path,index=False,encoding="utf-8-sig")
            load_csv.clear(); return True
        return False
    except Exception:
        df_new.to_csv(path,index=False,encoding="utf-8-sig")
        load_csv.clear(); return True

# =====================================
# LOGIN FULLSCREEN
# =====================================
def do_login_fullscreen():
    if st.session_state.get("logged_in"):
        return st.session_state["user"],st.session_state["role"]

    st.markdown("""
    <style>
    div[data-testid="stAppViewContainer"]{padding-top:0!important;}
    .block-container{
      display:flex;flex-direction:column;justify-content:center;
      align-items:center;height:100vh;background-color:#f8fafc;}
    .login-card{
      background:#fff;border:1px solid #e5e7eb;border-radius:12px;
      box-shadow:0 4px 16px rgba(0,0,0,0.08);
      padding:2rem 2.5rem;width:360px;text-align:center;}
    .login-title{font-size:1.3rem;font-weight:600;color:#2563eb;margin:1rem 0 1.4rem;}
    .stButton>button{
      width:260px;font-size:0.9rem;background-color:#2563eb;color:white;
      border:none;border-radius:6px;padding:0.5rem 0;}
    </style>
    """,unsafe_allow_html=True)

    st.markdown("<div class='login-card'>",unsafe_allow_html=True)
    st.image(LOGO_URL,width=140)
    st.markdown("<div class='login-title'>Accedi al CRM SHT</div>",unsafe_allow_html=True)
    username=st.text_input("Nome utente",key="login_user").strip().lower()
    password=st.text_input("Password",type="password",key="login_pass")

    if st.button("Entra"):
        users=st.secrets["auth"]["users"]
        if username in users and users[username]["password"]==password:
            st.session_state.update({
              "user":username,
              "role":users[username].get("role","viewer"),
              "logged_in":True})
            st.success(f"✅ Benvenuto {username}!")
            time.sleep(0.3); st.rerun()
        else:
            st.error("❌ Credenziali non valide.")
    st.markdown("</div>",unsafe_allow_html=True)
    st.stop()

# =====================================
# KPI CARD
# =====================================
def kpi_card(label:str,value,icon:str,color:str)->str:
    return f"""
    <div style="background-color:{color};
        padding:18px;border-radius:12px;text-align:center;color:white;">
        <div style='font-size:26px'>{icon}</div>
        <div style='font-size:22px;font-weight:700'>{value}</div>
        <div style='font-size:14px'>{label}</div>
    </div>
    """
# ======== FINE BLOCCO 1 ========
# =====================================
# 📊 PAGINA DASHBOARD COMPLETA
# =====================================
# =====================================
# 📊 BLOCCO D — DASHBOARD AVANZATA
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📊 Dashboard Gestionale SHT</h2>", unsafe_allow_html=True)
    st.divider()

    # === KPI PRINCIPALI ===
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())
    now = pd.Timestamp.now().normalize()

    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    new_contracts = df_ct[
        (df_ct["DataInizio"].notna()) & (df_ct["DataInizio"] >= pd.Timestamp(year=now.year, month=1, day=1))
    ]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#1976D2"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#388E3C"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#D32F2F"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Nuovi contratti anno", len(new_contracts), "⭐", "#FBC02D"), unsafe_allow_html=True)

    st.divider()

    # === CREAZIONE NUOVO CLIENTE + CONTRATTO ===
    with st.expander("➕ Crea Nuovo Cliente + Contratto"):
        with st.form("frm_new_cliente"):
            st.markdown("#### 📇 Dati Cliente")
            col1, col2 = st.columns(2)
            with col1:
                ragione = st.text_input("🏢 Ragione Sociale")
                persona = st.text_input("👤 Persona Riferimento")
                indirizzo = st.text_input("📍 Indirizzo")
                citta = st.text_input("🏙️ Città")
                cap = st.text_input("📮 CAP")
                telefono = st.text_input("📞 Telefono")
                cell = st.text_input("📱 Cellulare")
            with col2:
                email = st.text_input("✉️ Email")
                piva = st.text_input("💼 Partita IVA")
                iban = st.text_input("🏦 IBAN")
                sdi = st.text_input("📡 SDI")
                note = st.text_area("📝 Note Cliente", height=70)
                tmk = st.selectbox("👩‍💼 TMK di riferimento", ["", "Giulia", "Antonella", "Annalisa", "Laura"], index=0)

            # === SEZIONE CONTRATTO ===
            st.markdown("#### 📄 Primo Contratto del Cliente")
            colc1, colc2, colc3 = st.columns(3)
            num = colc1.text_input("📄 Numero Contratto")
            data_inizio = colc2.date_input("📅 Data Inizio", format="DD/MM/YYYY")
            durata = colc3.selectbox("📆 Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("🧾 Descrizione Prodotto", height=80)
            colp1, colp2, colp3 = st.columns(3)
            nf = colp1.text_input("🏦 NOL_FIN")
            ni = colp2.text_input("🏢 NOL_INT")
            tot = colp3.text_input("💰 Tot Rata")
            colx1, colx2, colx3, colx4 = st.columns(4)
            copie_bn = colx1.text_input("📄 Copie incluse B/N", "")
            ecc_bn = colx2.text_input("💰 Costo extra B/N (€)", "")
            copie_col = colx3.text_input("🖨️ Copie incluse Colore", "")
            ecc_col = colx4.text_input("💰 Costo extra Colore (€)", "")

            if st.form_submit_button("💾 Crea Cliente e Contratto"):
                try:
                    new_id = str(len(df_cli) + 1)
                    nuovo_cliente = {
                        "ClienteID": new_id, "RagioneSociale": ragione, "PersonaRiferimento": persona,
                        "Indirizzo": indirizzo, "Citta": citta, "CAP": cap,
                        "Telefono": telefono, "Cell": cell, "Email": email, "PartitaIVA": piva,
                        "IBAN": iban, "SDI": sdi,
                        "UltimoRecall": "", "ProssimoRecall": "", "UltimaVisita": "", "ProssimaVisita": "",
                        "TMK": tmk, "NoteCliente": note
                    }
                    df_cli = pd.concat([df_cli, pd.DataFrame([nuovo_cliente])], ignore_index=True)
                    save_csv(df_cli, CLIENTI_CSV)

                    data_fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))
                    nuovo_contratto = {
                        "ClienteID": new_id, "RagioneSociale": ragione, "NumeroContratto": num,
                        "DataInizio": fmt_date(data_inizio), "DataFine": fmt_date(data_fine),
                        "Durata": durata, "DescrizioneProdotto": desc, "NOL_FIN": nf, "NOL_INT": ni,
                        "TotRata": tot, "CopieBN": copie_bn, "EccBN": ecc_bn,
                        "CopieCol": copie_col, "EccCol": ecc_col, "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([nuovo_contratto])], ignore_index=True)
                    save_csv(df_ct, CONTRATTI_CSV)

                    st.success(f"✅ Cliente '{ragione}' e contratto creati correttamente!")
                    st.session_state.update({"selected_cliente": new_id, "nav_target": "Contratti"}); st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore creazione cliente: {e}")

    st.divider()
    st.markdown("### ⚠️ Contratti in scadenza entro 6 mesi")

    oggi = pd.Timestamp.now().normalize()
    entro_6_mesi = oggi + pd.DateOffset(months=6)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    scadenze = df_ct[
        (df_ct["DataFine"].notna()) &
        (df_ct["DataFine"] >= oggi) &
        (df_ct["DataFine"] <= entro_6_mesi) &
        (df_ct["Stato"].astype(str).str.lower() != "chiuso")
    ].copy()

    if scadenze.empty:
        st.success("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        scadenze = scadenze.sort_values("DataFine")
        for i, r in scadenze.iterrows():
            bg = "#f8fbff" if i % 2 == 0 else "#ffffff"
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 0.8])
            c1.markdown(f"<div style='background:{bg};padding:6px'><b>{r.get('RagioneSociale','—')}</b></div>", unsafe_allow_html=True)
            c2.markdown(f"<div style='background:{bg};padding:6px'>{r.get('NumeroContratto','—')}</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='background:{bg};padding:6px'>{fmt_date(r.get('DataFine'))}</div>", unsafe_allow_html=True)
            c4.markdown(f"<div style='background:{bg};padding:6px'>{r.get('Stato','—')}</div>", unsafe_allow_html=True)
            if c5.button("📂 Apri", key=f"open_scad_{i}", use_container_width=True):
                st.session_state.update({"selected_cliente": str(r.get("ClienteID")), "nav_target": "Contratti"}); st.rerun()

    st.divider()
    st.markdown("### ⚠️ Contratti recenti senza data di fine")
    contratti_senza_fine = df_ct[(df_ct["DataFine"].isna()) & (df_ct["DataInizio"].notna())].copy()
    if contratti_senza_fine.empty:
        st.success("✅ Tutti i contratti recenti hanno una data di fine.")
    else:
        for i, r in contratti_senza_fine.iterrows():
            bg = "#fffdf5" if i % 2 == 0 else "#ffffff"
            c1, c2, c3, c4, c5 = st.columns([2.5, 1, 1.2, 2.5, 0.8])
            c1.markdown(f"<div style='background:{bg};padding:6px'><b>{r.get('RagioneSociale','—')}</b></div>", unsafe_allow_html=True)
            c2.markdown(f"<div style='background:{bg};padding:6px'>{r.get('NumeroContratto','—')}</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='background:{bg};padding:6px'>{fmt_date(r.get('DataInizio'))}</div>", unsafe_allow_html=True)
            desc = str(r.get('DescrizioneProdotto','—'))
            if len(desc) > 60: desc = desc[:60] + "…"
            c4.markdown(f"<div style='background:{bg};padding:6px'>{desc}</div>", unsafe_allow_html=True)
            if c5.button("📂 Apri", key=f"open_ndf_{i}", use_container_width=True):
                st.session_state.update({"selected_cliente": str(r.get('ClienteID')), "nav_target": "Contratti"}); st.rerun()


# =====================================
# 🧱 BLOCCO B — PAGINA CLIENTI AVANZATA
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Gestione Clienti")

    if role == "limitato":
        st.warning("⚠️ Accesso in sola lettura per il tuo profilo.")
        st.stop()

    # === RICERCA CLIENTE ===
    search_query = st.text_input("🔍 Cerca cliente per nome o ID", key="search_cli")
    if search_query:
        filtered = df_cli[
            df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)
            | df_cli["ClienteID"].astype(str).str.contains(search_query, na=False)
        ]
    else:
        filtered = df_cli.copy()

    if filtered.empty:
        st.warning("❌ Nessun cliente trovato.")
        return

    selected_name = st.session_state.get("cliente_selezionato", filtered["RagioneSociale"].iloc[0])
    sel_rag = st.selectbox("Seleziona Cliente", filtered["RagioneSociale"].tolist(),
                           index=list(filtered["RagioneSociale"]).index(selected_name)
                           if selected_name in filtered["RagioneSociale"].values else 0)

    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    # === INTESTAZIONE CLIENTE + PULSANTI ===
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
        st.caption(f"ID Cliente: {sel_id}")

    with c2:
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("📄 Vai ai Contratti", use_container_width=True, key=f"go_cont_{sel_id}"):
            st.session_state.update({"selected_cliente": sel_id, "nav_target": "Contratti"}); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="btn-yellow">', unsafe_allow_html=True)
        if st.button("✏️ Modifica Anagrafica", use_container_width=True, key=f"edit_{sel_id}"):
            st.session_state[f"edit_cli_{sel_id}"] = not st.session_state.get(f"edit_cli_{sel_id}", False)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="btn-red">', unsafe_allow_html=True)
        if st.button("🗑️ Cancella Cliente", use_container_width=True, key=f"ask_del_{sel_id}"):
            st.session_state["confirm_delete_cliente"] = str(sel_id); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # === BOX INFORMATIVI ===
    infoA, infoB = st.columns(2)
    with infoA:
        st.markdown(f"""
        <div class="info-box">
            <div class="info-title">📇 Dati Principali</div>
            <div class="info-item"><span class="info-label">👤 Referente:</span> {cliente.get('PersonaRiferimento','')}</div>
            <div class="info-item"><span class="info-label">✉️ Email:</span> {cliente.get('Email','')}</div>
            <div class="info-item"><span class="info-label">👩‍💼 TMK:</span> {cliente.get('TMK','')}</div>
            <div class="info-item"><span class="info-label">📞 Telefono:</span> {cliente.get('Telefono','')} — <span class="info-label">📱 Cell:</span> {cliente.get('Cell','')}</div>
        </div>
        """, unsafe_allow_html=True)
    with infoB:
        st.markdown(f"""
        <div class="info-box">
            <div class="info-title">📍 Indirizzo e Dati Fiscali</div>
            <div class="info-item"><span class="info-label">📍 Indirizzo:</span> {cliente.get('Indirizzo','')} — {cliente.get('Citta','')} {cliente.get('CAP','')}</div>
            <div class="info-item"><span class="info-label">💼 Partita IVA:</span> {cliente.get('PartitaIVA','')}</div>
            <div class="info-item"><span class="info-label">🏦 IBAN:</span> {cliente.get('IBAN','')}</div>
            <div class="info-item"><span class="info-label">📡 SDI:</span> {cliente.get('SDI','')}</div>
        </div>
        """, unsafe_allow_html=True)

    # === MODIFICA ANAGRAFICA ===
    if st.session_state.get(f"edit_cli_{sel_id}", False):
        st.divider()
        st.markdown("### ✏️ Modifica Anagrafica Cliente")
        with st.form(f"frm_anagrafica_{sel_id}"):
            col1, col2 = st.columns(2)
            with col1:
                indirizzo = st.text_input("📍 Indirizzo", cliente.get("Indirizzo", ""))
                citta = st.text_input("🏙️ Città", cliente.get("Citta", ""))
                cap = st.text_input("📮 CAP", cliente.get("CAP", ""))
                telefono = st.text_input("📞 Telefono", cliente.get("Telefono", ""))
                cell = st.text_input("📱 Cellulare", cliente.get("Cell", ""))
                email = st.text_input("✉️ Email", cliente.get("Email", ""))
            with col2:
                persona = st.text_input("👤 Persona Riferimento", cliente.get("PersonaRiferimento", ""))
                piva = st.text_input("💼 Partita IVA", cliente.get("PartitaIVA", ""))
                iban = st.text_input("🏦 IBAN", cliente.get("IBAN", ""))
                sdi = st.text_input("📡 SDI", cliente.get("SDI", ""))
                tmk = st.selectbox(
                    "👩‍💼 TMK di riferimento",
                    ["", "Giulia", "Antonella", "Annalisa", "Laura"],
                    index=["", "Giulia", "Antonella", "Annalisa", "Laura"].index(cliente.get("TMK", "")) if cliente.get("TMK", "") in ["Giulia", "Antonella", "Annalisa", "Laura"] else 0
                )

            salva = st.form_submit_button("💾 Salva Modifiche")
            if salva:
                idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx, [
                    "Indirizzo", "Citta", "CAP", "Telefono", "Cell", "Email",
                    "PersonaRiferimento", "PartitaIVA", "IBAN", "SDI", "TMK"
                ]] = [indirizzo, citta, cap, telefono, cell, email, persona, piva, iban, sdi, tmk]
                save_csv(df_cli, CLIENTI_CSV)
                st.success("✅ Anagrafica aggiornata."); st.session_state[f"edit_cli_{sel_id}"] = False; st.rerun()

        # === NOTE CLIENTE ===
        st.divider()
        st.markdown("### 📝 Note Cliente")
        note_attuali = cliente.get("NoteCliente", "")
        nuove_note = st.text_area("Modifica note cliente:", note_attuali, height=160, key=f"note_{sel_id}")
        if st.button("💾 Salva Note Cliente", key=f"save_note_{sel_id}", use_container_width=True):
            idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
            df_cli.loc[idx_row, "NoteCliente"] = nuove_note
            save_csv(df_cli, CLIENTI_CSV)
            st.success("✅ Note aggiornate correttamente!"); st.rerun()

        # === RECALL E VISITE ===
        st.divider()
        st.markdown("### ⚡ Recall e Visite")
        def _safe_date(val):
            try:
                d = pd.to_datetime(val, dayfirst=True)
                return None if pd.isna(d) else d.date()
            except Exception:
                return None

        ur_val = _safe_date(cliente.get("UltimoRecall"))
        pr_val = _safe_date(cliente.get("ProssimoRecall"))
        uv_val = _safe_date(cliente.get("UltimaVisita"))
        pv_val = _safe_date(cliente.get("ProssimaVisita"))
        if ur_val and not pr_val: pr_val = (pd.Timestamp(ur_val)+pd.DateOffset(months=3)).date()
        if uv_val and not pv_val: pv_val = (pd.Timestamp(uv_val)+pd.DateOffset(months=6)).date()

        c1, c2, c3, c4 = st.columns(4)
        ur = c1.date_input("⏰ Ultimo Recall", value=ur_val, format="DD/MM/YYYY", key=f"ur_{sel_id}")
        pr = c2.date_input("📅 Prossimo Recall", value=pr_val, format="DD/MM/YYYY", key=f"pr_{sel_id}")
        uv = c3.date_input("👣 Ultima Visita", value=uv_val, format="DD/MM/YYYY", key=f"uv_{sel_id}")
        pv = c4.date_input("🗓️ Prossima Visita", value=pv_val, format="DD/MM/YYYY", key=f"pv_{sel_id}")

        if st.button("💾 Salva Aggiornamenti", use_container_width=True, key=f"save_recall_{sel_id}"):
            idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
            df_cli.loc[idx, ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]] = \
                [fmt_date(ur), fmt_date(pr), fmt_date(uv), fmt_date(pv)]
            save_csv(df_cli, CLIENTI_CSV)
            st.success("✅ Date aggiornate."); st.rerun()

# =====================================
# 📄 PAGINA CONTRATTI COMPLETA
# =====================================
# =====================================
# 📑 BLOCCO C — PAGINA CONTRATTI AVANZATA
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    ruolo_scrittura = st.session_state.get("ruolo_scrittura", role)
    permessi_limitati = ruolo_scrittura == "limitato"

    st.markdown("<h2>📄 Gestione Contratti</h2>", unsafe_allow_html=True)
    if permessi_limitati:
        st.info("👁️ Modalità sola lettura: puoi visualizzare i contratti ma non modificarli o crearne di nuovi.")

    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    sel_label = st.selectbox("Seleziona Cliente", labels.tolist(), index=0)
    sel_id = sel_label.split(" — ")[0]
    rag_soc = df_cli.loc[df_cli["ClienteID"] == sel_id, "RagioneSociale"].iloc[0]

    st.markdown(f"<h3 style='text-align:center;color:#2563eb;margin-bottom:0;'>{rag_soc}</h3>", unsafe_allow_html=True)
    st.caption(f"ID Cliente: {sel_id}")

    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy().reset_index(drop=True)

    # === CREAZIONE NUOVO CONTRATTO ===
    with st.expander("➕ Crea Nuovo Contratto", expanded=False):
        if permessi_limitati:
            st.warning("🔒 Non hai i permessi per creare nuovi contratti.")
        else:
            with st.form(f"frm_new_contract_{sel_id}"):
                c1, c2, c3, c4 = st.columns(4)
                num = c1.text_input("Numero Contratto")
                din = c2.date_input("Data Inizio", format="DD/MM/YYYY")
                durata = c3.selectbox("Durata (mesi)", DURATE_MESI, index=2)
                stato_new = c4.selectbox("Stato", ["aperto", "chiuso"], index=0)

                desc = st.text_area("Descrizione Prodotto", height=80)
                c5, c6, c7 = st.columns(3)
                nf = c5.text_input("NOL_FIN")
                ni = c6.text_input("NOL_INT")
                tot = c7.text_input("Tot Rata")

                c8, c9, c10, c11 = st.columns(4)
                copie_bn = c8.text_input("Copie incluse B/N", value="")
                ecc_bn = c9.text_input("Costo extra B/N (€)", value="")
                copie_col = c10.text_input("Copie incluse Colore", value="")
                ecc_col = c11.text_input("Costo extra Colore (€)", value="")

                if st.form_submit_button("💾 Crea contratto"):
                    try:
                        data_fine = pd.to_datetime(din) + pd.DateOffset(months=int(durata))
                        new_row = {
                            "ClienteID": sel_id, "RagioneSociale": rag_soc,
                            "NumeroContratto": num, "DataInizio": fmt_date(din),
                            "DataFine": fmt_date(data_fine), "Durata": durata,
                            "DescrizioneProdotto": desc, "NOL_FIN": nf, "NOL_INT": ni,
                            "TotRata": tot, "CopieBN": copie_bn, "EccBN": ecc_bn,
                            "CopieCol": copie_col, "EccCol": ecc_col, "Stato": stato_new or "aperto"
                        }
                        df_ct = pd.concat([df_ct, pd.DataFrame([new_row])], ignore_index=True)
                        save_csv(df_ct, CONTRATTI_CSV)
                        st.success("✅ Contratto creato con successo.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Errore creazione contratto: {e}")

    st.divider()
    st.markdown("### 📋 Contratti Esistenti")

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    # === FORMATTAZIONE ===
    ct["DataInizio"] = ct["DataInizio"].apply(fmt_date)
    ct["DataFine"] = ct["DataFine"].apply(fmt_date)
    ct["TotRata"] = ct["TotRata"].apply(money)

    # === VISUALIZZAZIONE CONTRATTI ===
    for i, r in ct.iterrows():
        rid = f"{sel_id}_{r['NumeroContratto']}_{i}"
        stato = str(r.get("Stato","")).lower()
        bg = "#f8fbff" if stato != "chiuso" else "#ffebee"

        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.1, 0.9, 0.9, 1.2, 1.5, 2.0, 1.0])
        c1.markdown(f"<div style='background:{bg};padding:6px'><b>{r.get('NumeroContratto','')}</b></div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='background:{bg};padding:6px'>{r.get('DataInizio','')}</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='background:{bg};padding:6px'>{r.get('DataFine','')}</div>", unsafe_allow_html=True)
        c4.markdown(f"<div style='background:{bg};padding:6px'>{r.get('TotRata','')}</div>", unsafe_allow_html=True)
        stato_tag = "<span class='pill-open'>Aperto</span>" if stato!="chiuso" else "<span class='pill-closed'>Chiuso</span>"
        c5.markdown(f"<div style='background:{bg};padding:6px'>{stato_tag}</div>", unsafe_allow_html=True)
        desc = r.get("DescrizioneProdotto","") or "—"
        if len(desc) > 70: desc = desc[:70] + "…"
        c6.markdown(f"<div style='background:{bg};padding:6px'>{desc}</div>", unsafe_allow_html=True)

        # Azioni
        with c7:
            colE, colD = st.columns(2)
            if permessi_limitati:
                colE.button("✏️", key=f"edit_{rid}", disabled=True)
                colD.button("🗑️", key=f"del_{rid}", disabled=True)
            else:
                if colE.button("✏️", key=f"edit_{rid}"):
                    st.session_state["edit_idx"] = i; st.rerun()
                if colD.button("🗑️", key=f"del_{rid}"):
                    st.session_state["del_idx"] = i; st.session_state["confirm_del"] = True; st.rerun()

    # === MODIFICA CONTRATTO ===
    if st.session_state.get("edit_idx") is not None:
        i = st.session_state["edit_idx"]
        r = ct.iloc[i]
        st.divider()
        st.markdown(f"### ✏️ Modifica Contratto {r['NumeroContratto']}")
        with st.form(f"frm_edit_{i}"):
            c1, c2, c3, c4 = st.columns(4)
            num = c1.text_input("Numero Contratto", r["NumeroContratto"])
            din = c2.date_input("Data Inizio", value=pd.to_datetime(r["DataInizio"], dayfirst=True), format="DD/MM/YYYY")
            durata = c3.text_input("Durata (mesi)", r["Durata"])
            stato_new = c4.selectbox("Stato", ["aperto","chiuso"], index=0 if stato!="chiuso" else 1)
            desc = st.text_area("Descrizione Prodotto", r["DescrizioneProdotto"], height=100)
            c5, c6, c7 = st.columns(3)
            nf, ni, tot = c5.text_input("NOL_FIN", r["NOL_FIN"]), c6.text_input("NOL_INT", r["NOL_INT"]), c7.text_input("Tot Rata", r["TotRata"])
            c8, c9, c10, c11 = st.columns(4)
            copie_bn, ecc_bn, copie_col, ecc_col = (
                c8.text_input("Copie incluse B/N", r["CopieBN"]),
                c9.text_input("Costo extra B/N (€)", r["EccBN"]),
                c10.text_input("Copie incluse Colore", r["CopieCol"]),
                c11.text_input("Costo extra Colore (€)", r["EccCol"])
            )
            if st.form_submit_button("💾 Salva Modifiche"):
                df_ct.loc[ct.index[i], [
                    "NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
                    "NOL_FIN","NOL_INT","TotRata","CopieBN","EccBN","CopieCol","EccCol","Stato"
                ]] = [
                    num, fmt_date(din),
                    fmt_date(pd.to_datetime(din) + pd.DateOffset(months=int(durata) if durata.isdigit() else 12)),
                    durata, desc, nf, ni, tot, copie_bn, ecc_bn, copie_col, ecc_col, stato_new
                ]
                save_csv(df_ct, CONTRATTI_CSV)
                st.success("✅ Contratto aggiornato.")
                st.session_state.pop("edit_idx", None); st.rerun()

            if st.form_submit_button("❌ Annulla"):
                st.session_state.pop("edit_idx", None); st.rerun()

    # === CONFERMA ELIMINAZIONE ===
    if st.session_state.get("confirm_del") and st.session_state.get("del_idx") is not None:
        i = st.session_state["del_idx"]
        r = ct.iloc[i]
        st.warning(f"⚠️ Confermi eliminazione contratto **{r['NumeroContratto']}** del cliente **{rag_soc}**?")
        col1, col2 = st.columns(2)
        if col1.button("✅ Sì, elimina", key=f"yesdel_{i}"):
            df_ct.drop(ct.index[i], inplace=True)
            save_csv(df_ct, CONTRATTI_CSV)
            st.success("🗑️ Contratto eliminato.")
            st.session_state.pop("confirm_del", None); st.session_state.pop("del_idx", None); st.rerun()
        if col2.button("❌ Annulla", key=f"nodel_{i}"):
            st.session_state.pop("confirm_del", None); st.session_state.pop("del_idx", None); st.info("Annullato.")
            st.rerun()

    # === ESPORTAZIONI ===
    st.divider()
    st.markdown("### 📤 Esportazioni")
    col1, col2 = st.columns(2)
    with col1:
        from io import BytesIO
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "Contratti"
        headers = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
        ws.append(headers)
        for _, row in ct.iterrows():
            ws.append([row.get(h,"") for h in headers])
        bio = BytesIO(); wb.save(bio)
        st.download_button("📘 Esporta Excel", bio.getvalue(),
            file_name=f"Contratti_{rag_soc}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with col2:
        pdf = FPDF(orientation="L", format="A4")
        pdf.add_page(); pdf.set_font("Arial","B",12)
        pdf.cell(0,10,safe_text(f"Contratti Cliente: {rag_soc}"),ln=1,align="C")
        pdf.set_font("Arial","",9)
        for _, row in ct.iterrows():
            line = f"{row['NumeroContratto']} — {row['DataFine']} — {row['TotRata']} — {row['Stato']}"
            pdf.cell(0,6,safe_text(line),ln=1)
        st.download_button("📗 Esporta PDF", data=pdf.output(dest="S").encode("latin-1"),
            file_name=f"Contratti_{rag_soc}.pdf", mime="application/pdf")

# =====================================
# 🧾 PAGINA PREVENTIVI COMPLETA
# =====================================
def page_preventivi(df_cli: pd.DataFrame, role: str):
    st.markdown("<h2>🧾 Gestione Preventivi</h2>", unsafe_allow_html=True)
    sel_cli = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"])
    cliente = df_cli[df_cli["RagioneSociale"] == sel_cli].iloc[0]
    sel_id = cliente["ClienteID"]

    prev_csv = PREVENTIVI_CSV
    if prev_csv.exists():
        df_prev = pd.read_csv(prev_csv, dtype=str).fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID","NumeroOfferta","Template","NomeFile","Percorso","DataCreazione"])

    anno = datetime.now().year
    nome_cliente = cliente.get("RagioneSociale","")
    nome_sicuro = "".join(c for c in nome_cliente if c.isalnum())[:6].upper()
    num_off = f"OFF-{anno}-{nome_sicuro}-{len(df_prev[df_prev['ClienteID']==sel_id])+1:03d}"

    with st.form(f"frm_prev_{sel_id}"):
        st.text_input("Numero Offerta", num_off, disabled=True)
        nome_file = st.text_input("Nome File", f"{num_off}.docx")
        template = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        genera_btn = st.form_submit_button("💾 Genera Preventivo")

    if genera_btn:
        tpl_path = TEMPLATES_DIR / TEMPLATE_OPTIONS[template]
        if not tpl_path.exists():
            st.error(f"❌ Template non trovato: {tpl_path}")
            st.stop()
        doc = Document(tpl_path)
        mappa = {
            "CLIENTE": nome_cliente,
            "INDIRIZZO": cliente.get("Indirizzo",""),
            "CITTA": str(cliente.get("Citta","")).strip().upper(),
            "NUMERO_OFFERTA": num_off,
            "DATA": datetime.now().strftime("%d/%m/%Y")
        }
        for p in doc.paragraphs:
            for k,v in mappa.items():
                if f"<<{k}>>" in p.text:
                    for run in p.runs:
                        run.text = run.text.replace(f"<<{k}>>", str(v))
        out_path = PREVENTIVI_DIR / nome_file
        doc.save(out_path)

        nuova_riga = {
            "ClienteID": sel_id, "NumeroOfferta": num_off,
            "Template": TEMPLATE_OPTIONS[template], "NomeFile": nome_file,
            "Percorso": str(out_path),
            "DataCreazione": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        df_prev = pd.concat([df_prev, pd.DataFrame([nuova_riga])], ignore_index=True)
        df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
        st.success(f"✅ Preventivo generato: {out_path.name}")
        st.rerun()

    # === Elenco preventivi cliente ===
    st.divider()
    st.markdown("### 📂 Elenco Preventivi Cliente")
    prev_cli = df_prev[df_prev["ClienteID"] == sel_id]
    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        for _, r in prev_cli.iterrows():
            path = Path(r["Percorso"])
            col1, col2, col3 = st.columns([0.6, 0.25, 0.15])
            col1.markdown(f"**{r['NumeroOfferta']}** — {r['Template']}  \n📅 {r['DataCreazione']}")
            if path.exists():
                with open(path, "rb") as f:
                    col2.download_button("⬇️ Scarica", f.read(), file_name=path.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            if col3.button("🗑 Elimina", key=f"del_prev_{sel_id}_{r['NumeroOfferta']}", use_container_width=True):
                try:
                    if path.exists(): path.unlink()
                    df_prev = df_prev[~(df_prev["NumeroOfferta"] == r["NumeroOfferta"])]
                    df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
                    st.success("🗑 Preventivo eliminato."); st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore eliminazione: {e}")

# =====================================
# 📅 PAGINA RECALL E VISITE
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📅 Gestione Recall e Visite</h2>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    filtro_nome = col1.text_input("🔍 Cerca per nome cliente")
    filtro_citta = col2.text_input("🏙️ Cerca per città")

    df = df_cli.copy()
    if filtro_nome:
        df = df[df["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        df = df[df["Citta"].str.contains(filtro_citta, case=False, na=False)]

    oggi = pd.Timestamp.now().normalize()
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

    st.markdown("### 🔔 Recall e Visite imminenti (entro 30 giorni)")
    imminenti = df[
        (df["ProssimoRecall"].between(oggi, oggi+pd.DateOffset(days=30))) |
        (df["ProssimaVisita"].between(oggi, oggi+pd.DateOffset(days=30)))
    ]
    if imminenti.empty:
        st.success("✅ Nessun richiamo o visita imminente.")
    else:
        for i, r in imminenti.iterrows():
            col1, col2, col3, col4 = st.columns([2, 1, 1, 0.7])
            col1.markdown(f"**{r['RagioneSociale']}**")
            col2.markdown(fmt_date(r["ProssimoRecall"]))
            col3.markdown(fmt_date(r["ProssimaVisita"]))
            if col4.button("📂 Apri", key=f"imm_{i}", use_container_width=True):
                st.session_state.update({"selected_cliente": r["ClienteID"], "nav_target": "Clienti"}); st.rerun()

    st.divider()
    st.markdown("### ⚠️ Recall e Visite scaduti")
    recall_vecchi = df[df["UltimoRecall"].notna() & (df["UltimoRecall"] < oggi - pd.DateOffset(months=3))]
    visite_vecchie = df[df["UltimaVisita"].notna() & (df["UltimaVisita"] < oggi - pd.DateOffset(months=6))]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📞 Recall > 3 mesi fa")
        if recall_vecchi.empty: st.info("✅ Nessun recall scaduto.")
        else:
            for i, r in recall_vecchi.iterrows():
                c1, c2, c3 = st.columns([2.5, 1.2, 0.8])
                c1.markdown(f"**{r['RagioneSociale']}**")
                c2.markdown(fmt_date(r["UltimoRecall"]))
                if c3.button("📂 Apri", key=f"rec_{i}", use_container_width=True):
                    st.session_state.update({"selected_cliente": r["ClienteID"], "nav_target": "Clienti"}); st.rerun()

    with col2:
        st.markdown("#### 👣 Visite > 6 mesi fa")
        if visite_vecchie.empty: st.info("✅ Nessuna visita scaduta.")
        else:
            for i, r in visite_vecchie.iterrows():
                c1, c2, c3 = st.columns([2.5, 1.2, 0.8])
                c1.markdown(f"**{r['RagioneSociale']}**")
                c2.markdown(fmt_date(r["UltimaVisita"]))
                if c3.button("📂 Apri", key=f"vis_{i}", use_container_width=True):
                    st.session_state.update({"selected_cliente": r["ClienteID"], "nav_target": "Clienti"}); st.rerun()
# ======== FINE BLOCCO 3 ========
# =====================================
# 📋 PAGINA LISTA COMPLETA CLIENTI E SCADENZE
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Scadenze Contratti")
    oggi = pd.Timestamp.now().normalize()

    df_ct = df_ct.copy()
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    df_ct["Stato"] = df_ct["Stato"].astype(str).str.lower().fillna("")
    attivi = df_ct[df_ct["Stato"] != "chiuso"]

    prime_scadenze = (
        attivi.groupby("ClienteID")["DataFine"]
        .min()
        .reset_index()
        .rename(columns={"DataFine": "PrimaScadenza"})
    )

    merged = df_cli.merge(prime_scadenze, on="ClienteID", how="left")
    merged["GiorniMancanti"] = (merged["PrimaScadenza"] - oggi).dt.days

    def badge(row):
        if pd.isna(row["PrimaScadenza"]): return "⚪ Nessuna"
        g = row["GiorniMancanti"]; d = fmt_date(row["PrimaScadenza"])
        if g < 0: return f"⚫ Scaduto ({d})"
        if g <= 30: return f"🔴 {d}"
        if g <= 90: return f"🟡 {d}"
        return f"🟢 {d}"
    merged["ScadenzaBadge"] = merged.apply(badge, axis=1)

    # === FILTRI ===
    st.markdown("### 🔍 Filtri principali")
    col1, col2, col3, col4 = st.columns(4)
    filtro_nome = col1.text_input("Cerca per nome cliente")
    filtro_citta = col2.text_input("Cerca per città")
    filtro_tmk = col3.selectbox("Filtra per TMK", ["Tutti", "Giulia", "Antonella", "Annalisa", "Laura"], index=0)
    sort_mode = col4.radio("Ordina per:", ["Nome (A→Z)", "Scadenza"], horizontal=True)

    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]
    if filtro_tmk != "Tutti":
        merged = merged[merged["TMK"] == filtro_tmk]
    if sort_mode == "Nome (A→Z)":
        merged = merged.sort_values("RagioneSociale", ascending=True)
    else:
        merged = merged.sort_values("PrimaScadenza", ascending=True, na_position="last")

    st.markdown("### 📇 Elenco Clienti e Scadenze")
    if merged.empty:
        st.warning("❌ Nessun cliente trovato con i criteri selezionati.")
        return

    for i, r in merged.iterrows():
        c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.3, 1, 0.7])
        c1.markdown(f"**{r['RagioneSociale']}**")
        c2.markdown(r.get("Citta","") or "—")
        c3.markdown(r["ScadenzaBadge"], unsafe_allow_html=True)
        c4.markdown(r.get("TMK","") or "—")
        if c5.button("📂 Apri", key=f"apri_cli_{i}", use_container_width=True):
            st.session_state.update({
                "selected_cliente": str(r["ClienteID"]),
                "nav_target": "Clienti"
            })
            st.rerun()
    st.caption(f"📋 Totale clienti mostrati: **{len(merged)}**")

# =====================================
# 🧩 FIX DATE AUTOMATICO UNA VOLTA SOLA
# =====================================
def fix_inverted_dates(series: pd.Series, col_name: str = "") -> pd.Series:
    fixed, count = [], 0
    for val in series:
        if not val or str(val).strip() in ["", "NaN", "None"]:
            fixed.append(""); continue
        try:
            d1 = pd.to_datetime(val, dayfirst=True, errors="coerce")
            d2 = pd.to_datetime(val, dayfirst=False, errors="coerce")
            parsed = d1
            if not pd.isna(d1) and not pd.isna(d2) and d1 != d2:
                if d1.day <= 12 and d2.day > 12:
                    parsed = d2; count += 1
            fixed.append(fmt_date(parsed))
        except Exception: fixed.append("")
    if count > 0:
        st.info(f"🔄 {count} date corrette nella colonna **{col_name}**.")
    return pd.Series(fixed)

def fix_dates_once(df_cli: pd.DataFrame, df_ct: pd.DataFrame):
    if st.session_state.get("_date_fix_done", False):
        return df_cli, df_ct
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        if c in df_cli.columns:
            df_cli[c] = fix_inverted_dates(df_cli[c], c)
    for c in ["DataInizio","DataFine"]:
        if c in df_ct.columns:
            df_ct[c] = fix_inverted_dates(df_ct[c], c)
    save_csv(df_cli, CLIENTI_CSV); save_csv(df_ct, CONTRATTI_CSV)
    st.toast("✅ Date corrette e salvate.")
    st.session_state["_date_fix_done"] = True
    return df_cli, df_ct

# =====================================
# 🚀 MAIN APP — AVVIO E ROUTING COMPLETO
# =====================================
def main():
    # --- LOGIN ---
    user, role = do_login_fullscreen()
    if not user: st.stop()

    # --- STORAGE DINAMICO ---
    global CLIENTI_CSV, CONTRATTI_CSV
    base_clienti = STORAGE_DIR / "clienti.csv"
    base_contratti = STORAGE_DIR / "contratti_clienti.csv"
    gabriele_clienti = STORAGE_DIR / "gabriele" / "clienti.csv"
    gabriele_contratti = STORAGE_DIR / "gabriele" / "contratti_clienti.csv"

    if user == "fabio":
        visibilita, ruolo_scrittura = "tutti","full"
        CLIENTI_CSV, CONTRATTI_CSV = base_clienti, base_contratti
    elif user in ["emanuela","claudia"]:
        visibilita, ruolo_scrittura = "tutti","full"
    elif user in ["giulia","antonella"]:
        visibilita, ruolo_scrittura = "tutti","limitato"
    elif user in ["gabriele","laura","annalisa"]:
        visibilita, ruolo_scrittura = "gabriele","limitato"
        CLIENTI_CSV, CONTRATTI_CSV = gabriele_clienti, gabriele_contratti
    else:
        visibilita, ruolo_scrittura = "solo_propri","limitato"

    # --- SIDEBAR ---
    st.sidebar.image(LOGO_URL, width=150)
    st.sidebar.success(f"👤 {user} — Ruolo: {role}")
    st.sidebar.info(f"📂 File in uso: {CLIENTI_CSV.name}")

    # --- CARICAMENTO DATI (cache) ---
    with st.spinner("Caricamento dati..."):
        df_cli = load_csv(CLIENTI_CSV, CLIENTI_COLS)
        df_ct = load_csv(CONTRATTI_CSV, CONTRATTI_COLS)
        if visibilita == "tutti":
            try:
                gcli = load_csv(gabriele_clienti, CLIENTI_COLS)
                gct = load_csv(gabriele_contratti, CONTRATTI_COLS)
                df_cli = pd.concat([df_cli, gcli], ignore_index=True)
                df_ct = pd.concat([df_ct, gct], ignore_index=True)
            except Exception as e:
                st.warning(f"⚠️ Impossibile caricare i dati di Gabriele: {e}")

    df_cli, df_ct = fix_dates_once(df_cli, df_ct)
    st.session_state["ruolo_scrittura"] = ruolo_scrittura
    st.session_state["visibilita"] = visibilita

    # --- PAGINE ---
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "Preventivi": lambda a,b,r: page_preventivi(a,r),
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti,
    }

    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()), index=0)
    if "nav_target" in st.session_state:
        target = st.session_state.pop("nav_target")
        if target in PAGES: page = target

    PAGES[page](df_cli, df_ct, ruolo_scrittura)

# =====================================
# AVVIO APP
# =====================================
if __name__ == "__main__":
    main()
# ======== FINE BLOCCO 4 ========
