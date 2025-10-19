# =====================================
# app.py — Gestionale Clienti SHT (FULL 2025 ITA)
# =====================================
from __future__ import annotations
import streamlit as st
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

# Scroll top
st.markdown("""
<script>
    window.addEventListener('load', function() {
        window.scrollTo(0, 0);
    });
</script>
""", unsafe_allow_html=True)

# --- Stile generale pagina ---
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


from pathlib import Path
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from docx import Document
from docx.shared import Pt

# =====================================
# CONFIG / COSTANTI
# =====================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

STORAGE_DIR = Path(
    st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage"))
)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "NoteCliente"
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]
DURATE_MESI = ["12", "24", "36", "48", "60", "72"]

# =====================================
# FUNZIONI UTILITY
# =====================================
def as_date(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    s = str(x).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return pd.NaT
    d = pd.to_datetime(s, errors="coerce", dayfirst=True)
    return d

def to_date_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series([], dtype="datetime64[ns]")
    return s.map(as_date)

def fmt_date(d) -> str:
    """Restituisce una data in formato dd/mm/aaaa."""
    import datetime as dt
    if d is None or d == "" or (isinstance(d, float) and pd.isna(d)):
        return ""
    try:
        if isinstance(d, (dt.date, dt.datetime, pd.Timestamp)):
            return pd.to_datetime(d).strftime("%d/%m/%Y")
        parsed = pd.to_datetime(str(d), errors="coerce", dayfirst=True)
        if pd.isna(parsed):
            return ""
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return ""

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def money(x):
    try:
        if x in (None, "", "nan", "NaN", "None") or pd.isna(x):
            return ""
        v = float(pd.to_numeric(x, errors="coerce"))
        if pd.isna(v):
            return ""
        return f"{v:,.2f} €"
    except Exception:
        return ""

def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

# =====================================
# I/O DATI — VERSIONE PULITA (NO NAN) + DATE ITA
# =====================================
def load_clienti() -> pd.DataFrame:
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",", encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
    )
    df = ensure_columns(df, CLIENTI_COLS)
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = to_date_series(df[c])
    return df


def load_contratti() -> pd.DataFrame:
    if CONTRATTI_CSV.exists():
        df = pd.read_csv(CONTRATTI_CSV, dtype=str, sep=",", encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
        df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
    )
    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio", "DataFine"]:
        df[c] = to_date_series(df[c])
    return df


# =====================================
# SALVATAGGI CON FORMATO ITALIANO
# =====================================
def save_clienti(df: pd.DataFrame):
    out = df.copy()
    out = out.replace(
        to_replace=["nan", "NaN", "None", "NULL", "null", "NaT"],
        value="",
        regex=True
    ).fillna("")
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        out[c] = out[c].apply(fmt_date)
    out.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")


