from __future__ import annotations
from pathlib import Path
from typing import Tuple
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ======================================================================================
# ------------------------------- LOGIN / AUTH (prima di tutto) ------------------------
# ======================================================================================

def _read_users_from_secrets() -> dict:
    auth = st.secrets.get("auth", {})
    return auth.get("users", {}) or {}

def _login_page(users: dict) -> None:
    st.title("GESTIONALE CLIENTI – SHT")
    st.subheader("Login")

    with st.form("login_form"):
        usr = st.selectbox("Utente", list(users.keys()))
        pwd = st.text_input("Password", type="password")
        ok  = st.form_submit_button("Entra", use_container_width=True)

    if ok:
        real_pwd = users.get(usr, {}).get("password", "")
        role     = users.get(usr, {}).get("role", "viewer")
        if pwd == real_pwd:
            st.session_state["auth_user"] = usr
            st.session_state["auth_role"] = role
            st.rerun()
        else:
            st.error("Password errata")

def require_login() -> Tuple[str, str]:
    users = _read_users_from_secrets()
    if not users:
        st.title("GESTIONALE CLIENTI – SHT")
        st.error("Autenticazione non configurata. Aggiungi [auth.users] nei Secrets.")
        st.stop()

    if "auth_user" in st.session_state and "auth_role" in st.session_state:
        return st.session_state["auth_user"], st.session_state["auth_role"]

    _login_page(users)
    st.stop()

def sidebar_userbox() -> None:
    if "auth_user" in st.session_state:
        st.sidebar.markdown(f"**Utente:** {st.session_state['auth_user']}")
        st.sidebar.caption(f"Ruolo: {st.session_state.get('auth_role','viewer')}")
        if st.sidebar.button("Logout", use_container_width=True):
            for k in ("auth_user", "auth_role"):
                st.session_state.pop(k, None)
            st.rerun()

# ======================================================================================
# --------------------------- Utilities caricamento/gestione dati ----------------------
# ======================================================================================

STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage"))

CLIENTI_COLS = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]
CONTRATTI_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]
PREVENTIVI_COLS = ["PreventivoID","ClienteID","Data","Numero","File","Totale"]

def ensure_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]

def load_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    try:
        if path.exists():
            df = pd.read_csv(path, dtype=str).fillna("")
        else:
            df = pd.DataFrame(columns=cols)
    except Exception:
        df = pd.DataFrame(columns=cols)
    return ensure_cols(df, cols)

def to_date(x):
    if x is None or x == "" or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    if isinstance(x, pd.Timestamp):
        return x
    try:
        return pd.to_datetime(str(x).strip(), errors="coerce", dayfirst=True)
    except Exception:
        return pd.NaT

def fmt_date(d):
    if d is None or d == "" or (isinstance(d, float) and pd.isna(d)):
        return ""
    try:
        return pd.to_datetime(d).strftime("%d/%m/%Y")
    except Exception:
        return ""

# ======================================================================================
# ----------------------------- HTML table renderer compatibile ------------------------
# ======================================================================================

TABLE_CSS = """
<style>
.ctr-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th, .ctr-table td { border: 1px solid #d0d7de; padding: 8px 10px; font-size: 13px; vertical-align: top; }
.ctr-table th { background: #e3f2fd; font-weight: 600; }
.ctr-row-closed td { background: #ffefef; color: #8a0000; }
.ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
"""

def show_html_table(html: str, *, height: int = 420):
    components.html(html, height=height, scrolling=True)

