diff --git a/app.py b/app.py
index 3495ac3ab538ddc5d26e4f36eb6d72e5e20f9765..28619e0980501af49c34a581ace6e47c18b16c71 100644
--- a/app.py
+++ b/app.py
@@ -1,277 +1,416 @@
 from __future__ import annotations
-import os
 from pathlib import Path
 from datetime import datetime, timedelta
-from typing import Dict
 import pandas as pd
 import streamlit as st
 from docx import Document
 from fpdf import FPDF
 from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
 
+
+def _ensure_directory(path: Path) -> Path:
+    path.mkdir(parents=True, exist_ok=True)
+    return path
+
+
+def _slugify(value: object) -> str:
+    cleaned = "".join(ch if str(ch).isalnum() else "_" for ch in str(value or ""))
+    cleaned = cleaned.strip("_")
+    return cleaned or "item"
+
+
 # Impostazioni pagina
 st.set_page_config(layout="wide", page_title="GESTIONALE CLIENTI – SHT")
 
 # ==========================
 # CONFIG
 # ==========================
 APP_TITLE = "GESTIONALE CLIENTI – SHT"
-STORAGE_DIR = Path("storage")
-STORAGE_DIR.mkdir(parents=True, exist_ok=True)
+STORAGE_DIR = _ensure_directory(Path("storage"))
 
 CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
 CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
 PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"
-TEMPLATES_DIR = STORAGE_DIR / "templates"
-EXTERNAL_PROPOSALS_DIR = STORAGE_DIR / "preventivi"
-EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
+TEMPLATES_DIR = _ensure_directory(STORAGE_DIR / "templates")
+EXTERNAL_PROPOSALS_DIR = _ensure_directory(STORAGE_DIR / "preventivi")
 
 LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"
 DURATE_MESI = ["12", "24", "36", "48", "60", "72"]
 
 TEMPLATE_OPTIONS = {
     "Offerta – Centralino": "Offerta_Centralino.docx",
     "Offerta – Varie": "Offerta_Varie.docx",
     "Offerta – A3": "Offerte_A3.docx",
     "Offerta – A4": "Offerte_A4.docx",
 }
 
+CLIENTI_COLUMNS = [
+    "ClienteID",
+    "RagioneSociale",
+    "PersonaRiferimento",
+    "Indirizzo",
+    "Citta",
+    "CAP",
+    "Telefono",
+    "Email",
+    "PartitaIVA",
+    "IBAN",
+    "SDI",
+    "UltimoRecall",
+    "ProssimoRecall",
+    "UltimaVisita",
+    "ProssimaVisita",
+    "NoteCliente",
+]
+
+CONTRATTI_COLUMNS = [
+    "ClienteID",
+    "NumeroContratto",
+    "DataInizio",
+    "DataFine",
+    "Durata",
+    "DescrizioneProdotto",
+    "NOL_FIN",
+    "NOL_INT",
+    "TotRata",
+    "Stato",
+]
+
+PREVENTIVI_COLUMNS = [
+    "ClienteID",
+    "NumeroOfferta",
+    "Template",
+    "NomeFile",
+    "Percorso",
+    "DataCreazione",
+]
+
 # ==========================
 # UTILS
 # ==========================
 def fmt_date(d):
     if pd.isna(d) or not d:
         return ""
     return pd.to_datetime(d).strftime("%d/%m/%Y")
 
 def money(x):
     try:
-        v = float(pd.to_numeric(x, errors="coerce"))
-        return f"{v:,.2f} €"
+        numeric = pd.to_numeric(x, errors="coerce")
+        if pd.isna(numeric):
+            return ""
+        return f"{float(numeric):,.2f} €"
     except Exception:
         return ""
 
-def load_clienti():
+@st.cache_data(show_spinner=False)
+def load_clienti() -> pd.DataFrame:
     if not CLIENTI_CSV.exists():
