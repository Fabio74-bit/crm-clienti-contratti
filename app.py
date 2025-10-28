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
# CONFIGURAZIONE STREAMLIT E STILE BASE
# =====================================
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

st.markdown("""
<style>
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}
section.main > div:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<script>
    window.addEventListener('load', function() {
        window.scrollTo(0, 0);
    });
</script>
""", unsafe_allow_html=True)

# =====================================
# COSTANTI GLOBALI (VERSIONE GITHUB + STREAMLIT CLOUD)
# =====================================

APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

# Percorsi base relativi (funziona su GitHub e Streamlit Cloud)
STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# File CSV principali
CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti.csv"

# Cartella e file per Gabriele
GABRIELE_DIR = STORAGE_DIR / "gabriele"
GABRIELE_DIR.mkdir(parents=True, exist_ok=True)
GABRIELE_CLIENTI = GABRIELE_DIR / "clienti.csv"
GABRIELE_CONTRATTI = GABRIELE_DIR / "contratti.csv"

# Cartella preventivi
PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)

# Cartella template preventivi
TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_OPTIONS = {
    "Offerta A4": "Offerta_A4.docx",
    "Offerta A3": "Offerta_A3.docx",
    "Centralino": "Offerta_Centralino.docx",
    "Varie": "Offerta_Varie.docx",
}

# Durate standard contratti
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
    """Carica i dati dei clienti dal file CSV (supporta ; , |)"""
    import pandas as pd
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=CLIENTI_COLS)

    for sep_try in [";", ",", "|", "\t"]:
        try:
            df = pd.read_csv(
                CLIENTI_CSV,
                dtype=str,
                sep=sep_try,
                encoding="utf-8-sig",
                on_bad_lines="skip",
                engine="python"
            ).fillna("")
            if len(df.columns) > 3:
                break
        except Exception:
            continue

    df = ensure_columns(df, CLIENTI_COLS)
    return df