def html_table(df: pd.DataFrame, *, closed_mask: pd.Series | None = None) -> str:
    if df is None or df.empty:
        return TABLE_CSS + "<div style='padding:8px;color:#666'>Nessun dato</div>"

    cols = list(df.columns)
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>"

    rows_html = []
    # attenzione: uso il positional i per closed_mask
    for i, row in enumerate(df.itertuples(index=False)):
        tr_class = " class='ctr-row-closed'" if (closed_mask is not None and bool(closed_mask.iloc[i])) else ""
        tds = []
        for c, val in zip(cols, row):
            sval = "" if pd.isna(val) else str(val)
            sval = sval.replace("\n", "<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows_html.append(f"<tr{tr_class}>" + "".join(tds) + "</tr>")

    tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
    return TABLE_CSS + f"<table class='ctr-table'>{thead}{tbody}</table>"

# ======================================================================================
# -------------------------------------- DASHBOARD -------------------------------------
# ======================================================================================

KPI_CARD_CSS = """
<style>
.kpi-wrap{display:grid;grid-template-columns:1fr;gap:12px;margin:6px 0 14px 0}
@media(min-width:900px){.kpi-wrap{grid-template-columns:1fr 1fr 1fr 1fr}}
.kpi{border:2px solid #e5e7eb;border-radius:16px;padding:18px 22px;background:#fff}
.kpi h4{margin:0 0 8px 0;font-size:14px;color:#374151;font-weight:600}
.kpi .v{font-size:28px;font-weight:800;color:#111827}
.kpi.green{border-color:#cfe9db}
.kpi.red{border-color:#f5c2c0}
.kpi.yellow{border-color:#f6e4b5}
</style>
"""

def kpi_grid_html(clienti_attivi:int, contratti_aperti:int, contratti_chiusi:int, contratti_anno:int, year_now:int)->str:
    # HTML senza indentazioni, per evitare che Markdown lo tratti come code block
    return (
        KPI_CARD_CSS +
        '<div class="kpi-wrap">'
        '<div class="kpi"><h4>Clienti attivi</h4><div class="v">'+str(clienti_attivi)+'</div></div>'
        '<div class="kpi green"><h4>Contratti aperti</h4><div class="v">'+str(contratti_aperti)+'</div></div>'
        '<div class="kpi red"><h4>Contratti chiusi</h4><div class="v">'+str(contratti_chiusi)+'</div></div>'
        '<div class="kpi yellow"><h4>Contratti '+str(year_now)+'</h4><div class="v">'+str(contratti_anno)+'</div></div>'
        '</div>'
    )

def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("## Dashboard")

    today = pd.Timestamp.today().normalize()
    year_now = today.year

    ct = df_ct.copy()
    stato = ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = int((stato != "chiuso").sum())
    contratti_chiusi = int((stato == "chiuso").sum())
    ct["DataInizioD"] = ct["DataInizio"].apply(to_date)
    contratti_anno = int((ct["DataInizioD"].dt.year == year_now).sum())
    clienti_attivi = int(df_cli["ClienteID"].nunique())

    # RENDER KPI in iframe (niente più HTML “in chiaro”)
    components.html(
        kpi_grid_html(clienti_attivi, contratti_aperti, contratti_chiusi, contratti_anno, year_now),
        height=150,
        scrolling=False
    )

    # Cerca cliente
    st.markdown("#### Cerca cliente")
    q = st.text_input("Digita il nome o l'ID cliente...", label_visibility="collapsed")
    if q.strip():
        filt = df_cli[
            df_cli["RagioneSociale"].str.contains(q, case=False, na=False) |
            df_cli["ClienteID"].astype(str).str.contains(q, na=False)
        ]
        if not filt.empty:
            fid = str(filt.iloc[0]["ClienteID"])
            if st.button(f"Apri scheda cliente {fid}"):
                st.session_state["nav_page"] = "Clienti"
                st.session_state["selected_client_id"] = fid
                st.rerun()

    st.divider()

    # Contratti in scadenza (entro 6 mesi)
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    temp = df_ct.copy()
    temp["DataFineD"] = temp["DataFine"].apply(to_date)
    open_mask = temp["Stato"].fillna("aperto").str.lower() != "chiuso"
    within_6m = (temp["DataFineD"].notna() &
                 (temp["DataFineD"] >= today) &
                 (temp["DataFineD"] <= today + pd.DateOffset(months=6)))
    scad = temp[open_mask & within_6m].copy()
    if not scad.empty:
        scad = scad.sort_values(["ClienteID", "DataFineD"])
        scad = scad.groupby("ClienteID", as_index=False).first()

    if scad.empty:
        show_html_table(html_table(pd.DataFrame()), height=160)
    else:
        labels = df_cli.set_index("ClienteID")["RagioneSociale"]
        disp = pd.DataFrame({
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
            "DataFine": scad["DataFineD"].apply(fmt_date),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "TotRata": scad["TotRata"].apply(lambda x: "" if x=="" else f"{pd.to_numeric(x, errors='coerce') or 0:.2f}")
        })
        show_html_table(html_table(disp), height=220)

    # Ultimi recall / visite
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecallD"] = cli["UltimoRecall"].apply(to_date)
        soglia = today - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecallD"].notna() & (cli["UltimoRecallD"] <= soglia)].copy()
        tab = r.loc[:, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]].copy()
        tab["UltimoRecall"]   = tab["UltimoRecall"].apply(fmt_date)
        tab["ProssimoRecall"] = tab["ProssimoRecall"].apply(fmt_date)
        show_html_table(html_table(tab), height=260)

    with c2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisitaD"] = cli["UltimaVisita"].apply(to_date)
        soglia_v = today - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisitaD"].notna() & (cli["UltimaVisitaD"] <= soglia_v)].copy()
        tabv = v.loc[:, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]].copy()
        tabv["UltimaVisita"]   = tabv["UltimaVisita"].apply(fmt_date)
        tabv["ProssimaVisita"] = tabv["ProssimaVisita"].apply(fmt_date)
        show_html_table(html_table(tabv), height=260)

# ======================================================================================
# ----------------------------- Placeholder “Clienti” e “Contratti” --------------------
# ======================================================================================

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("## Clienti")
    st.info("Pagina Clienti (placeholder). La completiamo dopo, la dashboard resta invariata.")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("## Contratti")
    st.info("Pagina Contratti (placeholder). La realizziamo dopo, con tabella completa.")

# ======================================================================================
# -------------------------------------------- MAIN ------------------------------------
# ======================================================================================

PAGES = {
    "Dashboard": page_dashboard,
    "Clienti": page_clienti,
    "Contratti": page_contratti,
}

def main():
    # 1) LOGIN
    user, role = require_login()
    sidebar_userbox()

    # 2) MENU
    st.sidebar.title("Menu")
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Dashboard"
    st.session_state["nav_page"] = st.sidebar.radio(
        label="", options=list(PAGES.keys()),
        index=list(PAGES.keys()).index(st.session_state["nav_page"]),
        label_visibility="collapsed",
    )

    # 3) DATI
    df_cli = load_csv(STORAGE_DIR / "clienti.csv", CLIENTI_COLS)
    df_ct  = load_csv(STORAGE_DIR / "contratti_clienti.csv", CONTRATTI_COLS)
    _      = load_csv(STORAGE_DIR / "preventivi.csv", PREVENTIVI_COLS)

    # 4) Banner titolo (non tocco il layout sotto)
    st.markdown("### GESTIONALE CLIENTI – SHT")

    # 5) PAGE DISPATCH
    page_fn = PAGES[st.session_state["nav_page"]]
    page_fn(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
