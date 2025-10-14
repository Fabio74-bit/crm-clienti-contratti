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
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📊 Dashboard CRM")

    today = pd.Timestamp.now().normalize()

    # --- BOX KPI sintetici ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Clienti attivi", len(df_cli))
    with col2:
        st.metric("Contratti attivi", len(df_ct[df_ct["Stato"].str.lower() != "chiuso"]))
    with col3:
        scad = df_ct[
            (df_ct["DataFine"].notna())
            & (df_ct["DataFine"] >= today)
            & (df_ct["DataFine"] <= today + pd.DateOffset(months=6))
            & (df_ct["Stato"].str.lower() != "chiuso")
        ]
        st.metric("Contratti in scadenza (6 mesi)", len(scad))

    st.divider()

    # --- Prepara i contratti in scadenza ---
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    df_ct["Stato"] = df_ct["Stato"].fillna("Attivo")

    scad = df_ct[
        (df_ct["DataFine"].notna())
        & (df_ct["DataFine"] >= today)
        & (df_ct["DataFine"] <= today + pd.DateOffset(months=6))
        & (df_ct["Stato"].str.lower() != "chiuso")
    ]

    # --- BOX CONTRATTI IN SCADENZA ---
    st.subheader("📅 Contratti in Scadenza (entro 6 mesi)")
    if scad.empty:
        st.info("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        scad = scad.sort_values("DataFine").groupby("ClienteID").first().reset_index()
        scad = scad.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")

        desc_col = "DescrizioneProdotto" if "DescrizioneProdotto" in scad.columns else "Descrizione"
        scad_show = scad[["RagioneSociale", "NumeroContratto", "DataFine", desc_col]].copy()
        scad_show = scad_show.rename(columns={desc_col: "Descrizione"})

        scad_show["DataFine"] = scad_show["DataFine"].dt.strftime("%d/%m/%Y")
        scad_show["Descrizione"] = scad_show["Descrizione"].astype(str).str.slice(0, 50) + "..."
        st.dataframe(scad_show, use_container_width=True, hide_index=True)

    st.divider()

    # --- BOX PROMEMORIA CONTRATTI SENZA DATA FINE ---
    st.subheader("⏰ Promemoria: Contratti Senza Data Fine (da oggi in poi)")
    recenti = df_ct[
        (df_ct["DataInizio"].notna())
        & (df_ct["DataInizio"] >= today)
        & (df_ct["DataFine"].isna())
        & (df_ct["Stato"].str.lower() != "chiuso")
    ]
    if recenti.empty:
        st.info("✅ Nessun nuovo contratto senza data fine.")
    else:
        recenti = recenti.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        desc_col = "DescrizioneProdotto" if "DescrizioneProdotto" in recenti.columns else "Descrizione"
        recenti_show = recenti[["RagioneSociale", "NumeroContratto", "DataInizio", desc_col]].copy()
        recenti_show = recenti_show.rename(columns={desc_col: "Descrizione"})
        recenti_show["DataInizio"] = pd.to_datetime(recenti_show["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
        st.dataframe(recenti_show, use_container_width=True, hide_index=True)

    st.divider()

    # --- BOX ULTIMI RECALL E VISITE ---
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### 📞 Ultimi Recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecall"] = pd.to_datetime(cli["UltimoRecall"], errors="coerce", dayfirst=True)
        soglia = pd.Timestamp.today().normalize() - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall"].notna() & (cli["UltimoRecall"] <= soglia)]
        if not r.empty:
            r["UltimoRecall"] = r["UltimoRecall"].dt.strftime("%d/%m/%Y")
            r["ProssimoRecall"] = pd.to_datetime(r["ProssimoRecall"], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y")
            st.dataframe(r[["ClienteID", "RagioneSociale", "UltimoRecall", "ProssimoRecall"]],
                         hide_index=True, use_container_width=True)
        else:
            st.info("✅ Nessun recall oltre 3 mesi.")

    with c2:
        st.markdown("### 🧳 Ultime Visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisita"] = pd.to_datetime(cli["UltimaVisita"], errors="coerce", dayfirst=True)
        soglia_v = pd.Timestamp.today().normalize() - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita"].notna() & (cli["UltimaVisita"] <= soglia_v)]
        if not v.empty:
            v["UltimaVisita"] = v["UltimaVisita"].dt.strftime("%d/%m/%Y")
            v["ProssimaVisita"] = pd.to_datetime(v["ProssimaVisita"], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y")
            st.dataframe(v[["ClienteID", "RagioneSociale", "UltimaVisita", "ProssimaVisita"]],
                         hide_index=True, use_container_width=True)
        else:
            st.info("✅ Nessuna visita oltre 6 mesi.")

# ==========================
# CLIENTI
# ==========================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Clienti")

    # === Ricerca cliente ===
    if "search_query" not in st.session_state:
        st.session_state["search_query"] = ""

    def clear_search():
        st.session_state["search_query"] = ""

    search_query = st.text_input("🔍 Cerca cliente per nome:", st.session_state["search_query"], key="search_field")

    filtered = df_cli[df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)] if search_query else df_cli

    if filtered.empty:
        st.info("Nessun cliente trovato.")
        return

    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox("Seleziona Cliente", options, key="sel_cliente_box")
    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    # ✅ Svuota campo ricerca dopo selezione
    if search_query:
        clear_search()
        st.rerun()

    # === Anagrafica principale ===
    st.markdown(f"### 🏢 {cliente.get('RagioneSociale', '')}")
    st.caption(f"ClienteID: {sel_id}")

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Indirizzo:** {cliente.get('Indirizzo','')} — {cliente.get('Citta','')} {cliente.get('CAP','')}")
        st.write(f"**Telefono:** {cliente.get('Telefono','')}")
        st.write(f"**Email:** {cliente.get('Email','')}")
        st.write(f"**Partita IVA:** {cliente.get('PartitaIVA','')}")
        st.write(f"**IBAN:** {cliente.get('IBAN','')}")
    with col2:
        st.write(f"**Persona Riferimento:** {cliente.get('PersonaRiferimento','')}")
        st.write(f"**SDI:** {cliente.get('SDI','')}")
        st.write(f"**Ultimo Recall:** {cliente.get('UltimoRecall','')}")
        st.write(f"**Ultima Visita:** {cliente.get('UltimaVisita','')}")

    st.divider()

    # === Gestione Recall e Visite ===
    st.markdown("### 📅 Gestione Recall e Visite")
    c1, c2, c3, c4 = st.columns(4)
    curr_ult_recall = pd.to_datetime(cliente.get("UltimoRecall"), errors="coerce")
    curr_ult_visita = pd.to_datetime(cliente.get("UltimaVisita"), errors="coerce")

    with c1:
        new_ult_recall = st.date_input("Ultimo Recall", curr_ult_recall if not pd.isna(curr_ult_recall) else None, key=f"ur_{sel_id}")
    with c3:
        new_ult_visita = st.date_input("Ultima Visita", curr_ult_visita if not pd.isna(curr_ult_visita) else None, key=f"uv_{sel_id}")

    live_next_recall = pd.to_datetime(new_ult_recall) + pd.DateOffset(months=3) if new_ult_recall else pd.NaT
    live_next_visita = pd.to_datetime(new_ult_visita) + pd.DateOffset(months=6) if new_ult_visita else pd.NaT

    with c2:
        st.date_input("Prossimo Recall (auto)",
                      value=None if pd.isna(live_next_recall) else live_next_recall.date(),
                      key=f"pr_{sel_id}", disabled=True)
    with c4:
        st.date_input("Prossima Visita (auto)",
                      value=None if pd.isna(live_next_visita) else live_next_visita.date(),
                      key=f"pv_{sel_id}", disabled=True)

    if st.button("💾 Aggiorna Recall/Visite"):
        idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx_row, "UltimoRecall"] = pd.to_datetime(new_ult_recall) if new_ult_recall else ""
        df_cli.loc[idx_row, "UltimaVisita"] = pd.to_datetime(new_ult_visita) if new_ult_visita else ""
        df_cli.loc[idx_row, "ProssimoRecall"] = live_next_recall
        df_cli.loc[idx_row, "ProssimaVisita"] = live_next_visita
        save_clienti(df_cli)
        st.success("✅ Recall e Visite aggiornati automaticamente.")
        st.rerun()

    st.divider()

    # === Note Cliente ===
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
    st.divider()

    # === CREAZIONE E GESTIONE PREVENTIVI ===
    st.markdown("### 🧾 Crea Nuovo Preventivo")

    from docx import Document
    import webbrowser
    import platform

    # 📂 Percorsi fissi
    TEMPLATES_DIR = STORAGE_DIR / "templates"
    EXTERNAL_PROPOSALS_DIR = STORAGE_DIR / "preventivi"
    EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

    # 🧩 Template disponibili
    TEMPLATE_OPTIONS = {
        "Offerta A4": "Offerte_A4.docx",
        "Offerta A3": "Offerte_A3.docx",
        "Centralino": "Offerta_Centralino.docx",
        "Varie": "Offerta_Varie.docx",
    }

    # === Carica preventivi esistenti ===
    prev_path = STORAGE_DIR / "preventivi.csv"
    if prev_path.exists():
        df_prev = pd.read_csv(prev_path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])

    # === Genera automaticamente il numero offerta ===
    def genera_numero_offerta(cliente_nome: str) -> str:
        anno = datetime.now().year
        nome_sicuro = "".join(c for c in cliente_nome if c.isalnum())[:6].upper()
        subset = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
        seq = len(subset) + 1
        return f"OFF-{anno}-{nome_sicuro}-{seq:03d}"

    next_num = genera_numero_offerta(cliente.get("RagioneSociale", ""))

    # === Form di creazione nuovo preventivo ===
    with st.form("frm_new_prev"):
        num = st.text_input("Numero Offerta", next_num)
        nome_file = st.text_input("Nome File (es. Offerta_ACME.docx)")
        template = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        submitted = st.form_submit_button("💾 Genera Preventivo")

        if submitted:
            try:
                from docx.shared import Pt  # 👉 per gestire il testo Word

                template_path = TEMPLATES_DIR / TEMPLATE_OPTIONS[template]

                # 🔒 Controllo nome file
                if not nome_file.strip():
                    nome_file = f"{num}.docx"
                if not nome_file.lower().endswith(".docx"):
                    nome_file += ".docx"

                output_path = EXTERNAL_PROPOSALS_DIR / nome_file

                if not template_path.exists():
                    st.error(f"❌ Template non trovato: {template_path}")
                else:
                    # 🧩 Crea documento da template Word
                    doc = Document(template_path)
                    mapping = {
                        "CLIENTE": cliente.get("RagioneSociale", ""),
                        "INDIRIZZO": cliente.get("Indirizzo", ""),
                        # ✅ Gestione doppia chiave "Citta" / "Città"
                        "CITTA": cliente.get("Citta", "") or cliente.get("Città", ""),
                        "NUMERO_OFFERTA": num,
                        "DATA": datetime.now().strftime("%d/%m/%Y"),
                    }

                    # 🔄 Sostituzione segnaposto + adattamento testo
                    for p in doc.paragraphs:
                        for key, val in mapping.items():
                            token = f"<<{key}>>"
                            if token in p.text:
                                for run in p.runs:
                                    if token in run.text:
                                        run.text = run.text.replace(token, str(val))
                                        run.font.size = Pt(10)  # 🔠 testo più piccolo per nomi lunghi
                                        p.alignment = 0         # ↩️ allineamento sinistra

                    # 💾 Salvataggio in locale
                    doc.save(output_path)
                    st.success(f"✅ Preventivo salvato: {output_path.name}")

                    # 🔄 Aggiungi record nel CSV preventivi
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

    # === Elenco preventivi esistenti ===
    st.markdown("### 📂 Elenco Preventivi Cliente")
    prev_cli = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        for _, r in prev_cli.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([0.75, 0.25])
                with c1:
                    st.write(f"**{r['NumeroOfferta']}** — {r['Template']}")
                    st.caption(f"Creato il {r['DataCreazione']}")
                with c2:
                    file_path = Path(r["Percorso"])
                    if file_path.exists():
                        with open(file_path, "rb") as f:
                            st.download_button(
                                "⬇️ Scarica",
                                data=f.read(),
                                file_name=file_path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_{r['NumeroOfferta']}",
                            )
                    else:
                        st.error("File non trovato in locale.")

    # === Pulsante per aprire la cartella ===
    st.divider()
    if st.button("📂 Apri cartella Preventivi"):
        try:
            folder_path = str(EXTERNAL_PROPOSALS_DIR.resolve())
            system_name = platform.system()
            if system_name == "Darwin":  # macOS
                os.system(f'open "{folder_path}"')
            elif system_name == "Windows":
                os.startfile(folder_path)
            else:
                os.system(f'xdg-open "{folder_path}"')
        except Exception as e:
            st.error(f"❌ Impossibile aprire la cartella: {e}")


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
