# app.py - SHT Gestione Clienti (compatibile Streamlit 1.50.0)

from __future__ import annotations
import os
import io
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import numpy as np
import streamlit as st
from docx import Document

# ------------------------------------------------------------
# ---------------------  CONFIG & UTILS  ---------------------
# ------------------------------------------------------------

APP_TITLE = "SHT – Gestione Clienti"
PAGES = ["Dashboard", "Clienti", "Contratti", "Impostazioni"]

# Storage (locale di default)
STORAGE_BACKEND = st.secrets.get("STORAGE_BACKEND", "local")
LOCAL_STORAGE_DIR = st.secrets.get("LOCAL_STORAGE_DIR", "storage")
BASE_DIR = Path(LOCAL_STORAGE_DIR)

# Percorsi standard
PATH_CLIENTI = BASE_DIR / "clienti.csv"
PATH_CONTRATTI = BASE_DIR / "contratti_clienti.csv"
PATH_PREVENTIVI = BASE_DIR / "preventivi.csv"
DIR_TEMPLATES = BASE_DIR / "templates"
DIR_ALLEGATI = BASE_DIR / "allegati"
DIR_PREVENTIVI_DOCS = BASE_DIR / "preventivi_docs"

# Intestazioni minime
CLIENTI_COLS = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]
CONTRATTI_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]
PREV_COLS = ["NumeroPrev","ClienteID","Data","Template","FileName","Key"]

def ensure_storage():
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    DIR_TEMPLATES.mkdir(parents=True, exist_ok=True)
    DIR_ALLEGATI.mkdir(parents=True, exist_ok=True)
    DIR_PREVENTIVI_DOCS.mkdir(parents=True, exist_ok=True)

    if not PATH_CLIENTI.exists():
        pd.DataFrame(columns=CLIENTI_COLS).to_csv(PATH_CLIENTI, index=False)
    if not PATH_CONTRATTI.exists():
        pd.DataFrame(columns=CONTRATTI_COLS).to_csv(PATH_CONTRATTI, index=False)
    if not PATH_PREVENTIVI.exists():
        pd.DataFrame(columns=PREV_COLS).to_csv(PATH_PREVENTIVI, index=False)

def read_csv_safe(path: Path, cols: List[str]) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception:
        df = pd.DataFrame(columns=cols)
    if set(cols) - set(df.columns):
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df = df[cols]
    return df

def write_csv_safe(path: Path, df: pd.DataFrame):
    df.to_csv(path, index=False)

def fmt_date_dmy(s: str) -> str:
    """Ritorna dd/mm/aaaa (se possibile) oppure stringa originale."""
    s = str(s or "").strip()
    if not s:
        return ""
    # Prova formati comuni
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, f).strftime("%d/%m/%Y")
        except Exception:
            pass
    # Se arriva già 'YYYY/MM/DD HH:MM' ecc…
    try:
        return pd.to_datetime(s, dayfirst=True).strftime("%d/%m/%Y")
    except Exception:
        return s

def parse_date_dmy(s: str) -> str:
    """Accetta input dd/mm/aaaa e salva in dd/mm/aaaa (pulito)."""
    s = str(s or "").strip()
    if not s:
        return ""
    try:
        # Se è una data tipo 2024-10-01 la sistemiamo
        dt = pd.to_datetime(s, dayfirst=True)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return s

def euro(x) -> str:
    try:
        if x in ("", None, np.nan):
            return ""
        v = float(str(x).replace(",", "."))
        return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x or "")

def status_chip(val: str) -> str:
    s = (val or "").strip().lower()
    if s == "chiuso":
        return '<span class="st-badge" style="background:#ffd6d6;color:#c62828;padding:2px 8px;border-radius:12px">chiuso</span>'
    if s == "aperto":
        return '<span class="st-badge" style="background:#e0f2f1;color:#00695c;padding:2px 8px;border-radius:12px">aperto</span>'
    return f'<span class="st-badge" style="background:#eee;color:#555;padding:2px 8px;border-radius:12px">{s or "-"}</span>'

