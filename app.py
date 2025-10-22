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
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "NoteCliente"
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

    login_col1, login_col2, _ = st.columns([1,2,1])
    with login_col2:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.image(LOGO_URL, width=140)
        st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)
        username = st.text_input("Nome utente", key="login_user").strip().lower()
        password = st.text_input("Password", type="password", key="login_pass")
        login_btn = st.button("Entra")
        st.markdown("</div>", unsafe_allow_html=True)

    if login_btn or (username and password and not st.session_state.get("_login_checked")):
        st.session_state["_login_checked"] = True
        users = st.secrets["auth"]["users"]
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
# PAGINA DASHBOARD
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
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
# PAGINA CLIENTI (VERSIONE FINALE STABILE)
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

    # === INTESTAZIONE CLIENTE + PULSANTI COLORATI ===
    st.markdown("""
    <style>
    /* Pulsanti pastello */
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
    /* Card info rapide */
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

    # === HEADER CON PULSANTI ===
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
        st.caption(f"ID Cliente: {sel_id}")

    with col2:
        # Blu: Vai ai contratti
        st.markdown('<div class="btn-blue">', unsafe_allow_html=True)
        if st.button("📄 Vai ai Contratti", use_container_width=True, key=f"go_cont_{sel_id}"):
            st.session_state.update({
                "selected_cliente": sel_id,
                "nav_target": "Contratti",
                "_go_contratti_now": True
            })
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Giallo: Modifica anagrafica
        st.markdown('<div class="btn-yellow">', unsafe_allow_html=True)
        if st.button("✏️ Modifica Anagrafica", use_container_width=True, key=f"edit_{sel_id}"):
            st.session_state[f"edit_cli_{sel_id}"] = not st.session_state.get(f"edit_cli_{sel_id}", False)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # Rosso: Cancella cliente
        st.markdown('<div class="btn-red">', unsafe_allow_html=True)
        if st.button("🗑️ Cancella Cliente", use_container_width=True, key=f"ask_del_{sel_id}"):
            st.session_state["confirm_delete_cliente"] = str(sel_id)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # === INFO RAPIDE (NUOVO LAYOUT A DUE CARD) ===
    infoA, infoB = st.columns(2)
    with infoA:
        st.markdown(f"""
        <div class="info-box">
            <div class="info-title">📇 Dati Principali</div>
            <div class="info-item"><span class="info-label">👤 Referente:</span> {cliente.get('PersonaRiferimento','')}</div>
            <div class="info-item"><span class="info-label">✉️ Email:</span> {cliente.get('Email','')}</div>
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

            salva = st.form_submit_button("💾 Salva Modifiche")
            if salva:
                idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx, [
                    "Indirizzo", "Citta", "CAP", "Telefono", "Cell", "Email",
                    "PersonaRiferimento", "PartitaIVA", "IBAN", "SDI"
                ]] = [indirizzo, citta, cap, telefono, cell, email, persona, piva, iban, sdi]
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


    # === GENERA PREVENTIVO (VERSIONE PULITA E STABILE) ===
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
# PAGINA CONTRATTI — DASHBOARD ELEGANTE DEFINITIVA 2025
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # 🔹 Reset automatico session state
    for k in list(st.session_state.keys()):
        if k.startswith("edit_ct_"):
            del st.session_state[k]

    st.markdown("""
    <style>
      .card{background:#fff;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.06);padding:1.2rem 1.4rem;margin-bottom:1rem;}
      .card h3{color:#2563eb;margin:0 0 .8rem 0;}
      .pill-open{background:#e8f5e9;color:#1b5e20;padding:2px 8px;border-radius:8px;font-weight:600;}
      .pill-closed{background:#ffebee;color:#b71c1c;padding:2px 8px;border-radius:8px;font-weight:600;}
      .tbl-head{font-weight:700;border-bottom:1px solid #e5e7eb;padding:.4rem 0;margin-top:.2rem}
      .tbl-row{border-bottom:1px solid #f0f2f5;padding:.35rem 0;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<h2>📄 Gestione Contratti</h2>", unsafe_allow_html=True)

    # === Selezione Cliente ===
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    cliente_ids = df_cli["ClienteID"].astype(str).tolist()

    selected_cliente_id = st.session_state.pop("selected_cliente", None)
    if selected_cliente_id and str(selected_cliente_id) in cliente_ids:
        sel_index = cliente_ids.index(str(selected_cliente_id))
    else:
        sel_index = 0

    sel_label = st.selectbox("Seleziona Cliente", labels.tolist(), index=sel_index, key="sel_cliente_contratti")
    sel_id = cliente_ids[labels.tolist().index(sel_label)]
    rag_soc = df_cli.loc[df_cli["ClienteID"] == sel_id, "RagioneSociale"].iloc[0]

    st.markdown(
        f"<h3 style='text-align:center;color:#2563eb;margin-bottom:0;'>{rag_soc}</h3>"
        f"<p style='text-align:center;color:#555;'>ID Cliente: {sel_id}</p>",
        unsafe_allow_html=True
    )

    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    ct = ct.reset_index().rename(columns={"index": "_gidx"})

    # === EXPANDER: NUOVO CONTRATTO ===
    with st.expander("➕ Crea Nuovo Contratto", expanded=False):
        with st.form(f"frm_new_contract_{sel_id}"):
            c1, c2, c3, c4 = st.columns(4)
            num = c1.text_input("Numero Contratto")
            din = c2.date_input("Data Inizio", format="DD/MM/YYYY")
            durata = c3.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            stato_new = c4.selectbox("Stato", ["aperto", "chiuso"], index=0)

            desc = st.text_area("Descrizione Prodotto", height=80)

            c5, c6, c7 = st.columns(3)
            nf = c5.text_input("NOL_FIN")
            ni = c6.text_input("NOL_INT")
            tot = c7.text_input("TotRata")

            c8, c9, c10, c11 = st.columns(4)
            copie_bn = c8.text_input("Copie incluse B/N", value="")
            ecc_bn = c9.text_input("Costo extra B/N (€)", value="")
            copie_col = c10.text_input("Copie incluse Colore", value="")
            ecc_col = c11.text_input("Costo extra Colore (€)", value="")

            if st.form_submit_button("💾 Crea contratto"):
                try:
                    data_fine = pd.to_datetime(din) + pd.DateOffset(months=int(durata))
                    new_row = {
                        "ClienteID": sel_id,
                        "RagioneSociale": rag_soc,
                        "NumeroContratto": num,
                        "DataInizio": fmt_date(din),
                        "DataFine": fmt_date(data_fine),
                        "Durata": durata,
                        "DescrizioneProdotto": desc,
                        "NOL_FIN": nf,
                        "NOL_INT": ni,
                        "TotRata": tot,
                        "CopieBN": copie_bn, "EccBN": ecc_bn,
                        "CopieCol": copie_col, "EccCol": ecc_col,
                        "Stato": stato_new or "aperto",
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([new_row])], ignore_index=True)
                    save_contratti(df_ct)
                    st.success("✅ Contratto creato con successo.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore creazione contratto: {e}")

    # === TABELLA CONTRATTI ESISTENTI ===
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3>📋 Contratti Esistenti</h3>", unsafe_allow_html=True)

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    for c in ["DataInizio", "DataFine"]:
        ct[c] = ct[c].apply(fmt_date)
    for c in ["TotRata", "NOL_FIN", "NOL_INT"]:
        ct[c] = ct[c].apply(money)

    # === RIGHE CONTRATTI (con evidenza visiva contratti chiusi) ===
    for i, r in ct.iterrows():
        gidx = int(r["_gidx"])
        rid = f"{r['ClienteID']}_{r.get('NumeroContratto','')}_{gidx}".replace("/", "_").replace(" ", "_")
        stato = str(r.get("Stato", "")).lower()
        bg = "#ffcdd2" if stato == "chiuso" else ("#f8fbff" if i % 2 == 0 else "#ffffff")

        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.1, 0.9, 0.9, 0.6, 1.2, 0.8, 2.0, 0.9])
        with c1: st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('NumeroContratto','')}</div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('DataInizio','')}</div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('DataFine','')}</div>", unsafe_allow_html=True)
        with c4: st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('Durata','')}</div>", unsafe_allow_html=True)
        with c5: st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('TotRata','')}</div>", unsafe_allow_html=True)

        stato_tag = "<span class='pill-open'>Aperto</span>" if stato != "chiuso" else "<span class='pill-closed'>Chiuso</span>"
        with c6: st.markdown(f"<div style='background:{bg};padding:6px'>{stato_tag}</div>", unsafe_allow_html=True)

        desc_short = str(r.get("DescrizioneProdotto", "")) or "—"
        if len(desc_short) > 80: desc_short = desc_short[:80] + "…"

        with c7:
            st.markdown(f"<div style='background:{bg};padding:6px'>", unsafe_allow_html=True)
            if st.button(desc_short, key=f"desc_{rid}", use_container_width=True):
                st.session_state["desc_popup"] = r.get("DescrizioneProdotto", "")
                st.session_state["desc_popup_title"] = r.get("NumeroContratto", "")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        with c8:
            st.markdown(f"<div style='background:{bg};padding:6px'>", unsafe_allow_html=True)
            colE, colD = st.columns(2)
            if colE.button("✏️", key=f"edit_{rid}", use_container_width=True):
                st.session_state["edit_gidx"] = gidx
                st.rerun()
            if colD.button("🗑️", key=f"del_{rid}", use_container_width=True):
                st.session_state["delete_gidx"] = gidx
                st.session_state["ask_delete_now"] = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # === MODIFICA CONTRATTO SELEZIONATO ===
    if st.session_state.get("edit_gidx") is not None:
        gidx = st.session_state["edit_gidx"]
        if gidx in df_ct.index:
            contratto = df_ct.loc[gidx]
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"### ✏️ Modifica Contratto {contratto.get('NumeroContratto','')}", unsafe_allow_html=True)

            with st.form(f"frm_edit_ct_{gidx}"):
                c1, c2, c3, c4 = st.columns(4)
                num = c1.text_input("Numero Contratto", contratto.get("NumeroContratto", ""))
                din = c2.date_input(
                    "Data Inizio",
                    value=pd.to_datetime(contratto.get("DataInizio"), dayfirst=True, errors="coerce")
                        if contratto.get("DataInizio") else pd.Timestamp.now(),
                    format="DD/MM/YYYY"
                )
                durata = c3.text_input("Durata (mesi)", contratto.get("Durata", ""))
                stato = c4.selectbox("Stato", ["aperto", "chiuso"],
                                    index=0 if str(contratto.get("Stato","")).lower()!="chiuso" else 1)

                desc = st.text_area("Descrizione Prodotto", contratto.get("DescrizioneProdotto", ""), height=100)

                c5, c6, c7 = st.columns(3)
                nf  = c5.text_input("NOL_FIN", contratto.get("NOL_FIN", ""))
                ni  = c6.text_input("NOL_INT", contratto.get("NOL_INT", ""))
                tot = c7.text_input("Tot Rata", contratto.get("TotRata", ""))

                c8, c9, c10, c11 = st.columns(4)
                copie_bn = c8.text_input("Copie incluse B/N", contratto.get("CopieBN", ""))
                ecc_bn   = c9.text_input("Costo extra B/N (€)", contratto.get("EccBN", ""))
                copie_col= c10.text_input("Copie incluse Colore", contratto.get("CopieCol", ""))
                ecc_col  = c11.text_input("Costo extra Colore (€)", contratto.get("EccCol", ""))

                salva = st.form_submit_button("💾 Salva Modifiche")
                if salva:
                    try:
                        durata_val = int(durata) if str(durata).isdigit() else 12
                        data_fine = pd.to_datetime(din) + pd.DateOffset(months=durata_val)
                        df_ct.loc[gidx, [
                            "NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
                            "NOL_FIN","NOL_INT","TotRata","CopieBN","EccBN","CopieCol","EccCol","Stato"
                        ]] = [
                            num, fmt_date(din), fmt_date(data_fine), durata, desc,
                            nf, ni, tot, copie_bn, ecc_bn, copie_col, ecc_col, stato
                        ]
                        save_contratti(df_ct)
                        st.success("✅ Contratto aggiornato con successo.")
                        st.session_state.pop("edit_gidx", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Errore durante il salvataggio: {e}")

            if st.button("❌ Annulla Modifica", key=f"cancel_edit_{gidx}", use_container_width=True):
                st.session_state.pop("edit_gidx", None)
                st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

    # === CONFERMA ELIMINAZIONE CONTRATTO ===
    if st.session_state.get("ask_delete_now") and st.session_state.get("delete_gidx") is not None:
        gidx = st.session_state["delete_gidx"]
        if gidx in df_ct.index:
            contratto = df_ct.loc[gidx]
            numero = contratto.get("NumeroContratto", "Senza numero")
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"### 🗑️ Eliminazione Contratto {numero}", unsafe_allow_html=True)
            st.warning(f"Sei sicuro di voler eliminare definitivamente il contratto **{numero}** del cliente **{rag_soc}**?")

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Sì, elimina", use_container_width=True, key=f"confirm_del_{gidx}"):
                    try:
                        df_ct = df_ct.drop(index=gidx).copy()
                        save_contratti(df_ct)
                        st.success("🗑️ Contratto eliminato con successo.")
                        st.session_state.pop("ask_delete_now", None)
                        st.session_state.pop("delete_gidx", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Errore durante l'eliminazione: {e}")
            with c2:
                if st.button("❌ Annulla", use_container_width=True, key=f"cancel_del_{gidx}"):
                    st.session_state.pop("ask_delete_now", None)
                    st.session_state.pop("delete_gidx", None)
                    st.info("Eliminazione annullata.")
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)

    # === ESPORTAZIONI (Excel + PDF migliorati) ===
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("<h3>📤 Esportazioni</h3>", unsafe_allow_html=True)
    cex1, cex2 = st.columns(2)



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
# 📇 PAGINA LISTA COMPLETA CLIENTI E SCADENZE (CON FILTRI)
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Scadenze Contratti")
    oggi = pd.Timestamp.now().normalize()

    # === Pulisce e prepara i dati contratti ===
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

    # === Funzione badge colorati ===
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

    # === FILTRI ===
    st.markdown("### 🔍 Filtri")
    col1, col2, col3, col4 = st.columns([1.5, 1.5, 1.5, 1.5])
    filtro_nome = col1.text_input("Cerca per nome cliente")
    filtro_citta = col2.text_input("Cerca per città")
    data_da = col3.date_input("Da data scadenza:", value=None, format="DD/MM/YYYY")
    data_a = col4.date_input("A data scadenza:", value=None, format="DD/MM/YYYY")

    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]
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
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.2, 0.7])
        with c1:
            st.markdown(f"**{r['RagioneSociale']}**")
        with c2:
            st.markdown(r.get("Citta", "") or "—")
        with c3:
            st.markdown(r["ScadenzaBadge"], unsafe_allow_html=True)
        with c4:
            if st.button("📂 Apri", key=f"apri_cli_{i}", use_container_width=True):
                st.session_state.update({
                    "selected_cliente": str(r["ClienteID"]),
                    "nav_target": "Clienti",
                    "_go_clienti_now": True,
                    "_force_scroll_top": True
                })
                st.rerun()
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
# MAIN APP
# =====================================
def main():
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    st.sidebar.success(f"👤 {user} — Ruolo: {role}")

    # --- Mappa pagine ---
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti,
    }

    # --- Pagina di default ---
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio(
        "📂 Menu principale",
        list(PAGES.keys()),
        index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0,
    )

    # --- Redirect rapidi ---
    if st.session_state.get("_go_contratti_now"):
        st.session_state["_go_contratti_now"] = False
        page = "Contratti"

    if st.session_state.get("_go_clienti_now"):
        st.session_state["_go_clienti_now"] = False
        page = "Clienti"

    # --- Caricamento dati ---
    df_cli, df_ct = load_clienti(), load_contratti()

    # --- Correzione date ONE-SHOT ---
    if not st.session_state.get("_date_fix_done", False):
        try:
            if not df_cli.empty:
                for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
                    if c in df_cli.columns:
                        df_cli[c] = fix_inverted_dates(df_cli[c], col_name=c)

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

    # --- Esegui la pagina scelta ---
    if page in PAGES:
        PAGES[page](df_cli, df_ct, role)

# =====================================
# AVVIO
# =====================================
if __name__ == "__main__":
    main()
