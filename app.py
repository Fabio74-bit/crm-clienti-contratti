# app.py — SHT – Gestione Clienti (Streamlit 1.50 compatibile)

from __future__ import annotations
from pathlib import Path
from datetime import date
from typing import Optional, Dict

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components  # per compatibilità (se mai servisse)
from docx import Document
from io import BytesIO

# --------------------------------------------------------------------------------------
# Config base
# --------------------------------------------------------------------------------------
st.set_page_config(page_title="SHT – Gestione Clienti", page_icon="🧭", layout="wide")

APP_TITLE = "SHT – Gestione Clienti"

# --------------------------------------------------------------------------------------
# Storage locale (CSV + templates)
# --------------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
TEMPLATES_DIR = STORAGE_DIR / "templates"

STORAGE_DIR.mkdir(exist_ok=True, parents=True)
TEMPLATES_DIR.mkdir(exist_ok=True, parents=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"

# --------------------------------------------------------------------------------------
# CSV di base (se non esistono)
# --------------------------------------------------------------------------------------
def _default_clienti() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ClienteID",
            "RagioneSociale",
            "PersonaRiferimento",
            "Indirizzo",
            "Citta",
            "CAP",
            "Telefono",
            "Email",
            "PartitaIVA",
            "IBAN",
            "SDI",
            "UltimoRecall",
            "ProssimoRecall",
            "UltimaVisita",
            "ProssimaVisita",
            "Note",
        ]
    )


def _default_contratti() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ClienteID",
            "NumeroContratto",
            "DataInizio",
            "DataFine",
            "Durata",
            "DescrizioneProdotto",
            "NOL_FIN",
            "NOL_INT",
            "TotRata",
            "Stato",
        ]
    )


def _default_preventivi() -> pd.DataFrame:
    return pd.DataFrame(columns=["ClienteID", "Numero", "Data", "Template", "FileSalvato", "Note"])


# --------------------------------------------------------------------------------------
# IO CSV
# --------------------------------------------------------------------------------------
def load_csv(path: Path, default_df: pd.DataFrame) -> pd.DataFrame:
    if not path.exists():
        default_df.to_csv(path, index=False, encoding="utf-8")
        return default_df.copy()
    try:
        return pd.read_csv(path, dtype=str, encoding="utf-8").fillna("")
    except Exception:
        return default_df.copy()


def save_csv(df: pd.DataFrame, path: Path):
    df = df.fillna("")
    df.to_csv(path, index=False, encoding="utf-8")


def load_clienti() -> pd.DataFrame:
    return load_csv(CLIENTI_CSV, _default_clienti())


def load_contratti() -> pd.DataFrame:
    return load_csv(CONTRATTI_CSV, _default_contratti())


def load_preventivi() -> pd.DataFrame:
    return load_csv(PREVENTIVI_CSV, _default_preventivi())


# --------------------------------------------------------------------------------------
# Utility varie
# --------------------------------------------------------------------------------------
def _today_str() -> str:
    today = date.today()
    return f"{today.day:02d}/{today.month:02d}/{today.year}"


def _fmt_eur(x) -> str:
    try:
        s = str(x).strip()
        if not s:
            return ""
        val = float(str(s).replace(",", "."))
        return f"€ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)


def do_rerun():
    st.rerun()


# --------------------------------------------------------------------------------------
# Placeholder mapping per i template Word
# --------------------------------------------------------------------------------------
PLACEHOLDERS: Dict[str, Optional[str]] = {
    "RAGIONE_SOCIALE": "RagioneSociale",
    "RIFERIMENTO": "PersonaRiferimento",
    "INDIRIZZO": "Indirizzo",
    "CITTA": "Citta",
    "CAP": "CAP",
    "PIVA": "PartitaIVA",
    "IBAN": "IBAN",
    "SDI": "SDI",
    "TELEFONO": "Telefono",
    "EMAIL": "Email",
    # dinamici
    "DATA": None,     # ci scriviamo la data
    "NUMERO": None,   # numero preventivo
}


def fill_docx_template(tpl_path: Path, mapping: Dict[str, str], out_path: Path):
    doc = Document(tpl_path)
    for p in doc.paragraphs:
        for ph, val in mapping.items():
            p.text = p.text.replace("{"+ph+"}", str(val))

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for ph, val in mapping.items():
                    cell.text = cell.text.replace("{"+ph+"}", str(val))

    doc.save(out_path)


def next_preventivo_number(df_prev: pd.DataFrame, cliente_id: int) -> int:
    try:
        df = df_prev.loc[df_prev["ClienteID"].astype(str) == str(cliente_id)]
        if df.empty:
            return 1
        m = df["Numero"].astype(int).max()
        return int(m) + 1
    except Exception:
        return 1


