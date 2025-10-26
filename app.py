# =====================================
# app.py — Gestionale Clienti SHT (VERSIONE 2025 OTTIMIZZATA)
# =====================================
from __future__ import annotations
import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from docx import Document
from docx.shared import Pt
from utils.data_io import *
from utils.formatting import *
from utils.auth import *
from utils.exports import *
from utils.fixes import *
from utils.pdf_builder import SHTPDF
from utils.dashboard import page_dashboard
from utils.dashboard_grafica import page_dashboard_grafica
from utils.lista_clienti import page_lista_clienti




# =====================================
# CONFIGURAZIONE STREAMLIT E STILE BASE
# =====================================
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

st.markdown("""
<style>
.block-container {
    max-width: 95% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
[data-testid="stAppViewContainer"] { background-color: #f7f8fa !important; }
[data-testid="stHeader"] { background: transparent !important; }
</style>
""", unsafe_allow_html=True)


# =====================================
# COSTANTI GLOBALI
# =====================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"
STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATES_DIR = Path("templates")
TEMPLATE_OPTIONS = {
    "Offerta A4": "Offerta_A4.docx",
    "Offerta A3": "Offerta_A3.docx",
    "Centralino": "Offerta_Centralino.docx",
    "Varie": "Offerta_Varie.docx",
}


DURATE_MESI = ["12", "24", "36", "48", "60", "72"]
# =====================================
# COLONNE STANDARD CSV
# =====================================
CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita",
    "TMK", "NoteCliente"
]


CONTRATTI_COLS = [
    "ClienteID", "RagioneSociale", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata",
    "CopieBN", "EccBN", "CopieCol", "EccCol", "Stato"
]
# =====================================
# FUNZIONI UTILITY
# =====================================
def fmt_date(d) -> str:
    """Ritorna una data in formato DD/MM/YYYY"""
    import datetime as dt
    if d in (None, "", "nan", "NaN"):
        return ""
    try:
        if isinstance(d, (dt.date, dt.datetime, pd.Timestamp)):
            return pd.to_datetime(d).strftime("%d/%m/%Y")
        parsed = pd.to_datetime(str(d), errors="coerce", dayfirst=True)
        return "" if pd.isna(parsed) else parsed.strftime("%d/%m/%Y")
    except Exception:
        return ""

def money(x):
    """Formatta numeri in valuta italiana"""
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        if pd.isna(v): return ""
        return f"{v:,.2f} €"
    except Exception:
        return ""

def safe_text(txt):
    """Rimuove caratteri non compatibili con PDF latin-1"""
    if pd.isna(txt) or txt is None: return ""
    s = str(txt)
    replacements = {"€": "EUR", "–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'"}
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]
def fix_inverted_dates(series: pd.Series, col_name: str = "") -> pd.Series:
    """
    Corregge automaticamente le date invertite (MM/DD/YYYY → DD/MM/YYYY)
    e mostra un log nel frontend Streamlit.
    """
    fixed = []
    fixed_count = 0
    total = len(series)

    for val in series:
        if pd.isna(val) or str(val).strip() == "":
            fixed.append("")
            continue

        s = str(val).strip()
        parsed = None

        try:
            # 1️⃣ Tentativo in formato italiano
            d1 = pd.to_datetime(s, dayfirst=True, errors="coerce")
            # 2️⃣ Tentativo in formato americano
            d2 = pd.to_datetime(s, dayfirst=False, errors="coerce")

            # Se entrambe valide e diverse → probabile inversione
            if not pd.isna(d1) and not pd.isna(d2) and d1 != d2:
                if d1.day <= 12 and d2.day > 12:
                    parsed = d2
                    fixed_count += 1
                else:
                    parsed = d1
            elif not pd.isna(d1):
                parsed = d1
            elif not pd.isna(d2):
                parsed = d2
            else:
                parsed = None
        except Exception:
            parsed = None

        if parsed is not None:
            fixed.append(parsed.strftime("%d/%m/%Y"))
        else:
            fixed.append("")

    # Mostra log su Streamlit (solo se ha corretto qualcosa)
    if fixed_count > 0:
        st.info(f"🔄 {fixed_count}/{total} date corrette automaticamente nella colonna **{col_name}**.")

    return pd.Series(fixed)

# =====================================
# CARICAMENTO E SALVATAGGIO DATI
# =====================================
def load_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(path, index=False, encoding="utf-8-sig")
    df = ensure_columns(df, cols)
    return df

def save_csv(df: pd.DataFrame, path: Path, date_cols=None):
    out = df.copy()
    if date_cols:
        for c in date_cols:
            out[c] = out[c].apply(fmt_date)
    out.to_csv(path, index=False, encoding="utf-8-sig")


def save_if_changed(df_new, path: Path, original_df):
    """Salva solo se i dati sono effettivamente cambiati."""
    import pandas as pd
    try:
        if not original_df.equals(df_new):
            df_new.to_csv(path, index=False, encoding='utf-8-sig')
            return True
        return False
    except Exception:
        df_new.to_csv(path, index=False, encoding='utf-8-sig')
        return True

