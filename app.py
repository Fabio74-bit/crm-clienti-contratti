# app_colorato.py — Gestionale Clienti SHT (versione aggiornata con colorazione contratti)
from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict

import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# ==========================
# CONFIG / COSTANTI
# ==========================
APP_TITLE = "GESTIONALE CLIENTI – SHT"

STORAGE_DIR = Path(
    st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage"))
)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV     = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV   = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV  = STORAGE_DIR / "preventivi.csv"
TEMPLATES_DIR   = STORAGE_DIR / "templates"

EXTERNAL_PROPOSALS_DIR = Path(
    st.secrets.get("storage", {}).get("proposals_dir") or (STORAGE_DIR / "preventivi")
)
EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

# 📂 Base URL OneDrive
ONEDRIVE_BASE_URL = "https://shtsrlit-my.sharepoint.com/personal/fabio_scaranello_shtsrl_com/Documents/OFFERTE"

CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]
PREVENTIVI_COLS = ["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"]

TEMPLATE_OPTIONS: Dict[str, str] = {
    "Offerta – Centralino": "Offerta_Centralino.docx",
    "Offerta – Varie": "Offerta_Varie.docx",
    "Offerta – A3": "Offerte_A3.docx",
    "Offerta – A4": "Offerte_A4.docx",
}

DURATE_MESI = ["12", "24", "36", "48", "60", "72"]

# ==========================
# UTILS
# ==========================
def as_date(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    if isinstance(x, (pd.Timestamp, pd.NaT.__class__)):
        return x
    s = str(x).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return pd.NaT
    d = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(d):
        d = pd.to_datetime(s, errors="coerce")
    return d

def to_date_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series([], dtype="datetime64[ns]")
    return s.map(as_date)

def fmt_date(d) -> str:
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%d/%m/%Y")

def money(x):
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        return f"{v:,.2f} €"
    except Exception:
        return ""

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def s(x) -> str:
    """Stringa sicura per Streamlit input (evita pd.NA / NaN)."""
    try:
        return "" if pd.isna(x) else str(x)
    except Exception:
        return "" if x is None else str(x)

def date_input_opt(label: str, current, *, key: str):
    d = as_date(current)
    try:
        if pd.isna(d):
            return st.date_input(label, key=key, format="DD/MM/YYYY")
        else:
            return st.date_input(label, value=d.to_pydatetime().date(), key=key, format="DD/MM/YYYY")
    except TypeError:
        if pd.isna(d):
            return st.date_input(label, key=key)
        else:
            return st.date_input(label, value=d.to_pydatetime().date(), key=key)

# ==========================
# I/O DATI
# ==========================
def load_clienti() -> pd.DataFrame:
    path = STORAGE_DIR / "clienti.csv"
    if not path.exists():
        st.warning("⚠️ File clienti.csv non trovato, esegui prima estrai_clienti_contratti.py")
        return pd.DataFrame(columns=CLIENTI_COLS + ["NoteCliente"])
    df = pd.read_csv(path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    if "NoteCliente" not in df.columns:
        df["NoteCliente"] = ""
    return df

def save_clienti(df: pd.DataFrame):
    path = STORAGE_DIR / "clienti.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")

def load_contratti() -> pd.DataFrame:
    path = STORAGE_DIR / "contratti_clienti.csv"
    if not path.exists():
        st.warning("⚠️ File contratti_clienti.csv non trovato, esegui prima estrai_clienti_contratti.py")
        return pd.DataFrame(columns=CONTRATTI_COLS)
    df = pd.read_csv(path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio", "DataFine"]:
        df[c] = to_date_series(df[c])
    return df

def save_contratti(df: pd.DataFrame):
    path = STORAGE_DIR / "contratti_clienti.csv"
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(path, index=False, encoding="utf-8-sig")


# ==========================
# FUNZIONI DI SUPPORTO PREVENTIVI
# ==========================
def _replace_docx_placeholders(doc: Document, mapping: dict):
    """Sostituisce segnaposto <<CHIAVE>> con i valori forniti nel dizionario."""
    for p in doc.paragraphs:
        for key, val in mapping.items():
            token = f"<<{key}>>"
            if token in p.text:
                inline = p.runs
                for i in range(len(inline)):
                    if token in inline[i].text:
                        inline[i].text = inline[i].text.replace(token, str(val))
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for key, val in mapping.items():
                        token = f"<<{key}>>"
                        if token in p.text:
                            inline = p.runs
                            for i in range(len(inline)):
                                if token in inline[i].text:
                                    inline[i].text = inline[i].text.replace(token, str(val))

def _gen_offerta_number(df_prev: pd.DataFrame, cliente_id: str, ragione_sociale: str) -> str:
    """Genera numero univoco per offerta, es. OFF-2025-CLIENTE-001"""
    year = datetime.now().year
    safe_name = "".join(ch if ch.isalnum() else "" for ch in str(ragione_sociale))[:8].upper()
    subset = df_prev[df_prev["ClienteID"].astype(str) == str(cliente_id)]
    seq = len(subset) + 1
    numero = f"OFF-{year}-{safe_name}-{seq:03d}"
    return numero
# ==========================
# AUTH
# ==========================
def do_login() -> Tuple[str, str]:
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")
    st.sidebar.subheader("Login")
    usr = st.sidebar.selectbox("Utente", list(users.keys()))
    pwd = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Entra", use_container_width=True):
        true_pwd = users[usr].get("password", "")
        role = users[usr].get("role", "viewer")
        if pwd == true_pwd:
            st.session_state["auth_user"] = usr
            st.session_state["auth_role"] = role
            st.rerun()
        else:
            st.sidebar.error("Password errata")
    if "auth_user" in st.session_state:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))
    return ("", "")

