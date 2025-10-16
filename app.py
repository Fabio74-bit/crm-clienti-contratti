# =====================================
# app.py — Gestionale Clienti SHT (versione completa 2025 con preventivi)
# =====================================
from __future__ import annotations
import streamlit as st
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

# --- stile globale per allargare la pagina ---
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
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    if "auth_user" in st.session_state and st.session_state["auth_user"]:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))

    st.markdown(
        f"""
        <div style='display:flex; flex-direction:column; align-items:center; justify-content:center;
                    height:100vh; text-align:center;'>
            <img src="{LOGO_URL}" width="220" style="margin-bottom:25px;">
            <h2>🔐 Accesso al Gestionale SHT</h2>
            <p style='color:grey; font-size:14px;'>Inserisci le credenziali</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    username = st.text_input("👤 Utente", key="login_user")
    password = st.text_input("🔒 Password", type="password", key="login_pwd")

    if st.button("Entra"):
        if username in users and password == users[username].get("password"):
            st.session_state["auth_user"] = username
            st.session_state["auth_role"] = users[username].get("role", "viewer")
            st.rerun()
        else:
            st.error("❌ Credenziali errate o utente inesistente.")
    st.stop()

# =====================================
# DASHBOARD
# =====================================
def kpi_card(label, value, icon, color):
    return f"""
    <div style="background-color:{color};padding:18px;border-radius:12px;text-align:center;color:white;">
        <div style="font-size:26px;">{icon}</div>
        <div style="font-size:22px;font-weight:700;">{value}</div>
        <div style="font-size:14px;">{label}</div>
    </div>
    """

def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📊 Dashboard Gestionale</h2>", unsafe_allow_html=True)
    st.divider()

    now = pd.Timestamp.now().normalize()
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())

    # Nuovi contratti nell’anno
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

    # Recall e visite
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
# =====================================
# CLIENTI
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Clienti")
    search = st.text_input("🔍 Cerca cliente per nome:")
    if search:
        df_cli = df_cli[df_cli["RagioneSociale"].str.contains(search, case=False, na=False)]
    if df_cli.empty:
        st.warning("Nessun cliente trovato.")
        return

    sel = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"])
    cliente = df_cli[df_cli["RagioneSociale"] == sel].iloc[0]
    sel_id = cliente["ClienteID"]

    st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
    st.caption(f"ClienteID: {sel_id}")

    indirizzo = cliente.get("Indirizzo", "")
    citta = cliente.get("Citta", "")
    cap = cliente.get("CAP", "")
    persona = cliente.get("PersonaRiferimento", "")
    telefono = cliente.get("Telefono", "")
    cell = cliente.get("Cell", "")
    ult_rec = fmt_date(cliente.get("UltimoRecall", ""))
    pross_rec = fmt_date(cliente.get("ProssimoRecall", ""))
    ult_vis = fmt_date(cliente.get("UltimaVisita", ""))
    pross_vis = fmt_date(cliente.get("ProssimaVisita", ""))

    st.markdown(f"""
    <div style='font-size:15px; line-height:1.6;'>
        📍 <b>Indirizzo:</b> {indirizzo} – {citta} {cap}<br>
        👤 <b>Referente:</b> {persona}<br>
        📞 <b>Telefono:</b> {telefono} — 📱 <b>Cell:</b> {cell}<br>
        ⏰ <b>Ultimo Recall:</b> {ult_rec or '—'} — 🗓️ <b>Prossimo Recall:</b> {pross_rec or '—'}<br>
        👣 <b>Ultima Visita:</b> {ult_vis or '—'} — 🗓️ <b>Prossima Visita:</b> {pross_vis or '—'}
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # === MODIFICA ANAGRAFICA ===
    with st.expander("✏️ Modifica anagrafica completa"):
        with st.form(f"frm_{sel_id}"):
            col1, col2 = st.columns(2)
            with col1:
                indirizzo = st.text_input("📍 Indirizzo", cliente.get("Indirizzo",""))
                citta = st.text_input("🏙️ Città", cliente.get("Citta",""))
                cap = st.text_input("📮 CAP", cliente.get("CAP",""))
                telefono = st.text_input("📞 Telefono", cliente.get("Telefono",""))
                cell = st.text_input("📱 Cellulare", cliente.get("Cell",""))
                persona = st.text_input("👤 Referente", cliente.get("PersonaRiferimento",""))
                email = st.text_input("✉️ Email", cliente.get("Email",""))
            with col2:
                piva = st.text_input("💼 P.IVA", cliente.get("PartitaIVA",""))
                iban = st.text_input("🏦 IBAN", cliente.get("IBAN",""))
                sdi = st.text_input("📡 SDI", cliente.get("SDI",""))
                def safe_date_input(label, value, key=None):
    try:
        d = as_date(value)
        if pd.isna(d):
            return st.date_input(label, value=datetime.now().date(), key=key)
        return st.date_input(label, value=d.date(), key=key)
    except Exception:
        return st.date_input(label, value=datetime.now().date(), key=key)

ur = safe_date_input("Ultimo Recall", cliente.get("UltimoRecall"), key=f"ur_{sel_id}")
pr = safe_date_input("Prossimo Recall", cliente.get("ProssimoRecall"), key=f"pr_{sel_id}")
uv = safe_date_input("Ultima Visita", cliente.get("UltimaVisita"), key=f"uv_{sel_id}")
pv = safe_date_input("Prossima Visita", cliente.get("ProssimaVisita"), key=f"pv_{sel_id}")

            if st.form_submit_button("💾 Salva"):
                idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx, [
                    "Indirizzo", "Citta", "CAP", "Telefono", "Cell", "PersonaRiferimento",
                    "Email", "PartitaIVA", "IBAN", "SDI",
                    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"
                ]] = [
                    indirizzo, citta, cap, telefono, cell, persona, email, piva, iban, sdi,
                    ur, pr, uv, pv
                ]
                save_clienti(df_cli)
                st.success("✅ Anagrafica aggiornata.")
                st.rerun()

