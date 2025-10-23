# =====================================
# app.py — Gestionale Clienti SHT (VERSIONE 2025 OTTIMIZZATA CON CACHE)
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
# COSTANTI GLOBALI E PERCORSI STORAGE
# =====================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"
STORAGE_DIR = Path("storage")
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
    """Aggiunge eventuali colonne mancanti al DataFrame"""
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]

# =====================================
# GESTIONE CACHE OTTIMIZZATA
# =====================================

@st.cache_data(ttl=60)
def load_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    """Carica un CSV con cache ottimizzata."""
    if path.exists():
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(path, index=False, encoding="utf-8-sig")
    return ensure_columns(df, cols)

def save_csv(df: pd.DataFrame, path: Path, date_cols=None):
    """Salva CSV e invalida cache."""
    out = df.copy()
    if date_cols:
        for c in date_cols:
            out[c] = out[c].apply(fmt_date)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    load_csv.clear()  # invalida cache

def save_if_changed(df_new, path: Path, original_df):
    """Salva solo se i dati sono effettivamente cambiati."""
    try:
        if not original_df.equals(df_new):
            df_new.to_csv(path, index=False, encoding='utf-8-sig')
            load_csv.clear()
            return True
        return False
    except Exception:
        df_new.to_csv(path, index=False, encoding='utf-8-sig')
        load_csv.clear()
        return True

# =====================================
# LOGIN FULLSCREEN OTTIMIZZATO
# =====================================
def do_login_fullscreen():
    """Login fullscreen con sfondo chiaro e logo SHT"""
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
# FUNZIONE CARD KPI
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
# ======== FINE SEZIONE A ========
# =====================================
# 📈 PAGINA DASHBOARD
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📊 Gestionale SHT</h2>", unsafe_allow_html=True)
    st.divider()

    with st.spinner("Caricamento dati..."):
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

    if scadenze.empty:
        st.success("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        for i, r in scadenze.iterrows():
            col1, col2, col3, col4 = st.columns([2.5, 1, 1, 0.7])
            col1.markdown(f"**{r.get('RagioneSociale','—')}**")
            col2.markdown(r.get("NumeroContratto", "—"))
            col3.markdown(r.get("DataFine", "—"))
            if col4.button("📂 Apri", key=f"open_scad_{i}", use_container_width=True):
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
# 👥 PAGINA CLIENTI
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Gestione Clienti")
    if role == "limitato":
        st.warning("👁️ Accesso in sola lettura per il tuo profilo.")
        st.stop()

    search_query = st.text_input("🔍 Cerca cliente per nome o ID")
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

    selected_name = st.selectbox(
        "Seleziona Cliente",
        filtered["RagioneSociale"].tolist(),
        index=0,
        key="sel_cliente_box"
    )
    cliente = filtered[filtered["RagioneSociale"] == selected_name].iloc[0]
    sel_id = cliente["ClienteID"]

    st.markdown(f"### 🏢 {cliente['RagioneSociale']}")
    st.caption(f"ID Cliente: {sel_id}")
    col1, col2 = st.columns([1, 1])
    if col1.button("📄 Vai ai Contratti", key=f"go_cont_{sel_id}"):
        st.session_state.update({"selected_cliente": sel_id, "nav_target": "Contratti"})
        st.rerun()
    if col2.button("🗑️ Elimina Cliente", key=f"del_cli_{sel_id}"):
        df_cli.drop(df_cli[df_cli["ClienteID"] == sel_id].index, inplace=True)
        save_csv(df_cli, CLIENTI_CSV)
        st.success("🗑 Cliente eliminato.")
        st.rerun()

    # === NOTE ===
    st.divider()
    st.markdown("### 📝 Note Cliente")
    note_attuali = cliente.get("NoteCliente", "")
    nuove_note = st.text_area("Modifica note cliente", note_attuali, height=140)
    if st.button("💾 Salva Note", key=f"save_note_{sel_id}"):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "NoteCliente"] = nuove_note
        save_csv(df_cli, CLIENTI_CSV)
        st.success("✅ Note aggiornate.")
        st.rerun()