# =====================================
# FUNZIONI DI SALVATAGGIO DEDICATE (con correzione automatica date)
# =====================================
def save_clienti(df: pd.DataFrame):
    """Salva il CSV clienti correggendo e formattando le date."""
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        if c in df.columns:
            df[c] = fix_inverted_dates(df[c], col_name=c)
    save_csv(df, CLIENTI_CSV, date_cols=["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"])


def save_contratti(df: pd.DataFrame):
    """Salva il CSV contratti correggendo e formattando le date."""
    for c in ["DataInizio", "DataFine"]:
        if c in df.columns:
            df[c] = fix_inverted_dates(df[c], col_name=c)
    save_csv(df, CONTRATTI_CSV, date_cols=["DataInizio", "DataFine"])

# =====================================
# CONVERSIONE SICURA DATE ITALIANE (VERSIONE DEFINITIVA 2025)
# =====================================
from datetime import datetime

def parse_date_safe(val: str) -> str:
    """Converte una data in formato coerente DD/MM/YYYY, accettando formati misti."""
    if not val or str(val).strip() in ["nan", "NaN", "None", "NaT", ""]:
        return ""
    val = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return val


def to_date_series(series: pd.Series) -> pd.Series:
    """Compatibilità retroattiva: applica parse_date_safe a una serie pandas."""
    return series.apply(parse_date_safe)


# =====================================
# CARICAMENTO CLIENTI (senza salvataggio automatico)
# =====================================
def load_clienti() -> pd.DataFrame:
    """Carica i dati dei clienti dal file CSV (solo lettura, coerente con date italiane)."""
    import pandas as pd

    if CLIENTI_CSV.exists():
        try:
            df = pd.read_csv(
                CLIENTI_CSV,
                dtype=str,
                sep=None,              # autodetect ; or ,
                engine="python",
                encoding="utf-8-sig",
                on_bad_lines="skip"
            )
        except Exception as e:
            st.error(f"❌ Errore durante la lettura dei clienti: {e}")
            df = pd.DataFrame(columns=CLIENTI_COLS)
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False, sep=";", encoding="utf-8-sig")

    # Normalizza valori vuoti o errati
    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
    )

    # Garantisce che tutte le colonne standard esistano
    df = ensure_columns(df, CLIENTI_COLS)

    # Conversione coerente delle date (senza salvarle)
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        if c in df.columns:
            df[c] = df[c].apply(parse_date_safe)

    return df


# =====================================
# CARICAMENTO CONTRATTI (senza salvataggio automatico)
# =====================================
def load_contratti() -> pd.DataFrame:
    """Carica i dati dei contratti dal file CSV (solo lettura, coerente con date italiane)."""
    import pandas as pd

    if CONTRATTI_CSV.exists():
        try:
            df = pd.read_csv(
                CONTRATTI_CSV,
                dtype=str,
                sep=None,
                engine="python",
                encoding="utf-8-sig",
                on_bad_lines="skip"
            )
        except Exception as e:
            st.error(f"❌ Errore durante la lettura dei contratti: {e}")
            df = pd.DataFrame(columns=CONTRATTI_COLS)
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
        df.to_csv(CONTRATTI_CSV, index=False, sep=";", encoding="utf-8-sig")

    # Pulisce valori testuali e garantisce colonne
    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
    )
    df = ensure_columns(df, CONTRATTI_COLS)

    # Conversione coerente delle date
    for c in ["DataInizio", "DataFine"]:
        if c in df.columns:
            df[c] = df[c].apply(parse_date_safe)

    return df


# =====================================
# FUNZIONI DI CARICAMENTO DATI (VERSIONE DEFINITIVA 2025)
# =====================================