# =====================================
# CARICAMENTO CONTRATTI (senza salvataggio automatico)
# =====================================
def load_contratti() -> pd.DataFrame:
    """Carica i dati dei contratti (supporta ; , |)"""
    import pandas as pd
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=CONTRATTI_COLS)

    for sep_try in [";", ",", "|", "\t"]:
        try:
            df = pd.read_csv(
                CONTRATTI_CSV,
                dtype=str,
                sep=sep_try,
                encoding="utf-8-sig",
                on_bad_lines="skip",
                engine="python"
            ).fillna("")
            if len(df.columns) > 3:
                break
        except Exception:
            continue

    df = ensure_columns(df, CONTRATTI_COLS)
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
# LOGIN FULLSCREEN
# =====================================
def do_login_fullscreen():
    """Login elegante con sfondo fullscreen"""
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

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

    login_col1, login_col2, _ = st.columns([1, 2, 1])
    with login_col2:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.image(LOGO_URL, width=140)
        st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)
        username = st.text_input("Nome utente", key="login_user").strip().lower()
        password = st.text_input("Password", type="password", key="login_pass")
        login_btn = st.button("Entra")
        st.markdown("</div>", unsafe_allow_html=True)

    # 🔹 Carica credenziali compatibili con formato Streamlit Cloud
    try:
        users = st.secrets["auth"]["users"]
    except Exception:
        # compatibilità con sottosezioni [auth.users.nome]
        users = st.secrets["auth"]["users"].to_dict() if hasattr(st.secrets["auth"]["users"], "to_dict") else st.secrets["auth"]["users"]
        if not users:
            users = {}
        # 🔹 costruisci manualmente il dizionario
        for k in st.secrets["auth"]["users"]:
            users[k] = st.secrets["auth"]["users"][k]

    if login_btn or (username and password and not st.session_state.get("_login_checked")):
        st.session_state["_login_checked"] = True

        # 🔹 compatibile con [auth.users.nome]
        if "auth" in st.secrets and "users" in st.secrets["auth"]:
            users = st.secrets["auth"]["users"]
        else:
            users = st.secrets.get("auth.users", {})

        # 🔹 login check
        if username in users and users[username]["password"] == password:
            st.session_state.update({
                "user": username,
                "role": users[username].get("role", "viewer"),
                "logged_in": True
            })
            st.success(f"✅ Benvenuto {username}!")
            time.sleep(0.3)
            st.rerun()
        else:
            st.error("❌ Credenziali non valide.")
            st.session_state["_login_checked"] = False

    st.stop()

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
# PAGINA DASHBOARD (CLASSICA con TMK e gestione Fabio/Gabriele)
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📊 Dashboard Gestionale</h2>", unsafe_allow_html=True)
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

    # === CREAZIONE NUOVO CLIENTE + CONTRATTO ===
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

            colx1, colx2, colx3, colx4 = st.columns(4)
            with colx1:
                copie_bn = st.text_input("📄 Copie incluse B/N", value="", key="copie_bn")
            with colx2:
                ecc_bn = st.text_input("💰 Costo extra B/N (€)", value="", key="ecc_bn")
            with colx3:
                copie_col = st.text_input("🖨️ Copie incluse Colore", value="", key="copie_col")
            with colx4:
                ecc_col = st.text_input("💰 Costo extra Colore (€)", value="", key="ecc_col")

            # === SALVATAGGIO COMPLETO ===
            if st.form_submit_button("💾 Crea Cliente e Contratto"):
                try:
                    new_id = str(len(df_cli) + 1)
                    data_fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))

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

                    # --- Scelta automatica file in base all'utente ---
                    user = st.session_state.get("user", "").lower()
                    if user == "gabriele":
                        path_cli = GABRIELE_CLIENTI
                        path_ct = GABRIELE_CONTRATTI
                    else:
                        path_cli = CLIENTI_CSV
                        path_ct = CONTRATTI_CSV

                    # --- Aggiorna CSV ---
                    if path_cli.exists():
                        df_exist = pd.read_csv(path_cli, dtype=str, encoding="utf-8-sig", on_bad_lines="skip").fillna("")
                    else:
                        df_exist = pd.DataFrame(columns=df_cli.columns)
                    df_exist = pd.concat([df_exist, pd.DataFrame([nuovo_cliente])], ignore_index=True)
                    df_exist.to_csv(path_cli, index=False, encoding="utf-8-sig")

                    if path_ct.exists():
                        df_ct_exist = pd.read_csv(path_ct, dtype=str, encoding="utf-8-sig", on_bad_lines="skip").fillna("")
                    else:
                        df_ct_exist = pd.DataFrame(columns=df_ct.columns)
                    df_ct_exist = pd.concat([df_ct_exist, pd.DataFrame([nuovo_contratto])], ignore_index=True)
                    df_ct_exist.to_csv(path_ct, index=False, encoding="utf-8-sig")

                    st.success(f"✅ Cliente '{ragione}' creato e salvato correttamente ({user.upper()})")
                    st.session_state.update({
                        "selected_cliente": new_id,
                        "nav_target": "Contratti",
                        "_go_contratti_now": True
                    })
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore creazione cliente: {e}")

    # === CONTRATTI IN SCADENZA ENTRO 6 MESI ===
    st.divider()
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

    if not scadenze.empty and "RagioneSociale" not in scadenze.columns:
        scadenze = scadenze.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")

    if scadenze.empty:
        st.success("✅ Nessun contratto attivo in scadenza nei prossimi 6 mesi.")
    else:
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        scadenze = scadenze.sort_values("DataFine")
        st.markdown(f"📅 **{len(scadenze)} contratti in scadenza entro 6 mesi:**")
        head_cols = st.columns([2, 1, 1, 1, 0.8])
        head_cols[0].markdown("**Cliente**")
        head_cols[1].markdown("**Contratto**")
        head_cols[2].markdown("**Scadenza**")
        head_cols[3].markdown("**Stato**")
        head_cols[4].markdown("**Azioni**")
        st.markdown("---")

        for i, r in scadenze.iterrows():
            bg_color = "#f8fbff" if i % 2 == 0 else "#ffffff"
            # normalizzo l'ID da inviare
            raw_id = str(r.get("ClienteID", "")).strip()
            cliente_id_norm = raw_id.lstrip("0").upper()
        
            cols = st.columns([2, 1, 1, 1, 0.8])
            with cols[0]:
                st.markdown(f"<div style='background:{bg_color};padding:6px'><b>{r.get('RagioneSociale','—')}</b></div>", unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f"<div style='background:{bg_color};padding:6px'>{r.get('NumeroContratto','—')}</div>", unsafe_allow_html=True)
            with cols[2]:
                st.markdown(f"<div style='background:{bg_color};padding:6px'>{fmt_date(r.get('DataFine'))}</div>", unsafe_allow_html=True)
            with cols[3]:
                st.markdown(f"<div style='background:{bg_color};padding:6px'>{r.get('Stato','—')}</div>", unsafe_allow_html=True)
            with cols[4]:
                if st.button("📂 Apri", key=f"open_scad_{cliente_id_norm}_{i}", use_container_width=True):
                    if cliente_id_norm:
                        st.session_state["selected_cliente"] = cliente_id_norm
                        st.session_state["nav_target"] = "Contratti"
                        st.session_state["_go_contratti_now"] = True
                        st.rerun()
                    else:
                        st.warning("⚠️ ID cliente non valido per questo contratto.")


    # === CONTRATTI RECENTI SENZA DATA FINE ===
    st.divider()
    st.markdown("### ⚠️ Contratti recenti senza data di fine")

    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    oggi = pd.Timestamp.now().normalize()

    contratti_senza_fine = df_ct[
        (df_ct["DataFine"].isna()) &
        (df_ct["DataInizio"].notna()) &
        (df_ct["DataInizio"] >= oggi)
    ].copy()

    if contratti_senza_fine.empty:
        st.success("✅ Tutti i contratti recenti hanno una data di fine.")
    else:
        st.warning(f"⚠️ {len(contratti_senza_fine)} contratti inseriti da oggi non hanno ancora una data di fine:")
        if "RagioneSociale" not in contratti_senza_fine.columns:
            contratti_senza_fine = contratti_senza_fine.merge(
                df_cli[["ClienteID", "RagioneSociale"]],
                on="ClienteID", how="left"
            )

        contratti_senza_fine["DataInizio"] = contratti_senza_fine["DataInizio"].apply(fmt_date)
        contratti_senza_fine = contratti_senza_fine.sort_values("DataInizio", ascending=False)

        for i, r in contratti_senza_fine.iterrows():
            # normalizzo l'ID da inviare
            raw_id = str(r.get("ClienteID", "")).strip()
            cliente_id_norm = raw_id.lstrip("0").upper()
        
            col1, col2, col3, col4, col5 = st.columns([2.5, 1, 1.2, 2.5, 0.8])
            with col1:
                st.markdown(f"**{r.get('RagioneSociale', '—')}**")
                st.markdown(r.get("NumeroContratto", "—"))
            with col3:
                st.markdown(r.get("DataInizio", "—"))
            with col4:
                desc = str(r.get("DescrizioneProdotto", "—"))
                if len(desc) > 60:
                    desc = desc[:60] + "…"
                st.markdown(desc)
            with col5:
                if st.button("📂 Apri", key=f"open_ndf_{cliente_id_norm}_{i}", use_container_width=True):
                    if cliente_id_norm:
                        st.session_state["selected_cliente"] = cliente_id_norm
                        st.session_state["nav_target"] = "Contratti"
                        st.session_state["_go_contratti_now"] = True
                        st.rerun()
                    else:
                        st.warning("⚠️ ID cliente non valido per questo contratto.")