# =====================================
# 📑 PAGINA CONTRATTI
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Gestione Contratti</h2>", unsafe_allow_html=True)
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    sel_label = st.selectbox("Seleziona Cliente", labels.tolist(), index=0)
    sel_id = sel_label.split(" — ")[0]
    rag_soc = df_cli.loc[df_cli["ClienteID"] == sel_id, "RagioneSociale"].iloc[0]

    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    ct = ct.reset_index().rename(columns={"index": "_gidx"})

    with st.expander("➕ Crea Nuovo Contratto"):
        with st.form(f"frm_new_contract_{sel_id}"):
            c1, c2, c3 = st.columns(3)
            num = c1.text_input("Numero Contratto")
            din = c2.date_input("Data Inizio", format="DD/MM/YYYY")
            durata = c3.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione Prodotto", height=60)
            stato = st.selectbox("Stato", ["aperto", "chiuso"], index=0)
            if st.form_submit_button("💾 Crea"):
                data_fine = pd.to_datetime(din) + pd.DateOffset(months=int(durata))
                nuovo = {
                    "ClienteID": sel_id, "RagioneSociale": rag_soc, "NumeroContratto": num,
                    "DataInizio": fmt_date(din), "DataFine": fmt_date(data_fine),
                    "Durata": durata, "DescrizioneProdotto": desc, "Stato": stato
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([nuovo])], ignore_index=True)
                save_csv(df_ct, CONTRATTI_CSV)
                st.success("✅ Contratto creato.")
                st.rerun()

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    for c in ["DataInizio", "DataFine"]:
        ct[c] = ct[c].apply(fmt_date)
    gb = GridOptionsBuilder.from_dataframe(ct)
    gb.configure_default_column(resizable=True, wrapText=True, autoHeight=True)
    gb.configure_column("NumeroContratto", pinned="left", width=180)
    AgGrid(ct, gridOptions=gb.build(), theme="streamlit")

# =====================================
# 📅 PAGINA RECALL E VISITE
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📅 Recall e Visite</h2>", unsafe_allow_html=True)
    oggi = pd.Timestamp.now().normalize()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df_cli[c] = pd.to_datetime(df_cli[c], errors="coerce", dayfirst=True)

    imminenti = df_cli[
        (df_cli["ProssimoRecall"].between(oggi, oggi + pd.DateOffset(days=30))) |
        (df_cli["ProssimaVisita"].between(oggi, oggi + pd.DateOffset(days=30)))
    ]
    st.markdown("### 🔔 Imminenti (entro 30 giorni)")
    if imminenti.empty:
        st.success("✅ Nessun recall/visita imminente.")
    else:
        for i, r in imminenti.iterrows():
            col1, col2, col3 = st.columns([2, 1, 0.6])
            col1.markdown(f"**{r['RagioneSociale']}**")
            col2.markdown(fmt_date(r["ProssimoRecall"]))
            if col3.button("📂 Apri", key=f"imm_{i}"):
                st.session_state.update({"selected_cliente": r["ClienteID"], "nav_target": "Clienti"})
                st.rerun()

# =====================================
# 📋 PAGINA LISTA COMPLETA CLIENTI
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti")
    oggi = pd.Timestamp.now().normalize()
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    df_ct["Stato"] = df_ct["Stato"].astype(str).str.lower().fillna("")
    attivi = df_ct[df_ct["Stato"] != "chiuso"]

    prime_scadenze = (
        attivi.groupby("ClienteID")["DataFine"].min().reset_index().rename(columns={"DataFine": "PrimaScadenza"})
    )
    merged = df_cli.merge(prime_scadenze, on="ClienteID", how="left")
    merged["GiorniMancanti"] = (merged["PrimaScadenza"] - oggi).dt.days

    def badge(row):
        if pd.isna(row["PrimaScadenza"]): return "⚪ Nessuna"
        g = row["GiorniMancanti"]
        if g < 0: return f"⚫ Scaduto ({fmt_date(row['PrimaScadenza'])})"
        if g <= 30: return f"🔴 {fmt_date(row['PrimaScadenza'])}"
        if g <= 90: return f"🟡 {fmt_date(row['PrimaScadenza'])}"
        return f"🟢 {fmt_date(row['PrimaScadenza'])}"
    merged["Badge"] = merged.apply(badge, axis=1)

    filtro = st.text_input("🔍 Cerca cliente per nome o città")
    if filtro:
        merged = merged[
            merged["RagioneSociale"].str.contains(filtro, case=False, na=False)
            | merged["Citta"].str.contains(filtro, case=False, na=False)
        ]

    st.dataframe(merged[["RagioneSociale", "Citta", "Badge", "TMK"]], use_container_width=True, hide_index=True)