-        return pd.DataFrame(columns=[
-            "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta",
-            "CAP", "Telefono", "Email", "PartitaIVA", "IBAN", "SDI",
-            "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "NoteCliente"
-        ])
-    return pd.read_csv(CLIENTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
-
-def save_clienti(df): df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
-
-def load_contratti():
-    if not CONTRATTI_CSV.exists():
-        return pd.DataFrame(columns=[
-            "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
-            "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
-        ])
-    df = pd.read_csv(CONTRATTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
-    for c in ["DataInizio", "DataFine"]:
-        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
-    return df
-
-def save_contratti(df):
-    df2 = df.copy()
-    for c in ["DataInizio", "DataFine"]:
-        df2[c] = df2[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
-    df2.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
+        return pd.DataFrame(columns=CLIENTI_COLUMNS)
+    df = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
+    return df.reindex(columns=CLIENTI_COLUMNS, fill_value="")
+
+
+def save_clienti(df: pd.DataFrame) -> None:
+    export = df.copy()
+    export = export.reindex(columns=CLIENTI_COLUMNS, fill_value="")
+    export.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
+    load_clienti.clear()
+
+
+@st.cache_data(show_spinner=False)
+def load_contratti() -> pd.DataFrame:
+    if CONTRATTI_CSV.exists():
+        df = pd.read_csv(CONTRATTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
+    else:
+        df = pd.DataFrame(columns=CONTRATTI_COLUMNS)
+    for column in ("DataInizio", "DataFine"):
+        df[column] = pd.to_datetime(df.get(column), errors="coerce", dayfirst=True)
+    return df.reindex(columns=CONTRATTI_COLUMNS)
+
+
+def save_contratti(df: pd.DataFrame) -> None:
+    export = df.copy()
+    for column in ("DataInizio", "DataFine"):
+        export[column] = export[column].apply(
+            lambda value: "" if pd.isna(value) else pd.to_datetime(value).strftime("%Y-%m-%d")
+        )
+    export = export.reindex(columns=CONTRATTI_COLUMNS)
+    export.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
+    load_contratti.clear()
+
+
+@st.cache_data(show_spinner=False)
+def load_preventivi() -> pd.DataFrame:
+    if not PREVENTIVI_CSV.exists():
+        return pd.DataFrame(columns=PREVENTIVI_COLUMNS)
+    df = pd.read_csv(PREVENTIVI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
+    return df.reindex(columns=PREVENTIVI_COLUMNS, fill_value="")
+
+
+def save_preventivi(df: pd.DataFrame) -> None:
+    export = df.copy().reindex(columns=PREVENTIVI_COLUMNS, fill_value="")
+    export.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")
+    load_preventivi.clear()
 
 # ==========================
 # LOGIN
 # ==========================
 def do_login_fullscreen():
     users = st.secrets.get("auth", {}).get("users", {})
     if not users:
         return ("ospite", "viewer")
 
     if "auth_user" in st.session_state:
         return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))
 
     st.markdown(f"""
     <style>
         [data-testid="stSidebar"] {{ display: none; }}
         .main > div:first-child {{ padding-top: 3rem; }}
     </style>
     <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;text-align:center;'>
         <img src="{LOGO_URL}" width="220" style="margin-bottom:25px;">
         <h2>🔐 Accesso al Gestionale SHT</h2>
         <p style='color:grey;font-size:14px;'>Inserisci le tue credenziali per continuare</p>
     </div>
     """, unsafe_allow_html=True)
 
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
     return ("", "")
 
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
 
-import uuid
-
-def create_contract_card(row):
+def create_contract_card(row, *, key_suffix: str = ""):
     """
     Card contratto con chiave univoca a prova di duplicati.
     """
-    # Chiave sempre unica (UUID)
-    unique_key = f"open_{row.get('ClienteID','')}_{row.get('NumeroContratto','')}_{uuid.uuid4().hex}"
+    # Chiave deterministica basata sui dati del contratto
+    unique_key = "open_{cliente}_{contratto}_{suffix}".format(
+        cliente=_slugify(row.get("ClienteID", "")),
+        contratto=_slugify(row.get("NumeroContratto", "")),
+        suffix=_slugify(key_suffix) or "0",
+    )
 
     st.markdown(f"""
     <div style="border:1px solid #ddd;border-radius:10px;padding:10px 14px;margin-bottom:8px;background-color:#fafafa;">
       <b>{row.get('RagioneSociale','')}</b> – Contratto: {row.get('NumeroContratto','')}<br>
       Data Inizio: {fmt_date(row.get('DataInizio'))} — Data Fine: {fmt_date(row.get('DataFine'))}<br>
       <small>Stato: {row.get('Stato','')}</small>
     </div>
     """, unsafe_allow_html=True)
 
     # Pulsante univoco
     if st.button("🔎 Apri Cliente", key=unique_key):
         st.session_state["selected_client_id"] = row["ClienteID"]
         st.session_state["nav_target"] = "Contratti"
         st.rerun()
 
 
 def page_dashboard(df_cli, df_ct, role):
     now = pd.Timestamp.now().normalize()
+    upcoming_window = now + pd.Timedelta(days=7)
     col1, col2 = st.columns([0.15, 0.85])
     with col1:
         st.image(LOGO_URL, width=120)
     with col2:
         st.markdown("<h1>SHT – CRM Dashboard</h1>", unsafe_allow_html=True)
         st.markdown("<p style='color:gray;'>Panoramica KPI e stato contratti</p>", unsafe_allow_html=True)
     st.divider()
 
     # === KPI cards ===
     stato = df_ct["Stato"].fillna("").astype(str).str.lower()
+    recall_dates = pd.to_datetime(df_cli["ProssimoRecall"], errors="coerce", dayfirst=True)
+    visita_dates = pd.to_datetime(df_cli["ProssimaVisita"], errors="coerce", dayfirst=True)
     kpi = [
         ("Clienti attivi", len(df_cli), "👥", "#2196F3"),
         ("Contratti attivi", (stato != "chiuso").sum(), "📄", "#009688"),
         ("Contratti chiusi", (stato == "chiuso").sum(), "❌", "#F44336"),
         ("Nuovi contratti", len(df_ct[df_ct["DataInizio"].dt.year == now.year]), "⭐", "#FFC107"),
+        (
+            "Recall imminenti",
+            int(recall_dates.between(now, upcoming_window, inclusive="both").sum()),
+            "📆",
+            "#673AB7",
+        ),
+        (
+            "Visite imminenti",
+            int(visita_dates.between(now, upcoming_window, inclusive="both").sum()),
+            "🚗",
+            "#3F51B5",
+        ),
     ]
-    c1, c2, c3, c4 = st.columns(4)
-    for c, d in zip([c1, c2, c3, c4], kpi):
-        with c:
-            st.markdown(kpi_card(*d), unsafe_allow_html=True)
+    for col, data in zip(st.columns(len(kpi)), kpi):
+        with col:
+            st.markdown(kpi_card(*data), unsafe_allow_html=True)
     st.divider()
 
     # === CONTRATTI IN SCADENZA (entro 6 mesi) ===
     st.subheader("📅 Contratti in Scadenza (entro 6 mesi)")
     scadenza = df_ct[
-        (df_ct["DataFine"].notna()) &
-        (df_ct["DataFine"] <= now + pd.DateOffset(months=6)) &
-        (df_ct["Stato"].str.lower() != "chiuso")
+        (df_ct["DataFine"].notna())
+        & (df_ct["DataFine"] >= now)
+        & (df_ct["DataFine"] <= now + pd.DateOffset(months=6))
+        & (df_ct["Stato"].str.lower() != "chiuso")
     ]
     if scadenza.empty:
         st.info("✅ Nessun contratto in scadenza.")
     else:
         scadenza = scadenza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
         scadenza = scadenza.sort_values("DataFine").head(10)  # Mostra solo i primi 10
         with st.container():
             st.markdown(
                 """
                 <style>
                 .scroll-box {
                     max-height: 250px;
                     overflow-y: auto;
                     border: 1px solid #ddd;
                     border-radius: 8px;
                     padding: 6px 10px;
                     background-color: #fafafa;
                 }
                 </style>
                 """,
                 unsafe_allow_html=True
             )
             st.markdown("<div class='scroll-box'>", unsafe_allow_html=True)
-            for _, row in scadenza.iterrows():
-                create_contract_card(row)
+            for idx, row in scadenza.iterrows():
+                create_contract_card(row, key_suffix=f"due_{idx}")
             st.markdown("</div>", unsafe_allow_html=True)
     st.divider()
 
+    # === CONTRATTI SCADUTI ===
+    st.subheader("⚠️ Contratti Scaduti")
+    scaduti = df_ct[
+        (df_ct["DataFine"].notna())
+        & (df_ct["DataFine"] < now)
+        & (df_ct["Stato"].str.lower() != "chiuso")
+    ]
+    if scaduti.empty:
+        st.info("✅ Nessun contratto scaduto non chiuso.")
+    else:
+        scaduti = scaduti.merge(
+            df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left"
+        ).sort_values("DataFine")
+        limit = 10
+        for idx, row in scaduti.head(limit).iterrows():
+            create_contract_card(row, key_suffix=f"expired_{idx}")
+        if len(scaduti) > limit:
+            st.caption(f"Mostrati i primi {limit} contratti scaduti su {len(scaduti)} totali.")
+    st.divider()
+
     # === CONTRATTI SENZA DATA FINE ===
     st.subheader("⏰ Contratti Senza Data Fine")
     senza = df_ct[(df_ct["DataFine"].isna()) & (df_ct["Stato"].str.lower() != "chiuso")]
     if senza.empty:
         st.info("✅ Nessun contratto senza data fine.")
     else:
         senza = senza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
         limit = 5
-        for i, (_, row) in enumerate(senza.iterrows()):
+        for i, (idx, row) in enumerate(senza.iterrows()):
             if i < limit:
-                create_contract_card(row)
+                create_contract_card(row, key_suffix=f"nodate_{idx}")
             else:
                 break
         if len(senza) > limit:
             if st.button(f"🔽 Mostra tutti ({len(senza) - limit} altri)", key="show_all_nodate"):
-                for _, row in senza.iloc[limit:].iterrows():
-                    create_contract_card(row)
+                for idx, row in senza.iloc[limit:].iterrows():
+                    create_contract_card(row, key_suffix=f"nodate_extra_{idx}")
     st.divider()
 
-    # === ULTIMI RECALL / VISITE ===
-    st.subheader("📞 Ultimi Recall e Visite")
-    df_cli["UltimoRecall"] = pd.to_datetime(df_cli["UltimoRecall"], errors="coerce", dayfirst=True)
-    df_cli["UltimaVisita"] = pd.to_datetime(df_cli["UltimaVisita"], errors="coerce", dayfirst=True)
-    col_r, col_v = st.columns(2)
-    with col_r:
-        st.markdown("#### 🔁 Ultimi Recall")
-        st.dataframe(
-            df_cli[["RagioneSociale", "UltimoRecall", "ProssimoRecall"]]
-            .sort_values("UltimoRecall", ascending=False)
-            .head(5),
-            hide_index=True,
-            use_container_width=True,
-        )
-    with col_v:
-        st.markdown("#### 🚗 Ultime Visite")
-        st.dataframe(
-            df_cli[["RagioneSociale", "UltimaVisita", "ProssimaVisita"]]
-            .sort_values("UltimaVisita", ascending=False)
-            .head(5),
-            hide_index=True,
-            use_container_width=True,
-        )
+    # === RECALL / VISITE ===
+    st.subheader("📞 Recall e Visite")
+    df_cli["UltimoRecall"] = pd.to_datetime(
+        df_cli["UltimoRecall"], errors="coerce", dayfirst=True
+    )
+    df_cli["UltimaVisita"] = pd.to_datetime(
+        df_cli["UltimaVisita"], errors="coerce", dayfirst=True
+    )
+    tab_recenti, tab_imminenti = st.tabs(["Recenti", "Imminenti"])
+    with tab_recenti:
+        col_r, col_v = st.columns(2)
+        with col_r:
+            st.markdown("#### 🔁 Ultimi Recall")
+            st.dataframe(
+                df_cli[["RagioneSociale", "UltimoRecall", "ProssimoRecall"]]
+                .sort_values("UltimoRecall", ascending=False)
+                .head(5),
+                hide_index=True,
+                use_container_width=True,
+            )
+        with col_v:
+            st.markdown("#### 🚗 Ultime Visite")
+            st.dataframe(
+                df_cli[["RagioneSociale", "UltimaVisita", "ProssimaVisita"]]
+                .sort_values("UltimaVisita", ascending=False)
+                .head(5),
+                hide_index=True,
+                use_container_width=True,
+            )
+    with tab_imminenti:
+        imminenti = df_cli.copy()
+        imminenti["ProssimoRecall"] = recall_dates
+        imminenti["ProssimaVisita"] = visita_dates
+        col_r_next, col_v_next = st.columns(2)
+        with col_r_next:
+            st.markdown("#### 🔜 Recall (prossimi 7 giorni)")
+            imminenti_recall = imminenti[
+                imminenti["ProssimoRecall"].between(now, upcoming_window, inclusive="both")
+            ][["RagioneSociale", "ProssimoRecall"]].sort_values("ProssimoRecall")
+            if imminenti_recall.empty:
+                st.info("Nessun recall in programma nella prossima settimana.")
+            else:
+                st.dataframe(imminenti_recall, hide_index=True, use_container_width=True)
+        with col_v_next:
+            st.markdown("#### 🔜 Visite (prossimi 7 giorni)")
+            imminenti_visite = imminenti[
+                imminenti["ProssimaVisita"].between(now, upcoming_window, inclusive="both")
+            ][["RagioneSociale", "ProssimaVisita"]].sort_values("ProssimaVisita")
+            if imminenti_visite.empty:
+                st.info("Nessuna visita in programma nella prossima settimana.")
+            else:
+                st.dataframe(imminenti_visite, hide_index=True, use_container_width=True)
 
 # ==========================
 # CLIENTI
 # ==========================
 def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
     st.title("📋 Gestione Clienti")
 
     # Ricerca cliente
     search_query = st.text_input("🔍 Cerca cliente per nome:")
     if search_query:
         filtered = df_cli[df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)]
     else:
         filtered = df_cli
     if filtered.empty:
         st.warning("Nessun cliente trovato.")
         st.stop()
 
     sel_rag = st.selectbox("Seleziona Cliente", filtered["RagioneSociale"].tolist())
     cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
     sel_id = cliente["ClienteID"]
 
     st.markdown(f"### 🏢 {cliente.get('RagioneSociale', '')}")
     st.caption(f"ClienteID: {sel_id}")
     st.divider()
 
@@ -342,97 +481,96 @@ def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
                 idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                 df_cli.loc[idx, ["RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
                                  "PartitaIVA", "Email", "Telefono"]] = [
                                      rag, ref, indir, citta, cap, piva, mail, tel]
                 save_clienti(df_cli)
                 st.success("✅ Anagrafica aggiornata con successo.")
                 st.rerun()
 
     st.divider()
 
     # Note Cliente
     st.markdown("### 📝 Note Cliente")
     note_attuali = cliente.get("NoteCliente", "")
     nuove_note = st.text_area("Note:", note_attuali, height=150)
     if st.button("💾 Salva Note"):
         idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
         df_cli.loc[idx, "NoteCliente"] = nuove_note
         save_clienti(df_cli)
         st.success("✅ Note salvate con successo.")
         st.rerun()
 
     st.divider()
 
     # Preventivi
     st.markdown("### 🧾 Crea Nuovo Preventivo DOCX")
-    prev_path = PREVENTIVI_CSV
-    if prev_path.exists():
-        df_prev = pd.read_csv(prev_path, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
-    else:
-        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])
+    df_prev = load_preventivi()
 
     def genera_numero_offerta(cliente_nome):
         anno = datetime.now().year
         nome_sicuro = "".join(c for c in cliente_nome if c.isalnum())[:6].upper()
         seq = len(df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]) + 1
         return f"OFF-{anno}-{nome_sicuro}-{seq:03d}"
 
     next_num = genera_numero_offerta(cliente["RagioneSociale"])
     with st.form("frm_new_prev"):
         num = st.text_input("Numero Offerta", next_num)
         template = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
         nome_file = st.text_input("Nome file (es. Offerta_ACME.docx)")
         submitted = st.form_submit_button("💾 Genera Preventivo")
         if submitted:
             template_path = TEMPLATES_DIR / TEMPLATE_OPTIONS[template]
