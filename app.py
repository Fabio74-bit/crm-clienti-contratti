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

def safe_date(val, fallback_days=0):
    if pd.isna(val) or val == "":
        return (datetime.now() + timedelta(days=fallback_days)).date()
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return (datetime.now() + timedelta(days=fallback_days)).date()

# ==========================
# I/O DATI
# ==========================
def load_clienti():
    if not CLIENTI_CSV.exists():
        cols = ["ClienteID","RagioneSociale","Citta","Telefono","Cellulare","PersonaRiferimento2",
                "Email","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["UltimoRecall", "UltimaVisita", "ProssimoRecall", "ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_clienti(df):
    out = df.copy()
    for c in ["UltimoRecall", "UltimaVisita", "ProssimoRecall", "ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if not CONTRATTI_CSV.exists():
        cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
                "DescrizioneProdotto","TotRata","Stato"]
        return pd.DataFrame(columns=cols)
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
# LOGIN FULLSCREEN
# ==========================
def do_login():
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    if "auth_user" in st.session_state:
        return st.session_state["auth_user"], st.session_state.get("auth_role", "viewer")

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
            st.rerun()
        else:
            st.error("❌ Credenziali errate.")
    st.stop()

# ==========================
# KPI CARD
# ==========================
def kpi_card(label, value, icon, bg):
    return f"""
    <div style="background-color:{bg};padding:18px;border-radius:12px;text-align:center;color:white;">
        <div style="font-size:26px;margin-bottom:6px;">{icon}</div>
        <div style="font-size:22px;font-weight:700;">{value}</div>
        <div style="font-size:14px;">{label}</div>
    </div>
    """

# ==========================
# DASHBOARD
# ==========================
def page_dashboard(df_cli, df_ct, role):
    now = pd.Timestamp.now().normalize()
    col1, col2 = st.columns([0.15, 0.85])
    with col1:
        st.image(LOGO_URL, width=120)
    with col2:
        st.markdown("<h1>SHT – CRM Dashboard</h1>", unsafe_allow_html=True)
    st.divider()

    # KPI
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    kpi_data = [
        ("Clienti attivi", len(df_cli), "👥", "#2196F3"),
        ("Contratti attivi", (stato != "chiuso").sum(), "📄", "#009688"),
        ("Contratti chiusi", (stato == "chiuso").sum(), "❌", "#F44336"),
        ("Nuovi contratti", len(df_ct[df_ct["DataInizio"].dt.year == now.year]), "⭐", "#FFC107")
    ]
    c1, c2, c3, c4 = st.columns(4)
    for c, data in zip([c1, c2, c3, c4], kpi_data):
        with c:
            st.markdown(kpi_card(*data), unsafe_allow_html=True)
    st.divider()

    # Contratti in scadenza entro 6 mesi
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
        scadenza = scadenza.merge(df_cli[["ClienteID","RagioneSociale"]], on="ClienteID", how="left").drop_duplicates(subset=["ClienteID","NumeroContratto"])
        for i, row in scadenza.iterrows():
            btn_key = f"open_{row['ClienteID']}_{i}"
            label = f"🔎 {row['RagioneSociale']} — scade il {fmt_date(row['DataFine'])}"
            if st.button(label, key=btn_key):
                st.session_state["selected_client_id"] = row["ClienteID"]
                st.session_state["nav_target"] = "Clienti"
                st.rerun()

    st.divider()

    # Contratti senza data fine
    st.subheader("⏰ Contratti Senza Data Fine (attivi da oggi)")
    senza = df_ct[
        (df_ct["DataFine"].isna()) &
        (df_ct["DataInizio"] >= now) &
        (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]
    if senza.empty:
        st.info("✅ Nessun nuovo contratto senza data fine.")
    else:
        senza = senza.merge(df_cli[["ClienteID","RagioneSociale"]], on="ClienteID", how="left")
        st.dataframe(
            senza[["RagioneSociale","NumeroContratto","DataInizio","Stato"]]
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
            df_cli[["RagioneSociale","UltimoRecall","ProssimoRecall"]]
            .dropna()
            .sort_values("UltimoRecall", ascending=False)
            .head(5),
            use_container_width=True,
            hide_index=True
        )
    with col_v:
        st.markdown("#### 🚗 Ultime Visite")
        st.dataframe(
            df_cli[["RagioneSociale","UltimaVisita","ProssimaVisita"]]
            .dropna()
            .sort_values("UltimaVisita", ascending=False)
            .head(5),
            use_container_width=True,
            hide_index=True
        )
# =========================================================
# CLIENTI COMPLETI – anagrafica + note + contratti + preventivi
# =========================================================
def page_clienti(df_cli, df_ct, role):
    st.title("🏢 Gestione Clienti Completa")

    if df_cli.empty:
        st.warning("Nessun cliente registrato.")
        return

    # ✅ Se è stato selezionato un cliente dalla dashboard, pre-selezionalo
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
        df_cli.loc[idx, ["RagioneSociale", "Citta", "Telefono", "Cellulare",
                         "PersonaRiferimento2", "Email", "IBAN", "SDI"]] = [
            rag, citta, tel, cell, ref2, email, iban, sdi
        ]
        df_cli.loc[idx, ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]] = [
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
    # CREAZIONE PREVENTIVO
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🧾 Gestione Preventivi DOCX")

    if PREVENTIVI_CSV.exists():
        df_prev = pd.read_csv(PREVENTIVI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])

    st.markdown("### ➕ Crea nuovo preventivo")

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

    # ---------------------------------------------------------
    # ELENCO PREVENTIVI
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📂 Elenco Preventivi Cliente")
    prev_cli = df_prev[df_prev["ClienteID"] == cli_id]
    if prev_cli.empty:
        st.info("Nessun preventivo presente per questo cliente.")
    else:
        st.dataframe(prev_cli[["NumeroOfferta", "Template", "DataCreazione", "NomeFile"]],
                     use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # CONTRATTI CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📜 Contratti del Cliente")

    contratti = df_ct[df_ct["ClienteID"] == cli_id].copy()
    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        contratti["DataInizio"] = pd.to_datetime(contratti["DataInizio"], errors="coerce")
        contratti["DataFine"] = pd.to_datetime(contratti["DataFine"], errors="coerce")
        contratti["TotRata"] = contratti["TotRata"].apply(money)
        contratti["Stato"] = contratti["Stato"].fillna("aperto")

        gb = GridOptionsBuilder.from_dataframe(contratti)
        gb.configure_default_column(editable=True, resizable=True, filter=True, sortable=True)
        gb.configure_grid_options(domLayout="autoHeight")

        try:
            grid = AgGrid(
                contratti,
                gridOptions=gb.build(),
                theme="balham",
                update_mode=GridUpdateMode.VALUE_CHANGED,
                allow_unsafe_jscode=True,
                height=420,
                fit_columns_on_grid_load=True,
            )
        except AttributeError:
            st.warning("⚠️ Problema con st_aggrid — aggiorna con: `pip install -U streamlit-aggrid`")
            st.dataframe(contratti, use_container_width=True)
            grid = {"data": contratti.to_dict("records")}

        if st.button("💾 Salva modifiche ai contratti"):
            nuovi = pd.DataFrame(grid["data"])
            for c in ["DataInizio","DataFine"]:
                nuovi[c] = pd.to_datetime(nuovi[c], errors="coerce", dayfirst=True)
            df_ct.update(nuovi)
            save_contratti(df_ct)
            st.success("✅ Contratti aggiornati.")
            st.rerun()

        st.divider()
        st.markdown("### ⚙️ Stato contratti")
        for i, r in contratti.iterrows():
            c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
            with c2:
                st.caption(f"{r['NumeroContratto']} — {str(r.get('DescrizioneProdotto',''))[:60]}")
            with c3:
                stato = (r["Stato"] or "aperto").lower()
                if stato == "chiuso":
                    if st.button("🔓 Riapri", key=f"open_{i}"):
                        df_ct.loc[df_ct.index == r.name, "Stato"] = "aperto"; save_contratti(df_ct); st.rerun()
                else:
                    if st.button("❌ Chiudi", key=f"close_{i}"):
                        df_ct.loc[df_ct.index == r.name, "Stato"] = "chiuso"; save_contratti(df_ct); st.rerun()

    # ---------------------------------------------------------
    # PREVENTIVI CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🧾 Preventivi Cliente")

    if PREVENTIVI_CSV.exists():
        df_prev = pd.read_csv(PREVENTIVI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID","NumeroOfferta","Template","NomeFile","Percorso","DataCreazione"])

    prev_cli = df_prev[df_prev["ClienteID"] == cli_id]

    if not prev_cli.empty:
        st.dataframe(prev_cli[["NumeroOfferta","Template","DataCreazione","NomeFile"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("Nessun preventivo per questo cliente.")

    st.markdown("### ➕ Crea nuovo preventivo")

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

    with st.form("new_prev_form"):
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
                        "CITTA": cli.get("Citta",""),
                        "DATA": datetime.now().strftime("%d/%m/%Y"),
                        "NUMERO_OFFERTA": num,
                    }
                    for p in doc.paragraphs:
                        for k,v in mapping.items():
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

                    with open(out_file, "rb") as f:
                        file_bytes = f.read()
                    st.download_button(
                        "⬇️ Scarica Preventivo",
                        data=file_bytes,
                        file_name=out_file.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"    
                    )


                    st.success(f"✅ Preventivo creato correttamente: {out_file.name}")
                    st.rerun()
            except Exception as e:
                st.error(f"Errore durante la creazione del preventivo: {e}")


# =========================================================
# CONTRATTI – gestione separata
# =========================================================
def page_contratti(df_cli, df_ct, role):
    st.title("📄 Gestione Contratti")

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    sel_cliente = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"].tolist())
    cli = df_cli[df_cli["RagioneSociale"] == sel_cliente].iloc[0]
    cli_id = cli["ClienteID"]

    contratti = df_ct[df_ct["ClienteID"] == cli_id].copy()
    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    contratti["DataInizio"] = pd.to_datetime(contratti["DataInizio"], errors="coerce")
    contratti["DataFine"] = pd.to_datetime(contratti["DataFine"], errors="coerce")
    contratti["TotRata"] = contratti["TotRata"].apply(money)
    contratti["Stato"] = contratti["Stato"].fillna("aperto")

    gb = GridOptionsBuilder.from_dataframe(contratti)
    gb.configure_default_column(editable=True, resizable=True, filter=True, sortable=True)
    gb.configure_grid_options(domLayout="autoHeight")

    grid = AgGrid(
        contratti,
        gridOptions=gb.build(),
        theme="balham",
        update_mode=GridUpdateMode.VALUE_CHANGED,
        height=420,
        allow_unsafe_jscode=True,
    )

    if st.button("💾 Salva modifiche ai contratti"):
        nuovi = pd.DataFrame(grid["data"])
        for c in ["DataInizio","DataFine"]:
            nuovi[c] = pd.to_datetime(nuovi[c], errors="coerce", dayfirst=True)
        df_ct.update(nuovi)
        save_contratti(df_ct)
        st.success("✅ Modifiche salvate.")
        st.rerun()

    st.divider()
    st.markdown("### ⚙️ Stato contratti")
    for i, r in contratti.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
        with c2:
            st.caption(f"{r['NumeroContratto']} — {str(r.get('DescrizioneProdotto',''))[:60]}")
        with c3:
            stato = (r["Stato"] or "aperto").lower()
            if stato == "chiuso":
                if st.button("🔓 Riapri", key=f"open_{i}"):
                    df_ct.loc[df_ct.index == r.name, "Stato"] = "aperto"; save_contratti(df_ct); st.rerun()
            else:
                if st.button("❌ Chiudi", key=f"close_{i}"):
                    df_ct.loc[df_ct.index == r.name, "Stato"] = "chiuso"; save_contratti(df_ct); st.rerun()

# =========================================================
# LISTA COMPLETA CLIENTI E CONTRATTI
# =========================================================
def page_lista(df_cli, df_ct, role):
    st.title("📋 Lista Completa Clienti e Contratti")
    col1, col2 = st.columns(2)
    with col1: filtro_nome = st.text_input("Cerca per nome cliente")
    with col2: filtro_citta = st.text_input("Cerca per città")
    merged = df_ct.merge(df_cli[["ClienteID","RagioneSociale","Citta"]], on="ClienteID", how="left")
    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]
    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")
    st.dataframe(merged[["RagioneSociale","Citta","NumeroContratto","DataInizio","DataFine","Stato"]],
                 use_container_width=True, hide_index=True)
    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_clienti_contratti.csv", "text/csv")

# =========================================================
# MAIN APP
# =========================================================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    user, role = do_login()
    st.sidebar.image(LOGO_URL, width=150)
    st.sidebar.markdown(f"**Utente:** {user}")
    if st.sidebar.button("🚪 Logout"):
        for k in ["auth_user", "auth_role", "selected_client_id"]:
            st.session_state.pop(k, None)
        st.rerun()

    pages = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "Lista Completa": page_lista,
    }

    df_cli = load_clienti()
    df_ct = load_contratti()

    if "nav_target" in st.session_state and st.session_state["nav_target"] == "Clienti":
        page = "Clienti"
        st.session_state.pop("nav_target", None)
    else:
        page = st.sidebar.radio("📂 Seleziona sezione", list(pages.keys()), index=0)

    pages[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
