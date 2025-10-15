from __future__ import annotations
import os
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict

import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# ==========================
# CONFIGURAZIONE BASE
# ==========================
APP_TITLE = "GESTIONALE CLIENTI – SHT"

STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"

LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

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

# ==========================
# UTILS
# ==========================
def fmt_date(d):
    if pd.isna(d) or d == "":
        return ""
    try:
        return pd.to_datetime(d).strftime("%d/%m/%Y")
    except Exception:
        return str(d)

def money(x):
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        return f"{v:,.2f} €"
    except Exception:
        return ""

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def load_clienti():
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=CLIENTI_COLS)
    df = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    return ensure_columns(df, CLIENTI_COLS)

def save_clienti(df):
    df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=CONTRATTI_COLS)
    df = pd.read_csv(CONTRATTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["DataInizio", "DataFine"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return ensure_columns(df, CONTRATTI_COLS)

def save_contratti(df):
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
# ==========================
# LOGIN
# ==========================
def do_login_fullscreen():
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    st.markdown(
        f"""
        <div style='display:flex; flex-direction:column; align-items:center; justify-content:center;
                    height:100vh; text-align:center;'>
            <img src="{LOGO_URL}" width="220" style="margin-bottom:25px;">
            <h2>🔐 Accesso al Gestionale SHT</h2>
            <p style='color:grey;'>Inserisci le tue credenziali per continuare</p>
        </div>
        """, unsafe_allow_html=True
    )

    username = st.text_input("👤 Utente", key="login_user")
    password = st.text_input("🔒 Password", type="password", key="login_pwd")

    if st.button("Entra", use_container_width=True):
        if username in users and password == users[username].get("password"):
            st.session_state["auth_user"] = username
            st.session_state["auth_role"] = users[username].get("role", "viewer")
            st.rerun()
        else:
            st.error("❌ Credenziali errate o utente inesistente.")

    if "auth_user" in st.session_state:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))
    return ("", "")

# ==========================
# HELPERS UI
# ==========================
def kpi_card(label, value, icon, bg_color):
    return f"""
    <div style="background-color:{bg_color};padding:16px;border-radius:10px;text-align:center;color:white;">
        <div style="font-size:24px;margin-bottom:4px;">{icon}</div>
        <div style="font-size:20px;font-weight:700;">{value}</div>
        <div style="font-size:13px;">{label}</div>
    </div>
    """

