# app.py — SHT Gestione Clienti (Streamlit 1.50)

from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime
from typing import Tuple

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# -------------------------- UTIL --------------------------

def get_storage_dir() -> Path:
    """Rileva cartella storage da secrets, default ./storage"""
    backend = st.secrets.get("STORAGE_BACKEND", "local")
    if backend != "local":
        # In questa versione gestiamo solo 'local'
        st.warning("STORAGE_BACKEND non 'local': uso storage locale.")
    base = st.secrets.get("LOCAL_STORAGE_DIR", "storage")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p

STORAGE = get_storage_dir()

# File paths
CLIENTI_CSV   = STORAGE / "clienti.csv"
CONTRATTI_CSV = STORAGE / "contratti_clienti.csv"
PREVENTIVI_CSV= STORAGE / "preventivi.csv"

# Campi minimi
CLIENTI_COLUMNS = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]
CONTRATTI_COLUMNS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]

def read_csv_safe(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path, dtype=str).fillna("")
    # assicura tutte le colonne
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    # ordina colonne
    df = df[[c for c in columns]]
    return df

def save_csv_safe(df: pd.DataFrame, path: Path):
    df.to_csv(path, index=False)

def to_date(x):
    """Parsa date (dd/mm/yyyy supportato). Restituisce pd.Timestamp o NaT"""
    if x is None or x == "" or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    if isinstance(x, pd.Timestamp):
        return x
    return pd.to_datetime(str(x).strip(), errors="coerce", dayfirst=True)

def fmt_date(d):
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%d/%m/%Y")

def to_date_series(s: pd.Series) -> pd.Series:
    return s.apply(to_date)

# --------------------- HTML helpers -----------------------

DASH_CSS = """
<style>
/* contenitore piena larghezza */
.block-container { padding-top: 1rem; max-width: 1400px; }
/* cards KPI */
.kpi-grid{ display:grid; grid-template-columns: repeat(4, minmax(220px,1fr)); gap:18px; margin:12px 0 8px 0;}
.kpi-card{
  border:1px solid #d0d7de; border-radius: 14px; background:#fff; padding:16px 18px;
}
.kpi-title{ color:#475569; font-weight:600; font-size:15px; }
.kpi-value{ font-weight:800; font-size:28px; margin-top:6px; }

.kpi-green{ box-shadow: 0 0 0 2px #d1fae5 inset; }
.kpi-red{   box-shadow: 0 0 0 2px #fee2e2 inset; }
.kpi-yellow{box-shadow: 0 0 0 2px #fef9c3 inset; }

/* tabelle contratti */
.ctr-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th, .ctr-table td { border: 1px solid #d0d7de; padding: 8px 10px; font-size: 13px; vertical-align: top; }
.ctr-table th { background: #e3f2fd; font-weight: 600; }
.ctr-row-closed td { background: #ffefef; color: #8a0000; }
.ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.sht-header{
  width:100%; padding:14px 18px; margin: 0 0 10px 0;
  border:1px solid #d0d7de; border-radius:12px; background:#ffffff;
}
.sht-title{ font-size:20px; font-weight:700; letter-spacing:.4px; color:#0f172a; }
</style>
"""
st.markdown(DASH_CSS, unsafe_allow_html=True)

def render_brand_header():
    st.markdown(
        '<div class="sht-header"><div class="sht-title">GESTIONALE CLIENTI – SHT</div></div>',
        unsafe_allow_html=True
    )

def show_html(html: str, *, height: int = 420):
    components.html(html, height=height, scrolling=True)

