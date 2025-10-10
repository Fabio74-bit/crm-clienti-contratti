# app.py  — SHT – Gestione Clienti (Streamlit 1.50 compatibile)

from __future__ import annotations
import io
import re
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components  # <-- al posto di st.html
from docx import Document
# --- compat per rerun: Streamlit >=1.27 usa st.rerun ---
def do_rerun():
    """Chiama st.rerun() se disponibile, altrimenti (per versioni vecchie) st.experimental_rerun()."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# -----------------------------------------------------------------------------
# Config e costanti
# -----------------------------------------------------------------------------
APP_TITLE = "SHT – Gestione Clienti"

# Segreti (si leggono da Streamlit Cloud > App settings > Secrets)
SECRETS = st.secrets if hasattr(st, "secrets") else {}

STORAGE_BACKEND = SECRETS.get("STORAGE_BACKEND", "local")
LOCAL_STORAGE_DIR = SECRETS.get("LOCAL_STORAGE_DIR", "storage")

USERS = SECRETS.get("auth", {}).get("users", {
    "fabio": {"password": "admin", "role": "admin"},
    "emanuela": {"password": "editor", "role": "editor"},
    "claudia": {"password": "editor", "role": "editor"},
    "giulia": {"password": "contributor", "role": "contributor"},
    "antonella": {"password": "contributor", "role": "contributor"},
})

BASE = Path(__file__).parent
STORAGE = (BASE / LOCAL_STORAGE_DIR).resolve()

CSV_CLIENTI = STORAGE / "clienti.csv"
CSV_CONTRATTI = STORAGE / "contratti_clienti.csv"
CSV_PREVENTIVI = STORAGE / "preventivi.csv"
TPL_DIR = STORAGE / "templates"

DATE_FMT = "%d/%m/%Y"

CLIENTI_COLS = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]

CONTRATTI_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
    "NOL_FIN","NOL_INT","TotRata","Stato"
]

PREVENTIVI_COLS = [
    "NumeroPreventivo","ClienteID","Data","Template","File"
]

# -----------------------------------------------------------------------------
# Utility di Filesystem & CSV
# -----------------------------------------------------------------------------
def ensure_dirs() -> None:
    STORAGE.mkdir(exist_ok=True, parents=True)
    TPL_DIR.mkdir(exist_ok=True, parents=True)
    (STORAGE / "preventivi").mkdir(exist_ok=True, parents=True)

def new_empty_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(columns=columns)
    df.to_csv(path, index=False)
    return df

def load_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return new_empty_csv(path, columns)
    df = pd.read_csv(path, dtype=str).fillna("")
    # garantisco le colonne attese
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    df = df[columns]
    return df

def save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False)

def fmt_date(s: str) -> str:
    """Normalizza in dd/mm/yyyy se possibile, altrimenti stringa originale."""
    s = str(s).strip()
    if not s:
        return ""
    # tenta auto parse
    for fmt in (DATE_FMT, "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime(DATE_FMT)
        except Exception:
            pass
    # tenta pandas
    try:
        return pd.to_datetime(s, dayfirst=True).strftime(DATE_FMT)
    except Exception:
        return s

# -----------------------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------------------
def show_html(html: str, height: int = 480, scrolling: bool = True, **kw):
    """Compatibile con Streamlit 1.50 – usa components.html."""
    components.html(html, height=height, scrolling=scrolling)

def status_class(s: str) -> str:
    s = (s or "").strip().lower()
    if s in ("chiuso","closed"):
        return "chip chip-red"
    if s in ("nuovo","new"):
        return "chip chip-yellow"
    # default: aperto
    return "chip chip-green"

def status_chip(s: str) -> str:
    cls = status_class(s)
    label = (s or "").strip() or "aperto"
    return f"<span class='{cls}'>{label}</span>"

def contracts_html(df: pd.DataFrame) -> str:
    # costruisci tabella HTML con stile + righe rosse se Stato=chiuso
    styles = """
    <style>
      table.ctr { width: 100%; border-collapse: collapse; font-size: 14px; }
      table.ctr th, table.ctr td { border:1px solid #dfe3e6; padding:8px; }
      table.ctr thead { background:#f5f7f9; }
      tr.closed { background:#ffecec; }
      .chip { padding: 2px 8px; border-radius: 999px; color:#fff; font-size:12px; }
      .chip-green { background:#2e7d32; }
      .chip-red { background:#c62828; }
      .chip-yellow { background:#f9a825; color:#111; }
    </style>
    """

    cols = [
        "NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
        "NOL_FIN","NOL_INT","TotRata","Stato"
    ]
    # safe columns
    for c in cols:
        if c not in df.columns:
            df[c] = ""

    # format date & money
    _df = df.copy()
    _df["DataInizio"] = _df["DataInizio"].map(fmt_date)
    _df["DataFine"]   = _df["DataFine"].map(fmt_date)
    for c in ("NOL_FIN","NOL_INT","TotRata"):
        _df[c] = _df[c].map(lambda x: format_currency(x))

    # stato chip col
    _df["_st"] = _df["Stato"].map(status_chip)

    # html
    th = "".join(f"<th>{c}</th>" for c in ["NumeroContratto","DataInizio","DataFine","Durata",
                                          "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"])
    rows = []
    for _, r in _df.iterrows():
        tr_cls = "closed" if str(r.get("Stato","")).strip().lower()=="chiuso" else ""
        rows.append(
            f"<tr class='{tr_cls}'>"
            f"<td>{safe(r['NumeroContratto'])}</td>"
            f"<td>{safe(r['DataInizio'])}</td>"
            f"<td>{safe(r['DataFine'])}</td>"
            f"<td>{safe(r['Durata'])}</td>"
            f"<td>{safe(r['DescrizioneProdotto'])}</td>"
            f"<td>{safe(r['NOL_FIN'])}</td>"
            f"<td>{safe(r['NOL_INT'])}</td>"
            f"<td>{safe(r['TotRata'])}</td>"
            f"<td>{r['_st']}</td>"
            f"</tr>"
        )
    tb = "<table class='ctr'><thead><tr>"+th+"</tr></thead><tbody>"+"".join(rows)+"</tbody></table>"
    return styles + tb

def safe(x) -> str:
    x = "" if pd.isna(x) else str(x)
    return x.replace("<","&lt;").replace(">","&gt;")

def format_currency(x) -> str:
    s = str(x).strip().replace(",", ".")
    try:
        v = float(s) if s else 0.0
    except Exception:
        return s
    # formato italiano € 1.234,56
    return "€ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")

def progressive_number(df: pd.DataFrame, col: str, width: int = 4) -> str:
    """Genera un progressivo semplice basato su max esistente (col string)."""
    try:
        nums = [int(re.findall(r"(\d+)$", str(x))[0]) for x in df[col].tolist() if re.findall(r"(\d+)$", str(x))]
        n = max(nums)+1 if nums else 1
    except Exception:
        n = 1
    return f"{n:0{width}d}"

# -----------------------------------------------------------------------------
# Autenticazione semplice
# -----------------------------------------------------------------------------
def logged_user() -> Tuple[str, str] | None:
    """Ritorna (user, role) se loggato, altrimenti None."""
    if "auth_user" in st.session_state and "auth_role" in st.session_state:
        return st.session_state["auth_user"], st.session_state["auth_role"]
    return None

def login_box():
    st.subheader("Accesso")
    u = st.text_input("Utente", key="lg_u")
    p = st.text_input("Password", type="password", key="lg_p")
    col1, col2 = st.columns([1,3])
    with col1:
        if st.button("Entra"):
            if u in USERS and p == USERS[u]["password"]:
                st.session_state["auth_user"] = u
                st.session_state["auth_role"] = USERS[u]["role"]
                st.success(f"Benvenuto, {u}!")
                st.experimental_rerun()
            else:
                st.error("Credenziali non valide")

def require_login() -> Tuple[str,str]:
    lu = logged_user()
    if lu is not None:
        return lu
    login_box()
    st.stop()

# -----------------------------------------------------------------------------
# Pagine
# -----------------------------------------------------------------------------
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.header("Clienti")

    if df_cli.empty:
        st.info("Nessun cliente. Crea almeno una riga in `storage/clienti.csv`.")
        return

    # selettore cliente
    opts = [f"{row.ClienteID} — {row.RagioneSociale}" for _, row in df_cli.iterrows()]
    sel = st.selectbox("Cliente", opts, index=0 if opts else None, key="sel_cli")

    if not sel:
        return
    sel_id = int(sel.split(" — ")[0])

    # anagrafica
    cli_row = df_cli.loc[df_cli["ClienteID"].astype(str) == str(sel_id)]
    if cli_row.empty:
        st.warning("Cliente non trovato.")
        return
    det = cli_row.iloc[0].to_dict()

    with st.container():
        st.subheader(det.get("RagioneSociale",""))
        c1, c2, c3 = st.columns(3)
        with c1:
            st.write(f"**Persona di riferimento:** {safe(det.get('PersonaRiferimento',''))}")
            st.write(f"**Indirizzo:** {safe(det.get('Indirizzo',''))}")
            st.write(f"**Città:** {safe(det.get('Citta',''))} — **CAP:** {safe(det.get('CAP',''))}")
            st.write(f"**Telefono:** {safe(det.get('Telefono',''))}")
            st.write(f"**Email:** {safe(det.get('Email',''))}")
        with c2:
            st.write(f"**Partita IVA:** {safe(det.get('PartitaIVA',''))}")
            st.write(f"**IBAN:** {safe(det.get('IBAN',''))}")
            st.write(f"**SDI:** {safe(det.get('SDI',''))}")
        with c3:
            st.write(f"**Ultimo Recall:** {fmt_date(det.get('UltimoRecall',''))}")
            st.write(f"**Prossimo Recall:** {fmt_date(det.get('ProssimoRecall',''))}")
            st.write(f"**Ultima Visita:** {fmt_date(det.get('UltimaVisita',''))}")
            st.write(f"**Prossima Visita:** {fmt_date(det.get('ProssimaVisita',''))}")
        if det.get("Note","").strip():
            st.info(det["Note"])

        if st.button("➡️ Vai alla gestione contratti di questo cliente"):
            st.session_state["current_client_id"] = sel_id
            go_to("Contratti")

    st.divider()
    st.subheader("Preventivi (rapido)")
    with st.expander("Genera nuovo preventivo"):
        templates = [p.name for p in TPL_DIR.glob("*.docx")]
        if not templates:
            st.warning("Carica prima dei template DOCX in `storage/templates/`.")
        else:
            tpl = st.selectbox("Scegli template", templates)
            if st.button("Crea preventivo"):
                df_prev = load_csv(CSV_PREVENTIVI, PREVENTIVI_COLS)
                nr = progressive_number(df_prev, "NumeroPreventivo", width=4)
                out_name = f"PREV-{sel_id}-{nr}.docx"
                out_path = STORAGE / "preventivi" / out_name
                try:
                    build_docx_from_template(TPL_DIR / tpl, out_path, det)
                    new_row = {
                        "NumeroPreventivo": f"{sel_id}-{nr}",
                        "ClienteID": str(sel_id),
                        "Data": date.today().strftime(DATE_FMT),
                        "Template": tpl,
                        "File": str(out_path.relative_to(STORAGE))
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([new_row])], ignore_index=True)
                    save_csv(df_prev, CSV_PREVENTIVI)
                    st.success(f"Creato: {out_name}")
                    with open(out_path, "rb") as fh:
                        st.download_button("Scarica preventivo", fh, file_name=out_name)
                except Exception as e:
                    st.error(f"Errore creazione preventivo: {e}")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.header("Contratti (rosso = chiusi)")

    if df_cli.empty:
        st.info("Nessun cliente in `clienti.csv`.")
        return

    # cliente selezionato
    default_id = st.session_state.get("current_client_id")
    opts = [f"{row.ClienteID} — {row.RagioneSociale}" for _, row in df_cli.iterrows()]
    default_idx = 0
    if default_id:
        for i, s in enumerate(opts):
            if s.split(" — ")[0] == str(default_id):
                default_idx = i
                break
    sel = st.selectbox("Cliente", opts, index=default_idx)
    sel_id = int(sel.split(" — ")[0])
    st.session_state["current_client_id"] = sel_id

    ct_cli = df_ct.loc[df_ct["ClienteID"].astype(str)==str(sel_id)].copy()

    # tabella HTML
    html = contracts_html(ct_cli)
    # altezza dinamica
    h = min(460, 120 + 28*len(ct_cli))
    show_html(html, height=h)

    st.divider()
    st.subheader("Esporta / Stampa contratti (selezione)")
    with st.expander("Esporta in Excel"):
        # seleziona righe
        multi = st.multiselect("Seleziona N. contratti (vuoto = tutti)", ct_cli["NumeroContratto"].tolist())
        to_export = ct_cli if not multi else ct_cli[ct_cli["NumeroContratto"].isin(multi)]
        if st.button("Scarica Excel"):
            xls = to_excel_bytes(to_export)
            st.download_button("Download contratti.xlsx", xls, file_name="contratti.xlsx")

    st.divider()
    st.subheader("Aggiungi / Modifica / Chiudi contratto")
    with st.expander("Aggiungi contratto"):
        form_add_contract(sel_id, df_ct, role)

    with st.expander("Modifica / Chiudi contratto"):
        if ct_cli.empty:
            st.info("Nessun contratto per questo cliente.")
        else:
            form_edit_contract(sel_id, df_ct, role)

# -----------------------------------------------------------------------------
# Forms contratti
# -----------------------------------------------------------------------------
def form_add_contract(cid: int, df_ct: pd.DataFrame, role: str):
    ncontr = st.text_input("NumeroContratto")
    din = st.date_input("Data inizio", value=date.today())
    dfin = st.date_input("Data fine", value=date.today())
    durata = st.number_input("Durata (mesi)", value=0, step=1)
    descr = st.text_input("Descrizione prodotto")
    nol_fin = st.number_input("NOL_FIN", value=0.0, step=1.0)
    nol_int = st.number_input("NOL_INT", value=0.0, step=1.0)
    link_tot = st.checkbox("TotRata = FIN + INT", value=True)
    if link_tot:
        tot = nol_fin + nol_int
    else:
        tot = st.number_input("TotRata", value=0.0, step=1.0)
    stato = st.selectbox("Stato", ["aperto","chiuso","nuovo"])

    if st.button("Aggiungi"):
        if not ncontr.strip():
            st.warning("NumeroContratto obbligatorio")
            return
        new = {
            "ClienteID": str(cid),
            "NumeroContratto": ncontr.strip(),
            "DataInizio": din.strftime(DATE_FMT),
            "DataFine": dfin.strftime(DATE_FMT),
            "Durata": str(int(durata)) if durata else "",
            "DescrizioneProdotto": descr.strip(),
            "NOL_FIN": f"{float(nol_fin):.2f}",
            "NOL_INT": f"{float(nol_int):.2f}",
            "TotRata": f"{float(tot):.2f}",
            "Stato": stato
        }
        df_all = load_csv(CSV_CONTRATTI, CONTRATTI_COLS)
        df_all = pd.concat([df_all, pd.DataFrame([new])], ignore_index=True)
        save_csv(df_all, CSV_CONTRATTI)
        st.success("Contratto aggiunto")
        st.experimental_rerun()

def form_edit_contract(cid: int, df_ct: pd.DataFrame, role: str):
    ct_cli = df_ct[df_ct["ClienteID"].astype(str)==str(cid)]
    sel_nc = st.selectbox("Seleziona numero", ct_cli["NumeroContratto"].tolist())
    row = ct_cli[ct_cli["NumeroContratto"]==sel_nc].iloc[0].to_dict()

    c1, c2 = st.columns(2)
    with c1:
        din = st.text_input("DataInizio", fmt_date(row.get("DataInizio","")))
        dfin = st.text_input("DataFine", fmt_date(row.get("DataFine","")))
        durata = st.text_input("Durata", row.get("Durata",""))
        descr = st.text_input("Descrizione", row.get("DescrizioneProdotto",""))
    with c2:
        nol_fin = st.number_input("NOL_FIN", value=float(row.get("NOL_FIN") or 0.0), step=1.0)
        nol_int = st.number_input("NOL_INT", value=float(row.get("NOL_INT") or 0.0), step=1.0)
        link_tot = st.checkbox("TotRata = FIN + INT", value=True)
        if link_tot:
            tot = nol_fin + nol_int
        else:
            tot = st.number_input("TotRata", value=float(row.get("TotRata") or 0.0), step=1.0)
        stato = st.selectbox("Stato", ["aperto","chiuso","nuovo"], index=["aperto","chiuso","nuovo"].index((row.get("Stato","aperto") or "aperto")))

    if st.button("Aggiorna"):
        df_all = load_csv(CSV_CONTRATTI, CONTRATTI_COLS)
        idx = df_all[(df_all["ClienteID"].astype(str)==str(cid)) & (df_all["NumeroContratto"]==sel_nc)].index
        if not len(idx):
            st.error("Riga non trovata")
            return
        i = idx[0]
        df_all.loc[i, "DataInizio"] = fmt_date(din)
        df_all.loc[i, "DataFine"]   = fmt_date(dfin)
        df_all.loc[i, "Durata"]     = str(durata).strip()
        df_all.loc[i, "DescrizioneProdotto"] = descr.strip()
        df_all.loc[i, "NOL_FIN"]    = f"{float(nol_fin):.2f}"
        df_all.loc[i, "NOL_INT"]    = f"{float(nol_int):.2f}"
        df_all.loc[i, "TotRata"]    = f"{float(tot):.2f}"
        df_all.loc[i, "Stato"]      = stato
        save_csv(df_all, CSV_CONTRATTI)
        st.success("Contratto aggiornato. Ricorda che le righe 'chiuso' vengono evidenziate in rosso.")
        st.experimental_rerun()

    with st.expander("Elimina contratto"):
        if st.button("Elimina definitivamente", type="primary"):
            df_all = load_csv(CSV_CONTRATTI, CONTRATTI_COLS)
            df_all = df_all[~((df_all["ClienteID"].astype(str)==str(cid)) & (df_all["NumeroContratto"]==sel_nc))]
            save_csv(df_all, CSV_CONTRATTI)
            st.success("Eliminato")
            st.experimental_rerun()

# -----------------------------------------------------------------------------
# Export helpers
# -----------------------------------------------------------------------------
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Contratti", index=False)
    return output.getvalue()

# -----------------------------------------------------------------------------
# DOCX helper
# -----------------------------------------------------------------------------
def build_docx_from_template(tpl_path: Path, out_path: Path, client: Dict[str,str]) -> None:
    """
    Sostituzione minima: rimpiazza in tutti i paragrafi e tabelle le chiavi {{CHIAVE}}
    con i valori dell'anagrafica cliente (case-insensitive).
    Esempi di campi nel DOCX:
      {{RagioneSociale}}  {{Indirizzo}}  {{Citta}}  {{CAP}}  {{PartitaIVA}}  ...
    """
    def replace_text_in_paragraph(par, mapping):
        for run in par.runs:
            txt = run.text
            for k,v in mapping.items():
                txt = txt.replace(f"{{{{{k}}}}}", v)
            run.text = txt

    mapping = {k: str(client.get(k,"")) for k in CLIENTI_COLS}
    doc = Document(str(tpl_path))
    for p in doc.paragraphs:
        replace_text_in_paragraph(p, mapping)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    replace_text_in_paragraph(p, mapping)
    doc.save(str(out_path))

# -----------------------------------------------------------------------------
# Navigazione
# -----------------------------------------------------------------------------
PAGES = ["Clienti","Contratti"]
def go_to(page_name: str):
    st.session_state["sidebar_page"] = page_name
    st.experimental_rerun()

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    ensure_dirs()

    user, role = require_login()

    # Sidebar
    if "sidebar_page" not in st.session_state:
        st.session_state["sidebar_page"] = "Clienti"
    with st.sidebar:
        st.write(f"**Utente:** {user}  \n**Ruolo:** {role}")
        page = st.radio("Navigazione", PAGES, index=PAGES.index(st.session_state["sidebar_page"]))
        st.session_state["sidebar_page"] = page
        if st.button("Esci"):
            for k in ("auth_user","auth_role"):
                st.session_state.pop(k, None)
            st.experimental_rerun()

    # carica CSV
    df_cli = load_csv(CSV_CLIENTI, CLIENTI_COLS)
    df_ct  = load_csv(CSV_CONTRATTI, CONTRATTI_COLS)

    if page == "Clienti":
        page_clienti(df_cli, df_ct, role)
    elif page == "Contratti":
        page_contratti(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
