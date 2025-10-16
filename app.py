from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# =========================================================
# CONFIGURAZIONE BASE
# =========================================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"

DURATE_MESI = ["12", "24", "36", "48", "60"]

# =========================================================
# FUNZIONI UTILITY
# =========================================================
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

def safe_date(val, add_days=0):
    if pd.isna(val) or val == "":
        return datetime.now() + timedelta(days=add_days)
    return pd.to_datetime(val)

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]

# =========================================================
# I/O CSV
# =========================================================
def load_clienti():
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=[
            "ClienteID","RagioneSociale","Citta","Telefono","Cellulare",
            "PersonaRiferimento2","Email","IBAN","SDI",
            "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
        ])
    df = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_clienti(df):
    out = df.copy()
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=[
            "ClienteID","NumeroContratto","DataInizio","DataFine",
            "Durata","DescrizioneProdotto","TotRata","Stato"
        ])
    df = pd.read_csv(CONTRATTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["DataInizio","DataFine"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_contratti(df):
    out = df.copy()
    for c in ["DataInizio","DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# =========================================================
# LOGIN FULLSCREEN CON LOGO SHT
# =========================================================
def do_login_fullscreen():
    """Schermata di login a pagina intera con logo SHT"""
    users = st.secrets.get("auth", {}).get("users", st.secrets.get("auth.users", {}))
    if not users:
        return ("ospite", "viewer")

    # Se già loggato → ritorna direttamente
    if "auth_user" in st.session_state and "auth_role" in st.session_state:
        return st.session_state["auth_user"], st.session_state["auth_role"]

    # Layout fullscreen
    st.markdown(
        f"""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;
                    height:90vh;text-align:center;'>
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

    return "", ""

# =========================================================
# DASHBOARD COMPLETA E COMPATTA
# =========================================================
def page_dashboard(df_cli, df_ct, role):
    st.title("📊 Dashboard Clienti e Contratti")

    # === 3 colonne layout principale ===
    col_logo, col_center, col_right = st.columns([1, 3, 1])

    with col_logo:
        st.image(LOGO_URL, width=140)
    with col_center:
        st.markdown("<h2 style='text-align:center;'>📋 Situazione Generale</h2>", unsafe_allow_html=True)
    with col_right:
        st.write("")
        st.write(f"👤 Utente: **{role.upper()}**")

    # === KPI sintetici ===
    tot_cli = len(df_cli)
    tot_contratti = len(df_ct)
    contratti_attivi = df_ct[df_ct["Stato"].str.lower().ne("chiuso")].shape[0]
    contratti_scadenza = df_ct[
        (df_ct["DataFine"].notna()) &
        (pd.to_datetime(df_ct["DataFine"]) <= datetime.now() + timedelta(days=180)) &
        (df_ct["Stato"].str.lower() != "chiuso")
    ]

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("👥 Clienti Totali", tot_cli)
    kpi2.metric("📑 Contratti Attivi", contratti_attivi)
    kpi3.metric("⏳ In Scadenza (6 mesi)", len(contratti_scadenza))

    st.markdown("---")

    # ---------------------------------------------------------
    # CONTRATTI IN SCADENZA (entro 6 mesi)
    # ---------------------------------------------------------
    st.subheader("📅 Contratti in Scadenza (entro 6 mesi)")

    upcoming = df_ct.copy()
    upcoming = upcoming[
        (upcoming["Stato"].str.lower() != "chiuso") &
        (upcoming["DataFine"].notna()) &
        (pd.to_datetime(upcoming["DataFine"], errors="coerce") <= datetime.now() + timedelta(days=180))
    ]

    if upcoming.empty:
        st.info("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        upcoming = upcoming.sort_values("DataFine")
        merged = upcoming.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        for i, (_, row) in enumerate(merged.head(10).iterrows()):
            cliente_nome = row["RagioneSociale"]
            cli_id = row["ClienteID"]
            fine = fmt_date(row["DataFine"])

            if st.button(f"🔎 {cliente_nome} — scade il {fine}", key=f"btn_scad_{cli_id}_{i}"):
                st.session_state["selected_client_id"] = cli_id
                st.session_state["page"] = "Clienti"
                st.rerun()

    st.markdown("---")

    # ---------------------------------------------------------
    # CONTRATTI SENZA DATA FINE
    # ---------------------------------------------------------
    st.subheader("❔ Contratti senza Data Fine")

    senza_fine = df_ct[
        (df_ct["DataFine"].isna() | (df_ct["DataFine"] == "")) &
        (df_ct["Stato"].str.lower() != "chiuso")
    ]

    if senza_fine.empty:
        st.info("✅ Tutti i contratti hanno una data di fine.")
    else:
        merged = senza_fine.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        for i, (_, row) in enumerate(merged.head(10).iterrows()):
            cliente_nome = row["RagioneSociale"]
            cli_id = row["ClienteID"]
            if st.button(f"📄 {cliente_nome} – Contratto senza Data Fine", key=f"btn_senza_{cli_id}_{i}"):
                st.session_state["selected_client_id"] = cli_id
                st.session_state["page"] = "Clienti"
                st.rerun()

    st.markdown("---")

    # ---------------------------------------------------------
    # RECALL / VISITE
    # ---------------------------------------------------------
    st.subheader("📞 Clienti da contattare (Recall / Visite)")

    prossimi = df_cli[
        (df_cli["ProssimoRecall"].notna()) &
        (pd.to_datetime(df_cli["ProssimoRecall"]) <= datetime.now() + timedelta(days=7))
    ].sort_values("ProssimoRecall")

    if prossimi.empty:
        st.info("✅ Nessun recall previsto nei prossimi 7 giorni.")
    else:
        for i, (_, row) in enumerate(prossimi.head(10).iterrows()):
            nome = row["RagioneSociale"]
            cli_id = row["ClienteID"]
            data = fmt_date(row["ProssimoRecall"])
            if st.button(f"📞 {nome} — Recall il {data}", key=f"btn_recall_{cli_id}_{i}"):
                st.session_state["selected_client_id"] = cli_id
                st.session_state["page"] = "Clienti"
                st.rerun()
# =========================================================
# GESTIONE CLIENTI COMPLETA
# =========================================================
def page_clienti(df_cli, df_ct, role):
    st.title("🏢 Gestione Clienti Completa")

    if df_cli.empty:
        st.warning("Nessun cliente registrato.")
        return

    # --- Pre-selezione cliente se proveniente dalla dashboard ---
    preselected_id = st.session_state.pop("selected_client_id", None)
    nomi_clienti = df_cli["RagioneSociale"].tolist()

    if preselected_id and preselected_id in df_cli["ClienteID"].values:
        idx_default = int(df_cli.index[df_cli["ClienteID"] == preselected_id][0])
    else:
        idx_default = 0
    if idx_default >= len(nomi_clienti):
        idx_default = 0

    cliente = st.selectbox("Seleziona Cliente", nomi_clienti, index=idx_default)
    cli = df_cli[df_cli["RagioneSociale"] == cliente].iloc[0]
    cli_id = cli["ClienteID"]
    cli = cli.fillna("")

    # ---------------------------------------------------------
    # ANAGRAFICA MODIFICABILE
    # ---------------------------------------------------------
    st.markdown("### 🧾 Dati Anagrafici")
    col1, col2, col3 = st.columns(3)
    with col1:
        rag = st.text_input("Ragione Sociale", str(cli.get("RagioneSociale") or ""), key=f"rag_{cli_id}")
        citta = st.text_input("Città", str(cli.get("Citta") or ""), key=f"citta_{cli_id}")
        tel = st.text_input("Telefono", str(cli.get("Telefono") or ""), key=f"tel_{cli_id}")
        cell = st.text_input("Cellulare", str(cli.get("Cellulare") or ""), key=f"cell_{cli_id}")
    with col2:
        ref2 = st.text_input("Persona di Riferimento 2", str(cli.get("PersonaRiferimento2") or ""), key=f"ref2_{cli_id}")
        email = st.text_input("Email", str(cli.get("Email") or ""), key=f"email_{cli_id}")
        iban = st.text_input("IBAN", str(cli.get("IBAN") or ""), key=f"iban_{cli_id}")
        sdi = st.text_input("SDI", str(cli.get("SDI") or ""), key=f"sdi_{cli_id}")
    with col3:
        ult_rec = st.date_input("Ultimo Recall", safe_date(cli.get("UltimoRecall")), key=f"ultrec_{cli_id}")
        pro_rec = st.date_input("Prossimo Recall", safe_date(cli.get("ProssimoRecall"), 30), key=f"prorec_{cli_id}")
        ult_vis = st.date_input("Ultima Visita", safe_date(cli.get("UltimaVisita")), key=f"ultvis_{cli_id}")
        pro_vis = st.date_input("Prossima Visita", safe_date(cli.get("ProssimaVisita"), 30), key=f"provis_{cli_id}")

    if st.button("💾 Salva Dati Anagrafici", key=f"save_anag_{cli_id}"):
        idx = df_cli.index[df_cli["ClienteID"] == cli_id][0]
        df_cli.loc[idx, ["RagioneSociale","Citta","Telefono","Cellulare",
                         "PersonaRiferimento2","Email","IBAN","SDI"]] = [
            rag, citta, tel, cell, ref2, email, iban, sdi
        ]
        df_cli.loc[idx, ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]] = [
            pd.to_datetime(ult_rec), pd.to_datetime(pro_rec),
            pd.to_datetime(ult_vis), pd.to_datetime(pro_vis)
        ]
        save_clienti(df_cli)
        st.success("✅ Dati anagrafici aggiornati.")
        st.rerun()

    # ---------------------------------------------------------
    # NOTE CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🗒️ Note Cliente")
    note_corrente = str(cli.get("Note") or "")
    nuova_nota = st.text_area("Note", note_corrente, height=150, key=f"note_{cli_id}")

    if st.button("💾 Salva Note Cliente", key=f"save_note_{cli_id}"):
        idx = df_cli.index[df_cli["ClienteID"] == cli_id][0]
        df_cli.loc[idx, "Note"] = nuova_nota
        save_clienti(df_cli)
        st.success("✅ Note salvate correttamente.")
        st.rerun()

    # ---------------------------------------------------------
    # CONTRATTI CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📄 Contratti Cliente")

    contratti = df_ct[df_ct["ClienteID"] == cli_id].copy()
    if contratti.empty:
        st.info("Nessun contratto presente per questo cliente.")
    else:
        contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
        contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)

        gb = GridOptionsBuilder.from_dataframe(contratti)
        gb.configure_default_column(editable=True, resizable=True, wrapText=True, autoHeight=True)
        gb.configure_selection(selection_mode="single", use_checkbox=False)
        gb.configure_grid_options(domLayout="autoHeight")
        grid = AgGrid(
            contratti,
            gridOptions=gb.build(),
            theme="balham",
            update_mode=GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            height=420,
            fit_columns_on_grid_load=True,
            key=f"grid_contratti_{cli_id}"
        )

        if st.button("💾 Salva modifiche ai contratti", key=f"save_contracts_{cli_id}"):
            new_df = pd.DataFrame(grid["data"])
            df_ct.update(new_df)
            save_contratti(df_ct)
            st.success("✅ Contratti aggiornati.")
            st.rerun()

    # ---------------------------------------------------------
    # PREVENTIVI CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🧾 Gestione Preventivi DOCX")

    if PREVENTIVI_CSV.exists():
        df_prev = pd.read_csv(PREVENTIVI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])

    templates = {
        "Offerta – Centralino": "Offerta_Centralino.docx",
        "Offerta – Varie": "Offerta_Varie.docx",
        "Offerta – A3": "Offerte_A3.docx",
        "Offerta – A4": "Offerte_A4.docx",
    }

    def next_global_number(df_prev):
        if df_prev.empty:
            return 1
        nums = df_prev["NumeroOfferta"].str.extract(r"(\d+)$")[0].dropna().astype(int)
        return nums.max() + 1 if not nums.empty else 1

    with st.form(f"new_prev_form_{cli_id}"):
        nome_file = st.text_input("Nome File (es. Offerta_SHT.docx)")
        template = st.selectbox("Template", list(templates.keys()))
        submitted = st.form_submit_button("💾 Genera Preventivo")

        if submitted:
            try:
                seq = next_global_number(df_prev)
                nome_sicuro = "".join(c for c in cli["RagioneSociale"].upper() if c.isalnum())
                num = f"SHT-{nome_sicuro}-{seq:03d}"
                tpl_path = STORAGE_DIR / "templates" / templates[template]

                if not tpl_path.exists():
                    st.error(f"❌ Template mancante: {tpl_path}")
                else:
                    out_dir = STORAGE_DIR / "preventivi"
                    out_dir.mkdir(exist_ok=True)
                    out_file = out_dir / (nome_file or f"{num}.docx")

                    doc = Document(tpl_path)
                    mapping = {
                        "CLIENTE": cli["RagioneSociale"],
                        "CITTA": cli.get("Citta", ""),
                        "DATA": datetime.now().strftime("%d/%m/%Y"),
                        "NUMERO_OFFERTA": num,
                    }
                    for p in doc.paragraphs:
                        for k, v in mapping.items():
                            if f"<<{k}>>" in p.text:
                                p.text = p.text.replace(f"<<{k}>>", v)
                    doc.save(out_file)

                    nuovo = {
                        "ClienteID": cli_id,
                        "NumeroOfferta": num,
                        "Template": template,
                        "NomeFile": out_file.name,
                        "Percorso": str(out_file),
                        "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([nuovo])], ignore_index=True)
                    df_prev.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")

                    st.session_state["last_prev_path"] = str(out_file)
                    st.session_state["last_prev_name"] = out_file.name
                    st.success(f"✅ Preventivo creato correttamente: {out_file.name}")

            except Exception as e:
                st.error(f"Errore durante la creazione del preventivo: {e}")

    # --- DOWNLOAD ULTIMO PREVENTIVO FUORI DAL FORM ---
    st.markdown("")
    if "last_prev_path" in st.session_state:
        path = Path(st.session_state["last_prev_path"])
        if path.exists():
            with open(path, "rb") as f:
                file_bytes = f.read()
            st.download_button(
                "⬇️ Scarica Ultimo Preventivo",
                data=file_bytes,
                file_name=st.session_state["last_prev_name"],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"dl_prev_{cli_id}"
            )

    # --- ELENCO PREVENTIVI CLIENTE ---
    st.markdown("---")
    st.subheader("📂 Elenco Preventivi Cliente")
    prev_cli = df_prev[df_prev["ClienteID"] == cli_id]
    if prev_cli.empty:
        st.info("Nessun preventivo presente per questo cliente.")
    else:
        st.dataframe(prev_cli[["NumeroOfferta","Template","DataCreazione","NomeFile"]],
                     use_container_width=True, hide_index=True)
# =========================================================
# CONTRATTI – GESTIONE SEPARATA
# =========================================================
def page_contratti(df_cli, df_ct, role):
    st.title("📄 Gestione Contratti")

    st.markdown("### 🔍 Cerca Contratti")
    col1, col2 = st.columns(2)
    with col1:
        filtro_nome = st.text_input("Cerca per Nome Cliente")
    with col2:
        filtro_stato = st.selectbox("Stato Contratto", ["Tutti", "Attivo", "Chiuso"], index=0)

    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]], on="ClienteID", how="left")

    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_stato != "Tutti":
        merged = merged[merged["Stato"].str.lower() == filtro_stato.lower()]

    merged["DataInizio"] = merged["DataInizio"].apply(fmt_date)
    merged["DataFine"] = merged["DataFine"].apply(fmt_date)

    st.dataframe(
        merged[["RagioneSociale", "Citta", "NumeroContratto", "DataInizio", "DataFine", "Durata", "Stato"]],
        use_container_width=True,
        hide_index=True
    )

    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_contratti.csv", "text/csv")

# =========================================================
# LISTA COMPLETA CLIENTI E CONTRATTI
# =========================================================
def page_lista(df_cli, df_ct, role):
    st.title("📋 Lista Completa Clienti e Contratti")
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

    merged["DataInizio"] = merged["DataInizio"].apply(fmt_date)
    merged["DataFine"] = merged["DataFine"].apply(fmt_date)

    st.dataframe(
        merged[["RagioneSociale", "Citta", "NumeroContratto", "DataInizio", "DataFine", "Stato"]],
        use_container_width=True,
        hide_index=True
    )

    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_clienti_contratti.csv", "text/csv")

# =========================================================
# MAIN APP
# =========================================================
# =========================================================
# MAIN APP – con layout originale e login fullscreen
# =========================================================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    user, role = do_login_fullscreen()
    if not user:
        st.stop()

    # === SIDEBAR (solo dopo login) ===
    st.sidebar.image(LOGO_URL, width=140)
    st.sidebar.markdown(f"**Utente:** {user}")
    if st.sidebar.button("🚪 Logout"):
        for k in ["auth_user", "auth_role"]:
            st.session_state.pop(k, None)
        st.rerun()

    # === Routing delle pagine ===
    pages = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "Lista Completa": page_lista,
    }

    df_cli = load_clienti()
    df_ct = load_contratti()

    current_page = st.session_state.get("page", "Dashboard")
    page = st.sidebar.radio(
        "📂 Seleziona sezione",
        list(pages.keys()),
        index=list(pages.keys()).index(current_page) if current_page in pages else 0
    )
    st.session_state["page"] = page

    # === Caricamento pagina ===
    pages[page](df_cli, df_ct, role)


