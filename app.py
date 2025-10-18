# =====================================
# app.py — Gestionale Clienti SHT (versione completa 2025)
# =====================================
from __future__ import annotations
import streamlit as st
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")
# Forza lo scroll in alto dopo ogni rerun (navigazione)
st.markdown("""
<script>
    window.addEventListener('load', function() {
        window.scrollTo(0, 0);
    });
</script>
""", unsafe_allow_html=True)
# --- stile generale pagina ---
st.markdown("""
<style>
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}

/* 🔧 Fix: rimuove qualsiasi blocco o margine vuoto sopra la prima card */
div[data-testid="stVerticalBlock"] > div:first-child:empty,
div[data-testid="stVerticalBlock"] > div:first-child > div:empty,
div[data-testid="stVerticalBlock"] > div:first-child > div:has(> div:empty),
div[data-testid="stVerticalBlock"] > div:first-child > div:has(> div > div:empty),
div[data-testid="stVerticalBlock"]:has(> div:empty),
section.main > div:has(div:empty) {
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* 🔹 Rimuove spazi extra sopra il contenuto principale */
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
        # Se vuoto, NaN, None, o stringa non numerica -> restituisci vuoto
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
# I/O DATI — VERSIONE PULITA (NO NAN)
# =====================================

def load_clienti() -> pd.DataFrame:
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",", encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

    # 🔹 Pulizia totale — anche delle stringhe "nan"
    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
        .applymap(lambda x: "" if str(x).strip().lower() in ["nan", "none", "null", "nat"] else x)
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

    # 🔹 Pulizia totale — anche delle stringhe "nan"
    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
        .applymap(lambda x: "" if str(x).strip().lower() in ["nan", "none", "null", "nat"] else x)
    )

    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio", "DataFine"]:
        df[c] = to_date_series(df[c])

    return df


    # 🔹 Pulizia totale di NaN, None, NaT, ecc.
    df = df.replace(
        to_replace=["nan", "NaN", "None", "NULL", "null", "NaT"],
        value="",
        regex=True
    ).fillna("")

    # 🔹 Garantisce tutte le colonne
    df = ensure_columns(df, CONTRATTI_COLS)

    # 🔹 Conversione date
    for c in ["DataInizio", "DataFine"]:
        df[c] = to_date_series(df[c])

    return df


def save_contratti(df: pd.DataFrame):
    """Salva i contratti puliti nel CSV (senza NaN o valori nulli)."""
    out = df.copy()

    # 🔹 Pulizia completa prima del salvataggio
    out = out.replace(
        to_replace=["nan", "NaN", "None", "NULL", "null", "NaT"],
        value="",
        regex=True
    ).fillna("")

    # 🔹 Format date
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(
            lambda d: "" if pd.isna(d) or d == "" else pd.to_datetime(d).strftime("%Y-%m-%d")
        )

    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")


def do_login_fullscreen():
    """Pagina di login centrata e compatta (funzionante al 100% in Streamlit)."""
    import time

    # Se già loggato, ritorna subito
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    # === STILE GENERALE ===
    st.markdown("""
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

    /* 🔧 Rimuove qualsiasi contenitore Streamlit vuoto sopra al login */
    div[data-testid="stVerticalBlock"] > div:empty,
    div[data-testid="stVerticalBlock"] > div:first-child:empty,
    div[data-testid="stVerticalBlock"]:has(> div:empty) {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* === CARD LOGIN === */
    .login-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        padding: 2rem 2.5rem;
        width: 360px;
        text-align: center;
        animation: fadeIn 0.4s ease-in-out;
    }

    /* Effetto comparsa */
    @keyframes fadeIn {
        from {opacity: 0; transform: translateY(-10px);}
        to {opacity: 1; transform: translateY(0);}
    }

    .login-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #2563eb;
        margin: 0.8rem 0 1.4rem 0;
    }

    .stTextInput>div>div>input {
        width: 260px !important;
        text-align: left !important;
        font-size: 0.9rem !important;
        padding: 6px 8px !important;
        border: 1px solid #d1d5db !important;
        border-radius: 6px !important;
        transition: border-color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
    }
    .stTextInput>div>div>input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 2px rgba(37,99,235,0.2) !important;
        outline: none !important;
    }
    .stButton>button {
        width: 260px !important;
        font-size: 0.9rem !important;
        padding: 0.4rem 0 !important;
        border-radius: 6px !important;
        background-color: #2563eb !important;
        color: white !important;
        border: none !important;
    }
    .stButton>button:hover {
        background-color: #1e40af !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # === LAYOUT CENTRATO ===
    login_col1, login_col2, login_col3 = st.columns([1, 2, 1])
    with login_col2:
        with st.container():
            st.markdown("<div class='login-card'>", unsafe_allow_html=True)
            st.image("https://www.shtsrl.com/template/images/logo.png", width=140)
            st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)

            username = st.text_input(
                "Nome utente",
                key="login_user",
                placeholder="Inserisci il tuo nome utente"
            ).strip().lower()

            password = st.text_input(
                "Password",
                type="password",
                key="login_pass",
                placeholder="Inserisci la tua password"
            )

            login_btn = st.button("Entra")

            st.markdown("</div>", unsafe_allow_html=True)

    # === LOGICA LOGIN ===
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
# DASHBOARD (Stile Pulito Business)
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # === Stile generale ===
    st.markdown("""
    <style>
    .section-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #2563eb;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .section-title span {
        font-size: 1.3rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # === HEADER E KPI ===
    st.image(LOGO_URL, width=120)
    st.markdown("<h2 style='margin-top:0.2rem;'>📊 Dashboard Gestionale</h2>", unsafe_allow_html=True)
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

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#1976D2"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#388E3C"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#D32F2F"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Nuovi contratti anno", count_new, "⭐", "#FBC02D"), unsafe_allow_html=True)
    st.divider()

        # =====================================
    # ⚠️ CONTRATTI IN SCADENZA ENTRO 6 MESI (TABELLARE)
    # =====================================
    with st.container():
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'><span>⚠️</span>Contratti in scadenza entro 6 mesi</div>", unsafe_allow_html=True)

        oggi = pd.Timestamp.now().normalize()
        entro_6_mesi = oggi + pd.DateOffset(months=6)

        # Filtra solo contratti attivi in scadenza
        df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce")
        scadenze = df_ct[
            (df_ct["DataFine"].notna())
            & (df_ct["DataFine"] >= oggi)
            & (df_ct["DataFine"] <= entro_6_mesi)
            & (df_ct["Stato"].str.lower() != "chiuso")
        ].copy()

        if scadenze.empty:
            st.success("✅ Nessun contratto attivo in scadenza nei prossimi 6 mesi.")
        else:
            scadenze = scadenze.merge(
                df_cli[["ClienteID", "RagioneSociale"]],
                on="ClienteID", how="left"
            )
            scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
            scadenze = scadenze.sort_values("DataFine", ascending=True)

            # ✅ Totale contratti in scadenza
            st.markdown(f"**🔢 {len(scadenze)} contratti attivi in scadenza entro 6 mesi:**")

            # === Stile tabella ===
            st.markdown("""
            <style>
            .tbl-scadenze {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9rem;
            }
            .tbl-scadenze th, .tbl-scadenze td {
                border-bottom: 1px solid #e5e7eb;
                padding: 8px 10px;
                text-align: left;
            }
            .tbl-scadenze th {
                background-color: #f3f4f6;
                font-weight: 600;
            }
            .tbl-scadenze tr:hover td {
                background-color: #fef9c3;
            }
            </style>
            """, unsafe_allow_html=True)

            # === Header tabella ===
            st.markdown(
                "<table class='tbl-scadenze'>"
                "<thead><tr>"
                "<th>Cliente</th>"
                "<th>Contratto</th>"
                "<th>Scadenza</th>"
                "<th>Stato</th>"
                "<th style='text-align:center;width:120px;'>Azione</th>"
                "</tr></thead><tbody>",
                unsafe_allow_html=True
            )

            # === Righe tabella ===
            for i, r in scadenze.iterrows():
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 0.8, 0.8])
                with col1:
                    st.markdown(f"**{r['RagioneSociale']}**")
                with col2:
                    st.markdown(r["NumeroContratto"] or "—")
                with col3:
                    st.markdown(r["DataFine"] or "—")
                with col4:
                    st.markdown(r["Stato"] or "—")
                with col5:
                    if st.button("Apri", key=f"open_scad_{i}", use_container_width=True):
                        st.session_state["selected_cliente"] = r["ClienteID"]
                        st.session_state["nav_target"] = "Contratti"
                        st.rerun()

            st.markdown("</tbody></table>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # =====================================
    # 🚫 CLIENTI SENZA DATA FINE
    # =====================================
    with st.container():
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'><span>🚫</span>Clienti senza Data Fine</div>", unsafe_allow_html=True)

        if df_ct is not None and not df_ct.empty:
            today = pd.Timestamp.today().normalize()
            ct = df_ct.copy()
            ct["DataInizio"] = pd.to_datetime(ct["DataInizio"], errors="coerce", dayfirst=True)
            ct["DataFine"] = pd.to_datetime(ct["DataFine"], errors="coerce", dayfirst=True)
            senza_datafine = ct[ct["DataFine"].isna()].copy()

            senza_datafine = senza_datafine[
                (senza_datafine["DataInizio"].notna()) & (senza_datafine["DataInizio"] >= today)
            ].copy()

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
                for i, row in vis.iterrows():
                    c1, c2, c3, c4, c5 = st.columns([1.2, 3, 2, 1.3, 1])
                    c1.markdown(str(row["ClienteID"]))
                    c2.markdown(f"**{row['RagioneSociale'] or '—'}**")
                    c3.markdown(row["NumeroContratto"] or "—")
                    c4.markdown(row["DataInizio"] or "—")
                    if c5.button("Apri", key=f"open_{row['ClienteID']}_{i}"):
                        st.session_state["selected_cliente"] = row["ClienteID"]
                        st.session_state["nav_target"] = "Clienti"
                        st.rerun()

        else:
            st.info("ℹ️ Nessun dato contratti disponibile.")

        st.markdown("</div>", unsafe_allow_html=True)




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
# CONTRATTI (AgGrid + gestione stato)
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # === 🔁 Se arrivi da "Vai ai Contratti" ===
    selected_cliente_id = None
    if "selected_cliente" in st.session_state:
        selected_cliente_id = st.session_state.pop("selected_cliente")

    # === Prepara lista clienti ===
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    cliente_ids = df_cli["ClienteID"].astype(str).tolist()

    # === Se arrivi da Dashboard, seleziona automaticamente quel cliente ===
    if selected_cliente_id and str(selected_cliente_id) in cliente_ids:
        sel_index = cliente_ids.index(str(selected_cliente_id))
    else:
        sel_index = 0

    # === Selettore cliente sicuro ===
    sel_label = st.selectbox("Cliente", labels.tolist(), index=sel_index if sel_index < len(labels) else 0)

    try:
        sel_index = labels.tolist().index(sel_label)
    except ValueError:
        sel_index = 0  # fallback di sicurezza se qualcosa non combacia

    sel_id = cliente_ids[sel_index]
    cliente_info = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]
    rag_soc = cliente_info["RagioneSociale"]

    # 🔙 Pulsante ritorno se arrivi da link diretto
    if selected_cliente_id:
        st.info(f"📌 Mostrati solo i contratti del cliente **{rag_soc}** (ID: {sel_id})")
        if st.button("🏠 Torna alla Home", use_container_width=True):
            st.session_state["nav_target"] = "Dashboard"
            st.rerun()

    # === Filtra i contratti del cliente selezionato ===
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()

    # === SEZIONE NUOVO CONTRATTO ===
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
            col_nf, col_ni, col_tot = st.columns(3)
            with col_nf:
                nf = st.text_input("NOL_FIN")
            with col_ni:
                ni = st.text_input("NOL_INT")
            with col_tot:
                tot = st.text_input("TotRata")

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
                st.success("✅ Contratto creato con successo.")
                st.rerun()

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

       # === FORMATTAZIONE E STILE TABELLA ===
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

    # Recupera la ragione sociale (fallback se non definita)
    rag_soc = cliente_info["RagioneSociale"] if "cliente_info" in locals() else "Cliente"
    
    if disp.empty:
        st.warning("⚠️ Nessun dato disponibile per l’esportazione.")
    else:
        # 👇 CREA LE DUE COLONNE
        c1, c2 = st.columns(2)
    st.divider()

    # =====================================
    # 🔹 Pulizia definitiva dei dati prima di esportazione
    # =====================================
    rag_soc = cliente_info["RagioneSociale"] if "cliente_info" in locals() else "Cliente"

    if "disp" not in locals() or disp is None or disp.empty:
        st.warning("⚠️ Nessun contratto disponibile per l’esportazione.")
        st.stop()

    disp = disp.copy().astype(str)
    disp = disp.replace(
        to_replace=r"^(nan|NaN|None|null|NULL|NaT|nan\s*EUR|\s*)$",
        value="",
        regex=True
    )
    for c in disp.columns:
        disp[c] = disp[c].apply(lambda x: x.strip() if isinstance(x, str) else x)

    # === CREA LE DUE COLONNE ===
    c1, c2 = st.columns(2)

    # === ESPORTAZIONE EXCEL MIGLIORATA ===
    with c1:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
        from openpyxl.utils import get_column_letter
        from io import BytesIO

        wb = Workbook()
        ws = wb.active
        ws.title = f"Contratti {rag_soc}"

        # === TITOLO CLIENTE ===
        ws.merge_cells("A1:G1")
        title = ws["A1"]
        title.value = f"Contratti - {rag_soc}"
        title.font = Font(size=12, bold=True, color="2563EB")
        title.alignment = Alignment(horizontal="center", vertical="center")
        ws.append([])

        # === PULIZIA COLONNE ===
        disp = disp.loc[:, ~disp.columns.str.lower().str.startswith("je")]
        headers = list(disp.columns)

        center = Alignment(horizontal="center", vertical="center", wrap_text=True)
        left = Alignment(horizontal="left", vertical="top", wrap_text=True)
        bold = Font(bold=True, color="FFFFFF")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin")
        )
        header_fill = PatternFill("solid", fgColor="2563EB")

        # === INTESTAZIONI ===
        ws.append(headers)
        for i, h in enumerate(headers, 1):
            cell = ws.cell(row=ws.max_row, column=i)
            cell.font = bold
            cell.fill = header_fill
            cell.alignment = center
            cell.border = thin_border

        # === RIGHE DATI ===
        for _, riga in disp.iterrows():
            ws.append(list(riga))
            for col_idx, col_name in enumerate(headers, 1):
                cell = ws.cell(row=ws.max_row, column=col_idx)
                cell.border = thin_border
                cell.alignment = left if "descrizione" in col_name.lower() else center

        # === ADATTA LARGHEZZA E ALTEZZA ===
        for col_idx in range(1, ws.max_column + 1):
            max_length = 0
            for row in range(1, ws.max_row + 1):
                cell = ws.cell(row=row, column=col_idx)
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    pass
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = min(max_length + 4, 60)

        for r in range(3, ws.max_row + 1):
            ws.row_dimensions[r].height = 30

        bio = BytesIO()
        wb.save(bio)
        st.download_button(
            "📘 Esporta Excel",
            data=bio.getvalue(),
            file_name=f"contratti_{rag_soc}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # === ESPORTAZIONE PDF MIGLIORATA ===
    with c2:
        from fpdf import FPDF
        from textwrap import wrap

        def safe_pdf_text(txt: str) -> str:
            if pd.isna(txt) or txt is None:
                return ""
            if not isinstance(txt, str):
                txt = str(txt)
            txt = txt.replace("€", "EUR").replace("–", "-").replace("—", "-")
            return txt.encode("latin-1", "replace").decode("latin-1")

        try:
            class PDF(FPDF):
                def header(self):
                    self.set_font("Arial", "B", 12)
                    titolo = safe_pdf_text(f"Contratti - {rag_soc}")
                    self.cell(0, 8, titolo, ln=1, align="C")
                    self.ln(4)

            pdf = PDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)

            headers = ["Numero Contratto", "Data Inizio", "Data Fine", "Durata",
                       "Descrizione Prodotto", "Tot Rata", "Stato"]
            widths = [35, 25, 25, 20, 90, 25, 25]
            pdf.set_font("Arial", "B", 9)
            pdf.set_fill_color(37, 99, 235)
            pdf.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                pdf.cell(widths[i], 7, safe_pdf_text(h), 1, 0, "C", fill=True)
            pdf.ln(7)

            pdf.set_font("Arial", "", 9)
            pdf.set_text_color(0, 0, 0)
            for _, row in disp.iterrows():
                desc = safe_pdf_text(row.get("DescrizioneProdotto", ""))
                desc_lines = wrap(desc, 70)
                h = max(7, len(desc_lines) * 4)

                x = pdf.get_x()
                y = pdf.get_y()

                def cell(text, w, align="C"):
                    pdf.multi_cell(w, h, safe_pdf_text(text or ""), 1, align)
                    pdf.set_xy(x + w, y)

                cell(row.get("NumeroContratto", ""), widths[0])
                cell(row.get("DataInizio", ""), widths[1])
                cell(row.get("DataFine", ""), widths[2])
                cell(row.get("Durata", ""), widths[3])
                pdf.multi_cell(widths[4], 4, desc, 1, "L")
                y_new = pdf.get_y()
                pdf.set_xy(x + sum(widths[:5]), y)
                cell(row.get("TotRata", ""), widths[5])
                cell(row.get("Stato", ""), widths[6])
                pdf.set_y(max(y_new, y + h))

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
# 📅 PAGINA RICHIAMI E VISITE (stile Pulito Business)
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # --- Stile coerente con dashboard ---
    st.markdown("""
    <style>
    .section-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #2563eb;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .section-title span {
        font-size: 1.3rem;
    }
    .tbl-recall {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }
    .tbl-recall th, .tbl-recall td {
        border-bottom: 1px solid #e5e7eb;
        padding: 8px 10px;
        text-align: left;
    }
    .tbl-recall th {
        background-color: #f3f4f6;
        font-weight: 600;
    }
    .tbl-recall tr:hover td {
        background-color: #fef9c3;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Intestazione ---
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📅 Gestione Recall e Visite</h2>", unsafe_allow_html=True)
    st.divider()

    # --- FILTRO RICERCA ---
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'><span>🔍</span>Filtra clienti</div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([0.4, 0.4, 0.2])
    with col1:
        filtro_nome = st.text_input("Cerca per nome cliente")
    with col2:
        filtro_citta = st.text_input("Cerca per città")
    with col3:
        if st.button("🔄 Pulisci filtri"):
            st.experimental_rerun()

    filtrato = df_cli.copy()
    if filtro_nome:
        filtrato = filtrato[filtrato["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        filtrato = filtrato[filtrato["Citta"].str.contains(filtro_citta, case=False, na=False)]

    if filtrato.empty:
        st.warning("❌ Nessun cliente trovato con i criteri di ricerca.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    df_cli = filtrato.copy()
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Conversione date ---
    oggi = pd.Timestamp.now().normalize()
    for col in ["UltimoRecall", "UltimaVisita", "ProssimoRecall", "ProssimaVisita"]:
        df_cli[col] = pd.to_datetime(df_cli[col], errors="coerce")

       # =====================================
    # 🔁 RECALL E VISITE IMMINENTI (entro 30 giorni)
    # =====================================
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'><span>🔁</span>Recall e Visite imminenti (entro 30 giorni)</div>", unsafe_allow_html=True)

    oggi = pd.Timestamp.now().normalize()
    df_cli["ProssimoRecall"] = pd.to_datetime(df_cli["ProssimoRecall"], errors="coerce")
    df_cli["ProssimaVisita"] = pd.to_datetime(df_cli["ProssimaVisita"], errors="coerce")

    imminenti = df_cli[
        (df_cli["ProssimoRecall"].between(oggi, oggi + pd.DateOffset(days=30))) |
        (df_cli["ProssimaVisita"].between(oggi, oggi + pd.DateOffset(days=30)))
    ].copy()

    if imminenti.empty:
        st.success("✅ Nessun richiamo o visita imminente.")
    else:
        st.markdown("""
        <style>
        .tbl-imminenti {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .tbl-imminenti th, .tbl-imminenti td {
            border-bottom: 1px solid #e5e7eb;
            padding: 6px 10px;
            text-align: left;
        }
        .tbl-imminenti th {
            background-color: #f3f4f6;
            font-weight: 600;
        }
        .tbl-imminenti tr:hover td {
            background-color: #fef9c3;
        }
        </style>
        """, unsafe_allow_html=True)

        # Header tabella
        st.markdown(
            "<table class='tbl-imminenti'><thead><tr>"
            "<th style='width:45%'>Cliente</th>"
            "<th style='width:25%'>Prossimo Recall</th>"
            "<th style='width:25%'>Prossima Visita</th>"
            "<th style='text-align:center;width:15%'>Azione</th>"
            "</tr></thead><tbody>",
            unsafe_allow_html=True
        )

        # Righe
        for i, r in imminenti.iterrows():
            cols = st.columns([2.5, 1.2, 1.2, 0.8])
            with cols[0]:
                st.markdown(f"**{r['RagioneSociale']}**")
            with cols[1]:
                st.markdown(fmt_date(r["ProssimoRecall"]))
            with cols[2]:
                st.markdown(fmt_date(r["ProssimaVisita"]))
            with cols[3]:
                if st.button("Apri", key=f"imm_{i}", use_container_width=True):
                    st.session_state["selected_cliente"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Clienti"
                    st.rerun()

        st.markdown("</tbody></table>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

       # =====================================
    # ⚠️ IN RITARDO
    # =====================================
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'><span>⚠️</span>Recall e Visite in ritardo</div>", unsafe_allow_html=True)

    recall_vecchi = df_cli[
        df_cli["UltimoRecall"].notna() & (df_cli["UltimoRecall"] < oggi - pd.DateOffset(months=3))
    ].copy()

    visite_vecchie = df_cli[
        df_cli["UltimaVisita"].notna() & (df_cli["UltimaVisita"] < oggi - pd.DateOffset(months=6))
    ].copy()

    col1, col2 = st.columns(2)

    # === COLONNA SINISTRA: RECALL ===
    with col1:
        st.markdown("### 📞 Recall > 3 mesi")
        if recall_vecchi.empty:
            st.info("✅ Nessun recall scaduto.")
        else:
            st.markdown("""
            <style>
            .tbl-recall {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9rem;
            }
            .tbl-recall th, .tbl-recall td {
                border-bottom: 1px solid #e5e7eb;
                padding: 6px 10px;
                text-align: left;
            }
            .tbl-recall th {
                background-color: #f3f4f6;
                font-weight: 600;
            }
            .tbl-recall tr:hover td {
                background-color: #fef9c3;
            }
            </style>
            """, unsafe_allow_html=True)

            st.markdown(
                "<table class='tbl-recall'><thead><tr>"
                "<th style='width:55%'>Cliente</th>"
                "<th style='width:25%'>Ultimo Recall</th>"
                "<th style='text-align:center;width:20%'>Azione</th>"
                "</tr></thead><tbody>",
                unsafe_allow_html=True
            )

            for i, r in recall_vecchi.iterrows():
                cols = st.columns([2.5, 1.2, 0.8])
                with cols[0]:
                    st.markdown(f"**{r['RagioneSociale']}**")
                with cols[1]:
                    st.markdown(fmt_date(r["UltimoRecall"]))
                with cols[2]:
                    if st.button("Apri", key=f"recold_{i}", use_container_width=True):
                        st.session_state["selected_cliente"] = r["ClienteID"]
                        st.session_state["nav_target"] = "Clienti"
                        st.rerun()

            st.markdown("</tbody></table>", unsafe_allow_html=True)

    # === COLONNA DESTRA: VISITE ===
    with col2:
        st.markdown("### 👣 Visite > 6 mesi")
        if visite_vecchie.empty:
            st.info("✅ Nessuna visita scaduta.")
        else:
            st.markdown("""
            <style>
            .tbl-recall {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9rem;
            }
            .tbl-recall th, .tbl-recall td {
                border-bottom: 1px solid #e5e7eb;
                padding: 6px 10px;
                text-align: left;
            }
            .tbl-recall th {
                background-color: #f3f4f6;
                font-weight: 600;
            }
            .tbl-recall tr:hover td {
                background-color: #fef9c3;
            }
            </style>
            """, unsafe_allow_html=True)

            st.markdown(
                "<table class='tbl-recall'><thead><tr>"
                "<th style='width:55%'>Cliente</th>"
                "<th style='width:25%'>Ultima Visita</th>"
                "<th style='text-align:center;width:20%'>Azione</th>"
                "</tr></thead><tbody>",
                unsafe_allow_html=True
            )

            for i, r in visite_vecchie.iterrows():
                cols = st.columns([2.5, 1.2, 0.8])
                with cols[0]:
                    st.markdown(f"**{r['RagioneSociale']}**")
                with cols[1]:
                    st.markdown(fmt_date(r["UltimaVisita"]))
                with cols[2]:
                    if st.button("Apri", key=f"visold_{i}", use_container_width=True):
                        st.session_state["selected_cliente"] = r["ClienteID"]
                        st.session_state["nav_target"] = "Clienti"
                        st.rerun()

            st.markdown("</tbody></table>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # =====================================
    # 🧾 STORICO COMPLETO
    # =====================================
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'><span>🧾</span>Storico completo</div>", unsafe_allow_html=True)

    tabella = df_cli[[
        "RagioneSociale", "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"
    ]].copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        tabella[c] = tabella[c].apply(fmt_date)

    st.dataframe(tabella, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

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

    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]], on="ClienteID", how="left")
    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]

    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")
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

    # === PAGINE ===
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
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