def create_contract_card(row):
    key = f"btn_{row.get('ClienteID')}_{row.get('NumeroContratto')}_{hash(str(row))}"
    st.markdown(f"""
    <div style="border:1px solid #ddd;border-radius:10px;padding:10px 14px;margin-bottom:6px;background-color:#fafafa;">
      <b>{row.get('RagioneSociale','')}</b> – Contratto: {row.get('NumeroContratto','')}<br>
      Data Inizio: {fmt_date(row.get('DataInizio'))} — Data Fine: {fmt_date(row.get('DataFine'))}<br>
      <small>Stato: {row.get('Stato','')}</small>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🔎 Apri Cliente", key=key):
        st.session_state["selected_client_id"] = row["ClienteID"]
        st.session_state["nav_target"] = "Contratti"
        st.rerun()

# ==========================
# DASHBOARD COMPATTA
# ==========================
def page_dashboard(df_cli, df_ct, role):
    now = pd.Timestamp.now().normalize()

    col1, col2 = st.columns([0.15, 0.85])
    with col1: st.image(LOGO_URL, width=120)
    with col2:
        st.markdown("<h1>SHT – CRM Dashboard</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:gray;'>Panoramica contratti e attività</p>", unsafe_allow_html=True)
    st.divider()

    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    kpi = [
        ("Clienti attivi", len(df_cli), "👥", "#2196F3"),
        ("Contratti attivi", (stato != "chiuso").sum(), "📄", "#009688"),
        ("Contratti chiusi", (stato == "chiuso").sum(), "❌", "#F44336"),
        ("Nuovi contratti", len(df_ct[df_ct["DataInizio"].dt.year == now.year]), "⭐", "#FFC107")
    ]
    c1, c2, c3, c4 = st.columns(4)
    for c, d in zip([c1, c2, c3, c4], kpi):
        with c: st.markdown(kpi_card(*d), unsafe_allow_html=True)
    st.divider()

    # Contratti in scadenza (max 8)
    st.subheader("📅 Contratti in Scadenza (entro 6 mesi)")
    scadenza = df_ct[
        (df_ct["DataFine"].notna()) & (df_ct["DataFine"] >= now) &
        (df_ct["DataFine"] <= now + pd.DateOffset(months=6)) &
        (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]
    if not scadenza.empty:
        scadenza = scadenza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left").head(8)
        st.markdown("<div style='max-height:220px;overflow-y:auto;'>", unsafe_allow_html=True)
        for _, r in scadenza.iterrows():
            create_contract_card(r)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("✅ Nessun contratto in scadenza.")

    st.divider()

    # Contratti senza data fine (solo da oggi in poi)
    st.subheader("⏰ Contratti Senza Data Fine (da oggi in poi)")
    senza = df_ct[
        (df_ct["DataFine"].isna()) & (df_ct["DataInizio"] >= now) &
        (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]
    if not senza.empty:
        senza = senza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left").head(6)
        st.markdown("<div style='max-height:200px;overflow-y:auto;'>", unsafe_allow_html=True)
        for _, r in senza.iterrows():
            create_contract_card(r)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("✅ Nessun nuovo contratto senza data fine (da oggi).")

    st.divider()

    # Ultimi Recall e Visite
    st.subheader("📞 Ultimi Recall e Visite")
    df_cli["UltimoRecall"] = pd.to_datetime(df_cli["UltimoRecall"], errors="coerce", dayfirst=True)
    df_cli["UltimaVisita"] = pd.to_datetime(df_cli["UltimaVisita"], errors="coerce", dayfirst=True)
    col_r, col_v = st.columns(2)
    with col_r:
        st.markdown("#### 🔁 Ultimi Recall")
        st.dataframe(df_cli[["RagioneSociale", "UltimoRecall", "ProssimoRecall"]]
                     .sort_values("UltimoRecall", ascending=False).head(5),
                     hide_index=True, use_container_width=True)
    with col_v:
        st.markdown("#### 🚗 Ultime Visite")
        st.dataframe(df_cli[["RagioneSociale", "UltimaVisita", "ProssimaVisita"]]
                     .sort_values("UltimaVisita", ascending=False).head(5),
                     hide_index=True, use_container_width=True)
# ==========================
# PAGINA CONTRATTI
# ==========================
def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📑 Gestione Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str) == str(pre)][0])
        except:
            idx = 0

    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = df_cli.iloc[labels[labels == sel_label].index[0]]["ClienteID"]
    rag_soc = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]["RagioneSociale"]

    # Nuovo contratto
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

    # Tabella contratti
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
        if (stato === 'chiuso') {
            return { 'backgroundColor': '#ffebee', 'color': '#b71c1c', 'fontWeight': 'bold' };
        } else if (stato === 'attivo' || stato === 'aperto') {
            return { 'backgroundColor': '#e8f5e9', 'color': '#1b5e20' };
        } else if (stato === 'nuovo') {
            return { 'backgroundColor': '#fff8e1', 'color': '#8a6d00' };
        } else {
            return {};
        }
    }
    """)
    gb.configure_grid_options(getRowStyle=js_code)
    grid_opts = gb.build()

    st.markdown("### 📋 Lista contratti")
    grid_resp = AgGrid(
        disp,
        gridOptions=grid_opts,
        theme="balham",
        height=380,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True
    )

    selected = grid_resp.get("selected_rows", [])
    if selected:
        sel = selected[0]
        st.markdown("### 📝 Descrizione completa")
        st.info(sel.get("DescrizioneProdotto", ""), icon="🪶")

    st.divider()
    st.markdown("### ⚙️ Gestione Stato Contratti")
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
        with c2:
            st.caption(f"{r['NumeroContratto']} — {str(r.get('DescrizioneProdotto',''))[:60]}")
        curr = (r["Stato"] or "aperto").lower()
        with c3:
            if curr == "chiuso":
                if st.button("🔓 Riapri", key=f"open_{i}"):
                    df_ct.loc[i, "Stato"] = "aperto"
                    save_contratti(df_ct)
                    st.rerun()
            else:
                if st.button("❌ Chiudi", key=f"close_{i}"):
                    df_ct.loc[i, "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        csv = disp.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📄 Esporta CSV", csv, f"contratti_{rag_soc}.csv", "text/csv")
    with c2:
        try:
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", size=9)
            pdf.cell(0, 8, safe_text(f"Contratti - {rag_soc}"), ln=1, align="C")
            for _, row in disp.iterrows():
                pdf.cell(35, 6, safe_text(row["NumeroContratto"]), 1)
                pdf.cell(25, 6, safe_text(row["DataInizio"]), 1)
                pdf.cell(25, 6, safe_text(row["DataFine"]), 1)
                pdf.cell(20, 6, safe_text(row["Durata"]), 1)
                pdf.cell(80, 6, safe_text(row["DescrizioneProdotto"])[:60], 1)
                pdf.cell(20, 6, safe_text(row["TotRata"]), 1)
                pdf.cell(20, 6, safe_text(row["Stato"]), 1)
                pdf.ln()
            pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
            st.downlo# ==========================
# PAGINA LISTA CLIENTI
# ==========================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📋 Lista Completa Clienti e Contratti</h2>", unsafe_allow_html=True)

    st.markdown("### 🔍 Filtra Clienti")
    col1, col2 = st.columns(2)
    with col1:
        filtro_nome = st.text_input("Cerca per nome cliente")
    with col2:
        filtro_citta = st.text_input("Cerca per città")

    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]],
                         on="ClienteID", how="left")

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
# ==========================
# PAGINA PREVENTIVI / OFFERTE
# ==========================
def next_preventivo_number():
    """Genera numero progressivo preventivo e aggiorna preventivi.csv"""
    if not PREVENTIVI_CSV.exists():
        df_prev = pd.DataFrame(columns=["NumeroPreventivo", "Data", "ClienteID", "RagioneSociale", "File"])
        df_prev.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")
        return 1

    df_prev = pd.read_csv(PREVENTIVI_CSV, encoding="utf-8-sig")
    if df_prev.empty:
        return 1
    else:
        return int(df_prev["NumeroPreventivo"].max()) + 1


