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

# =====================================
# COSTANTI GLOBALI SEMPRE DISPONIBILI
# =====================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

# Directory di archiviazione locale (una per ogni utente)
STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Percorsi principali
CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)

# Template e durate
TEMPLATES_DIR = Path("templates")
TEMPLATE_OPTIONS = {
    "Offerta A4": "Offerta_A4.docx",
    "Offerta A3": "Offerta_A3.docx",
    "Centralino": "Offerta_Centralino.docx",
    "Varie": "Offerta_Varie.docx",
}

DURATE_MESI = ["12", "24", "36", "48", "60", "72"]


# =====================================
# CONFIGURAZIONE STREAMLIT E STILE BASE
# =====================================
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

# --- Stile generale app ---
st.markdown("""
<style>
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    padding-top: 1rem;
    max-width: 100% !important;
}
section.main > div:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
[data-testid="stSidebar"] {
    background-color: #f8fafc !important;
}
h2, h3 {
    color: #2563eb;
}
</style>
""", unsafe_allow_html=True)

# --- Script per mantenere lo scroll in alto al cambio pagina ---
st.markdown("""
<script>
window.addEventListener('load', function() {
    window.scrollTo(0, 0);
});
</script>
""", unsafe_allow_html=True)

# =====================================
# COLONNE STANDARD CSV
# =====================================
CLIENTI_COLS = [
    "clienteid", "ragionesociale", "personariferimento", "indirizzo", "citta", "cap",
    "telefono", "cell", "email", "partitaiva", "iban", "sdi",
    "ultimorecall", "prossimorecall", "ultimavisita", "prossimavisita",
    "tmk", "notecliente", "owner"
]

CONTRATTI_COLS = [
    "clienteid", "ragionesociale", "numerocontratto", "datainizio", "datafine", "durata",
    "descrizioneprodotto", "nol_fin", "nol_int", "totrata",
    "copiebn", "eccbn", "copiecol", "ecccol", "stato", "owner"
]


# =====================================
# CONNESSIONE A SUPABASE
# =====================================
from supabase import create_client
import os

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_ANON_KEY = st.secrets["supabase"]["anon_key"]
SUPABASE_SERVICE_KEY = st.secrets["supabase"]["service_key"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# =====================================
# CARICAMENTO E SALVATAGGIO DATI (CSV + SUPABASE)
# =====================================

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """
    Garantisce che il DataFrame contenga tutte le colonne richieste
    (nell'ordine corretto), aggiungendo quelle mancanti come stringhe vuote.

    - Gestisce DataFrame vuoti o None.
    - Mantiene l'ordine delle colonne specificato.
    - Riempie i valori mancanti con stringhe vuote.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)

    out = df.copy()

    for c in cols:
        if c not in out.columns:
            out[c] = ""

    # Riordina e pulisce
    out = out[cols]
    out = out.fillna("").astype(str)

    return out


# =====================================
# CARICAMENTO CSV UNIVERSALE — VERSIONE 2025 (ottimizzata + cache + garanzia colonne)
# =====================================
@st.cache_data(ttl=120)
def load_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    """
    Carica un CSV locale in modo sicuro e coerente.
    - Se il file non esiste, lo crea vuoto con le colonne richieste.
    - Gestisce encoding UTF-8 e caratteri speciali.
    - Usa cache per migliorare le performance.
    """
    try:
        if not path.exists():
            st.warning(f"⚠️ File {path.name} non trovato. Creato un nuovo CSV vuoto.")
            df = pd.DataFrame(columns=cols)
            df.to_csv(path, index=False, encoding="utf-8-sig")
            return df

        # --- Lettura CSV robusta ---
        df = pd.read_csv(
            path,
            dtype=str,
            encoding="utf-8-sig",
            sep=None,               # auto-rilevamento delimitatore
            engine="python",
            on_bad_lines="skip"
        ).fillna("")

        # --- Garantisce tutte le colonne richieste ---
        for c in cols:
            if c not in df.columns:
                df[c] = ""

        # Riordina secondo la lista delle colonne attese
        df = df[cols]

        return df

    except Exception as e:
        st.error(f"❌ Errore durante il caricamento di {path.name}: {e}")
        return pd.DataFrame(columns=cols)


# =====================================
# CLIENTI E CONTRATTI (SALVATAGGIO + SYNC)
# =====================================

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Garantisce che il DataFrame abbia tutte le colonne richieste."""
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]


def load_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    """Carica CSV locale, crea file vuoto se mancante."""
    if not path.exists():
        pd.DataFrame(columns=cols).to_csv(path, index=False, encoding="utf-8-sig", sep=";")
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(path, dtype=str, sep=None, engine="python",
                         encoding="utf-8-sig", on_bad_lines="skip").fillna("")
        return ensure_columns(df, cols)
    except Exception as e:
        st.error(f"❌ Errore caricamento {path.name}: {e}")
        return pd.DataFrame(columns=cols)


def save_csv(df: pd.DataFrame, path: Path, date_cols=None):
    """
    Salva il DataFrame in locale e sincronizza automaticamente con Supabase.
    Gestisce sia 'clienti' che 'contratti' a seconda del file.
    """
    try:
        out = df.copy()

        if date_cols:
            for c in date_cols:
                out[c] = out[c].apply(fmt_date)

        out.to_csv(path, index=False, encoding="utf-8-sig")
        st.toast(f"💾 {path.name} salvato in locale", icon="📁")

        if "supabase" in globals() and st.session_state.get("logged_in"):
            user = st.session_state.get("user", "")
            if not user:
                st.warning("⚠️ Utente non definito: sincronizzazione annullata.")
                return

            table = "clienti" if "client" in path.name.lower() else "contratti"

            try:
                supabase.table(table).delete().eq("owner", user).execute()
            except Exception as e:
                st.warning(f"⚠️ Pulizia tabella {table} non riuscita: {e}")

            upload_df = out.copy()
            upload_df["owner"] = user
            upload_df = upload_df.fillna("")

            try:
                supabase.table(table).insert(upload_df.to_dict(orient="records")).execute()
                st.toast(f"☁️ Dati sincronizzati con Supabase ({table})", icon="✅")
            except Exception as e:
                st.warning(f"⚠️ Errore durante la sincronizzazione di {table}: {e}")
        else:
            st.info("ℹ️ Sync cloud non attiva (utente non loggato o Supabase non inizializzato).")

    except Exception as e:
        st.error(f"❌ Errore durante il salvataggio di {path.name}: {e}")


def load_clienti() -> pd.DataFrame:
    """Carica i clienti dal CSV locale e sincronizza da Supabase."""
    CLIENTI_CSV = st.session_state["CLIENTI_CSV"]
    CLIENTI_COLS = st.session_state["CLIENTI_COLS"]
    df = load_csv(CLIENTI_CSV, CLIENTI_COLS)

    # 🔹 Merge da Supabase
    try:
        response = supabase.table("clienti").select("*").eq("owner", st.session_state["user"]).execute()
        if response.data:
            df_sb = pd.DataFrame(response.data)
            df_sb = ensure_columns(df_sb, CLIENTI_COLS)
            df = pd.concat([df, df_sb], ignore_index=True).drop_duplicates(subset=["ClienteID"], keep="last")
            df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
    except Exception as e:
        st.warning(f"⚠️ Sync Supabase clienti saltata: {e}")
    return df.fillna("")


def save_clienti(df: pd.DataFrame):
    """Salva clienti — delega completamente a save_csv()."""
    save_csv(df, st.session_state["CLIENTI_CSV"])


def load_contratti() -> pd.DataFrame:
    """Carica contratti dal CSV locale e sincronizza da Supabase."""
    CONTRATTI_CSV = st.session_state["CONTRATTI_CSV"]
    CONTRATTI_COLS = st.session_state["CONTRATTI_COLS"]
    df = load_csv(CONTRATTI_CSV, CONTRATTI_COLS)

    try:
        response = supabase.table("contratti").select("*").eq("owner", st.session_state["user"]).execute()
        if response.data:
            df_sb = pd.DataFrame(response.data)
            df_sb = ensure_columns(df_sb, CONTRATTI_COLS)
            df = pd.concat([df, df_sb], ignore_index=True).drop_duplicates(subset=["NumeroContratto"], keep="last")
            df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
    except Exception as e:
        st.warning(f"⚠️ Sync Supabase contratti saltata: {e}")
    return df.fillna("")


