# -*- coding: utf-8 -*-
from __future__ import annotations
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime

# -------------------- CONFIG BASE --------------------
st.set_page_config(page_title="SHT – Gestione Clienti", layout="wide")

# -------------------- HELPERS DATE --------------------
def to_date(x):
    """Converte valori vari in Timestamp (accetta dd/mm/yyyy), altrimenti NaT."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    if isinstance(x, pd.Timestamp):
        return x
    try:
        return pd.to_datetime(str(x).strip(), errors="coerce", dayfirst=True)
    except Exception:
        return pd.NaT

def fmt_date(d):
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%d/%m/%Y")

# -------------------- RENDER HTML (iframe) --------------------
def show_html(html: str, *, height: int = 420):
    """Renderizza HTML/CSS dentro un iframe (evita artefatti di st.markdown)."""
    components.html(html, height=height, scrolling=True)

# -------------------- CSS + KPI + TABELLA SEMPLICE --------------------
DASH_CSS = """
<style>
.kpi {
  border:1px solid var(--kpi-border,#d0d7de);
  border-radius:12px;
  padding:16px 18px;
  background:#fff;
}
.kpi .label{
  font-size:16px; color:#667085; margin-bottom:8px;
}
.kpi .value{
  font-size:28px; font-weight:700; color:#111827;
}
.kpi-green  { --kpi-border:#d1f2e3; background:#f3fbf7; }
.kpi-red    { --kpi-border:#ffd6d6; background:#fff5f5; }
.kpi-yellow { --kpi-border:#ffe9a8; background:#fffbeb; }
.kpi-blue   { --kpi-border:#d7e9ff; background:#f1f7ff; }

.table-ctr { width:100%; border-collapse:collapse; table-layout:fixed; }
.table-ctr th, .table-ctr td {
  border:1px solid #d0d7de; padding:8px 10px; font-size:13px; vertical-align:top;
}
.table-ctr th { background:#e3f2fd; font-weight:600; }
</style>
"""

def kpi_card(label: str, value, color: str = "blue") -> str:
    css_class = {"green":"kpi-green","red":"kpi-red","yellow":"kpi-yellow","blue":"kpi-blue"}.get(color,"kpi-blue")
    return f"""
    <div class="kpi {css_class}">
      <div class="label">{label}</div>
      <div class="value">{value}</div>
    </div>
    """

def html_table_simple(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return DASH_CSS + "<div style='padding:8px;color:#666'>Nessun dato</div>"
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in df.columns) + "</tr></thead>"
    body_rows = []
    for _, r in df.iterrows():
        tds = "".join(f"<td>{'' if pd.isna(v) else str(v)}</td>" for v in r.tolist())
        body_rows.append(f"<tr>{tds}</tr>")
    tbody = "<tbody>" + "".join(body_rows) + "</tbody>"
    return DASH_CSS + f"<table class='table-ctr'>{thead}{tbody}</table>"

# -------------------- STORAGE (CSV) --------------------
def _safe_columns(df: pd.DataFrame, needed: list[str]) -> pd.DataFrame:
    for c in needed:
        if c not in df.columns:
            df[c] = pd.Series(index=df.index, dtype="object")
    return df

def load_clienti(path: str = "storage/clienti.csv") -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except FileNotFoundError:
        df = pd.DataFrame(columns=[
            "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP","Telefono",
            "Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
        ])
    needed = ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]
    return _safe_columns(df, needed)

def load_contratti(path: str = "storage/contratti_clienti.csv") -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except FileNotFoundError:
        df = pd.DataFrame(columns=[
            "ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
            "NOL_FIN","NOL_INT","TotRata","Stato"
        ])
    needed = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
              "NOL_FIN","NOL_INT","TotRata","Stato"]
    return _safe_columns(df, needed)

# -------------------- LOGIN --------------------
def login_box() -> tuple[str|None, str|None]:
    st.title("SHT – Gestione Clienti")
    st.write("Accedi con le credenziali impostate in **Secrets**.")
    u = st.text_input("Utente", key="login_user")
    p = st.text_input("Password", type="password", key="login_pass")
    if st.button("Entra"):
        try:
            users = st.secrets["auth"]["users"]
        except Exception:
            st.error("Manca la sezione [auth.users] nei secrets.")
            return None, None
        if u in users and str(p) == str(users[u]["password"]):
            return u, users[u].get("role", "viewer")
        st.error("Credenziali non valide.")
    return None, None

def require_login() -> tuple[str, str]:
    if "user" in st.session_state and "role" in st.session_state:
        return st.session_state["user"], st.session_state["role"]
    user, role = login_box()
    if user:
        st.session_state["user"] = user
        st.session_state["role"] = role
        st.rerun()
    st.stop()  # blocca esecuzione finché non loggato

# -------------------- PAGINE --------------------
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown(DASH_CSS, unsafe_allow_html=True)
    st.subheader("Dashboard")

    # KPI
    today    = pd.Timestamp.today().normalize()
    year_now = today.year

    ct = df_ct.copy()
    stato = ct.get("Stato", pd.Series(index=ct.index)).fillna("aperto").str.lower()
    contratti_aperti = (stato != "chiuso").sum()
    contratti_chiusi = (stato == "chiuso").sum()
    contratti_anno   = (ct.get("DataInizio", pd.Series(index=ct.index)).apply(to_date).dt.year == year_now).sum()
    clienti_attivi   = df_cli.get("ClienteID", pd.Series()).nunique()

    c1,c2,c3,c4 = st.columns([1,1,1,1])
    with c1:
        st.markdown(kpi_card("Clienti attivi",    clienti_attivi,    "blue"),   unsafe_allow_html=True)
    with c2:
        st.markdown(kpi_card("Contratti aperti",  contratti_aperti,  "green"),  unsafe_allow_html=True)
    with c3:
        st.markdown(kpi_card("Contratti chiusi",  contratti_chiusi,  "red"),    unsafe_allow_html=True)
    with c4:
        st.markdown(kpi_card(f"Contratti {year_now}", contratti_anno, "yellow"),unsafe_allow_html=True)

    st.divider()

    # Cerca cliente
    st.markdown("**Cerca cliente**")
    q = st.text_input("Digita il nome o l'ID cliente...", label_visibility="collapsed")
    if q.strip():
        filt = df_cli[
            df_cli["RagioneSociale"].str.contains(q, case=False, na=False) |
            df_cli["ClienteID"].astype(str).str.contains(q, na=False)
        ]
        if not filt.empty:
            fid = str(filt.iloc[0]["ClienteID"])
            if st.button(f"Apri scheda cliente {fid}"):
                st.session_state["nav_target"] = "Clienti"
                st.session_state["selected_client_id"] = fid
                st.rerun()

    st.divider()

    # Contratti in scadenza (entro 6 mesi)
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    ct2 = df_ct.copy()
    ct2["DataFine"] = ct2.get("DataFine", pd.Series(index=ct2.index)).apply(to_date)
    open_mask = ct2.get("Stato", pd.Series(index=ct2.index)).fillna("aperto").str.lower() != "chiuso"
    within_6m = (ct2["DataFine"].notna() &
                 (ct2["DataFine"] >= today) &
                 (ct2["DataFine"] <= today + pd.DateOffset(months=6)))
    scad = ct2[open_mask & within_6m].copy()

    if not scad.empty:
        scad = scad.sort_values(["ClienteID", "DataFine"])
        scad = scad.groupby("ClienteID", as_index=False).first()

    if not scad.empty:
        disp = pd.DataFrame({
            "NumeroContratto":   scad.get("NumeroContratto","").fillna(""),
            "DataFine":          scad["DataFine"].apply(fmt_date),
            "DescrizioneProdotto": scad.get("DescrizioneProdotto","").fillna(""),
            "TotRata": scad.get("TotRata", pd.Series(index=scad.index)).apply(
                lambda x: "" if pd.isna(pd.to_numeric(x, errors="coerce")) else f"{float(pd.to_numeric(x, errors='coerce')):.2f}"
            ),
        })
    else:
        disp = pd.DataFrame(columns=["NumeroContratto","DataFine","DescrizioneProdotto","TotRata"])

    show_html(html_table_simple(disp), height=240)

    # Ultimi recall / visite
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecall"]   = cli.get("UltimoRecall", pd.Series()).apply(to_date)
        cli["ProssimoRecall"] = cli.get("ProssimoRecall", pd.Series()).apply(to_date)
        soglia = today - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall"].notna() & (cli["UltimoRecall"] <= soglia)]
        tab = r.loc[:, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]].copy()
        tab["UltimoRecall"]   = tab["UltimoRecall"].apply(fmt_date)
        tab["ProssimoRecall"] = tab["ProssimoRecall"].apply(fmt_date)
        show_html(html_table_simple(tab), height=260)

    with c2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisita"]    = cli.get("UltimaVisita", pd.Series()).apply(to_date)
        cli["ProssimaVisita"]  = cli.get("ProssimaVisita", pd.Series()).apply(to_date)
        soglia_v = today - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita"].notna() & (cli["UltimaVisita"] <= soglia_v)]
        tab = v.loc[:, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]].copy()
        tab["UltimaVisita"]   = tab["UltimaVisita"].apply(fmt_date)
        tab["ProssimaVisita"] = tab["ProssimaVisita"].apply(fmt_date)
        show_html(html_table_simple(tab), height=260)

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")
    st.info("Pagina 'Clienti' minimale (la completiamo dopo).")
    st.dataframe(df_cli, use_container_width=True)

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti")
    st.info("Pagina 'Contratti' minimale (la completiamo dopo).")
    st.dataframe(df_ct, use_container_width=True)

# -------------------- MAIN --------------------
def main():
    user, role = require_login()

    # Carica dati
    df_cli = load_clienti()
    df_ct  = load_contratti()

    # Navigator
    pages = ["Dashboard", "Clienti", "Contratti"]
    default_page = st.session_state.get("nav_target", "Dashboard")
    try:
        default_index = pages.index(default_page)
    except ValueError:
        default_index = 0
    page = st.sidebar.radio("Menu", pages, index=default_index)

    # reset eventuale target
    st.session_state["nav_target"] = page

    if page == "Dashboard":
        page_dashboard(df_cli, df_ct, role)
    elif page == "Clienti":
        page_clienti(df_cli, df_ct, role)
    elif page == "Contratti":
        page_contratti(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