def save_contratti(df: pd.DataFrame):
    out = df.copy()
    out = out.replace(
        to_replace=["nan", "NaN", "None", "NULL", "null", "NaT"],
        value="",
        regex=True
    ).fillna("")
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(fmt_date)
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# =====================================
# LOGIN FULLSCREEN
# =====================================
def do_login_fullscreen():
    import time

    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    st.markdown("""
    <style>
    div[data-testid="stAppViewContainer"] { padding-top: 0 !important; }
    .block-container {
        display: flex; flex-direction: column; justify-content: center;
        align-items: center; height: 100vh; background-color: #f8fafc;
    }
    .login-card {
        background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        padding: 2rem 2.5rem; width: 360px; text-align: center;
        animation: fadeIn 0.4s ease-in-out;
    }
    @keyframes fadeIn {
        from {opacity: 0; transform: translateY(-10px);}
        to {opacity: 1; transform: translateY(0);}
    }
    .login-title { font-size: 1.3rem; font-weight: 600; color: #2563eb; margin: 0.8rem 0 1.4rem 0; }
    .stTextInput>div>div>input { width: 260px !important; font-size: 0.9rem !important; }
    .stButton>button {
        width: 260px !important; font-size: 0.9rem !important;
        background-color: #2563eb !important; color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

    login_col1, login_col2, login_col3 = st.columns([1, 2, 1])
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
            st.session_state["user"] = username
            st.session_state["role"] = users[username].get("role", "viewer")
            st.session_state["logged_in"] = True
            st.success(f"✅ Benvenuto {username}!")
            time.sleep(0.3)
            st.rerun()
        elif username and password:
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
# DASHBOARD COMPLETA
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2 style='margin-top:0.2rem;'>📊 Dashboard Gestionale</h2>", unsafe_allow_html=True)
    st.divider()

    # === KPI principali ===
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

    # =====================================
    # ➕ CREA NUOVO CLIENTE + CONTRATTO
    # =====================================
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

            st.markdown("#### 📄 Primo Contratto del Cliente")
            colc1, colc2, colc3 = st.columns(3)
            with colc1:
                num = st.text_input("Numero Contratto")
            with colc2:
                data_inizio = st.date_input("Data Inizio", format="DD/MM/YYYY")
            with colc3:
                durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione Prodotto", height=80)
            colp1, colp2, colp3 = st.columns(3)
            with colp1:
                nf = st.text_input("NOL_FIN")
            with colp2:
                ni = st.text_input("NOL_INT")
            with colp3:
                tot = st.text_input("Tot Rata")

            submit_new = st.form_submit_button("💾 Crea Cliente e Contratto")
            if submit_new:
                try:
                    new_id = str(len(df_cli) + 1)
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

                    data_fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))
                    nuovo_contratto = {
                        "ClienteID": new_id,
                        "NumeroContratto": num,
                        "DataInizio": fmt_date(data_inizio),
                        "DataFine": fmt_date(data_fine),
                        "Durata": durata,
                        "DescrizioneProdotto": desc,
                        "NOL_FIN": nf,
                        "NOL_INT": ni,
                        "TotRata": tot,
                        "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([nuovo_contratto])], ignore_index=True)
                    save_contratti(df_ct)

                    st.success(f"✅ Cliente '{ragione}' e contratto creati correttamente!")
                    st.session_state["selected_cliente"] = new_id
                    st.session_state["nav_target"] = "Contratti"
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore creazione cliente: {e}")

    st.divider()

    # =====================================
    # ⚠️ CONTRATTI IN SCADENZA ENTRO 6 MESI
    # =====================================
    st.markdown("### ⚠️ Contratti in scadenza entro 6 mesi")
    oggi = pd.Timestamp.now().normalize()
    entro_6_mesi = oggi + pd.DateOffset(months=6)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    scadenze = df_ct[
        (df_ct["DataFine"].notna()) &
        (df_ct["DataFine"] >= oggi) &
        (df_ct["DataFine"] <= entro_6_mesi) &
        (df_ct["Stato"].str.lower() != "chiuso")
    ].copy()

    if scadenze.empty:
        st.success("✅ Nessun contratto attivo in scadenza nei prossimi 6 mesi.")
    else:
        scadenze = scadenze.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        scadenze = scadenze.sort_values("DataFine")
        st.markdown(f"**🔢 {len(scadenze)} contratti in scadenza entro 6 mesi:**")
        for i, r in scadenze.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 0.8, 0.8])
            with col1: st.markdown(f"**{r['RagioneSociale']}**")
            with col2: st.markdown(r["NumeroContratto"] or "—")
            with col3: st.markdown(r["DataFine"] or "—")
            with col4: st.markdown(r["Stato"] or "—")
            with col5:
                if st.button("Apri", key=f"open_scad_{i}", use_container_width=True):
                    st.session_state["selected_cliente"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Contratti"
                    st.rerun()

    st.divider()

    # =====================================
    # 🚫 CLIENTI SENZA DATA FINE (DURATA 36-48-60-72 e NON CHIUSI)
    # =====================================
    st.markdown("### 🚫 Clienti con contratti senza Data Fine")
    oggi = pd.Timestamp.now().normalize()
    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)

    senza_datafine = df_ct[df_ct["DataFine"].isna() | (df_ct["DataFine"] == "")]
    senza_datafine = senza_datafine[
        (senza_datafine["DataInizio"] >= pd.Timestamp("2025-01-01")) &
        (senza_datafine["Stato"].astype(str).str.lower() != "chiuso")
    ]
    valid_durations = ["36", "48", "60", "72"]
    mask_valid = senza_datafine["Durata"].astype(str).str.strip().isin(valid_durations)
    senza_datafine = senza_datafine[mask_valid]

    if senza_datafine.empty:
        st.success("✅ Tutti i contratti validi hanno una Data Fine impostata.")
    else:
        senza_datafine = senza_datafine.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        senza_datafine = senza_datafine.sort_values("DataInizio")
        st.markdown(f"**🔹 {len(senza_datafine)} clienti hanno contratti senza Data Fine (36/48/60/72 mesi):**")
        for i, r in senza_datafine.iterrows():
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 0.8])
            with c1: st.markdown(f"**{r['RagioneSociale']}**")
            with c2: st.markdown(r["NumeroContratto"] or "—")
            with c3: st.markdown(fmt_date(r["DataInizio"]) or "—")
            with c4: st.markdown(r["Durata"] or "—")
            with c5:
                if st.button("Apri", key=f"open_nofine_{i}", use_container_width=True):
                    st.session_state["selected_cliente"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Contratti"
                    st.rerun()
# ==== FINE BLOCCO 2 ====
# =====================================
# PAGINA CLIENTI (completa con anagrafica + preventivi)
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Clienti")

    # 🔁 Se è stato selezionato un cliente dalla dashboard, aprilo automaticamente
    if "selected_cliente" in st.session_state:
        selected_id = st.session_state.pop("selected_cliente")
        if selected_id in df_cli["ClienteID"].values:
            cliente_row = df_cli[df_cli["ClienteID"] == selected_id].iloc[0]
            st.session_state["cliente_selezionato"] = cliente_row["RagioneSociale"]

    # 🔍 Ricerca cliente
    st.markdown("### 🔍 Cerca Cliente")
    search_query = st.text_input("Cerca cliente per nome o ID:")
    if search_query:
        filtered = df_cli[
            df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)
            | df_cli["ClienteID"].astype(str).str.contains(search_query, na=False)
        ]
    else:
        filtered = df_cli

    if filtered.empty:
        st.warning("Nessun cliente trovato.")
        return

    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox(
        "Seleziona Cliente",
        options,
        index=options.index(st.session_state.get("cliente_selezionato", options[0])) if options else 0
    )

    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    # === HEADER ===
    col_header1, col_header2 = st.columns([4, 1])
    with col_header1:
        st.markdown(f"## 🏢 {cliente.get('RagioneSociale', '')}")
        st.caption(f"ClienteID: {sel_id}")
    with col_header2:
        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        if st.button("📄 Vai ai Contratti", use_container_width=True):
            st.session_state["selected_cliente"] = sel_id
            st.session_state["nav_target"] = "Contratti"
            st.rerun()

    # === INFO RAPIDE ===
    indirizzo = cliente.get("Indirizzo", "")
    citta = cliente.get("Citta", "")
    cap = cliente.get("CAP", "")
    persona = cliente.get("PersonaRiferimento", "")
    telefono = cliente.get("Telefono", "")
    cell = cliente.get("Cell", "")

    st.markdown(
        f"""
        <div style='font-size:15px; line-height:1.7;'>
            <b>📍 Indirizzo:</b> {indirizzo} – {citta} {cap}<br>
            <b>🧑‍💼 Referente:</b> {persona}<br>
            <b>📞 Telefono:</b> {telefono} — <b>📱 Cell:</b> {cell}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    # === DATE RECALL E VISITE ===
    st.markdown("### ⚡ Recall e Visite")

    def _safe_date(val):
        try:
            d = pd.to_datetime(val, dayfirst=True)
            return None if pd.isna(d) else d.date()
        except Exception:
            return None

    col1, col2, col3, col4 = st.columns(4)
    ur = col1.date_input("⏰ Ultimo Recall", value=_safe_date(cliente.get("UltimoRecall")), format="DD/MM/YYYY")
    pr = col2.date_input("📅 Prossimo Recall", value=_safe_date(cliente.get("ProssimoRecall")), format="DD/MM/YYYY")
    uv = col3.date_input("👣 Ultima Visita", value=_safe_date(cliente.get("UltimaVisita")), format="DD/MM/YYYY")
    pv = col4.date_input("🗓️ Prossima Visita", value=_safe_date(cliente.get("ProssimaVisita")), format="DD/MM/YYYY")

    if st.button("💾 Salva Aggiornamenti", use_container_width=True):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "UltimoRecall"] = fmt_date(ur)
        df_cli.loc[idx, "ProssimoRecall"] = fmt_date(pr)
        df_cli.loc[idx, "UltimaVisita"] = fmt_date(uv)
        df_cli.loc[idx, "ProssimaVisita"] = fmt_date(pv)
        save_clienti(df_cli)
        st.success("✅ Date aggiornate.")
        st.rerun()

    # === MODIFICA ANAGRAFICA COMPLETA ===
    st.divider()
    with st.expander("✏️ Modifica Anagrafica Completa"):
        with st.form(f"frm_anagrafica_{sel_id}"):
            col1, col2 = st.columns(2)
            with col1:
                indirizzo = st.text_input("📍 Indirizzo", cliente.get("Indirizzo", ""))
                citta = st.text_input("🏙️ Città", cliente.get("Citta", ""))
                cap = st.text_input("📮 CAP", cliente.get("CAP", ""))
                telefono = st.text_input("📞 Telefono", cliente.get("Telefono", ""))
                cell = st.text_input("📱 Cellulare", cliente.get("Cell", ""))
                email = st.text_input("✉️ Email", cliente.get("Email", ""))
                persona = st.text_input("👤 Persona Riferimento", cliente.get("PersonaRiferimento", ""))
            with col2:
                piva = st.text_input("💼 Partita IVA", cliente.get("PartitaIVA", ""))
                iban = st.text_input("🏦 IBAN", cliente.get("IBAN", ""))
                sdi = st.text_input("📡 SDI", cliente.get("SDI", ""))
                note = st.text_area("📝 Note Cliente", cliente.get("NoteCliente", ""), height=110)

            salva_btn = st.form_submit_button("💾 Salva Modifiche")
            if salva_btn:
                idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx, "Indirizzo"] = indirizzo
                df_cli.loc[idx, "Citta"] = citta
                df_cli.loc[idx, "CAP"] = cap
                df_cli.loc[idx, "Telefono"] = telefono
                df_cli.loc[idx, "Cell"] = cell
                df_cli.loc[idx, "Email"] = email
                df_cli.loc[idx, "PersonaRiferimento"] = persona
                df_cli.loc[idx, "PartitaIVA"] = piva
                df_cli.loc[idx, "IBAN"] = iban
                df_cli.loc[idx, "SDI"] = sdi
                df_cli.loc[idx, "NoteCliente"] = note
                save_clienti(df_cli)
                st.success("✅ Anagrafica aggiornata.")
                st.rerun()

    st.divider()

    # =======================================================
    # 🧾 GESTIONE PREVENTIVI INTEGRATA
    # =======================================================
    st.markdown("### 🧾 Gestione Preventivi Cliente")

    TEMPLATES_DIR = STORAGE_DIR / "templates"
    PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
    PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)
    prev_csv = STORAGE_DIR / "preventivi.csv"

    TEMPLATE_OPTIONS = {
        "Offerta A4": "Offerte_A4.docx",
        "Offerta A3": "Offerte_A3.docx",
        "Centralino": "Offerta_Centralino.docx",
        "Varie": "Offerta_Varie.docx",
    }

    if prev_csv.exists():
        df_prev = pd.read_csv(prev_csv, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])

    with st.form("frm_new_prev"):
        anno = datetime.now().year
        nome_cliente = cliente.get("RagioneSociale", "")
        nome_sicuro = "".join(c for c in nome_cliente if c.isalnum())[:6].upper()
        num_off = f"OFF-{anno}-{nome_sicuro}-{len(df_prev[df_prev['ClienteID'] == sel_id]) + 1:03d}"

        st.text_input("Numero Offerta", num_off, disabled=True)
        nome_file = st.text_input("Nome File", f"{num_off}.docx")
        template = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        submit = st.form_submit_button("💾 Genera Preventivo")

        if submit:
            try:
                tpl = TEMPLATES_DIR / TEMPLATE_OPTIONS[template]
                if not tpl.exists():
                    st.error(f"❌ Template non trovato: {tpl}")
                else:
                    doc = Document(tpl)
                    mappa = {
                        "CLIENTE": cliente.get("RagioneSociale", ""),
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
                            p.text = p.text.replace(f"<<{k}>>", str(v))
                            for run in p.runs:
                                run.font.size = Pt(10)
                    out = PREVENTIVI_DIR / nome_file
                    doc.save(out)

                    nuova_riga = {
                        "ClienteID": sel_id,
                        "NumeroOfferta": num_off,
                        "Template": TEMPLATE_OPTIONS[template],
                        "NomeFile": nome_file,
                        "Percorso": str(out),
                        "DataCreazione": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([nuova_riga])], ignore_index=True)
                    df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
                    st.success(f"✅ Preventivo generato: {out.name}")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante la creazione: {e}")

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
                            "⬇️ Scarica",
                            f.read(),
                            file_name=file_path.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{r['NumeroOfferta']}"
                        )
            with col3:
                if role == "admin":
                    if st.button("🗑 Elimina", key=f"del_{r['NumeroOfferta']}_{i}"):
                        try:
                            if file_path.exists():
                                file_path.unlink()
                            df_prev = df_prev.drop(i)
                            df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
                            st.success(f"🗑 Preventivo '{r['NumeroOfferta']}' eliminato.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Errore eliminazione: {e}")