def save_contratti(df: pd.DataFrame):
    """Salva contratti — delega completamente a save_csv()."""
    save_csv(df, st.session_state["CONTRATTI_CSV"])

# =====================================
# NORMALIZZAZIONE COLONNE (compatibilità Supabase)
# =====================================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rinomina automaticamente le colonne in maiuscolo standard
    per compatibilità col codice Streamlit.
    """
    mapping = {
        "clienteid": "ClienteID",
        "ragionesociale": "RagioneSociale",
        "personariferimento": "PersonaRiferimento",
        "indirizzo": "Indirizzo",
        "citta": "Citta",
        "cap": "CAP",
        "telefono": "Telefono",
        "cell": "Cell",
        "email": "Email",
        "partitaiva": "PartitaIVA",
        "iban": "IBAN",
        "sdi": "SDI",
        "ultimorecall": "UltimoRecall",
        "prossimorecall": "ProssimoRecall",
        "ultimavisita": "UltimaVisita",
        "prossimavisita": "ProssimaVisita",
        "tmk": "TMK",
        "notecliente": "NoteCliente",
        "numerocontratto": "NumeroContratto",
        "datainizio": "DataInizio",
        "datafine": "DataFine",
        "durata": "Durata",
        "descrizioneprodotto": "DescrizioneProdotto",
        "nol_fin": "NOL_FIN",
        "nol_int": "NOL_INT",
        "totrata": "TotRata",
        "copiebn": "CopieBN",
        "eccbn": "EccBN",
        "copiecol": "CopieCol",
        "ecccol": "EccCol",
        "stato": "Stato",
        "owner": "owner"
    }

    # 🔹 Normalizza i nomi delle colonne in modo case-insensitive
    df = df.rename(columns={c: mapping.get(c.lower(), c) for c in df.columns})

    # 🔹 Cast di sicurezza per chiavi relazionali
    if "ClienteID" in df.columns:
        df["ClienteID"] = df["ClienteID"].astype(str)
    if "NumeroContratto" in df.columns:
        df["NumeroContratto"] = df["NumeroContratto"].astype(str)

    return df


# =====================================
# SINCRONIZZAZIONE AUTOMATICA SUPABASE
# =====================================
import threading
import time

def sync_supabase_periodico():
    """Sincronizza automaticamente clienti e contratti ogni 5 minuti per l’utente loggato."""
    while True:
        try:
            if st.session_state.get("logged_in") and "user" in st.session_state:
                user = st.session_state["user"]
                CLIENTI_CSV = st.session_state.get("CLIENTI_CSV")
                CONTRATTI_CSV = st.session_state.get("CONTRATTI_CSV")

                # Carica dati locali
                df_cli = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
                df_ct = pd.read_csv(CONTRATTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")

                # 🔁 Sincronizza con Supabase
                supabase.table("clienti").delete().eq("owner", user).execute()
                supabase.table("clienti").insert(df_cli.assign(owner=user).to_dict(orient="records")).execute()

                supabase.table("contratti").delete().eq("owner", user).execute()
                supabase.table("contratti").insert(df_ct.assign(owner=user).to_dict(orient="records")).execute()

            time.sleep(300)  # 5 minuti
        except Exception as e:

            time.sleep(300)
# =====================================
# CARICAMENTO DATI DA SUPABASE (versione finale stabile)
# =====================================
def carica_dati_supabase(user: str):
    """Scarica i dati di clienti e contratti da Supabase, li normalizza e verifica la coerenza."""
    import streamlit as st
    import pandas as pd

    try:
        # --- CLIENTI ---
        res_cli = supabase.table("clienti").select("*").execute()
        data_cli = res_cli.data
        df_cli = pd.DataFrame(data_cli)
        

        # 🔍 Filtro in Python per owner (se la colonna esiste)
        if not df_cli.empty:
            if "owner" in df_cli.columns:
                df_cli = df_cli[df_cli["owner"].astype(str).str.lower() == user.lower()]
            elif "Owner" in df_cli.columns:
                df_cli = df_cli[df_cli["Owner"].astype(str).str.lower() == user.lower()]
            else:
                st.sidebar.info("ℹ️ Nessuna colonna 'owner' trovata per i clienti.")

        # --- CONTRATTI ---
        res_ct = supabase.table("contratti").select("*").execute()
        data_ct = res_ct.data
        df_ct = pd.DataFrame(data_ct)

        # 🔍 Filtro in Python per owner (se la colonna esiste)
        if not df_ct.empty:
            if "owner" in df_ct.columns:
                df_ct = df_ct[df_ct["owner"].astype(str).str.lower() == user.lower()]
            elif "Owner" in df_ct.columns:
                df_ct = df_ct[df_ct["Owner"].astype(str).str.lower() == user.lower()]
            else:
                st.sidebar.info("ℹ️ Nessuna colonna 'owner' trovata per i contratti.")

        # --- Normalizzazione colonne ---
        df_cli = normalize_columns(df_cli)
        df_ct = normalize_columns(df_ct)

        # --- Colonne minime garantite ---
        for col in ["ClienteID", "RagioneSociale"]:
            if col not in df_cli.columns:
                df_cli[col] = ""
        for col in ["ClienteID", "NumeroContratto", "DescrizioneProdotto"]:
            if col not in df_ct.columns:
                df_ct[col] = ""

        # --- Log nella sidebar ---
        st.sidebar.markdown(f"📡 Supabase: **{len(df_cli)} clienti / {len(df_ct)} contratti**")

        # === 🔍 Verifica coerenza ===
        if not df_ct.empty and not df_cli.empty:
            cli_ids = set(df_cli["ClienteID"].astype(str))
            ct_ids = set(df_ct["ClienteID"].astype(str))
            orfani = sorted(list(ct_ids - cli_ids))
            if orfani:
                st.sidebar.warning(f"⚠️ Contratti orfani (ClienteID non trovato): {len(orfani)}")
            else:
                st.sidebar.success("✅ Dati Supabase coerenti!")

        return df_cli, df_ct

    except Exception as e:
        import traceback
        st.sidebar.error(f"❌ Errore caricamento Supabase: {e}")
        st.sidebar.text(traceback.format_exc())
        return pd.DataFrame(), pd.DataFrame()

# =====================================
# FIX AUTOMATICO OWNER SU SUPABASE
# =====================================
def fix_supabase_owner(user: str):
    """Aggiorna i record su Supabase aggiungendo il campo owner dove manca."""
    import streamlit as st
    import pandas as pd

    st.warning("⚙️ Avvio controllo e correzione 'owner' su Supabase...")

    try:
        # --- CLIENTI ---
        res_cli = supabase.table("clienti").select("*").execute()
        df_cli = pd.DataFrame(res_cli.data)

        if "owner" not in df_cli.columns:
            st.error("❌ La tabella 'clienti' non ha la colonna 'owner'. Aggiungila manualmente su Supabase.")
        else:
            mancanti_cli = df_cli[df_cli["owner"].astype(str).str.strip() == ""]
            if not mancanti_cli.empty:
                for _, row in mancanti_cli.iterrows():
                    supabase.table("clienti").update({"owner": user}).eq("id", row["id"]).execute()
                st.success(f"✅ Aggiornati {len(mancanti_cli)} clienti senza owner.")
            else:
                st.info("✅ Tutti i clienti hanno già un owner.")

        # --- CONTRATTI ---
        res_ct = supabase.table("contratti").select("*").execute()
        df_ct = pd.DataFrame(res_ct.data)

        if "owner" not in df_ct.columns:
            st.error("❌ La tabella 'contratti' non ha la colonna 'owner'. Aggiungila manualmente su Supabase.")
        else:
            mancanti_ct = df_ct[df_ct["owner"].astype(str).str.strip() == ""]
            if not mancanti_ct.empty:
                for _, row in mancanti_ct.iterrows():
                    supabase.table("contratti").update({"owner": user}).eq("id", row["id"]).execute()
                st.success(f"✅ Aggiornati {len(mancanti_ct)} contratti senza owner.")
            else:
                st.info("✅ Tutti i contratti hanno già un owner.")

        st.success("🎉 Correzione completata! Ricarica l'app per vedere i dati aggiornati.")

    except Exception as e:
        import traceback
        st.error(f"❌ Errore durante il fix: {e}")
        st.text(traceback.format_exc())

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
# LOGIN FULLSCREEN (versione aggiornata con sync Supabase)
# =====================================
def do_login_fullscreen():
    """Login elegante con sfondo fullscreen + storage multiutente + sync periodico Supabase"""
    import threading
    import time

    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    # --- Stile ---
    st.markdown("""
    <style>
    div[data-testid="stAppViewContainer"] {padding-top:0 !important;}
    .block-container {
        display:flex;flex-direction:column;justify-content:center;
        align-items:center;height:100vh;background-color:#f8fafc;
    }
    .login-card {
        background:#fff;border:1px solid #e5e7eb;border-radius:12px;
        box-shadow:0 4px 16px rgba(0,0,0,0.08);
        padding:2rem 2.5rem;width:360px;text-align:center;
    }
    .login-title {font-size:1.3rem;font-weight:600;color:#2563eb;margin:1rem 0 1.4rem;}
    .stButton>button {
        width:260px;font-size:0.9rem;background-color:#2563eb;color:white;
        border:none;border-radius:6px;padding:0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- UI ---
    login_col1, login_col2, _ = st.columns([1, 2, 1])
    with login_col2:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.image(LOGO_URL, width=140)
        st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)
        username = st.text_input("Nome utente", key="login_user").strip().lower()
        password = st.text_input("Password", type="password", key="login_pass")
        login_btn = st.button("Entra")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Login ---
    if login_btn or (username and password and not st.session_state.get("_login_checked")):
        st.session_state["_login_checked"] = True
        users = st.secrets["auth"]["users"]

        if username in users and users[username]["password"] == password:
            st.session_state.update({
                "user": username,
                "role": users[username].get("role", "viewer"),
                "logged_in": True
            })

            # =====================================
            # STORAGE MULTIUTENTE AUTOMATICO
            # =====================================
            from pathlib import Path
            base_storage = Path("storage")
            user = username.lower()

            # Fabio lavora nella root
            if user == "fabio":
                user_storage = base_storage
            else:
                user_storage = base_storage / user
                user_storage.mkdir(parents=True, exist_ok=True)

            # === Percorsi personali ===
            CLIENTI_CSV = user_storage / "clienti.csv"
            CONTRATTI_CSV = user_storage / "contratti_clienti.csv"
            PREVENTIVI_CSV = user_storage / "preventivi.csv"

            # === Struttura colonne ===
            CLIENTI_COLS = [
                "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
                "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
                "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita",
                "TMK", "NoteCliente", "owner"
            ]
            CONTRATTI_COLS = [
                "ClienteID", "RagioneSociale", "NumeroContratto", "DataInizio", "DataFine", "Durata",
                "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata",
                "CopieBN", "EccBN", "CopieCol", "EccCol", "Stato", "owner"
            ]

            # === Crea i CSV se non esistono ===
            for path, cols in [
                (CLIENTI_CSV, CLIENTI_COLS),
                (CONTRATTI_CSV, CONTRATTI_COLS),
                (PREVENTIVI_CSV, [])
            ]:
                if not path.exists():
                    import pandas as pd
                    pd.DataFrame(columns=cols).to_csv(path, index=False, encoding="utf-8-sig")

            # === Salva nel session_state ===
            st.session_state["CLIENTI_CSV"] = CLIENTI_CSV
            st.session_state["CONTRATTI_CSV"] = CONTRATTI_CSV
            st.session_state["PREVENTIVI_CSV"] = PREVENTIVI_CSV
            st.session_state["CLIENTI_COLS"] = CLIENTI_COLS
            st.session_state["CONTRATTI_COLS"] = CONTRATTI_COLS

            # =====================================
            # 🔄 AVVIO SINCRONIZZAZIONE AUTOMATICA SUPABASE
            # =====================================
            if "sync_thread_started" not in st.session_state:
                threading.Thread(target=sync_supabase_periodico, daemon=True).start()
                st.session_state["sync_thread_started"] = True

            # =====================================
            st.success(f"✅ Benvenuto {username}!")
            time.sleep(0.3)
            st.rerun()

        else:
            st.error("❌ Credenziali non valide.")
            st.session_state["_login_checked"] = False

    st.stop()

# =====================================
# KPI CARD — grafica con colore e icona
# =====================================
def kpi_card(titolo: str, valore, icona: str, colore: str = "#2563eb") -> str:
    """Crea una card colorata per i KPI della dashboard."""
    return f"""
    <div style="
        background:{colore}10;
        border-left:6px solid {colore};
        border-radius:10px;
        padding:1rem 1.2rem;
        box-shadow:0 2px 8px rgba(0,0,0,0.06);
        height:100%;
    ">
        <div style="font-size:1.6rem;">{icona}</div>
        <div style="font-size:0.9rem;font-weight:600;color:#444;">{titolo}</div>
        <div style="font-size:1.8rem;font-weight:700;color:{colore};">{valore}</div>
    </div>
    """

# =====================================
# PAGINA DASHBOARD
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(globals().get("LOGO_URL", ""), width=120)
    st.markdown("<h2>📊 Gestionale SHT</h2>", unsafe_allow_html=True)
    st.divider()

    # === KPI principali ===
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())
    now = pd.Timestamp.now().normalize()

    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    new_contracts = df_ct[
        (df_ct["DataInizio"].notna()) &
        (df_ct["DataInizio"] >= pd.Timestamp(year=now.year, month=1, day=1))
    ]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#1976D2"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#388E3C"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#D32F2F"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Nuovi contratti anno", len(new_contracts), "⭐", "#FBC02D"), unsafe_allow_html=True)
    st.divider()

    # === CREAZIONE NUOVO CLIENTE + CONTRATTO (VERSIONE COMPLETA 2025) ===
    with st.expander("➕ Crea Nuovo Cliente + Contratto"):
        with st.form("frm_new_cliente"):
            st.markdown("#### 📇 Dati Cliente")
            col1, col2 = st.columns(2)
            with col1:
                ragione = st.text_input("🏢 Ragione Sociale")
                persona = st.text_input("👤 Persona Riferimento")
                indirizzo = st.text_input("📍 Indirizzo")
                citta = st.text_input("🏙️ Città")
                cap = st.text_input("📮 CAP")
                telefono = st.text_input("📞 Telefono")
                cell = st.text_input("📱 Cellulare")
            with col2:
                email = st.text_input("✉️ Email")
                piva = st.text_input("💼 Partita IVA")
                iban = st.text_input("🏦 IBAN")
                sdi = st.text_input("📡 SDI")
                note = st.text_area("📝 Note Cliente", height=70)
                tmk = st.selectbox(
                    "👩‍💼 TMK di riferimento",
                    ["", "Giulia", "Antonella", "Annalisa", "Laura"],
                    index=0
            )
            # === SEZIONE CONTRATTO ===
            st.markdown("#### 📄 Primo Contratto del Cliente")
            
            colc1, colc2, colc3 = st.columns(3)
            num = colc1.text_input("📄 Numero Contratto")
            data_inizio = colc2.date_input("📅 Data Inizio", format="DD/MM/YYYY")
            durata = colc3.selectbox("📆 Durata (mesi)", DURATE_MESI, index=2)
            
            desc = st.text_area("🧾 Descrizione Prodotto", height=80)
            
            colp1, colp2, colp3 = st.columns(3)
            nf = colp1.text_input("🏦 NOL_FIN")
            ni = colp2.text_input("🏢 NOL_INT")
            tot = colp3.text_input("💰 Tot Rata")
            
            # 🔹 Copie e costi extra nello stesso blocco (senza intestazione e senza + / -)
            colx1, colx2, colx3, colx4 = st.columns(4)
            with colx1:
                copie_bn = st.text_input("📄 Copie incluse B/N", value="", key="copie_bn")
            with colx2:
                ecc_bn = st.text_input("💰 Costo extra B/N (€)", value="", key="ecc_bn")
            with colx3:
                copie_col = st.text_input("🖨️ Copie incluse Colore", value="", key="copie_col")
            with colx4:
                ecc_col = st.text_input("💰 Costo extra Colore (€)", value="", key="ecc_col")


            # === SALVA CLIENTE + CONTRATTO ===
            if st.form_submit_button("💾 Crea Cliente e Contratto"):
                try:
                    new_id = str(len(df_cli) + 1)

                    # --- CREA NUOVO CLIENTE ---
                    nuovo_cliente = {
                        "ClienteID": new_id,
                        "RagioneSociale": ragione,
                        "PersonaRiferimento": persona,
                        "Indirizzo": indirizzo,
                        "Citta": citta,
                        "CAP": cap,
                        "Telefono": telefono,
                        "Cell": cell,
                        "Email": email,
                        "PartitaIVA": piva,
                        "IBAN": iban,
                        "SDI": sdi,
                        "UltimoRecall": "",
                        "ProssimoRecall": "",
                        "UltimaVisita": "",
                        "ProssimaVisita": "",
                        "TMK": tmk,
                        "NoteCliente": note
                    }
                    df_cli = pd.concat([df_cli, pd.DataFrame([nuovo_cliente])], ignore_index=True)
                    save_clienti(df_cli)

                    # --- CREA NUOVO CONTRATTO ---
                    data_fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))
                    nuovo_contratto = {
                        "ClienteID": new_id,
                        "RagioneSociale": ragione,
                        "NumeroContratto": num,
                        "DataInizio": fmt_date(data_inizio),
                        "DataFine": fmt_date(data_fine),
                        "Durata": durata,
                        "DescrizioneProdotto": desc,
                        "NOL_FIN": nf,
                        "NOL_INT": ni,
                        "TotRata": tot,
                        "CopieBN": copie_bn,
                        "EccBN": ecc_bn,
                        "CopieCol": copie_col,
                        "EccCol": ecc_col,
                        "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([nuovo_contratto])], ignore_index=True)
                    save_contratti(df_ct)

                    st.success(f"✅ Cliente '{ragione}' e contratto creati correttamente!")
                    st.session_state.update({
                        "selected_cliente": new_id,
                        "nav_target": "Contratti",
                        "_go_contratti_now": True
                    })
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Errore creazione cliente: {e}")

    st.divider()

    # === CONTRATTI IN SCADENZA ENTRO 6 MESI ===
    st.markdown("### ⚠️ Contratti in scadenza entro 6 mesi")

    oggi = pd.Timestamp.now().normalize()
    entro_6_mesi = oggi + pd.DateOffset(months=6)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)

    scadenze = df_ct[
        (df_ct["DataFine"].notna()) &
        (df_ct["DataFine"] >= oggi) &
        (df_ct["DataFine"] <= entro_6_mesi) &
        (df_ct["Stato"].astype(str).str.lower() != "chiuso")
    ].copy()

    # Se manca RagioneSociale nei contratti, la aggiunge
    if not scadenze.empty and "RagioneSociale" not in scadenze.columns:
        scadenze = scadenze.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")

    if scadenze.empty:
        st.success("✅ Nessun contratto attivo in scadenza nei prossimi 6 mesi.")
    else:
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        scadenze = scadenze.sort_values("DataFine")

        st.markdown(f"📅 **{len(scadenze)} contratti in scadenza entro 6 mesi:**")

        # Intestazione tabella
        head_cols = st.columns([2, 1, 1, 1, 0.8])
        head_cols[0].markdown("**Cliente**")
        head_cols[1].markdown("**Contratto**")
        head_cols[2].markdown("**Scadenza**")
        head_cols[3].markdown("**Stato**")
        head_cols[4].markdown("**Azioni**")

        st.markdown("---")

        # Righe tabella (zebra + pulsante funzionante)
        for i, r in scadenze.iterrows():
            bg = "#f8fbff" if i % 2 == 0 else "#ffffff"
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 0.8])
            with col1:
                st.markdown(f"<div style='background:{bg};padding:6px'><b>{r.get('RagioneSociale','—')}</b></div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('NumeroContratto','—') or '—'}</div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div style='background:{bg};padding:6px'>{fmt_date(r.get('DataFine'))}</div>", unsafe_allow_html=True)
            with col4:
                st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('Stato','—')}</div>", unsafe_allow_html=True)
            with col5:
                if st.button("📂 Apri", key=f"open_scad_{i}", use_container_width=True):
                    # 🔹 Pulisce eventuali flag di modifica prima di cambiare pagina
                    for k in list(st.session_state.keys()):
                        if k.startswith("edit_ct_") or k.startswith("edit_cli_"):
                            del st.session_state[k]

                    st.session_state.update({
                        "selected_cliente": str(r.get("ClienteID")),
                        "nav_target": "Contratti",
                        "_go_contratti_now": True
                    })
                    st.rerun()

    # === CONTRATTI SENZA DATA FINE (solo inseriti da oggi in poi) ===
    st.divider()
    st.markdown("### ⚠️ Contratti recenti senza data di fine")

    oggi = pd.Timestamp.now().normalize()

    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)

    contratti_senza_fine = df_ct[
        (df_ct["DataFine"].isna()) &
        (df_ct["DataInizio"].notna()) &
        (df_ct["DataInizio"] >= oggi)
    ].copy()

    if contratti_senza_fine.empty:
        st.success("✅ Tutti i contratti recenti hanno una data di fine.")
    else:
        st.warning(f"⚠️ {len(contratti_senza_fine)} contratti inseriti da oggi non hanno ancora una data di fine:")

        if "RagioneSociale" not in contratti_senza_fine.columns or contratti_senza_fine["RagioneSociale"].eq("").any():
            contratti_senza_fine = contratti_senza_fine.merge(
                df_cli[["ClienteID", "RagioneSociale"]],
                on="ClienteID", how="left"
            )

        contratti_senza_fine["DataInizio"] = contratti_senza_fine["DataInizio"].apply(fmt_date)
        contratti_senza_fine = contratti_senza_fine.sort_values("DataInizio", ascending=False)

        # Intestazione
        head_cols = st.columns([2.5, 1, 1.2, 2.5, 0.8])
        head_cols[0].markdown("**Cliente**")
        head_cols[1].markdown("**Contratto**")
        head_cols[2].markdown("**Inizio**")
        head_cols[3].markdown("**Descrizione**")
        head_cols[4].markdown("**Azioni**")

        st.markdown("---")

        # Righe
        for i, r in contratti_senza_fine.iterrows():
            bg = "#fffdf5" if i % 2 == 0 else "#ffffff"
            col1, col2, col3, col4, col5 = st.columns([2.5, 1, 1.2, 2.5, 0.8])
            with col1:
                st.markdown(f"<div style='background:{bg};padding:6px'><b>{r.get('RagioneSociale','—')}</b></div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('NumeroContratto','—') or '—'}</div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div style='background:{bg};padding:6px'>{fmt_date(r.get('DataInizio'))}</div>", unsafe_allow_html=True)
            with col4:
                desc = str(r.get('DescrizioneProdotto', '—'))
                if len(desc) > 60:
                    desc = desc[:60] + "…"
                st.markdown(f"<div style='background:{bg};padding:6px'>{desc}</div>", unsafe_allow_html=True)
            with col5:
                if st.button("📂 Apri", key=f"open_ndf_{i}", use_container_width=True):
                    # 🔹 Pulisce eventuali flag di modifica prima di cambiare pagina
                    for k in list(st.session_state.keys()):
                        if k.startswith("edit_ct_") or k.startswith("edit_cli_"):
                            del st.session_state[k]

                    st.session_state.update({
                        "selected_cliente": str(r.get("ClienteID")),
                        "nav_target": "Contratti",
                        "_go_contratti_now": True
                    })
                    st.rerun()



