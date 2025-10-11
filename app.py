# SHT – Gestione Clienti (Streamlit 1.50) — layout wide, tabella contratti migliorata, cerca cliente
from __future__ import annotations

import io
import re
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Tuple, List

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components  # per HTML embeddato
from docx import Document

# -----------------------------------------------------------------------------
# Config & storage
# -----------------------------------------------------------------------------
APP_TITLE = "SHT – Gestione Clienti"
st.set_page_config(page_title=APP_TITLE, layout="wide")

ROOT = Path(__file__).parent
STORAGE = ROOT / "storage"
TEMPLATES = STORAGE / "templates"
PREV_DIR = STORAGE / "preventivi"
PREV_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV = STORAGE / "clienti.csv"
CONTRATTI_CSV = STORAGE / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE / "preventivi.csv"

DATE_FMT = "%d/%m/%Y"

CLIENTI_COLS = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall",
    "UltimaVisita","ProssimaVisita","Note"
]
CONTRATTI_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
    "NOL_FIN","NOL_INT","TotRata","Stato"
]

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def _coerce_date(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(s, errors="coerce", dayfirst=True, format="mixed")

def _fmt_date(d) -> str:
    if pd.isna(d):
        return ""
    if isinstance(d, str):  # già formattata
        return d
    return d.strftime(DATE_FMT)

def load_csv(path: Path, cols: List[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype=str).fillna("")
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    # date
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","DataInizio","DataFine"]:
        if c in df.columns:
            df[c] = _coerce_date(df[c])
    if "ClienteID" in df.columns:
        df["ClienteID"] = df["ClienteID"].astype(str)
    return df[cols]

def save_csv(df: pd.DataFrame, path: Path):
    df = df.copy()
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","DataInizio","DataFine"]:
        if c in df.columns:
            df[c] = df[c].map(lambda x: _fmt_date(x) if isinstance(x, pd.Timestamp) else (x or ""))
    df.to_csv(path, index=False)

def month_add(d: pd.Timestamp, months: int) -> pd.Timestamp:
    if pd.isna(d) or not str(months).isdigit():
        return pd.NaT
    months = int(months)
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    mdays = [31,29 if y%4==0 and (y%100!=0 or y%400==0) else 28,31,30,31,30,31,31,30,31,30,31][m-1]
    day = min(d.day, mdays)
    return pd.Timestamp(year=y, month=m, day=day)

def euro(x) -> str:
    try:
        v = float(str(x).replace(",", "."))
        return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return ""

def status_chip(s: str) -> str:
    s = (s or "").strip().lower()
    if s == "chiuso":
        return "<span class='chip chip-red'>chiuso</span>"
    if s == "aperto" or s == "":
        return "<span class='chip chip-green'>aperto</span>"
    return f"<span class='chip chip-gray'>{s}</span>"

def require_login() -> Tuple[str, str]:
    if "user" in st.session_state and "role" in st.session_state:
        return st.session_state["user"], st.session_state["role"]

    st.markdown(f"<h2 style='margin-bottom:0'>{APP_TITLE}</h2>", unsafe_allow_html=True)
    st.caption("Login")

    with st.form("login"):
        u = st.text_input("Utente", value="", autocomplete="username")
        p = st.text_input("Password", value="", type="password", autocomplete="current-password")
        ok = st.form_submit_button("Entra", use_container_width=True)
    if ok:
        users = dict(getattr(st.secrets, "auth", {}).get("users", {}))
        if u in users and p == users[u].get("password", ""):
            st.session_state["user"] = u
            st.session_state["role"] = users[u].get("role", "viewer")
            st.success(f"Benvenuto, {u}!")
            st.rerun()
        else:
            st.error("Credenziali non valide.")
    st.stop()

def pill(title: str, value: str):
    st.markdown(
        f"""
        <div class='kpi'>
          <div class='kpi-title'>{title}</div>
          <div class='kpi-value'>{value}</div>
        </div>
        """, unsafe_allow_html=True
    )

def safe_selectbox(label: str, options: List[str], default_label: str=""):
    idx = 0
    if default_label and default_label in options:
        idx = options.index(default_label)
    if not options:
        options = [""]
        idx = 0
    return st.selectbox(label, options, index=idx)

def go_to(page_name: str, cid: str | None = None):
    st.session_state["forced_page"] = page_name
    if cid:
        st.session_state["focus_cid"] = str(cid)
    st.rerun()

# -----------------------------------------------------------------------------
# CSS
# -----------------------------------------------------------------------------
CSS = """
<style>
:root { --brand:#1e88e5; }
.block-container { padding-top: 1.0rem; }
h1,h2,h3 { color:#0d1117; }
.kpi{display:inline-block;margin:6px 8px;padding:10px 14px;border:1px solid #e0e3e7;border-radius:10px;background:#fff}
.kpi-title{font-size:.85rem;color:#6b7280}
.kpi-value{font-size:1.4rem;font-weight:700}

.ctr-wrap{border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;}
.ctr-table{width:100%;border-collapse:separate;border-spacing:0;}
.ctr-table thead th{position:sticky;top:0;background:#f8fafc;border-bottom:1px solid #e5e7eb;z-index:2}
.ctr-table th,.ctr-table td{border-bottom:1px solid #f1f5f9;padding:10px 8px;font-size:.93rem;vertical-align:top;text-align:left}
.ctr-table tbody tr:nth-child(even){background:#fcfdff}
.ctr-table td{white-space:normal;word-break:break-word}
.tr-closed{background:#ffecec !important;}
.chip{padding:2px 8px;border-radius:999px;color:#fff;font-size:.78rem}
.chip-green{background:#10b981}.chip-red{background:#ef4444}.chip-gray{background:#6b7280}
.btn-go{font-size:.85rem;background:#e3f2fd;border:1px solid #bbdefb;padding:3px 8px;border-radius:8px}
.small{font-size:.85rem;color:#6b7280}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Load data
# -----------------------------------------------------------------------------
df_cli = load_csv(CLIENTI_CSV, CLIENTI_COLS)
df_ct  = load_csv(CONTRATTI_CSV, CONTRATTI_COLS)

# se DataFine mancante prova a calcolarla da DataInizio+Durata
m = (df_ct["DataFine"].isna() | (df_ct["DataFine"]=="")) & df_ct["DataInizio"].notna() & df_ct["Durata"].astype(str).str.isdigit()
for i in df_ct.index[m]:
    df_ct.at[i,"DataFine"] = month_add(df_ct.at[i,"DataInizio"], int(df_ct.at[i,"Durata"]))

# -----------------------------------------------------------------------------
# Preventivi
# -----------------------------------------------------------------------------
def replace_docx_placeholders(doc: Document, mapping: Dict[str, str]):
    def _repl(t: str) -> str:
        for k,v in mapping.items():
            t = t.replace(k, v)
        return t
    for p in doc.paragraphs:
        for r in p.runs:
            r.text = _repl(r.text)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.text = _repl(r.text)

def genera_preventivo(cliente_row: pd.Series, tpl_name: str) -> Path:
    doc = Document(TEMPLATES / tpl_name)
    m = {
        "<<CLIENTE>>": cliente_row.get("RagioneSociale",""),
        "<<INDIRIZZO>>": cliente_row.get("Indirizzo",""),
        "<<CITTA>>": cliente_row.get("Citta",""),
        "<<NUMERO_OFFERTA>>": f"{date.today().strftime('%y.%m')}-{cliente_row['ClienteID']}",
        "<<DATA>>": date.today().strftime(DATE_FMT),
    }
    replace_docx_placeholders(doc, m)
    out = PREV_DIR / f"Preventivo_{cliente_row['ClienteID']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(out)
    return out

# -----------------------------------------------------------------------------
# HTML table
# -----------------------------------------------------------------------------
def contracts_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<div class='small'>Nessun contratto</div>"
    df = df.copy()
    df["_st"] = df["Stato"].map(lambda s: status_chip(s))
    for c in ["NOL_FIN","NOL_INT","TotRata"]:
        df[c] = df[c].map(euro)
    for c in ["DataInizio","DataFine"]:
        df[c] = df[c].map(_fmt_date)

    cols = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
            "NOL_FIN","NOL_INT","TotRata","Stato"]
    head = "".join(f"<th>{'Stato' if c=='Stato' else c}</th>" for c in cols)
    body = ""
    for _, r in df[cols].iterrows():
        closed = " tr-closed" if str(r["Stato"]).strip().lower()=="chiuso" else ""
        tds = "".join(f"<td>{r[c] if c!='Stato' else status_chip(r['Stato'])}</td>" for c in cols)
        body += f"<tr class='{closed}'>{tds}</tr>"
    return f"<div class='ctr-wrap'><table class='ctr-table'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"

# -----------------------------------------------------------------------------
# Excel export
# -----------------------------------------------------------------------------
def export_xlsx(cliente: str, df: pd.DataFrame) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as xw:
        sheet = "Contratti"
        df2 = df.copy()
        for c in ["DataInizio","DataFine"]:
            df2[c] = df2[c].map(_fmt_date)
        df2.to_excel(xw, sheet_name=sheet, index=False, startrow=6)
        wb = xw.book
        ws = xw.sheets[sheet]
        title_fmt = wb.add_format({"bold": True, "font_size": 16, "align":"center"})
        ws.merge_range(0,0,0,max(0,len(df2.columns)-1), f"Contratti – {cliente}", title_fmt)
        hdr_fmt = wb.add_format({"bold": True, "bg_color":"#E3F2FD","border":1})
        for col in range(len(df2.columns)):
            ws.write(6, col, df2.columns[col], hdr_fmt)
            ws.set_column(col, col, 24)
    out.seek(0)
    return out.read()

# -----------------------------------------------------------------------------
# Pagine
# -----------------------------------------------------------------------------
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    # KPI
    y = date.today().year
    k1 = df_cli["ClienteID"].nunique()
    k2 = (df_ct["Stato"].str.lower()!="chiuso").sum()
    k3 = (df_ct["Stato"].str.lower()=="chiuso").sum()
    k4 = (_coerce_date(df_ct["DataInizio"]).dt.year==y).sum()
    c1,c2,c3,c4 = st.columns(4)
    with c1: pill("Clienti attivi", f"{k1}")
    with c2: pill("Contratti aperti", f"{k2}")
    with c3: pill("Contratti chiusi", f"{k3}")
    with c4: pill(f"Contratti {y}", f"{k4}")

    # Cerca cliente → vai alla scheda
    st.markdown("#### Cerca cliente")
    q = st.text_input("Digita il nome o l'ID cliente...")
    if q:
        ql = q.lower().strip()
        res = df_cli[(df_cli["RagioneSociale"].str.lower().str.contains(ql)) | (df_cli["ClienteID"].str.contains(ql))]
        if not res.empty:
            label = (res["ClienteID"]+" — "+res["RagioneSociale"]).tolist()
            pick = st.selectbox("Risultati", label)
            if st.button("Apri scheda cliente", use_container_width=True):
                go_to("Clienti", pick.split(" — ")[0])

    # Scadenze entro 6 mesi
    st.markdown("#### Contratti in scadenza (entro 6 mesi)")
    due = _coerce_date(df_ct["DataFine"])
    six = pd.Timestamp.today() + pd.DateOffset(months=6)
    m = (df_ct["Stato"].str.lower()!="chiuso") & (due.notna()) & (due<=six)
    df_alert = df_ct.loc[m].copy()
    if not df_alert.empty:
        df_alert["Cliente"] = df_alert["ClienteID"].map(dict(df_cli[["ClienteID","RagioneSociale"]].values))
        view = df_alert[["Cliente","NumeroContratto","DescrizioneProdotto","DataFine","TotRata"]].copy()
        view["DataFine"] = view["DataFine"].map(_fmt_date)
        st.dataframe(view, hide_index=True, height=280)
    else:
        st.caption("Nessuna scadenza entro 6 mesi.")

    c1,c2 = st.columns(2)
    with c1:
        st.markdown("#### Ultimi recall (> 3 mesi)")
        mrec = _coerce_date(df_cli["UltimoRecall"])
        old = (pd.Timestamp.today() - mrec) > pd.Timedelta(days=90)
        tab = df_cli.loc[old, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]].copy()
        tab["UltimoRecall"] = tab["UltimoRecall"].map(_fmt_date)
        tab["ProssimoRecall"] = _coerce_date(df_cli["ProssimoRecall"]).map(_fmt_date)
        st.dataframe(tab, hide_index=True, height=240)
    with c2:
        st.markdown("#### Ultime visite (> 6 mesi)")
        mvis = _coerce_date(df_cli["UltimaVisita"])
        old = (pd.Timestamp.today() - mvis) > pd.Timedelta(days=180)
        tab = df_cli.loc[old, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]].copy()
        tab["UltimaVisita"] = tab["UltimaVisita"].map(_fmt_date)
        tab["ProssimaVisita"] = _coerce_date(df_cli["ProssimaVisita"]).map(_fmt_date)
        st.dataframe(tab, hide_index=True, height=240)

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")
    opts = (df_cli["ClienteID"]+" — "+df_cli["RagioneSociale"]).tolist()
    pre = st.session_state.get("focus_cid","")
    default_label = ""
    if pre and pre in df_cli["ClienteID"].values:
        default_label = (df_cli.loc[df_cli["ClienteID"]==pre, "ClienteID"]+" — "+df_cli.loc[df_cli["ClienteID"]==pre, "RagioneSociale"]).iloc[0]
    sel = safe_selectbox("Cliente", opts, default_label=default_label)
    st.session_state["focus_cid"] = ""
    if not sel: st.stop()
    cid = sel.split(" — ")[0].strip()
    cli = df_cli.loc[df_cli["ClienteID"]==cid].iloc[0].copy()

    st.markdown("##### Anagrafica")
    with st.form("edit_cli"):
        c1,c2 = st.columns(2)
        with c1:
            rag = st.text_input("Ragione sociale", cli["RagioneSociale"])
            ref = st.text_input("Persona di riferimento", cli["PersonaRiferimento"])
            ind = st.text_input("Indirizzo", cli["Indirizzo"])
            citta = st.text_input("Città", cli["Citta"])
            cap = st.text_input("CAP", cli["CAP"])
        with c2:
            tel = st.text_input("Telefono", cli["Telefono"])
            email = st.text_input("Email", cli["Email"])
            piva = st.text_input("Partita IVA", cli["PartitaIVA"])
            iban = st.text_input("IBAN", cli["IBAN"])
            sdi = st.text_input("SDI", cli["SDI"])
        n1,n2 = st.columns(2)
        with n1:
            ultimo_recall = st.date_input("Ultimo recall", value=cli["UltimoRecall"] if isinstance(cli["UltimoRecall"], pd.Timestamp) else None)
            ultima_visita = st.date_input("Ultima visita", value=cli["UltimaVisita"] if isinstance(cli["UltimaVisita"], pd.Timestamp) else None)
        with n2:
            prossimo_recall = st.date_input("Prossimo recall", value=cli["ProssimoRecall"] if isinstance(cli["ProssimoRecall"], pd.Timestamp) else None)
            prossima_visita = st.date_input("Prossima visita", value=cli["ProssimaVisita"] if isinstance(cli["ProssimaVisita"], pd.Timestamp) else None)
        note = st.text_area("Note", cli["Note"], height=100)
        ok = st.form_submit_button("Salva anagrafica", use_container_width=True)

    def _valid_cap(x): return re.fullmatch(r"\d{5}", x or "") is not None
    def _valid_piva(x): return re.fullmatch(r"\d{11}", x or "") is not None
    def _valid_iban(x): return re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{1,30}", (x or "").replace(" ", "").upper()) is not None
    def _valid_sdi(x): return re.fullmatch(r"[A-Z0-9]{7}", (x or "").upper()) is not None

    if ok:
        if cap and not _valid_cap(cap): st.error("CAP non valido (5 cifre)."); st.stop()
        if piva and not _valid_piva(piva): st.error("Partita IVA non valida (11 cifre)."); st.stop()
        if iban and not _valid_iban(iban): st.error("IBAN non valido."); st.stop()
        if sdi and not _valid_sdi(sdi): st.error("SDI non valido (7 alfanumerici)."); st.stop()
        idx = df_cli.index[df_cli["ClienteID"]==cid][0]
        for k,v in {
            "RagioneSociale":rag,"PersonaRiferimento":ref,"Indirizzo":ind,"Citta":citta,"CAP":cap,
            "Telefono":tel,"Email":email,"PartitaIVA":piva,"IBAN":iban,"SDI":sdi,"Note":note
        }.items(): df_cli.at[idx,k]=v
        for k,val in [("UltimoRecall",ultimo_recall),("ProssimoRecall",prossimo_recall),
                     ("UltimaVisita",ultima_visita),("ProssimaVisita",prossima_visita)]:
            df_cli.at[idx,k]= pd.Timestamp(val) if val else pd.NaT
        save_csv(df_cli, CLIENTI_CSV)
        st.success("Anagrafica salvata.")

    st.markdown("##### Preventivi")
    tpl_files = [p.name for p in TEMPLATES.glob("*.docx")]
    if tpl_files:
        chosen = st.selectbox("Template", tpl_files)
        if st.button("Genera preventivo", use_container_width=True):
            out = genera_preventivo(cli, chosen)
            st.success("Preventivo generato.")
            with open(out, "rb") as f:
                st.download_button("Scarica il preventivo", data=f.read(), file_name=out.name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti (rosso = chiusi)")

    opts = (df_cli["ClienteID"]+" — "+df_cli["RagioneSociale"]).tolist()
    pre = st.session_state.get("focus_cid","")
    default_label = ""
    if pre and pre in df_cli["ClienteID"].values:
        default_label = (df_cli.loc[df_cli["ClienteID"]==pre, "ClienteID"]+" — "+df_cli.loc[df_cli["ClienteID"]==pre, "RagioneSociale"]).iloc[0]
    sel = safe_selectbox("Cliente", opts, default_label=default_label)
    st.session_state["focus_cid"] = ""
    if not sel: st.stop()
    cid = sel.split(" — ")[0].strip()
    cli_name = df_cli.loc[df_cli["ClienteID"]==cid,"RagioneSociale"].iloc[0]

    ct_cli = df_ct.loc[df_ct["ClienteID"]==cid].copy()

    st.markdown("##### Aggiungi nuovo contratto")
    with st.expander("Nuovo contratto per questo cliente"):
        with st.form("new_ctr"):
            c1,c2,c3 = st.columns(3)
            with c1:
                ncontr = st.text_input("Numero contratto")
                din = st.date_input("Data inizio", value=None)
            with c2:
                durata = st.selectbox("Durata (mesi)", ["","12","24","36","48","60","72"], index=0)
                dfine = st.date_input("Data fine (opz.)", value=None)
            with c3:
                nolfin = st.text_input("NOL_FIN")
                nolint = st.text_input("NOL_INT")
                totrate = st.text_input("TotRata")
            descr = st.text_area("Descrizione prodotto")
            sub = st.form_submit_button("Aggiungi", use_container_width=True)
        if sub:
            row = {c:"" for c in CONTRATTI_COLS}
            row.update({
                "ClienteID":cid,"NumeroContratto":ncontr,
                "DataInizio":pd.Timestamp(din) if din else pd.NaT,
                "DataFine":pd.Timestamp(dfine) if dfine else (month_add(pd.Timestamp(din), int(durata)) if din and durata.isdigit() else pd.NaT),
                "Durata":durata,"DescrizioneProdotto":descr,"NOL_FIN":nolfin,"NOL_INT":nolint,"TotRata":totrate,"Stato":"aperto"
            })
            df_ct.loc[len(df_ct)] = row
            save_csv(df_ct, CONTRATTI_CSV)
            st.success("Contratto aggiunto.")
            st.rerun()

    st.markdown("##### Selezione/chiusura righe")
    if ct_cli.empty:
        st.caption("Nessun contratto per questo cliente.")
    else:
        for i, r in ct_cli.iterrows():
            left, mid, right = st.columns([0.08, 0.72, 0.2])
            with left:
                st.checkbox("", key=f"sel_{i}", value=False)
            with mid:
                di = _fmt_date(r["DataInizio"]); df = _fmt_date(r["DataFine"])
                st.write(f"**{r['DescrizioneProdotto']}**")
                st.caption(f"dal {di} al {df} · {r['Durata']} M")
            with right:
                if st.button("Chiudi", key=f"close_{i}"):
                    df_ct.at[i, "Stato"] = "chiuso"
                    save_csv(df_ct, CONTRATTI_CSV)
                    st.success("Contratto chiuso.")
                    st.rerun()

    st.markdown("##### Tabella completa")
    html = contracts_html(ct_cli)
    components.html(html, height=min(560, 160 + 32*max(1,len(ct_cli))), scrolling=True)

    st.markdown("##### Esporta / Stampa selezione")
    sel_ids = [int(k.split("_")[1]) for k,v in st.session_state.items() if k.startswith("sel_") and v]
    df_sel = df_ct.loc[sel_ids].copy() if sel_ids else ct_cli.copy()
    df_sel = df_sel[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]]
    if st.button("Esporta selezione in Excel"):
        data = export_xlsx(cli_name, df_sel)
        st.download_button("Scarica Excel", data=data, file_name=f"Contratti_{cid}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.info("La stampa PDF può essere effettuata dal file Excel o tramite stampa del browser.")

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    user, role = require_login()
    st.sidebar.success(f"Utente: {user} · Ruolo: {role}")
    pages = ["Dashboard","Clienti","Contratti"]
    default_page = st.session_state.get("forced_page","Dashboard")
    page = st.sidebar.radio("Navigazione", pages, index=pages.index(default_page))
    st.session_state["forced_page"] = page

    if page=="Dashboard": page_dashboard(df_cli, df_ct, role)
    elif page=="Clienti": page_clienti(df_cli, df_ct, role)
    elif page=="Contratti": page_contratti(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