def normalize_cliente_id(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizza la colonna ClienteID rimuovendo zeri iniziali e spazi."""
    if "ClienteID" not in df.columns:
        return df
    df["ClienteID"] = (
        df["ClienteID"]
        .astype(str)
        .str.strip()
        .str.replace(r"^0+", "", regex=True)
        .replace({"": None})
    )
    return df


def load_clienti() -> pd.DataFrame:
    """Carica i dati dei clienti dal file CSV (solo lettura, nessuna riscrittura automatica)."""
    import pandas as pd

    try:
        if CLIENTI_CSV.exists():
            df = pd.read_csv(
                CLIENTI_CSV,
                dtype=str,
                sep=None,              # autodetect ; or ,
                engine="python",
                encoding="utf-8-sig",
                on_bad_lines="skip"
            )
        else:
            df = pd.DataFrame(columns=CLIENTI_COLS)
    except Exception as e:
        st.error(f"❌ Errore durante la lettura dei clienti: {e}")
        df = pd.DataFrame(columns=CLIENTI_COLS)

    # Pulizia e normalizzazione
    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
    )
    df = ensure_columns(df, CLIENTI_COLS)
    df = normalize_cliente_id(df)

    # Conversione date coerente
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        if c in df.columns:
            df[c] = to_date_series(df[c])

    return df


def load_contratti() -> pd.DataFrame:
    """Carica i dati dei contratti dal file CSV (solo lettura, nessuna riscrittura automatica)."""
    import pandas as pd

    try:
        if CONTRATTI_CSV.exists():
            df = pd.read_csv(
                CONTRATTI_CSV,
                dtype=str,
                sep=None,              # autodetect ; or ,
                engine="python",
                encoding="utf-8-sig",
                on_bad_lines="skip"
            )
        else:
            df = pd.DataFrame(columns=CONTRATTI_COLS)
    except Exception as e:
        st.error(f"❌ Errore durante la lettura dei contratti: {e}")
        df = pd.DataFrame(columns=CONTRATTI_COLS)

    # Pulizia e normalizzazione
    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
    )
    df = ensure_columns(df, CONTRATTI_COLS)
    df = normalize_cliente_id(df)

    # Conversione date coerente
    for c in ["DataInizio", "DataFine"]:
        if c in df.columns:
            df[c] = to_date_series(df[c])

    return df



# =====================================
# KPI CARD (riutilizzata)
# =====================================
def kpi_card(label: str, value, icon: str, color: str) -> str:
    return f"""
    <div style="
        background-color:{color};
        padding:18px;
        border-radius:12px;
        text-align:center;
        color:white;">
        <div style="font-size:26px;">{icon}</div>
        <div style="font-size:22px;font-weight:700;">{value}</div>
        <div style="font-size:14px;">{label}</div>
    </div>
    """

# =====================================
# PAGINA CLIENTI — VERSIONE FINALE STABILE
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Gestione Clienti")

    # --- Permessi ---
    if role == "limited":
        st.warning("⚠️ Accesso in sola lettura per il tuo profilo.")
        st.stop()

    # --- Pre-selezione cliente ---
    if "selected_cliente" in st.session_state:
        sel_id = str(st.session_state.pop("selected_cliente"))
        cli_ids = df_cli["ClienteID"].astype(str)
        if sel_id in set(cli_ids):
            row = df_cli.loc[cli_ids == sel_id].iloc[0]
            st.session_state["cliente_selezionato"] = row["RagioneSociale"]

    # --- Ricerca cliente ---
    search_query = st.text_input("🔍 Cerca cliente per nome o ID", key="search_cli")
    if search_query:
        filtered = df_cli[
            df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)
            | df_cli["ClienteID"].astype(str).str.contains(search_query, na=False)
        ]
    else:
        filtered = df_cli.copy()

    if filtered.empty:
        st.warning("❌ Nessun cliente trovato.")
        return

    options = filtered["RagioneSociale"].tolist()
    selected_name = st.session_state.get("cliente_selezionato", options[0])
    sel_rag = st.selectbox(
        "Seleziona Cliente",
        options,
        index=options.index(selected_name),
        key="sel_cliente_box"
    )

    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    # --- Stile ---
    st.markdown("""
    <style>
    .btn-blue > button {
        background-color:#e3f2fd !important; color:#0d47a1 !important;
        border:none !important; border-radius:6px !important; font-weight:500 !important;
    }
    .btn-yellow > button {
        background-color:#fff8e1 !important; color:#ef6c00 !important;
        border:none !important; border-radius:6px !important; font-weight:500 !important;
    }
    .btn-red > button {
        background-color:#ffebee !important; color:#b71c1c !important;
        border:none !important; border-radius:6px !important; font-weight:500 !important;
    }
    .info-box {
        background:#fff; border-radius:12px; box-shadow:0 3px 10px rgba(0,0,0,0.06);
        padding:1.3rem 1.6rem; margin-top:0.8rem; margin-bottom:1.5rem;
        font-size:15px; line-height:1.7; border-left:5px solid #2563eb;
    }
    .info-title { color:#2563eb; font-size:17px; font-weight:600; margin-bottom:0.6rem; }
    .info-item { margin-bottom:0.3rem; }
    .info-label { font-weight:600; color:#0d1117; }
    </style>
    """, unsafe_allow_html=True)

    # --- Intestazione Cliente ---
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
        st.caption(f"ID Cliente: {sel_id}")

    with col2:
        # Vai ai contratti
        if st.button("📄 Vai ai Contratti", use_container_width=True, key=f"go_cont_{sel_id}"):
            st.session_state.update({
                "selected_cliente": sel_id,
                "nav_target": "Contratti",
                "_go_contratti_now": True
            })
            st.rerun()

        # Modifica anagrafica (NO rerun)
        if st.button("✏️ Modifica Anagrafica", use_container_width=True, key=f"edit_{sel_id}"):
            st.session_state[f"edit_cli_{sel_id}"] = not st.session_state.get(f"edit_cli_{sel_id}", False)

        # Cancella cliente
        if st.button("🗑️ Cancella Cliente", use_container_width=True, key=f"ask_del_{sel_id}"):
            st.session_state["confirm_delete_cliente"] = str(sel_id)
            st.rerun()

    # --- INFO RAPIDE ---
    infoA, infoB = st.columns(2)
    with infoA:
        st.markdown(f"""
        <div class="info-box">
            <div class="info-title">📇 Dati Principali</div>
            <div class="info-item"><span class="info-label">👤 Referente:</span> {cliente.get('PersonaRiferimento','')}</div>
            <div class="info-item"><span class="info-label">✉️ Email:</span> {cliente.get('Email','')}</div>
            <div class="info-item"><span class="info-label">👩‍💼 TMK:</span> {cliente.get('TMK','')}</div>
            <div class="info-item"><span class="info-label">📞 Telefono:</span> {cliente.get('Telefono','')} — <span class="info-label">📱 Cell:</span> {cliente.get('Cell','')}</div>
        </div>
        """, unsafe_allow_html=True)
    with infoB:
        st.markdown(f"""
        <div class="info-box">
            <div class="info-title">📍 Indirizzo e Dati Fiscali</div>
            <div class="info-item"><span class="info-label">📍 Indirizzo:</span> {cliente.get('Indirizzo','')} — {cliente.get('Citta','')} {cliente.get('CAP','')}</div>
            <div class="info-item"><span class="info-label">💼 Partita IVA:</span> {cliente.get('PartitaIVA','')}</div>
            <div class="info-item"><span class="info-label">🏦 IBAN:</span> {cliente.get('IBAN','')}</div>
            <div class="info-item"><span class="info-label">📡 SDI:</span> {cliente.get('SDI','')}</div>
        </div>
        """, unsafe_allow_html=True)

    # --- MODIFICA ANAGRAFICA ---
    if st.session_state.get(f"edit_cli_{sel_id}", False):
        st.divider()
        st.markdown("### ✏️ Modifica Anagrafica Cliente")

        with st.form(f"frm_anagrafica_{sel_id}"):
            col1, col2 = st.columns(2)
            with col1:
                indirizzo = st.text_input("📍 Indirizzo", cliente.get("Indirizzo", ""))
                citta = st.text_input("🏙️ Città", cliente.get("Citta", ""))
                cap = st.text_input("📮 CAP", cliente.get("CAP", ""))
                telefono = st.text_input("📞 Telefono", cliente.get("Telefono", ""))
                cell = st.text_input("📱 Cellulare", cliente.get("Cell", ""))
                email = st.text_input("✉️ Email", cliente.get("Email", ""))
            with col2:
                persona = st.text_input("👤 Persona Riferimento", cliente.get("PersonaRiferimento", ""))
                piva = st.text_input("💼 Partita IVA", cliente.get("PartitaIVA", ""))
                iban = st.text_input("🏦 IBAN", cliente.get("IBAN", ""))
                sdi = st.text_input("📡 SDI", cliente.get("SDI", ""))
                tmk = st.selectbox(
                    "👩‍💼 TMK di riferimento",
                    ["", "Giulia", "Antonella", "Annalisa", "Laura"],
                    index=["", "Giulia", "Antonella", "Annalisa", "Laura"].index(cliente.get("TMK", "")) if cliente.get("TMK", "") in ["Giulia", "Antonella", "Annalisa", "Laura"] else 0
                )

            salva = st.form_submit_button("💾 Salva Modifiche")
            if salva:
                idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx, [
                    "Indirizzo", "Citta", "CAP", "Telefono", "Cell", "Email",
                    "PersonaRiferimento", "PartitaIVA", "IBAN", "SDI", "TMK"
                ]] = [indirizzo, citta, cap, telefono, cell, email, persona, piva, iban, sdi, tmk]
                save_clienti(df_cli)
                st.success("✅ Anagrafica aggiornata.")
                st.session_state[f"edit_cli_{sel_id}"] = False
                st.rerun()

        # --- NOTE CLIENTE ---
        st.divider()
        st.markdown("### 📝 Note Cliente")
        note_attuali = cliente.get("NoteCliente", "")
        nuove_note = st.text_area("Modifica note cliente:", note_attuali, height=160, key=f"note_{sel_id}")

        if st.button("💾 Salva Note Cliente", key=f"save_note_{sel_id}", use_container_width=True):
            try:
                idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx_row, "NoteCliente"] = nuove_note
                save_clienti(df_cli)
                st.success("✅ Note aggiornate correttamente!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante il salvataggio delle note: {e}")



# =====================================
# 📑 PAGINA CONTRATTI — LAYOUT ORIGINALE + FIX PULSANTI + RIGA ROSSA CHIUSI
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📄 Gestione Contratti")

    # === Recupera cliente selezionato ===
    if "selected_cliente" not in st.session_state:
        st.warning("🔍 Seleziona prima un cliente dalla pagina Clienti.")
        return

    sel_id = str(st.session_state["selected_cliente"])
    cli = df_cli[df_cli["ClienteID"].astype(str) == sel_id]
    if cli.empty:
        st.warning("❌ Cliente non trovato.")
        return

    cliente = cli.iloc[0]
    rag_soc = cliente["RagioneSociale"]

    # === Header Cliente ===
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"## 🏢 {rag_soc}")
        st.caption(f"ID Cliente: {sel_id}")
    with col2:
        if st.button("↩️ Torna ai Clienti", use_container_width=True):
            st.session_state.update({"nav_target": "Clienti"})
            st.rerun()

    st.markdown("---")

    # === Filtra contratti cliente ===
    contratti = df_ct[df_ct["ClienteID"].astype(str) == sel_id]
    if contratti.empty:
        st.info("📭 Nessun contratto registrato per questo cliente.")
    else:
        contratti = contratti.sort_values("DataInizio", ascending=False)
        st.markdown("### 📋 Elenco Contratti")

        for idx, r in contratti.iterrows():
            stato = str(r.get("Stato", "aperto")).lower()
            # 🔹 Colori dinamici
            bg_color = "#ffffff" if stato == "aperto" else "#ffe5e5"
            border_color = "#2196f3" if stato == "aperto" else "#b71c1c"

            st.markdown(f"""
            <div style="background:{bg_color};padding:12px 16px;margin-bottom:10px;
                        border-left:5px solid {border_color};border-radius:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <b>📄 N°</b> {r.get("NumeroContratto","—")} &nbsp;&nbsp;
                        <b>🗓️ Inizio:</b> {r.get("DataInizio","—")} &nbsp;&nbsp;
                        <b>🏁 Fine:</b> {r.get("DataFine","—")} &nbsp;&nbsp;
                        <b>💰 Tot. Rata:</b> {r.get("TotRata","—")} &nbsp;&nbsp;
                        <b>📄 Stato:</b> {"✅ Aperto" if stato=="aperto" else "❌ Chiuso"}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns([0.1, 0.1])
            with c1:
                if st.button("✏️ Modifica", key=f"edit_{idx}", use_container_width=True):
                    st.session_state["edit_contract_id"] = idx
                    st.session_state["editing_contract"] = True
                    st.rerun()
            with c2:
                if stato != "chiuso" and st.button("❌ Chiudi Contratto", key=f"close_{idx}", use_container_width=True):
                    try:
                        df_ct.loc[idx, "Stato"] = "chiuso"
                        save_contratti(df_ct)
                        st.session_state["highlight_closed"] = idx
                        st.success(f"✅ Contratto {r.get('NumeroContratto','')} chiuso con successo.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Errore durante la chiusura: {e}")

    # === MODIFICA CONTRATTO ===
    if st.session_state.get("editing_contract"):
        idx = st.session_state.get("edit_contract_id")
        if idx in df_ct.index:
            c = df_ct.loc[idx]
            st.divider()
            st.markdown("### ✏️ Modifica Contratto")
            with st.form(f"frm_edit_{idx}"):
                col1, col2, col3 = st.columns(3)
                numero = col1.text_input("📄 Numero Contratto", c.get("NumeroContratto", ""))
                data_inizio = col2.date_input(
                    "📅 Data Inizio",
                    pd.to_datetime(c.get("DataInizio"), errors="coerce"),
                    format="DD/MM/YYYY"
                )
                data_fine = col3.date_input(
                    "🏁 Data Fine",
                    pd.to_datetime(c.get("DataFine"), errors="coerce"),
                    format="DD/MM/YYYY"
                )

                descrizione = st.text_area("🧾 Descrizione Prodotto", c.get("DescrizioneProdotto", ""), height=80)
                tot_rata = st.text_input("💰 Tot. Rata", c.get("TotRata", ""))
                stato = st.selectbox(
                    "📄 Stato", ["aperto", "chiuso"],
                    index=0 if c.get("Stato", "aperto") == "aperto" else 1
                )

                colb1, colb2 = st.columns([0.2, 0.2])
                salva = colb1.form_submit_button("💾 Salva Modifiche")
                annulla = colb2.form_submit_button("❌ Annulla")

                if salva:
                    try:
                        df_ct.loc[idx, [
                            "NumeroContratto", "DataInizio", "DataFine",
                            "DescrizioneProdotto", "TotRata", "Stato"
                        ]] = [
                            numero, fmt_date(data_inizio), fmt_date(data_fine),
                            descrizione, tot_rata, stato
                        ]
                        save_contratti(df_ct)
                        st.success("✅ Modifiche salvate correttamente.")
                        st.session_state["editing_contract"] = False
                        st.session_state["edit_contract_id"] = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Errore durante il salvataggio: {e}")

                if annulla:
                    st.session_state["editing_contract"] = False
                    st.session_state["edit_contract_id"] = None
                    st.rerun()

    # === CREAZIONE NUOVO CONTRATTO ===
    st.divider()
    st.markdown("### ➕ Crea Nuovo Contratto")
    with st.form("frm_nuovo_contratto"):
        col1, col2, col3 = st.columns(3)
        numero = col1.text_input("📄 Numero Contratto")
        data_inizio = col2.date_input("📅 Data Inizio", format="DD/MM/YYYY")
        durata = col3.selectbox("📆 Durata (mesi)", [12, 24, 36, 48, 60], index=2)
        descrizione = st.text_area("🧾 Descrizione Prodotto", height=80)
        tot = st.text_input("💰 Tot. Rata")

        salva = st.form_submit_button("💾 Crea Contratto")
        if salva:
            try:
                fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))
                nuovo = {
                    "ClienteID": sel_id,
                    "RagioneSociale": rag_soc,
                    "NumeroContratto": numero,
                    "DataInizio": fmt_date(data_inizio),
                    "DataFine": fmt_date(fine),
                    "DescrizioneProdotto": descrizione,
                    "TotRata": tot,
                    "Durata": durata,
                    "Stato": "aperto"
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([nuovo])], ignore_index=True)
                save_contratti(df_ct)
                st.success("✅ Nuovo contratto creato correttamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante la creazione del contratto: {e}")