def page_preventivi(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>🧾 Gestione Preventivi / Offerte</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.warning("⚠️ Nessun cliente presente.")
        return

    # Selezione cliente
    sel_cliente = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"].tolist())
    cli = df_cli[df_cli["RagioneSociale"] == sel_cliente].iloc[0]

    # Template disponibili
    template_dir = Path("template_preventivi")
    template_dir.mkdir(exist_ok=True)
    templates = [f for f in os.listdir(template_dir) if f.endswith(".docx")]
    if not templates:
        st.warning("📄 Nessun template trovato nella cartella 'template_preventivi/'.")
        st.info("Aggiungi fino a 4 modelli DOCX personalizzati (es. 'modello1.docx', 'modello2.docx').")
        return

    modello = st.selectbox("📑 Seleziona modello", templates)

    # Compilazione automatica
    col1, col2 = st.columns(2)
    with col1:
        oggetto = st.text_input("Oggetto preventivo", value="Offerta commerciale")
    with col2:
        validita = st.date_input("Validità fino al", value=datetime.now() + timedelta(days=30))

    note = st.text_area("Note aggiuntive", value="")

    if st.button("🧾 Genera Preventivo DOCX"):
        numero = next_preventivo_number()
        data_oggi = datetime.now().strftime("%d/%m/%Y")

        doc = Document(template_dir / modello)

        # Sostituzione placeholder nel documento
        for p in doc.paragraphs:
            if "{{RAGIONESOCIALE}}" in p.text:
                p.text = p.text.replace("{{RAGIONESOCIALE}}", cli["RagioneSociale"])
            if "{{DATA}}" in p.text:
                p.text = p.text.replace("{{DATA}}", data_oggi)
            if "{{NUMERO}}" in p.text:
                p.text = p.text.replace("{{NUMERO}}", str(numero))
            if "{{OGGETTO}}" in p.text:
                p.text = p.text.replace("{{OGGETTO}}", oggetto)
            if "{{VALIDITA}}" in p.text:
                p.text = p.text.replace("{{VALIDITA}}", fmt_date(validita))
            if "{{NOTE}}" in p.text:
                p.text = p.text.replace("{{NOTE}}", note)

        # Nome file
        nome_file = f"Preventivo_{numero}_{cli['RagioneSociale'].replace(' ', '_')}.docx"
        save_path = STORAGE_DIR / nome_file
        doc.save(save_path)

        # Salvataggio registro preventivi
        df_prev = pd.read_csv(PREVENTIVI_CSV, encoding="utf-8-sig") if PREVENTIVI_CSV.exists() else pd.DataFrame()
        new_row = pd.DataFrame([{
            "NumeroPreventivo": numero,
            "Data": data_oggi,
            "ClienteID": cli["ClienteID"],
            "RagioneSociale": cli["RagioneSociale"],
            "File": nome_file
        }])
        df_prev = pd.concat([df_prev, new_row], ignore_index=True)
        df_prev.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")

        # Download file
        with open(save_path, "rb") as f:
            st.download_button(
                "⬇️ Scarica Preventivo DOCX",
                f,
                file_name=nome_file,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )

        st.success(f"✅ Preventivo n° {numero} creato con successo!")


    st.divider()
    st.markdown("### 📚 Storico Preventivi")
    if PREVENTIVI_CSV.exists():
        df_prev = pd.read_csv(PREVENTIVI_CSV, encoding="utf-8-sig")
        if not df_prev.empty:
            st.dataframe(df_prev.sort_values("NumeroPreventivo", ascending=False),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Nessun preventivo registrato.")
    else:
        st.info("Nessun preventivo registrato.")

# ==========================
# MAIN APP
# ==========================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="📘")

    # === LOGIN PRIMA DI TUTTO ===
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    st.sidebar.success(f"Utente: {user} — Ruolo: {role}")

    # Pagine principali
    PAGES = {
    "Dashboard": page_dashboard,
    "Clienti": page_clienti,
    "Contratti": page_contratti,
    "Preventivi": page_preventivi,
    "📋 Lista Clienti": page_lista_clienti
}


    # Imposta pagina predefinita e navigazione
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio(
        "Menu",
        list(PAGES.keys()),
        index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0
    )

    # Caricamento dati
    df_cli = load_clienti()
    df_ct = load_contratti()

    # Routing verso la pagina selezionata
    PAGES[page](df_cli, df_ct, role)


# ==========================
# AVVIO APP
# ==========================
if __name__ == "__main__":
    main()
ad_button("📘 Esporta PDF", pdf_bytes, f"contratti_{rag_soc}.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Errore PDF: {e}")