+            if not template_path.exists():
+                st.error("❌ Template non trovato. Verifica la cartella templates.")
+                st.stop()
             if not nome_file.strip():
                 nome_file = f"{num}.docx"
             if not nome_file.lower().endswith(".docx"):
                 nome_file += ".docx"
             output_path = EXTERNAL_PROPOSALS_DIR / nome_file
             doc = Document(template_path)
             mapping = {
                 "CLIENTE": cliente["RagioneSociale"],
                 "INDIRIZZO": cliente["Indirizzo"],
                 "CITTA": cliente["Citta"],
                 "NUMERO_OFFERTA": num,
                 "DATA": datetime.now().strftime("%d/%m/%Y"),
             }
             for p in doc.paragraphs:
                 for key, val in mapping.items():
                     p.text = p.text.replace(f"<<{key}>>", str(val))
             doc.save(output_path)
             nuovo = {
-                "ClienteID": sel_id,
+                "ClienteID": str(sel_id),
                 "NumeroOfferta": num,
                 "Template": TEMPLATE_OPTIONS[template],
                 "NomeFile": nome_file,
                 "Percorso": str(output_path),
                 "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
             }
             df_prev = pd.concat([df_prev, pd.DataFrame([nuovo])], ignore_index=True)
-            df_prev.to_csv(prev_path, index=False, encoding="utf-8-sig")
+            save_preventivi(df_prev)
             st.success(f"✅ Preventivo creato: {nome_file}")
             st.rerun()
 
     # Elenco preventivi
     st.markdown("### 📂 Elenco Preventivi")
     prev_cli = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)]
     if prev_cli.empty:
         st.info("Nessun preventivo per questo cliente.")
     else:
         for _, r in prev_cli.iterrows():
             col1, col2 = st.columns([0.8, 0.2])
             with col1:
                 st.write(f"📄 **{r['NumeroOfferta']}** — {r['Template']} ({r['DataCreazione']})")
             with col2:
                 file_path = Path(r["Percorso"])
                 if file_path.exists():
                     with open(file_path, "rb") as f:
                         st.download_button("⬇️ Scarica", f, file_path.name)
                 else:
                     st.error("❌ File mancante")
 
 
 # ==========================
 # HELPER FUNZIONI DATE ITALIANE
 # ==========================