# =====================================
# FUNZIONE MODALE MODIFICA CONTRATTO
# =====================================
def show_contract_modal(contratto, df_ct, df_cli, rag_soc):
    """Mostra la finestra di modifica al centro schermo"""
    st.markdown("""
    <style>
    .modal-bg {
        position: fixed; top:0; left:0; width:100%; height:100%;
        background: rgba(0,0,0,0.4); z-index: 9998;
        display: flex; align-items: center; justify-content: center;
    }
    .modal-box {
        background: white; border-radius: 12px; width: 620px;
        padding: 1.8rem 2rem; box-shadow: 0 4px 18px rgba(0,0,0,0.25);
    }
    </style>
    <div class="modal-bg"><div class="modal-box">
    """, unsafe_allow_html=True)

    st.markdown(f"### ✏️ Modifica Contratto {contratto.get('NumeroContratto','')}")
    with st.form("frm_edit_contract"):
        col1, col2 = st.columns(2)
        with col1:
            num = st.text_input("Numero Contratto", contratto.get("NumeroContratto",""), disabled=True)
            din = st.date_input("Data Inizio", value=pd.to_datetime(contratto.get("DataInizio"), dayfirst=True, errors="coerce"))
            durata = st.text_input("Durata (mesi)", contratto.get("Durata",""))
            stato = st.selectbox("Stato", ["aperto", "chiuso"], index=0 if contratto.get("Stato","")!="chiuso" else 1)
        with col2:
            nf = st.text_input("NOL_FIN", contratto.get("NOL_FIN",""))
            ni = st.text_input("NOL_INT", contratto.get("NOL_INT",""))
            tot = st.text_input("Tot Rata", contratto.get("TotRata",""))
        desc = st.text_area("Descrizione Prodotto", contratto.get("DescrizioneProdotto",""), height=100)
        colA, colB, colC, colD = st.columns(4)
        copie_bn = colA.text_input("Copie B/N", contratto.get("CopieBN",""))
        ecc_bn   = colB.text_input("Extra B/N (€)", contratto.get("EccBN",""))
        copie_col= colC.text_input("Copie Colore", contratto.get("CopieCol",""))
        ecc_col  = colD.text_input("Extra Colore (€)", contratto.get("EccCol",""))

        salva = st.form_submit_button("💾 Salva modifiche", use_container_width=True)
        annulla = st.form_submit_button("❌ Annulla", use_container_width=True)

        if salva:
            try:
                idx = df_ct.index[df_ct["NumeroContratto"] == num][0]
                df_ct.loc[idx, [
                    "DataInizio","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT",
                    "TotRata","CopieBN","EccBN","CopieCol","EccCol","Stato"
                ]] = [
                    fmt_date(din), durata, desc, nf, ni, tot, copie_bn, ecc_bn, copie_col, ecc_col, stato
                ]
                save_contratti(df_ct)
                st.success("✅ Contratto aggiornato con successo.")
                time.sleep(0.6)
                st.experimental_set_query_params()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante il salvataggio: {e}")

        if annulla:
            st.experimental_set_query_params()
            st.rerun()

    st.markdown("</div></div>", unsafe_allow_html=True)