# =====================================
# CONTRATTI
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    sel_label = st.selectbox(
        "Seleziona cliente",
        df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    )
    sel_id = sel_label.split(" — ")[0]
    rag_soc = df_cli[df_cli["ClienteID"] == sel_id].iloc[0]["RagioneSociale"]

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
                st.success("✅ Contratto creato.")
                st.rerun()

    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

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
        if (stato === "chiuso") {
            return { 'color': 'white', 'backgroundColor': '#757575' };
        }
        return {};
    }
    """)
    gb.configure_columns(["Stato"], cellStyle=js_code)
    grid = AgGrid(disp, gridOptions=gb.build(), update_mode=GridUpdateMode.NO_UPDATE, height=320)
# =====================================
# PREVENTIVI
# =====================================
from docx import Document
from docx.shared import Pt
from pathlib import Path

def page_preventivi(df_cli: pd.DataFrame, role: str):
    st.markdown("<h2>🧾 Preventivi</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente disponibile.")
        return

    cliente_sel = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"])
    cliente = df_cli[df_cli["RagioneSociale"] == cliente_sel].iloc[0]
    sel_id = cliente["ClienteID"]

    TEMPLATES_DIR = STORAGE_DIR / "templates"
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    TEMPLATE_OPTIONS = {
        "Offerta – Centralino": "Offerta_Centralino.docx",
        "Offerta – Varie": "Offerta_Varie.docx",
        "Offerta – A3": "Offerte_A3.docx",
        "Offerta – A4": "Offerte_A4.docx",
    }

    st.markdown("### 📄 Crea nuovo preventivo")
    with st.form("frm_new_prev"):
        tpl_choice = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        num_offerta = st.text_input("Numero Offerta (es. OFF-2025-001)")
        nome_file = st.text_input("Nome File (es. Offerta_ACME.docx)")
        submitted = st.form_submit_button("💾 Genera Preventivo")

        if submitted:
            tpl_path = TEMPLATES_DIR / TEMPLATE_OPTIONS[tpl_choice]
            if not tpl_path.exists():
                st.error(f"Template non trovato: {tpl_path.name}")
            else:
                nome_file = nome_file or f"{num_offerta}.docx"
                if not nome_file.endswith(".docx"):
                    nome_file += ".docx"
                out_path = PREVENTIVI_DIR / nome_file
                doc = Document(tpl_path)

                mapping = {
                    "CLIENTE": cliente.get("RagioneSociale", ""),
                    "INDIRIZZO": cliente.get("Indirizzo", ""),
                    "CITTA": cliente.get("Citta", ""),
                    "NUMERO_OFFERTA": num_offerta,
                    "DATA": datetime.now().strftime("%d/%m/%Y"),
                }

                for p in doc.paragraphs:
                    for key, val in mapping.items():
                        token = f"<<{key}>>"
                        if token in p.text:
                            p.text = p.text.replace(token, str(val))
                            for run in p.runs:
                                run.font.size = Pt(10)

                doc.save(out_path)
                st.success(f"✅ Preventivo creato: {out_path.name}")
                st.download_button("⬇️ Scarica subito", out_path.read_bytes(), file_name=out_path.name)

    st.divider()

    st.markdown("### 📂 Elenco Preventivi Cliente")
    files = list(PREVENTIVI_DIR.glob("*.docx"))
    if not files:
        st.info("Nessun preventivo presente.")
    else:
        for f in sorted(files, reverse=True):
            col1, col2 = st.columns([0.8, 0.2])
            with col1:
                st.markdown(f"📄 **{f.name}**  _(creato il {datetime.fromtimestamp(f.stat().st_mtime).strftime('%d/%m/%Y %H:%M')})_")
            with col2:
                with open(f, "rb") as data:
                    st.download_button("⬇️", data=data.read(), file_name=f.name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f.name)


# =====================================
# MAIN APP
# =====================================
def main():
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    st.sidebar.success(f"Utente: {user} — Ruolo: {role}")

    # Pagine del gestionale
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "Preventivi": page_preventivi
    }

    # Navigazione
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("📁 Menu", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)

    df_cli = load_clienti()
    df_ct = load_contratti()

    PAGES[page](df_cli, df_ct if "Contratti" in page or "Dashboard" in page else None, role)


if __name__ == "__main__":
    main()
