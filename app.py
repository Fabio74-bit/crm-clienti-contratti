   # app.py — SHT – Gestione Clienti (Dashboard + Contratti + Login)

from __future__ import annotations
import io
from pathlib import Path
from datetime import datetime, date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# =========================
# CONFIG PERCORSI (CSV)
# =========================
BASE = Path("storage")
BASE.mkdir(exist_ok=True, parents=True)

CLIENTI_CSV    = BASE / "clienti.csv"
CONTRATTI_CSV  = BASE / "contratti_clienti.csv"
PREVENTIVI_CSV = BASE / "preventivi.csv"  # non usato qui, ma già pronto

# colonne minime attese
CLIENTI_COLS = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]
CONTRATTI_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]

# =========================
# HELPER DATE/NUMERI
# =========================
def to_date(x):
    if x is None or (isinstance(x,float) and pd.isna(x)) or str(x).strip()=="":
        return pd.NaT
    if isinstance(x, pd.Timestamp): return x
    try:
        return pd.to_datetime(str(x).strip(), errors="coerce", dayfirst=True)
    except Exception:
        return pd.NaT

def to_date_series(s: pd.Series) -> pd.Series:
    return s.apply(to_date) if s is not None else s

def fmt_date(x):
    if x is None or pd.isna(x): return ""
    try:
        return pd.to_datetime(x).strftime("%d/%m/%Y")
    except Exception:
        return ""

def to_num(x):
    try:
        v = pd.to_numeric(x, errors="coerce")
        return v
    except Exception:
        return pd.NA

# =========================
# LOAD / SAVE CON TOLLERANZA
# =========================
def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns: df[c] = pd.NA
    # riordino
    return df[[c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]]

def load_clienti() -> pd.DataFrame:
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False)
    df = ensure_columns(df, CLIENTI_COLS)
    return df

def load_contratti() -> pd.DataFrame:
    if CONTRATTI_CSV.exists():
        df = pd.read_csv(CONTRATTI_CSV, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
        df.to_csv(CONTRATTI_CSV, index=False)
    df = ensure_columns(df, CONTRATTI_COLS)
    return df

def save_contratti(df: pd.DataFrame):
    df = ensure_columns(df, CONTRATTI_COLS).copy()
    df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8")

# =========================
# RENDER HTML (iframe)
# =========================
def show_html(html: str, *, height: int = 420):
    components.html(html, height=height, scrolling=True)

# =========================
# KPI CARDS COLORATE
# =========================
KPI_CSS = """
<style>
.kpi-row{display:grid;grid-template-columns:repeat(4, minmax(0,1fr));gap:18px;margin:8px 0 18px 0}
.kpi{border:1px solid #d0d7de;border-radius:14px;padding:16px 18px;background:#fff}
.kpi h5{margin:0 0 8px 0;font-size:15px;color:#5a6772;font-weight:600}
.kpi .v{font-size:28px;font-weight:800;margin:0}
.kpi.green {box-shadow:0 0 0 2px #C8E6C9 inset}
.kpi.red   {box-shadow:0 0 0 2px #FFCDD2 inset}
.kpi.yellow{box-shadow:0 0 0 2px #FFF9C4 inset}
</style>
"""

def kpi_card(title, value, color):
    return f"""
    <div class="kpi {color}">
      <h5>{title}</h5>
      <div class="v">{value}</div>
    </div>
    """

# =========================
# TABELLA CONTRATTI (HTML)
# =========================
CONTRACT_TABLE_CSS = """
<style>
:root{
  --bd:#d0d7de;
  --thbg:#e3f2fd;
  --rowzebra:#f9fbff;
  --closedbg:#fdecea;
  --closedfg:#b71c1c;
}
.ct-table{width:100%;border-collapse:separate;border-spacing:0;table-layout:fixed;font-size:13px;}
.ct-table thead th{position:sticky;top:0;background:var(--thbg);border:1px solid var(--bd);padding:8px 10px;text-align:left;font-weight:600;}
.ct-table tbody td{border:1px solid var(--bd);padding:8px 10px;vertical-align:top;}
.ct-table tbody tr:nth-child(odd):not(.closed){background:var(--rowzebra);}
.ct-table tbody tr.closed td{background:var(--closedbg);color:var(--closedfg);}
.ellipsis{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
</style>
"""

CONTRACT_DISPLAY_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]

