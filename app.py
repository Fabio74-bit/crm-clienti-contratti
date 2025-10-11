# SHT – Gestione Clienti (Streamlit 1.50 compatibile)
from __future__ import annotations
import re
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List, Tuple
import io

import pandas as pd
import streamlit as st
from docx import Document
import xlsxwriter  # requirements already include it

# -----------------------------------------------------------------------------
# Config & Paths
# -----------------------------------------------------------------------------
APP_TITLE = "SHT – Gestione Clienti"
BASE = Path("storage")
BASE.mkdir(parents=True, exist_ok=True)
TPL_DIR = BASE / "templates"
PREV_DIR = BASE / "preventivi"
PREV_DIR.mkdir(parents=True, exist_ok=True)

CSV_CLIENTI = BASE / "clienti.csv"
CSV_CONTRATTI = BASE / "contratti_clienti.csv"
CSV_PREVENTIVI = BASE / "preventivi.csv"
COUNTER_FILE = BASE / "preventivi_counter.txt"

DATE_FMT = "%d/%m/%Y"

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def _df_empty(path: Path, cols: List[str]) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path, dtype=str).fillna("")
    else:
        df = pd.DataFrame(columns=cols)
    return df

def load_clienti() -> pd.DataFrame:
    cols = [
        "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","CAP","Citta",
        "Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall",
        "UltimaVisita","ProssimaVisita","Note"
    ]
    return _df_empty(CSV_CLIENTI, cols)

def save_clienti(df: pd.DataFrame):
    df.fillna("").to_csv(CSV_CLIENTI, index=False)

def load_contratti() -> pd.DataFrame:
    cols = [
        "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
        "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
    ]
    return _df_empty(CSV_CONTRATTI, cols)

def save_contratti(df: pd.DataFrame):
    df.fillna("").to_csv(CSV_CONTRATTI, index=False)

def load_preventivi() -> pd.DataFrame:
    cols = ["Numero","ClienteID","Data","Template","FilePath"]
    return _df_empty(CSV_PREVENTIVI, cols)

def save_preventivi(df: pd.DataFrame):
    df.fillna("").to_csv(CSV_PREVENTIVI, index=False)

def fmt_date(s: str) -> str:
    """Ritorna dd/mm/aaaa se possibile, altrimenti stringa originale."""
    s = (s or "").strip()
    if not s: return ""
    for f in ("%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%Y/%m/%d"):
        try:
            return datetime.strptime(s, f).strftime(DATE_FMT)
        except Exception:
            continue
    return s

def today_str() -> str:
    return date.today().strftime(DATE_FMT)

def inc_quote_counter() -> str:
    """Restituisce il prossimo numero preventivo formattato SHT-MI-0001."""
    n = 0
    if COUNTER_FILE.exists():
        try:
            n = int(COUNTER_FILE.read_text().strip())
        except Exception:
            n = 0
    n += 1
    COUNTER_FILE.write_text(str(n))
    return f"SHT-MI-{n:04d}"

