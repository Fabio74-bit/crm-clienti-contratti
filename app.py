# ======================================================
# app.py — Gestionale Clienti SHT (versione completa finale)
# ======================================================
from __future__ import annotations

import streamlit as st
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

# Layout ampio globale
st.markdown("""
<style>
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}
</style>
""", unsafe_allow_html=True)

import os
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
from docx import Document
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# ======================
# CONFIGURAZIONE BASE
# ======================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"
TEMPLATES_DIR = STORAGE_DIR / "templates"
PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
TEMPLATES_DIR.mkdir(exist_ok=True)
PREVENTIVI_DIR.mkdir(exist_ok=True)

DURATE_MESI = ["12", "24", "36", "48", "60"]

CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "PersonaRiferimento2",
    "Indirizzo", "Citta", "CAP", "Telefono", "Cellulare",
    "Email", "PartitaIVA", "IBAN", "SDI", 
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "NoteCliente"
]

CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine",
    "Durata", "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]

# ======================
# UTILS
# ======================
def as_date(x):
    if x is None or str(x).strip() == "":
        return pd.NaT
    try:
        return pd.to_datetime(x, dayfirst=True, errors="coerce")
    except Exception:
        return pd.NaT

def fmt_date(d):
    return "" if pd.isna(d) else pd.to_datetime(d).strftime("%d/%m/%Y")

def money(x):
    try:
        v = float(x)
        return f"{v:,.2f} €"
    except Exception:
        return str(x)

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols]

# ======================
# I/O DATI
# ======================
def load_clienti():
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=CLIENTI_COLS)
    df = pd.read_csv(CLIENTI_CSV, dtype=str).fillna("")
    return ensure_columns(df, CLIENTI_COLS)