def show_html(html: str, **kw):
    # compat per vecchie installazioni senza st.html
    if hasattr(st, "html"):
        st.html(html, **kw)
    else:
        st.markdown(html, unsafe_allow_html=True)

# ------------------------------------------------------------
# ----------------------  LOGIN / AUTH  ----------------------
# ------------------------------------------------------------

def load_users_from_secrets() -> Dict[str, Dict[str, str]]:
    users = {}
    auth = st.secrets.get("auth", {})
    users_section = auth.get("users", {})
    for uname, info in users_section.items():
        if isinstance(info, dict) and "password" in info and "role" in info:
            users[str(uname).strip().lower()] = {
                "password": str(info["password"]),
                "role": str(info["role"]).strip().lower()
            }
    if not users:
        users["admin"] = {"password": "admin", "role": "admin"}
    return users

def login_box():
    users = load_users_from_secrets()
    st.markdown("### 🔐 Login")
    u_raw = st.text_input("Utente")
    p_raw = st.text_input("Password", type="password")
    if st.button("Entra"):
        u = (u_raw or "").strip().lower()
        p = (p_raw or "").strip()
        info = users.get(u)
        if info and info["password"] == p:
            st.session_state["user"] = u
            st.session_state["role"] = info["role"]
            st.success(f"Benvenuto, {u} ({info['role']})")
            st.rerun()
        else:
            st.error("Credenziali non valide. Controlla utente/password e i Secrets.")

def require_login():
    if "user" not in st.session_state:
        login_box()
        st.stop()

def role_is(*roles: str) -> bool:
    r = st.session_state.get("role", "")
    return r in roles

# ------------------------------------------------------------
# ----------------------  RENDER HELPERS  --------------------
# ------------------------------------------------------------

def contracts_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p><em>Nessun contratto.</em></p>"
    df = df.copy()
    df["DataInizio"] = df["DataInizio"].map(fmt_date_dmy)
    df["DataFine"] = df["DataFine"].map(fmt_date_dmy)
    df["TotRata"] = df["TotRata"].map(euro)
    # Chip stato
    df["_st"] = df["Stato"].map(status_chip)
    df = df.drop(columns=["Stato"]).rename(columns={"_st": "Stato"})
    # Zebra + riga rossa per chiusi
    rows = []
    for _, r in df.iterrows():
        cls = "row-chiuso" if str(r.get("Stato","")).find("badge")>=0 and "chiuso" in r["Stato"] else ""
        tds = "".join(f"<td>{r[c] if not pd.isna(r[c]) else ''}</td>" for c in df.columns)
        rows.append(f"<tr class='{cls}'>{tds}</tr>")
    thead = "".join(f"<th>{c}</th>" for c in df.columns)
    html = f"""
    <style>
    table.ctr {{ border-collapse:collapse; width:100%; }}
    .ctr th,.ctr td {{ border:1px solid #eee; padding:6px 8px; font-size:13px; }}
    .ctr th {{ background:#f5f7fb; text-align:left; }}
    .ctr tr:nth-child(even) {{ background:#fafafa; }}
    .ctr tr.row-chiuso {{ background:#ffecec; }}
    </style>
    <table class="ctr"><thead><tr>{thead}</tr></thead><tbody>
    {''.join(rows)}
    </tbody></table>
    """
    return html

def select_cliente(df_cli: pd.DataFrame, label="Seleziona cliente") -> str:
    if df_cli.empty:
        st.info("Nessun cliente presente. Aggiungilo da **Impostazioni** (import CSV) o da **Clienti**.")
        return ""
    options = (df_cli["ClienteID"].astype(str) + " — " + df_cli["RagioneSociale"].astype(str)).tolist()
    sel = st.selectbox(label, options, index=0)
    cid = sel.split(" — ")[0]
    return cid

# ------------------------------------------------------------
# -------------------------  PAGINE  -------------------------
# ------------------------------------------------------------

