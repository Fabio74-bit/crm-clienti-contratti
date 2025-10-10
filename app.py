from __future__ import annotations

import os
import io
import re
import json
import time
import shutil
from datetime import date, datetime
from typing import Dict, Any, List

import numpy as np
import pandas as pd
import streamlit as st
from docx import Document
import xlsxwriter

# -----------------------------------------------------------------------------
# COSTANTI & PERCORSI
# -----------------------------------------------------------------------------
APP_TITLE = "SHT – Gestione Clienti"
PAGES = ["Dashboard", "Clienti", "Contratti", "Impostazioni"]

# Struttura storage
DEFAULT_STORAGE_DIR = "storage"
CLIENTI_CSV = "clienti.csv"
CONTRATTI_CSV = "contratti_clienti.csv"
PREVENTIVI_CSV = "preventivi.csv"
TEMPLATES_DIR = "templates"
PREVENTIVI_DIR = "preventivi"

# Colonne attese nei CSV
CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo",
    "Citta", "CAP", "Telefono", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
]

CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]

PREVENTIVI_COLS = [
    "ClienteID", "NumeroPrev", "Data", "RagioneSociale", "Descrizione", "FilePath"
]

# -----------------------------------------------------------------------------
# UTILS: storage locale / cartelle
# -----------------------------------------------------------------------------
def storage_dir() -> str:
    """Ritorna la cartella base di storage (da secrets o default)."""
    try:
        if st.secrets.get("STORAGE_BACKEND", "local") == "local":
            base = st.secrets.get("LOCAL_STORAGE_DIR", DEFAULT_STORAGE_DIR)
        else:
            # Per ora gestiamo solo local – altri backend (S3/OneDrive) si attivano in futuro
            base = DEFAULT_STORAGE_DIR
    except Exception:
        base = DEFAULT_STORAGE_DIR
    os.makedirs(base, exist_ok=True)
    return base

def path_clients() -> str:
    return os.path.join(storage_dir(), CLIENTI_CSV)

def path_contracts() -> str:
    return os.path.join(storage_dir(), CONTRATTI_CSV)

def path_preventivi_csv() -> str:
    return os.path.join(storage_dir(), PREVENTIVI_CSV)

def path_templates_dir() -> str:
    p = os.path.join(storage_dir(), TEMPLATES_DIR)
    os.makedirs(p, exist_ok=True)
    return p

def path_preventivi_dir() -> str:
    p = os.path.join(storage_dir(), PREVENTIVI_DIR)
    os.makedirs(p, exist_ok=True)
    return p

# -----------------------------------------------------------------------------
# UTILS: CSV load/save (robusti)
# -----------------------------------------------------------------------------
def load_csv(path: str, columns: List[str]) -> pd.DataFrame:
    if not os.path.exists(path):
        # crea CSV vuoto con intestazioni
        df = pd.DataFrame(columns=columns)
        df.to_csv(path, index=False)
        return df.copy()
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        # se c'è formattazione strana, prova a leggere con engine python
        df = pd.read_csv(path, dtype=str, engine="python").fillna("")
    # assicura tutte le colonne
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    # ordina colonne
    df = df[columns]
    return df.copy()

def save_csv(df: pd.DataFrame, path: str):
    # salvataggio "atomico"
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)

# -----------------------------------------------------------------------------
# AUTENTICAZIONE (da secrets)
# -----------------------------------------------------------------------------
def get_users_from_secrets() -> Dict[str, Dict[str, str]]:
    """
    Attende in Secrets:
    [auth.users.fabio]
    password="..."
    role="admin"
    """
    users = {}
    try:
        users = st.secrets["auth"]["users"]
    except Exception:
        pass
    # normalizza a dict nativo
    native = {}
    for k, v in users.items():
        native[str(k)] = {"password": str(v.get("password", "")),
                          "role": str(v.get("role", ""))}
    return native

