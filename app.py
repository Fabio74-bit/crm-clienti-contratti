# =====================================
# app.py — Gestionale Clienti SHT (versione completa 2025)
# =====================================
from __future__ import annotations
import streamlit as st
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

# --- stile generale pagina ---
st.markdown("""
<style>
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
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
# UTILS
# =====================================
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
    """Restituisce una data in formato DD/MM/YYYY."""
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
        v = float(pd.to_numeric(x, errors="coerce"))
        return f"{v:,.2f} €"
    except Exception:
        return ""

def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

# =====================================
# I/O DATI
# =====================================
def load_clienti() -> pd.DataFrame:
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
    df = ensure_columns(df, CLIENTI_COLS)
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = to_date_series(df[c])
    return df

def save_clienti(df: pd.DataFrame):
    out = df.copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti() -> pd.DataFrame:
    if CONTRATTI_CSV.exists():
        df = pd.read_csv(CONTRATTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
        df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio", "DataFine"]:
        df[c] = to_date_series(df[c])
    return df

def save_contratti(df: pd.DataFrame):
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# =====================================
# LOGIN
# =====================================
def do_login_fullscreen():
    """Pagina di login centrata e senza box vuoti, con redirect pulito alla Dashboard."""
    import time

    # === Se già loggato, ritorna direttamente ===
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    # === Stili CSS ===
    st.markdown(
        """
        <style>
        div[data-testid="stAppViewContainer"] {
            padding-top: 0 !important;
        }
        .block-container {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background-color: #f8fafc;
        }
        .login-box {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            border-radius: 16px;
            padding: 2rem 3rem;
            width: 340px;
        }
        .login-title {
            font-size: 1.4rem;
            font-weight: 600;
            color: #2563eb;
            text-align: center;
            margin-bottom: 1rem;
        }
        .center-logo {
            display: flex;
            justify-content: center;
            margin-bottom: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # === LOGO CENTRATO ===
    st.markdown("<div class='center-logo'>", unsafe_allow_html=True)
    st.image("https://www.shtsrl.com/template/images/logo.png", width=180)  # <-- Sostituisci col tuo URL/logo locale
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='login-title'>Accedi al CRM</div>", unsafe_allow_html=True)

    # === FORM DI LOGIN IN UN CONTENITORE PULITO ===
    placeholder = st.empty()
    with placeholder.container():
        username = st.text_input("👤 Nome utente", key="login_user").strip().lower()
        password = st.text_input("🔑 Password", type="password", key="login_pass")
        login_btn = st.button("Entra", use_container_width=True)

    # === Controllo credenziali ===
    if login_btn:
        users = st.secrets["auth"]["users"]
        if username in users and users[username]["password"] == password:
            st.session_state["user"] = username
            st.session_state["role"] = users[username].get("role", "viewer")
            st.session_state["logged_in"] = True
            placeholder.empty()  # 🔥 Elimina completamente il form (via DOM)
            st.success(f"✅ Benvenuto {username}!")
            time.sleep(0.3)
            st.rerun()  # 🔁 Ricarica l'app (mostrerà subito la dashboard)
        else:
            st.error("❌ Credenziali non valide.")

    # Blocca tutto se non loggato
    st.stop()
# ==========================
# KPI CARD (riutilizzata in Dashboard)
# ==========================
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
# DASHBOARD
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📊 Dashboard Gestionale</h2>", unsafe_allow_html=True)
    st.divider()

    now = pd.Timestamp.now().normalize()
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())

    # Nuovi contratti dell’anno
    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    start_year = pd.Timestamp(year=now.year, month=1, day=1)
    new_contracts = df_ct[(df_ct["DataInizio"].notna()) & (df_ct["DataInizio"] >= start_year)]
    count_new = len(new_contracts)

    # === KPI ===
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#1976D2"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#388E3C"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#D32F2F"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Nuovi contratti anno", count_new, "⭐", "#FBC02D"), unsafe_allow_html=True)
    st.divider()

    # =====================================
    # 🔄 AGGIORNA AUTOMATICAMENTE PROSSIMI RECALL / VISITE
    # =====================================
    df_cli["UltimoRecall"] = pd.to_datetime(df_cli["UltimoRecall"], errors="coerce", dayfirst=True)
    df_cli["ProssimoRecall"] = pd.to_datetime(df_cli["ProssimoRecall"], errors="coerce", dayfirst=True)
    df_cli["UltimaVisita"] = pd.to_datetime(df_cli["UltimaVisita"], errors="coerce", dayfirst=True)
    df_cli["ProssimaVisita"] = pd.to_datetime(df_cli["ProssimaVisita"], errors="coerce", dayfirst=True)

    # Aggiorna solo se mancano i prossimi ma ci sono gli ultimi
    mask_recall = df_cli["UltimoRecall"].notna() & df_cli["ProssimoRecall"].isna()
    mask_visita = df_cli["UltimaVisita"].notna() & df_cli["ProssimaVisita"].isna()

    if mask_recall.any():
        df_cli.loc[mask_recall, "ProssimoRecall"] = df_cli.loc[mask_recall, "UltimoRecall"] + pd.DateOffset(months=3)
    if mask_visita.any():
        df_cli.loc[mask_visita, "ProssimaVisita"] = df_cli.loc[mask_visita, "UltimaVisita"] + pd.DateOffset(months=6)

    # Salva solo se qualcosa è cambiato
    if mask_recall.any() or mask_visita.any():
        save_clienti(df_cli)

    # =====================================
    # RECALL E VISITE IMMINENTI
    # =====================================
    st.subheader("📞 Recall e 👣 Visite imminenti")

    df_cli["ProssimoRecall"] = pd.to_datetime(df_cli["ProssimoRecall"], errors="coerce")
    df_cli["ProssimaVisita"] = pd.to_datetime(df_cli["ProssimaVisita"], errors="coerce")

    prossimi_recall = df_cli[df_cli["ProssimoRecall"].between(now, now + pd.DateOffset(days=7), inclusive="both")]
    prossime_visite = df_cli[df_cli["ProssimaVisita"].between(now, now + pd.DateOffset(days=30), inclusive="both")]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🔁 Recall (entro 7 giorni)")
        if prossimi_recall.empty:
            st.info("✅ Nessun recall programmato.")
        else:
            for _, r in prossimi_recall.iterrows():
                st.markdown(f"- **{r['RagioneSociale']}** → {fmt_date(r['ProssimoRecall'])}")

    with col2:
        st.markdown("### 🗓️ Visite (entro 30 giorni)")
        if prossime_visite.empty:
            st.info("✅ Nessuna visita programmata.")
        else:
            for _, r in prossime_visite.iterrows():
                st.markdown(f"- **{r['RagioneSociale']}** → {fmt_date(r['ProssimaVisita'])}")

    st.divider()

    # =====================================
    # CLIENTI SENZA DATA FINE (DA OGGI IN POI)
    # =====================================
    st.subheader("🚫 Clienti senza Data Fine (da oggi in poi)")

    if df_ct is not None and not df_ct.empty:
        if "DataFine" not in df_ct.columns:
            st.info("ℹ️ Il campo 'DataFine' non è presente nel file contratti.")
        else:
            today = pd.Timestamp.today().normalize()

            ct = df_ct.copy()
            ct["DataInizio"] = pd.to_datetime(ct["DataInizio"], errors="coerce", dayfirst=True)
            ct["DataFine"] = pd.to_datetime(ct["DataFine"], errors="coerce", dayfirst=True)

            senza_datafine = ct[ct["DataFine"].isna()].copy()

            bad_ids = {"nuovocontratto", "nuovo contratto", "nan", ""}
            mask_bad = senza_datafine["ClienteID"].astype(str).str.strip().str.lower().isin(bad_ids)
            senza_datafine = senza_datafine[~mask_bad]

            mask_recent = senza_datafine["DataInizio"].notna() & (senza_datafine["DataInizio"] >= today)
            senza_datafine = senza_datafine.loc[mask_recent].copy()

            senza_datafine = senza_datafine.sort_values("DataInizio", ascending=True)

            if senza_datafine.empty:
                st.success("✅ Tutti i contratti da oggi in poi hanno una Data Fine impostata.")
            else:
                st.warning(f"⚠️ {len(senza_datafine)} contratti recenti senza Data Fine.")

                vis = (
                    senza_datafine
                    .merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
                    [["ClienteID", "RagioneSociale", "NumeroContratto", "DataInizio"]]
                    .reset_index(drop=True)
                )
                vis["DataInizio"] = vis["DataInizio"].apply(fmt_date)

                st.markdown(
                    "<div style='display:flex;font-weight:bold;margin-bottom:6px'>"
                    "<div style='width:15%'>ClienteID</div>"
                    "<div style='width:35%'>Ragione Sociale</div>"
                    "<div style='width:25%'>Numero Contratto</div>"
                    "<div style='width:15%'>Data Inizio</div>"
                    "<div style='width:10%;text-align:center'>Azione</div>"
                    "</div><hr>",
                    unsafe_allow_html=True,
                )

                for i, row in vis.iterrows():
                    c1, c2, c3, c4, c5 = st.columns([1.2, 3, 2, 1.3, 1])
                    c1.markdown(str(row["ClienteID"]))
                    c2.markdown(f"**{row['RagioneSociale'] or '—'}**")
                    c3.markdown(row["NumeroContratto"] or "—")
                    c4.markdown(row["DataInizio"] or "—")

                    btn_key = f"open_{row['ClienteID']}_{row.get('NumeroContratto','')}_{i}"
                    if c5.button("🔍 Apri Scheda", key=btn_key):
                        st.session_state["selected_cliente"] = row["ClienteID"]
                        st.session_state["nav_target"] = "Clienti"
                        st.rerun()
    else:
        st.info("ℹ️ Nessun dato contratti disponibile.")


# =====================================
# PAGINA CLIENTI
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Clienti")

    # 🔁 Se è stato selezionato un cliente dalla dashboard, aprilo automaticamente
    if "selected_cliente" in st.session_state:
        selected_id = st.session_state.pop("selected_cliente")
        if selected_id in df_cli["ClienteID"].values:
            cliente_row = df_cli[df_cli["ClienteID"] == selected_id].iloc[0]
            st.session_state["cliente_selezionato"] = cliente_row["RagioneSociale"]

    # 🔍 Ricerca
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

    # Selezione cliente
    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox(
        "Seleziona Cliente",
        options,
        index=options.index(st.session_state.get("cliente_selezionato", options[0])) if options else 0
    )

    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    # === HEADER CON NOME CLIENTE E PULSANTE CONTRATTI ===
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

    # === BLOCCO INFO RAPIDE ===
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

    # === BLOCCO DATE (modificabili direttamente) ===
    st.markdown("### ⚡ Recall e Visite")

    def _safe_date_for_input(val):
        d = as_date(val)
        if d is None or pd.isna(d):
            return None
        try:
            return pd.to_datetime(d).date()
        except Exception:
            return None

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("<div style='background:#E0E7FF;padding:8px;border-radius:8px'><b>⏰ Ultimo Recall</b></div>", unsafe_allow_html=True)
        ur = st.date_input(" ", value=_safe_date_for_input(cliente.get("UltimoRecall")), format="DD/MM/YYYY", key=f"ur_{sel_id}")

    with col2:
        st.markdown("<div style='background:#DBEAFE;padding:8px;border-radius:8px'><b>📅 Prossimo Recall</b></div>", unsafe_allow_html=True)
        pr = st.date_input(" ", value=_safe_date_for_input(cliente.get("ProssimoRecall")), format="DD/MM/YYYY", key=f"pr_{sel_id}")

    with col3:
        st.markdown("<div style='background:#DCFCE7;padding:8px;border-radius:8px'><b>👣 Ultima Visita</b></div>", unsafe_allow_html=True)
        uv = st.date_input(" ", value=_safe_date_for_input(cliente.get("UltimaVisita")), format="DD/MM/YYYY", key=f"uv_{sel_id}")

    with col4:
        st.markdown("<div style='background:#BBF7D0;padding:8px;border-radius:8px'><b>🗓️ Prossima Visita</b></div>", unsafe_allow_html=True)
        pv = st.date_input(" ", value=_safe_date_for_input(cliente.get("ProssimaVisita")), format="DD/MM/YYYY", key=f"pv_{sel_id}")

    # 🔄 Aggiorna automatico: se ci sono date Ultimo Recall / Ultima Visita, aggiorna anche Prossimi
    if ur and (not pr):
        pr = ur + pd.Timedelta(days=30)
    if uv and (not pv):
        pv = uv + pd.Timedelta(days=90)

    # Pulsante per salvare
    if st.button("💾 Salva Aggiornamenti", use_container_width=True):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "UltimoRecall"] = fmt_date(ur)
        df_cli.loc[idx, "ProssimoRecall"] = fmt_date(pr)
        df_cli.loc[idx, "UltimaVisita"] = fmt_date(uv)
        df_cli.loc[idx, "ProssimaVisita"] = fmt_date(pv)
        save_clienti(df_cli)
        st.success("✅ Date aggiornate correttamente!")
        st.rerun()

    st.divider()


    # ===== EXPANDER ANAGRAFICA EDITABILE =====
    with st.expander("✏️ Modifica anagrafica completa"):
        with st.form(key=f"frm_anagrafica_{sel_id}_{hash(sel_rag)}"):
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

            salva_btn = st.form_submit_button("💾 Salva modifiche")
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
                save_clienti(df_cli)
                st.success("✅ Anagrafica aggiornata.")
                st.rerun()

    st.divider()

    # ===== NOTE CLIENTE =====
    st.markdown("### 📝 Note Cliente")
    note_attuali = cliente.get("NoteCliente", "")
    nuove_note = st.text_area("Modifica note cliente:", note_attuali, height=180, key=f"note_{sel_id}")
    if st.button("💾 Salva Note"):
        idx_row = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx_row, "NoteCliente"] = nuove_note
        save_clienti(df_cli)
        st.success("✅ Note aggiornate.")
        st.rerun()


            # =======================================================
    # SEZIONE PREVENTIVI DOCX (con gestione date integrata)
    # =======================================================
    st.divider()
    st.markdown("### 🧾 Gestione Preventivi")

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

    # === Funzione per numero preventivo ===
    def genera_numero_offerta(cliente_nome: str, cliente_id: str) -> str:
        anno = datetime.now().year
        nome_sicuro = "".join(c for c in cliente_nome if c.isalnum())[:6].upper()
        subset = df_prev[df_prev["ClienteID"].astype(str) == str(cliente_id)]
        seq = len(subset) + 1
        return f"OFF-{anno}-{nome_sicuro}-{seq:03d}"

    next_num = genera_numero_offerta(cliente.get("RagioneSociale", ""), sel_id)

    # === CREAZIONE NUOVO PREVENTIVO ===
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

                    # === Mappatura campi cliente e date ===
                    mappa = {
                        "CLIENTE": cliente.get("RagioneSociale", ""),
                        "INDIRIZZO": cliente.get("Indirizzo", ""),
                        "CITTA": cliente.get("Citta", "") or cliente.get("Città", ""),
                        "NUMERO_OFFERTA": num,
                        "DATA": datetime.now().strftime("%d/%m/%Y"),
                        "ULTIMO_RECALL": fmt_date(cliente.get("UltimoRecall")),
                        "PROSSIMO_RECALL": fmt_date(cliente.get("ProssimoRecall")),
                        "ULTIMA_VISITA": fmt_date(cliente.get("UltimaVisita")),
                        "PROSSIMA_VISITA": fmt_date(cliente.get("ProssimaVisita")),
                    }

                    # 🔄 Sostituzione segnaposto <<CHIAVE>>
                    for p in doc.paragraphs:
                        full_text = "".join(run.text for run in p.runs)
                        modified = False
                        for chiave, valore in mappa.items():
                            token = f"<<{chiave}>>"
                            if token in full_text:
                                full_text = full_text.replace(token, str(valore))
                                modified = True
                        if modified:
                            for run in p.runs:
                                run.text = ""
                            p.runs[0].text = full_text
                            for run in p.runs:
                                run.font.size = Pt(10)
                            p.alignment = 0

                    doc.save(output_path)
                    st.success(f"✅ Preventivo salvato: {output_path.name}")

                    # === Registro CSV preventivi ===
                    nuova_riga = {
                        "ClienteID": sel_id,
                        "NumeroOfferta": num,
                        "Template": TEMPLATE_OPTIONS[template],
                        "NomeFile": nome_file,
                        "Percorso": str(output_path),
                        "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([nuova_riga])], ignore_index=True)
                    df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")

                    st.toast("✅ Preventivo aggiunto al database", icon="📄")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante la creazione del preventivo: {e}")

    # === ELENCO PREVENTIVI ===
    st.divider()
    st.markdown("### 📂 Elenco Preventivi Cliente")

    prev_cli = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        prev_cli = prev_cli.sort_values(by="DataCreazione", ascending=False)

        st.markdown("""
        <style>
         .preventivo-card {
             border:1px solid #ddd;
             border-radius:10px;
             padding:8px 14px;
             margin-bottom:8px;
             background:#f9f9f9;
         }
         .preventivo-header {font-weight:600; color:#222;}
         .preventivo-info {font-size:0.9rem; color:#444;}
        </style>
        """, unsafe_allow_html=True)

        for i, r in prev_cli.iterrows():
            file_path = Path(r["Percorso"])
            col1, col2, col3 = st.columns([0.5, 0.3, 0.2])
            with col1:
                st.markdown(
                    f"<div class='preventivo-card'>"
                    f"<div class='preventivo-header'>{r['NumeroOfferta']}</div>"
                    f"<div class='preventivo-info'>{r['Template']}</div>"
                    f"<div class='preventivo-info'>Creato il {r['DataCreazione']}</div>"
                    f"</div>", unsafe_allow_html=True
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
                    if st.button("🗑 Elimina", key=f"del_{r['NumeroOfferta']}_{i}"):
                        try:
                            if file_path.exists():
                                file_path.unlink()
                            df_prev = df_prev.drop(i)
                            df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")
                            st.success(f"🗑 Preventivo '{r['NumeroOfferta']}' eliminato.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Errore eliminazione: {e}")


# =====================================
# CONTRATTI (nuova versione completa 2025)
# =====================================
# =====================================
# CONTRATTI (versione definitiva con pulsante fisso)
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    import io
    from fpdf import FPDF
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

    # --- CSS: full screen + pulsante fisso ---
    st.markdown("""
    <style>
    div.block-container {padding: 0 1rem 1rem 1rem !important; max-width: 100%;}
    [data-testid="stSidebar"] {background-color: #f8fafc;}
    .floating-home {
        position: fixed;
        top: 20px;
        right: 25px;
        z-index: 1000;
        background-color: #2563eb;
        color: white;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        padding: 8px 14px;
        cursor: pointer;
        box-shadow: 0 3px 8px rgba(0,0,0,0.2);
        transition: all 0.2s ease;
    }
    .floating-home:hover {
        background-color: #1e40af;
        transform: scale(1.03);
    }
    </style>

    <script>
    function goHome() {
        window.parent.postMessage({isStreamlitCommand: true, command: 'setSessionState', args: {'nav_target': 'Dashboard'}}, '*');
    }
    </script>

    <button class="floating-home" onclick="goHome()">🏠 Home</button>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='margin-top:3rem'>📄 Gestione Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # --- Se arrivi da link "Vai ai Contratti" ---
    selected_cliente_id = st.session_state.pop("selected_cliente", None)
    cliente_ids = df_cli["ClienteID"].astype(str).tolist()
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1).tolist()

    if selected_cliente_id and str(selected_cliente_id) in cliente_ids:
        sel_index = cliente_ids.index(str(selected_cliente_id))
    else:
        sel_index = 0

    sel_label = st.selectbox("Cliente", labels, index=sel_index)
    sel_id = cliente_ids[sel_index]
    cliente_info = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]
    rag_soc = cliente_info["RagioneSociale"]

    st.divider()

    # --- Filtra i contratti del cliente ---
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()

    # --- Aggiunta nuovo contratto ---
    st.subheader(f"➕ Nuovo contratto per {rag_soc}")
    with st.form("frm_new_contract_full"):
        c1, c2, c3 = st.columns(3)
        with c1:
            num = st.text_input("Numero Contratto")
        with c2:
            data_inizio = st.date_input("Data Inizio", format="DD/MM/YYYY")
        with c3:
            durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
        desc = st.text_area("Descrizione prodotto", height=80)
        col_nf, col_ni, col_tot = st.columns(3)
        with col_nf:
            nf = st.text_input("NOL_FIN")
        with col_ni:
            ni = st.text_input("NOL_INT")
        with col_tot:
            tot = st.text_input("TotRata")

        if st.form_submit_button("💾 Crea contratto"):
            try:
                new_row = {
                    "ClienteID": str(sel_id),
                    "NumeroContratto": num,
                    "DataInizio": pd.to_datetime(data_inizio),
                    "DataFine": pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata)),
                    "Durata": durata,
                    "DescrizioneProdotto": desc,
                    "NOL_FIN": nf,
                    "NOL_INT": ni,
                    "TotRata": tot,
                    "Stato": "aperto"
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([new_row])], ignore_index=True)
                save_contratti(df_ct)
                st.success("✅ Contratto creato con successo.")
                st.rerun()
            except Exception as e:
                st.error(f"Errore durante la creazione del contratto: {e}")

    st.divider()

    # --- Tabella contratti editabile ---
    st.markdown("### 📋 Contratti esistenti")

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp = disp.drop(columns=["ClienteID"], errors="ignore")

    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(editable=True, wrapText=True, autoHeight=True, resizable=True)
    gb.configure_selection("single")
    gb.configure_grid_options(domLayout="normal", ensureDomOrder=True)
    gb.configure_columns(list(disp.columns), cellStyle={"whiteSpace": "normal"})

    # --- COLORI RIGHE ---
    js_style = JsCode("""
    function(params) {
        if (!params.data.Stato) return {};
        const stato = params.data.Stato.toLowerCase();
        if (stato === 'chiuso') {
            return { 'backgroundColor': '#ffebee', 'color': '#b71c1c', 'fontWeight': 'bold' };
        } else {
            return { 'backgroundColor': 'white', 'color': 'black' };
        }
    }
    """)
    gb.configure_grid_options(getRowStyle=js_style)

    grid_opts = gb.build()

    st.markdown("<div style='height:620px'>", unsafe_allow_html=True)
    grid_return = AgGrid(
        disp,
        gridOptions=grid_opts,
        theme="balham",
        height=620,
        width="100%",
        update_mode=GridUpdateMode.VALUE_CHANGED,
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=False
    )
    st.markdown("</div>", unsafe_allow_html=True)

    updated_rows = grid_return["data"]

    # --- Salva modifiche ---
    if st.button("💾 Salva modifiche ai contratti", use_container_width=True):
        try:
            updated_rows["DataInizio"] = pd.to_datetime(updated_rows["DataInizio"], errors="coerce", dayfirst=True)
            updated_rows["DataFine"] = pd.to_datetime(updated_rows["DataFine"], errors="coerce", dayfirst=True)
            updated_rows["ClienteID"] = sel_id
            save_contratti(updated_rows)
            st.success("✅ Tutte le modifiche salvate.")
            st.rerun()
        except Exception as e:
            st.error(f"Errore durante il salvataggio: {e}")

    st.divider()

    # --- Pulsante Chiudi/Riapri ---
    st.markdown("### ⚙️ Stato contratti")
    for i, r in updated_rows.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.65, 0.3])
        c2.caption(f"{r['NumeroContratto']} — {r['DescrizioneProdotto'][:60]}")
        stato = (r["Stato"] or "aperto").lower()
        if stato == "chiuso":
            if c3.button("🔓 Riapri", key=f"riapri_{i}"):
                df_ct.loc[df_ct.index[i], "Stato"] = "aperto"
                save_contratti(df_ct)
                st.rerun()
        else:
            if c3.button("❌ Chiudi", key=f"chiudi_{i}"):
                df_ct.loc[df_ct.index[i], "Stato"] = "chiuso"
                save_contratti(df_ct)
                st.rerun()

    st.divider()

    # --- Esportazione CSV ---
    csv = updated_rows.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("📄 Esporta CSV (orizzontale)", csv, f"contratti_{rag_soc}.csv", "text/csv", use_container_width=True)

    # --- Esportazione PDF migliorata ---
    if st.button("📘 Esporta PDF (layout migliorato)", use_container_width=True):
        try:
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, f"Contratti - {rag_soc}", ln=1, align="C")
            pdf.set_font("Arial", "", 9)
            pdf.ln(4)

            headers = ["Numero", "Data Inizio", "Data Fine", "Durata", "Descrizione", "TotRata", "Stato"]
            col_widths = [35, 25, 25, 20, 110, 25, 20]

            # Header
            for h, w in zip(headers, col_widths):
                pdf.cell(w, 8, safe_text(h), 1, 0, "C")
            pdf.ln()

            # Rows (multiline)
            for _, row in updated_rows.iterrows():
                pdf.set_font("Arial", "", 8)
                row_data = [
                    safe_text(row.get("NumeroContratto", "")),
                    safe_text(row.get("DataInizio", "")),
                    safe_text(row.get("DataFine", "")),
                    safe_text(row.get("Durata", "")),
                    safe_text(row.get("DescrizioneProdotto", "")),
                    safe_text(row.get("TotRata", "")),
                    safe_text(row.get("Stato", "")),
                ]
                y_start = pdf.get_y()
                x_start = pdf.get_x()
                for text, width in zip(row_data, col_widths):
                    x_before = pdf.get_x()
                    pdf.multi_cell(width, 6, text, 1, "L")
                    pdf.set_xy(x_before + width, y_start)
                pdf.ln(6)
            pdf_buffer = io.BytesIO(pdf.output(dest="S").encode("latin-1", "replace"))
            st.download_button(
                "⬇️ Scarica PDF",
                data=pdf_buffer,
                file_name=f"contratti_{rag_soc}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Errore durante l'esportazione PDF: {e}")

# =====================================
# LISTA COMPLETA CLIENTI E CONTRATTI
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Contratti")

    st.markdown("### 🔍 Filtra Clienti")
    col1, col2 = st.columns(2)
    with col1:
        filtro_nome = st.text_input("Cerca per nome cliente")
    with col2:
        filtro_citta = st.text_input("Cerca per città")

    merged = df_ct.merge(
        df_cli[["ClienteID", "RagioneSociale", "Citta"]],
        on="ClienteID",
        how="left"
    )

    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]

    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged = merged[
        ["RagioneSociale", "Citta", "NumeroContratto", "DataInizio", "DataFine", "Stato"]
    ].fillna("")

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

    # === PAGINE ===
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📋 Lista Clienti": page_lista_clienti
    }

    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio(
        "📂 Menu principale",
        list(PAGES.keys()),
        index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0
    )

    # === DATI ===
    df_cli = load_clienti()
    df_ct = load_contratti()

    # === RENDER PAGINA ===
    if page in PAGES:
        PAGES[page](df_cli, df_ct, role)


if __name__ == "__main__":
    main()