# =====================================
# PAGINA RECALL E VISITE (aggiornata e coerente)
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📅 Gestione Recall e Visite</h2>", unsafe_allow_html=True)
    st.divider()

    col1, col2 = st.columns(2)
    filtro_nome = col1.text_input("🔍 Cerca per nome cliente")
    filtro_citta = col2.text_input("🏙️ Cerca per città")

    df = df_cli.copy()
    if filtro_nome:
        df = df[df["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        df = df[df["Citta"].str.contains(filtro_citta, case=False, na=False)]
    if df.empty:
        st.warning("❌ Nessun cliente trovato.")
        return

    oggi = pd.Timestamp.now().normalize()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

    # === Imminenti (entro 30 giorni) ===
    st.markdown("### 🔔 Recall e Visite imminenti (entro 30 giorni)")
    imminenti = df[
        (df["ProssimoRecall"].between(oggi, oggi + pd.DateOffset(days=30))) |
        (df["ProssimaVisita"].between(oggi, oggi + pd.DateOffset(days=30)))
    ]

    if imminenti.empty:
        st.success("✅ Nessun richiamo o visita imminente.")
    else:
        for i, r in imminenti.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1, 1, 0.7])
            c1.markdown(f"**{r['RagioneSociale']}**")
            c2.markdown(fmt_date(r["ProssimoRecall"]))
            c3.markdown(fmt_date(r["ProssimaVisita"]))
            if c4.button("📂 Apri", key=f"imm_{i}", use_container_width=True):
                st.session_state.update({
                    "selected_cliente": r["ClienteID"],
                    "nav_target": "Clienti",
                    "_go_clienti_now": True
                })
                st.rerun()

    st.divider()

    # === Recall e visite in ritardo ===
    st.markdown("### ⚠️ Recall e Visite scaduti")
    recall_vecchi = df[
        df["UltimoRecall"].notna() & (df["UltimoRecall"] < oggi - pd.DateOffset(months=3))
    ]
    visite_vecchie = df[
        df["UltimaVisita"].notna() & (df["UltimaVisita"] < oggi - pd.DateOffset(months=6))
    ]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📞 Recall > 3 mesi fa")
        if recall_vecchi.empty:
            st.info("✅ Nessun recall scaduto.")
        else:
            for i, r in recall_vecchi.iterrows():
                c1, c2, c3 = st.columns([2.5, 1.2, 0.8])
                c1.markdown(f"**{r['RagioneSociale']}**")
                c2.markdown(fmt_date(r["UltimoRecall"]))
                if c3.button("📂 Apri", key=f"rec_{i}", use_container_width=True):
                    st.session_state.update({
                        "selected_cliente": r["ClienteID"],
                        "nav_target": "Clienti",
                        "_go_clienti_now": True
                    })
                    st.rerun()

    with col2:
        st.markdown("#### 👣 Visite > 6 mesi fa")
        if visite_vecchie.empty:
            st.info("✅ Nessuna visita scaduta.")
        else:
            for i, r in visite_vecchie.iterrows():
                c1, c2, c3 = st.columns([2.5, 1.2, 0.8])
                c1.markdown(f"**{r['RagioneSociale']}**")
                c2.markdown(fmt_date(r["UltimaVisita"]))
                if c3.button("📂 Apri", key=f"vis_{i}", use_container_width=True):
                    st.session_state.update({
                        "selected_cliente": r["ClienteID"],
                        "nav_target": "Clienti",
                        "_go_clienti_now": True
                    })
                    st.rerun()

    st.divider()
    st.markdown("### 🧾 Storico Recall e Visite")
    tabella = df[["RagioneSociale", "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]].copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        tabella[c] = tabella[c].apply(fmt_date)
    st.dataframe(tabella, use_container_width=True, hide_index=True)

# =====================================
# FIX DATE: ESEGUILO UNA SOLA VOLTA
# =====================================
def fix_dates_once(df_cli: pd.DataFrame, df_ct: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Corregge le date solo una volta per sessione.
    NON usa variabili globali, evita NameError.
    Ritorna SEMPRE (df_cli, df_ct) aggiornati.
    """
    if st.session_state.get("_date_fix_done", False):
        return df_cli, df_ct

    try:
        # Clienti
        if not df_cli.empty:
            for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
                if c in df_cli.columns:
                    df_cli[c] = fix_inverted_dates(df_cli[c], col_name=c)

        # Contratti
        if not df_ct.empty:
            for c in ["DataInizio", "DataFine"]:
                if c in df_ct.columns:
                    df_ct[c] = fix_inverted_dates(df_ct[c], col_name=c)

        # Salva una sola volta
        df_cli.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
        df_ct.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

        st.toast("🔄 Date corrette e salvate nei CSV.", icon="✅")
        st.session_state["_date_fix_done"] = True
    except Exception as e:
        st.warning(f"⚠️ Correzione automatica date non completata: {e}")

    return df_cli, df_ct


# =====================================
# MAIN APP — versione definitiva 2025 con filtro visibilità e loader sicuro
# =====================================
def main():
    # --- FIX LAYOUT E STILE ---
    st.markdown("""
    <style>
    .block-container {
        max-width: 95% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    [data-testid="stAppViewContainer"] {
        background-color: #f8fafc;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: scale(1.02);
    }
    div[data-testid="stHorizontalBlock"] > div {
        overflow-x: auto !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- LOGIN ---
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    # --- Percorsi base ---
    global CLIENTI_CSV, CONTRATTI_CSV
    base_clienti = STORAGE_DIR / "clienti.csv"
    base_contratti = STORAGE_DIR / "contratti_clienti.csv"
    gabriele_clienti = STORAGE_DIR / "gabriele" / "clienti.csv"
    gabriele_contratti = STORAGE_DIR / "gabriele" / "contratti_clienti.csv"

    # --- Ruolo e diritti ---
    if user == "fabio":
        ruolo_scrittura = "full"
    elif user in ["emanuela", "claudia"]:
        ruolo_scrittura = "full"
    elif user in ["giulia", "antonella", "gabriele", "laura", "annalisa"]:
        ruolo_scrittura = "limitato"
    else:
        ruolo_scrittura = "limitato"

    # --- Selettore visibilità (solo per Fabio, Giulia, Antonella) ---
    if user in ["fabio", "giulia", "antonella"]:
        visibilita_scelta = st.sidebar.radio(
            "📂 Visualizza clienti di:",
            ["Miei", "Gabriele", "Tutti"],
            index=0
        )
    else:
        visibilita_scelta = "Miei"

    # --- Caricamento CSV base ---
    df_cli_main, df_ct_main = load_clienti(), load_contratti()

    # --- Caricamento CSV Gabriele (robusto) ---
    try:
        if gabriele_clienti.exists():
            df_cli_gab = pd.read_csv(gabriele_clienti, dtype=str, sep=None,
                                     engine="python", encoding="utf-8-sig",
                                     on_bad_lines="skip").fillna("")
        else:
            df_cli_gab = pd.DataFrame(columns=CLIENTI_COLS)

        if gabriele_contratti.exists():
            df_ct_gab = pd.read_csv(gabriele_contratti, dtype=str, sep=None,
                                    engine="python", encoding="utf-8-sig",
                                    on_bad_lines="skip").fillna("")
        else:
            df_ct_gab = pd.DataFrame(columns=CONTRATTI_COLS)
    except Exception as e:
        st.warning(f"⚠️ Impossibile caricare i dati di Gabriele: {e}")
        df_cli_gab = pd.DataFrame(columns=CLIENTI_COLS)
        df_ct_gab = pd.DataFrame(columns=CONTRATTI_COLS)

    # --- Applica filtro scelto ---
    if visibilita_scelta == "Miei":
        df_cli, df_ct = df_cli_main, df_ct_main
    elif visibilita_scelta == "Gabriele":
        df_cli, df_ct = df_cli_gab, df_ct_gab
    else:
        df_cli = pd.concat([df_cli_main, df_cli_gab], ignore_index=True)
        df_ct = pd.concat([df_ct_main, df_ct_gab], ignore_index=True)

    # --- Correzione date una sola volta ---
    if not st.session_state.get("_date_fix_done", False):
        try:
            for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
                if c in df_cli.columns:
                    df_cli[c] = fix_inverted_dates(df_cli[c], col_name=c)
            for c in ["DataInizio", "DataFine"]:
                if c in df_ct.columns:
                    df_ct[c] = fix_inverted_dates(df_ct[c], col_name=c)
            st.session_state["_date_fix_done"] = True
        except Exception as e:
            st.warning(f"⚠️ Correzione automatica date non completata: {e}")

    # --- Sidebar info ---
    st.sidebar.success(f"👤 {user} — Ruolo: {role}")
    st.sidebar.info(f"📂 Vista: {visibilita_scelta}")

    # --- Stato globale per navigazione ---
    if "nav_target" not in st.session_state:
        st.session_state["nav_target"] = None
    if "selected_cliente" not in st.session_state:
        st.session_state["selected_cliente"] = None
    if "_go_contratti_now" not in st.session_state:
        st.session_state["_go_contratti_now"] = False

    st.session_state["ruolo_scrittura"] = ruolo_scrittura
    st.session_state["visibilita"] = visibilita_scelta

    # --- Pagine ---
    PAGES = {
        "📋 Dashboard": page_dashboard,
        "📊 Dashboard Grafica": page_dashboard_grafica,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti,
    }

    # --- Menu principale ---
    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()), index=0)

    # --- Navigazione automatica da pulsanti interni ---
    if "_go_contratti_now" in st.session_state and st.session_state["_go_contratti_now"]:
        page = "Contratti"
        st.session_state["_go_contratti_now"] = False
    elif "nav_target" in st.session_state and st.session_state["nav_target"]:
        target = st.session_state.pop("nav_target")
        if target in PAGES:
            page = target

    # --- Esegui pagina ---
    if page in PAGES:
        PAGES[page](df_cli, df_ct, ruolo_scrittura)

# --- Fix layout globale dopo caricamento pagina ---
st.markdown("""
<style>
.block-container {
    max-width: 90% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
[data-testid="stSidebarNav"] {
    padding-top: 1rem;
}
[data-testid="stAppViewContainer"] {
    background-color: #f8fafc;
}
</style>
""", unsafe_allow_html=True)

# =====================================
# AVVIO APPLICAZIONE
# =====================================
if __name__ == "__main__":
    main()