# =====================================
# PAGINA CLIENTI (VERSIONE FINALE STABILE — FIX NameError COMPLETO)
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Gestione Clienti")

    # Blocco permessi
    if role == "limited":
        st.warning("⚠️ Accesso in sola lettura per il tuo profilo.")
        st.stop()

    # === PRE-SELEZIONE CLIENTE ===
    if "selected_cliente" in st.session_state:
        sel_id = str(st.session_state.pop("selected_cliente"))
        cli_ids = df_cli["ClienteID"].astype(str)
        if sel_id in set(cli_ids):
            row = df_cli.loc[cli_ids == sel_id].iloc[0]
            st.session_state["cliente_selezionato"] = row["RagioneSociale"]

    # === RICERCA CLIENTE ===
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

    # === INTESTAZIONE CLIENTE + PULSANTI ===
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

    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
        st.caption(f"ID Cliente: {sel_id}")

    with col2:
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("📄 Vai ai Contratti", use_container_width=True, key=f"go_cont_{sel_id}"):
            st.session_state.update({
                "selected_cliente": sel_id,
                "nav_target": "Contratti",
                "_go_contratti_now": True
            })
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="btn-yellow">', unsafe_allow_html=True)
        if st.button("✏️ Modifica Anagrafica", use_container_width=True, key=f"edit_{sel_id}"):
            st.session_state[f"edit_cli_{sel_id}"] = not st.session_state.get(f"edit_cli_{sel_id}", False)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="btn-red">', unsafe_allow_html=True)
        if st.button("🗑️ Cancella Cliente", use_container_width=True, key=f"ask_del_{sel_id}"):
            st.session_state["confirm_delete_cliente"] = str(sel_id)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # === INFO RAPIDE ===
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

    # === MODIFICA ANAGRAFICA ===
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

        # === NOTE CLIENTE ===
        st.divider()
        st.markdown("### 📝 Note Cliente")
        note_attuali = cliente.get("NoteCliente", "")
        nuove_note = st.text_area("Modifica note cliente:", note_attuali, height=160, key=f"note_{sel_id}_{int(time.time()*1000)}")

        if st.button("💾 Salva Note Cliente", key=f"save_note_{sel_id}_{int(time.time()*1000)}", use_container_width=True):
            try:
                idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx_row, "NoteCliente"] = nuove_note
                save_clienti(df_cli)
                st.success("✅ Note aggiornate correttamente!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante il salvataggio delle note: {e}")

        # === RECALL E VISITE ===
        st.divider()
        st.markdown("### ⚡ Recall e Visite")

        def _safe_date(val):
            try:
                d = pd.to_datetime(val, dayfirst=True)
                return None if pd.isna(d) else d.date()
            except Exception:
                return None

        ur_val = _safe_date(cliente.get("UltimoRecall"))
        pr_val = _safe_date(cliente.get("ProssimoRecall"))
        uv_val = _safe_date(cliente.get("UltimaVisita"))
        pv_val = _safe_date(cliente.get("ProssimaVisita"))

        if ur_val and not pr_val:
            pr_val = (pd.Timestamp(ur_val) + pd.DateOffset(months=3)).date()
        if uv_val and not pv_val:
            pv_val = (pd.Timestamp(uv_val) + pd.DateOffset(months=6)).date()

        import time as _t
        uniq = f"{sel_id}_{int(_t.time()*1000)}"
        c1, c2, c3, c4 = st.columns(4)
        ur = c1.date_input("⏰ Ultimo Recall", value=ur_val, format="DD/MM/YYYY", key=f"ur_{uniq}")
        pr = c2.date_input("📅 Prossimo Recall", value=pr_val, format="DD/MM/YYYY", key=f"pr_{uniq}")
        uv = c3.date_input("👣 Ultima Visita", value=uv_val, format="DD/MM/YYYY", key=f"uv_{uniq}")
        pv = c4.date_input("🗓️ Prossima Visita", value=pv_val, format="DD/MM/YYYY", key=f"pv_{uniq}")

        if st.button("💾 Salva Aggiornamenti", use_container_width=True, key=f"save_recall_{uniq}"):
            idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
            df_cli.loc[idx, ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]] = \
                [fmt_date(ur), fmt_date(pr), fmt_date(uv), fmt_date(pv)]
            save_clienti(df_cli)
            st.success("✅ Date aggiornate.")
            st.rerun()

        # === GENERA PREVENTIVO + ELENCO ===
        st.divider()
        st.markdown("### 🧾 Genera Nuovo Preventivo")
        # (segue qui la sezione preventivi e elenco preventivi, invariata)

    
    TEMPLATE_OPTIONS = {
        "Offerta A4": "Offerta_A4.docx",
        "Offerta A3": "Offerta_A3.docx",
        "Centralino": "Offerta_Centralino.docx",
        "Varie": "Offerta_Varie.docx",
    }
    
    PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
    PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)
    prev_csv = STORAGE_DIR / "preventivi.csv"
    
    if prev_csv.exists():
        df_prev = pd.read_csv(prev_csv, dtype=str).fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])
    
    anno = datetime.now().year
    nome_cliente = cliente.get("RagioneSociale", "")
    nome_sicuro = "".join(c for c in nome_cliente if c.isalnum())[:6].upper()
    num_off = f"OFF-{anno}-{nome_sicuro}-{len(df_prev[df_prev['ClienteID'] == sel_id]) + 1:03d}"
    
    with st.form(f"frm_prev_{sel_id}"):
        st.text_input("Numero Offerta", num_off, disabled=True)
        nome_file = st.text_input("Nome File", f"{num_off}.docx")
        template = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        genera_btn = st.form_submit_button("💾 Genera Preventivo")
    
    if genera_btn:
        try:
            from docx import Document

            tpl_path = Path.cwd() / "templates" / TEMPLATE_OPTIONS[template]
            if not tpl_path.exists():
                st.error(f"❌ Template non trovato: {tpl_path}")
                st.stop()

            doc = Document(tpl_path)

            # === Sostituzione segnaposti (versione robusta con gestione CITTA) ===
            mappa = {
                "CLIENTE": nome_cliente,
                "INDIRIZZO": str(cliente.get("Indirizzo", "")).strip(),
                # Gestione robusta della città: accetta varianti, toglie spazi e mette in maiuscolo
                "CITTA": str(
                    cliente.get("Citta", cliente.get("CITTÀ", cliente.get("Citta ", "")))
                ).strip().upper(),
                "NUMERO_OFFERTA": num_off,
                "DATA": datetime.now().strftime("%d/%m/%Y"),
                "ULTIMO_RECALL": fmt_date(cliente.get("UltimoRecall")),
                "PROSSIMO_RECALL": fmt_date(cliente.get("ProssimoRecall")),
                "ULTIMA_VISITA": fmt_date(cliente.get("UltimaVisita")),
                "PROSSIMA_VISITA": fmt_date(cliente.get("ProssimaVisita")),
            }

            # Sostituzione più tollerante nei paragrafi (gestisce anche << CITTA >> con spazi)
            for p in doc.paragraphs:
                for k, v in mappa.items():
                    if f"<<{k}>>" in p.text or f"<< {k} >>" in p.text:
                        for run in p.runs:
                            run.text = run.text.replace(f"<<{k}>>", str(v))
                            run.text = run.text.replace(f"<< {k} >>", str(v))

            # === Salvataggio del documento ===
            out_path = PREVENTIVI_DIR / nome_file
            doc.save(out_path)

            # === Aggiornamento registro CSV ===
            nuova_riga = {
                "ClienteID": sel_id,
                "NumeroOfferta": num_off,
                "Template": TEMPLATE_OPTIONS[template],
                "NomeFile": nome_file,
                "Percorso": str(out_path),
                "DataCreazione": datetime.now().strftime("%d/%m/%Y %H:%M"),
            }
            df_prev = pd.concat([df_prev, pd.DataFrame([nuova_riga])], ignore_index=True)
            df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")

            st.success(f"✅ Preventivo generato: {out_path.name}")
            st.rerun()

        except Exception as e:
            import traceback
            st.error(f"❌ Errore durante la generazione del preventivo:\n\n{traceback.format_exc()}")