def save_clienti(df):
    df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=CONTRATTI_COLS)
    df = pd.read_csv(CONTRATTI_CSV, dtype=str).fillna("")
    for c in ["DataInizio", "DataFine"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return ensure_columns(df, CONTRATTI_COLS)

def save_contratti(df):
    df_out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        df_out[c] = df_out[c].apply(lambda x: "" if pd.isna(x) else pd.to_datetime(x).strftime("%Y-%m-%d"))
    df_out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# ======================
# LOGIN FULLSCREEN
# ======================
def do_login_fullscreen():
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    # Se già loggato → entra diretto
    if "auth_user" in st.session_state and st.session_state["auth_user"]:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))

    # Mostra form di login
    st.markdown(
        f"""
        <div style='display:flex; flex-direction:column; align-items:center; justify-content:center;
                    height:100vh; text-align:center;'>
            <img src="{LOGO_URL}" width="220" style="margin-bottom:25px;">
            <h2>🔐 Accesso al Gestionale SHT</h2>
            <p style='color:grey;'>Inserisci le credenziali per continuare</p>
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
            st.error("❌ Credenziali errate.")

    st.stop()

# ======================
# DASHBOARD
# ======================
def kpi_card(label, value, icon, color):
    return f"""
    <div style='background:{color}; padding:18px; border-radius:10px; color:white; text-align:center;'>
        <div style='font-size:26px;'>{icon}</div>
        <div style='font-size:22px; font-weight:700;'>{value}</div>
        <div>{label}</div>
    </div>"""

def page_dashboard(df_cli, df_ct, role):
    now = pd.Timestamp.now()
    st.image(LOGO_URL, width=150)
    st.title("📊 Dashboard CRM SHT")
    st.divider()

    stato = df_ct["Stato"].fillna("").str.lower()
    total_clients = len(df_cli)
    active = (stato != "chiuso").sum()
    closed = (stato == "chiuso").sum()
    new = ((pd.to_datetime(df_ct["DataInizio"], errors="coerce") >= f"{now.year}-01-01")).sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(kpi_card("Clienti Attivi", total_clients, "👥", "#2196F3"), unsafe_allow_html=True)
    with c2: st.markdown(kpi_card("Contratti Attivi", active, "📄", "#009688"), unsafe_allow_html=True)
    with c3: st.markdown(kpi_card("Contratti Chiusi", closed, "❌", "#F44336"), unsafe_allow_html=True)
    with c4: st.markdown(kpi_card("Nuovi Contratti Anno", new, "⭐", "#FFC107"), unsafe_allow_html=True)

    st.divider()
# ======================================================
# CLIENTI – Ricerca, Modifica, Recall/Visite, Preventivi
# ======================================================

def _parse_italian_date(value):
    if pd.isna(value) or not str(value).strip():
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y")
    except Exception:
        try:
            return pd.to_datetime(value, dayfirst=True)
        except Exception:
            return None

def _format_italian_date(date_val):
    if not date_val or pd.isna(date_val):
        return ""
    return pd.to_datetime(date_val).strftime("%d/%m/%Y")

def page_clienti(df_cli, df_ct, role):
    st.title("📋 Gestione Clienti")

    st.markdown("### 🔍 Cerca Cliente")
    search_query = st.text_input("Cerca cliente per nome:")
    if search_query:
        filtered = df_cli[df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)]
    else:
        filtered = df_cli

    if filtered.empty:
        st.warning("Nessun cliente trovato.")
        st.stop()

    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox("Seleziona Cliente", options)
    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    st.markdown(f"## 🏢 {cliente.get('RagioneSociale', '')}")
    st.caption(f"ID Cliente: {sel_id}")

    # --- Dati anagrafici ---
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"📍 **Indirizzo:** {cliente.get('Indirizzo','')} - {cliente.get('Citta','')} {cliente.get('CAP','')}")
        st.write(f"☎️ **Telefono:** {cliente.get('Telefono','')}  |  📱 **Cell:** {cliente.get('Cellulare','')}")
        st.write(f"📧 **Email:** {cliente.get('Email','')}")
        st.write(f"💼 **Partita IVA:** {cliente.get('PartitaIVA','')}")
        st.write(f"🏦 **IBAN:** {cliente.get('IBAN','')}")
    with col2:
        st.write(f"👤 **Referente:** {cliente.get('PersonaRiferimento','')}")
        st.write(f"👤 **Referente 2:** {cliente.get('PersonaRiferimento2','')}")
        st.write(f"🧾 **SDI:** {cliente.get('SDI','')}")
        st.write(f"📅 **Ultimo Recall:** {cliente.get('UltimoRecall','')}")
        st.write(f"📅 **Ultima Visita:** {cliente.get('UltimaVisita','')}")

    st.divider()

    # --- Recall / Visite TMK ---
    st.markdown("### 📞 Gestione Recall e Visite")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ult_recall = _parse_italian_date(cliente.get("UltimoRecall",""))
        new_recall = st.date_input("Ultimo Recall", value=ult_recall or datetime.now(), format="DD/MM/YYYY")
    with c2:
        ult_visita = _parse_italian_date(cliente.get("UltimaVisita",""))
        new_visita = st.date_input("Ultima Visita", value=ult_visita or datetime.now(), format="DD/MM/YYYY")

    with c3:
        pross_recall = (pd.to_datetime(new_recall) + timedelta(days=30)).date()
        st.date_input("Prossimo Recall", value=pross_recall, disabled=True, format="DD/MM/YYYY")
    with c4:
        pross_visita = (pd.to_datetime(new_visita) + timedelta(days=180)).date()
        st.date_input("Prossima Visita", value=pross_visita, disabled=True, format="DD/MM/YYYY")

    if st.button("💾 Aggiorna Recall/Visite"):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "UltimoRecall"] = _format_italian_date(new_recall)
        df_cli.loc[idx, "UltimaVisita"] = _format_italian_date(new_visita)
        df_cli.loc[idx, "ProssimoRecall"] = _format_italian_date(pross_recall)
        df_cli.loc[idx, "ProssimaVisita"] = _format_italian_date(pross_visita)
        save_clienti(df_cli)
        st.success("✅ Dati aggiornati con successo!")
        st.rerun()

    st.divider()

    # --- Modifica Anagrafica ---
    st.markdown("### 🧾 Modifica Dati Cliente")
    with st.expander("✏️ Modifica anagrafica cliente"):
        with st.form("frm_anagrafica"):
            c1, c2, c3 = st.columns(3)
            with c1:
                rag = st.text_input("Ragione Sociale", cliente.get("RagioneSociale",""))
                ref1 = st.text_input("Persona Riferimento 1", cliente.get("PersonaRiferimento",""))
                ref2 = st.text_input("Persona Riferimento 2", cliente.get("PersonaRiferimento2",""))
            with c2:
                indir = st.text_input("Indirizzo", cliente.get("Indirizzo",""))
                citta = st.text_input("Città", cliente.get("Citta",""))
                cap = st.text_input("CAP", cliente.get("CAP",""))
                tel = st.text_input("Telefono", cliente.get("Telefono",""))
            with c3:
                cell = st.text_input("Cellulare", cliente.get("Cellulare",""))
                piva = st.text_input("Partita IVA", cliente.get("PartitaIVA",""))
                mail = st.text_input("Email", cliente.get("Email",""))
                sdi = st.text_input("SDI", cliente.get("SDI",""))
                iban = st.text_input("IBAN", cliente.get("IBAN",""))

            submit = st.form_submit_button("💾 Salva Modifiche")
            if submit:
                idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx, [
                    "RagioneSociale","PersonaRiferimento","PersonaRiferimento2","Indirizzo",
                    "Citta","CAP","Telefono","Cellulare","PartitaIVA","Email","SDI","IBAN"
                ]] = [rag,ref1,ref2,indir,citta,cap,tel,cell,piva,mail,sdi,iban]
                save_clienti(df_cli)
                st.success("✅ Anagrafica aggiornata con successo!")
                st.rerun()

    st.divider()

    # --- Preventivi DOCX ---
    st.markdown("### 🧾 Genera Nuovo Preventivo")
    template_map = {
        "Offerta – Centralino": "Offerta_Centralino.docx",
        "Offerta – Varie": "Offerta_Varie.docx",
        "Offerta – A3": "Offerte_A3.docx",
        "Offerta – A4": "Offerte_A4.docx",
    }

    if PREVENTIVI_CSV.exists():
        df_prev = pd.read_csv(PREVENTIVI_CSV, dtype=str).fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID","NumeroOfferta","Template","NomeFile","Percorso","DataCreazione"])

    anno = datetime.now().year
    nome_sicuro = "".join(c for c in cliente["RagioneSociale"] if c.isalnum())[:6].upper()
    next_num = f"OFF-{anno}-{nome_sicuro}-{len(df_prev)+1:03d}"

    with st.form("frm_new_prev"):
        num = st.text_input("Numero Offerta", next_num)
        nome_file = st.text_input("Nome File (es. Offerta_ACME.docx)")
        template = st.selectbox("Template", list(template_map.keys()))
        submitted = st.form_submit_button("💾 Crea Preventivo")

        if submitted:
            tpl_path = TEMPLATES_DIR / template_map[template]
            if not tpl_path.exists():
                st.error(f"Template non trovato: {tpl_path}")
            else:
                doc = Document(tpl_path)
                mapping = {
                    "CLIENTE": cliente.get("RagioneSociale",""),
                    "CITTA": cliente.get("Citta",""),
                    "INDIRIZZO": cliente.get("Indirizzo",""),
                    "NUMERO_OFFERTA": num,
                    "DATA": datetime.now().strftime("%d/%m/%Y"),
                }
                for p in doc.paragraphs:
                    for key,val in mapping.items():
                        p.text = p.text.replace(f"<<{key}>>", str(val))
                out_name = nome_file or f"{num}.docx"
                out_path = PREVENTIVI_DIR / out_name
                doc.save(out_path)

                nuovo = {
                    "ClienteID": sel_id,
                    "NumeroOfferta": num,
                    "Template": template,
                    "NomeFile": out_name,
                    "Percorso": str(out_path),
                    "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                df_prev = pd.concat([df_prev, pd.DataFrame([nuovo])], ignore_index=True)
                df_prev.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")
                st.success(f"✅ Preventivo creato: {out_name}")
                st.rerun()

    st.divider()

    # --- Elenco Preventivi ---
    st.markdown("### 📂 Elenco Preventivi Cliente")
    prev_cli = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
    if prev_cli.empty:
        st.info("Nessun preventivo presente.")
    else:
        for i, row in prev_cli.iterrows():
            col1, col2 = st.columns([0.8,0.2])
            with col1:
                st.write(f"📄 **{row['NumeroOfferta']}** – {row['Template']} ({row['DataCreazione']})")
            with col2:
                file_path = Path(row["Percorso"])
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        st.download_button("⬇️ Scarica", f, file_path.name, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", key=f"dl_{i}")
# ======================================================
# CONTRATTI — creazione, modifica, chiusura/riapertura
# ======================================================
def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

def page_contratti(df_cli, df_ct, role):
    st.title("📑 Gestione Contratti")

    if df_cli.empty:
        st.warning("Nessun cliente trovato.")
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

    st.divider()

    # === Nuovo Contratto ===
    with st.expander(f"➕ Nuovo contratto per {rag_soc}"):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            with c1: num = st.text_input("Numero Contratto")
            with c2: din = st.date_input("Data Inizio", format="DD/MM/YYYY")
            with c3: durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto", height=100)
            c4, c5, c6 = st.columns(3)
            with c4: nf = st.text_input("NOL_FIN")
            with c5: ni = st.text_input("NOL_INT")
            with c6: tot = st.text_input("TotRata")

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
                st.success("✅ Contratto creato!")
                st.rerun()

    # === Tabella Contratti ===
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["DataInizio"] = ct["DataInizio"].apply(fmt_date)
    ct["DataFine"] = ct["DataFine"].apply(fmt_date)
    ct["TotRata"] = ct["TotRata"].apply(money)
    ct = ct.fillna("")

    gb = GridOptionsBuilder.from_dataframe(ct)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True)
    js_code = JsCode("""
    function(params) {
        if (!params.data.Stato) return {};
        const s = params.data.Stato.toLowerCase();
        if (s === 'chiuso') return {'backgroundColor': '#ffebee', 'color': '#b71c1c', 'fontWeight': 'bold'};
        if (s === 'aperto') return {'backgroundColor': '#e8f5e9', 'color': '#1b5e20'};
        return {};
    }""")
    gb.configure_grid_options(getRowStyle=js_code)
    grid_opts = gb.build()

    grid_resp = AgGrid(
        ct, gridOptions=grid_opts, theme="balham", height=380,
        update_mode=GridUpdateMode.SELECTION_CHANGED, allow_unsafe_jscode=True
    )

    selected = grid_resp.get("selected_rows", [])
    if selected:
        sel = selected[0]
        st.markdown("### ✏️ Modifica Contratto Selezionato")
        idx = df_ct.index[(df_ct["ClienteID"] == sel["ClienteID"]) & (df_ct["NumeroContratto"] == sel["NumeroContratto"])][0]
        with st.form("edit_contract"):
            c1, c2, c3 = st.columns(3)
            with c1:
                data_inizio = st.date_input("Data Inizio", pd.to_datetime(sel["DataInizio"], errors="coerce") or datetime.now(), format="DD/MM/YYYY")
            with c2:
                data_fine = st.date_input("Data Fine", pd.to_datetime(sel["DataFine"], errors="coerce") or datetime.now(), format="DD/MM/YYYY")
            with c3:
                stato = st.selectbox("Stato", ["aperto", "chiuso", "sospeso"], index=["aperto","chiuso","sospeso"].index(sel["Stato"].lower() if sel["Stato"] else "aperto"))
            desc = st.text_area("Descrizione prodotto", sel["DescrizioneProdotto"], height=100)
            tot = st.text_input("TotRata", sel["TotRata"])
            if st.form_submit_button("💾 Salva Modifiche"):
                df_ct.loc[idx, ["DataInizio","DataFine","Stato","DescrizioneProdotto","TotRata"]] = [
                    pd.to_datetime(data_inizio), pd.to_datetime(data_fine), stato, desc, tot
                ]
                save_contratti(df_ct)
                st.success("✅ Contratto aggiornato!")
                st.rerun()

    # === Stato Contratti ===
    st.divider()
    st.markdown("### ⚙️ Stato Contratti")
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.75, 0.2])
        with c2:
            st.caption(f"{r['NumeroContratto']} – {r['DescrizioneProdotto'][:50]}")
        curr = r["Stato"].lower()
        with c3:
            if curr == "chiuso":
                btn_label = "🔓 Riapri"
                if st.button(btn_label, key=f"riapri_{i}"):
                    df_ct.loc[df_ct.index[i], "Stato"] = "aperto"
                    save_contratti(df_ct)
                    st.rerun()
            else:
                btn_label = "❌ Chiudi"
                if st.button(btn_label, key=f"chiudi_{i}"):
                    st.warning(f"Vuoi davvero chiudere il contratto {r['NumeroContratto']}?")
                    if st.button("✅ Conferma", key=f"conf_{i}"):
                        df_ct.loc[df_ct.index[i], "Stato"] = "chiuso"
                        save_contratti(df_ct)
                        st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        csv = ct.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📄 Esporta CSV", csv, f"contratti_{rag_soc}.csv", "text/csv")
    with c2:
        try:
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", size=9)
            pdf.cell(0, 8, safe_text(f"Contratti - {rag_soc}"), ln=1, align="C")
            for _, row in ct.iterrows():
                pdf.cell(35, 6, safe_text(row["NumeroContratto"]), 1)
                pdf.cell(25, 6, safe_text(row["DataInizio"]), 1)
                pdf.cell(25, 6, safe_text(row["DataFine"]), 1)
                pdf.cell(80, 6, safe_text(row["DescrizioneProdotto"][:60]), 1)
                pdf.cell(20, 6, safe_text(row["TotRata"]), 1)
                pdf.cell(20, 6, safe_text(row["Stato"]), 1)
                pdf.ln()
            pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
            st.download_button("📘 Esporta PDF", pdf_bytes, f"contratti_{rag_soc}.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Errore PDF: {e}")

# ======================================================
# LISTA CLIENTI – tabella con filtri
# ======================================================
def page_lista_clienti(df_cli, df_ct, role):
    st.title("📋 Lista Completa Clienti e Contratti")

    col1, col2 = st.columns(2)
    with col1:
        filtro_nome = st.text_input("🔍 Filtra per nome cliente")
    with col2:
        filtro_citta = st.text_input("🏙️ Filtra per città")

    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]], on="ClienteID", how="left")
    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]

    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged = merged.fillna("")
    st.dataframe(merged, use_container_width=True, hide_index=True)
    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_clienti_contratti.csv", "text/csv")

# ======================================================
# MAIN APP
# ======================================================
def main():
    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    st.sidebar.success(f"Utente: {user} — Ruolo: {role}")
    if st.sidebar.button("🚪 Logout"):
        st.session_state.clear()
        st.rerun()

    df_cli = load_clienti()
    df_ct = load_contratti()

    PAGES = {
        "🏠 Dashboard": page_dashboard,
        "📋 Clienti": page_clienti,
        "📑 Contratti": page_contratti,
        "📜 Lista Clienti": page_lista_clienti
    }

    page = st.sidebar.radio("Navigazione", list(PAGES.keys()))
    st.sidebar.divider()
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
