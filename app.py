# =====================================
# app.py — Gestionale Clienti SHT (FULL 2025 ITA)
# =====================================
from __future__ import annotations
import streamlit as st
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

# === Scroll all’avvio ===
st.markdown("""
<script>
window.addEventListener('load', function() {
    window.scrollTo(0, 0);
});
</script>
""", unsafe_allow_html=True)

# === Stile globale ===
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

# =====================================
# LIBRERIE
# =====================================
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

STORAGE_DIR = Path("storage")
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
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Copie", "Eccedenze", "Stato"
]
DURATE_MESI = ["12", "24", "36", "48", "60", "72"]

# =====================================
# FUNZIONI BASE
# =====================================
def fmt_date(d):
    if d in ("", None) or pd.isna(d): return ""
    try:
        return pd.to_datetime(d, dayfirst=True).strftime("%d/%m/%Y")
    except Exception:
        return ""

def as_date(s):
    try:
        if s in ("", None) or pd.isna(s): return pd.NaT
        return pd.to_datetime(s, dayfirst=True, errors="coerce")
    except Exception:
        return pd.NaT

def to_date_series(s): return s.map(as_date)

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]

def money(x):
    try:
        v = float(str(x).replace("€", "").replace(",", "."))
        return f"{v:,.2f} €"
    except: return ""

# =====================================
# LOAD / SAVE CSV
# =====================================
def load_clienti():
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
    df = ensure_columns(df, CLIENTI_COLS)
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = to_date_series(df[c])
    return df