# ======== FINE SEZIONE B ========
# =====================================
# 🚀 MAIN APP — AVVIO E ROUTING COMPLETO
# =====================================
def fix_inverted_dates(series: pd.Series, col_name: str = "") -> pd.Series:
    """Corregge automaticamente date invertite (MM/DD/YYYY → DD/MM/YYYY)."""
    fixed = []
    fixed_count = 0
    for val in series:
        if not val or str(val).strip() in ["", "NaN", "None"]:
            fixed.append("")
            continue
        s = str(val).strip()
        try:
            d1 = pd.to_datetime(s, dayfirst=True, errors="coerce")
            d2 = pd.to_datetime(s, dayfirst=False, errors="coerce")
            parsed = d1
            if not pd.isna(d1) and not pd.isna(d2) and d1 != d2:
                if d1.day <= 12 and d2.day > 12:
                    parsed = d2
                    fixed_count += 1
            fixed.append(fmt_date(parsed))
        except Exception:
            fixed.append("")
    if fixed_count > 0:
        st.info(f"🔄 {fixed_count} date corrette nella colonna **{col_name}**.")
    return pd.Series(fixed)

def fix_dates_once(df_cli: pd.DataFrame, df_ct: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Corregge le date una sola volta per sessione."""
    if st.session_state.get("_date_fix_done", False):
        return df_cli, df_ct
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        if c in df_cli.columns:
            df_cli[c] = fix_inverted_dates(df_cli[c], col_name=c)
    for c in ["DataInizio", "DataFine"]:
        if c in df_ct.columns:
            df_ct[c] = fix_inverted_dates(df_ct[c], col_name=c)
    save_csv(df_cli, CLIENTI_CSV)
    save_csv(df_ct, CONTRATTI_CSV)
    st.toast("✅ Date corrette e salvate nei CSV.")
    st.session_state["_date_fix_done"] = True
    return df_cli, df_ct

# =====================================
# MAIN FUNZIONE PRINCIPALE
# =====================================
def main():
    # --- LOGIN ---
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    # --- STORAGE DINAMICO ---
    global CLIENTI_CSV, CONTRATTI_CSV
    base_clienti = STORAGE_DIR / "clienti.csv"
    base_contratti = STORAGE_DIR / "contratti_clienti.csv"
    gabriele_clienti = STORAGE_DIR / "gabriele" / "clienti.csv"
    gabriele_contratti = STORAGE_DIR / "gabriele" / "contratti_clienti.csv"

    if user == "fabio":
        visibilita = "tutti"
        ruolo_scrittura = "full"
        CLIENTI_CSV, CONTRATTI_CSV = base_clienti, base_contratti
    elif user in ["emanuela", "claudia"]:
        visibilita, ruolo_scrittura = "tutti", "full"
    elif user in ["giulia", "antonella"]:
        visibilita, ruolo_scrittura = "tutti", "limitato"
    elif user in ["gabriele", "laura", "annalisa"]:
        visibilita, ruolo_scrittura = "gabriele", "limitato"
        CLIENTI_CSV, CONTRATTI_CSV = gabriele_clienti, gabriele_contratti
    else:
        visibilita, ruolo_scrittura = "solo_propri", "limitato"

    # --- SIDEBAR INFO ---
    st.sidebar.image(LOGO_URL, width=160)
    st.sidebar.success(f"👤 {user} — Ruolo: {role}")
    st.sidebar.info(f"📂 File in uso: {CLIENTI_CSV.name}")

    # --- CARICAMENTO DATI (con cache) ---
    with st.spinner("Caricamento dati..."):
        df_cli = load_csv(CLIENTI_CSV, CLIENTI_COLS)
        df_ct = load_csv(CONTRATTI_CSV, CONTRATTI_COLS)
        if visibilita == "tutti":
            try:
                gcli = load_csv(gabriele_clienti, CLIENTI_COLS)
                gct = load_csv(gabriele_contratti, CONTRATTI_COLS)
                df_cli = pd.concat([df_cli, gcli], ignore_index=True)
                df_ct = pd.concat([df_ct, gct], ignore_index=True)
            except Exception as e:
                st.warning(f"⚠️ Impossibile caricare i dati di Gabriele: {e}")

    # --- CORREZIONE DATE UNA SOLA VOLTA ---
    df_cli, df_ct = fix_dates_once(df_cli, df_ct)

    # --- SESSIONE ---
    st.session_state["ruolo_scrittura"] = ruolo_scrittura
    st.session_state["visibilita"] = visibilita

    # --- MENU PAGINE ---
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti,
    }

    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()), index=0)

    # --- NAVIGAZIONE INTERNA ---
    if "nav_target" in st.session_state:
        target = st.session_state.pop("nav_target")
        if target in PAGES:
            page = target

    # --- ESECUZIONE PAGINA ---
    if page in PAGES:
        PAGES[page](df_cli, df_ct, ruolo_scrittura)

# =====================================
# AVVIO
# =====================================
if __name__ == "__main__":
    main()