def html_contract_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return CONTRACT_TABLE_CSS + "<div style='padding:8px;color:#666'>Nessun contratto</div>"

    show = df.copy()

    # format
    if "DataInizio" in show.columns:
        show["DataInizio"] = show["DataInizio"].apply(fmt_date)
    if "DataFine" in show.columns:
        show["DataFine"] = show["DataFine"].apply(fmt_date)
    for c in ("NOL_FIN","NOL_INT","TotRata"):
        if c in show.columns:
            def _fmt(x):
                try:
                    v = pd.to_numeric(x, errors="coerce")
                    if pd.isna(v): return ""
                    return f"{v:.2f}"
                except Exception:
                    return "" if pd.isna(x) else str(x)
            show[c] = show[c].apply(_fmt)

    cols = [c for c in CONTRACT_DISPLAY_COLS if c in show.columns]
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>"

    rows = []
    for _, r in show.iterrows():
        closed = str(r.get("Stato","")).strip().lower() == "chiuso"
        trclass = " class='closed'" if closed else ""
        tds = []
        for c in cols:
            sval = "" if pd.isna(r.get(c)) else str(r.get(c))
            sval = sval.replace("\n","<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows.append(f"<tr{trclass}>" + "".join(tds) + "</tr>")

    return CONTRACT_TABLE_CSS + "<table class='ct-table'>" + thead + "<tbody>" + "".join(rows) + "</tbody></table>"

# =========================
# TOGGLE CHIUDI/RIAPRI
# =========================
def toggle_contract_state(df_ct: pd.DataFrame, row_index) -> pd.DataFrame:
    current = str(df_ct.loc[row_index, "Stato"]) if "Stato" in df_ct.columns else ""
    new_state = "" if current.strip().lower() == "chiuso" else "chiuso"
    df_ct.loc[row_index, "Stato"] = new_state
    save_contratti(df_ct)
    return df_ct

# =========================
# PAGINA: DASHBOARD
# =========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    # KPI
    today = pd.Timestamp.today().normalize()
    year_now = today.year

    stato = df_ct["Stato"].fillna("").str.lower()
    n_aperti = (stato != "chiuso").sum()
    n_chiusi = (stato == "chiuso").sum()
    n_anno   = (to_date_series(df_ct["DataInizio"]).dt.year == year_now).sum()
    n_clienti= df_cli["ClienteID"].astype(str).nunique()

    st.markdown(KPI_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="kpi-row">
          {kpi_card("Clienti attivi", n_clienti, "")}
          {kpi_card("Contratti aperti", n_aperti, "green")}
          {kpi_card("Contratti chiusi", n_chiusi, "red")}
          {kpi_card(f"Contratti {year_now}", n_anno, "yellow")}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Ricerca veloce cliente
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
                st.session_state["selected_client_id"] = fid
                st.session_state["nav_target"] = "Clienti"
                st.rerun()

    st.markdown("---")

    # Contratti in scadenza entro 6 mesi (primo per cliente)
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    ct = df_ct.copy()
    ct["DataFine"] = to_date_series(ct["DataFine"])
    open_mask = ct["Stato"].fillna("").str.lower() != "chiuso"
    within_6m = ct["DataFine"].notna() & (ct["DataFine"] >= today) & (ct["DataFine"] <= today + pd.DateOffset(months=6))
    scad = ct[open_mask & within_6m].copy()
    if not scad.empty:
        scad = scad.sort_values(["ClienteID","DataFine"]).groupby("ClienteID", as_index=False).first()

    disp_scad = pd.DataFrame()
    if not scad.empty:
        labels = df_cli.set_index("ClienteID")["RagioneSociale"]
        disp_scad = pd.DataFrame({
            "Cliente": scad["ClienteID"].map(labels).fillna(scad["ClienteID"].astype(str)),
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "DataFine": scad["DataFine"].apply(fmt_date),
            "TotRata": scad["TotRata"].apply(lambda x: "" if pd.isna(to_num(x)) else f"{float(to_num(x)):.2f}")
        })
    show_html(html_contract_table(disp_scad), height=240)

    # Recall > 3 mesi
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecall"] = to_date_series(cli["UltimoRecall"])
        cli["ProssimoRecall"] = to_date_series(cli["ProssimoRecall"])
        soglia = today - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall"].notna() & (cli["UltimoRecall"] <= soglia)]
        tab = r.loc[:, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]].copy()
        tab["UltimoRecall"]   = tab["UltimoRecall"].apply(fmt_date)
        tab["ProssimoRecall"] = tab["ProssimoRecall"].apply(fmt_date)
        show_html(html_contract_table(tab), height=260)

    # Visite > 6 mesi
    with c2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisita"]   = to_date_series(cli["UltimaVisita"])
        cli["ProssimaVisita"] = to_date_series(cli["ProssimaVisita"])
        soglia_v = today - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita"].notna() & (cli["UltimaVisita"] <= soglia_v)]
        tab = v.loc[:, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]].copy()
        tab["UltimaVisita"]   = tab["UltimaVisita"].apply(fmt_date)
        tab["ProssimaVisita"] = tab["ProssimaVisita"].apply(fmt_date)
        show_html(html_contract_table(tab), height=260)

