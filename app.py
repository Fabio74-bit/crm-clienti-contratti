# =====================================
# app.py — Gestionale Clienti SHT (versione completa 2025)
# =====================================
from __future__ import annotations
import streamlit as st
from pathlib import Path
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from docx import Document
from docx.shared import Pt

# =====================================
# CONFIGURAZIONE BASE
# =====================================
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

# --- STILE GRAFICO BASE ---
st.markdown("""
<style>
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}
</style>
""", unsafe_allow_html=True)

# =====================================
# COSTANTI E PERCORSI FILE
# =====================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

# Percorso principale
STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage"))
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
# FUNZIONI UTILI
# =====================================
def as_date(x):
    """Converte una stringa o numero in una data pandas (NaT se vuoto)."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    s = str(x).strip()
    if s in ("", "NaT", "None", "nan"):
        return pd.NaT
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return pd.to_datetime(s, format=fmt)
        except Exception:
            continue
    return pd.to_datetime(s, errors="coerce")

def load_data():
    """Carica i dati da CSV (in futuro integrabile con MySQL)."""
    if CLIENTI_CSV.exists():
        df_cli = pd.read_csv(CLIENTI_CSV)
    else:
        df_cli = pd.DataFrame(columns=CLIENTI_COLS)

    if CONTRATTI_CSV.exists():
        df_ct = pd.read_csv(CONTRATTI_CSV)
    else:
        df_ct = pd.DataFrame(columns=CONTRATTI_COLS)

    return df_cli, df_ct

def save_data(df_cli, df_ct):
    """Salva i dati aggiornati nei CSV."""
    df_cli.to_csv(CLIENTI_CSV, index=False)
    df_ct.to_csv(CONTRATTI_CSV, index=False)

# =====================================
# RUOLI E LOGIN (BASIC)
# =====================================
def login():
    """Login semplice con ruoli base."""
    st.sidebar.image(LOGO_URL, width=180)
    st.sidebar.title("Accesso Utente")
    user = st.sidebar.text_input("Nome utente")
    pwd = st.sidebar.text_input("Password", type="password")
    role = None

    if st.sidebar.button("Accedi"):
        if user.lower() == "admin" and pwd == "admin":
            role = "Admin"
            st.session_state["role"] = role
            st.success("Accesso effettuato come Amministratore ✅")
        elif user.lower() == "utente" and pwd == "utente":
            role = "Utente"
            st.session_state["role"] = role
            st.success("Accesso effettuato come Utente 👤")
        else:
            st.error("Credenziali non valide ❌")

    return st.session_state.get("role")

# =====================================
# RENDERER PER AGGRID
# =====================================
action_renderer = JsCode("""
function(params) {
    return `
    <div style="text-align:center">
        <button class="btn btn-primary" style="background-color:#2563eb;border:none;border-radius:4px;padding:2px 6px;color:white;cursor:pointer;">
            Apri
        </button>
    </div>`;
}
""")
# =====================================
# DASHBOARD
# =====================================
def kpi_card(title, value, icon, color):
    """Crea una card HTML per i KPI."""
    return f"""
    <div style='background-color:white;padding:20px;border-radius:10px;
                box-shadow:0 0 6px rgba(0,0,0,0.1);text-align:center;'>
        <div style='font-size:30px;'>{icon}</div>
        <div style='font-size:18px;color:#666;'>{title}</div>
        <div style='font-size:26px;color:{color};font-weight:bold;'>{value}</div>
    </div>
    """

def page_dashboard(df_cli, df_ct, role):
    st.title("📊 Dashboard")

    total_clients = len(df_cli)
    active_contracts = len(df_ct[df_ct["Stato"].str.lower() == "attivo"]) if not df_ct.empty else 0
    expired_contracts = len(df_ct[df_ct["Stato"].str.lower() == "scaduto"]) if not df_ct.empty else 0

    c1, c2, c3 = st.columns(3)
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#2563eb"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#2e7d32"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti scaduti", expired_contracts, "⚠️", "#d32f2f"), unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Ultimi contratti registrati")
    if not df_ct.empty:
        df_show = df_ct.sort_values(by="DataInizio", ascending=False).head(10)
        gb = GridOptionsBuilder.from_dataframe(df_show)
        gb.configure_default_column(resizable=True, wrapText=True, autoHeight=True)
        gb.configure_grid_options(domLayout="normal", ensureDomOrder=True)
        AgGrid(df_show, gridOptions=gb.build(), height=300)
    else:
        st.info("Nessun contratto registrato al momento.")

# =====================================
# PAGINA CLIENTI
# =====================================
def page_clienti(df_cli, df_ct, role):
    st.title("👥 Gestione Clienti")

    st.markdown("### Elenco Clienti")
    gb = GridOptionsBuilder.from_dataframe(df_cli)
    gb.configure_default_column(resizable=True, wrapText=True, autoHeight=True)
    gb.configure_column("RagioneSociale", width=200)
    gb.configure_column("Email", width=200)
    gb.configure_column("Azioni", width=120, pinned="right", suppressMovable=True, cellRenderer=action_renderer)
    grid = AgGrid(df_cli, gridOptions=gb.build(), update_mode=GridUpdateMode.SELECTION_CHANGED, height=400)

    selected = grid["selected_rows"]
    if selected:
        cliente = selected[0]
        st.subheader(f"📄 Dettagli Cliente: {cliente['RagioneSociale']}")
        st.write(cliente)

    if role == "Admin":
        st.markdown("---")
        st.subheader("➕ Aggiungi / Modifica Cliente")
        with st.form("form_cliente"):
            new_cli = {}
            for col in CLIENTI_COLS:
                new_cli[col] = st.text_input(col, value="")
            submitted = st.form_submit_button("Salva Cliente")
            if submitted:
                df_cli = pd.concat([df_cli, pd.DataFrame([new_cli])], ignore_index=True)
                save_data(df_cli, df_ct)
                st.success("Cliente salvato con successo ✅")
                st.experimental_rerun()
# =====================================
# PAGINA CONTRATTI
# =====================================
def page_contratti(df_cli, df_ct, role):
    st.title("📄 Gestione Contratti")

    st.markdown("### Elenco Contratti")
    disp = df_ct.copy()

    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(resizable=True, wrapText=True, autoHeight=True)
    gb.configure_column("DescrizioneProdotto", wrapText=True, autoHeight=True)
    gb.configure_column("Azioni", width=120, pinned="right", suppressMovable=True, cellRenderer=action_renderer)
    gb.configure_grid_options(domLayout="normal", ensureDomOrder=True)
    AgGrid(disp, gridOptions=gb.build(), height=400)

    if role == "Admin":
        st.markdown("---")
        st.subheader("➕ Crea / Modifica Contratto")
        with st.form("form_contratto"):
            new_ct = {}
            for col in CONTRATTI_COLS:
                new_ct[col] = st.text_input(col, value="")
            submitted = st.form_submit_button("Salva Contratto")
            if submitted:
                df_ct = pd.concat([df_ct, pd.DataFrame([new_ct])], ignore_index=True)
                save_data(df_cli, df_ct)
                st.success("Contratto salvato con successo ✅")
                st.experimental_rerun()

# =====================================
# PAGINA PREVENTIVI
# =====================================
class PDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Preventivo Cliente", align="C", ln=True)
        self.ln(5)

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 10, title, ln=True)
        self.ln(4)

    def chapter_body(self, body):
        self.set_font("Helvetica", "", 11)
        self.multi_cell(0, 8, body)
        self.ln()

def genera_preventivo(cliente, contratto):
    """Crea un preventivo PDF per un cliente e contratto."""
    pdf = PDF()
    pdf.add_page()

    pdf.chapter_title("Dati Cliente")
    for k, v in cliente.items():
        pdf.chapter_body(f"{k}: {v}")

    pdf.chapter_title("Dati Contratto")
    for k, v in contratto.items():
        pdf.chapter_body(f"{k}: {v}")

    nome_file = f"Preventivo_{cliente['RagioneSociale']}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    file_path = PREVENTIVI_DIR / nome_file
    pdf.output(str(file_path))
    return file_path

def page_preventivi(df_cli, df_ct, role):
    st.title("💼 Gestione Preventivi")

    st.markdown("### Seleziona Cliente e Contratto")
    if df_cli.empty or df_ct.empty:
        st.warning("Devi avere almeno un cliente e un contratto registrato.")
        return

    cli_sel = st.selectbox("Cliente", df_cli["RagioneSociale"])
    cliente = df_cli[df_cli["RagioneSociale"] == cli_sel].iloc[0].to_dict()

    contratti_cli = df_ct[df_ct["ClienteID"] == cliente["ClienteID"]]
    if contratti_cli.empty:
        st.info("Questo cliente non ha contratti associati.")
        return

    cont_sel = st.selectbox("Contratto", contratti_cli["NumeroContratto"])
    contratto = contratti_cli[contratti_cli["NumeroContratto"] == cont_sel].iloc[0].to_dict()

    if st.button("📄 Genera Preventivo PDF"):
        file_path = genera_preventivo(cliente, contratto)
        with open(file_path, "rb") as f:
            st.download_button("⬇️ Scarica Preventivo", f, file_name=file_path.name)
# =====================================
# PAGINA IMPOSTAZIONI
# =====================================
def page_impostazioni(df_cli, df_ct, role):
    st.title("⚙️ Impostazioni")

    st.markdown("### Informazioni Applicazione")
    st.info("""
    **Gestionale Clienti – SHT**  
    Versione 2025 completa  
    Realizzato per la gestione di clienti, contratti e preventivi.
    """)

    st.markdown("---")
    st.markdown("### Operazioni di Sistema")
    c1, c2 = st.columns(2)

    with c1:
        if st.button("💾 Forza Salvataggio Dati"):
            save_data(df_cli, df_ct)
            st.success("Dati salvati con successo ✅")

    with c2:
        if st.button("🔁 Ricarica Dati"):
            st.experimental_rerun()

    if role == "Admin":
        st.markdown("---")
        st.subheader("🧹 Pulizia Dati")
        if st.button("Elimina tutti i contratti (solo Admin)"):
            df_ct = pd.DataFrame(columns=CONTRATTI_COLS)
            save_data(df_cli, df_ct)
            st.warning("Tutti i contratti sono stati eliminati ❌")

# =====================================
# GESTIONE PAGINE / MENU
# =====================================
PAGES = {
    "Dashboard": page_dashboard,
    "Clienti": page_clienti,
    "Contratti": page_contratti,
    "Preventivi": page_preventivi,
    "Impostazioni": page_impostazioni
}

# =====================================
# MAIN APP
# =====================================
def main():
    st.sidebar.image(LOGO_URL, width=180)
    st.sidebar.title("Menù Principale")

    # login
    role = st.session_state.get("role")
    if not role:
        role = login()
        if not role:
            st.stop()

    # caricamento dati
    df_cli, df_ct = load_data()

    # selezione pagina
    page = st.sidebar.radio("Naviga tra le pagine:", list(PAGES.keys()), index=0)
    st.sidebar.markdown(f"**Ruolo attuale:** {role}")

    # chiamata pagina selezionata
    PAGES[page](df_cli, df_ct, role)

    st.markdown("---")
    st.caption("© 2025 SHT – Gestionale Clienti e Contratti")

# =====================================
# AVVIO
# =====================================
if __name__ == "__main__":
    main()
