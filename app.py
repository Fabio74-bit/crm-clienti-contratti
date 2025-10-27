# =====================================
# app.py — Gestionale Clienti SHT (VERSIONE 2025 OFFLINE COMPLETA)
# =====================================
from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
from docx import Document
from docx.shared import Pt
from io import BytesIO
import requests

# =====================================
# COSTANTI GLOBALI SEMPRE DISPONIBILI
# =====================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

# Directory locale
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "gabriele").mkdir(parents=True, exist_ok=True)

# Percorsi principali CSV
CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti.csv"

# Template preventivi
TEMPLATES_DIR = Path("templates")
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
# CONFIGURAZIONE STREAMLIT E STILE BASE
# =====================================
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown("""
<style>
.block-container { padding:1rem 2rem; max-width:100% !important; }
[data-testid="stSidebar"] { background-color:#f8fafc !important; }
h2, h3 { color:#2563eb; }
</style>
""", unsafe_allow_html=True)

# =====================================
# GESTIONE CSV LOCALI — SICURA E ROBUSTA
# =====================================
def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]

def load_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    """Carica un CSV locale, crea file vuoto se mancante."""
    if not path.exists():
        pd.DataFrame(columns=cols).to_csv(path, index=False, encoding="utf-8-sig", sep=";")
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(path, dtype=str, sep=None, engine="python", encoding="utf-8-sig", on_bad_lines="skip").fillna("")
        return ensure_columns(df, cols)
    except Exception as e:
        st.error(f"❌ Errore caricamento {path.name}: {e}")
        return pd.DataFrame(columns=cols)

def save_csv(df: pd.DataFrame, path: Path):
    """Salva CSV locale e avvia backup automatico su Box."""
    try:
        df.to_csv(path, index=False, encoding="utf-8-sig", sep=";")
        st.toast(f"💾 {path.name} salvato", icon="📁")
        # === Backup Box automatico ===
        try:
            box_token = st.secrets["box"]["access_token"]
            url = "https://upload.box.com/api/2.0/files/content"
            headers = {"Authorization": f"Bearer {box_token}"}
            files = {'file': (path.name, open(path, 'rb'))}
            data = {'parent_id': '0'}  # ID cartella radice (modificabile)
            requests.post(url, headers=headers, files=files, data=data, timeout=30)
        except Exception as e:
            print(f"[BACKUP] ⚠️ Errore backup Box: {e}")
    except Exception as e:
        st.error(f"❌ Errore salvataggio {path.name}: {e}")

# =====================================
# FUNZIONI DI UTILITÀ GENERALI
# =====================================
def fmt_date(d) -> str:
    if d in (None, "", "nan", "NaN"):
        return ""
    try:
        return pd.to_datetime(d, errors="coerce", dayfirst=True).strftime("%d/%m/%Y")
    except Exception:
        return ""

def money(x):
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        if pd.isna(v): return ""
        return f"{v:,.2f} €"
    except Exception:
        return ""

def safe_text(txt):
    """Rimuove caratteri non compatibili PDF."""
    if pd.isna(txt) or txt is None:
        return ""
    s = str(txt)
    replacements = {"€": "EUR", "–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'"}
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")