def login_box():
    st.subheader("Accesso")
    user = st.text_input("Utente", key="login_user")
    pwd  = st.text_input("Password", type="password", key="login_pwd")
    if st.button("Entra", type="primary"):
        users = get_users_from_secrets()
        if user in users and pwd == users[user]["password"]:
            st.session_state["user"] = user
            st.session_state["role"] = users[user]["role"]
            st.success(f"Benvenuto, {user}")
            st.rerun()
        else:
            st.error("Credenziali non valide.")

def require_login():
    if "user" not in st.session_state:
        login_box()
        st.stop()

def has_role(*roles: str) -> bool:
    r = st.session_state.get("role", "")
    return r in roles

# -----------------------------------------------------------------------------
# FORMATI & STATUS (robusti ai valori vuoti/NaN)
# -----------------------------------------------------------------------------
def it_date_to_str(dt: Any) -> str:
    """Converte date/str in 'dd/mm/aaaa' (vuoto se non valida)."""
    if dt is None:
        return ""
    if isinstance(dt, date):
        return dt.strftime("%d/%m/%Y")
    s = str(dt).strip()
    if not s:
        return ""
    # prova parse flessibile
    for fmt in ("%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%d.%m.%Y"):
        try:
            d = datetime.strptime(s, fmt).date()
            return d.strftime("%d/%m/%Y")
        except Exception:
            pass
    # tenta pandas
    try:
        d = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.notna(d):
            return d.strftime("%d/%m/%Y")
    except Exception:
        pass
    return ""