# =========================
# PAGINA: CLIENTI (minimale)
# =========================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    labels = (df_cli["ClienteID"].astype(str) + " — " + df_cli["RagioneSociale"].astype(str)).tolist()
    ids = df_cli["ClienteID"].astype(str).tolist()

    default_idx = 0
    if "selected_client_id" in st.session_state:
        try:
            default_idx = ids.index(str(st.session_state["selected_client_id"]))
        except Exception:
            default_idx = 0

    sel = st.selectbox("Apri scheda", labels, index=default_idx if len(labels)>0 else 0)
    sel_id = ids[labels.index(sel)]

    cli = df_cli[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0].to_dict()

    c1, c2, c3 = st.columns(3)
    c1.write(f"**Ragione Sociale**: {cli.get('RagioneSociale','')}")
    c1.write(f"**Persona rif.**: {cli.get('PersonaRiferimento','')}")
    c1.write(f"**Email**: {cli.get('Email','')}")
    c2.write(f"**Indirizzo**: {cli.get('Indirizzo','')}")
    c2.write(f"**Città**: {cli.get('Citta','')}, {cli.get('CAP','')}")
    c2.write(f"**Telefono**: {cli.get('Telefono','')}")
    c3.write(f"**P.IVA**: {cli.get('PartitaIVA','')}")
    c3.write(f"**IBAN**: {cli.get('IBAN','')}")
    c3.write(f"**SDI**: {cli.get('SDI','')}")

    st.markdown("---")
    if st.button("➡️ Vai ai contratti di questo cliente"):
        st.session_state["selected_client_id"] = sel_id
        st.session_state["nav_target"] = "Contratti"
        st.rerun()