# === ELENCO PREVENTIVI === 
    st.divider()
    st.markdown("### 📂 Elenco Preventivi Cliente")
    
    prev_cli = df_prev[df_prev["ClienteID"] == sel_id]
    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        # Ordino per data di creazione (stringa) in modo consistente
        prev_cli = prev_cli.copy().sort_values("DataCreazione", ascending=False)
    
        for _, r in prev_cli.iterrows():
            file_path = Path(str(r.get("Percorso", "")))
            num_offerta = r.get("NumeroOfferta", "")
            nome_file_r = r.get("NomeFile", "")
    
            col1, col2, col3 = st.columns([0.6, 0.25, 0.15])
            with col1:
                st.markdown(f"**{num_offerta}** — {r.get('Template','')}  \n📅 {r.get('DataCreazione','')}")
            with col2:
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "⬇️ Scarica",
                            f.read(),
                            file_name=file_path.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{sel_id}_{num_offerta}"
                        )
                else:
                    st.caption("File non trovato su disco")
    
            with col3:
                if role == "admin":
                    # Chiave stabile basata su NumeroOfferta
                    if st.button("🗑 Elimina", key=f"del_prev_{sel_id}_{num_offerta}", use_container_width=True):
                        try:
                            # 1) Rimuovi file dal disco (se c'è)
                            try:
                                if file_path.exists():
                                    file_path.unlink()
                            except Exception as fe:
                                st.warning(f"Impossibile cancellare il file dal disco: {fe}")
    
                            # 2) Rimuovi la riga dal CSV in modo robusto (match per chiave)
                            mask = (
                                (df_prev["ClienteID"] == str(sel_id)) &
                                (df_prev["NumeroOfferta"] == str(num_offerta)) &
                                (df_prev["NomeFile"] == str(nome_file_r))
                            )
                            if mask.any():
                                df_prev = df_prev[~mask].copy()
                                df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
                                st.success("🗑 Preventivo eliminato.")
                                st.rerun()
                            else:
                                st.error("Riga non trovata nel CSV. Aggiorna la pagina e riprova.")
                        except Exception as e:
                            st.error(f"❌ Errore eliminazione: {e}")