# --------------------------------------------------------------------------------------
# Login minimo (in st.secrets opzionale). Se non presente -> "fabio" (admin) di default
# --------------------------------------------------------------------------------------
def require_login():
    users = st.secrets.get("auth", {}).get("users", None)
    if not users:
        # fallback: login finto
        st.session_state.setdefault("user", "fabio")
        st.session_state.setdefault("role", "admin")
        return "fabio", "admin"

    if "user" in st.session_state and "role" in st.session_state:
        return st.session_state["user"], st.session_state["role"]

    st.info("Accedi per continuare")
    with st.form("login"):
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Entra")
    if ok:
        if u in users and str(users[u].get("password", "")) == str(p):
            st.session_state["user"] = u
            st.session_state["role"] = users[u].get("role", "viewer")
            st.success(f"Benvenuto, {u}!")
            do_rerun()
        else:
            st.error("Credenziali errate")
    st.stop()


def can_edit(role: str) -> bool:
    return role in ("admin", "editor")


# --------------------------------------------------------------------------------------
# Helpers clienti
# --------------------------------------------------------------------------------------
def new_cliente_id(df_cli: pd.DataFrame) -> int:
    if df_cli.empty:
        return 1
    try:
        return int(df_cli["ClienteID"].astype(int).max()) + 1
    except Exception:
        return 1


def upsert_cliente(df_cli: pd.DataFrame, row: dict, delete: bool = False) -> pd.DataFrame:
    df2 = df_cli.copy()
    cid = str(row["ClienteID"])
    if delete:
        df2 = df2.loc[df2["ClienteID"].astype(str) != cid].copy()
    else:
        mask = df2["ClienteID"].astype(str) == cid
        if mask.any():
            for k, v in row.items():
                df2.loc[mask, k] = str(v)
        else:
            df2 = pd.concat([df2, pd.DataFrame([row])], ignore_index=True)
    save_csv(df2, CLIENTI_CSV)
    return df2


# --------------------------------------------------------------------------------------
# UI utilities
# --------------------------------------------------------------------------------------
def header(title: str):
    st.markdown(f"## {title}")


def select_cliente(df_cli: pd.DataFrame, key="cliente_sel") -> Optional[dict]:
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return None

    df_cli = df_cli.copy()
    df_cli["__label"] = df_cli["ClienteID"].astype(str) + " — " + df_cli["RagioneSociale"].astype(str)
    labels = df_cli["__label"].tolist()

    # default da sessione
    default_label = None
    if "cliente_corrente_id" in st.session_state:
        try:
            cid = int(st.session_state["cliente_corrente_id"])
            r = df_cli.loc[df_cli["ClienteID"].astype(int) == cid]
            if not r.empty:
                default_label = f"{cid} — {r.iloc[0]['RagioneSociale']}"
        except Exception:
            default_label = None

    idx = labels.index(default_label) if default_label in labels else 0
    sel = st.selectbox("Cliente", labels, index=idx, key=key)

    cid = int(sel.split(" — ")[0])
    st.session_state["cliente_corrente_id"] = cid

    return df_cli.loc[df_cli["ClienteID"].astype(int) == cid].iloc[0].to_dict()