def parse_date_input(s: str) -> date | None:
    """Ritorna date (python) da stringa dd/mm/aaaa o None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except Exception:
        try:
            d = pd.to_datetime(s, dayfirst=True, errors="coerce")
            if pd.notna(d):
                return d.date()
        except Exception:
            pass
    return None

def euro(v: Any) -> str:
    try:
        # accetta “1.234,56” oppure float
        if isinstance(v, (int,float)):
            return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        s = str(v).strip().replace("€","").replace(" ", "")
        if not s:
            return ""
        s = s.replace(".", "").replace(",", ".")
        f = float(s)
        return euro(f)
    except Exception:
        return str(v or "")

# ---- STATUS tolerant ---------------------------------------------------------
def _norm(val) -> str:
    if val is None:
        return ""
    s = str(val)
    if s.lower() == "nan":
        return ""
    return s.strip().lower()

def status_class(val: Any) -> str:
    s = _norm(val)
    if s in ("chiuso", "closed", "chiusa"):
        return "closed"
    elif s in ("aperto", "open", "nuovo", "nuova"):
        return "open"
    return "open"

def status_chip(val: Any) -> str:
    label = str(val).strip() if _norm(val) else "aperto"
    cls = status_class(val)
    return f"<span class='chip {cls}'>{label}</span>"

# -----------------------------------------------------------------------------
# HTML helpers (tabella contratti)
# -----------------------------------------------------------------------------
CSS = """
<style>
.chip {
  display:inline-block; padding:2px 8px; border-radius:12px; font-size:12px;
  color:#fff; background:#1e88e5;
}
.chip.closed { background:#d32f2f; }
.chip.open { background:#388e3c; }
.ctr-table { width:100%; border-collapse:collapse; font-size:14px; }
.ctr-table th, .ctr-table td { border:1px solid #e0e0e0; padding:6px 8px; }
.ctr-table thead th { background:#e3f2fd; }
.ctr-table tr.closed-row td { background:#ffebee; }
</style>
"""

def contracts_html(df: pd.DataFrame) -> str:
    if "Stato" not in df.columns:
        df["Stato"] = ""
    # colonna chip per stato (tollerante)
    df["_st"] = df["Stato"].fillna("").apply(status_chip)

    # formattazioni
    df = df.copy()
    # date lato UI: dd/mm/aaaa
    for c in ["DataInizio", "DataFine"]:
        df[c] = df[c].apply(it_date_to_str)
    # euro
    for c in ["NOL_FIN", "NOL_INT", "TotRata"]:
        df[c] = df[c].apply(euro)

    # ordinamento colonne nella tabella
    cols = ["NumeroContratto","DataInizio","DataFine","Durata",
            "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","_st"]
    cols = [c for c in cols if c in df.columns]
    df2 = df[cols].rename(columns={"_st":"Stato"})

    # righe rosse per contratti chiusi
    trs = []
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in df2.columns) + "</tr></thead>"
    for _, r in df2.iterrows():
        row_class = "closed-row" if status_class(r.get("Stato","")) == "closed" else ""
        tds = "".join(f"<td>{r[c]}</td>" for c in df2.columns)
        trs.append(f"<tr class='{row_class}'>{tds}</tr>")
    tbody = "<tbody>" + "".join(trs) + "</tbody>"
    return CSS + f"<table class='ctr-table'>{thead}{tbody}</table>"

def show_html(html: str, **kw):
    if hasattr(st, "html"):
        st.html(html, **kw)
    else:
        st.markdown(html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PREVENTIVI (Word) – generazione da template
# -----------------------------------------------------------------------------
def next_preventivo_number(df_prev: pd.DataFrame) -> int:
    if df_prev.empty:
        return 1
    try:
        nums = pd.to_numeric(df_prev["NumeroPrev"], errors="coerce").fillna(0).astype(int)
        return int(nums.max()) + 1
    except Exception:
        return len(df_prev) + 1

def list_templates() -> List[str]:
    base = path_templates_dir()
    files = [f for f in os.listdir(base) if f.lower().endswith(".docx")]
    files.sort()
    return files

def create_preventivo(cliente: Dict[str, Any], template_name: str, descrizione: str) -> Dict[str, Any]:
    """Genera preventivo da template Word e ritorna info riga da appendere al CSV."""
    base = path_templates_dir()
    tpl_path = os.path.join(base, template_name)
    if not os.path.exists(tpl_path):
        raise FileNotFoundError(f"Template non trovato: {template_name}")

    # carica preventivi.csv
    prev_csv = path_preventivi_csv()
    df_prev = load_csv(prev_csv, PREVENTIVI_COLS)

    numero = next_preventivo_number(df_prev)
    oggi = date.today().strftime("%d/%m/%Y")

    # prepara docx
    doc = Document(tpl_path)
    placeholders = {
        "{{NumeroPrev}}": str(numero),
        "{{Data}}": oggi,
        "{{RagioneSociale}}": str(cliente.get("RagioneSociale","")),
        "{{PersonaRiferimento}}": str(cliente.get("PersonaRiferimento","")),
        "{{Descrizione}}": str(descrizione or ""),
    }
    for p, v in placeholders.items():
        for par in doc.paragraphs:
            if p in par.text:
                par.text = par.text.replace(p, v)
        # anche nelle tabelle
        for tb in doc.tables:
            for row in tb.rows:
                for cell in row.cells:
                    if p in cell.text:
                        cell.text = cell.text.replace(p, v)
    # salva file
    out_dir = path_preventivi_dir()
    safe_rs = re.sub(r"[^A-Za-z0-9_.-]+", "_", cliente.get("RagioneSociale",""))
    out_name = f"PREV-{numero:05d}-{safe_rs}.docx"
    out_path = os.path.join(out_dir, out_name)
    doc.save(out_path)

    # riga per CSV
    return {
        "ClienteID": str(cliente.get("ClienteID","")),
        "NumeroPrev": str(numero),
        "Data": oggi,
        "RagioneSociale": str(cliente.get("RagioneSociale","")),
        "Descrizione": str(descrizione or ""),
        "FilePath": out_path
    }

# -----------------------------------------------------------------------------
# ESPORTA EXCEL
# -----------------------------------------------------------------------------
def df_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Contratti", index=False)
    return output.getvalue()

# -----------------------------------------------------------------------------
# UI – PAGINE
# -----------------------------------------------------------------------------
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame):
    st.subheader("Promemoria in arrivo (30 giorni)")
    # esempio semplice: prossimi recall e prossime visite
    for field, label in [("ProssimoRecall", "Prossimi Recall"),
                         ("ProssimaVisita", "Prossime Visite")]:
        st.markdown(f"**{label}**")
        now = date.today()
        horizon = now + pd.Timedelta(days=30)
        tmp = df_cli.copy()
        tmp[field] = tmp[field].apply(parse_date_input)
        mask = tmp[field].notna() & (tmp[field] >= now) & (tmp[field] <= horizon)
        out = tmp.loc[mask, ["ClienteID","RagioneSociale",field]].copy()
        out[field] = out[field].apply(lambda d: d.strftime("%d/%m/%Y") if d else "")
        if out.empty:
            st.info("Nessun promemoria.")
        else:
            st.dataframe(out, hide_index=True, use_container_width=True)
        st.divider()

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")

    # elenco clienti per select
    df_cli = df_cli.copy()
    df_cli["__label"] = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    sel = st.selectbox("Cliente", df_cli["__label"].tolist())
    sel_id = sel.split(" — ")[0] if sel else ""
    cli = df_cli.loc[df_cli["ClienteID"] == sel_id].iloc[0].to_dict()

    # ANAGRAFICA
    st.markdown("### Anagrafica")
    cols = st.columns(3)
    cols[0].markdown(f"**Persona di riferimento:** {cli.get('PersonaRiferimento','') or '—'}")
    cols[0].markdown(f"**Indirizzo:** {cli.get('Indirizzo','') or '—'}")
    cols[0].markdown(f"**Città:** {cli.get('Citta','')} **CAP:** {cli.get('CAP','')}")
    cols[1].markdown(f"**Telefono:** {cli.get('Telefono','') or '—'}")
    cols[1].markdown(f"**Email:** {cli.get('Email','') or '—'}")
    cols[1].markdown(f"**Partita IVA:** {cli.get('PartitaIVA','') or '—'}")
    cols[2].markdown(f"**IBAN:** {cli.get('IBAN','') or '—'}")
    cols[2].markdown(f"**SDI:** {cli.get('SDI','') or '—'}")

    st.info(cli.get("Note","") or "—")

    # Preventivi (lista/genera)
    with st.expander("📄 Preventivi"):
        templates = list_templates()
        if not templates:
            st.warning("Nessun template trovato in `storage/templates/`.")
        else:
            tpl = st.selectbox("Template", templates)
            desc = st.text_area("Descrizione prodotto/servizio")
            if st.button("Genera preventivo", type="primary"):
                try:
                    row = create_preventivo(cli, tpl, desc)
                    df_prev = load_csv(path_preventivi_csv(), PREVENTIVI_COLS)
                    df_prev = pd.concat([df_prev, pd.DataFrame([row])], ignore_index=True)
                    save_csv(df_prev, path_preventivi_csv())
                    st.success(f"Preventivo {row['NumeroPrev']} creato.")
                except Exception as e:
                    st.error(f"Errore generazione preventivo: {e}")

        # Elenco preventivi del cliente
        df_prev = load_csv(path_preventivi_csv(), PREVENTIVI_COLS)
        mine = df_prev[df_prev["ClienteID"] == cli["ClienteID"]].copy()
        if not mine.empty:
            st.dataframe(mine[["NumeroPrev","Data","Descrizione","FilePath"]],
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nessun preventivo per questo cliente.")

    # goto contratti
    if st.button("➡ Vai alla gestione contratti di questo cliente"):
        st.session_state["selected_cliente"] = cli["ClienteID"]
        st.session_state["nav_page"] = "Contratti"
        st.rerun()

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti (rosso = chiusi)")
    # selezione cliente in alto
    df_cli = df_cli.copy()
    df_cli["__label"] = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    default_sel = None
    if "selected_cliente" in st.session_state:
        sid = st.session_state["selected_cliente"]
        matches = df_cli["__label"][df_cli["ClienteID"] == sid]
        default_sel = matches.iloc[0] if not matches.empty else None

    sel = st.selectbox("Cliente", df_cli["__label"].tolist(), index=(
        df_cli["__label"].tolist().index(default_sel) if default_sel in df_cli["__label"].tolist() else 0
    ))
    sel_id = sel.split(" — ")[0] if sel else ""
    ct_cli = df_ct[df_ct["ClienteID"] == sel_id].copy()

    # tabella HTML
    show_html(contracts_html(ct_cli), height=min(460, 120 + 28 * len(ct_cli)))

    st.divider()

    # ESPORTA / STAMPA
    with st.expander("🧾 Esporta / Stampa contratti"):
        # selezione subset
        all_nums = ct_cli["NumeroContratto"].dropna().tolist()
        pick = st.multiselect("Seleziona N. contratti (vuoto = tutti)", all_nums)
        to_export = ct_cli.copy()
        if pick:
            to_export = to_export[to_export["NumeroContratto"].isin(pick)]
        # normalizza per Excel
        out = to_export.copy()
        for c in ["DataInizio","DataFine"]:
            out[c] = out[c].apply(it_date_to_str)
        for c in ["NOL_FIN","NOL_INT","TotRata"]:
            out[c] = out[c].apply(lambda x: re.sub(r"[€\s\.]", "", str(euro(x))).replace(",", "."))
        if st.button("Esporta Excel"):
            xls = df_to_xlsx_bytes(out.drop(columns=["Stato"], errors="ignore"))
            st.download_button(
                "Scarica contratti.xlsx",
                xls,
                file_name=f"contratti_{sel_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    st.divider()

    editable = has_role("admin", "editor")
    if not editable:
        st.info("Solo Admin/Editor possono modificare i contratti.")
        return

    # AGGIUNGI CONTRATTO
    with st.expander("➕ Aggiungi contratto"):
        col1, col2 = st.columns(2)
        num = col1.text_input("NumeroContratto")
        data_inizio = col1.text_input("DataInizio (dd/mm/aaaa)")
        data_fine   = col1.text_input("DataFine (dd/mm/aaaa)")
        durata      = col1.text_input("Durata (mesi)")
        descr       = col2.text_input("DescrizioneProdotto")
        fin         = col2.text_input("NOL_FIN (€/mese)", value="")
        intr        = col2.text_input("NOL_INT (€/mese)", value="")
        stato       = col2.selectbox("Stato", ["aperto","chiuso"])

        # calcolo TotRata se NON INT non vuoto
        def _to_float(s: str) -> float:
            s = (s or "").replace("€","").replace(" ", "").replace(".", "").replace(",", ".")
            return float(s) if s else 0.0

        if st.button("Aggiungi"):
            if not num:
                st.error("NumeroContratto obbligatorio.")
            else:
                row = {
                    "ClienteID": sel_id,
                    "NumeroContratto": num,
                    "DataInizio": it_date_to_str(data_inizio),
                    "DataFine": it_date_to_str(data_fine),
                    "Durata": durata or "",
                    "DescrizioneProdotto": descr or "",
                    "NOL_FIN": str(_to_float(fin)) if fin else "",
                    "NOL_INT": str(_to_float(intr)) if intr else "",
                    "TotRata": str((_to_float(fin) + _to_float(intr)) if (fin or intr) else ""),
                    "Stato": stato or "aperto"
                }
                df_ct2 = pd.concat([df_ct, pd.DataFrame([row])], ignore_index=True)
                save_csv(df_ct2, path_contracts())
                st.success("Contratto aggiunto.")
                st.rerun()

    # MODIFICA/CHIUDI CONTRATTO
    with st.expander("✏️ Modifica/Chiudi contratto"):
        if ct_cli.empty:
            st.info("Nessun contratto per il cliente selezionato.")
        else:
            nums = ct_cli["NumeroContratto"].tolist()
            nsel = st.selectbox("Seleziona numero", nums)
            row  = ct_cli[ct_cli["NumeroContratto"] == nsel].iloc[0].to_dict()

            c1, c2 = st.columns(2)
            di = c1.text_input("DataInizio", it_date_to_str(row.get("DataInizio","")))
            df_ = c1.text_input("DataFine",   it_date_to_str(row.get("DataFine","")))
            durata = c1.text_input("Durata", str(row.get("Durata","")))
            descr  = c2.text_input("DescrizioneProdotto", row.get("DescrizioneProdotto",""))
            fin    = c2.text_input("NOL_FIN", str(row.get("NOL_FIN","")))
            intr   = c2.text_input("NOL_INT", str(row.get("NOL_INT","")))
            stato  = c2.selectbox("Stato", ["aperto","chiuso"], index= 1 if status_class(row.get("Stato",""))=="closed" else 0)

            if st.button("Aggiorna"):
                df_ct2 = df_ct.copy()
                mask = (df_ct2["ClienteID"]==sel_id) & (df_ct2["NumeroContratto"]==nsel)
                df_ct2.loc[mask, "DataInizio"] = it_date_to_str(di)
                df_ct2.loc[mask, "DataFine"]   = it_date_to_str(df_)
                df_ct2.loc[mask, "Durata"]     = str(durata or "")
                df_ct2.loc[mask, "DescrizioneProdotto"] = descr or ""
                # normalizza numeri
                def _to_f(s):
                    try:
                        s = str(s).replace("€","").replace(" ","").replace(".", "").replace(",", ".")
                        return str(float(s)) if s else ""
                    except Exception:
                        return ""
                df_ct2.loc[mask, "NOL_FIN"] = _to_f(fin)
                df_ct2.loc[mask, "NOL_INT"] = _to_f(intr)
                # tot
                try:
                    tot = float(df_ct2.loc[mask, "NOL_FIN"].iloc[0] or 0) + float(df_ct2.loc[mask, "NOL_INT"].iloc[0] or 0)
                    df_ct2.loc[mask, "TotRata"] = str(tot)
                except Exception:
                    pass
                df_ct2.loc[mask, "Stato"] = stato
                save_csv(df_ct2, path_contracts())
                st.success("Contratto aggiornato.")
                st.rerun()

    with st.expander("🗑 Elimina contratto"):
        if ct_cli.empty:
            st.info("Nessun contratto da eliminare.")
        else:
            nsel = st.selectbox("Numero da eliminare", ct_cli["NumeroContratto"].tolist(), key="delnum")
            if st.button("Elimina DEFINITIVAMENTE"):
                df_ct2 = df_ct[~((df_ct["ClienteID"]==sel_id) & (df_ct["NumeroContratto"]==nsel))].copy()
                save_csv(df_ct2, path_contracts())
                st.success("Contratto eliminato.")
                st.rerun()

def page_settings():
    st.subheader("Impostazioni")
    st.write("Percorso storage:", f"`{storage_dir()}`")
    st.write("Templates:", f"`{path_templates_dir()}`")
    st.write("Preventivi:", f"`{path_preventivi_dir()}`")
    st.info("Per cambiare colori e tema usa `.streamlit/config.toml`.")

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    # LOGIN
    require_login()

    # Navigazione sidebar (usiamo sessione per poter “saltare” tra pagine)
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Clienti"

    with st.sidebar:
        page = st.radio("📂 Pagine", PAGES, index=PAGES.index(st.session_state["nav_page"]))
        st.session_state["nav_page"] = page
        st.caption(f"Utente: **{st.session_state.get('user','?')}** — ruolo: **{st.session_state.get('role','?')}**")
        if st.button("Esci"):
            for k in ("user","role","nav_page","selected_cliente"):
                st.session_state.pop(k, None)
            st.rerun()

    # carica dati
    df_cli = load_csv(path_clients(), CLIENTI_COLS)
    df_ct  = load_csv(path_contracts(), CONTRATTI_COLS)

    # routing
    page = st.session_state["nav_page"]
    if page == "Dashboard":
        page_dashboard(df_cli, df_ct)
    elif page == "Clienti":
        page_clienti(df_cli, df_ct, st.session_state.get("role",""))
    elif page == "Contratti":
        page_contratti(df_cli, df_ct, st.session_state.get("role",""))
    elif page == "Impostazioni":
        page_settings()
    else:
        st.write("Pagina non trovata.")

if __name__ == "__main__":
    main()