# ==== FINE BLOCCO 3 ====
# =====================================
# PAGINA CONTRATTI
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    selected_cliente_id = st.session_state.pop("selected_cliente", None)
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    cliente_ids = df_cli["ClienteID"].astype(str).tolist()

    if selected_cliente_id and str(selected_cliente_id) in cliente_ids:
        sel_index = cliente_ids.index(str(selected_cliente_id))
    else:
        sel_index = 0

    sel_label = st.selectbox("Cliente", labels.tolist(), index=sel_index)
    sel_index = labels.tolist().index(sel_label)
    sel_id = cliente_ids[sel_index]
    cliente_info = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]
    rag_soc = cliente_info["RagioneSociale"]

    if selected_cliente_id:
        st.info(f"📌 Mostrati solo i contratti del cliente **{rag_soc}** (ID: {sel_id})")
        if st.button("🏠 Torna alla Home", use_container_width=True):
            st.session_state["nav_target"] = "Dashboard"
            st.rerun()

    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()

    # === NUOVO CONTRATTO ===
    with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            num = c1.text_input("Numero Contratto")
            din = c2.date_input("Data inizio", format="DD/MM/YYYY")
            durata = c3.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto", height=100)
            col_nf, col_ni, col_tot = st.columns(3)
            nf = col_nf.text_input("NOL_FIN")
            ni = col_ni.text_input("NOL_INT")
            tot = col_tot.text_input("TotRata")

            if st.form_submit_button("💾 Crea contratto"):
                try:
                    data_fine = pd.to_datetime(din) + pd.DateOffset(months=int(durata))
                    row = {
                        "ClienteID": str(sel_id),
                        "NumeroContratto": num,
                        "DataInizio": fmt_date(din),
                        "DataFine": fmt_date(data_fine),
                        "Durata": durata,
                        "DescrizioneProdotto": desc,
                        "NOL_FIN": nf,
                        "NOL_INT": ni,
                        "TotRata": tot,
                        "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([row])], ignore_index=True)
                    save_contratti(df_ct)
                    st.success("✅ Contratto creato con successo.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore creazione contratto: {e}")

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    # === FORMATTAZIONE ===
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
            return { 'backgroundColor': '#ffebee', 'color': '#b71c1c', 'fontWeight': 'bold' };
        } else if (stato === 'aperto' || stato === 'attivo') {
            return { 'backgroundColor': '#e8f5e9', 'color': '#1b5e20' };
        } else {
            return {};
        }
    }
    """)
    gb.configure_grid_options(getRowStyle=js_code)
    grid_opts = gb.build()

    st.markdown("### 📑 Lista contratti")
    AgGrid(
        disp,
        gridOptions=grid_opts,
        theme="balham",
        height=380,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True
    )

    st.divider()
    c1, c2 = st.columns(2)

    # === ESPORTAZIONE EXCEL ===
    with c1:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
        from openpyxl.utils import get_column_letter
        from io import BytesIO

        wb = Workbook()
        ws = wb.active
        ws.title = f"Contratti {rag_soc}"
        ws.merge_cells("A1:G1")
        title = ws["A1"]
        title.value = f"Contratti - {rag_soc}"
        title.font = Font(size=12, bold=True, color="2563EB")
        title.alignment = Alignment(horizontal="center", vertical="center")
        ws.append([])

        disp = disp.loc[:, ~disp.columns.str.lower().str.startswith("je")]
        headers = list(disp.columns)

        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left = Alignment(horizontal="left", vertical="top", wrap_text=True)
        bold = Font(bold=True, color="FFFFFF")
        thin_border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
        header_fill = PatternFill("solid", fgColor="2563EB")

        ws.append(headers)
        for i, h in enumerate(headers, 1):
            cell = ws.cell(row=ws.max_row, column=i)
            cell.font = bold
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border

        for _, riga in disp.iterrows():
            ws.append(list(riga))
            for col_idx, col_name in enumerate(headers, 1):
                cell = ws.cell(row=ws.max_row, column=col_idx)
                cell.border = thin_border
                cell.alignment = left if "descrizione" in col_name.lower() else center

        for col_idx in range(1, ws.max_column + 1):
            max_length = max(len(str(cell.value)) for cell in ws[get_column_letter(col_idx)])
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max_length + 4, 60)

        bio = BytesIO()
        wb.save(bio)
        st.download_button(
            "📘 Esporta Excel",
            data=bio.getvalue(),
            file_name=f"contratti_{rag_soc}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # === ESPORTAZIONE PDF ===
    with c2:
        from fpdf import FPDF
        from textwrap import wrap

        def safe_pdf_text(txt):
            if pd.isna(txt) or txt is None:
                return ""
            txt = str(txt).replace("€", "EUR").replace("–", "-").replace("—", "-")
            return txt.encode("latin-1", "replace").decode("latin-1")

        try:
            class PDF(FPDF):
                def header(self):
                    self.set_font("Arial", "B", 12)
                    titolo = safe_pdf_text(f"Contratti - {rag_soc}")
                    self.cell(0, 10, titolo, ln=1, align="C")
                    self.ln(3)

            pdf = PDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", size=9)

            widths = [35, 25, 25, 20, 140, 32]
            headers = ["Numero Contratto", "Data Inizio", "Data Fine", "Durata", "Descrizione Prodotto", "Tot Rata"]

            # Intestazione tabella
            pdf.set_fill_color(37, 99, 235)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", "B", 9)
            for i, h in enumerate(headers):
                pdf.cell(widths[i], 8, safe_pdf_text(h), border=1, align="C", fill=True)
            pdf.ln(8)

            # Dati tabella
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", "", 8)
            for _, row in disp.iterrows():
                values = [
                    safe_pdf_text(row.get("NumeroContratto", "")),
                    safe_pdf_text(row.get("DataInizio", "")),
                    safe_pdf_text(row.get("DataFine", "")),
                    safe_pdf_text(row.get("Durata", "")),
                    safe_pdf_text(row.get("DescrizioneProdotto", "")),
                    safe_pdf_text(row.get("TotRata", "")),
                ]
                # Calcolo altezza dinamica
                desc_lines = wrap(values[4], 110)
                max_lines = max(len(desc_lines), 1)
                line_height = 4
                row_height = line_height * max_lines
                x_start = pdf.get_x()
                y_start = pdf.get_y()

                for i, text in enumerate(values):
                    align = "L" if i == 4 else "C"
                    x = pdf.get_x()
                    pdf.multi_cell(widths[i], line_height, text, border=1, align=align)
                    pdf.set_xy(x + widths[i], y_start)

                pdf.ln(row_height)

            pdf_bytes = pdf.output(dest="S").encode("latin-1", errors="replace")
            st.download_button(
                "📗 Esporta PDF",
                data=pdf_bytes,
                file_name=f"contratti_{rag_soc}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"❌ Errore PDF: {e}")


# =====================================
# 📅 PAGINA RECALL E VISITE (versione bella)
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    df_cli = load_clienti()
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📅 Gestione Recall e Visite</h2>", unsafe_allow_html=True)
    st.divider()

    col1, col2 = st.columns(2)
    filtro_nome = col1.text_input("🔍 Cerca per nome cliente")
    filtro_citta = col2.text_input("🏙️ Cerca per città")

    filtrato = df_cli.copy()
    if filtro_nome:
        filtrato = filtrato[filtrato["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        filtrato = filtrato[filtrato["Citta"].str.contains(filtro_citta, case=False, na=False)]
    if filtrato.empty:
        st.warning("❌ Nessun cliente trovato con i criteri di ricerca.")
        return

    for c in ["UltimoRecall", "UltimaVisita", "ProssimoRecall", "ProssimaVisita"]:
        filtrato[c] = pd.to_datetime(filtrato[c], errors="coerce", dayfirst=True)

    oggi = pd.Timestamp.now().normalize()
    imminenti = filtrato[
        (filtrato["ProssimoRecall"].between(oggi, oggi + pd.DateOffset(days=30))) |
        (filtrato["ProssimaVisita"].between(oggi, oggi + pd.DateOffset(days=30)))
    ].copy()

    st.markdown("### 🔁 Recall e Visite imminenti (entro 30 giorni)")
    if imminenti.empty:
        st.success("✅ Nessun richiamo o visita imminente.")
    else:
        for i, r in imminenti.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1, 1, 0.8])
            c1.markdown(f"**{r['RagioneSociale']}**")
            c2.markdown(fmt_date(r["ProssimoRecall"]))
            c3.markdown(fmt_date(r["ProssimaVisita"]))
            if c4.button("Apri", key=f"imm_{i}", use_container_width=True):
                st.session_state["selected_cliente"] = r["ClienteID"]
                st.session_state["nav_target"] = "Clienti"
                st.rerun()

    st.divider()
    st.markdown("### ⚠️ Recall e Visite in ritardo")
    recall_vecchi = filtrato[
        filtrato["UltimoRecall"].notna() & (filtrato["UltimoRecall"] < oggi - pd.DateOffset(months=3))
    ]
    visite_vecchie = filtrato[
        filtrato["UltimaVisita"].notna() & (filtrato["UltimaVisita"] < oggi - pd.DateOffset(months=6))
    ]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 📞 Recall > 3 mesi")
        if recall_vecchi.empty:
            st.info("✅ Nessun recall scaduto.")
        else:
            for i, r in recall_vecchi.iterrows():
                c1, c2, c3 = st.columns([2.5, 1.2, 0.8])
                c1.markdown(f"**{r['RagioneSociale']}**")
                c2.markdown(fmt_date(r["UltimoRecall"]))
                if c3.button("Apri", key=f"rec_{i}", use_container_width=True):
                    st.session_state["selected_cliente"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Clienti"
                    st.rerun()

    with col2:
        st.markdown("#### 👣 Visite > 6 mesi")
        if visite_vecchie.empty:
            st.info("✅ Nessuna visita scaduta.")
        else:
            for i, r in visite_vecchie.iterrows():
                c1, c2, c3 = st.columns([2.5, 1.2, 0.8])
                c1.markdown(f"**{r['RagioneSociale']}**")
                c2.markdown(fmt_date(r["UltimaVisita"]))
                if c3.button("Apri", key=f"vis_{i}", use_container_width=True):
                    st.session_state["selected_cliente"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Clienti"
                    st.rerun()

    st.divider()
    st.markdown("### 🧾 Storico completo")
    tabella = filtrato[["RagioneSociale", "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]].copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        tabella[c] = tabella[c].apply(fmt_date)
    st.dataframe(tabella, use_container_width=True, hide_index=True)

# =====================================
# LISTA COMPLETA CLIENTI E CONTRATTI
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Contratti")
    filtro_nome = st.text_input("Cerca per nome cliente")
    filtro_citta = st.text_input("Cerca per città")

    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]], on="ClienteID", how="left")
    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]

    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce", dayfirst=True).dt.strftime("%d/%m/%Y")
    merged = merged[["RagioneSociale", "Citta", "NumeroContratto", "DataInizio", "DataFine", "Stato"]].fillna("")
    st.dataframe(merged, use_container_width=True, hide_index=True)
    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_clienti_contratti.csv", "text/csv")

# =====================================
# MAIN APP
# =====================================
def main():
    # === LOGIN ===
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    # === SIDEBAR ===
    st.sidebar.success(f"👤 Utente: {user} — Ruolo: {role}")

    # === PAGINE DISPONIBILI ===
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti
    }

    # === SELEZIONE PAGINA ===
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio(
        "📂 Menu principale",
        list(PAGES.keys()),
        index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0
    )

    # === CARICAMENTO DATI ===
    df_cli = load_clienti()
    df_ct = load_contratti()

    # === ESECUZIONE PAGINA SELEZIONATA ===
    if page in PAGES:
        PAGES[page](df_cli, df_ct, role)


# =====================================
# AVVIO APPLICAZIONE
# =====================================
if __name__ == "__main__":
    main()
