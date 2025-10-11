# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Tuple
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# --------------------------------------------------
# CONFIG BASE
# --------------------------------------------------
st.set_page_config(page_title="SHT – Gestione Clienti", layout="wide", page_icon="🗂️")

def get_storage_dir() -> Path:
    base = st.secrets.get("LOCAL_STORAGE_DIR", "storage")
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p

STORAGE = get_storage_dir()
CLIENTI_CSV   = STORAGE / "clienti.csv"
CONTRATTI_CSV = STORAGE / "contratti_clienti.csv"

CLIENTI_COLS = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]
CONTRATTI_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]

# --------------------------------------------------
# UTILITY DATE
# --------------------------------------------------
def to_date(x):
    if x is None or x == "" or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    if isinstance(x, pd.Timestamp):
        return x
    return pd.to_datetime(str(x).strip(), errors="coerce", dayfirst=True)

def to_date_series(s: pd.Series) -> pd.Series:
    return s.apply(to_date)

def fmt_date(d):
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%d/%m/%Y")

# --------------------------------------------------
# HTML/CSS
# --------------------------------------------------
BASE_CSS = """
<style>
/* contenitore largo */
.block-container { padding-top: 1rem; max-width: 1400px; }

/* header brand */
.sht-header{
  width:100%; padding:14px 18px; margin: 0 0 10px 0;
  border:1px solid #d0d7de; border-radius:12px; background:#ffffff;
}
.sht-title{ font-size:20px; font-weight:700; letter-spacing:.4px; color:#0f172a; }

/* KPI dashboard (layout "buono") */
.kpi-row{display:flex;gap:18px;flex-wrap:wrap;margin:8px 0 16px 0}
.kpi{flex:1 1 260px;background:#fff;border:1px solid #d0d7de;border-radius:14px;padding:16px 18px;}
.kpi .t{color:#475569;font-weight:600;font-size:15px}
.kpi .v{font-weight:800;font-size:28px;margin-top:6px}
.kpi.green{box-shadow:0 0 0 2px #d1fae5 inset}
.kpi.red{box-shadow:0 0 0 2px #fee2e2 inset}
.kpi.yellow{box-shadow:0 0 0 2px #fef3c7 inset}

/* tabelle */
.ctr-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th, .ctr-table td {
  border: 1px solid #d0d7de; padding: 8px 10px; font-size: 13px; vertical-align: top;
}
.ctr-table th { background: #e3f2fd; font-weight: 600; }
.ctr-row-closed td { background: #ffefef; color: #8a0000; }
.ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
"""
st.markdown(BASE_CSS, unsafe_allow_html=True)

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

# --------------------------------------------------
# STORAGE
# --------------------------------------------------
def _ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]

def read_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype=str).fillna("")
    return _ensure_cols(df, cols)

@st.cache_data(show_spinner=False)
def load_clienti() -> pd.DataFrame:
    return read_csv(CLIENTI_CSV, CLIENTI_COLS)

@st.cache_data(show_spinner=False)
def load_contratti() -> pd.DataFrame:
    return read_csv(CONTRATTI_CSV, CONTRATTI_COLS)

def save_clienti(df: pd.DataFrame):
    df = _ensure_cols(df, CLIENTI_COLS)
    df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8")
    st.cache_data.clear()

def save_contratti(df: pd.DataFrame):
    df = _ensure_cols(df, CONTRATTI_COLS)
    df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8")
    st.cache_data.clear()

# --------------------------------------------------
# AUTH
# --------------------------------------------------
def _secrets_users() -> dict:
    # atteso formato: [auth.users.fabio] ...
    try:
        return st.secrets["auth"]["users"]
    except Exception:
        return {}

def require_login() -> Tuple[str,str]:
    if "user" in st.session_state and st.session_state.get("user"):
        return st.session_state["user"], st.session_state.get("role","viewer")
    st.title("SHT – Gestione Clienti")
    st.caption("Accedi con le credenziali impostate nei Secrets.")
    with st.form("login"):
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Entra")
    if ok:
        users = _secrets_users()
        rec = users.get(u)
        if rec and str(rec.get("password")) == p:
            st.session_state["user"] = u
            st.session_state["role"] = rec.get("role","viewer")
            st.success(f"Benvenuto, {u}!")
            st.rerun()
        else:
            st.error("Credenziali non valide.")
    st.stop()