# --------------------------------------------------------------------------------------
# Preventivi
# --------------------------------------------------------------------------------------
def preventivi_panel(cliente: dict, role: str, df_prev: pd.DataFrame):
    st.markdown("### 🧾 Preventivi")

    # elenco esistente del cliente
    my_prev = df_prev.loc[df_prev["ClienteID"].astype(str) == str(cliente["ClienteID"])].copy()
    if not my_prev.empty:
        st.markdown("#### Preventivi esistenti")
        my_prev = my_prev.sort_values(["Data", "Numero"], ascending=[False, False])
        for _, r in my_prev.iterrows():
            file_name = r.get("FileSalvato", "")
            file_path = TEMPLATES_DIR / file_name if file_name else None
            cols = st.columns([4, 2, 3, 2])
            cols[0].write(f"**N° {r['Numero']}** – {r['Template']}")
            cols[1].write(r.get("Data", ""))
            cols[2].write(file_name or "")
            if file_path and file_path.exists():
                with open(file_path, "rb") as f:
                    cols[3].download_button(
                        "⬇️ Scarica",
                        data=f.read(),
                        file_name=file_name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_prev_{r['Numero']}_{file_name}"
                    )
            else:
                cols[3].warning("File non trovato")

    st.markdown("---")
    templates = [p for p in TEMPLATES_DIR.glob("*.docx")]
    if not templates:
        st.info("Carica i template .docx in **storage/templates/**")
        return

    tnames = [p.name for p in templates]
    tsel = st.selectbox("Template", tnames, index=0, key="tpl_sel")
    tpl_path = TEMPLATES_DIR / tsel

    n_next = next_preventivo_number(df_prev, int(cliente["ClienteID"]))
    col1, col2 = st.columns(2)
    with col1:
        nro = st.number_input("Numero preventivo", min_value=1, value=int(n_next), step=1)
    with col2:
        data_p = st.text_input("Data", _today_str())

    if st.button("📄 Genera preventivo (Word)"):
        mapping = {}
        for ph, field in PLACEHOLDERS.items():
            if field is None:
                mapping[ph] = data_p if ph == "DATA" else str(nro)
            else:
                mapping[ph] = str(cliente.get(field, ""))

        out_name = f"PREV_{cliente['ClienteID']}_{nro}.docx"
        out_path = TEMPLATES_DIR / out_name
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
        save_csv(df_prev2, PREVENTIVI_CSV)

        st.success(f"Preventivo creato e salvato in **storage/templates/{out_name}**.")
        with open(out_path, "rb") as f:
            st.download_button("⬇️ Scarica preventivo", f, file_name=out_name)
        do_rerun()


# --------------------------------------------------------------------------------------
# Clienti
# --------------------------------------------------------------------------------------
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("👥 Clienti")

    # Aggiungi nuovo cliente
    with st.expander("➕ Aggiungi nuovo cliente", expanded=False):
        colA, colB = st.columns(2)
        with colA:
            rag = st.text_input("Ragione Sociale *", key="new_rag")
            rif = st.text_input("Persona di riferimento", key="new_rif")
            ind = st.text_input("Indirizzo", key="new_ind")
            citta = st.text_input("Città", key="new_citta")
            cap = st.text_input("CAP", key="new_cap")
            tel = st.text_input("Telefono", key="new_tel")
            email = st.text_input("Email", key="new_email")
        with colB:
            piva = st.text_input("Partita IVA", key="new_piva")
            iban = st.text_input("IBAN", key="new_iban")
            sdi = st.text_input("SDI", key="new_sdi")
            ult_rec = st.text_input("Ultimo Recall (dd/mm/aaaa)", key="new_ultrec")
            pro_rec = st.text_input("Prossimo Recall (dd/mm/aaaa)", key="new_prorec")
            ult_vis = st.text_input("Ultima Visita (dd/mm/aaaa)", key="new_ultvis")
            pro_vis = st.text_input("Prossima Visita (dd/mm/aaaa)", key="new_provis")
        note_new = st.text_area("Note", key="new_note")

        if can_edit(role) and st.button("💾 Crea cliente"):
            if not rag.strip():
                st.error("Ragione Sociale obbligatoria.")
            else:
                cid = new_cliente_id(df_cli)
                row = {
                    "ClienteID": str(cid),
                    "RagioneSociale": rag, "PersonaRiferimento": rif, "Indirizzo": ind,
                    "Citta": citta, "CAP": cap, "Telefono": tel, "Email": email,
                    "PartitaIVA": piva, "IBAN": iban, "SDI": sdi,
                    "UltimoRecall": ult_rec, "ProssimoRecall": pro_rec,
                    "UltimaVisita": ult_vis, "ProssimaVisita": pro_vis,
                    "Note": note_new
                }
                upsert_cliente(df_cli, row)
                st.session_state["cliente_corrente_id"] = cid
                st.success(f"Cliente creato: {cid} — {rag}")
                do_rerun()

    # Selezione cliente e anagrafica
    cliente = select_cliente(df_cli, key="cli_select")
    if not cliente:
        return

    st.markdown("#### Anagrafica")
    colL, colR = st.columns(2)
    with colL:
        st.write(f"**Ragione Sociale**: {cliente['RagioneSociale']}")
        st.write(f"**Persona di riferimento**: {cliente.get('PersonaRiferimento','')}")
        st.write(f"**Indirizzo**: {cliente.get('Indirizzo','')}")
        st.write(f"**Città**: {cliente.get('Citta','')}  **CAP**: {cliente.get('CAP','')}")
        st.write(f"**Telefono**: {cliente.get('Telefono','')}")
        st.write(f"**Email**: {cliente.get('Email','')}")
        st.write(f"**Note**: {cliente.get('Note','')}")
    with colR:
        st.write(f"**P.IVA**: {cliente.get('PartitaIVA','')}")
        st.write(f"**IBAN**: {cliente.get('IBAN','')}")
        st.write(f"**SDI**: {cliente.get('SDI','')}")
        st.write(f"**Ultimo Recall**: {cliente.get('UltimoRecall','')}")
        st.write(f"**Prossimo Recall**: {cliente.get('ProssimoRecall','')}")
        st.write(f"**Ultima Visita**: {cliente.get('UltimaVisita','')}")
        st.write(f"**Prossima Visita**: {cliente.get('ProssimaVisita','')}")

    # Modifica/Elimina
    with st.expander("✏️ Modifica / 🗑️ Elimina cliente", expanded=False):
        df_cli_cols = _default_clienti().columns.tolist()
        edited = {}
        for c in df_cli_cols:
            edited[c] = st.text_input(c, value=str(cliente.get(c, "")), key=f"edit_{c}")

        c_left, c_right = st.columns(2)
        with c_left:
            if can_edit(role) and st.button("💾 Salva modifiche"):
                upsert_cliente(df_cli, edited)
                st.success("Cliente aggiornato.")
                do_rerun()
        with c_right:
            if can_edit(role) and st.button("🗑️ Elimina cliente"):
                upsert_cliente(df_cli, edited, delete=True)
                st.success("Cliente eliminato.")
                st.session_state.pop("cliente_corrente_id", None)
                do_rerun()

    st.markdown("---")
    if st.button("➡️ Vai alla gestione contratti di questo cliente"):
        st.session_state["cliente_corrente_id"] = int(cliente["ClienteID"])
        st.session_state["nav_page"] = "Contratti"
        do_rerun()

    # Preventivi
    df_prev = load_preventivi()
    preventivi_panel(cliente, role, df_prev)


