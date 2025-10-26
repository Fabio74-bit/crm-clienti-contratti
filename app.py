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
# =====================================
# PAGINA CLIENTI — VERSIONE FINALE STABILE CORRETTA
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
    .btn-blue > button { background-color:#e3f2fd !important; color:#0d47a1 !important; border:none !important; border-radius:6px !important; font-weight:500 !important; }
    .btn-yellow > button { background-color:#fff8e1 !important; color:#ef6c00 !important; border:none !important; border-radius:6px !important; font-weight:500 !important; }
    .btn-red > button { background-color:#ffebee !important; color:#b71c1c !important; border:none !important; border-radius:6px !important; font-weight:500 !important; }
    .info-box { background:#fff; border-radius:12px; box-shadow:0 3px 10px rgba(0,0,0,0.06); padding:1.3rem 1.6rem; margin-top:0.8rem; margin-bottom:1.5rem; font-size:15px; line-height:1.7; border-left:5px solid #2563eb; }
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
        if st.button("📄 Vai ai Contratti", use_container_width=True, key=f"go_cont_{sel_id}"):
            st.session_state.update({
                "selected_cliente": sel_id,
                "nav_target": "Contratti",
                "_go_contratti_now": True
            })
            st.rerun()

        if st.button("✏️ Modifica Anagrafica", use_container_width=True, key=f"edit_{sel_id}"):
            st.session_state[f"edit_cli_{sel_id}"] = not st.session_state.get(f"edit_cli_{sel_id}", False)

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

                tmk_value = cliente.get("TMK", "")
                if pd.isna(tmk_value) or tmk_value not in ["Giulia", "Antonella", "Annalisa", "Laura"]:
                    tmk_value = ""
                tmk = st.selectbox(
                    "👩‍💼 TMK di riferimento",
                    ["", "Giulia", "Antonella", "Annalisa", "Laura"],
                    index=["", "Giulia", "Antonella", "Annalisa", "Laura"].index(tmk_value)
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
# PAGINA CONTRATTI — VERSIONE DEFINITIVA 2025 CON FADE, EXPORT, FIX E PERFORMANCE OTTIMIZZATA
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    import time
    from utils.exports import export_excel_contratti, export_pdf_contratti
    from utils.formatting import fmt_date
    from utils.data_io import save_contratti

    ruolo_scrittura = st.session_state.get("ruolo_scrittura", role)
    permessi_limitati = ruolo_scrittura == "limitato"

    st.markdown("## 📄 Gestione Contratti")

    # === Inizializza variabili modali ===
    if "modal_add_contract" not in st.session_state:
        st.session_state["modal_add_contract"] = False
    if "modal_edit_contract" not in st.session_state:
        st.session_state["modal_edit_contract"] = None

    # === Selezione cliente ===
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    clienti_labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    clienti_ids = df_cli["ClienteID"].astype(str).tolist()
    sel_label = st.selectbox("Seleziona Cliente", clienti_labels.tolist())
    sel_id = clienti_ids[clienti_labels.tolist().index(sel_label)]
    rag_soc = df_cli.loc[df_cli["ClienteID"] == sel_id, "RagioneSociale"].iloc[0]

    # === Titolo Cliente ===
    st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:space-between;
                    margin-top:10px;margin-bottom:15px;'>
            <h3 style='margin:0;color:#2563eb;'>🏢 {rag_soc}</h3>
        </div>
    """, unsafe_allow_html=True)

    # === Azioni globali ===
    colA, colB, colC = st.columns([0.25, 0.25, 0.5])
    with colA:
        if not permessi_limitati:
            if st.button("➕ Aggiungi Contratto", use_container_width=True, key="btn_add_contract"):
                # Delay minimo per garantire visibilità del modale prima del rerun
                st.session_state["modal_add_contract"] = True
                st.session_state["_modal_open_time"] = time.time()
                st.rerun()

    with colB:
        if st.button("📤 Esporta Excel", use_container_width=True):
            xlsx_bytes = export_excel_contratti(df_ct, sel_id, rag_soc)
            st.download_button(
                label="⬇️ Scarica Excel",
                data=xlsx_bytes,
                file_name=f"Contratti_{rag_soc}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    with colC:
        if st.button("📄 Esporta PDF", use_container_width=True):
            pdf_bytes = export_pdf_contratti(df_ct, sel_id, rag_soc)
            if pdf_bytes:
                st.download_button(
                    label="⬇️ Scarica PDF",
                    data=pdf_bytes,
                    file_name=f"Contratti_{rag_soc}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ Nessun contratto da esportare per questo cliente.")

    # === Filtra contratti ===
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto registrato per questo cliente.")
        return

    st.markdown("### 📋 Elenco Contratti")

    for i, r in ct.iterrows():
        numero = r.get("NumeroContratto", "—")
        stato = str(r.get("Stato", "aperto")).lower()
        colore_sfondo = "#f9f9f9" if stato == "aperto" else "#ffebee"
        bordo = "#2563eb" if stato == "aperto" else "#b71c1c"

        # === CARD CONTRATTO ===
        with st.container():
            st.markdown(f"""
                <div style="background:{colore_sfondo};padding:12px 16px;
                            border-radius:10px;margin-bottom:10px;
                            border-left:6px solid {bordo};
                            box-shadow:0 2px 6px rgba(0,0,0,0.05);">
                    <b>📄 Contratto {numero}</b> — <i>{r.get('DescrizioneProdotto','—')}</i><br>
                    <b>📅 Periodo:</b> {r.get('DataInizio','—')} → {r.get('DataFine','—')}  
                    | <b>Durata:</b> {r.get('Durata','—')} mesi  
                    | <b>💰 Totale Rata:</b> {r.get('TotRata','—')}
                    <br><b>Copie B/N:</b> {r.get('CopieBN','—')} | <b>Ecc. B/N:</b> {r.get('EccBN','—')}
                    | <b>Copie Colore:</b> {r.get('CopieCol','—')} | <b>Ecc. Colore:</b> {r.get('EccCol','—')}
                    <br><b>NOL Fin:</b> {r.get('NOL_FIN','—')} | <b>NOL Int:</b> {r.get('NOL_INT','—')}
                    <br><b>Stato:</b> {"✅ Aperto" if stato == "aperto" else "❌ Chiuso"}
                </div>
            """, unsafe_allow_html=True)

            # === DESCRIZIONE ESPANDIBILE ===
            with st.expander("📖 Mostra descrizione completa"):
                st.markdown(f"**Descrizione prodotto:** {r.get('DescrizioneProdotto','—')}")

            # === AZIONI ===
            c1, c2, c3 = st.columns([0.15, 0.15, 0.7])
            with c1:
                if not permessi_limitati:
                    if st.button("✏️", key=f"edit_{numero}_{i}", use_container_width=True):
                        st.session_state["modal_edit_contract"] = numero
                        st.rerun()
            with c2:
                if not permessi_limitati:
                    if stato == "aperto":
                        if st.button("❌", key=f"close_{numero}_{i}", use_container_width=True):
                            idx = df_ct.index[df_ct["NumeroContratto"] == numero]
                            if len(idx) > 0:
                                df_ct.loc[idx[0], "Stato"] = "chiuso"
                                save_contratti(df_ct)
                                st.success(f"Contratto {numero} chiuso ✅")
                                st.rerun()
                    else:
                        if st.button("🔓", key=f"reopen_{numero}_{i}", use_container_width=True):
                            idx = df_ct.index[df_ct["NumeroContratto"] == numero]
                            if len(idx) > 0:
                                df_ct.loc[idx[0], "Stato"] = "aperto"
                                save_contratti(df_ct)
                                st.success(f"Contratto {numero} riaperto ✅")
                                st.rerun()

    # === MODALE NUOVO CONTRATTO (con effetto fade-in) ===
    if st.session_state.get("modal_add_contract", False):
        st.markdown("""
        <style>
        @keyframes fadeIn {
            from {opacity: 0;}
            to {opacity: 1;}
        }
        @keyframes fadeOut {
            from {opacity: 1;}
            to {opacity: 0;}
        }
        .modal-bg {
            position: fixed;
            top:0; left:0;
            width:100%; height:100%;
            background: rgba(0,0,0,0.45);
            z-index:9999;
            display:flex;
            justify-content:center;
            align-items:center;
            animation: fadeIn 0.25s ease-in-out;
        }
        .modal-box {
            background:white;
            border-radius:12px;
            width:540px;
            padding:1.8rem 2rem;
            box-shadow:0 4px 20px rgba(0,0,0,0.25);
            transform: scale(0.98);
            animation: fadeIn 0.3s ease-out;
        }
        </style>
        <div class="modal-bg"><div class="modal-box">
        """, unsafe_allow_html=True)

        st.markdown("### ➕ Nuovo Contratto")
        with st.form("form_add_contract"):
            num = st.text_input("Numero Contratto")
            data_inizio = st.date_input("Data Inizio")
            durata = st.selectbox("Durata (mesi)", [12, 24, 36, 48, 60], index=2)
            desc = st.text_area("Descrizione Prodotto", height=100)
            tot = st.text_input("Totale Rata")

            col1, col2 = st.columns(2)
            with col1:
                salva = st.form_submit_button("💾 Salva")
            with col2:
                annulla = st.form_submit_button("❌ Annulla")

            if salva:
                data_fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))
                nuovo = {
                    "ClienteID": sel_id,
                    "RagioneSociale": rag_soc,
                    "NumeroContratto": num,
                    "DataInizio": fmt_date(data_inizio),
                    "DataFine": fmt_date(data_fine),
                    "Durata": durata,
                    "TotRata": tot,
                    "DescrizioneProdotto": desc,
                    "Stato": "aperto"
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([nuovo])], ignore_index=True)
                save_contratti(df_ct)
                st.session_state["modal_add_contract"] = False
                st.success("✅ Contratto aggiunto con successo!")
                time.sleep(0.5)
                st.rerun()

            if annulla:
                st.session_state["modal_add_contract"] = False
                st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)

    # === MODALE MODIFICA CONTRATTO ===
    if st.session_state.get("modal_edit_contract"):
        numero = st.session_state["modal_edit_contract"]
        contratto = df_ct[df_ct["NumeroContratto"] == numero].iloc[0]

        st.markdown("""
        <style>
        .modal-bg {
            position: fixed; top:0; left:0; width:100%; height:100%;
            background: rgba(0,0,0,0.45); z-index:9999;
            display:flex; justify-content:center; align-items:center;
            animation: fadeIn 0.3s ease-in-out;
        }
        .modal-box {
            background:white; border-radius:12px; width:540px;
            padding:1.8rem 2rem; box-shadow:0 4px 20px rgba(0,0,0,0.25);
            transform: scale(0.98);
            animation: fadeIn 0.3s ease-out;
        }
        </style>
        <div class="modal-bg"><div class="modal-box">
        """, unsafe_allow_html=True)

        st.markdown(f"### ✏️ Modifica Contratto {numero}")
        with st.form("form_edit_contract"):
            desc = st.text_area("Descrizione", contratto.get("DescrizioneProdotto", ""), height=100)
            tot = st.text_input("Totale Rata", contratto.get("TotRata", ""))
            stato = st.selectbox("Stato", ["aperto", "chiuso"],
                                 index=0 if contratto.get("Stato","")!="chiuso" else 1)

            col1, col2 = st.columns(2)
            with col1:
                salva = st.form_submit_button("💾 Salva")
            with col2:
                annulla = st.form_submit_button("❌ Annulla")

            if salva:
                idx = df_ct.index[df_ct["NumeroContratto"] == numero][0]
                df_ct.loc[idx, ["DescrizioneProdotto", "TotRata", "Stato"]] = [desc, tot, stato]
                save_contratti(df_ct)
                st.session_state["modal_edit_contract"] = None
                st.success("✅ Contratto aggiornato!")
                time.sleep(0.5)
                st.rerun()

            if annulla:
                st.session_state["modal_edit_contract"] = None
                st.rerun()

        st.markdown("</div></div>", unsafe_allow_html=True)
        # Evita chiusura immediata del modale appena aperto
        if st.session_state.get("modal_add_contract", False):
            if "_modal_open_time" in st.session_state:
                if time.time() - st.session_state["_modal_open_time"] < 0.5:
                    pass  # lascialo aperto

    # === FIX SICUREZZA MODALE ===
    if st.session_state.get("modal_add_contract", False) and not st.session_state.get("modal_edit_contract"):
        st.session_state["modal_add_contract"] = False
    if st.session_state.get("modal_safety_lock", False):
        st.session_state["modal_safety_lock"] = False



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
        # === Clienti ===
        if not df_cli.empty:
            for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
                # 🔧 Controllo sicuro per evitare ValueError anche se df_cli.columns è strano
                if isinstance(df_cli.columns, (list, pd.Index)) and c in list(df_cli.columns):
                    try:
                        df_cli[c] = fix_inverted_dates(df_cli[c], col_name=c)
                    except Exception as e:
                        st.warning(f"⚠️ Errore durante la correzione della colonna {c}: {e}")

        # === Contratti ===
        if not df_ct.empty:
            for c in ["DataInizio", "DataFine"]:
                if isinstance(df_ct.columns, (list, pd.Index)) and c in list(df_ct.columns):
                    try:
                        df_ct[c] = fix_inverted_dates(df_ct[c], col_name=c)
                    except Exception as e:
                        st.warning(f"⚠️ Errore durante la correzione della colonna {c}: {e}")

        # === Salva una sola volta ===
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

# 🧹 Pulizia cache automatica all’avvio (solo per debug o refresh completo)
st.cache_data.clear()
st.cache_resource.clear()

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