# ==========================
# DASHBOARD
# ==========================
# ==========================
# DASHBOARD
# ==========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    import pandas as pd
    from datetime import datetime, timedelta
    import streamlit as st

    st.markdown("<h1 style='text-align:center; color:#0A84FF;'>📊 Dashboard CRM</h1>", unsafe_allow_html=True)

    # === Sicurezza sui dati ===
    if df_ct is None or not isinstance(df_ct, pd.DataFrame) or df_ct.empty:
        st.warning("⚠️ Nessun dato contratti caricato.")
        return
    df_ct = df_ct.copy()

    # 🔗 Aggiunge nome cliente se manca
    if "RagioneSociale" not in df_ct.columns and "ClienteID" in df_ct.columns:
        df_ct = df_ct.merge(
            df_cli[["ClienteID", "RagioneSociale"]],
            on="ClienteID",
            how="left"
        )

    # --- Normalizza date e stato ---
    df_ct["DataInizio"] = pd.to_datetime(df_ct.get("DataInizio", pd.NaT), errors="coerce", dayfirst=True)
    df_ct["DataFine"] = pd.to_datetime(df_ct.get("DataFine", pd.NaT), errors="coerce", dayfirst=True)

    # ✅ Gestione colonna "stato" sicura
    if "stato" not in df_ct.columns:
        df_ct["stato"] = "Attivo"
    else:
        df_ct["stato"] = df_ct["stato"].fillna("Attivo")

    # === Calcoli principali ===
    clienti_attivi = df_cli["ClienteID"].nunique()
    contratti_attivi = df_ct[df_ct["stato"].str.lower() == "attivo"].shape[0]
    contratti_chiusi = df_ct[df_ct["stato"].str.lower() == "chiuso"].shape[0]
    anno_corrente = datetime.now().year
    contratti_nuovi = df_ct[df_ct["DataInizio"].dt.year == anno_corrente].shape[0]

    # === BOX METRICHE (stile moderno) ===
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"<div style='background:#007bff20;padding:20px;border-radius:12px;text-align:center;'><h3>👥 Clienti Attivi</h3><h2 style='color:#007bff'>{clienti_attivi}</h2></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='background:#28a74520;padding:20px;border-radius:12px;text-align:center;'><h3>📄 Contratti Attivi</h3><h2 style='color:#28a745'>{contratti_attivi}</h2></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div style='background:#dc354520;padding:20px;border-radius:12px;text-align:center;'><h3>🛑 Contratti Chiusi</h3><h2 style='color:#dc3545'>{contratti_chiusi}</h2></div>", unsafe_allow_html=True)
    with c4:
        st.markdown(f"<div style='background:#ffc10720;padding:20px;border-radius:12px;text-align:center;'><h3>🆕 Contratti Nuovi {anno_corrente}</h3><h2 style='color:#ff9800'>{contratti_nuovi}</h2></div>", unsafe_allow_html=True)

    st.divider()

    # === CONTRATTI IN SCADENZA (entro 60 giorni) ===
    oggi = datetime.now()
    prossimi_60 = oggi + timedelta(days=60)
    df_scadenza = df_ct[
        (df_ct["DataFine"].notna()) &
        (df_ct["DataFine"] >= oggi) &
        (df_ct["DataFine"] <= prossimi_60)
    ].sort_values("DataFine")

    st.markdown("### ⏳ Contratti in Scadenza (prossimi 60 giorni)")
    if df_scadenza.empty:
        st.info("✅ Nessun contratto in scadenza nei prossimi 60 giorni.")
    else:
        for i, r in df_scadenza.iterrows():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{r.get('RagioneSociale', 'N/D')}** — Scadenza: {r['DataFine'].strftime('%d/%m/%Y') if pd.notna(r['DataFine']) else 'N/A'}")
            with c2:
                if st.button("📂 Apri cliente", key=f"open_scad_{i}", use_container_width=True):
                    st.session_state["selected_cliente"] = r.get("RagioneSociale", "")
                    st.session_state["page"] = "Clienti"
                    st.rerun()

    st.divider()

    # === CONTRATTI SENZA DATA FINE ===
    st.markdown("### 📄 Promemoria: Contratti senza Data Fine")
    df_nofine = df_ct[df_ct["DataFine"].isna()]
    df_nofine = df_nofine[df_nofine["RagioneSociale"].fillna("") != "NuovoContratto"]

    if df_nofine.empty:
        st.info("✅ Tutti i contratti hanno una data di fine.")
    else:
        for _, r in df_nofine.iterrows():
            st.write(f"• **{r.get('RagioneSociale', 'N/D')}** — {str(r.get('Descrizione', '')).strip()[:60]}...")

    st.divider()