@@ -441,61 +579,71 @@ def _parse_italian_date(value):
         return None
     try:
         return datetime.strptime(str(value), "%d/%m/%Y")
     except Exception:
         try:
             return pd.to_datetime(value, dayfirst=True)
         except Exception:
             return None
 
 def _format_italian_date(date_val):
     return date_val.strftime("%d/%m/%Y") if pd.notna(date_val) and date_val else ""
 # ==========================
 # CONTRATTI (AgGrid + stile coerente)
 # ==========================
 def safe_text(txt):
     return str(txt).encode("latin-1", "replace").decode("latin-1")
 
 def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
     st.title("📄 Gestione Contratti")
 
     if df_cli.empty:
         st.info("Nessun cliente presente.")
         return
 
     pre = st.session_state.get("selected_client_id")
-    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
-    idx = 0
-    if pre:
-        try:
-            idx = int(df_cli.index[df_cli["ClienteID"].astype(str) == str(pre)][0])
-        except:
-            idx = 0
-
-    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
-    sel_id = df_cli.iloc[labels[labels == sel_label].index[0]]["ClienteID"]
-    rag_soc = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]["RagioneSociale"]
+    client_options = [
+        (row["ClienteID"], f"{row['ClienteID']} — {row['RagioneSociale']}")
+        for _, row in df_cli.iterrows()
+    ]
+    default_index = next(
+        (i for i, (cid, _) in enumerate(client_options) if str(cid) == str(pre)),
+        0,
+    )
+    selected_option = st.selectbox(
+        "Cliente",
+        client_options,
+        index=default_index if default_index < len(client_options) else 0,
+        format_func=lambda item: item[1] if isinstance(item, tuple) else str(item),
+    )
+    sel_id, _ = selected_option
+    cliente_row = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)]
+    if cliente_row.empty:
+        st.error("Cliente selezionato non trovato nei dati disponibili.")
+        return
+    cliente_row = cliente_row.iloc[0]
+    rag_soc = cliente_row.get("RagioneSociale", "")
 
     # Creazione nuovo contratto
     with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
         with st.form("frm_new_contract"):
             c1, c2, c3 = st.columns(3)
             with c1:
                 num = st.text_input("Numero Contratto")
             with c2:
                 din = st.date_input("Data Inizio", format="DD/MM/YYYY")
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
@@ -605,52 +753,50 @@ def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
                 pdf.cell(20, 6, safe_text(row["Stato"]), 1)
                 pdf.ln()
             pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
             st.download_button("📘 Esporta PDF", pdf_bytes, f"contratti_{rag_soc}.pdf", "application/pdf")
         except Exception as e:
             st.error(f"Errore PDF: {e}")
 
 
 # ==========================
 # LISTA CLIENTI
 # ==========================
 def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
     st.title("📋 Lista Clienti")
     filtro = st.text_input("🔎 Cerca cliente o città:")
     if filtro:
         df_fil = df_cli[df_cli.apply(lambda r: filtro.lower() in str(r).lower(), axis=1)]
     else:
         df_fil = df_cli
     st.dataframe(df_fil[["ClienteID", "RagioneSociale", "Citta", "Telefono", "Email"]])
 
 
 # ==========================
 # MAIN APP
 # ==========================
 def main():
-    st.set_page_config(page_title="Gestionale Clienti SHT", layout="wide")
-
     # Login
     user, role = do_login_fullscreen()
     if not user:
         st.stop()
 
     st.sidebar.success(f"Utente: {user} — Ruolo: {role}")
 
     # Menu laterale
     PAGES = {
         "Dashboard": page_dashboard,
         "Clienti": page_clienti,
         "Contratti": page_contratti,
         "📋 Lista Clienti": page_lista_clienti
     }
 
     default_page = st.session_state.pop("nav_target", "Dashboard")
     page = st.sidebar.radio("Menu", list(PAGES.keys()),
                             index=list(PAGES.keys()).index(default_page)
                             if default_page in PAGES else 0)
 
     # Caricamento dati
     df_cli = load_clienti()
     df_ct = load_contratti()
 
     # Routing