# =====================================
# PAGINA CLIENTI (VERSIONE COMPLETA CON NOTE E RECALL VICINI)
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Gestione Clienti")

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

    # === HEADER CLIENTE ===
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
            st.rerun()

        # === CANCELLA CLIENTE (chiede conferma) ===
        if st.button("🗑️ Cancella Cliente", use_container_width=True, key=f"ask_del_{sel_id}"):
            st.session_state["confirm_delete_cliente"] = str(sel_id)
            st.rerun()

    # === BLOCCO CONFERMA CANCELLAZIONE ===
    if st.session_state.get("confirm_delete_cliente") == str(sel_id):
        st.warning(
            f"⚠️ Eliminare definitivamente **{cliente['RagioneSociale']}** (ID {sel_id}) "
            f"e tutti i contratti associati?"
        )
        cdel1, cdel2 = st.columns(2)
        with cdel1:
            if st.button("✅ Sì, elimina", use_container_width=True, key=f"do_del_{sel_id}"):
                try:
                    df_cli_new = df_cli[df_cli["ClienteID"].astype(str) != str(sel_id)].copy()
                    df_ct_new = df_ct[df_ct["ClienteID"].astype(str) != str(sel_id)].copy()
                    df_cli_new.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
                    df_ct_new.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
                    st.cache_data.clear()
                    st.session_state.pop("confirm_delete_cliente", None)
                    st.success("🗑️ Cliente e contratti eliminati con successo! ✅")
                    time.sleep(0.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore durante l'eliminazione: {e}")
        with cdel2:
            if st.button("❌ Annulla", use_container_width=True, key=f"undo_del_{sel_id}"):
                st.session_state.pop("confirm_delete_cliente", None)
                st.info("Operazione annullata.")
                st.rerun()

    # === INFO RAPIDE ANAGRAFICA ===
    st.markdown(
        f"""
        <div style='font-size:15px; line-height:1.7;'>
        <b>📍 Indirizzo:</b> {cliente.get('Indirizzo','')} — {cliente.get('Citta','')} {cliente.get('CAP','')}<br>
        <b>🧑‍💼 Referente:</b> {cliente.get('PersonaRiferimento','')}<br>
        <b>📞 Telefono:</b> {cliente.get('Telefono','')} — <b>📱 Cell:</b> {cliente.get('Cell','')}
        </div>
        """,
        unsafe_allow_html=True
    )

    # === NOTE CLIENTE subito sotto anagrafica ===
    st.divider()
    st.markdown("### 📝 Note Cliente")
    st.caption("Annotazioni o informazioni utili sul cliente (visibili a tutti gli utenti).")

    note_attuali = cliente.get("NoteCliente", "")
    nuove_note = st.text_area(
        "Scrivi o modifica le note del cliente:",
        note_attuali,
        height=160,
        key=f"note_{sel_id}_{int(time.time()*1000)}"
    )

    c1, c2 = st.columns([0.25, 0.75])
    with c1:
        if st.button("💾 Salva Note", use_container_width=True, key=f"save_note_{sel_id}"):
            try:
                idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx_row, "NoteCliente"] = nuove_note
                save_clienti(df_cli)
                st.success("✅ Note salvate correttamente.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante il salvataggio: {e}")
    with c2:
        st.info("Le modifiche vengono salvate immediatamente nel file clienti.csv")

    # === RECALL E VISITE subito dopo le note ===
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

    uniq = f"{sel_id}_{int(time.time()*1000)}"
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

    # === GENERA PREVENTIVO E ELENCO (come prima) ===
    st.divider()
    st.markdown("### 🧾 Genera Nuovo Preventivo")

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
            mappa = {
                "CLIENTE": nome_cliente,
                "INDIRIZZO": cliente.get("Indirizzo", ""),
                "CITTA": cliente.get("Citta", ""),
                "NUMERO_OFFERTA": num_off,
                "DATA": datetime.now().strftime("%d/%m/%Y"),
                "ULTIMO_RECALL": fmt_date(cliente.get("UltimoRecall")),
                "PROSSIMO_RECALL": fmt_date(cliente.get("ProssimoRecall")),
                "ULTIMA_VISITA": fmt_date(cliente.get("UltimaVisita")),
                "PROSSIMA_VISITA": fmt_date(cliente.get("ProssimaVisita")),
            }

            for p in doc.paragraphs:
                for k, v in mappa.items():
                    if f"<<{k}>>" in p.text:
                        for run in p.runs:
                            run.text = run.text.replace(f"<<{k}>>", str(v))

            out_path = PREVENTIVI_DIR / nome_file
            doc.save(out_path)

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
        prev_cli = prev_cli.sort_values("DataCreazione", ascending=False)
        for i, r in prev_cli.iterrows():
            file_path = Path(r["Percorso"])
            col1, col2, col3 = st.columns([0.6, 0.25, 0.15])
            with col1:
                st.markdown(f"**{r['NumeroOfferta']}** — {r['Template']}  \n📅 {r['DataCreazione']}")
            with col2:
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "⬇️ Scarica", f.read(),
                            file_name=file_path.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{sel_id}_{i}_{int(time.time()*1000)}"
                        )
            with col3:
                if role == "admin":
                    if st.button("🗑 Elimina", key=f"del_prev_{sel_id}_{i}_{int(time.time()*1000)}"):
                        try:
                            if file_path.exists():
                                file_path.unlink()
                            df_prev = df_prev.drop(i)
                            df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
                            st.success("🗑 Preventivo eliminato.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Errore eliminazione: {e}")