# --------------------------------------------------------------------------------------
# Contratti
# --------------------------------------------------------------------------------------
def export_contratti_excel(df: pd.DataFrame, ragione: str) -> bytes:
    if df.empty:
        df = pd.DataFrame({"Info": ["Nessun contratto"]})
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Contratti")
    out.seek(0)
    return out.read()


def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("📑 Contratti (rosso = chiusi)")

    cliente = select_cliente(df_cli, key="cli_in_contratti")
    if not cliente:
        return

    cid = int(cliente["ClienteID"])
    ct_cli = df_ct.loc[df_ct["ClienteID"].astype(str) == str(cid)].copy()

    st.markdown("#### Elenco contratti")
    if ct_cli.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        df_show = ct_cli.copy()
        for c in ("NOL_FIN", "NOL_INT", "TotRata"):
            if c in df_show.columns:
                df_show[c] = df_show[c].apply(_fmt_eur)
        st.dataframe(
            df_show[
                ["NumeroContratto", "DataInizio", "DataFine", "Durata",
                 "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"]
            ],
            use_container_width=True
        )

    xls = export_contratti_excel(ct_cli, cliente["RagioneSociale"])
    st.download_button("⬇️ Esporta in Excel",
                       data=xls,
                       file_name=f"contratti_{cid}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    if not can_edit(role):
        st.warning("Solo Admin/Editor possono aggiungere o modificare contratti.")
        return

    st.markdown("---")
    st.markdown("#### ➕ Aggiungi / ✏️ Modifica / 🗑️ Elimina contratto")

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
            save_csv(df2, CONTRATTI_CSV)
            st.success("Contratto salvato.")
            do_rerun()
    with colY:
        if st.button("🗑️ Elimina (per NumeroContratto)"):
            df2 = df_ct.copy()
            mask = (df2["ClienteID"].astype(str) == str(cid)) & (df2["NumeroContratto"].astype(str) == numero)
            df2 = df2.loc[~mask].copy()
            save_csv(df2, CONTRATTI_CSV)
            st.success("Contratto eliminato (se esisteva).")
            do_rerun()


# --------------------------------------------------------------------------------------
# Navigazione
# --------------------------------------------------------------------------------------
PAGES = ["Clienti", "Contratti"]

def main():
    user, role = require_login()

    st.sidebar.title("📚 Navigazione")
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Clienti"
    page = st.sidebar.radio("Vai a:", PAGES, index=PAGES.index(st.session_state["nav_page"]))
    st.session_state["nav_page"] = page

    df_cli = load_clienti()
    df_ct = load_contratti()

    st.markdown(f"### {APP_TITLE}")

    if page == "Clienti":
        page_clienti(df_cli, df_ct, role)
    elif page == "Contratti":
        page_contratti(df_cli, df_ct, role)


if __name__ == "__main__":
    main()