def render_dashboard():
    st.markdown("## 📊 Dashboard")
    df_cli = read_csv_safe(PATH_CLIENTI, CLIENTI_COLS)
    df_ct = read_csv_safe(PATH_CONTRATTI, CONTRATTI_COLS)

    st.write(f"**Clienti totali:** {len(df_cli)}")
    st.write(f"**Contratti totali:** {len(df_ct)}")

    # Promemoria entro 30gg: considera ProssimoRecall e ProssimaVisita
    today = pd.to_datetime(date.today())
    horizon = today + pd.Timedelta(days=30)

    def due_within(s):
        s = str(s or "").strip()
        if not s: return False
        d = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(d): return False
        return (today <= d) and (d <= horizon)

    promemoria = df_cli[
        df_cli["ProssimoRecall"].apply(due_within) |
        df_cli["ProssimaVisita"].apply(due_within)
    ][["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]].copy()

    if not promemoria.empty:
        promemoria["ProssimoRecall"] = promemoria["ProssimoRecall"].map(fmt_date_dmy)
        promemoria["ProssimaVisita"] = promemoria["ProssimaVisita"].map(fmt_date_dmy)
        st.markdown("### 🔔 Promemoria in arrivo (30 giorni)")
        st.dataframe(promemoria, use_container_width=True, hide_index=True)
    else:
        st.info("Nessun promemoria nei prossimi 30 giorni.")

def render_clienti():
    st.markdown("## 👥 Clienti")

    df_cli = read_csv_safe(PATH_CLIENTI, CLIENTI_COLS)
    df_ct = read_csv_safe(PATH_CONTRATTI, CONTRATTI_COLS)

    # Selettore cliente
    cid = select_cliente(df_cli)
    if not cid:
        return
    row = df_cli[df_cli["ClienteID"].astype(str) == str(cid)].head(1)
    if row.empty:
        st.warning("Cliente non trovato.")
        return
    r = row.iloc[0]

    col1, col2 = st.columns(2)
    with col1:
        st.subheader(r["RagioneSociale"])
        st.write(f"**Persona di riferimento:** {r['PersonaRiferimento'] or ''}")
        st.write(f"**Indirizzo:** {r['Indirizzo'] or ''}")
        st.write(f"**Città/CAP:** {r['Citta'] or ''}  {r['CAP'] or ''}")
        st.write(f"**Telefono/Email:** {r['Telefono'] or ''}  /  {r['Email'] or ''}")
    with col2:
        st.write(f"**Partita IVA:** {r['PartitaIVA'] or ''}")
        st.write(f"**IBAN / SDI:** {r['IBAN'] or ''} / {r['SDI'] or ''}")
        st.write(f"**Ultimo Recall:** {fmt_date_dmy(r['UltimoRecall'])}")
        st.write(f"**Prossimo Recall:** {fmt_date_dmy(r['ProssimoRecall'])}")
        st.write(f"**Ultima Visita:** {fmt_date_dmy(r['UltimaVisita'])}")
        st.write(f"**Prossima Visita:** {fmt_date_dmy(r['ProssimaVisita'])}")

    st.info(r["Note"] or "")

    st.markdown("### 📎 Allegati cliente")
    up = st.file_uploader("Carica allegato", key="up_cli", label_visibility="collapsed")
    if up is not None:
        target_dir = DIR_ALLEGATI / str(cid)
        target_dir.mkdir(parents=True, exist_ok=True)
        with open(target_dir / up.name, "wb") as f:
            f.write(up.getbuffer())
        st.success("Allegato caricato.")
    # Lista allegati
    target_dir = DIR_ALLEGATI / str(cid)
    if target_dir.exists():
        files = sorted([p.name for p in target_dir.iterdir() if p.is_file()])
        if files:
            st.write("**File:**", ", ".join(files))

    st.markdown("### 📄 Contratti (rosso = chiusi)")
    ct_cli = df_ct[df_ct["ClienteID"].astype(str) == str(cid)].copy()
    show_html(contracts_html(ct_cli), height=min(460, 120 + 28 * len(ct_cli)))

    # PREVENTIVI
    st.markdown("### 🧾 Preventivi")
    tmpls = [p.name for p in DIR_TEMPLATES.glob("*.docx")]
    if not tmpls:
        st.info("Carica prima dei template .docx in `storage/templates/`.")
    else:
        tcol1, tcol2 = st.columns([2, 1])
        with tcol1:
            template = st.selectbox("Template", tmpls)
        with tcol2:
            if st.button("Genera preventivo"):
                num = genera_preventivo(cid, r["RagioneSociale"], template)
                st.success(f"Preventivo creato: {num}")
                st.rerun()

    # Vai alla gestione contratti
    if st.button("➡️ Vai alla gestione contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["cid_focus"] = str(cid)
        st.rerun()

def render_contratti():
    st.markdown("## 📃 Contratti (rosso = chiusi)")

    df_cli = read_csv_safe(PATH_CLIENTI, CLIENTI_COLS)
    df_ct = read_csv_safe(PATH_CONTRATTI, CONTRATTI_COLS)

    # Filtro cliente (se arriva focus dalla pagina Clienti, lo usiamo)
    default_idx = 0
    cid_focus = st.session_state.get("cid_focus")
    if cid_focus:
        try:
            default_idx = df_cli["ClienteID"].astype(str).tolist().index(str(cid_focus))
        except Exception:
            default_idx = 0

    options = (df_cli["ClienteID"].astype(str) + " — " + df_cli["RagioneSociale"].astype(str)).tolist()
    sel = st.selectbox("Cliente", options, index=default_idx)
    cid = sel.split(" — ")[0]
    ct_cli = df_ct[df_ct["ClienteID"].astype(str) == str(cid)].copy()

    # Tabella
    show_html(contracts_html(ct_cli), height=min(460, 120 + 28 * len(ct_cli)))

    st.markdown("---")
    st.markdown("### ⬇️ Esporta / 🖨️ Stampa contratti (selezione)")
    # Selezione numeri contratto
    numeri = ct_cli["NumeroContratto"].dropna().astype(str).tolist()
    sel_nums = st.multiselect("Seleziona N. contratti (vuoto = tutti)", numeri)
    df_export = ct_cli if not sel_nums else ct_cli[ct_cli["NumeroContratto"].astype(str).isin(sel_nums)]

    # Esporta Excel
    if st.button("Esporta in Excel"):
        xls = to_excel(df_export)
        st.download_button("Scarica contratti.xlsx", data=xls, file_name=f"contratti_{cid}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Stampa (HTML -> stampa dal browser)
    if st.button("Stampa (HTML)"):
        html = f"<h3 style='text-align:center'>{df_cli.loc[df_cli['ClienteID'].astype(str)==str(cid),'RagioneSociale'].values[0]}</h3>"
        html += contracts_html(df_export)
        show_html(html, height=600)

    st.markdown("---")
    st.markdown("### ➕ Aggiungi contratto")
    with st.form("add_ct"):
        nc = st.text_input("Numero contratto")
        di = st.text_input("Data inizio (dd/mm/aaaa)")
        dfine = st.text_input("Data fine (dd/mm/aaaa)")
        dur = st.text_input("Durata (mesi)")
        desc = st.text_area("Descrizione prodotto")
        fin = st.text_input("NOL_FIN", value="")
        intr = st.text_input("NOL_INT", value="")
        tot = st.text_input("TotRata", value="")
        stato = st.selectbox("Stato", ["aperto","chiuso"])
        ok = st.form_submit_button("Aggiungi")
    if ok:
        new_row = {
            "ClienteID": str(cid),
            "NumeroContratto": nc.strip(),
            "DataInizio": parse_date_dmy(di),
            "DataFine": parse_date_dmy(dfine),
            "Durata": dur.strip(),
            "DescrizioneProdotto": desc.strip(),
            "NOL_FIN": fin.strip(),
            "NOL_INT": intr.strip(),
            "TotRata": tot.strip(),
            "Stato": stato.strip().lower()
        }
        df_ct = pd.concat([df_ct, pd.DataFrame([new_row])], ignore_index=True)
        write_csv_safe(PATH_CONTRATTI, df_ct)
        st.success("Contratto aggiunto.")
        st.rerun()

    st.markdown("### ✏️ Modifica/Chiudi contratto")
    if not ct_cli.empty:
        sel_num = st.selectbox("Seleziona numero", [""] + ct_cli["NumeroContratto"].astype(str).tolist())
        if sel_num:
            det = ct_cli[ct_cli["NumeroContratto"].astype(str) == sel_num].iloc[0].copy()
            with st.form("edit_ct"):
                e_di = st.text_input("Data inizio", det["DataInizio"])
                e_df = st.text_input("Data fine", det["DataFine"])
                e_dur = st.text_input("Durata", det["Durata"])
                e_desc = st.text_area("Descrizione", det["DescrizioneProdotto"])
                e_fin = st.text_input("NOL_FIN", det["NOL_FIN"])
                e_int = st.text_input("NOL_INT", det["NOL_INT"])
                e_tot = st.text_input("TotRata", det["TotRata"])
                e_stato = st.selectbox("Stato", ["aperto","chiuso"], index=1 if det["Stato"]=="chiuso" else 0)
                ok2 = st.form_submit_button("Aggiorna")
            if ok2:
                idx = df_ct.index[(df_ct["ClienteID"].astype(str)==str(cid)) & (df_ct["NumeroContratto"].astype(str)==sel_num)]
                if len(idx):
                    i = idx[0]
                    df_ct.loc[i, "DataInizio"] = parse_date_dmy(e_di)
                    df_ct.loc[i, "DataFine"] = parse_date_dmy(e_df)
                    df_ct.loc[i, "Durata"] = e_dur
                    df_ct.loc[i, "DescrizioneProdotto"] = e_desc
                    df_ct.loc[i, "NOL_FIN"] = e_fin
                    df_ct.loc[i, "NOL_INT"] = e_int
                    df_ct.loc[i, "TotRata"] = e_tot
                    df_ct.loc[i, "Stato"] = e_stato
                    write_csv_safe(PATH_CONTRATTI, df_ct)
                    st.success("Contratto aggiornato.")
                    st.rerun()

    st.markdown("### 🗑️ Elimina contratto")
    if not ct_cli.empty:
        del_num = st.selectbox("Numero da eliminare", [""] + ct_cli["NumeroContratto"].astype(str).tolist())
        if del_num and st.button("Elimina definitivamente"):
            df_ct = df_ct[~((df_ct["ClienteID"].astype(str)==str(cid)) & (df_ct["NumeroContratto"].astype(str)==del_num))]
            write_csv_safe(PATH_CONTRATTI, df_ct)
            st.success("Eliminato.")
            st.rerun()

def render_settings():
    st.markdown("## ⚙️ Impostazioni")

    st.markdown("### CSV di esempio / Import")
    # Download
    st.download_button("Scarica clienti.csv (vuoto)", data=io.BytesIO(PATH_CLIENTI.read_bytes()), file_name="clienti.csv")
    st.download_button("Scarica contratti_clienti.csv (vuoto)", data=io.BytesIO(PATH_CONTRATTI.read_bytes()), file_name="contratti_clienti.csv")
    st.download_button("Scarica preventivi.csv (vuoto)", data=io.BytesIO(PATH_PREVENTIVI.read_bytes()), file_name="preventivi.csv")

    st.markdown("#### Import clienti.csv")
    up_c = st.file_uploader("Trascina clienti.csv", type=["csv"], key="imp_cli")
    if up_c:
        df = pd.read_csv(up_c, dtype=str)
        write_csv_safe(PATH_CLIENTI, df)
        st.success("Clienti importati.")

    st.markdown("#### Import contratti_clienti.csv")
    up_k = st.file_uploader("Trascina contratti_clienti.csv", type=["csv"], key="imp_ct")
    if up_k:
        df = pd.read_csv(up_k, dtype=str)
        write_csv_safe(PATH_CONTRATTI, df)
        st.success("Contratti importati.")

    st.markdown("#### Carica template .docx")
    up_t = st.file_uploader("Carica template .docx", type=["docx"], key="imp_tpl")
    if up_t:
        with open(DIR_TEMPLATES / up_t.name, "wb") as f:
            f.write(up_t.getbuffer())
        st.success("Template caricato.")

# ------------------------------------------------------------
# ---------------  PREVENTIVI / EXPORT HELPERS  --------------
# ------------------------------------------------------------

def next_preventivo_number() -> str:
    df = read_csv_safe(PATH_PREVENTIVI, PREV_COLS)
    if df.empty:
        return "PRV-0001"
    def ext(n):
        try:
            return int(str(n).split("-")[-1])
        except Exception:
            return 0
    last = df["NumeroPrev"].map(ext).max()
    return f"PRV-{last+1:04d}"

def genera_preventivo(cid: str, ragione: str, template_name: str) -> str:
    numero = next_preventivo_number()
    tpl = DIR_TEMPLATES / template_name
    if not tpl.exists():
        st.error("Template non trovato.")
        return ""
    # Sostituzioni basilari
    placeholders = {
        "{{RAGIONE_SOCIALE}}": ragione,
        "{{DATA}}": datetime.today().strftime("%d/%m/%Y"),
        "{{NUMERO_PREVENTIVO}}": numero,
    }
    doc = Document(str(tpl))
    for p in doc.paragraphs:
        for k, v in placeholders.items():
            if k in p.text:
                p.text = p.text.replace(k, v)
    # tabelle
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for k, v in placeholders.items():
                    if k in cell.text:
                        cell.text = cell.text.replace(k, v)
    out_name = f"{numero}_{ragione.replace(' ','_')}.docx"
    out_path = DIR_PREVENTIVI_DOCS / out_name
    doc.save(out_path)

    # Log su CSV
    df = read_csv_safe(PATH_PREVENTIVI, PREV_COLS)
    new_row = {
        "NumeroPrev": numero,
        "ClienteID": str(cid),
        "Data": datetime.today().strftime("%d/%m/%Y"),
        "Template": template_name,
        "FileName": out_name,
        "Key": f"{cid}-{numero}"
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    write_csv_safe(PATH_PREVENTIVI, df)
    return numero

def to_excel(df: pd.DataFrame) -> bytes:
    df2 = df.copy()
    df2["DataInizio"] = df2["DataInizio"].map(fmt_date_dmy)
    df2["DataFine"] = df2["DataFine"].map(fmt_date_dmy)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df2.to_excel(writer, sheet_name="Contratti", index=False)
    return output.getvalue()

# ------------------------------------------------------------
# --------------------------- MAIN ---------------------------
# ------------------------------------------------------------

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🗂️", layout="wide")
    st.title(APP_TITLE)

    ensure_storage()

    # NAV
    if "sidebar_page" not in st.session_state:
        st.session_state["sidebar_page"] = "Clienti"
    if "nav_target" in st.session_state:
        st.session_state["sidebar_page"] = st.session_state.pop("nav_target")

    require_login()

    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.get('user','')}** ({st.session_state.get('role','')})")
        page = st.radio("Navigazione", PAGES, index=PAGES.index(st.session_state["sidebar_page"]))
        st.session_state["sidebar_page"] = page
        if st.button("Esci"):
            for k in ("user","role"):
                st.session_state.pop(k, None)
            st.rerun()

    if st.session_state["sidebar_page"] == "Dashboard":
        render_dashboard()
    elif st.session_state["sidebar_page"] == "Clienti":
        render_clienti()
    elif st.session_state["sidebar_page"] == "Contratti":
        render_contratti()
    else:
        render_settings()

if __name__ == "__main__":
    main()
