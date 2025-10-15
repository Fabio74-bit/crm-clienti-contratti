# ==========================
# BLOCCO 1 — CONFIG, UTILS, LOGIN
# ==========================
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


# Imposta la pagina Streamlit più larga (layout ampio)
st.set_page_config(layout="wide", page_title="GESTIONALE CLIENTI – SHT")


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

# Logo statico SHT
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

# Base URL OneDrive (rimane com’era)
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
# I/O DATI
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
# AUTH — Login a pagina intera
# ==========================
def do_login_fullscreen():
    """Login a pagina intera con logo SHT"""
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    if "auth_user" in st.session_state:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))

    # Layout centrato, copre tutta la pagina
    st.markdown(
        f"""
        <style>
            [data-testid="stSidebar"] {{ display: none; }}
            .main > div:first-child {{ padding-top: 3rem; }}
        </style>
        <div style='display:flex; flex-direction:column; align-items:center; justify-content:center;
                    height:100vh; text-align:center;'>
            <img src="{LOGO_URL}" width="220" style="margin-bottom:25px;">
            <h2>🔐 Accesso al Gestionale SHT</h2>
            <p style='color:grey; font-size:14px;'>Inserisci le tue credenziali per continuare</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    username = st.text_input("👤 Utente", key="login_user")
    password = st.text_input("🔒 Password", type="password", key="login_pwd")

    login_btn = st.button("Entra", use_container_width=True)

    if login_btn:
        if username in users and password == users[username].get("password"):
            st.session_state["auth_user"] = username
            st.session_state["auth_role"] = users[username].get("role", "viewer")
            st.success("✅ Accesso effettuato!")
            st.rerun()

        else:
            st.error("❌ Credenziali errate o utente inesistente.")

    return ("", "")
# ==========================
# BLOCCO 2 — DASHBOARD + CLIENTI + PREVENTIVI
# ==========================

# ==========================
# DASHBOARD (KPI + Contratti + Recall)
# ==========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    now = pd.Timestamp.now().normalize()

    # Header con logo e titolo
    col_logo, col_title = st.columns([0.15, 0.85])
    with col_logo:
        st.image(LOGO_URL, width=110)
    with col_title:
        st.markdown("<h1 style='margin-top:0;'>SHT – CRM Dashboard</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:grey;margin-top:-10px;'>Panoramica generale di clienti, contratti e attività</p>", unsafe_allow_html=True)
    st.divider()

    # === KPI principali ===
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())
    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    new_contracts = df_ct[df_ct["DataInizio"].dt.year == now.year]
    new_contracts_count = len(new_contracts)

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#2196F3"), unsafe_allow_html=True)
    with col2: st.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#009688"), unsafe_allow_html=True)
    with col3: st.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#F44336"), unsafe_allow_html=True)
    with col4: st.markdown(kpi_card("Nuovi contratti (anno)", new_contracts_count, "⭐", "#FFC107"), unsafe_allow_html=True)

    st.divider()

    # === Contratti in scadenza ===
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
        scadenza = scadenza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left").sort_values("DataFine")
        st.markdown("""
        <style>
        .scad-header, .scad-row {
            display:grid; grid-template-columns:38% 22% 20% 12% 8%;
            align-items:center; padding:6px 10px;
        }
        .scad-header {font-weight:600; background:#f0f0f0; border-radius:6px;}
        .scad-row {border-bottom:1px solid #eee;}
        .scad-row:hover {background:#fafafa;}
        </style>
        <div class='scad-header'>
          <div>Cliente</div><div>Contratto</div><div>Scadenza</div><div>Stato</div><div style='text-align:center;'>Apri</div>
        </div>
        """, unsafe_allow_html=True)

        for i, r in scadenza.iterrows():
            st.markdown(
                f"""
                <div class='scad-row'>
                    <div><b>{r['RagioneSociale']}</b></div>
                    <div>{r['NumeroContratto'] or '-'}</div>
                    <div>{fmt_date(r['DataFine'])}</div>
                    <div>{r['Stato']}</div>
                    <div style='text-align:center;'>➡️</div>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("Apri", key=f"scad_{i}_{r['ClienteID']}"):
                st.session_state["selected_client_id"] = r["ClienteID"]
                st.session_state["nav_target"] = "Contratti"
                st.rerun()

    st.divider()

    # === Contratti senza data fine ===
    st.subheader("⏰ Promemoria: Contratti Senza Data Fine")
    senza_fine = df_ct[
        (df_ct["DataFine"].isna()) &
        (df_ct["DataInizio"].notna()) &
        (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]
    if senza_fine.empty:
        st.info("✅ Nessun contratto senza data fine.")
    else:
        senza_fine = senza_fine.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        for _, row in senza_fine.iterrows():
            create_contract_card(row)

    st.divider()

    # === Ultimi Recall / Ultime Visite ===
    st.subheader("📞 Ultimi Recall e Visite Programmate")
    df_cli["UltimoRecall"] = pd.to_datetime(df_cli["UltimoRecall"], errors="coerce", dayfirst=True)
    df_cli["ProssimoRecall"] = pd.to_datetime(df_cli["ProssimoRecall"], errors="coerce", dayfirst=True)
    df_cli["UltimaVisita"] = pd.to_datetime(df_cli["UltimaVisita"], errors="coerce", dayfirst=True)
    df_cli["ProssimaVisita"] = pd.to_datetime(df_cli["ProssimaVisita"], errors="coerce", dayfirst=True)

    recent_recall = df_cli[df_cli["UltimoRecall"].notna()].sort_values("UltimoRecall", ascending=False).head(5)
    recent_visite = df_cli[df_cli["UltimaVisita"].notna()].sort_values("UltimaVisita", ascending=False).head(5)

    col_r, col_v = st.columns(2)
    with col_r:
        st.markdown("#### 🔁 Ultimi Recall")
        st.dataframe(recent_recall[["RagioneSociale", "UltimoRecall", "ProssimoRecall"]].fillna(""), use_container_width=True, hide_index=True)
    with col_v:
        st.markdown("#### 🚗 Ultime Visite")
        st.dataframe(recent_visite[["RagioneSociale", "UltimaVisita", "ProssimaVisita"]].fillna(""), use_container_width=True, hide_index=True)


# ==========================
# CLIENTI (Anagrafica + Note + Preventivi)
# ==========================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Gestione Clienti")

    search = st.text_input("🔍 Cerca Cliente per nome o città")
    if search:
        df_cli = df_cli[df_cli["RagioneSociale"].str.contains(search, case=False, na=False)]

    if df_cli.empty:
        st.warning("Nessun cliente trovato.")
        return

    sel = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"])
    cliente = df_cli[df_cli["RagioneSociale"] == sel].iloc[0]
    sel_id = cliente["ClienteID"]

    st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Indirizzo:** {cliente.get('Indirizzo','')} – {cliente.get('Citta','')}")
        st.write(f"**Telefono:** {cliente.get('Telefono','')}")
        st.write(f"**Email:** {cliente.get('Email','')}")
    with col2:
        st.write(f"**P.IVA:** {cliente.get('PartitaIVA','')}")
        st.write(f"**IBAN:** {cliente.get('IBAN','')}")
        st.write(f"**SDI:** {cliente.get('SDI','')}")

    st.divider()

    # === Recall / Visite ===
    st.markdown("### 📅 Recall e Visite Programmate")
    def safe_date(v): return pd.to_datetime(v, errors="coerce", dayfirst=True) if v else None

    ult_recall = safe_date(cliente.get("UltimoRecall"))
    ult_visita = safe_date(cliente.get("UltimaVisita"))

    col1, col2 = st.columns(2)
    with col1:
        new_recall = st.date_input("Ultimo Recall", value=ult_recall if not pd.isna(ult_recall) else None, format="DD/MM/YYYY")
    with col2:
        new_visita = st.date_input("Ultima Visita", value=ult_visita if not pd.isna(ult_visita) else None, format="DD/MM/YYYY")

    if st.button("💾 Aggiorna Recall/Visite"):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "UltimoRecall"] = new_recall.strftime("%d/%m/%Y")
        df_cli.loc[idx, "UltimaVisita"] = new_visita.strftime("%d/%m/%Y")
        df_cli.loc[idx, "ProssimoRecall"] = (pd.to_datetime(new_recall) + timedelta(days=30)).strftime("%d/%m/%Y")
        df_cli.loc[idx, "ProssimaVisita"] = (pd.to_datetime(new_visita) + timedelta(days=180)).strftime("%d/%m/%Y")
        save_clienti(df_cli)
        st.success("✅ Dati aggiornati.")
        st.rerun()

    st.divider()

    # === Modifica Anagrafica ===
    with st.expander("✏️ Modifica Anagrafica Cliente"):
        with st.form("frm_anagrafica"):
            c1, c2, c3 = st.columns(3)
            with c1:
                rag = st.text_input("Ragione Sociale", cliente.get("RagioneSociale", ""))
                ref = st.text_input("Referente", cliente.get("PersonaRiferimento", ""))
                indir = st.text_input("Indirizzo", cliente.get("Indirizzo", ""))
            with c2:
                citta = st.text_input("Città", cliente.get("Citta", ""))
                tel = st.text_input("Telefono", cliente.get("Telefono", ""))
                mail = st.text_input("Email", cliente.get("Email", ""))
            with c3:
                piva = st.text_input("Partita IVA", cliente.get("PartitaIVA", ""))
                sdi = st.text_input("SDI", cliente.get("SDI", ""))
                iban = st.text_input("IBAN", cliente.get("IBAN", ""))

            if st.form_submit_button("💾 Salva Modifiche"):
                i = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[i, ["RagioneSociale","PersonaRiferimento","Indirizzo","Citta","Telefono","Email","PartitaIVA","SDI","IBAN"]] = [rag, ref, indir, citta, tel, mail, piva, sdi, iban]
                save_clienti(df_cli)
                st.success("✅ Anagrafica aggiornata.")
                st.rerun()

    st.divider()

    # === Preventivi DOCX ===
    st.markdown("### 🧾 Crea Nuovo Preventivo")
    if not TEMPLATES_DIR.exists():
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    prev_path = PREVENTIVI_CSV
    df_prev = pd.read_csv(prev_path, dtype=str, sep=",", encoding="utf-8-sig").fillna("") if prev_path.exists() else pd.DataFrame(columns=PREVENTIVI_COLS)

    def gen_offerta(cliente_nome: str) -> str:
        anno = datetime.now().year
        nome = "".join(c for c in cliente_nome if c.isalnum())[:6].upper()
        seq = len(df_prev[df_prev["ClienteID"] == sel_id]) + 1
        return f"OFF-{anno}-{nome}-{seq:03d}"

    with st.form("frm_prev"):
        num = st.text_input("Numero Offerta", gen_offerta(cliente["RagioneSociale"]))
        tpl = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        nome_file = st.text_input("Nome File (es. Offerta_ACME.docx)")
        ok = st.form_submit_button("💾 Genera Preventivo")

        if ok:
            tpl_path = TEMPLATES_DIR / TEMPLATE_OPTIONS[tpl]
            out_path = EXTERNAL_PROPOSALS_DIR / (nome_file or f"{num}.docx")
            doc = Document(tpl_path)
            for p in doc.paragraphs:
                for key, val in {
                    "CLIENTE": cliente.get("RagioneSociale", ""),
                    "CITTA": cliente.get("Citta", ""),
                    "NUMERO_OFFERTA": num,
                    "DATA": datetime.now().strftime("%d/%m/%Y"),
                }.items():
                    p.text = p.text.replace(f"<<{key}>>", str(val))
            doc.save(out_path)
            nuovo = {
                "ClienteID": sel_id, "NumeroOfferta": num, "Template": tpl,
                "NomeFile": out_path.name, "Percorso": str(out_path),
                "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            df_prev = pd.concat([df_prev, pd.DataFrame([nuovo])], ignore_index=True)
            df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")
            st.success(f"✅ Preventivo generato: {out_path.name}")
            st.rerun()

    st.divider()
    prev_cli = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
    st.markdown("### 📂 Elenco Preventivi Cliente")
    if prev_cli.empty:
        st.info("Nessun preventivo disponibile.")
    else:
        for _, r in prev_cli.iterrows():
            col1, col2 = st.columns([0.7, 0.3])
            with col1:
                st.write(f"📄 **{r['NumeroOfferta']}** – {r['Template']} ({r['DataCreazione']})")
            with col2:
                try:
                    with open(r["Percorso"], "rb") as f:
                        st.download_button("⬇️ Scarica", f.read(), r["NomeFile"])
                except:
                    st.warning("File non trovato.")
# ==========================
# BLOCCO 3 — CONTRATTI + LISTA CLIENTI + MAIN
# ==========================

# ==========================
# CONTRATTI (completi e aggiornabili)
# ==========================
def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")


def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Gestione Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente disponibile.")
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
    sel_id = df_cli.iloc[labels[labels == sel_label].index[0]]["ClienteID"]
    rag_soc = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]["RagioneSociale"]

    # === Nuovo Contratto ===
    with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            with c1: num = st.text_input("Numero Contratto")
            with c2: din = st.date_input("Data Inizio", format="DD/MM/YYYY")
            with c3: durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto", height=80)
            col_nf, col_ni, col_tot = st.columns(3)
            with col_nf: nf = st.text_input("NOL_FIN")
            with col_ni: ni = st.text_input("NOL_INT")
            with col_tot: tot = st.text_input("TotRata")

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
                    "Stato": "aperto",
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([row])], ignore_index=True)
                save_contratti(df_ct)
                st.success("✅ Contratto creato.")
                st.rerun()

    # === Tabella Contratti ===
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["DataInizio"] = pd.to_datetime(ct["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    ct["DataFine"] = pd.to_datetime(ct["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")
    ct["TotRata"] = ct["TotRata"].apply(money)

    # === Stile AG Grid ===
    gb = GridOptionsBuilder.from_dataframe(ct)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True)
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

    st.markdown("### 📑 Elenco contratti")
    grid_resp = AgGrid(
        ct,
        gridOptions=grid_opts,
        theme="balham",
        height=400,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
    )

    selected = grid_resp.get("selected_rows", [])
    if selected:
        sel = selected[0]
        st.markdown("### 📝 Dettagli contratto")
        st.info(sel.get("DescrizioneProdotto", ""))
        st.markdown("#### ✏️ Modifica contratto esistente")
        with st.form("frm_edit"):
            col1, col2, col3 = st.columns(3)
            with col1: new_fine = st.date_input("Nuova data fine", value=pd.to_datetime(sel["DataFine"], errors="coerce"), format="DD/MM/YYYY")
            with col2: new_stato = st.selectbox("Stato", ["aperto", "attivo", "chiuso"], index=["aperto","attivo","chiuso"].index(sel["Stato"].lower() if sel["Stato"] else "aperto"))
            with col3: new_tot = st.text_input("TotRata", value=str(sel["TotRata"]))
            new_desc = st.text_area("Descrizione", value=sel.get("DescrizioneProdotto", ""), height=80)

            if st.form_submit_button("💾 Salva modifiche"):
                idx = df_ct.index[
                    (df_ct["ClienteID"].astype(str) == str(sel_id)) &
                    (df_ct["NumeroContratto"] == sel["NumeroContratto"])
                ][0]
                df_ct.loc[idx, ["DataFine", "TotRata", "DescrizioneProdotto", "Stato"]] = [
                    new_fine.strftime("%Y-%m-%d"), new_tot, new_desc, new_stato
                ]
                save_contratti(df_ct)
                st.success("✅ Contratto aggiornato.")
                st.rerun()

    # === Pulsanti Chiudi / Riapri ===
    st.divider()
    st.markdown("### ⚙️ Gestione Stato Contratti")
    for i, r in ct.iterrows():
        col1, col2 = st.columns([0.7, 0.3])
        with col1:
            st.caption(f"{r['NumeroContratto']} — {r['DescrizioneProdotto'][:60]}")
        with col2:
            if (r["Stato"] or "").lower() == "chiuso":
                if st.button("🔓 Riapri", key=f"open_{i}"):
                    df_ct.loc[i, "Stato"] = "aperto"
                    save_contratti(df_ct)
                    st.rerun()
            else:
                if st.button("❌ Chiudi", key=f"close_{i}"):
                    df_ct.loc[i, "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.rerun()

    # === Esportazione CSV / PDF ===
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        csv = ct.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📄 Esporta CSV", csv, f"contratti_{rag_soc}.csv", "text/csv")
    with col2:
        try:
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", size=9)
            pdf.cell(0, 8, safe_text(f"Contratti - {rag_soc}"), ln=1, align="C")
            for _, row in ct.iterrows():
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
# LISTA COMPLETA CLIENTI
# ==========================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Contratti")
    filtro_nome = st.text_input("🔍 Filtra per nome cliente")
    filtro_citta = st.text_input("🏙️ Filtra per città")

    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]], on="ClienteID", how="left")
    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]

    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")

    st.dataframe(merged[["RagioneSociale", "Citta", "NumeroContratto", "DataInizio", "DataFine", "Stato"]], use_container_width=True, hide_index=True)

    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_clienti_contratti.csv", "text/csv")


# ==========================
# MAIN
# ==========================
def main():
    # === LOGIN ===
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    st.sidebar.success(f"Utente: {user} — Ruolo: {role}")

    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📋 Lista Clienti": page_lista_clienti,
    }

    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio(
        "Menu", list(PAGES.keys()),
        index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0,
    )

    df_cli = load_clienti()
    df_ct = load_contratti()
    PAGES[page](df_cli, df_ct, role)


if __name__ == "__main__":
    main()
