from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

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
# FUNZIONI DI UTILITÀ
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

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df

# =========================================================
# I/O DATI
# =========================================================
def load_clienti():
    base_cols = [
        "ClienteID", "RagioneSociale", "Citta", "Telefono", "Cellulare",
        "PersonaRiferimento2", "Email", "UltimoRecall", "ProssimoRecall",
        "UltimaVisita", "ProssimaVisita", "IBAN", "SDI", "Note"
    ]
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=base_cols)

    df = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    df = ensure_columns(df, base_cols)

    # parsing date
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_clienti(df):
    out = df.copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) or d == "" else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=[
            "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
            "DescrizioneProdotto", "TotRata", "Stato"
        ])
    df = pd.read_csv(CONTRATTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["DataInizio", "DataFine"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_contratti(df):
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) or d == "" else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# =========================================================
# LOGIN
# =========================================================
def do_login():
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    if "auth_user" in st.session_state:
        return st.session_state["auth_user"], st.session_state["auth_role"]

    st.markdown(
        f"""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:90vh;text-align:center;'>
            <img src="{LOGO_URL}" width="230" style="margin-bottom:30px;">
            <h2>🔐 Accesso al Gestionale SHT</h2>
            <p style='color:grey;'>Inserisci le tue credenziali per continuare</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    username = st.text_input("👤 Utente")
    password = st.text_input("🔒 Password", type="password")

    if st.button("Entra", use_container_width=True):
        if username in users and password == users[username].get("password"):
            st.session_state["auth_user"] = username
            st.session_state["auth_role"] = users[username].get("role", "viewer")
            st.rerun()
        else:
            st.error("❌ Credenziali errate.")

    st.stop()

# =========================================================
# DASHBOARD
# =========================================================
def page_dashboard(df_cli, df_ct, role):
    now = pd.Timestamp.now().normalize()
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:20px;">
            <img src="{LOGO_URL}" width="120">
            <h1 style="margin-top:15px;">SHT – CRM Dashboard</h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("<hr>", unsafe_allow_html=True)

    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    kpi = [
        ("Clienti", len(df_cli), "👥", "#2196F3"),
        ("Contratti Attivi", (stato != "chiuso").sum(), "📄", "#009688"),
        ("Contratti Chiusi", (stato == "chiuso").sum(), "❌", "#E53935"),
        ("Nuovi Anno", len(df_ct[df_ct["DataInizio"].dt.year == now.year]), "🆕", "#FFC107")
    ]
    c1, c2, c3, c4 = st.columns(4)
    for c, (lbl, val, ico, bg) in zip([c1, c2, c3, c4], kpi):
        c.markdown(f"""
        <div style="background:{bg};color:white;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:30px;">{ico}</div>
            <div style="font-size:20px;font-weight:700;">{val}</div>
            <div>{lbl}</div>
        </div>""", unsafe_allow_html=True)

    # ---------------------------------------------------------
    # CONTRATTI IN SCADENZA
    # ---------------------------------------------------------
    st.markdown("### 📅 Contratti in Scadenza (entro 6 mesi)")
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce")

    scadenza = (
        df_ct[(df_ct["DataFine"].notna()) &
              (df_ct["DataFine"] >= now) &
              (df_ct["DataFine"] <= now + pd.DateOffset(months=6)) &
              (df_ct["Stato"].fillna("").str.lower() != "chiuso")]
        .merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
    )

    if scadenza.empty:
        st.info("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        scadenza = scadenza.drop_duplicates(subset="ClienteID")
        scadenza["DataFine"] = scadenza["DataFine"].dt.strftime("%d/%m/%Y")

        for _, r in scadenza.iterrows():
            key = f"open_{r['ClienteID']}"
            if st.button(f"🔎 {r['RagioneSociale']} – Scade il {r['DataFine']}", key=key, use_container_width=True):
                st.session_state["selected_client_id"] = r["ClienteID"]
                st.session_state["nav_target"] = "Clienti"
                st.rerun()

    # ---------------------------------------------------------
    # PROSSIMI RECALL E VISITE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📅 Prossimi Recall e Visite")

    def color_for_date(d):
        if pd.isna(d): return "grey"
        days = (pd.Timestamp.now() - d).days
        if days > 30: return "green"
        elif days > 7: return "orange"
        else: return "red"

    recall = df_cli[["RagioneSociale", "ProssimoRecall"]].dropna().copy()
    recall["Colore"] = recall["ProssimoRecall"].apply(color_for_date)

    visite = df_cli[["RagioneSociale", "ProssimaVisita"]].dropna().copy()
    visite["Colore"] = visite["ProssimaVisita"].apply(color_for_date)

    col_r, col_v = st.columns(2)
    with col_r:
        st.markdown("#### 📞 Recall")
        for _, r in recall.sort_values("ProssimoRecall").head(10).iterrows():
            color = r["Colore"]
            st.markdown(f"<span style='color:{color}'>• {r['RagioneSociale']} – {fmt_date(r['ProssimoRecall'])}</span>", unsafe_allow_html=True)
    with col_v:
        st.markdown("#### 🚗 Visite")
        for _, r in visite.sort_values("ProssimaVisita").head(10).iterrows():
            color = r["Colore"]
            st.markdown(f"<span style='color:{color}'>• {r['RagioneSociale']} – {fmt_date(r['ProssimaVisita'])}</span>", unsafe_allow_html=True)
# =========================================================
# CLIENTI COMPLETI – anagrafica + note + contratti + preventivi
# =========================================================
def page_clienti(df_cli, df_ct, role):
    st.title("🏢 Gestione Clienti Completa")

    if df_cli.empty:
        st.warning("Nessun cliente registrato.")
        return

    # ---------------------------------------------------------
    # SELEZIONE CLIENTE
    # ---------------------------------------------------------
    cliente = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"])
    cli = df_cli[df_cli["RagioneSociale"] == cliente].iloc[0]
    cli = cli.fillna("")  # converte eventuali pd.NA in stringhe vuote

    cli_id = cli["ClienteID"]

    st.markdown("---")
    st.subheader("📇 Dati Anagrafici")

      # ---------------------------------------------------------
    # SEZIONE ANAGRAFICA MODIFICABILE
    # ---------------------------------------------------------
    col1, col2, col3 = st.columns(3)

    with col1:
        rag = st.text_input("Ragione Sociale", str(cli.get("RagioneSociale") or ""))
        citta = st.text_input("Città", str(cli.get("Citta") or ""))
        tel = st.text_input("Telefono", str(cli.get("Telefono") or ""))
        cell = st.text_input("Cellulare", str(cli.get("Cellulare") or ""))

    with col2:
        ref2 = st.text_input("Persona di Riferimento 2", str(cli.get("PersonaRiferimento2") or ""))
        email = st.text_input("Email", str(cli.get("Email") or ""))
        iban = st.text_input("IBAN", str(cli.get("IBAN") or ""))
        sdi = st.text_input("SDI", str(cli.get("SDI") or ""))

    with col3:
        ult_rec = st.date_input(
            "Ultimo Recall",
            cli.get("UltimoRecall") if not pd.isna(cli.get("UltimoRecall")) else datetime.now()
        )
        pro_rec = st.date_input(
            "Prossimo Recall",
            cli.get("ProssimoRecall") if not pd.isna(cli.get("ProssimoRecall")) else datetime.now() + timedelta(days=30)
        )
        ult_vis = st.date_input(
            "Ultima Visita",
            cli.get("UltimaVisita") if not pd.isna(cli.get("UltimaVisita")) else datetime.now()
        )
        pro_vis = st.date_input(
            "Prossima Visita",
            cli.get("ProssimaVisita") if not pd.isna(cli.get("ProssimaVisita")) else datetime.now() + timedelta(days=30)
        )

    if st.button("💾 Salva Dati Anagrafici"):
        idx = df_cli.index[df_cli["ClienteID"] == cli_id][0]
        df_cli.loc[idx, ["RagioneSociale", "Citta", "Telefono", "Cellulare", "PersonaRiferimento2", "Email", "IBAN", "SDI"]] = [
            rag, citta, tel, cell, ref2, email, iban, sdi
        ]
        df_cli.loc[idx, ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]] = [
            ult_rec, pro_rec, ult_vis, pro_vis
        ]
        save_clienti(df_cli)
        st.success("✅ Dati anagrafici aggiornati.")
        st.rerun()


      # ---------------------------------------------------------
    # NOTE CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🗒️ Note Cliente")

    # valore sicuro (evita errore con pd.NA)
    note_corrente = str(cli.get("Note") or "")

    note = st.text_area("Note", note_corrente, height=140)

    if st.button("💾 Salva Note Cliente"):
        idx = df_cli.index[df_cli["ClienteID"] == cli_id][0]
        df_cli.loc[idx, "Note"] = note
        save_clienti(df_cli)
        st.success("✅ Note salvate con successo.")
        st.rerun()


    # ---------------------------------------------------------
    # CONTRATTI CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📜 Contratti del Cliente")

    contratti = df_ct[df_ct["ClienteID"] == cli_id].copy()
    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

        def stato_badge(s):
            s = str(s).lower()
            if s == "chiuso":  return "🔴 chiuso"
            elif s == "aperto": return "🟢 aperto"
            return s

        contratti["Stato"] = contratti["Stato"].apply(stato_badge)
        contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
        contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
        contratti["TotRata"] = contratti["TotRata"].apply(money)

        gb = GridOptionsBuilder.from_dataframe(contratti)
        gb.configure_default_column(editable=True, resizable=True, filter=True, sortable=True, wrapText=True, autoHeight=True)
        gb.configure_grid_options(domLayout="autoHeight")

        grid = AgGrid(
            contratti,
            gridOptions=gb.build(),
            theme="balham",
            update_mode=GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            height=420,
            fit_columns_on_grid_load=True,
        )

        # pulsanti chiudi/riapri
        st.divider()
        st.markdown("### ⚙️ Gestione Stato Contratti")
        for i, r in contratti.iterrows():
            c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
            with c2:
                st.caption(f"{r['NumeroContratto']} — {r.get('DescrizioneProdotto','')[:60]}")
            with c3:
                stato_clean = str(r["Stato"]).replace("🔴","").replace("🟢","").strip().lower()
                if stato_clean == "chiuso":
                    if st.button("🔓 Riapri", key=f"open_{i}"):
                        df_ct.loc[df_ct.index == r.name, "Stato"] = "aperto"
                        save_contratti(df_ct)
                        st.rerun()
                else:
                    if st.button("❌ Chiudi", key=f"close_{i}"):
                        df_ct.loc[df_ct.index == r.name, "Stato"] = "chiuso"
                        save_contratti(df_ct)
                        st.rerun()

        # salvataggio modifiche inline
        if st.button("💾 Salva modifiche ai contratti"):
            new_df = pd.DataFrame(grid["data"])
            for c in ["DataInizio", "DataFine"]:
                new_df[c] = pd.to_datetime(new_df[c], errors="coerce", dayfirst=True)
            save_contratti(new_df)
            st.success("✅ Contratti aggiornati.")
            st.rerun()

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
        st.dataframe(prev_cli[["NumeroOfferta","Template","DataCreazione","NomeFile"]], use_container_width=True)
    else:
        st.info("Nessun preventivo per questo cliente.")

    st.markdown("### ➕ Crea nuovo preventivo")
    templates = {
        "Offerta – Centralino": "Offerta_Centralino.docx",
        "Offerta – Varie": "Offerta_Varie.docx",
        "Offerta – A3": "Offerte_A3.docx",
        "Offerta – A4": "Offerte_A4.docx",
    }

    def next_global_offer_number(df_prev):
        if df_prev.empty:
            return 1
        try:
            nums = df_prev["NumeroOfferta"].str.extract(r"(\d+)$")[0].dropna().astype(int)
            return nums.max() + 1 if not nums.empty else 1
        except:
            return 1

    with st.form("new_prev"):
        nome = st.text_input("Nome File (es. Offerta_SHT.docx)")
        template = st.selectbox("Template", list(templates.keys()))
        submit = st.form_submit_button("💾 Genera Preventivo")
        if submit:
            try:
                seq = next_global_offer_number(df_prev)
                nome_sicuro = "".join(c for c in cli["RagioneSociale"].upper() if c.isalnum())
                num = f"SHT-{nome_sicuro}-{seq:03d}"

                tpl_path = STORAGE_DIR / "templates" / templates[template]
                if not tpl_path.exists():
                    st.error(f"Template mancante: {tpl_path}")
                else:
                    dest = STORAGE_DIR / "preventivi"
                    dest.mkdir(exist_ok=True)
                    out = dest / (nome or f"{num}.docx")

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
                    doc.save(out)

                    nuovo = {
                        "ClienteID": cli_id,
                        "NumeroOfferta": num,
                        "Template": template,
                        "NomeFile": out.name,
                        "Percorso": str(out),
                        "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([nuovo])], ignore_index=True)
                    df_prev.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")

                    with open(out, "rb") as f:
                        st.download_button("⬇️ Scarica Preventivo", data=f, file_name=out.name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

                    st.success(f"✅ Preventivo creato: {out.name}")
                    st.rerun()
            except Exception as e:
                st.error(f"Errore creazione preventivo: {e}")
# =========================================================
# CONTRATTI – gestione completa
# =========================================================
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

# =========================================================
# LISTA COMPLETA CLIENTI E CONTRATTI
# =========================================================
def page_lista(df_cli, df_ct, role):
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

# =========================================================
# MAIN APP
# =========================================================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    user, role = do_login()
    st.sidebar.image(LOGO_URL, width=150)
    st.sidebar.markdown(f"**Utente:** {user}")
    if st.sidebar.button("🚪 Logout"):
        for k in ["auth_user", "auth_role"]:
            st.session_state.pop(k, None)
        st.rerun()

    # Routing
    pages = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "Lista Completa": page_lista,
    }

    df_cli = load_clienti()
    df_ct = load_contratti()

    page = st.sidebar.radio("📂 Seleziona sezione", list(pages.keys()), index=0)
    if page == "Clienti" and "selected_client_id" in st.session_state:
        cid = st.session_state["selected_client_id"]
        if cid in df_cli["ClienteID"].values:
            cliente_nome = df_cli.loc[df_cli["ClienteID"] == cid, "RagioneSociale"].values[0]
            st.session_state.pop("selected_client_id", None)
            st.session_state["cliente_default"] = cliente_nome
    pages[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