# =========================
# PAGINA: CONTRATTI
# =========================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti (rosso = chiusi)")

    labels = (df_cli["ClienteID"].astype(str) + " — " + df_cli["RagioneSociale"].astype(str)).tolist()
    ids = df_cli["ClienteID"].astype(str).tolist()
    default_idx = 0
    if "selected_client_id" in st.session_state:
        try:
            default_idx = ids.index(str(st.session_state["selected_client_id"]))
        except Exception:
            default_idx = 0
    sel_label = st.selectbox("Cliente", labels, index=default_idx if len(labels)>0 else 0)
    if not labels:
        st.info("Nessun cliente presente.")
        return
    sel_id = ids[labels.index(sel_label)]

    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()

    st.markdown("### Selezione/chiusura righe")
    selected_rows = []

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        for ridx, row in ct.iterrows():
            col_ck, col_info = st.columns([0.06, 0.94])
            checked = col_ck.checkbox("", key=f"sel_{ridx}")
            if checked:
                selected_rows.append(ridx)

            inizio = fmt_date(row.get("DataInizio"))
            fine   = fmt_date(row.get("DataFine"))
            testo = f"— {row.get('DescrizioneProdotto','')}\n*dal {inizio or '*'} al {fine or '*'}*"
            col_info.markdown(testo)

            stato = str(row.get("Stato","")).strip().lower()
            action = "Riapri" if stato == "chiuso" else "Chiudi"
            if col_info.button(action, key=f"toggle_{ridx}"):
                toggle_contract_state(df_ct, ridx)
                st.success(f"Contratto {'riaperto' if action=='Riapri' else 'chiuso'}.")
                st.rerun()

    st.markdown("---")
    st.markdown("### Tabella completa")
    st.markdown(html_contract_table(ct), unsafe_allow_html=True)

    st.markdown("### Esporta / Stampa selezione")
    c1, _ = st.columns([0.25, 0.75])
    with c1:
        if st.button("Esporta selezione in Excel"):
            if not selected_rows:
                st.warning("Seleziona almeno una riga sopra.")
            else:
                outcols = [c for c in CONTRACT_DISPLAY_COLS if c in ct.columns]
                df_out = ct.loc[selected_rows, outcols].copy()

                nome = df_cli.loc[df_cli["ClienteID"].astype(str)==str(sel_id), "RagioneSociale"].iloc[0]
                df_header = pd.DataFrame({"Cliente":[f"{sel_id} — {nome}"]})

                bio = io.BytesIO()
                with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
                    df_header.to_excel(writer, sheet_name="Selezione", index=False, startrow=0)
                    df_out.to_excel(writer, sheet_name="Selezione", index=False, startrow=2)

                    wb  = writer.book
                    ws  = writer.sheets["Selezione"]
                    fmt_header = wb.add_format({"bold":True, "bg_color":"#E3F2FD", "border":1})
                    fmt_cell   = wb.add_format({"border":1})

                    for j, colname in enumerate(df_out.columns):
                        ws.write(2, j, colname, fmt_header)
                    for irow in range(len(df_out)):
                        for j in range(len(df_out.columns)):
                            ws.write(3+irow, j, df_out.iloc[irow, j], fmt_cell)

                st.download_button(
                    "Scarica Excel",
                    data=bio.getvalue(),
                    file_name=f"Contratti_{sel_id}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

# =========================
# LOGIN SEMPLICE
# =========================
def require_login():
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"], st.session_state.get("role","admin")

    st.title("SHT – Gestione Clienti")
    st.caption("Accesso richiesto")

    default_users = {
        "fabio": {"password": "admin", "role": "admin"},
    }
    users = default_users
    if "auth" in st.secrets:
        try:
            users = {k: dict(v) for k, v in st.secrets["auth"].items()}
        except Exception:
            pass

    with st.form("login"):
        u = st.text_input("Utente", value="fabio")
        p = st.text_input("Password", value="admin", type="password")
        ok = st.form_submit_button("Entra")
    if ok:
        rec = users.get(u)
        if rec and str(rec.get("password")) == p:
            st.session_state["user"] = u
            st.session_state["role"] = rec.get("role","admin")
            st.success("Benvenuto, " + u)
            st.rerun()
        else:
            st.error("Credenziali non valide.")
            st.stop()

    st.stop()

# =========================
# NAVIGAZIONE
# =========================
PAGES = {
    "Dashboard": page_dashboard,
    "Clienti": page_clienti,
    "Contratti": page_contratti,
}

def main():
    user, role = require_login()

    # carica dati
    df_cli = load_clienti()
    df_ct  = load_contratti()

    st.sidebar.title("SHT – Gestione Clienti")
    page = st.sidebar.radio("Vai a…", list(PAGES.keys()), key="sidebar_page")

    if "nav_target" in st.session_state:
        page = st.session_state.pop("nav_target")

    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
