# app.py — SHT – Gestione Clienti (Streamlit 1.50 ready)

from __future__ import annotations
import io
import re
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Tuple, Optional, List

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components  # per show_html
from docx import Document
import xlsxwriter


# ------------------------------------------------------------------------------
# 1) Compat layer / helpers
# ------------------------------------------------------------------------------
def do_rerun():
    """Usa st.rerun() se disponibile; fallback a st.experimental_rerun()."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def show_html(html: str, **kw):
    """Fallback sicuro alla componente HTML."""
    components.html(html, scrolling=True, **({"height": 400} | kw))


@st.cache_data(show_spinner=False)
def _status_color(s: str) -> str:
    s = (s or "").strip().lower()
    if s in ("chiuso", "closed", "close"):
        return "#ffebee"  # rosino
    if s in ("aperto", "open"):
        return "#e8f5e9"  # verdino
    return "#fafafa"      # neutro


def _fmt_eur(x) -> str:
    if pd.isna(x) or x == "":
        return ""
    try:
        v = float(str(x).replace(",", "."))
    except Exception:
        return str(x)
    return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def status_chip(val: str) -> str:
    s = (val or "").strip().lower()
    if s == "chiuso":
        return "🔴 chiuso"
    if s == "aperto":
        return "🟢 aperto"
    return val or ""


def _today_str() -> str:
    return date.today().strftime("%d/%m/%Y")


# ------------------------------------------------------------------------------
# 2) Storage back-end (local + CSV)
# ------------------------------------------------------------------------------
def base_dir() -> Path:
    """Ritorna la root di storage in base ai secrets."""
    backend = st.secrets.get("STORAGE_BACKEND", "local").lower()
    if backend == "local":
        return Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage")).resolve()
    # (futuro: s3/onedrive …)
    return Path("storage").resolve()


def ensure_dirs():
    b = base_dir()
    (b / "templates").mkdir(parents=True, exist_ok=True)


def _csv_path(name: str) -> Path:
    return base_dir() / name


CLIENTI_PATH = lambda: _csv_path("clienti.csv")
CONTRATTI_PATH = lambda: _csv_path("contratti_clienti.csv")
PREVENTIVI_PATH = lambda: _csv_path("preventivi.csv")
TEMPLATES_DIR = lambda: base_dir() / "templates"


def _default_clienti() -> pd.DataFrame:
    cols = [
        "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo",
        "Citta", "CAP", "Telefono", "Email", "PartitaIVA", "IBAN", "SDI",
        "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
    ]
    return pd.DataFrame(columns=cols)


def _default_contratti() -> pd.DataFrame:
    cols = [
        "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
        "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
    ]
    return pd.DataFrame(columns=cols)


def _default_preventivi() -> pd.DataFrame:
    cols = ["ClienteID", "Numero", "Data", "Template", "FileSalvato", "Note"]
    return pd.DataFrame(columns=cols)


def _read_csv(path: Path, empty_df: pd.DataFrame) -> pd.DataFrame:
    if not path.exists():
        empty_df.to_csv(path, index=False)
        return empty_df.copy()
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
    except Exception:
        df = empty_df.copy()
    # assicurati di avere tutte le colonne
    for c in empty_df.columns:
        if c not in df.columns:
            df[c] = ""
    df = df[empty_df.columns]  # ordine
    return df


def load_clienti() -> pd.DataFrame:
    return _read_csv(CLIENTI_PATH(), _default_clienti())


def load_contratti() -> pd.DataFrame:
    return _read_csv(CONTRATTI_PATH(), _default_contratti())


def load_preventivi() -> pd.DataFrame:
    return _read_csv(PREVENTIVI_PATH(), _default_preventivi())


def save_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# ------------------------------------------------------------------------------
# 3) Auth & roles
# ------------------------------------------------------------------------------
def get_users_from_secrets() -> Dict[str, Dict[str, str]]:
    """Raccoglie utenti dal blocco [auth.users.*] dei secrets."""
    users = {}
    if "auth" in st.secrets and "users" in st.secrets["auth"]:
        for uname, item in st.secrets["auth"]["users"].items():
            users[str(uname).strip().lower()] = {
                "password": str(item.get("password", "")),
                "role": str(item.get("role", "contributor"))
            }
    return users


def require_login() -> Tuple[str, str]:
    """Ritorna (user, role), mostrando il login box se necessario."""
    if "user" in st.session_state and "role" in st.session_state:
        return st.session_state["user"], st.session_state["role"]

    users = get_users_from_secrets()

    st.markdown("### 🔐 Login")
    with st.form("login_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Utente").strip().lower()
        with col2:
            password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Entra")

    if submitted:
        if username in users and password == users[username]["password"]:
            st.session_state["user"] = username
            st.session_state["role"] = users[username]["role"]
            st.success(f"Benvenuto, {username}!")
            do_rerun()
        else:
            st.error("Credenziali non valide.")

    st.stop()  # fermo qui finché non loggato


def can_edit(role: str) -> bool:
    return role in ("admin", "editor")


def can_view(role: str) -> bool:
    return role in ("admin", "editor", "contributor")


# ------------------------------------------------------------------------------
# 4) UI util
# ------------------------------------------------------------------------------
def header(title: str):
    st.markdown(f"## {title}")


def go_to(page_name: str):
    st.session_state["nav_target"] = page_name
    do_rerun()


def select_cliente(df_cli: pd.DataFrame, key="cliente_sel") -> Optional[dict]:
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return None
    df_cli = df_cli.copy()
    df_cli["__label"] = df_cli["ClienteID"].astype(str) + " — " + df_cli["RagioneSociale"].astype(str)
    sel = st.selectbox("Cliente", df_cli["__label"].tolist(), index=0, key=key)
    cid = int(sel.split(" — ")[0])
    return df_cli.loc[df_cli["ClienteID"].astype(int) == cid].iloc[0].to_dict()


def contracts_html(df: pd.DataFrame) -> str:
    """Ritorna tabella HTML con righe colorate in base allo stato."""
    if df.empty:
        return "<em>Nessun contratto</em>"

    df_v = df.copy()
    df_v["NOL_FIN"] = df_v["NOL_FIN"].apply(_fmt_eur)
    df_v["NOL_INT"] = df_v["NOL_INT"].apply(_fmt_eur)
    df_v["TotRata"] = df_v["TotRata"].apply(_fmt_eur)
    df_v["__bg"] = df_v["Stato"].map(_status_color)

    cols = ["NumeroContratto", "DataInizio", "DataFine", "Durata", "DescrizioneProdotto",
            "NOL_FIN", "NOL_INT", "TotRata", "Stato"]
    cols_show = [c for c in cols if c in df_v.columns]

    # costruzione html semplice
    head = "".join(f"<th>{c}</th>" for c in cols_show)
    body = []
    for _, r in df_v.iterrows():
        tds = "".join(f"<td>{r.get(c,'')}</td>" for c in cols_show)
        body.append(f"<tr style='background:{r['__bg']}'>"+tds+"</tr>")
    table = f"""
    <table class="ctr-table" style="width:100%; border-collapse:collapse;">
      <thead><tr>{head}</tr></thead>
      <tbody>{"".join(body)}</tbody>
    </table>
    """
    return table


def export_contratti_excel(df: pd.DataFrame, cliente_nome: str) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Contratti")
        # un po' di formattazione
        wb = writer.book
        ws = writer.sheets["Contratti"]
        money_fmt = wb.add_format({"num_format": "€ #,##0.00"})
        for col, name in enumerate(df.columns):
            if name in ("NOL_FIN", "NOL_INT", "TotRata"):
                ws.set_column(col, col, 12, money_fmt)
            else:
                ws.set_column(col, col, 22)
        ws.write(0, 0, f"Contratti — {cliente_nome}")
    return out.getvalue()


# ------------------------------------------------------------------------------
# 5) PREVENTIVI (Word .docx)
# ------------------------------------------------------------------------------
PLACEHOLDERS = {
    "RAGIONE_SOCIALE": "RagioneSociale",
    "DATA": None,            # today
    "NUMERO": None,          # progressivo
    "PERSONA_RIF": "PersonaRiferimento",
    "INDIRIZZO": "Indirizzo",
    "CITTA": "Citta",
    "CAP": "CAP",
    "PIVA": "PartitaIVA",
    "IBAN": "IBAN",
    "SDI": "SDI",
}

def next_preventivo_number(df_prev: pd.DataFrame, cliente_id: int) -> int:
    filt = df_prev.loc[df_prev["ClienteID"].astype(str) == str(cliente_id)]
    if filt.empty:
        return 1
    try:
        return int(filt["Numero"].astype(int).max()) + 1
    except Exception:
        return 1


def fill_docx_template(template_path: Path, mapping: Dict[str, str], out_path: Path):
    doc = Document(str(template_path))
    # sostituzione semplice nei paragrafi
    for p in doc.paragraphs:
        for k, v in mapping.items():
            p.text = p.text.replace(f"{{{{{k}}}}}", v)
    # tabelle
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for k, v in mapping.items():
                    cell.text = cell.text.replace(f"{{{{{k}}}}}", v)
    doc.save(out_path)


def preventivi_panel(cliente: dict, role: str, df_prev: pd.DataFrame):
    st.markdown("### 🧾 Preventivi")
    templates = [p for p in TEMPLATES_DIR().glob("*.docx")]
    if not templates:
        st.info("Carica i template .docx in **storage/templates/**")
        return

    tnames = [p.name for p in templates]
    tsel = st.selectbox("Template", tnames, index=0, key="tpl_sel")
    tpl_path = TEMPLATES_DIR() / tsel

    n_next = next_preventivo_number(df_prev, int(cliente["ClienteID"]))
    col1, col2 = st.columns(2)
    with col1:
        nro = st.number_input("Numero preventivo", min_value=1, value=int(n_next), step=1)
    with col2:
        data_p = st.text_input("Data", _today_str())

    if st.button("📄 Genera preventivo (Word)"):
        # mappatura placeholder
        mapping = {}
        for ph, field in PLACEHOLDERS.items():
            if field is None:
                if ph == "DATA":
                    mapping[ph] = data_p
                elif ph == "NUMERO":
                    mapping[ph] = str(nro)
            else:
                mapping[ph] = str(cliente.get(field, ""))

        out_name = f"PREV_{cliente['ClienteID']}_{nro}.docx"
        out_path = TEMPLATES_DIR() / out_name
        fill_docx_template(tpl_path, mapping, out_path)

        # aggiorno CSV preventivi
        df_prev2 = df_prev.copy()
        row = {
            "ClienteID": str(cliente["ClienteID"]),
            "Numero": str(nro),
            "Data": data_p,
            "Template": tsel,
            "FileSalvato": out_name,
            "Note": "",
        }
        df_prev2 = pd.concat([df_prev2, pd.DataFrame([row])], ignore_index=True)
        save_csv(df_prev2, PREVENTIVI_PATH())
        st.success(f"Preventivo creato: {out_name}")

        with open(out_path, "rb") as f:
            st.download_button("⬇️ Scarica il preventivo", f, file_name=out_name)

        do_rerun()


# ------------------------------------------------------------------------------
# 6) Pagine
# ------------------------------------------------------------------------------
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("👥 Clienti")
    cliente = select_cliente(df_cli, key="cli_select")
    if not cliente:
        return

    # anagrafica
    st.markdown("#### Anagrafica")
    colL, colR = st.columns(2)
    with colL:
        st.write(f"**Ragione Sociale**: {cliente['RagioneSociale']}")
        st.write(f"**Persona di riferimento**: {cliente.get('PersonaRiferimento','')}")
        st.write(f"**Indirizzo**: {cliente.get('Indirizzo','')}")
        st.write(f"**Città**: {cliente.get('Citta','')}  **CAP**: {cliente.get('CAP','')}")
        st.write(f"**Telefono**: {cliente.get('Telefono','')}")
        st.write(f"**Email**: {cliente.get('Email','')}")
    with colR:
        st.write(f"**P.IVA**: {cliente.get('PartitaIVA','')}")
        st.write(f"**IBAN**: {cliente.get('IBAN','')}")
        st.write(f"**SDI**: {cliente.get('SDI','')}")
        st.write(f"**Ultimo Recall**: {cliente.get('UltimoRecall','')}")
        st.write(f"**Prossimo Recall**: {cliente.get('ProssimoRecall','')}")
        st.write(f"**Ultima Visita**: {cliente.get('UltimaVisita','')}")
        st.write(f"**Prossima Visita**: {cliente.get('ProssimaVisita','')}")

    st.markdown("---")
    if st.button("➡️ Vai alla gestione contratti di questo cliente"):
        st.session_state["cliente_corrente_id"] = int(cliente["ClienteID"])
        go_to("Contratti")

    # pannello preventivi
    df_prev = load_preventivi()
    preventivi_panel(cliente, role, df_prev)


def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("📑 Contratti (rosso = chiusi)")
    # selezione cliente (preferisci quello in sessione)
    default_label = None
    if "cliente_corrente_id" in st.session_state:
        try:
            cid = int(st.session_state["cliente_corrente_id"])
            r = df_cli.loc[df_cli["ClienteID"].astype(int) == cid]
            if not r.empty:
                default_label = f"{cid} — {r.iloc[0]['RagioneSociale']}"
        except:
            default_label = None

    cliente = select_cliente(df_cli, key="cli_in_contratti")
    if not cliente:
        return

    cid = int(cliente["ClienteID"])
    ct_cli = df_ct.loc[df_ct["ClienteID"].astype(str) == str(cid)].copy()

    st.markdown("#### Elenco")
    html = contracts_html(ct_cli)
    show_html(html, height=min(460, 120 + 28 * len(ct_cli)))

    # esporta/stampa
    col1, col2 = st.columns(2)
    with col1:
        xls = export_contratti_excel(ct_cli, cliente["RagioneSociale"])
        st.download_button("⬇️ Esporta in Excel", data=xls,
                           file_name=f"contratti_{cid}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        st.info("Per la stampa, usa l'Excel esportato o il comando stampa del browser.")

    if not can_edit(role):
        st.warning("Solo Admin/Editor possono aggiungere o modificare contratti.")
        return

    st.markdown("---")
    st.markdown("#### ➕ Aggiungi / ✏️ Modifica contratto")

    # form add/update
    colA, colB, colC = st.columns(3)
    with colA:
        numero = st.text_input("NumeroContratto")
        datainizio = st.text_input("DataInizio (dd/mm/aaaa)", value=_today_str())
        datafine = st.text_input("DataFine (dd/mm/aaaa)", value="")
        durata = st.text_input("Durata (es. 60 M)", value="")
    with colB:
        descr = st.text_input("DescrizioneProdotto", value="")
        fin = st.text_input("NOL_FIN (mensile)", value="")
        intr = st.text_input("NOL_INT (mensile)", value="")
        tot = st.text_input("TotRata", value="")
    with colC:
        stato = st.selectbox("Stato", ["aperto", "chiuso"], index=0)

    colX, colY = st.columns(2)
    with colX:
        if st.button("💾 Salva/aggiorna"):
            df2 = df_ct.copy()
            # se numero esiste per quel cliente -> update, altrimenti append
            mask = (df2["ClienteID"].astype(str) == str(cid)) & (df2["NumeroContratto"].astype(str) == numero)
            row = {
                "ClienteID": str(cid),
                "NumeroContratto": numero,
                "DataInizio": datainizio,
                "DataFine": datafine,
                "Durata": durata,
                "DescrizioneProdotto": descr,
                "NOL_FIN": fin,
                "NOL_INT": intr,
                "TotRata": tot,
                "Stato": stato,
            }
            if mask.any():
                df2.loc[mask, list(row.keys())] = list(row.values())
            else:
                df2 = pd.concat([df2, pd.DataFrame([row])], ignore_index=True)
            save_csv(df2, CONTRATTI_PATH())
            st.success("Contratto salvato.")
            do_rerun()
    with colY:
        if st.button("🗑️ Elimina (per NumeroContratto)"):
            df2 = df_ct.copy()
            mask = (df2["ClienteID"].astype(str) == str(cid)) & (df2["NumeroContratto"].astype(str) == numero)
            df2 = df2.loc[~mask].copy()
            save_csv(df2, CONTRATTI_PATH())
            st.success("Contratto eliminato (se esisteva).")
            do_rerun()


# ------------------------------------------------------------------------------
# 7) main
# ------------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="SHT – Gestione Clienti", page_icon="📘", layout="wide")
    ensure_dirs()

    # login
    user, role = require_login()
    if not can_view(role):
        st.error("Non autorizzato.")
        st.stop()

    # sidebar nav
    PAGES = ["Clienti", "Contratti", "Impostazioni"]
    if "sidebar_page" not in st.session_state:
        st.session_state["sidebar_page"] = "Clienti"
    # redirect "go_to"
    if "nav_target" in st.session_state:
        st.session_state["sidebar_page"] = st.session_state.pop("nav_target")

    page = st.sidebar.radio("Navigazione", PAGES, index=PAGES.index(st.session_state["sidebar_page"]))
    st.session_state["sidebar_page"] = page

    # logout
    if st.sidebar.button("🚪 Logout"):
        for k in ("user", "role", "sidebar_page", "nav_target", "cliente_corrente_id"):
            st.session_state.pop(k, None)
        do_rerun()

    # dati
    df_cli = load_clienti()
    df_ct = load_contratti()

    st.markdown("# SHT – Gestione Clienti")

    if page == "Clienti":
        page_clienti(df_cli, df_ct, role)
    elif page == "Contratti":
        page_contratti(df_cli, df_ct, role)
    else:
        st.markdown("### ⚙️ Impostazioni")
        st.write("Collega OneDrive/S3 o configura MySQL in seguito. Per ora lo storage è locale su `storage/`.")
        st.write(f"Cartella storage: `{base_dir()}`")


if __name__ == "__main__":
    main()