# =====================================
# PAGINA CONTRATTI — VERSIONE 2025 “GRAFICA PULITA ESTESA STREAMLIT”
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # === FIX NAVIGAZIONE DA DASHBOARD ===
    if "selected_cliente" in st.session_state:
        sel = str(st.session_state.get("selected_cliente", "")).strip()
        # correzione zeri/spazi per ID
        sel_clean = sel.lstrip("0").strip()
        st.session_state["selected_cliente"] = sel_clean


    ruolo_scrittura = st.session_state.get("ruolo_scrittura", role)
    permessi_limitati = ruolo_scrittura == "limitato"

    st.markdown("## 📄 Gestione Contratti")

    # === SELEZIONE CLIENTE (con navigazione corretta da Dashboard) ===
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return
    
    # Etichette e ID originali
    clienti_labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1).tolist()
    clienti_ids_raw = df_cli["ClienteID"].astype(str).tolist()
    
    # Versione normalizzata per confronto
    clienti_ids_norm = [cid.strip().lstrip("0").upper() for cid in clienti_ids_raw]
    
    # Recupero eventuale selezione arrivata da Dashboard
    selected_cliente_id = st.session_state.pop("selected_cliente", None)
    sel_index = 0
    if selected_cliente_id is not None:
        key = str(selected_cliente_id).strip().lstrip("0").upper()
        if key in clienti_ids_norm:
            sel_index = clienti_ids_norm.index(key)
        else:
            sel_index = 0  # fallback se non trovato
    
    # Combo box per scelta cliente
    sel_label = st.selectbox("Seleziona Cliente", clienti_labels, index=sel_index)
    sel_index_final = clienti_labels.index(sel_label)
    sel_id = clienti_ids_raw[sel_index_final]
    rag_soc = df_cli.iloc[sel_index_final]["RagioneSociale"]

    # === Header e pulsante aggiunta ===
    st.markdown(
        f"""
        <div style='display:flex;align-items:center;justify-content:space-between;margin-top:10px;margin-bottom:20px;'>
            <h3 style='margin:0;color:#2563eb;'>🏢 {rag_soc}</h3>
        </div>
        """, unsafe_allow_html=True
    )

    if not permessi_limitati:
        if st.button("➕ Aggiungi Contratto", use_container_width=False, key="btn_add_contract"):
            st.session_state["open_modal"] = "new"
            st.rerun()

    # === Filtra contratti del cliente ===
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto registrato per questo cliente.")
        return

    # === Formatta dati ===
    for c in ["DataInizio", "DataFine"]:
        ct[c] = ct[c].apply(fmt_date)
    ct["TotRata"] = ct["TotRata"].apply(money)
    ct["NOL_FIN"] = ct["NOL_FIN"].apply(money)
    ct["NOL_INT"] = ct["NOL_INT"].apply(money)

    # === Stile tabella (estesa) ===
    st.markdown("""
    <style>
      .tbl-wrapper { overflow-x:auto; }
      .tbl-container {
          border:1px solid #e0e0e0; border-radius:10px; overflow:hidden;
          box-shadow:0 2px 6px rgba(0,0,0,0.05); min-width:1400px;
      }
      .tbl-header, .tbl-row {
          display:grid;
          grid-template-columns: 
            1.1fr 0.9fr 0.9fr 0.6fr 0.9fr 1.2fr 0.8fr 0.8fr 0.8fr 0.8fr 0.9fr 0.9fr 0.8fr 0.9fr;
          padding:8px 14px; font-size:14px; align-items:center;
      }
      .tbl-header { background:#f8fafc; font-weight:600; border-bottom:1px solid #e5e7eb; }
      .tbl-row:nth-child(even) { background:#ffffff; }
      .tbl-row:nth-child(odd) { background:#fdfdfd; }
      .tbl-row.chiuso { background:#ffebee !important; }
      .pill {
          display:inline-block; padding:2px 8px; border-radius:999px; font-weight:600; font-size:12px;
      }
      .pill-open { background:#e8f5e9; color:#1b5e20; }
      .pill-closed { background:#ffebee; color:#b71c1c; }
      .action-btn { border:none; border-radius:6px; padding:3px 6px; color:white; cursor:pointer; }
      .edit { background:#1976d2; }
      .del { background:#e53935; margin-left:6px; }
      .desc-clip { display:block; max-width:380px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='tbl-wrapper'><div class='tbl-container'>", unsafe_allow_html=True)
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
        """, unsafe_allow_html=True
    )

    # === Righe tabella (estese) ===
    for i, r in ct.iterrows():
        stato = str(r.get("Stato", "")).lower()
        bg_class = "chiuso" if stato == "chiuso" else ""
        numero = r.get("NumeroContratto", "—")
        din = r.get("DataInizio", "")
        dfi = r.get("DataFine", "")
        durata = r.get("Durata", "")
        tot = r.get("TotRata", "")
        desc = str(r.get("DescrizioneProdotto", "") or "—")
        desc_short = (desc[:80] + "…") if len(desc) > 80 else desc
        copie_bn = r.get("CopieBN", "")
        ecc_bn = r.get("EccBN", "")
        copie_col = r.get("CopieCol", "")
        ecc_col = r.get("EccCol", "")
        nfin = r.get("NOL_FIN", "")
        nint = r.get("NOL_INT", "")
        num_cont = r.get("NumeroContratto", "")

        # badge stato
        stato_badge = (
            "<span class='pill pill-closed'>Chiuso</span>" if stato == "chiuso"
            else "<span class='pill pill-open'>Aperto</span>"
        )

        # pulsanti azione
        btn_edit = ""
        btn_close = ""
        if not permessi_limitati:
            btn_edit = f"<button class='action-btn edit' onClick='window.location=\"?edit={num_cont}\"'>✏️</button>"
            btn_close = f"<button class='action-btn del' onClick='window.location=\"?close={num_cont}\"'>❌</button>"

        st.markdown(
            f"""
            <div class='tbl-row {bg_class}'>
                <div>{numero}</div>
                <div>{din}</div>
                <div>{dfi}</div>
                <div>{durata}</div>
                <div>{tot}</div>
                <div><span class='desc-clip' title="{desc.replace('"','&quot;')}">{desc_short}</span></div>
                <div>{copie_bn}</div>
                <div>{ecc_bn}</div>
                <div>{copie_col}</div>
                <div>{ecc_col}</div>
                <div>{nfin}</div>
                <div>{nint}</div>
                <div>{stato_badge}</div>
                <div style='text-align:center;'>{btn_edit} {btn_close}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("</div></div>", unsafe_allow_html=True)

    # === Gestione eventi ===
    query_params = st.query_params

    if "edit" in query_params and not permessi_limitati:
        num_cont = query_params["edit"]
        if isinstance(num_cont, list):
            num_cont = num_cont[0]
        contratto = df_ct[df_ct["NumeroContratto"] == num_cont]
        if not contratto.empty:
            contratto = contratto.iloc[0]
            show_contract_modal(contratto, df_ct, df_cli, rag_soc)
        else:
            st.warning("Contratto non trovato.")
        return

    if "close" in query_params and not permessi_limitati:
        num_cont = query_params["close"]
        if isinstance(num_cont, list):
            num_cont = num_cont[0]
        idx = df_ct.index[df_ct["NumeroContratto"] == num_cont]
        if len(idx) > 0:
            df_ct.loc[idx[0], "Stato"] = "chiuso"
            save_contratti(df_ct)
            st.success(f"✅ Contratto {num_cont} chiuso correttamente.")
            time.sleep(0.4)
            st.query_params.clear()
            st.rerun()

    # === Esportazioni ===
    st.markdown("---")
    st.markdown("### 📤 Esportazioni")

    cex1, cex2 = st.columns(2)
    with cex1:
        st.download_button(
            "📘 Esporta Excel",
            export_excel_contratti(df_ct, sel_id, rag_soc),
            file_name=f"Contratti_{rag_soc}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    with cex2:
        st.download_button(
            "📗 Esporta PDF",
            export_pdf_contratti(df_ct, sel_id, rag_soc),
            file_name=f"Contratti_{rag_soc}.pdf",
            mime="application/pdf",
            use_container_width=True
        )



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
# MAIN APP — versione 2025 GitHub + Streamlit Cloud (multi-proprietario)
# =====================================
def main():
    st.write("✅ Avvio CRM SHT — Buon Lavoro")

    # --- LOGIN (mostra schermata se non autenticato) ---
    if not st.session_state.get("logged_in", False):
        do_login_fullscreen()
        st.stop()

    user = st.session_state.get("user", "")
    role = st.session_state.get("role", "")

    if not user:
        st.warning("⚠️ Nessun utente loggato — ricarica la pagina.")
        st.stop()

    # --- Ruolo e diritti di scrittura ---
    if user == "fabio":
        ruolo_scrittura = "full"
    elif user in ["emanuela", "claudia"]:
        ruolo_scrittura = "full"
    elif user in ["giulia", "antonella", "gabriele", "laura", "annalisa"]:
        ruolo_scrittura = "limitato"
    else:
        ruolo_scrittura = "limitato"

    # --- Selettore visibilità ---
    if user in ["fabio", "giulia", "antonella", "emanuela", "claudia"]:
        visibilita_opzioni = ["Fabio", "Gabriele", "Tutti"]
        visibilita_scelta = st.sidebar.radio(
            "📂 Visualizza clienti di:",
            visibilita_opzioni,
            index=0
        )
    else:
        visibilita_scelta = "Fabio"

    # --- Caricamento dati base (Fabio) ---
    df_cli_main = load_clienti()
    df_ct_main = load_contratti()

        # --- Caricamento dati Gabriele ---
    try:
        if GABRIELE_CLIENTI.exists():
            for sep_try in [";", ",", "|", "\t"]:
                try:
                    df_cli_gab = pd.read_csv(
                        GABRIELE_CLIENTI,
                        dtype=str,
                        sep=sep_try,
                        encoding="utf-8-sig",
                        on_bad_lines="skip",
                        engine="python"
                    ).fillna("")
                    if len(df_cli_gab.columns) > 3:
                        break
                except Exception:
                    continue
        else:
            df_cli_gab = pd.DataFrame(columns=CLIENTI_COLS)

        if GABRIELE_CONTRATTI.exists():
            for sep_try in [";", ",", "|", "\t"]:
                try:
                    df_ct_gab = pd.read_csv(
                        GABRIELE_CONTRATTI,
                        dtype=str,
                        sep=sep_try,
                        encoding="utf-8-sig",
                        on_bad_lines="skip",
                        engine="python"
                    ).fillna("")
                    if len(df_ct_gab.columns) > 3:
                        break
                except Exception:
                    continue
        else:
            df_ct_gab = pd.DataFrame(columns=CONTRATTI_COLS)

        # 🔹 Correzione colonne mancanti (solo in memoria)
        df_cli_gab = ensure_columns(df_cli_gab, CLIENTI_COLS)
        df_ct_gab = ensure_columns(df_ct_gab, CONTRATTI_COLS)

    except Exception as e:
        st.warning(f"⚠️ Impossibile caricare i dati di Gabriele: {e}")
        df_cli_gab = pd.DataFrame(columns=CLIENTI_COLS)
        df_ct_gab = pd.DataFrame(columns=CONTRATTI_COLS)

    # --- Applica filtro visibilità ---
    if visibilita_scelta == "Fabio":
        df_cli, df_ct = df_cli_main, df_ct_main
    elif visibilita_scelta == "Gabriele":
        df_cli, df_ct = df_cli_gab, df_ct_gab
    else:
        df_cli = pd.concat([df_cli_main, df_cli_gab], ignore_index=True)
        df_ct = pd.concat([df_ct_main, df_ct_gab], ignore_index=True)

    # --- Correzione date automatica una sola volta ---
    df_cli, df_ct = fix_dates_once(df_cli, df_ct)

    # --- Sidebar info ---
    st.sidebar.success(f"👤 {user} — Ruolo: {role}")
    st.sidebar.info(f"📂 Vista: {visibilita_scelta}")

    # --- Salva contesto in sessione ---
    st.session_state["ruolo_scrittura"] = ruolo_scrittura
    st.session_state["visibilita"] = visibilita_scelta

    # --- Pagine principali ---
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti,
    }

    # --- Menu laterale ---
    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()), index=0)

    # --- Navigazione automatica (dai pulsanti interni) ---
    if "nav_target" in st.session_state:
        target = st.session_state.pop("nav_target")
        if target in PAGES:
            page = target

    # --- Esecuzione pagina selezionata ---
    if page in PAGES:
        st.session_state["utente_loggato"] = user
        PAGES[page](df_cli, df_ct, ruolo_scrittura)


# =====================================
# AVVIO APP
# =====================================
if __name__ == "__main__":
    main()
