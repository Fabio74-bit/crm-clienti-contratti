from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# ==========================
# CONFIG / COSTANTI
# ==========================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"

DURATE_MESI = ["12", "24", "36", "48", "60"]

# ==========================
# FUNZIONI UTILITY
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
    return df[cols]

# ==========================
# I/O DATI
# ==========================
def load_clienti():
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=["ClienteID", "RagioneSociale", "Citta", "UltimoRecall", "UltimaVisita", "ProssimoRecall", "ProssimaVisita"])
    df = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["UltimoRecall", "UltimaVisita", "ProssimoRecall", "ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_clienti(df):
    df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=["ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata", "DescrizioneProdotto", "TotRata", "Stato"])
    df = pd.read_csv(CONTRATTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["DataInizio", "DataFine"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_contratti(df):
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
# ==========================
# LOGIN
# ==========================
def do_login_fullscreen():
    """Schermata di login a pagina intera con logo SHT"""
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    st.markdown(
        f"""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:90vh;text-align:center;'>
            <img src="{LOGO_URL}" width="220" style="margin-bottom:25px;">
            <h2>🔐 Accesso al Gestionale SHT</h2>
            <p style='color:grey;'>Inserisci le tue credenziali per accedere</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    username = st.text_input("👤 Utente", key="login_user")
    password = st.text_input("🔒 Password", type="password", key="login_pwd")

    if st.button("Entra", use_container_width=True):
        if username in users and password == users[username].get("password"):
            st.session_state["auth_user"] = username
            st.session_state["auth_role"] = users[username].get("role", "viewer")
            st.success("✅ Accesso effettuato!")
            st.rerun()
        else:
            st.error("❌ Credenziali errate o utente inesistente.")

    if "auth_user" in st.session_state:
        return st.session_state["auth_user"], st.session_state.get("auth_role", "viewer")
    return "", ""

# ==========================
# DASHBOARD
# ==========================
def kpi_card(label, value, icon, bg_color):
    return f"""
    <div style="background-color:{bg_color};padding:18px;border-radius:12px;text-align:center;color:white;">
        <div style="font-size:26px;margin-bottom:6px;">{icon}</div>
        <div style="font-size:22px;font-weight:700;">{value}</div>
        <div style="font-size:14px;">{label}</div>
    </div>
    """

def create_contract_card(row):
    key = f"card_{row.get('ClienteID')}_{row.get('NumeroContratto')}_{hash(str(row))}"
    st.markdown(f"""
        <div style="border:1px solid #e4e4e4;border-radius:10px;padding:10px 14px;margin-bottom:8px;background-color:#fafafa;">
            <b>{row.get('RagioneSociale','')}</b> – Contratto: {row.get('NumeroContratto','')}<br>
            Data Inizio: {fmt_date(row.get('DataInizio'))} — Data Fine: {fmt_date(row.get('DataFine'))}<br>
            <small>Stato: {row.get('Stato','')}</small>
        </div>
    """, unsafe_allow_html=True)
    if st.button("🔎 Apri Cliente", key=key):
        st.session_state["selected_client_id"] = row["ClienteID"]
        st.session_state["nav_target"] = "Contratti"
        st.rerun()

def page_dashboard(df_cli, df_ct, role):
    now = pd.Timestamp.now().normalize()
    col1, col2 = st.columns([0.15, 0.85])
    with col1: st.image(LOGO_URL, width=120)
    with col2: st.markdown("<h1>SHT – CRM Dashboard</h1>", unsafe_allow_html=True)
    st.divider()

    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    kpi_data = [
        ("Clienti attivi", len(df_cli), "👥", "#2196F3"),
        ("Contratti attivi", (stato != "chiuso").sum(), "📄", "#009688"),
        ("Contratti chiusi", (stato == "chiuso").sum(), "❌", "#F44336"),
        ("Nuovi contratti", len(df_ct[df_ct["DataInizio"].dt.year == now.year]), "⭐", "#FFC107")
    ]
    c1, c2, c3, c4 = st.columns(4)
    for c, data in zip([c1, c2, c3, c4], kpi_data):
        with c: st.markdown(kpi_card(*data), unsafe_allow_html=True)
    st.divider()

    # Contratti in scadenza (entro 6 mesi) — compatti
    st.subheader("📅 Contratti in Scadenza (entro 6 mesi)")
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce")
    scadenza = df_ct[
        (df_ct["DataFine"].notna()) &
        (df_ct["DataFine"] >= now) &
        (df_ct["DataFine"] <= now + pd.DateOffset(months=6)) &
        (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]
    if scadenza.empty:
        st.info("✅ Nessun contratto in scadenza.")
    else:
        scadenza = scadenza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        with st.container():
            st.dataframe(
                scadenza[["RagioneSociale", "NumeroContratto", "DataFine", "Stato"]]
                .sort_values("DataFine")
                .head(10),
                use_container_width=True,
                hide_index=True
            )

    st.divider()

    # Contratti senza data fine (solo da oggi in poi)
    st.subheader("⏰ Contratti Senza Data Fine (attivi da oggi)")
    senza = df_ct[
        (df_ct["DataFine"].isna()) &
        (df_ct["DataInizio"] >= now) &
        (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]
    if senza.empty:
        st.info("✅ Nessun nuovo contratto senza data fine.")
    else:
        senza = senza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        st.dataframe(
            senza[["RagioneSociale", "NumeroContratto", "DataInizio", "Stato"]]
            .sort_values("DataInizio")
            .head(10),
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # Ultimi Recall e Visite
    st.subheader("📞 Ultimi Recall e Visite")
    col_r, col_v = st.columns(2)
    with col_r:
        st.markdown("#### 🔁 Ultimi Recall")
        st.dataframe(
            df_cli[["RagioneSociale", "UltimoRecall", "ProssimoRecall"]]
            .dropna()
            .sort_values("UltimoRecall", ascending=False)
            .head(5),
            use_container_width=True,
            hide_index=True
        )
    with col_v:
        st.markdown("#### 🚗 Ultime Visite")
        st.dataframe(
            df_cli[["RagioneSociale", "UltimaVisita", "ProssimaVisita"]]
            .dropna()
            .sort_values("UltimaVisita", ascending=False)
            .head(5),
            use_container_width=True,
            hide_index=True
        )

# ==========================
# CLIENTI
# ==========================
def page_clienti(df_cli, df_ct, role):
    st.subheader("📋 Gestione Clienti")
    search = st.text_input("🔍 Cerca cliente per nome:")
    if search:
        df_cli = df_cli[df_cli["RagioneSociale"].str.contains(search, case=False, na=False)]

    if df_cli.empty:
        st.warning("Nessun cliente trovato.")
        return

    sel = st.selectbox("Seleziona cliente", df_cli["RagioneSociale"].tolist())
    cli = df_cli[df_cli["RagioneSociale"] == sel].iloc[0]
    st.markdown(f"### 🏢 {cli['RagioneSociale']}")

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Città:** {cli.get('Citta','')}")
        st.write(f"**Ultimo Recall:** {fmt_date(cli.get('UltimoRecall'))}")
        st.write(f"**Prossimo Recall:** {fmt_date(cli.get('ProssimoRecall'))}")
    with col2:
        st.write(f"**Ultima Visita:** {fmt_date(cli.get('UltimaVisita'))}")
        st.write(f"**Prossima Visita:** {fmt_date(cli.get('ProssimaVisita'))}")

    st.divider()
    st.markdown("### 🗒️ Note Cliente")
    note = st.text_area("Annotazioni:", cli.get("Note", ""), height=150)
    if st.button("💾 Salva Note"):
        idx = df_cli.index[df_cli["ClienteID"] == cli["ClienteID"]][0]
        df_cli.loc[idx, "Note"] = note
        save_clienti(df_cli)
        st.success("✅ Note aggiornate.")
        st.rerun()
# ==========================
# LISTA COMPLETA CLIENTI
# ==========================
def page_lista_clienti(df_cli, df_ct, role):
    st.title("📋 Lista Completa Clienti e Contratti")

    # Filtro rapido
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

# ==========================
# PREVENTIVI (DOCX)
# ==========================
def page_preventivi(df_cli, df_ct, role):
    st.title("🧾 Gestione Preventivi / Offerte DOCX")

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    sel = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"].tolist())
    cli = df_cli[df_cli["RagioneSociale"] == sel].iloc[0]
    cli_id = cli["ClienteID"]

    st.divider()

    st.markdown(f"### 🧰 Crea nuovo preventivo per **{cli['RagioneSociale']}**")

    template_opts = {
        "Offerta – Centralino": "Offerta_Centralino.docx",
        "Offerta – Varie": "Offerta_Varie.docx",
        "Offerta – A3": "Offerte_A3.docx",
        "Offerta – A4": "Offerte_A4.docx",
    }

    if PREVENTIVI_CSV.exists():
        df_prev = pd.read_csv(PREVENTIVI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])

    def genera_numero_offerta(cliente_nome: str) -> str:
        anno = datetime.now().year
        nome_sicuro = "".join(c for c in cliente_nome if c.isalnum())[:6].upper()
        subset = df_prev[df_prev["ClienteID"].astype(str) == str(cli_id)]
        seq = len(subset) + 1
        return f"OFF-{anno}-{nome_sicuro}-{seq:03d}"

    next_num = genera_numero_offerta(cli["RagioneSociale"])

    with st.form("frm_new_prev"):
        num = st.text_input("Numero Offerta", next_num)
        nome_file = st.text_input("Nome File (es. Offerta_SHT.docx)")
        template = st.selectbox("Template", list(template_opts.keys()))
        submitted = st.form_submit_button("💾 Genera Preventivo")

        if submitted:
            try:
                template_path = STORAGE_DIR / "templates" / template_opts[template]
                output_path = STORAGE_DIR / "preventivi"
                output_path.mkdir(exist_ok=True)
                dest_file = output_path / (nome_file or f"{num}.docx")

                if not template_path.exists():
                    st.error(f"❌ Template non trovato: {template_path}")
                else:
                    doc = Document(template_path)
                    mapping = {
                        "CLIENTE": cli["RagioneSociale"],
                        "CITTA": cli.get("Citta", ""),
                        "DATA": datetime.now().strftime("%d/%m/%Y"),
                        "NUMERO_OFFERTA": num,
                    }

                    for p in doc.paragraphs:
                        for key, val in mapping.items():
                            token = f"<<{key}>>"
                            if token in p.text:
                                p.text = p.text.replace(token, str(val))

                    doc.save(dest_file)
                    nuovo = {
                        "ClienteID": cli_id,
                        "NumeroOfferta": num,
                        "Template": template,
                        "NomeFile": dest_file.name,
                        "Percorso": str(dest_file),
                        "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([nuovo])], ignore_index=True)
                    df_prev.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")

                    st.success(f"✅ Preventivo creato: {dest_file.name}")
                    st.rerun()
            except Exception as e:
                st.error(f"Errore durante creazione preventivo: {e}")

    st.divider()
    st.markdown("### 📂 Elenco Preventivi Cliente")
    prev_cli = df_prev[df_prev["ClienteID"].astype(str) == str(cli_id)]
    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        st.dataframe(prev_cli[["NumeroOfferta", "Template", "DataCreazione", "NomeFile"]], use_container_width=True)
# ==========================
# CONTRATTI (gestione completa con AgGrid)
# ==========================
def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("""
    <style>
      .btn-primary {background:#2196F3; color:#fff; padding:6px 10px; border-radius:8px; font-size:14px;}
      .btn-danger  {background:#F44336; color:#fff; padding:6px 10px; border-radius:8px; font-size:14px;}
      .btn-success {background:#009688; color:#fff; padding:6px 10px; border-radius:8px; font-size:14px;}
      .section-hdr {font-size:20px; font-weight:700; margin:6px 0 8px 0;}
    </style>
    """, unsafe_allow_html=True)
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # Preselezione da Dashboard → Apri Cliente
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

    # --- Nuovo contratto ---
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
                tot = st.text_input("TotRata (€)")
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

    # --- Tabella contratti (AgGrid) ---
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

    st.markdown("<div class='section-hdr'>📑 Lista contratti</div>", unsafe_allow_html=True)
    grid_resp = AgGrid(
        disp,
        gridOptions=grid_opts,
        theme="balham",
        height=380,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True
    )

    selected = grid_resp.get("selected_rows", [])
    if isinstance(selected, list) and len(selected) > 0:
        sel = selected[0]
        st.markdown("### 📝 Descrizione completa")
        st.info(sel.get("DescrizioneProdotto", ""), icon="🪶")

    # --- Stato contratti (chiudi / riapri) ---
    st.divider()
    st.markdown("<div class='section-hdr'>⚙️ Stato contratti</div>", unsafe_allow_html=True)
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
        with c2:
            st.caption(f"{r['NumeroContratto']} — {str(r.get('DescrizioneProdotto',''))[:60]}")
        curr = (r["Stato"] or "aperto").lower()
        with c3:
            if curr == "chiuso":
                if st.button("🔓 Riapri", key=f"open_{i}"):
                    df_ct.loc[i, "Stato"] = "aperto"; save_contratti(df_ct); st.rerun()
            else:
                if st.button("❌ Chiudi", key=f"close_{i}"):
                    df_ct.loc[i, "Stato"] = "chiuso"; save_contratti(df_ct); st.rerun()

    # --- Esportazioni ---
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
            st.download_button("📘 Esporta PDF", pdf_bytes, f"contratti_{rag_soc}.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Errore PDF: {e}")
# ==========================
# MAIN APP
# ==========================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    st.sidebar.success(f"Utente: {user} — Ruolo: {role}")

    # Routing delle pagine
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,  # ✅ ora esiste
        "Lista Clienti": page_lista_clienti,
        "Preventivi": page_preventivi,
}


    df_cli = load_clienti()
    df_ct = load_contratti()

    page = st.sidebar.radio("Menu", list(PAGES.keys()), index=0)
    if PAGES[page]:
        PAGES[page](df_cli, df_ct, role)
    else:
        st.info("⚙️ Sezione in aggiornamento.")

if __name__ == "__main__":
    main()