# ==========================
# CLIENTI
# ==========================
# === CLIENTI ===
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Clienti")

    # 🔄 Apertura diretta da Dashboard
    if "selected_cliente" in st.session_state and st.session_state["selected_cliente"]:
        cliente_da_aprire = st.session_state["selected_cliente"]
        st.session_state["selected_cliente"] = None  # resetta la selezione
        st.info(f"📂 Apertura cliente: **{cliente_da_aprire}**")
        search_query = cliente_da_aprire
    else:
        search_query = st.text_input("Cerca cliente per nome:")

    if not search_query:
        st.stop()

    # Filtraggio
    filtered = df_cli[df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)]
    if filtered.empty:
        st.warning("Nessun cliente trovato.")
        st.stop()

    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox("Seleziona Cliente", options, index=0)
    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]


    # === 🏢 Anagrafica principale ===
    st.markdown(f"### 🏢 {cliente.get('RagioneSociale', '')}")
    st.caption(f"ClienteID: {sel_id}")

    def safe_date_str(val):
        if not val or pd.isna(val):
            return ""
        try:
            return pd.to_datetime(val, dayfirst=True).strftime("%d/%m/%Y")
        except Exception:
            return str(val)

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Indirizzo:** {cliente.get('Indirizzo','')} — {cliente.get('Citta','')} {cliente.get('CAP','')}")
        st.write(f"**Telefono:** {cliente.get('Telefono','')}")
        st.write(f"**Email:** {cliente.get('Email','')}")
        st.write(f"**Partita IVA:** {cliente.get('PartitaIVA','')}")
        st.write(f"**IBAN:** {cliente.get('IBAN','')}")
    with col2:
        st.write(f"**Persona Riferimento 1:** {cliente.get('PersonaRiferimento','')}")
        st.write(f"**Persona Riferimento 2:** {cliente.get('PersonaRiferimento2','')}")
        st.write(f"**Cellulare:** {cliente.get('Cellulare','')}")
        st.write(f"**SDI:** {cliente.get('SDI','')}")
        st.write(f"**Ultimo Recall:** {safe_date_str(cliente.get('UltimoRecall',''))}")
        st.write(f"**Ultima Visita:** {safe_date_str(cliente.get('UltimaVisita',''))}")

    st.divider()

    # === 📅 Gestione Recall e Visite ===
    st.markdown("### 📅 Gestione Recall e Visite")

    from datetime import datetime, timedelta

    def parse_italian_date(value):
        if pd.isna(value) or value == "":
            return None
        try:
            return datetime.strptime(str(value), "%d/%m/%Y")
        except Exception:
            try:
                return pd.to_datetime(value, dayfirst=True)
            except Exception:
                return None

    def format_italian_date(date_val):
        return date_val.strftime("%d/%m/%Y") if pd.notna(date_val) and date_val else ""

    curr_ult_recall = parse_italian_date(cliente.get("UltimoRecall", ""))
    curr_ult_visita = parse_italian_date(cliente.get("UltimaVisita", ""))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        new_ult_recall = st.date_input(
            "Ultimo Recall",
            curr_ult_recall.date() if curr_ult_recall else None,
            format="DD/MM/YYYY",
            key=f"ur_{sel_id}"
        )
    with c3:
        new_ult_visita = st.date_input(
            "Ultima Visita",
            curr_ult_visita.date() if curr_ult_visita else None,
            format="DD/MM/YYYY",
            key=f"uv_{sel_id}"
        )

    next_recall = (pd.to_datetime(new_ult_recall) + timedelta(days=30)).date() if new_ult_recall else None
    next_visita = (pd.to_datetime(new_ult_visita) + timedelta(days=180)).date() if new_ult_visita else None

    with c2:
        st.date_input(
            "Prossimo Recall (auto)",
            value=next_recall,
            format="DD/MM/YYYY",
            key=f"pr_{sel_id}",
            disabled=True
        )
    with c4:
        st.date_input(
            "Prossima Visita (auto)",
            value=next_visita,
            format="DD/MM/YYYY",
            key=f"pv_{sel_id}",
            disabled=True
        )

    if st.button("💾 Aggiorna Recall/Visite"):
        try:
            idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
            df_cli.loc[idx_row, "UltimoRecall"] = format_italian_date(pd.to_datetime(new_ult_recall))
            df_cli.loc[idx_row, "UltimaVisita"] = format_italian_date(pd.to_datetime(new_ult_visita))
            df_cli.loc[idx_row, "ProssimoRecall"] = format_italian_date(pd.to_datetime(next_recall))
            df_cli.loc[idx_row, "ProssimaVisita"] = format_italian_date(pd.to_datetime(next_visita))
            save_clienti(df_cli)
            st.success("✅ Recall e Visite aggiornati con successo.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Errore durante aggiornamento Recall/Visite: {e}")

    st.divider()

    # === 🧾 Modifica Anagrafica ===
    st.markdown("### 🧾 Modifica Anagrafica")
    with st.expander("Modifica i dati anagrafici del cliente", expanded=False):
        with st.form("frm_anagrafica"):
            col1, col2, col3 = st.columns(3)
            with col1:
                rag = st.text_input("Ragione Sociale", cliente.get("RagioneSociale", ""))
                ref1 = st.text_input("Persona Riferimento 1", cliente.get("PersonaRiferimento", ""))
                ref2 = st.text_input("Persona Riferimento 2", cliente.get("PersonaRiferimento2", ""))
            with col2:
                indir = st.text_input("Indirizzo", cliente.get("Indirizzo", ""))
                citta = st.text_input("Città", cliente.get("Citta", ""))
                cap = st.text_input("CAP", cliente.get("CAP", ""))
                tel = st.text_input("Telefono", cliente.get("Telefono", ""))
            with col3:
                cell = st.text_input("Cellulare", cliente.get("Cellulare", ""))
                piva = st.text_input("Partita IVA", cliente.get("PartitaIVA", ""))
                sdi = st.text_input("SDI", cliente.get("SDI", ""))
                mail = st.text_input("Email", cliente.get("Email", ""))
                iban = st.text_input("IBAN", cliente.get("IBAN", ""))

            salva_btn = st.form_submit_button("💾 Salva Anagrafica")
            if salva_btn:
                err = False
                if cap and (not cap.isdigit() or len(cap) != 5):
                    st.error("❌ CAP non valido: deve contenere 5 cifre.")
                    err = True
                if piva and (not piva.isdigit() or len(piva) != 11):
                    st.error("❌ Partita IVA non valida: deve contenere 11 cifre.")
                    err = True
                if mail and "@" not in mail:
                    st.error("❌ Email non valida.")
                    err = True

                if not err:
                    idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                    df_cli.loc[idx_row, [
                        "RagioneSociale", "PersonaRiferimento", "PersonaRiferimento2",
                        "Indirizzo", "Citta", "CAP", "Telefono", "Cellulare",
                        "PartitaIVA", "Email", "SDI", "IBAN"
                    ]] = [rag, ref1, ref2, indir, citta, cap, tel, cell, piva, mail, sdi, iban]
                    save_clienti(df_cli)
                    st.success("✅ Anagrafica aggiornata con successo.")
                    st.rerun()

    st.divider()



    # === 📝 Note Cliente ===
    st.markdown("### 📝 Note Cliente")
    note_attuali = cliente.get("NoteCliente", "")
    nuove_note = st.text_area("Modifica note cliente:", note_attuali, height=180, key=f"note_{sel_id}")
    if st.button("💾 Salva Note"):
        idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx_row, "NoteCliente"] = nuove_note
        save_clienti(df_cli)
        st.success("✅ Note aggiornate.")
        st.rerun()

    st.divider()

        # === 🧾 CREAZIONE E GESTIONE PREVENTIVI ===
    st.markdown("### 🧾 Crea Nuovo Preventivo")

    from docx import Document
    import platform
    from docx.shared import Pt

    TEMPLATES_DIR = STORAGE_DIR / "templates"
    EXTERNAL_PROPOSALS_DIR = STORAGE_DIR / "preventivi"
    EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

    TEMPLATE_OPTIONS = {
        "Offerta A4": "Offerte_A4.docx",
        "Offerta A3": "Offerte_A3.docx",
        "Centralino": "Offerta_Centralino.docx",
        "Varie": "Offerta_Varie.docx",
    }

    prev_path = STORAGE_DIR / "preventivi.csv"
    if prev_path.exists():
        df_prev = pd.read_csv(prev_path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])

    def genera_numero_offerta(cliente_nome: str) -> str:
        anno = datetime.now().year
        nome_sicuro = "".join(c for c in cliente_nome if c.isalnum())[:6].upper()
        subset = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
        seq = len(subset) + 1
        return f"OFF-{anno}-{nome_sicuro}-{seq:03d}"

    next_num = genera_numero_offerta(cliente.get("RagioneSociale", ""))

    with st.form("frm_new_prev"):
        num = st.text_input("Numero Offerta", next_num)
        nome_file = st.text_input("Nome File (es. Offerta_ACME.docx)")
        template = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        submitted = st.form_submit_button("💾 Genera Preventivo")

        if submitted:
            try:
                template_path = TEMPLATES_DIR / TEMPLATE_OPTIONS[template]
                if not nome_file.strip():
                    nome_file = f"{num}.docx"
                if not nome_file.lower().endswith(".docx"):
                    nome_file += ".docx"

                output_path = EXTERNAL_PROPOSALS_DIR / nome_file

                if not template_path.exists():
                    st.error(f"❌ Template non trovato: {template_path}")
                else:
                    doc = Document(template_path)
                    mapping = {
                        "CLIENTE": cliente.get("RagioneSociale", ""),
                        "INDIRIZZO": cliente.get("Indirizzo", ""),
                        "CITTA": cliente.get("Citta", "") or cliente.get("Città", ""),
                        "NUMERO_OFFERTA": num,
                        "DATA": datetime.now().strftime("%d/%m/%Y"),
                    }

                    # --- sostituzione robusta anche per segnaposti spezzati ---
                    for p in doc.paragraphs:
                        full_text = "".join(run.text for run in p.runs)
                        modified = False

                        for key, val in mapping.items():
                            token = f"<<{key}>>"
                            if token in full_text:
                                full_text = full_text.replace(token, str(val))
                                modified = True

                        if modified:
                            # Cancella tutte le run precedenti
                            for run in p.runs:
                                run.text = ""
                            # Scrive il testo completo aggiornato
                            p.runs[0].text = full_text

                            # Applica stile uniforme
                            for run in p.runs:
                                run.font.size = Pt(9 if template == "Offerta A4" else 10)
                            p.alignment = 0

                    # --- Salvataggio ---
                    doc.save(output_path)
                    st.success(f"✅ Preventivo salvato: {output_path.name}")

                    # --- Aggiunta nel CSV ---
                    nuovo = {
                        "ClienteID": sel_id,
                        "NumeroOfferta": num,
                        "Template": TEMPLATE_OPTIONS[template],
                        "NomeFile": nome_file,
                        "Percorso": str(output_path),
                        "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([nuovo])], ignore_index=True)
                    df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")

                    st.toast("✅ Preventivo aggiunto al database", icon="📄")
                    st.rerun()

            except Exception as e:
                st.error(f"❌ Errore durante la creazione del preventivo: {e}")

    st.divider()


   
        # === 📂 Elenco Preventivi Cliente ===
    st.markdown("### 📂 Elenco Preventivi Cliente")

    prev_cli = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]

    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        import datetime

        def fmt_date(date_str):
            try:
                return pd.to_datetime(date_str, errors="coerce", dayfirst=True).strftime("%d/%m/%Y")
            except Exception:
                return date_str

        # Ordina i preventivi dal più recente
        prev_cli = prev_cli.sort_values(by="DataCreazione", ascending=False)

        st.markdown(
            """
            <style>
            .preventivo-card {
                border: 1px solid #ddd;
                border-radius: 10px;
                padding: 8px 14px;
                margin-bottom: 8px;
                background-color: #f9f9f9;
                box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            }
            .preventivo-header {
                font-weight: 600;
                color: #222;
            }
            .preventivo-info {
                font-size: 0.9rem;
                color: #444;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        for i, r in prev_cli.iterrows():
            file_path = Path(r["Percorso"])
            col1, col2, col3 = st.columns([0.5, 0.3, 0.2])

            with col1:
                st.markdown(
                    f"<div class='preventivo-card'>"
                    f"<div class='preventivo-header'>{r['NumeroOfferta']}</div>"
                    f"<div class='preventivo-info'>{r['Template']}</div>"
                    f"<div class='preventivo-info'>Creato il {fmt_date(r['DataCreazione'])}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

            with col2:
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "⬇️ Scarica",
                            data=f.read(),
                            file_name=file_path.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{r['NumeroOfferta']}",
                            use_container_width=True
                        )
                else:
                    st.error("❌ File mancante")

            with col3:
                if role == "admin":
                    elimina_key = f"del_{r['NumeroOfferta']}_{i}"
                    if st.button("🗑 Elimina", key=elimina_key, type="secondary", use_container_width=True):
                        try:
                            # Rimuove file locale
                            if file_path.exists():
                                file_path.unlink()
                            # Rimuove record dal CSV
                            df_prev = df_prev.drop(i)
                            df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")
                            st.success(f"🗑 Preventivo '{r['NumeroOfferta']}' eliminato con successo.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Errore durante eliminazione: {e}")

        st.divider()


# ==========================
# CONTRATTI
# ==========================
def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return
    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except: idx=0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"]
    rag_soc = df_cli[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0]["RagioneSociale"]

    # Nuovo contratto
    with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            with c1:
                num = st.text_input("Numero Contratto")
            with c2:
                din = st.date_input("Data inizio", format="DD/MM/YYYY")
            with c3:
                durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto", height=100)
            nol_fin, nol_int, tota = st.columns(3)
            with nol_fin: nf = st.text_input("NOL_FIN")
            with nol_int: ni = st.text_input("NOL_INT")
            with tota: tot = st.text_input("TotRata")
            if st.form_submit_button("💾 Crea contratto"):
                row = {
                    "ClienteID": str(sel_id),
                    "NumeroContratto": num,
                    "DataInizio": pd.to_datetime(din),
                    "DataFine": pd.to_datetime(din) + pd.DateOffset(months=int(durata)),
                    "Durata": durata,
                    "DescrizioneProdotto": desc,
                    "NOL_FIN": nf,
                    "NOL_INT": ni,
                    "TotRata": tot,
                    "Stato": "aperto"
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([row])], ignore_index=True)
                save_contratti(df_ct)
                st.success("✅ Contratto creato.")
                st.rerun()

    # ======== TABELLA CONTRATTI CON COLORI ========
    ct = df_ct[df_ct["ClienteID"].astype(str)==str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp["TotRata"] = disp["TotRata"].apply(money)
    disp = disp.drop(columns=["ClienteID"], errors="ignore")

    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True)
    js_code = JsCode("""
    function(params) {
        if (!params.data.Stato) return {};
        const stato = params.data.Stato.toLowerCase();

        if (stato === 'chiuso') {
            return { 'backgroundColor': '#ffcccc', 'color': '#800000', 'fontWeight': 'bold' };
        } else if (stato === 'attivo') {
            return { 'backgroundColor': '#d7f7d7', 'color': '#006600' };
        } else if (stato === 'nuovo') {
            return { 'backgroundColor': '#fffacd', 'color': '#8a6d00' };
        } else {
            return {};
        }
    }
    """)
    gb.configure_grid_options(getRowStyle=js_code)
    grid_opts = gb.build()
    grid_resp = AgGrid(disp, gridOptions=grid_opts, theme="balham", height=350,
                       update_mode=GridUpdateMode.SELECTION_CHANGED, allow_unsafe_jscode=True)

    selected = grid_resp.get("selected_rows", [])
    if isinstance(selected, list) and len(selected)>0:
        sel = selected[0]
        st.markdown("### 📝 Descrizione completa")
        st.info(sel.get("DescrizioneProdotto", ""), icon="🪶")
    # ======== GESTIONE STATO CONTRATTI ========
    st.divider()
    st.markdown("### ⚙️ Stato contratti")
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
        with c2: st.caption(f"{r['NumeroContratto']} — {r['DescrizioneProdotto'][:60]}")
        curr = (r["Stato"] or "aperto").lower()
        with c3:
            if curr == "chiuso":
                if st.button("🔓 Riapri", key=f"open_{i}"):
                    df_ct.loc[i, "Stato"] = "aperto"; save_contratti(df_ct); st.rerun()
            else:
                if st.button("❌ Chiudi", key=f"close_{i}"):
                    df_ct.loc[i, "Stato"] = "chiuso"; save_contratti(df_ct); st.rerun()

    # ======== ESPORTAZIONI ========
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        csv = disp.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📄 Esporta CSV", csv, f"contratti_{rag_soc}.csv", "text/csv")
    with c2:
        try:
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", size=9)
            pdf.cell(0, 8, safe_text(f"Contratti - {rag_soc}"), ln=1, align="C")
            for _, row in disp.iterrows():
                pdf.cell(35, 6, safe_text(row["NumeroContratto"]), 1)
                pdf.cell(25, 6, safe_text(row["DataInizio"]), 1)
                pdf.cell(25, 6, safe_text(row["DataFine"]), 1)
                pdf.cell(20, 6, safe_text(row["Durata"]), 1)
                pdf.cell(80, 6, safe_text(row["DescrizioneProdotto"])[:60], 1)
                pdf.cell(20, 6, safe_text(row["TotRata"]), 1)
                pdf.cell(20, 6, safe_text(row["Stato"]), 1)
                pdf.ln()
            pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
            st.download_button("📘 Esporta PDF", pdf_bytes,
                               f"contratti_{rag_soc}.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Errore PDF: {e}")

# ==========================
# MAIN APP
# ==========================
def main():
    st.set_page_config(page_title="SHT – Gestionale", layout="wide")
    st.markdown(f"<h3 style='margin-top:8px'>{APP_TITLE}</h3>", unsafe_allow_html=True)
    user, role = do_login()
    if user and role:
        st.sidebar.success(f"Utente: {user} — Ruolo: {role}")
    else:
        st.sidebar.info("Accesso come ospite")

    PAGES = {"Dashboard": page_dashboard, "Clienti": page_clienti, "Contratti": page_contratti}
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("Menu", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)
    df_cli = load_clienti()
    df_ct = load_contratti()
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