# --------------------------------------------------
# PAGINE
# --------------------------------------------------
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    # KPI (layout buono: 4 box colorati)
    today = pd.Timestamp.today().normalize()
    year_now = today.year
    stato = df_ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = int((stato != "chiuso").sum())
    contratti_chiusi = int((stato == "chiuso").sum())
    contratti_anno   = int((to_date_series(df_ct["DataInizio"]).dt.year == year_now).sum())
    clienti_attivi   = int(df_cli["ClienteID"].nunique())

    st.markdown('<div class="kpi-row">', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi"><div class="t">Clienti attivi</div><div class="v">{clienti_attivi}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi green"><div class="t">Contratti aperti</div><div class="v">{contratti_aperti}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi red"><div class="t">Contratti chiusi</div><div class="v">{contratti_chiusi}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="kpi yellow"><div class="t">Contratti {year_now}</div><div class="v">{contratti_anno}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Ricerca cliente
    st.markdown("**Cerca cliente**")
    q = st.text_input("Digita il nome o l'ID cliente…", label_visibility="collapsed")
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
        scad = scad.sort_values(["ClienteID","DataFine"]).groupby("ClienteID", as_index=False).first()
        disp = pd.DataFrame({
            "NumeroContratto":    scad["NumeroContratto"].fillna(""),
            "DataFine":           scad["DataFine"].apply(fmt_date),
            "DescrizioneProdotto":scad["DescrizioneProdotto"].fillna(""),
            "TotRata":            scad["TotRata"].apply(lambda x: f"{pd.to_numeric(x, errors='coerce') or 0:.2f}")
        })
    else:
        disp = pd.DataFrame(columns=["NumeroContratto","DataFine","DescrizioneProdotto","TotRata"])
    show_html(html_table(disp), height=240)

    # Ultimi recall (> 3 mesi) e Ultime visite (> 6 mesi)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        if "UltimoRecall" not in cli.columns: cli["UltimoRecall"]=""
        if "ProssimoRecall" not in cli.columns: cli["ProssimoRecall"]=""
        cli["_UltimoRecall"] = to_date_series(cli["UltimoRecall"])
        soglia = today - pd.DateOffset(months=3)
        r = cli[cli["_UltimoRecall"].notna() & (cli["_UltimoRecall"] <= soglia)].copy()
        tab = r.loc[:, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]]
        show_html(html_table(tab), height=260)

    with c2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        if "UltimaVisita" not in cli.columns: cli["UltimaVisita"]=""
        if "ProssimaVisita" not in cli.columns: cli["ProssimaVisita"]=""
        cli["_UltimaVisita"] = to_date_series(cli["UltimaVisita"])
        soglia_v = today - pd.DateOffset(months=6)
        v = cli[cli["_UltimaVisita"].notna() & (cli["_UltimaVisita"] <= soglia_v)].copy()
        tab = v.loc[:, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]]
        show_html(html_table(tab), height=260)

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")

    if df_cli.empty:
        st.info("Nessun cliente.")
        return

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
        return
    sel_id = sel.split(" — ")[0] if " — " in sel else str(opts.iloc[0]["ClienteID"])

    row = df_cli[df_cli["ClienteID"].astype(str)==sel_id]
    if row.empty:
        st.info("Cliente non trovato.")
        return
    r = row.iloc[0]

    c1, c2 = st.columns(2)
    with c1:
        st.write("**Ragione Sociale**:", r.get("RagioneSociale",""))
        st.write("**Persona di riferimento**:", r.get("PersonaRiferimento",""))
        st.write("**Indirizzo**:", r.get("Indirizzo",""))
        st.write("**Città**:", r.get("Citta",""), " **CAP**:", r.get("CAP",""))
        st.write("**Email**:", r.get("Email",""))
        st.write("**Telefono**:", r.get("Telefono",""))
    with c2:
        st.write("**Partita IVA**:", r.get("PartitaIVA",""))
        st.write("**IBAN**:", r.get("IBAN",""))
        st.write("**SDI**:", r.get("SDI",""))
        st.write("**Ultimo Recall**:", r.get("UltimoRecall",""))
        st.write("**Ultima Visita**:", r.get("UltimaVisita",""))

    st.markdown("---")
    if st.button("➡️ Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = sel_id
        st.rerun()

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti (rosso = chiusi)")

    if df_cli.empty:
        st.info("Nessun cliente.")
        return

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
    sel_id = sel.split(" — ")[0] if " — " in sel else str(opts.iloc[0]["ClienteID"])

    # contratti del cliente
    ct = df_ct[df_ct["ClienteID"].astype(str)==sel_id].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
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
                    save_contratti(df_ct)
                    st.success("Contratto riaperto.")
                    st.rerun()
            else:
                if st.button("Chiudi", key=f"close_{idx}"):
                    df_ct.loc[idx, "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.success("Contratto chiuso.")
                    st.rerun()

    st.markdown("---")
    st.markdown("### Tabella completa")
    view = ct.copy()
    view["DataInizio"] = to_date_series(view["DataInizio"]).apply(fmt_date)
    view["DataFine"]   = to_date_series(view["DataFine"]).apply(fmt_date)
    def _fmt_num(x):
        v = pd.to_numeric(x, errors="coerce")
        return "" if pd.isna(v) else f"{float(v):.2f}"
    if "TotRata" in view.columns:
        view["TotRata"] = view["TotRata"].apply(_fmt_num)
    cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
            "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    view = view[[c for c in cols if c in view.columns]]
    closed_mask = view["Stato"].fillna("").str.lower().eq("chiuso")
    show_html(html_table(view, closed_mask=closed_mask), height=340)

# --------------------------------------------------
# MAIN
# --------------------------------------------------
def main():
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