def ensure_dates(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = df[c].map(fmt_date)
    return df

def status_class(s: str) -> str:
    s = (s or "").strip().lower()
    if s == "chiuso":
        return "closed"
    return ""

# -----------------------------------------------------------------------------
# CSS (colori, tabelle, wrap testo, metriche)
# -----------------------------------------------------------------------------
CSS = """
<style>
/* allarga lo schermo */
section.main > div {max-width: 1400px; padding-top: 10px}

/* cards metriche */
.sht-cards {display:flex; gap:18px; flex-wrap:wrap; margin-bottom:10px}
.sht-card {
  border-radius:14px; padding:18px 22px; min-width:180px;
  background:#e9f2ff; border:1px solid #d8e7ff;
}
.sht-card h4{margin:0; font-weight:600; color:#4a5568; font-size:18px}
.sht-card .v{margin-top:6px; font-size:28px; font-weight:700; color:#0f172a}

/* colori specifici */
.sht-green {background:#e8f7ee; border-color:#c9efd8}
.sht-green .v {color:#166534}
.sht-red   {background:#ffeaea; border-color:#ffd4d4}
.sht-red .v {color:#991b1b}
.sht-yellow{background:#fff7d1; border-color:#ffec9a}
.sht-yellow .v {color:#854d0e}
.sht-blue  {background:#e6f0ff; border-color:#cddfff}
.sht-blue .v {color:#1e3a8a}

/* tabella contratti */
.table-wrap{overflow-x:auto}
.ctr-table{width:100%; border-collapse:collapse; table-layout:fixed}
.ctr-table thead th{
  background:#f1f5f9; color:#0f172a; border-bottom:2px solid #e2e8f0;
  padding:8px; text-align:left; font-weight:700;
}
.ctr-table tbody td{
  border-bottom:1px solid #eef2f7; padding:8px;
  word-wrap:break-word; white-space:normal; vertical-align:top;
}
.ctr-table tbody tr.closed td{ background:#ffecec !important; }

/* pulsante mini */
.btn-mini{padding:4px 8px; font-size:12px; border-radius:8px; background:#f8fafc; border:1px solid #e5e7eb}
.btn-mini:hover{background:#eef2f7}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Contracts HTML
# -----------------------------------------------------------------------------
SAFE_CONTRACT_COLS = ["NumeroContratto","DataInizio","DataFine",
                      "Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]

def contracts_html(df: pd.DataFrame) -> str:
    """Ritorna HTML tabella contratti con righe rosse per chiusi."""
    cols = SAFE_CONTRACT_COLS
    head = "".join(f"<th>{c}</th>" for c in cols)
    rows = []
    for _, r in df[cols].iterrows():
        cls = status_class(r.get("Stato",""))
        tds = "".join(f"<td>{(str(r.get(c,'')) or '').replace('\n','<br>')}</td>" for c in cols)
        rows.append(f"<tr class='{cls}'>{tds}</tr>")
    body = "".join(rows) or "<tr><td colspan='9'>Nessun contratto</td></tr>"
    return f"<div class='table-wrap'><table class='ctr-table'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"

# -----------------------------------------------------------------------------
# Preventivi
# -----------------------------------------------------------------------------
def docx_replace(doc: Document, mapping: Dict[str,str]):
    for p in doc.paragraphs:
        for k,v in mapping.items():
            if k in p.text:
                inline = p.runs
                # ricostruzione testuale
                text = "".join(run.text for run in inline)
                text = text.replace(k, v)
                # riscrivi nei run (semplice)
                if inline:
                    inline[0].text = text
                    for run in inline[1:]:
                        run.text = ""
    # anche nelle tabelle
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for k,v in mapping.items():
                    if k in cell.text:
                        cell.text = cell.text.replace(k, v)

def crea_preventivo(df_cli_row: pd.Series, template_name: str) -> Tuple[str, Path]:
    """Crea docx e registra in CSV preventivi. Ritorna (numero, path)."""
    tpl_path = TPL_DIR / template_name
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template non trovato: {tpl_path.name}")
    numero = inc_quote_counter()  # SHT-MI-0001
    # mapping placeholder -> valori
    m = {
        "{{NumeroPreventivo}}": numero,
        "{{Data}}": today_str(),
        "{{ClienteID}}": str(df_cli_row["ClienteID"]),
        "{{RagioneSociale}}": str(df_cli_row["RagioneSociale"]),
        "{{PersonaRiferimento}}": str(df_cli_row["PersonaRiferimento"]),
        "{{Indirizzo}}": str(df_cli_row["Indirizzo"]),
        "{{CAP}}": str(df_cli_row["CAP"]),
        "{{Citta}}": str(df_cli_row["Citta"]),
        "{{PartitaIVA}}": str(df_cli_row["PartitaIVA"]),
        "{{IBAN}}": str(df_cli_row["IBAN"]),
        "{{SDI}}": str(df_cli_row["SDI"]),
        # altri placeholder possono essere aggiunti nei template
    }
    doc = Document(str(tpl_path))
    docx_replace(doc, m)
    out = PREV_DIR / f"{numero}_{df_cli_row['ClienteID']}.docx"
    doc.save(str(out))

    df_prev = load_preventivi()
    df_prev = pd.concat([
        df_prev,
        pd.DataFrame([{
            "Numero": numero,
            "ClienteID": str(df_cli_row["ClienteID"]),
            "Data": today_str(),
            "Template": template_name,
            "FilePath": str(out)
        }])
    ], ignore_index=True)
    save_preventivi(df_prev)
    return numero, out

# -----------------------------------------------------------------------------
# AUTH (semplice): usa st.secrets se presenti; altrimenti login “fabio/admin”
# -----------------------------------------------------------------------------
def login_box() -> Tuple[str,str]:
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"], st.session_state.get("role","admin")

    st.write("### Login")
    u = st.text_input("Utente", value="", key="login_u")
    p = st.text_input("Password", value="", type="password", key="login_p")
    if st.button("Entra", use_container_width=False):
        users = {}
        try:
            users = dict(st.secrets["auth"]["users"])
        except Exception:
            users = {"fabio":{"password":"admin","role":"admin"}}
        if u in users and p == users[u]["password"]:
            st.session_state["user"] = u
            st.session_state["role"] = users[u].get("role","viewer")
            st.rerun()
        else:
            st.error("Credenziali non valide")
    st.stop()

def require_login() -> Tuple[str,str]:
    try:
        return st.session_state["user"], st.session_state.get("role","viewer")
    except Exception:
        return login_box()

# -----------------------------------------------------------------------------
# Pagine
# -----------------------------------------------------------------------------
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # metriche
    df_ct = ensure_dates(df_ct.copy(), ["DataInizio","DataFine"])
    aperti = (df_ct["Stato"].str.lower() != "chiuso").sum()
    chiusi = (df_ct["Stato"].str.lower() == "chiuso").sum()
    this_year = str(date.today().year)
    contratti_anno = (df_ct["DataInizio"].str.endswith(this_year)).sum()
    n_cli = len(df_cli)

    col1, col2, col3, col4 = st.columns([1,1,1,1])
    with col1:
        st.markdown(f"""
        <div class="sht-card sht-blue"><h4>Clienti attivi</h4><div class="v">{n_cli}</div></div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="sht-card sht-green"><h4>Contratti aperti</h4><div class="v">{aperti}</div></div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="sht-card sht-red"><h4>Contratti chiusi</h4><div class="v">{chiusi}</div></div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="sht-card sht-yellow"><h4>Contratti {this_year}</h4><div class="v">{contratti_anno}</div></div>
        """, unsafe_allow_html=True)

    st.markdown("### Cerca cliente")
    q = st.text_input("Digita nome o ID cliente…", label_visibility="collapsed")
    if q:
        m = df_cli[
            df_cli["RagioneSociale"].str.contains(q, case=False, na=False) |
            df_cli["ClienteID"].astype(str).str.contains(q, na=False)
        ][["ClienteID","RagioneSociale"]].head(20)
        if len(m):
            sel = st.selectbox("Risultati", [f"{r.ClienteID} — {r.RagioneSociale}" for _,r in m.iterrows()])
            if st.button("Apri scheda cliente"):
                st.session_state["nav"] = "Clienti"
                st.session_state["open_cliente"] = int(sel.split(" — ")[0])
                st.rerun()

    # contratti in scadenza entro 6 mesi (solo aperti)
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    due = []
    today = date.today()
    for _, r in df_ct.iterrows():
        if str(r.get("Stato","")).lower() == "chiuso":
            continue
        d = fmt_date(r.get("DataFine",""))
        try:
            dt = datetime.strptime(d, DATE_FMT).date()
            months = (dt.year - today.year) * 12 + (dt.month - today.month)
            if 0 <= months <= 6:
                due.append(r)
        except Exception:
            pass
    df_due = pd.DataFrame(due)
    if len(df_due):
        df_due = df_due.merge(df_cli[["ClienteID","RagioneSociale"]], on="ClienteID", how="left")
        df_due = df_due[["RagioneSociale","NumeroContratto","DescrizioneProdotto","DataFine","TotRata"]]
        df_due = ensure_dates(df_due, ["DataFine"])
        st.dataframe(df_due, use_container_width=True, hide_index=True)
    else:
        st.info("Nessun contratto in scadenza entro 6 mesi.")

    # richiami e visite
    colA, colB = st.columns(2)
    with colA:
        st.markdown("### Ultimi recall (> 3 mesi)")
        def older_3m(s): 
            s = fmt_date(s)
            try:
                d = datetime.strptime(s, DATE_FMT).date()
                months = (today.year - d.year)*12 + (today.month - d.month)
                return months >= 3
            except Exception:
                return False
        dfr = df_cli[df_cli["UltimoRecall"].map(older_3m)][["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]]
        st.dataframe(dfr, use_container_width=True, hide_index=True)
    with colB:
        st.markdown("### Ultime visite (> 6 mesi)")
        def older_6m(s):
            s = fmt_date(s)
            try:
                d = datetime.strptime(s, DATE_FMT).date()
                months = (today.year - d.year)*12 + (today.month - d.month)
                return months >= 6
            except Exception:
                return False
        dfv = df_cli[df_cli["UltimaVisita"].map(older_6m)][["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]]
        st.dataframe(dfv, use_container_width=True, hide_index=True)

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    opts = [f"{r.ClienteID} — {r.RagioneSociale}" for _,r in df_cli.iterrows()]
    default_idx = 0
    if "open_cliente" in st.session_state:
        cid = str(st.session_state["open_cliente"])
        for i, s in enumerate(opts):
            if s.startswith(cid + " — "): default_idx = i; break

    sel = st.selectbox("Cliente", opts, index=default_idx if len(opts)>0 else 0)
    if not sel: 
        st.info("Nessun cliente.")
        return
    cid = int(sel.split(" — ")[0])
    cli = df_cli[df_cli["ClienteID"].astype(str) == str(cid)].iloc[0]

    col1, col2 = st.columns([3,1])
    with col1:
        st.subheader(cli["RagioneSociale"])
        info = pd.DataFrame([{
            "PersonaRiferimento": cli["PersonaRiferimento"],
            "Indirizzo": cli["Indirizzo"],
            "Città": f'{cli["CAP"]} {cli["Citta"]}',
            "Telefono": cli["Telefono"],
            "Email": cli["Email"],
            "P.IVA": cli["PartitaIVA"], "IBAN": cli["IBAN"], "SDI": cli["SDI"],
            "Ultimo Recall": fmt_date(cli["UltimoRecall"]),
            "Prossimo Recall": fmt_date(cli["ProssimoRecall"]),
            "Ultima Visita": fmt_date(cli["UltimaVisita"]),
            "Prossima Visita": fmt_date(cli["ProssimaVisita"]),
            "Note": cli["Note"]
        }]).T
        info.columns = ["Valore"]
        st.dataframe(info, use_container_width=True, height=370)

    with col2:
        if st.button("Vai ai contratti di questo cliente", use_container_width=True):
            st.session_state["nav"] = "Contratti"
            st.session_state["open_cliente"] = cid
            st.rerun()

    # Modifiche rapide anagrafica
    with st.expander("Modifica anagrafica"):
        pr = st.text_input("Persona di riferimento", value=cli["PersonaRiferimento"])
        note = st.text_area("Note", value=cli["Note"])
        if st.button("Salva anagrafica"):
            df_cli.loc[df_cli["ClienteID"].astype(str)==str(cid),"PersonaRiferimento"] = pr
            df_cli.loc[df_cli["ClienteID"].astype(str)==str(cid),"Note"] = note
            save_clienti(df_cli)
            st.success("Anagrafica aggiornata.")
            st.rerun()

    # Preventivi
    st.markdown("---")
    st.subheader("Preventivi")
    tpls = [p.name for p in sorted(TPL_DIR.glob("*.docx"))]
    tpl_sel = st.selectbox("Template", tpls) if tpls else None
    if tpl_sel and st.button("Genera preventivo"):
        numero, path = crea_preventivo(cli, tpl_sel)
        st.success(f"Preventivo **{numero}** creato.")
        st.download_button("Scarica preventivo", data=Path(path).read_bytes(),
                           file_name=Path(path).name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    df_prev = load_preventivi()
    prev_cli = df_prev[df_prev["ClienteID"] == str(cid)].sort_values("Data", ascending=False)
    st.dataframe(prev_cli, use_container_width=True, hide_index=True)

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # selezione cliente
    opts = [f"{r.ClienteID} — {r.RagioneSociale}" for _,r in df_cli.iterrows()]
    default_idx = 0
    if "open_cliente" in st.session_state:
        cid = str(st.session_state["open_cliente"])
        for i, s in enumerate(opts):
            if s.startswith(cid + " — "): default_idx = i; break
    sel = st.selectbox("Cliente", opts, index=default_idx if len(opts)>0 else 0)
    if not sel: 
        st.info("Nessun cliente.")
        return
    cid = int(sel.split(" — ")[0])

    # chiudi riga singola
    st.markdown("### Selezione/chiusura righe")
    ct_cli = df_ct[df_ct["ClienteID"].astype(str)==str(cid)].copy()
    ct_cli = ensure_dates(ct_cli, ["DataInizio","DataFine"])
    ct_cli = ct_cli.reset_index(drop=True)

    # elenco righe con pulsante chiudi
    for i, r in ct_cli.iterrows():
        colA, colB, colC = st.columns([0.1, 0.65, 0.25])
        with colA:
            st.write("")
        with colB:
            lab = r["DescrizioneProdotto"] or "(senza descrizione)"
            period = f"dal {r['DataInizio'] or '-'} al {r['DataFine'] or '-'} · {r['Durata'] or ''}"
            st.markdown(f"— **{lab}**  \n*{period}*")
        with colC:
            if st.button("Chiudi", key=f"chiudi_{i}"):
                df_ct.loc[(df_ct["ClienteID"].astype(str)==str(cid)) & (df_ct.index==ct_cli.index[i]), "Stato"] = "chiuso"
                save_contratti(df_ct)
                st.success("Contratto chiuso.")
                st.rerun()

    st.markdown("---")
    st.markdown("### Tabella completa")
    # tabella HTML ben formattata
    html = contracts_html(ct_cli)
    st.markdown(html, unsafe_allow_html=True)

    st.markdown("### Esporta / Stampa selezione")
    # selezione per esportazione
    scelte = [f"{i+1} — {r.DescrizioneProdotto[:60]}" for i,r in ct_cli.iterrows()]
    pick = st.multiselect("Seleziona righe (vuoto=tutte)", scelte)
    if st.button("Esporta selezione in Excel"):
        if pick:
            idxs = [int(s.split(" — ")[0])-1 for s in pick]
            out = ct_cli.iloc[idxs].copy()
        else:
            out = ct_cli.copy()
        # intestazione cliente in prima riga
        cli = df_cli[df_cli["ClienteID"].astype(str)==str(cid)].iloc[0]
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            out[SAFE_CONTRACT_COLS].to_excel(writer, index=False, sheet_name="Contratti")
            wb = writer.book; ws = writer.sheets["Contratti"]
            title = f"{cli['RagioneSociale']} (ID {cli['ClienteID']})"
            ws.merge_range(0,0,0,len(SAFE_CONTRACT_COLS)-1, title,
                           wb.add_format({"bold":True, "align":"center", "valign":"vcenter"}))
        st.download_button("Scarica Excel", data=buffer.getvalue(),
                           file_name=f"contratti_{cli['ClienteID']}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.info("Per il PDF puoi stampare dal browser oppure dal file Excel.")

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="📄", layout="wide")
    st.title("Dashboard")

    # login
    user, role = require_login()

    # carica CSV (crea se mancanti)
    df_cli = load_clienti()
    df_ct  = load_contratti()

    # normalizza date in memoria
    df_cli = ensure_dates(df_cli, ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"])
    df_ct  = ensure_dates(df_ct,  ["DataInizio","DataFine"])

    # nav
    PAGES = ["Dashboard","Clienti","Contratti"]
    if "nav" not in st.session_state: st.session_state["nav"] = "Dashboard"
    with st.sidebar:
        st.header("SHT – Gestione Clienti")
        st.session_state["nav"] = st.radio("Vai a…", PAGES, index=PAGES.index(st.session_state["nav"]))
        st.caption(f"Loggato come **{user}** ({role})")

    page = st.session_state["nav"]
    if page == "Dashboard":
        page_dashboard(df_cli, df_ct, role)
    elif page == "Clienti":
        page_clienti(df_cli, df_ct, role)
    else:
        page_contratti(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