def html_table(df: pd.DataFrame, *, closed_mask: pd.Series | None = None) -> str:
    if df is None or df.empty:
        return "<div style='padding:8px;color:#666'>Nessun dato</div>"

    cols = list(df.columns)
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>"
    rows_html = []
    for i, row in df.iterrows():
        tr_class = " class='ctr-row-closed'" if (closed_mask is not None and i in closed_mask.index and bool(closed_mask.loc[i])) else ""
        tds = []
        for c in cols:
            sval = "" if pd.isna(row.get(c,"")) else str(row.get(c,""))
            sval = sval.replace("\n", "<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows_html.append(f"<tr{tr_class}>" + "".join(tds) + "</tr>")
    tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
    return f"<table class='ctr-table'>{thead}{tbody}</table>"

# ---------------------- AUTH -----------------------------

def _auth_table() -> dict:
    auth = st.secrets.get("auth", {})
    return auth.get("users", {})

def check_credentials(user: str, pwd: str) -> Tuple[bool, str]:
    users = _auth_table()
    info = users.get(user)
    if not info: return False, ""
    return info.get("password") == pwd, info.get("role","viewer")

def login_box() -> Tuple[str,str]:
    with st.form("login"):
        st.text_input("Utente", key="__user")
        st.text_input("Password", type="password", key="__pwd")
        ok = st.form_submit_button("Entra")
    if ok:
        u, p = st.session_state.get("__user",""), st.session_state.get("__pwd","")
        ok, role = check_credentials(u, p)
        if ok:
            st.session_state["user"] = u
            st.session_state["role"] = role
            st.success(f"Benvenuto, {u}!")
            st.rerun()
        else:
            st.error("Credenziali non valide")
    return "", ""

def require_login() -> Tuple[str,str]:
    if "user" in st.session_state and st.session_state.get("user"):
        return st.session_state["user"], st.session_state.get("role","viewer")
    login_box()
    st.stop()

# --------------------- CARICAMENTO DATI ------------------

@st.cache_data(show_spinner=False)
def load_clienti() -> pd.DataFrame:
    df = read_csv_safe(CLIENTI_CSV, CLIENTI_COLUMNS)
    # tipizza
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        df[c] = df[c].astype(str)
    return df

@st.cache_data(show_spinner=False)
def load_contratti() -> pd.DataFrame:
    df = read_csv_safe(CONTRATTI_CSV, CONTRATTI_COLUMNS)
    # tipizza numerici come string (li formatteremo quando serve)
    for c in ["NOL_FIN","NOL_INT","TotRata"]:
        df[c] = df[c].astype(str)
    return df

def persist_contratti(df: pd.DataFrame):
    save_csv_safe(df, CONTRATTI_CSV)
    st.cache_data.clear()  # invalida cache load_contratti

def persist_clienti(df: pd.DataFrame):
    save_csv_safe(df, CLIENTI_CSV)
    st.cache_data.clear()

# ------------------------- PAGINE ------------------------

def kpi_card(label: str, value: str, color: str):
    st.markdown(
        f"""
        <div class="kpi-card {color}">
          <div class="kpi-title">{label}</div>
          <div class="kpi-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    # KPI
    today = pd.Timestamp.today().normalize()
    year_now = today.year

    ct = df_ct.copy()
    stato = ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = (stato != "chiuso").sum()
    contratti_chiusi = (stato == "chiuso").sum()
    contratti_anno = (to_date_series(ct["DataInizio"]).dt.year == year_now).sum()
    clienti_attivi = df_cli["ClienteID"].nunique()

    st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)
    kpi_card("Clienti attivi", f"{clienti_attivi}", "")
    kpi_card("Contratti aperti", f"{contratti_aperti}", "kpi-green")
    kpi_card("Contratti chiusi", f"{contratti_chiusi}", "kpi-red")
    kpi_card(f"Contratti {year_now}", f"{contratti_anno}", "kpi-yellow")
    st.markdown("</div>", unsafe_allow_html=True)

    # Ricerca cliente
    st.markdown("**Cerca cliente**")
    q = st.text_input("Digita nome o ID cliente…", label_visibility="collapsed")
    if q.strip():
        filt = df_cli[
            df_cli["RagioneSociale"].str.contains(q, case=False, na=False) |
            df_cli["ClienteID"].astype(str).str.contains(q, na=False)
        ]
        if not filt.empty:
            sel_id = str(filt.iloc[0]["ClienteID"])
            if st.button(f"Apri scheda cliente {sel_id}"):
                st.session_state["nav_target"] = "Clienti"
                st.session_state["selected_client_id"] = sel_id
                st.rerun()
    st.divider()

    # Contratti in scadenza (entro 6 mesi) — 1 per cliente
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    ct = df_ct.copy()
    ct["DataFine"] = to_date_series(ct["DataFine"])
    open_mask = ct["Stato"].fillna("aperto").str.lower() != "chiuso"
    within_6m = (ct["DataFine"].notna() &
                 (ct["DataFine"] >= today) &
                 (ct["DataFine"] <= today + pd.DateOffset(months=6)))
    scad = ct[open_mask & within_6m].copy()
    if not scad.empty:
        scad = scad.sort_values(["ClienteID","DataFine"])
        scad = scad.groupby("ClienteID", as_index=False).first()

    disp = pd.DataFrame()
    if not scad.empty:
        labels = df_cli.set_index("ClienteID")["RagioneSociale"]
        disp = pd.DataFrame({
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
            "DataFine": scad["DataFine"].apply(fmt_date),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "TotRata": scad["TotRata"].apply(lambda x: f"{pd.to_numeric(x, errors='coerce') or 0:.2f}")
        })
    show_html(html_table(disp), height=240)

    # Ultimi recall (>3m)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        if "UltimoRecall" not in cli.columns:
            cli["UltimoRecall"] = ""
        if "ProssimoRecall" not in cli.columns:
            cli["ProssimoRecall"] = ""

        cli["UltimoRecall_dt"] = to_date_series(cli["UltimoRecall"])
        soglia = today - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall_dt"].notna() & (cli["UltimoRecall_dt"] <= soglia)].copy()
        tab = r.loc[:, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]]
        show_html(html_table(tab), height=260)

    with c2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        for c in ["UltimaVisita","ProssimaVisita"]:
            if c not in cli.columns: cli[c] = ""
        cli["UltimaVisita_dt"] = to_date_series(cli["UltimaVisita"])
        soglia_v = today - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita_dt"].notna() & (cli["UltimaVisita_dt"] <= soglia_v)].copy()
        tab = v.loc[:, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]]
        show_html(html_table(tab), height=260)

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")

    # Prepara lista
    opts = (df_cli.assign(label=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"].astype(str))[["ClienteID","label"]]
            .sort_values("label"))

    default_idx = 0
    preset = st.session_state.get("selected_client_id")
    if preset:
        try:
            default_idx = opts.index[opts["ClienteID"].astype(str) == str(preset)].tolist()[0]
        except Exception:
            default_idx = 0

    sel = st.selectbox("Cliente", opts["label"].tolist(), index=default_idx if len(opts)>0 else 0)
    if len(opts)==0:
        st.info("Nessun cliente.")
        return
    sel_id = str(opts.iloc[st.session_state.get("_selectbox_index", 0) if default_idx==0 else default_idx]["ClienteID"]) \
             if "—" not in sel else sel.split(" — ")[0]

    row = df_cli[df_cli["ClienteID"].astype(str)==sel_id]
    if row.empty:
        st.info("Cliente non trovato.")
        return
    r = row.iloc[0]

    cols = st.columns(2)
    with cols[0]:
        st.write("**Ragione Sociale**:", r.get("RagioneSociale",""))
        st.write("**Persona di riferimento**:", r.get("PersonaRiferimento",""))
        st.write("**Indirizzo**:", r.get("Indirizzo",""))
        st.write("**Città**:", r.get("Citta",""), " **CAP**:", r.get("CAP",""))
        st.write("**Email**:", r.get("Email",""), " **Telefono**:", r.get("Telefono",""))
    with cols[1]:
        st.write("**Partita IVA**:", r.get("PartitaIVA",""))
        st.write("**IBAN**:", r.get("IBAN",""))
        st.write("**SDI**:", r.get("SDI",""))
        st.write("**Ultimo Recall**:", r.get("UltimoRecall",""))
        st.write("**Ultima Visita**:", r.get("UltimaVisita",""))

    st.markdown("---")
    if st.button("Vai alla gestione contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = sel_id
        st.rerun()

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti (rosso = chiusi)")

    # Select cliente
    opts = (df_cli.assign(label=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"].astype(str))[["ClienteID","label"]]
            .sort_values("label"))
    default_idx = 0
    preset = st.session_state.get("selected_client_id")
    if preset:
        try:
            default_idx = opts.index[opts["ClienteID"].astype(str) == str(preset)].tolist()[0]
        except Exception:
            default_idx = 0

    sel = st.selectbox("Cliente", opts["label"].tolist(), index=default_idx if len(opts)>0 else 0)
    if len(opts)==0:
        st.info("Nessun cliente.")
        return
    sel_id = sel.split(" — ")[0] if " — " in sel else str(opts.iloc[0]["ClienteID"])

    # Contratti del cliente
    ct = df_ct[df_ct["ClienteID"].astype(str)==sel_id].copy()
    if ct.empty:
        st.info("Nessun contratto per il cliente selezionato.")
        return

    st.markdown("### Selezione/chiusura righe")
    for i, r in ct.reset_index(drop=False).iterrows():
        idx = r["index"]
        descr = str(r.get("DescrizioneProdotto",""))
        din = fmt_date(to_date(r.get("DataInizio","")))
        dfi = fmt_date(to_date(r.get("DataFine","")))
        durata = str(r.get("Durata",""))
        stato_attuale = str(r.get("Stato","")).lower()

        c1, c2, c3 = st.columns([0.05, 0.75, 0.2])
        with c2:
            st.write(f"— {descr if descr else '(senza descrizione)'}")
            st.caption(f"dal {din or '*'} al {dfi or '*'} · {durata or '*'}")
        with c3:
            if stato_attuale == "chiuso":
                if st.button("Riapri", key=f"reopen_{idx}"):
                    df_ct.loc[idx, "Stato"] = "aperto"
                    persist_contratti(df_ct)
                    st.success("Contratto riaperto.")
                    st.rerun()
            else:
                if st.button("Chiudi", key=f"close_{idx}"):
                    df_ct.loc[idx, "Stato"] = "chiuso"
                    persist_contratti(df_ct)
                    st.success("Contratto chiuso.")
                    st.rerun()

    st.markdown("---")
    st.markdown("### Tabella completa")
    # Tabella con riga rossa se chiuso
    view = ct.copy()
    view["DataInizio"] = to_date_series(view["DataInizio"]).apply(fmt_date)
    view["DataFine"]   = to_date_series(view["DataFine"]).apply(fmt_date)
    view["TotRata"]    = view["TotRata"].apply(lambda x: f"{pd.to_numeric(x, errors='coerce') or 0:.2f}")

    cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
            "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    view = view[[c for c in cols if c in view.columns]]
    closed_mask = view["Stato"].fillna("").str.lower().eq("chiuso")
    show_html(html_table(view, closed_mask=closed_mask), height=320)

# ------------------------- MAIN --------------------------

def main():
    st.set_page_config(page_title="SHT – Gestione Clienti", layout="wide", page_icon="🗂️")
    render_brand_header()

    user, role = require_login()

    df_cli = load_clienti()
    df_ct  = load_contratti()

    pages = ["Dashboard","Clienti","Contratti"]
    default = st.session_state.get("nav_target","Dashboard")
    try:
        idx = pages.index(default)
    except ValueError:
        idx = 0
    page = st.sidebar.radio("Menu", pages, index=idx)
    st.session_state["nav_target"] = page

    if page == "Dashboard":
        page_dashboard(df_cli, df_ct, role)
    elif page == "Clienti":
        page_clienti(df_cli, df_ct, role)
    elif page == "Contratti":
        page_contratti(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