# =====================================
# PAGINA CONTRATTI — VERSIONE 2025 (completa e funzionante con modali)
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    ruolo_scrittura = st.session_state.get("ruolo_scrittura", role)
    permessi_limitati = ruolo_scrittura == "limitato"

    st.markdown("## 📄 Gestione Contratti")

    # === Selezione cliente ===
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # 🔹 Preselezione automatica cliente (da Dashboard)
    selected_cliente = st.session_state.get("selected_cliente")
    clienti_ids = df_cli["ClienteID"].astype(str).tolist()
    clienti_labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1).tolist()

    if selected_cliente and selected_cliente in clienti_ids:
        idx_preselezionato = clienti_ids.index(selected_cliente)
    else:
        idx_preselezionato = 0

    sel_label = st.selectbox("Seleziona Cliente", clienti_labels, index=idx_preselezionato)
    sel_id = clienti_ids[clienti_labels.index(sel_label)]
    rag_soc = df_cli.loc[df_cli["ClienteID"] == sel_id, "RagioneSociale"].iloc[0]

    # === Header e pulsante aggiunta ===
    st.markdown(
        f"""
        <div style='display:flex;align-items:center;justify-content:space-between;margin-top:10px;margin-bottom:20px;'>
            <h3 style='margin:0;color:#2563eb;'>🏢 {rag_soc}</h3>
        </div>
        """, unsafe_allow_html=True
    )

    # 🔹 Pulsante "Aggiungi Contratto"
    if not permessi_limitati:
        if st.button("➕ Aggiungi Contratto", key="btn_add_contract", use_container_width=False):
            st.session_state["selected_contratto"] = None
            st.session_state["open_modal"] = "new"
            # La modale verrà gestita subito sotto

    # === GESTIONE MODALE (nuovo/modifica) ===
    _open = st.session_state.get("open_modal")
    _sel = st.session_state.get("selected_contratto")

    if _open == "new":
        show_contract_modal({}, df_ct, df_cli, rag_soc)
        st.stop()

    elif _open == "edit" and _sel:
        row = df_ct[df_ct["NumeroContratto"].astype(str) == str(_sel)]
        if not row.empty:
            show_contract_modal(row.iloc[0], df_ct, df_cli, rag_soc)
            st.stop()

    # === Filtra contratti del cliente ===
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto registrato per questo cliente.")
        return

    # === Formatta dati ===
    for c in ["DataInizio", "DataFine"]:
        ct[c] = ct[c].apply(fmt_date)
    for c in ["TotRata", "NOL_FIN", "NOL_INT"]:
        ct[c] = ct[c].apply(money)

    # === Intestazione tabella ===
    st.markdown("""
    <style>
      .tbl-wrapper { overflow-x:auto; }
      .tbl-header, .tbl-row {
          display:grid;
          grid-template-columns: 
            1.1fr 0.9fr 0.9fr 0.6fr 0.9fr 1.6fr 0.8fr 0.8fr 0.8fr 0.8fr 0.9fr 0.9fr 0.8fr 1.2fr;
          padding:8px 14px; font-size:14px; align-items:center;
      }
      .tbl-header { background:#f8fafc; font-weight:600; border-bottom:1px solid #e5e7eb; }
      .tbl-row:nth-child(even) { background:#ffffff; }
      .tbl-row:nth-child(odd) { background:#fdfdfd; }
      .tbl-row.chiuso { background:#ffebee !important; }
      .pill-open { background:#e8f5e9; color:#1b5e20; padding:2px 8px; border-radius:12px; font-weight:600; font-size:12px; }
      .pill-closed { background:#ffebee; color:#b71c1c; padding:2px 8px; border-radius:12px; font-weight:600; font-size:12px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(
        """
        <div class='tbl-header'>
            <div>📄 Numero</div>
            <div>📅 Inizio</div>
            <div>📅 Fine</div>
            <div>📆 Durata</div>
            <div>💰 Tot Rata</div>
            <div>🧾 Descrizione</div>
            <div>📄 Copie B/N</div>
            <div>💶 Extra B/N</div>
            <div>🖨️ Copie Col</div>
            <div>💶 Extra Col</div>
            <div>🏦 NOL_FIN</div>
            <div>🏢 NOL_INT</div>
            <div>🟢 Stato</div>
            <div>⚙️ Azioni</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # === Righe tabella ===
    for i, r in ct.iterrows():
        stato = str(r.get("Stato", "")).lower()
        bg_class = "chiuso" if stato == "chiuso" else ""
        numero = r.get("NumeroContratto", "—")

        stato_badge = (
            f"<span class='pill-closed'>Chiuso</span>" if stato == "chiuso"
            else f"<span class='pill-open'>Aperto</span>"
        )

        # Riga base
        st.markdown(
            f"""
            <div class='tbl-row {bg_class}'>
                <div>{r.get('NumeroContratto','—')}</div>
                <div>{r.get('DataInizio','')}</div>
                <div>{r.get('DataFine','')}</div>
                <div>{r.get('Durata','')}</div>
                <div>{r.get('TotRata','')}</div>
                <div>{r.get('DescrizioneProdotto','')}</div>
                <div>{r.get('CopieBN','')}</div>
                <div>{r.get('EccBN','')}</div>
                <div>{r.get('CopieCol','')}</div>
                <div>{r.get('EccCol','')}</div>
                <div>{r.get('NOL_FIN','')}</div>
                <div>{r.get('NOL_INT','')}</div>
                <div>{stato_badge}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # === Pulsanti Azione ===
        if not permessi_limitati:
            c1, c2 = st.columns(2)
            if c1.button("✏️ Modifica", key=f"edit_{i}_{sel_id}"):
                st.session_state["selected_contratto"] = r.get("NumeroContratto")
                st.session_state["open_modal"] = "edit"
                st.experimental_rerun()

            if c2.button("❌ Chiudi", key=f"close_{i}_{sel_id}"):
                num = r.get("NumeroContratto")
                idx = df_ct.index[df_ct["NumeroContratto"].astype(str) == str(num)]
                if len(idx) > 0:
                    df_ct.loc[idx[0], "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.success(f"✅ Contratto {num} chiuso correttamente.")
                    st.session_state.pop("open_modal", None)
                    st.session_state.pop("selected_contratto", None)
                    st.experimental_rerun()



# =====================================
# MODALE CONTRATTO — VERSIONE 2025 (completa: nuova creazione + modifica)
# =====================================
def show_contract_modal(contratto, df_ct, df_cli, rag_soc):
    import datetime

    ruolo_scrittura = st.session_state.get("ruolo_scrittura", "viewer")
    permessi_limitati = ruolo_scrittura == "limitato"

    is_new = st.session_state.get("open_modal") == "new"
    numero = contratto.get("NumeroContratto", "") if not is_new else ""
    titolo = "➕ Nuovo Contratto" if is_new else f"✏️ Modifica Contratto #{numero}"

    st.markdown(
        f"""
        <div style='padding:15px 20px;border-radius:12px;background:#f8fafc;margin-top:10px;'>
            <h4 style='margin:0 0 10px 0;color:#2563eb;'>{titolo}</h4>
        </div>
        """, unsafe_allow_html=True
    )

    with st.form(f"form_contratto_{numero or 'new'}"):
        col1, col2, col3 = st.columns(3)
        with col1:
            din = st.date_input(
                "📅 Data Inizio",
                value=(
                    pd.to_datetime(contratto.get("DataInizio"), errors="coerce").date()
                    if not is_new and pd.notna(contratto.get("DataInizio"))
                    else datetime.date.today()
                ),
                format="DD/MM/YYYY"
            )
        with col2:
            dfi = st.date_input(
                "📅 Data Fine",
                value=(
                    pd.to_datetime(contratto.get("DataFine"), errors="coerce").date()
                    if not is_new and pd.notna(contratto.get("DataFine"))
                    else datetime.date.today() + datetime.timedelta(days=365)
                ),
                format="DD/MM/YYYY"
            )
        with col3:
            durata = st.selectbox(
                "📆 Durata (mesi)",
                DURATE_MESI,
                index=(
                    DURATE_MESI.index(str(contratto.get("Durata", "12")))
                    if not is_new and str(contratto.get("Durata", "12")) in DURATE_MESI
                    else 2
                )
            )

        desc = st.text_area(
            "🧾 Descrizione Prodotto",
            contratto.get("DescrizioneProdotto", "") if not is_new else "",
            height=100
        )

        colp1, colp2, colp3 = st.columns(3)
        with colp1:
            nf = st.text_input("🏦 NOL_FIN", contratto.get("NOL_FIN", "") if not is_new else "")
        with colp2:
            ni = st.text_input("🏢 NOL_INT", contratto.get("NOL_INT", "") if not is_new else "")
        with colp3:
            tot = st.text_input("💰 Tot Rata", contratto.get("TotRata", "") if not is_new else "")

        colx1, colx2, colx3, colx4 = st.columns(4)
        with colx1:
            copie_bn = st.text_input("📄 Copie incluse B/N", contratto.get("CopieBN", "") if not is_new else "")
        with colx2:
            ecc_bn = st.text_input("💶 Costo extra B/N (€)", contratto.get("EccBN", "") if not is_new else "")
        with colx3:
            copie_col = st.text_input("🖨️ Copie incluse Colore", contratto.get("CopieCol", "") if not is_new else "")
        with colx4:
            ecc_col = st.text_input("💶 Costo extra Colore (€)", contratto.get("EccCol", "") if not is_new else "")

        stato = st.selectbox(
            "🟢 Stato Contratto",
            ["aperto", "chiuso"],
            index=0 if is_new or str(contratto.get("Stato", "")).lower() != "chiuso" else 1
        )

        st.markdown("---")

        cbtn1, cbtn2, cbtn3 = st.columns([1, 1, 2])
        with cbtn1:
            salva = st.form_submit_button("💾 Salva", use_container_width=True, disabled=permessi_limitati)
        with cbtn2:
            annulla = st.form_submit_button("❌ Chiudi", use_container_width=True)

    # === LOGICA SALVATAGGIO ===
    if salva:
        try:
            if is_new:
                new_num = str(len(df_ct) + 1)
                new_contratto = {
                    "ClienteID": st.session_state.get("selected_cliente", ""),
                    "RagioneSociale": rag_soc,
                    "NumeroContratto": new_num,
                    "DataInizio": fmt_date(din),
                    "DataFine": fmt_date(dfi),
                    "Durata": durata,
                    "DescrizioneProdotto": desc,
                    "NOL_FIN": nf,
                    "NOL_INT": ni,
                    "TotRata": tot,
                    "CopieBN": copie_bn,
                    "EccBN": ecc_bn,
                    "CopieCol": copie_col,
                    "EccCol": ecc_col,
                    "Stato": stato
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([new_contratto])], ignore_index=True)
                save_contratti(df_ct)
                st.success(f"✅ Nuovo contratto creato correttamente ({rag_soc}).")

            else:
                idx = df_ct.index[df_ct["NumeroContratto"] == numero]
                if len(idx) == 0:
                    st.error("Contratto non trovato nel DataFrame.")
                    return
                i = idx[0]
                df_ct.loc[i, "DataInizio"] = fmt_date(din)
                df_ct.loc[i, "DataFine"] = fmt_date(dfi)
                df_ct.loc[i, "Durata"] = durata
                df_ct.loc[i, "DescrizioneProdotto"] = desc
                df_ct.loc[i, "NOL_FIN"] = nf
                df_ct.loc[i, "NOL_INT"] = ni
                df_ct.loc[i, "TotRata"] = tot
                df_ct.loc[i, "CopieBN"] = copie_bn
                df_ct.loc[i, "EccBN"] = ecc_bn
                df_ct.loc[i, "CopieCol"] = copie_col
                df_ct.loc[i, "EccCol"] = ecc_col
                df_ct.loc[i, "Stato"] = stato
                save_contratti(df_ct)
                st.success(f"✅ Contratto {numero} aggiornato correttamente.")

            time.sleep(0.4)
            st.session_state.pop("open_modal", None)
            st.session_state.pop("selected_contratto", None)
            st.query_params.clear()
            st.rerun()

        except Exception as e:
            st.error(f"❌ Errore durante il salvataggio: {e}")

    elif annulla:
        st.session_state.pop("open_modal", None)
        st.session_state.pop("selected_contratto", None)
        st.query_params.clear()
        st.rerun()

# =====================================
# FUNZIONI DI ESPORTAZIONE (Excel + PDF)
# =====================================
def export_excel_contratti(df_ct, sel_id, rag_soc):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    disp = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Contratti {rag_soc}"
    ws.merge_cells("A1:M1")
    title = ws["A1"]
    title.value = f"Contratti Cliente: {rag_soc}"
    title.font = Font(size=14, bold=True, color="2563EB")
    title.alignment = Alignment(horizontal="center")

    headers = ["NumeroContratto", "DataInizio", "DataFine", "Durata", "DescrizioneProdotto",
               "NOL_FIN", "NOL_INT", "TotRata", "CopieBN", "EccBN", "CopieCol", "EccCol", "Stato"]
    ws.append(headers)

    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="2563EB")
    center = Alignment(horizontal="center", wrap_text=True)
    thin = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

    for i, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=i)
        c.font = head_font; c.fill = head_fill; c.alignment = center; c.border = thin

    for _, row in disp.iterrows():
        ws.append([str(row.get(h, "")) for h in headers])
        stato = str(row.get("Stato", "")).lower()
        r_idx = ws.max_row
        for j in range(1, len(headers)+1):
            cell = ws.cell(row=r_idx, column=j)
            cell.alignment = center
            cell.border = thin
            if stato == "chiuso":
                cell.fill = PatternFill("solid", fgColor="FFCDD2")

    for i in range(1, len(headers)+1):
        ws.column_dimensions[get_column_letter(i)].width = 25

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def export_pdf_contratti(df_ct, sel_id, rag_soc):
    from fpdf import FPDF
    disp = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    headers = ["NumeroContratto", "DataInizio", "DataFine", "Durata", "TotRata", "Stato"]
    widths = [30, 25, 25, 15, 25, 20]

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, safe_text(f"Contratti Cliente: {rag_soc}"), ln=1, align="C")
    pdf.set_font("Arial", "B", 10)
    for i, h in enumerate(headers):
        pdf.cell(widths[i], 8, safe_text(h), 1, 0, "C", True)
    pdf.ln()
    pdf.set_font("Arial", "", 9)
    for _, r in disp.iterrows():
        for i, h in enumerate(headers):
            stato = str(r.get("Stato", "")).lower()
            if stato == "chiuso":
                pdf.set_fill_color(255, 235, 238)
                pdf.cell(widths[i], 7, safe_text(r.get(h, "")), 1, 0, "C", fill=True)
            else:
                pdf.cell(widths[i], 7, safe_text(r.get(h, "")), 1, 0, "C")
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1", errors="replace")

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
# 📇 PAGINA LISTA COMPLETA CLIENTI E SCADENZE (CON FILTRO TMK)
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Scadenze Contratti")
    oggi = pd.Timestamp.now().normalize()

    # === Prepara i dati contratti ===
    df_ct = df_ct.copy()
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    df_ct["Stato"] = df_ct["Stato"].astype(str).str.lower().fillna("")
    attivi = df_ct[df_ct["Stato"] != "chiuso"]

    # === Calcola la prima scadenza per ogni cliente ===
    prime_scadenze = (
        attivi.groupby("ClienteID")["DataFine"]
        .min()
        .reset_index()
        .rename(columns={"DataFine": "PrimaScadenza"})
    )

    merged = df_cli.merge(prime_scadenze, on="ClienteID", how="left")
    merged["GiorniMancanti"] = (merged["PrimaScadenza"] - oggi).dt.days

    # === Badge colorati per scadenza ===
    def badge_scadenza(row):
        if pd.isna(row["PrimaScadenza"]):
            return "<span style='color:#999;'>⚪ Nessuna</span>"
        giorni = row["GiorniMancanti"]
        data_fmt = fmt_date(row["PrimaScadenza"])
        if giorni < 0:
            return f"<span style='color:#757575;font-weight:600;'>⚫ Scaduto ({data_fmt})</span>"
        elif giorni <= 30:
            return f"<span style='color:#d32f2f;font-weight:600;'>🔴 {data_fmt}</span>"
        elif giorni <= 90:
            return f"<span style='color:#f9a825;font-weight:600;'>🟡 {data_fmt}</span>"
        else:
            return f"<span style='color:#388e3c;font-weight:600;'>🟢 {data_fmt}</span>"

    merged["ScadenzaBadge"] = merged.apply(badge_scadenza, axis=1)

    # === FILTRI PRINCIPALI ===
    st.markdown("### 🔍 Filtri")
    col1, col2, col3, col4, col5 = st.columns([1.5, 1.5, 1.5, 1.5, 1.5])

    filtro_nome = col1.text_input("Cerca per nome cliente")
    filtro_citta = col2.text_input("Cerca per città")
    tmk_options = ["Tutti", "Giulia", "Antonella", "Annalisa", "Laura"]
    filtro_tmk = col3.selectbox("Filtra per TMK", tmk_options, index=0)
    data_da = col4.date_input("Da data scadenza:", value=None, format="DD/MM/YYYY")
    data_a = col5.date_input("A data scadenza:", value=None, format="DD/MM/YYYY")

    # === Applica filtri ===
    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]
    if filtro_tmk != "Tutti":
        merged = merged[merged["TMK"] == filtro_tmk]
    if data_da:
        merged = merged[merged["PrimaScadenza"] >= pd.Timestamp(data_da)]
    if data_a:
        merged = merged[merged["PrimaScadenza"] <= pd.Timestamp(data_a)]

    # === RIEPILOGO NUMERICO ===
    total_clienti = len(merged)
    entro_30 = (merged["GiorniMancanti"] <= 30).sum()
    entro_90 = ((merged["GiorniMancanti"] > 30) & (merged["GiorniMancanti"] <= 90)).sum()
    oltre_90 = (merged["GiorniMancanti"] > 90).sum()
    scaduti = (merged["GiorniMancanti"] < 0).sum()
    senza_scadenza = merged["PrimaScadenza"].isna().sum()

    st.markdown(f"""
    **Totale Clienti:** {total_clienti}  
    ⚫ **Scaduti:** {scaduti}  
    🔴 **Entro 30 giorni:** {entro_30}  
    🟡 **Entro 90 giorni:** {entro_90}  
    🟢 **Oltre 90 giorni:** {oltre_90}  
    ⚪ **Senza scadenza:** {senza_scadenza}
    """)

    # === ORDINAMENTO ===
    st.markdown("### ↕️ Ordinamento elenco")
    ord_col1, ord_col2 = st.columns(2)
    sort_mode = ord_col1.radio(
        "Ordina per:",
        ["Nome Cliente (A → Z)", "Nome Cliente (Z → A)", "Data Scadenza (più vicina)", "Data Scadenza (più lontana)"],
        horizontal=True,
        key="sort_lista_clienti"
    )

    if sort_mode == "Nome Cliente (A → Z)":
        merged = merged.sort_values("RagioneSociale", ascending=True)
    elif sort_mode == "Nome Cliente (Z → A)":
        merged = merged.sort_values("RagioneSociale", ascending=False)
    elif sort_mode == "Data Scadenza (più vicina)":
        merged = merged.sort_values("PrimaScadenza", ascending=True, na_position="last")
    elif sort_mode == "Data Scadenza (più lontana)":
        merged = merged.sort_values("PrimaScadenza", ascending=False, na_position="last")

    # === VISUALIZZAZIONE ===
    st.divider()
    st.markdown("### 📇 Elenco Clienti e Scadenze")

    if merged.empty:
        st.warning("❌ Nessun cliente trovato con i criteri selezionati.")
        return

    for i, r in merged.iterrows():
        c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.2, 1.2, 0.7])
        with c1:
            st.markdown(f"**{r['RagioneSociale']}**")
        with c2:
            st.markdown(r.get("Citta", "") or "—")
        with c3:
            st.markdown(r["ScadenzaBadge"], unsafe_allow_html=True)
        with c4:
            tmk = r.get("TMK", "")
            if tmk:
                st.markdown(f"<span style='background:#e3f2fd;color:#0d47a1;padding:3px 8px;border-radius:8px;font-weight:600;'>{tmk}</span>", unsafe_allow_html=True)
            else:
                st.markdown("—")
        with c5:
            if st.button("📂 Apri", key=f"apri_cli_{i}", use_container_width=True):
                st.session_state.update({
                    "selected_cliente": str(r["ClienteID"]),
                    "nav_target": "Clienti",
                    "_go_clienti_now": True,
                    "_force_scroll_top": True
                })
                st.rerun()

    st.caption(f"📋 Totale clienti mostrati: **{len(merged)}**")

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
    global LOGO_URL  # 🔹 rende disponibile la variabile globale all’interno di main()
    
    # --- LOGIN ---
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    # 🔁 Riavvia thread sync se non attivo
    if "sync_thread_started" not in st.session_state:
        t = threading.Thread(target=sync_supabase_periodico, daemon=True)
        t.start()
        st.session_state["sync_thread_started"] = True

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
    elif user in ["giulia", "antonella"]:
        ruolo_scrittura = "limitato"
    elif user in ["gabriele", "laura", "annalisa"]:
        ruolo_scrittura = "limitato"
    else:
        ruolo_scrittura = "limitato"

    # --- Selettore visibilità (solo per Fabio, Giulia, Antonella) ---
    if user in ["fabio", "giulia", "antonella"]:
        default_view = "Miei"
        visibilita_opzioni = ["Miei", "Gabriele", "Tutti"]
        visibilita_scelta = st.sidebar.radio(
            "📂 Visualizza clienti di:",
            visibilita_opzioni,
            index=visibilita_opzioni.index(default_view)
        )
    else:
        visibilita_scelta = "Miei"

    
    # --- Caricamento dati base (da Supabase o CSV in fallback) ---
    try:
        if st.session_state.get("logged_in") and "user" in st.session_state:
            user = st.session_state["user"]
            df_cli_main, df_ct_main = carica_dati_supabase(user)
            
            # Se Supabase restituisce vuoto (es. prima connessione), fallback ai CSV locali
            if df_cli_main.empty or df_ct_main.empty:
                df_cli_main, df_ct_main = load_clienti(), load_contratti()
        else:
            df_cli_main, df_ct_main = load_clienti(), load_contratti()
    except Exception as e:
        st.warning(f"⚠️ Errore caricamento da Supabase, uso CSV locali: {e}")
        df_cli_main, df_ct_main = load_clienti(), load_contratti()


    # --- Caricamento CSV Gabriele (robusto) ---
    try:
        if gabriele_clienti.exists():
            df_cli_gab = pd.read_csv(
                gabriele_clienti,
                dtype=str,
                sep=None,
                engine="python",
                encoding="utf-8-sig",
                on_bad_lines="skip"
            ).fillna("")
        else:
            df_cli_gab = pd.DataFrame(columns=CLIENTI_COLS)

        if gabriele_contratti.exists():
            df_ct_gab = pd.read_csv(
                gabriele_contratti,
                dtype=str,
                sep=None,
                engine="python",
                encoding="utf-8-sig",
                on_bad_lines="skip"
            ).fillna("")
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
    else:  # Tutti
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

    # --- Passaggio info ai moduli ---
    st.session_state["ruolo_scrittura"] = ruolo_scrittura
    st.session_state["visibilita"] = visibilita_scelta

    # --- Pagine ---
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti,
    }

    # --- Menu ---
    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()), index=0)

    # --- Navigazione automatica da pulsanti interni ---
    if "nav_target" in st.session_state:
        target = st.session_state.pop("nav_target")
        if target in PAGES:
            page = target

    # --- Esegui pagina ---
    if page in PAGES:
        PAGES[page](df_cli, df_ct, ruolo_scrittura)

# =====================================
# 🔧 UTILITÀ AMMINISTRATIVE
# =====================================
if st.sidebar.button("🛠️ Correggi owner su Supabase (solo admin)"):
    user = st.session_state.get("user", "")
    if user.lower() == "fabio":
        fix_supabase_owner(user)
    else:
        st.sidebar.warning("⚠️ Solo l'admin può eseguire questa operazione.")

# =====================================
# AVVIO APPLICAZIONE
# =====================================
if "main" in globals():
    main()