def save_clienti(df):
    df = df.copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = df[c].apply(fmt_date)
    df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if CONTRATTI_CSV.exists():
        df = pd.read_csv(CONTRATTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio", "DataFine"]:
        df[c] = to_date_series(df[c])
    return df

def save_contratti(df):
    df = df.copy()
    for c in ["DataInizio", "DataFine"]:
        df[c] = df[c].apply(fmt_date)
    df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# =====================================
# LOGIN
# =====================================
def do_login_fullscreen():
    import time
    if st.session_state.get("logged_in"):
        return st.session_state["user"], "admin"

    st.markdown("""
    <style>
    .block-container { display:flex;justify-content:center;align-items:center;height:100vh; }
    .login-card { background:white;padding:2rem 2.5rem;border-radius:12px;
        box-shadow:0 4px 16px rgba(0,0,0,0.1);text-align:center;width:360px; }
    .stButton>button { background:#2563eb;color:white;width:100%; }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.image(LOGO_URL, width=140)
        st.markdown("<h4>Accedi al CRM-SHT</h4>", unsafe_allow_html=True)
        user = st.text_input("Nome utente").strip().lower()
        pwd = st.text_input("Password", type="password")
        if st.button("Entra"):
            if user == "admin" and pwd == "admin":
                st.session_state["logged_in"] = True
                st.session_state["user"] = "admin"
                st.success("✅ Accesso eseguito")
                time.sleep(0.3)
                st.rerun()
            else:
                st.error("❌ Credenziali errate.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()
# =====================================
# KPI CARD
# =====================================
def kpi_card(label, value, icon, color):
    return f"""
    <div style='background:{color};padding:16px;border-radius:12px;text-align:center;color:white;'>
        <div style='font-size:26px;'>{icon}</div>
        <div style='font-size:22px;font-weight:700;'>{value}</div>
        <div style='font-size:14px;'>{label}</div>
    </div>
    """

# =====================================
# DASHBOARD
# =====================================
def page_dashboard(df_cli, df_ct, role):
    st.image(LOGO_URL, width=120)
    st.markdown("## 📊 Dashboard Gestionale")
    st.divider()

    stato = df_ct["Stato"].fillna("").str.lower()
    total_clients = len(df_cli)
    active_contracts = (stato != "chiuso").sum()
    closed_contracts = (stato == "chiuso").sum()

    c1, c2, c3 = st.columns(3)
    c1.markdown(kpi_card("Clienti", total_clients, "👥", "#2563eb"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#22c55e"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#ef4444"), unsafe_allow_html=True)
    st.divider()

    st.markdown("### ⚠️ Contratti in scadenza entro 6 mesi")
    oggi = pd.Timestamp.now().normalize()
    entro_6_mesi = oggi + pd.DateOffset(months=6)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    scadenze = df_ct[(df_ct["DataFine"].notna()) & (df_ct["DataFine"] <= entro_6_mesi) & (df_ct["Stato"].str.lower() != "chiuso")]
    if scadenze.empty:
        st.success("✅ Nessun contratto in scadenza.")
    else:
        scadenze = scadenze.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        for _, r in scadenze.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1, 1, 0.7])
            c1.markdown(f"**{r['RagioneSociale']}**")
            c2.markdown(r["NumeroContratto"])
            c3.markdown(r["DataFine"])
            with c4:
                if st.button("📂 Apri", key=f"open_scad_{r['NumeroContratto']}"):
                    st.session_state["selected_cliente"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Clienti"
                    st.rerun()

# =====================================
# PAGINA CLIENTI — con note, recall, preventivi e contratti
# =====================================
def page_clienti(df_cli, df_ct, role):
    st.markdown("## 📇 Scheda Cliente")

    search = st.text_input("🔍 Cerca cliente per nome o ID:")
    if search:
        filtered = df_cli[df_cli["RagioneSociale"].str.contains(search, case=False, na=False)]
    else:
        filtered = df_cli
    if filtered.empty:
        st.warning("Nessun cliente trovato.")
        return

    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox("Seleziona cliente", options)
    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    # Header
    c1, c2 = st.columns([4, 1])
    with c1:
        st.markdown(f"### 🏢 {cliente['RagioneSociale']}")
        st.caption(f"Cliente ID: {sel_id}")
    with c2:
        if st.button("📄 Vai ai Contratti", use_container_width=True):
            st.session_state["selected_cliente"] = sel_id
            st.session_state["nav_target"] = "Contratti"
            st.rerun()

    # Info principali
    st.markdown(f"""
    **📍 Indirizzo:** {cliente.get('Indirizzo','')} — {cliente.get('Citta','')} {cliente.get('CAP','')}  
    **👤 Referente:** {cliente.get('PersonaRiferimento','')}  
    **📞 Telefono:** {cliente.get('Telefono','')} — **📱 Cell:** {cliente.get('Cell','')}
    """)

    # Note cliente
    st.divider()
    st.markdown("### 📝 Note Cliente")
    note_attuali = cliente.get("NoteCliente", "")
    nuove_note = st.text_area("Modifica note:", note_attuali, height=160)
    if st.button("💾 Salva Note Cliente", use_container_width=True):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "NoteCliente"] = nuove_note
        save_clienti(df_cli)
        st.success("✅ Note aggiornate.")
        st.rerun()

    # Recall e Visite
    st.divider()
    st.markdown("### ⚡ Recall e Visite")
    def safe_date(x):
        try:
            d = pd.to_datetime(x, dayfirst=True)
            return None if pd.isna(d) else d.date()
        except: return None
    ur = safe_date(cliente.get("UltimoRecall"))
    pr = safe_date(cliente.get("ProssimoRecall"))
    uv = safe_date(cliente.get("UltimaVisita"))
    pv = safe_date(cliente.get("ProssimaVisita"))
    if ur and not pr: pr = (pd.Timestamp(ur) + pd.DateOffset(months=3)).date()
    if uv and not pv: pv = (pd.Timestamp(uv) + pd.DateOffset(months=6)).date()
    col1, col2, col3, col4 = st.columns(4)
    ur = col1.date_input("⏰ Ultimo Recall", value=ur, format="DD/MM/YYYY")
    pr = col2.date_input("📅 Prossimo Recall", value=pr, format="DD/MM/YYYY")
    uv = col3.date_input("👣 Ultima Visita", value=uv, format="DD/MM/YYYY")
    pv = col4.date_input("🗓️ Prossima Visita", value=pv, format="DD/MM/YYYY")
    if st.button("💾 Salva Aggiornamenti", use_container_width=True):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]] = [
            fmt_date(ur), fmt_date(pr), fmt_date(uv), fmt_date(pv)
        ]
        save_clienti(df_cli)
        st.success("✅ Date aggiornate.")
        st.rerun()

    # Elenco contratti cliente
    st.divider()
    st.markdown("### 📋 Elenco Contratti Cliente")
    contratti_cli = df_ct[df_ct["ClienteID"] == sel_id].copy()
    if contratti_cli.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        contratti_cli["DataInizio"] = contratti_cli["DataInizio"].apply(fmt_date)
        contratti_cli["DataFine"] = contratti_cli["DataFine"].apply(fmt_date)
        contratti_cli["TotRata"] = contratti_cli["TotRata"].apply(money)

        st.markdown("""
        <style>
        .tbl-contratti { width:100%; border-collapse:collapse; font-size:0.9rem; }
        .tbl-contratti th, .tbl-contratti td { border-bottom:1px solid #e5e7eb; padding:8px; text-align:left; }
        .tbl-contratti th { background:#f3f4f6; font-weight:600; }
        .tbl-contratti tr:hover td { background:#fef9c3; }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("<table class='tbl-contratti'><thead><tr>"
                    "<th>Numero</th><th>Descrizione</th><th>Inizio</th><th>Fine</th>"
                    "<th>Durata</th><th>Tot Rata</th><th>Stato</th><th>Azioni</th>"
                    "</tr></thead><tbody>", unsafe_allow_html=True)

        for _, r in contratti_cli.iterrows():
            stato = str(r.get("Stato", "")).lower().strip()
            bg = "#e8f5e9" if "aperto" in stato or "attivo" in stato else "#ffebee"
            tx = "#1b5e20" if "aperto" in stato or "attivo" in stato else "#b71c1c"
            st.markdown(f"""
            <tr style='background:{bg};color:{tx};'>
                <td>{r['NumeroContratto']}</td>
                <td>{r['DescrizioneProdotto']}</td>
                <td>{r['DataInizio']}</td>
                <td>{r['DataFine']}</td>
                <td>{r['Durata']}</td>
                <td>{r['TotRata']}</td>
                <td>{r['Stato']}</td>
                <td>✏️ Modifica | ✅ Chiudi</td>
            </tr>
            """, unsafe_allow_html=True)
        st.markdown("</tbody></table>", unsafe_allow_html=True)

# =====================================
# PAGINA CONTRATTI (Tabella interattiva)
# =====================================
def page_contratti(df_cli, df_ct, role):
    st.image(LOGO_URL, width=120)
    st.markdown("## 📄 Contratti")
    st.divider()

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    sel_label = st.selectbox("Cliente", labels)
    sel_id = df_cli.loc[labels == sel_label, "ClienteID"].values[0]
    rag_soc = df_cli.loc[labels == sel_label, "RagioneSociale"].values[0]

    contratti = df_ct[df_ct["ClienteID"] == sel_id].copy()
    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    contratti["TotRata"] = contratti["TotRata"].apply(money)

    gb = GridOptionsBuilder.from_dataframe(contratti)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True)
    js_code = JsCode("""
    function(params) {
        if (!params.data.Stato) return {};
        const stato = params.data.Stato.toLowerCase();
        if (stato === 'chiuso') return {'backgroundColor':'#ffebee','color':'#b71c1c','fontWeight':'bold'};
        if (stato === 'aperto' || stato === 'attivo') return {'backgroundColor':'#e8f5e9','color':'#1b5e20'};
        return {};
    }
    """)
    gb.configure_grid_options(getRowStyle=js_code)
    grid_opts = gb.build()
    st.markdown(f"### 📋 Contratti di {rag_soc}")
    AgGrid(contratti, gridOptions=grid_opts, theme="balham", height=400, allow_unsafe_jscode=True)
# =====================================
# 📅 PAGINA RECALL E VISITE
# =====================================
def page_richiami_visite(df_cli, df_ct, role):
    st.image(LOGO_URL, width=120)
    st.markdown("## 📅 Gestione Recall e Visite")
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
        st.warning("❌ Nessun cliente trovato.")
        return

    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        filtrato[c] = pd.to_datetime(filtrato[c], errors="coerce", dayfirst=True)

    oggi = pd.Timestamp.now().normalize()

    # === Recall / Visite imminenti ===
    st.markdown("### 🔁 Recall e Visite imminenti (entro 30 giorni)")
    imminenti = filtrato[
        (filtrato["ProssimoRecall"].between(oggi, oggi + pd.DateOffset(days=30))) |
        (filtrato["ProssimaVisita"].between(oggi, oggi + pd.DateOffset(days=30)))
    ]
    if imminenti.empty:
        st.success("✅ Nessun richiamo o visita imminente.")
    else:
        for i, r in imminenti.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1, 1, 0.8])
            c1.markdown(f"**{r['RagioneSociale']}**")
            c2.markdown(fmt_date(r["ProssimoRecall"]))
            c3.markdown(fmt_date(r["ProssimaVisita"]))
            if c4.button("📂 Apri", key=f"imm_{i}", use_container_width=True):
                st.session_state["selected_cliente"] = r["ClienteID"]
                st.session_state["nav_target"] = "Clienti"
                st.rerun()

    # === Recall / Visite scaduti ===
    st.divider()
    st.markdown("### ⚠️ Recall e Visite scaduti")
    recall_vecchi = filtrato[
        filtrato["UltimoRecall"].notna() & (filtrato["UltimoRecall"] < oggi - pd.DateOffset(months=3))
    ]
    visite_vecchie = filtrato[
        filtrato["UltimaVisita"].notna() & (filtrato["UltimaVisita"] < oggi - pd.DateOffset(months=6))
    ]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 📞 Recall scaduti (>3 mesi)")
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

    with c2:
        st.markdown("#### 👣 Visite scadute (>6 mesi)")
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

    # === Storico completo ===
    st.divider()
    st.markdown("### 📋 Storico Recall e Visite")
    tabella = filtrato[["RagioneSociale", "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]].copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        tabella[c] = tabella[c].apply(fmt_date)
    st.dataframe(tabella, use_container_width=True, hide_index=True)


# =====================================
# 📋 LISTA COMPLETA CLIENTI
# =====================================
def page_lista_clienti(df_cli, df_ct, role):
    st.image(LOGO_URL, width=120)
    st.markdown("## 📋 Lista Clienti e Scadenze Contratti")
    st.divider()

    df_ct["Stato"] = df_ct["Stato"].fillna("").str.lower()
    df_ct = df_ct[df_ct["Stato"] != "chiuso"]

    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    oggi = pd.Timestamp.now().normalize()

    prime_scadenze = (
        df_ct[df_ct["DataFine"].notna()]
        .groupby("ClienteID")["DataFine"]
        .min()
        .reset_index()
        .rename(columns={"DataFine": "PrimaScadenza"})
    )

    merged = df_cli.merge(prime_scadenze, on="ClienteID", how="left")
    merged["GiorniMancanti"] = (merged["PrimaScadenza"] - oggi).dt.days

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

    # === Filtri ===
    st.markdown("### 🔍 Filtri")
    c1, c2, c3, c4 = st.columns(4)
    nome = c1.text_input("Nome cliente")
    citta = c2.text_input("Città")
    da_data = c3.date_input("Da data", format="DD/MM/YYYY")
    a_data = c4.date_input("A data", format="DD/MM/YYYY")

    if nome:
        merged = merged[merged["RagioneSociale"].str.contains(nome, case=False, na=False)]
    if citta:
        merged = merged[merged["Citta"].str.contains(citta, case=False, na=False)]
    if da_data:
        merged = merged[merged["PrimaScadenza"] >= pd.Timestamp(da_data)]
    if a_data:
        merged = merged[merged["PrimaScadenza"] <= pd.Timestamp(a_data)]

    # === Ordinamento ===
    st.markdown("### ↕️ Ordinamento")
    ordine = st.radio("Ordina per:", ["Nome (A→Z)", "Nome (Z→A)", "Scadenza (più vicina)", "Scadenza (più lontana)"], horizontal=True)
    if ordine == "Nome (A→Z)":
        merged = merged.sort_values("RagioneSociale")
    elif ordine == "Nome (Z→A)":
        merged = merged.sort_values("RagioneSociale", ascending=False)
    elif ordine == "Scadenza (più vicina)":
        merged = merged.sort_values("PrimaScadenza", ascending=True, na_position="last")
    else:
        merged = merged.sort_values("PrimaScadenza", ascending=False, na_position="last")

    # === Tabella clienti ===
    st.divider()
    st.markdown("### 📇 Elenco Clienti")

    for i, r in merged.iterrows():
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.2, 0.8])
        with c1: st.markdown(f"**{r['RagioneSociale']}**")
        with c2: st.markdown(r.get("Citta", "") or "—")
        with c3: st.markdown(r["ScadenzaBadge"], unsafe_allow_html=True)
        with c4:
            if st.button("📂 Apri", key=f"apri_cli_{i}", use_container_width=True):
                st.session_state["selected_cliente"] = r["ClienteID"]
                st.session_state["nav_target"] = "Clienti"
                st.rerun()


# =====================================
# MAIN APP
# =====================================
def main():
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    st.sidebar.success(f"👤 Utente: {user} — Ruolo: {role}")

    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti,
    }

    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)

    df_cli = load_clienti()
    df_ct = load_contratti()

    if page in PAGES:
        PAGES[page](df_cli, df_ct, role)


# =====================================
# AVVIO
# =====================================
if __name__ == "__main__":
    main()