# =====================================
# LOGIN FULLSCREEN (multiutente locale)
# =====================================
def do_login_fullscreen():
    """Login fullscreen elegante, utenti da st.secrets["auth"]["users"]."""
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    st.markdown("""
    <style>
    div[data-testid="stAppViewContainer"]{padding-top:0 !important;}
    .block-container{
        display:flex;flex-direction:column;justify-content:center;align-items:center;
        height:100vh;background-color:#f8fafc;
    }
    .login-card{
        background:#fff;border:1px solid #e5e7eb;border-radius:12px;
        box-shadow:0 4px 16px rgba(0,0,0,0.08);
        padding:2rem 2.5rem;width:360px;text-align:center;
    }
    .login-title{font-size:1.3rem;font-weight:600;color:#2563eb;margin:1rem 0 1.4rem;}
    .stButton>button{
        width:260px;font-size:0.9rem;background-color:#2563eb;color:white;
        border:none;border-radius:6px;padding:0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.image(LOGO_URL, width=140)
    st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)
    username = st.text_input("Nome utente").strip().lower()
    password = st.text_input("Password", type="password")
    login_btn = st.button("Entra")
    st.markdown("</div>", unsafe_allow_html=True)

    if login_btn and username and password:
        users = st.secrets["auth"]["users"]
        if username in users and users[username]["password"] == password:
            st.session_state.update({
                "user": username,
                "role": users[username].get("role", "viewer"),
                "logged_in": True
            })
            # === STORAGE MULTIUTENTE ===
            user_storage = STORAGE_DIR / username if username != "fabio" else STORAGE_DIR
            user_storage.mkdir(parents=True, exist_ok=True)

            st.session_state["CLIENTI_CSV"] = user_storage / "clienti.csv"
            st.session_state["CONTRATTI_CSV"] = user_storage / "contratti.csv"

            # crea file se non esistono
            for p in [st.session_state["CLIENTI_CSV"], st.session_state["CONTRATTI_CSV"]]:
                if not p.exists():
                    pd.DataFrame().to_csv(p, index=False, encoding="utf-8-sig")

            st.success(f"✅ Benvenuto {username}")
            time.sleep(0.3)
            st.rerun()
        else:
            st.error("❌ Credenziali non valide.")
    st.stop()
# =====================================
# KPI CARD — grafica con colore e icona
# =====================================
def kpi_card(titolo: str, valore, icona: str, colore: str = "#2563eb") -> str:
    return f"""
    <div style="background:{colore}10;border-left:6px solid {colore};
        border-radius:10px;padding:1rem 1.2rem;box-shadow:0 2px 8px rgba(0,0,0,0.06);
        height:100%;">
        <div style="font-size:1.6rem;">{icona}</div>
        <div style="font-size:0.9rem;font-weight:600;color:#444;">{titolo}</div>
        <div style="font-size:1.8rem;font-weight:700;color:{colore};">{valore}</div>
    </div>
    """

# =====================================
# PAGINA DASHBOARD
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📊 Gestionale SHT</h2>", unsafe_allow_html=True)
    st.divider()

    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())
    now = pd.Timestamp.now().normalize()

    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    new_contracts = df_ct[(df_ct["DataInizio"].notna()) & (df_ct["DataInizio"] >= pd.Timestamp(year=now.year, month=1, day=1))]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#1976D2"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#388E3C"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#D32F2F"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Nuovi contratti anno", len(new_contracts), "⭐", "#FBC02D"), unsafe_allow_html=True)

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

    if scadenze.empty:
        st.success("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
        return

    scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
    scadenze = scadenze.sort_values("DataFine")

    for i, r in scadenze.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 0.7])
        col1.markdown(f"**{r.get('RagioneSociale','')}**")
        col2.markdown(r.get("NumeroContratto", ""))
        col3.markdown(fmt_date(r.get("DataFine")))
        col4.markdown(r.get("Stato", ""))
        if col5.button("📂 Apri", key=f"dash_open_{i}", use_container_width=True):
            st.session_state.update({"selected_cliente": str(r.get("ClienteID")), "nav_target": "Contratti"})
            st.rerun()

# =====================================
# PAGINA CLIENTI
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Gestione Clienti")

    search_query = st.text_input("🔍 Cerca cliente per nome o ID", key="search_cli")
    filtered = df_cli[df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)] if search_query else df_cli.copy()
    if filtered.empty:
        st.warning("❌ Nessun cliente trovato.")
        return

    sel_name = st.selectbox("Seleziona Cliente", filtered["RagioneSociale"].tolist())
    cliente = filtered[filtered["RagioneSociale"] == sel_name].iloc[0]
    sel_id = cliente["ClienteID"]

    st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
    st.caption(f"ID Cliente: {sel_id}")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("📄 Vai ai Contratti", use_container_width=True):
            st.session_state.update({"selected_cliente": sel_id, "nav_target": "Contratti"})
            st.rerun()

    # === NOTE CLIENTE ===
    st.markdown("### 📝 Note Cliente")
    note_attuali = cliente.get("NoteCliente", "")
    nuove_note = st.text_area("Modifica note:", note_attuali, height=140, key=f"note_{sel_id}")
    if st.button("💾 Salva Note Cliente", use_container_width=True, key=f"save_note_{sel_id}"):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "NoteCliente"] = nuove_note
        save_csv(df_cli, CLIENTI_CSV)
        st.success("✅ Note aggiornate.")
        st.rerun()

    # === GENERA PREVENTIVO ===
    st.divider()
    st.markdown("### 🧾 Genera Nuovo Preventivo")
    PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
    PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)
    prev_csv = PREVENTIVI_DIR / "preventivi.csv"

    if prev_csv.exists():
        df_prev = pd.read_csv(prev_csv, dtype=str).fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID","NumeroOfferta","Template","NomeFile","Percorso","DataCreazione"])

    anno = datetime.now().year
    nome_cliente = cliente.get("RagioneSociale", "")
    nome_sicuro = "".join(c for c in nome_cliente if c.isalnum())[:6].upper()
    num_off = f"OFF-{anno}-{nome_sicuro}-{len(df_prev[df_prev['ClienteID']==sel_id])+1:03d}"

    with st.form(f"frm_prev_{sel_id}"):
        st.text_input("Numero Offerta", num_off, disabled=True)
        nome_file = st.text_input("Nome File", f"{num_off}.docx")
        template = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        genera_btn = st.form_submit_button("💾 Genera Preventivo")

    if genera_btn:
        try:
            tpl_path = TEMPLATES_DIR / TEMPLATE_OPTIONS[template]
            if not tpl_path.exists():
                st.error(f"❌ Template non trovato: {tpl_path}")
                return
            doc = Document(tpl_path)
            mappa = {
                "CLIENTE": nome_cliente,
                "DATA": datetime.now().strftime("%d/%m/%Y"),
                "NUMERO_OFFERTA": num_off
            }
            for p in doc.paragraphs:
                for k, v in mappa.items():
                    p.text = p.text.replace(f"<<{k}>>", str(v))
            out_path = PREVENTIVI_DIR / nome_file
            doc.save(out_path)
            nuova_riga = {
                "ClienteID": sel_id, "NumeroOfferta": num_off, "Template": TEMPLATE_OPTIONS[template],
                "NomeFile": nome_file, "Percorso": str(out_path), "DataCreazione": datetime.now().strftime("%d/%m/%Y %H:%M")
            }
            df_prev = pd.concat([df_prev, pd.DataFrame([nuova_riga])], ignore_index=True)
            df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
            st.success(f"✅ Preventivo creato: {nome_file}")
        except Exception as e:
            st.error(f"❌ Errore: {e}")

# =====================================
# PAGINA CONTRATTI
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📄 Gestione Contratti")

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    clienti_labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    sel_label = st.selectbox("Seleziona Cliente", clienti_labels.tolist())
    sel_id = df_cli.iloc[clienti_labels.tolist().index(sel_label)]["ClienteID"]
    rag_soc = df_cli.loc[df_cli["ClienteID"] == sel_id, "RagioneSociale"].iloc[0]

    st.markdown(f"### 🏢 {rag_soc}")

    # Filtra contratti cliente
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto registrato per questo cliente.")
        return

    ct["TotRata"] = ct["TotRata"].apply(money)
    ct["DataInizio"] = ct["DataInizio"].apply(fmt_date)
    ct["DataFine"] = ct["DataFine"].apply(fmt_date)

    st.dataframe(ct[["NumeroContratto","DataInizio","DataFine","Durata","TotRata","Stato"]], use_container_width=True)

    if st.button("➕ Nuovo Contratto", use_container_width=True):
        st.session_state["new_contract_for"] = sel_id
        st.session_state["nav_target"] = "Contratti"
        st.rerun()

# =====================================
# PAGINA RECALL E VISITE
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📅 Gestione Recall e Visite</h2>", unsafe_allow_html=True)
    st.divider()

    df = df_cli.copy()
    oggi = pd.Timestamp.now().normalize()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

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
                st.session_state.update({"selected_cliente": r["ClienteID"], "nav_target": "Clienti"})
                st.rerun()

# =====================================
# PAGINA LISTA COMPLETA CLIENTI
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Scadenze")
    oggi = pd.Timestamp.now().normalize()

    df_ct = df_ct.copy()
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    attivi = df_ct[df_ct["Stato"].astype(str).str.lower() != "chiuso"]
    prime_scadenze = attivi.groupby("ClienteID")["DataFine"].min().reset_index().rename(columns={"DataFine": "PrimaScadenza"})
    merged = df_cli.merge(prime_scadenze, on="ClienteID", how="left")
    merged["GiorniMancanti"] = (merged["PrimaScadenza"] - oggi).dt.days

    for i, r in merged.iterrows():
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.markdown(f"**{r['RagioneSociale']}**")
        c2.markdown(fmt_date(r["PrimaScadenza"]))
        if c3.button("📂 Apri", key=f"lista_{i}", use_container_width=True):
            st.session_state.update({"selected_cliente": r["ClienteID"], "nav_target": "Clienti"})
            st.rerun()
# =====================================
# FIX DATE UNA SOLA VOLTA
# =====================================
def fix_inverted_dates(series: pd.Series, col_name: str = "") -> pd.Series:
    """Corregge date con mese/giorno invertiti."""
    fixed = []
    fixed_count = 0
    for val in series:
        if pd.isna(val) or str(val).strip() == "":
            fixed.append("")
            continue
        s = str(val).strip()
        try:
            d1 = pd.to_datetime(s, dayfirst=True, errors="coerce")
            d2 = pd.to_datetime(s, dayfirst=False, errors="coerce")
            if not pd.isna(d1) and not pd.isna(d2) and d1 != d2:
                if d1.day <= 12 and d2.day > 12:
                    fixed.append(d2.strftime("%d/%m/%Y"))
                    fixed_count += 1
                else:
                    fixed.append(d1.strftime("%d/%m/%Y"))
            elif not pd.isna(d1):
                fixed.append(d1.strftime("%d/%m/%Y"))
            elif not pd.isna(d2):
                fixed.append(d2.strftime("%d/%m/%Y"))
            else:
                fixed.append("")
        except Exception:
            fixed.append("")
    if fixed_count > 0:
        st.info(f"🔄 {fixed_count} date corrette nella colonna **{col_name}**.")
    return pd.Series(fixed)

def fix_dates_once(df_cli: pd.DataFrame, df_ct: pd.DataFrame):
    """Esegue correzione date una sola volta per sessione."""
    if st.session_state.get("_date_fix_done", False):
        return df_cli, df_ct
    try:
        if not df_cli.empty:
            for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
                if c in df_cli.columns:
                    df_cli[c] = fix_inverted_dates(df_cli[c], c)
        if not df_ct.empty:
            for c in ["DataInizio","DataFine"]:
                if c in df_ct.columns:
                    df_ct[c] = fix_inverted_dates(df_ct[c], c)
        save_csv(df_cli, CLIENTI_CSV)
        save_csv(df_ct, CONTRATTI_CSV)
        st.toast("✅ Date corrette e salvate.", icon="🔄")
        st.session_state["_date_fix_done"] = True
    except Exception as e:
        st.warning(f"⚠️ Correzione date non completata: {e}")
    return df_cli, df_ct

# =====================================
# MAIN APP — versione completa 2025 offline
# =====================================
def main():
    st.write("✅ Avvio CRM SHT — modalità offline locale")

    # --- LOGIN ---
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    # --- Percorsi locali ---
    base_clienti = STORAGE_DIR / "clienti.csv"
    base_contratti = STORAGE_DIR / "contratti.csv"
    gabriele_dir = STORAGE_DIR / "gabriele"
    gabriele_dir.mkdir(parents=True, exist_ok=True)
    gabriele_clienti = gabriele_dir / "clienti.csv"
    gabriele_contratti = gabriele_dir / "contratti.csv"

    # --- Ruoli ---
    if user in ["fabio","emanuela","claudia"]:
        ruolo_scrittura = "full"
    else:
        ruolo_scrittura = "limitato"

    # --- Selettore visibilità ---
    if user in ["fabio","giulia","antonella"]:
        visibilita_opzioni = ["Miei","Gabriele","Tutti"]
        visibilita_scelta = st.sidebar.radio("📂 Visualizza clienti di:", visibilita_opzioni, index=0)
    else:
        visibilita_scelta = "Miei"

    # --- Caricamento dati ---
    CLIENTI_COLS = ["ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
                    "Telefono","Cell","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall",
                    "UltimaVisita","ProssimaVisita","TMK","NoteCliente","owner"]
    CONTRATTI_COLS = ["ClienteID","RagioneSociale","NumeroContratto","DataInizio","DataFine","Durata",
                      "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","CopieBN","EccBN",
                      "CopieCol","EccCol","Stato","owner"]

    df_cli_main = load_csv(base_clienti, CLIENTI_COLS)
    df_ct_main = load_csv(base_contratti, CONTRATTI_COLS)
    df_cli_gab = load_csv(gabriele_clienti, CLIENTI_COLS)
    df_ct_gab = load_csv(gabriele_contratti, CONTRATTI_COLS)

    # --- Applica filtro ---
    if visibilita_scelta == "Miei":
        df_cli, df_ct = df_cli_main, df_ct_main
    elif visibilita_scelta == "Gabriele":
        df_cli, df_ct = df_cli_gab, df_ct_gab
    else:
        df_cli = pd.concat([df_cli_main, df_cli_gab], ignore_index=True)
        df_ct = pd.concat([df_ct_main, df_ct_gab], ignore_index=True)

    # --- Fix date ---
    df_cli, df_ct = fix_dates_once(df_cli, df_ct)

    # --- Sidebar info ---
    st.sidebar.success(f"👤 {user} — Ruolo: {role}")
    st.sidebar.info(f"📂 Vista: {visibilita_scelta}")

    # --- Passa info a sessione ---
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

    # --- Menu ---
    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()), index=0)
    if "nav_target" in st.session_state:
        target = st.session_state.pop("nav_target")
        if target in PAGES:
            page = target

    # --- Esegui pagina ---
    if page in PAGES:
        PAGES[page](df_cli, df_ct, ruolo_scrittura)

# =====================================
# AVVIO APPLICAZIONE
# =====================================
if __name__ == "__main__":
    main()
