# =====================================
# app_FULL_2025.py — Gestionale Clienti SHT
# =====================================
from __future__ import annotations
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from docx import Document
from docx.shared import Pt

st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

# =====================================
# CONFIG / COSTANTI
# =====================================
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage")))
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
    if x is None or (isinstance(x, float) and pd.isna(x)): return pd.NaT
    s = str(x).strip()
    if not s or s.lower() in ("nan", "nat", "none"): return pd.NaT
    d = pd.to_datetime(s, errors="coerce", dayfirst=True)
    return d

def fmt_date(d):
    if pd.isna(d) or d in ("", None): return ""
    try: return pd.to_datetime(d).strftime("%d/%m/%Y")
    except: return ""

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns: df[c] = ""
    return df[cols].copy()

def money(x):
    try:
        if x in (None, "", "nan", "NaN", "None") or pd.isna(x): return ""
        return f"{float(x):,.2f} €"
    except: return ""

def load_clienti():
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
    return ensure_columns(df, CLIENTI_COLS)

def load_contratti():
    if CONTRATTI_CSV.exists():
        df = pd.read_csv(CONTRATTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
        df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
    return ensure_columns(df, CONTRATTI_COLS)

def save_clienti(df): df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
def save_contratti(df): df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# =====================================
# LOGIN FULLSCREEN
# =====================================
def do_login_fullscreen():
    import time
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    st.markdown("<div style='text-align:center;margin-top:10vh;'>", unsafe_allow_html=True)
    st.image(LOGO_URL, width=140)
    st.markdown("<h3>🔐 Accesso CRM-SHT</h3>", unsafe_allow_html=True)

    username = st.text_input("Nome utente").strip().lower()
    password = st.text_input("Password", type="password")

    if st.button("Entra"):
        users = st.secrets["auth"]["users"]
        if username in users and users[username]["password"] == password:
            st.session_state.update({"logged_in": True, "user": username, "role": users[username].get("role", "viewer")})
            time.sleep(0.3)
            st.rerun()
        else:
            st.error("❌ Credenziali non valide.")
    st.stop()

# =====================================
# KPI CARD
# =====================================
def kpi_card(label, value, icon, color):
    return f"""
    <div style="background-color:{color};padding:18px;border-radius:12px;text-align:center;color:white;">
        <div style="font-size:26px;">{icon}</div>
        <div style="font-size:22px;font-weight:700;">{value}</div>
        <div style="font-size:14px;">{label}</div>
    </div>
    """

# =====================================
# DASHBOARD COMPLETA (KPI + NUOVO CLIENTE + SCADENZE + SENZA DATA FINE)
# =====================================
def page_dashboard(df_cli, df_ct, role):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📊 Dashboard Gestionale</h2>", unsafe_allow_html=True)
    st.divider()

    now = pd.Timestamp.now().normalize()
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())

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

    # =====================================
    # ➕ CREA NUOVO CLIENTE + CONTRATTO (aggiornato)
    # =====================================
    with st.expander("➕ Crea Nuovo Cliente + Contratto", expanded=False):
        with st.form("frm_new_cliente_contratto"):
            st.markdown("#### 🧑‍💼 Dati Cliente")
            col1, col2, col3 = st.columns(3)
            with col1:
                new_id = f"C{len(df_cli)+1:04d}"
                rag_soc = st.text_input("Ragione Sociale *")
                persona = st.text_input("Referente")
                piva = st.text_input("Partita IVA")
            with col2:
                indirizzo = st.text_input("Indirizzo")
                citta = st.text_input("Città")
                cap = st.text_input("CAP")
                iban = st.text_input("IBAN")
            with col3:
                telefono = st.text_input("Telefono")
                cell = st.text_input("Cellulare")
                email = st.text_input("Email")
                sdi = st.text_input("SDI")

            st.markdown("#### 📄 Primo Contratto")
            colc1, colc2, colc3 = st.columns(3)
            with colc1:
                num = st.text_input("Numero Contratto (inserisci manualmente)")
            with colc2:
                data_inizio = st.date_input("Data Inizio")
            with colc3:
                durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)

            desc = st.text_area("Descrizione prodotto", height=80)
            colnf, colni, coltot = st.columns(3)
            with colnf: nf = st.text_input("NOL_FIN")
            with colni: ni = st.text_input("NOL_INT")
            with coltot: tot = st.text_input("TotRata")

            submit = st.form_submit_button("💾 Crea Cliente + Contratto")
            if submit:
                if not rag_soc.strip():
                    st.error("Inserisci la ragione sociale.")
                elif not num.strip():
                    st.error("Inserisci il Numero Contratto.")
                else:
                    nuovo_cliente = {
                        "ClienteID": new_id,
                        "RagioneSociale": rag_soc,
                        "PersonaRiferimento": persona,
                        "Indirizzo": indirizzo,
                        "Citta": citta,
                        "CAP": cap,
                        "Telefono": telefono,
                        "Cell": cell,
                        "Email": email,
                        "PartitaIVA": piva,
                        "IBAN": iban,
                        "SDI": sdi,
                        "UltimoRecall": "",
                        "ProssimoRecall": "",
                        "UltimaVisita": "",
                        "ProssimaVisita": "",
                        "NoteCliente": ""
                    }
                    df_cli = pd.concat([df_cli, pd.DataFrame([nuovo_cliente])], ignore_index=True)
                    save_clienti(df_cli)

                    data_fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))
                    nuovo_contratto = {
                        "ClienteID": new_id,
                        "NumeroContratto": num,
                        "DataInizio": data_inizio,
                        "DataFine": data_fine if data_fine else "",
                        "Durata": durata,
                        "DescrizioneProdotto": desc,
                        "NOL_FIN": nf,
                        "NOL_INT": ni,
                        "TotRata": tot,
                        "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([nuovo_contratto])], ignore_index=True)
                    save_contratti(df_ct)

                    st.success(f"✅ Cliente «{rag_soc}» e contratto creati con successo!")
                    st.session_state["selected_cliente"] = new_id
                    st.session_state["nav_target"] = "Contratti"
                    st.rerun()

    # =====================================
    # ⚠️ CONTRATTI IN SCADENZA ENTRO 6 MESI
    # =====================================
    with st.container():
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### ⚠️ Contratti in scadenza entro 6 mesi")

        oggi = pd.Timestamp.now().normalize()
        entro_6_mesi = oggi + pd.DateOffset(months=6)
        df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce")

        scadenze = df_ct[
            (df_ct["DataFine"].notna())
            & (df_ct["DataFine"] >= oggi)
            & (df_ct["DataFine"] <= entro_6_mesi)
            & (df_ct["Stato"].str.lower() != "chiuso")
        ].copy()

        if scadenze.empty:
            st.success("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
        else:
            scadenze = scadenze.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
            scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
            scadenze = scadenze.sort_values("DataFine", ascending=True)
            st.markdown(f"**🔢 {len(scadenze)} contratti in scadenza entro 6 mesi:**")

            for i, r in scadenze.iterrows():
                c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 0.8])
                c1.markdown(f"**{r['RagioneSociale']}**")
                c2.write(r["NumeroContratto"])
                c3.write(r["DataFine"])
                c4.write(r["Stato"])
                if c5.button("Apri", key=f"scad_{i}"):
                    st.session_state["selected_cliente"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Contratti"
                    st.rerun()

        # =====================================
    # 🚫 CLIENTI SENZA DATA FINE
    # (mostra SOLO Durata = 36, 48, 60, 72)
    # =====================================
    with st.container():
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### 🚫 Clienti con contratti senza Data Fine")

        oggi = pd.Timestamp.now().normalize()
        df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
        df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)

        # 🔹 Contratti senza Data Fine
        senza_datafine = df_ct[df_ct["DataFine"].isna() | (df_ct["DataFine"] == "")]
        # 🔹 Solo contratti nuovi (dal 2025)
        senza_datafine = senza_datafine[senza_datafine["DataInizio"] >= pd.Timestamp("2025-01-01")]

        # 🔹 Escludi contratti chiusi
        senza_datafine = senza_datafine[
            ~senza_datafine["Stato"].astype(str).str.lower().eq("chiuso")
        ]

        # 🔹 Includi solo quelli con Durata 36, 48, 60, 72
        valid_durations = ["36", "48", "60", "72"]
        mask_valid = senza_datafine["Durata"].astype(str).str.strip().isin(valid_durations)
        senza_datafine = senza_datafine[mask_valid]

        if senza_datafine.empty:
            st.success("✅ Tutti i nuovi contratti hanno una Data Fine impostata o non rientrano nelle durate 36-48-60-72.")
        else:
            senza_datafine = senza_datafine.merge(
                df_cli[["ClienteID", "RagioneSociale"]],
                on="ClienteID", how="left"
            )
            senza_datafine = senza_datafine.sort_values("DataInizio", ascending=True)
            st.markdown(f"**🔹 {len(senza_datafine)} clienti hanno contratti senza Data Fine (36/48/60/72 mesi):**")

            for i, r in senza_datafine.iterrows():
                c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 0.8])
                with c1:
                    st.markdown(f"**{r['RagioneSociale']}**")
                with c2:
                    st.markdown(r["NumeroContratto"] or "—")
                with c3:
                    st.markdown(fmt_date(r["DataInizio"]) or "—")
                with c4:
                    st.markdown(r["Durata"] or "—")
                with c5:
                    if st.button("Apri", key=f"open_nofine_{i}", use_container_width=True):
                        st.session_state["selected_cliente"] = r["ClienteID"]
                        st.session_state["nav_target"] = "Contratti"
                        st.rerun()


# =====================================
# PAGINA CLIENTI (completa con anagrafica + preventivi)
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Clienti")

    # 🔁 Se è stato selezionato un cliente dalla dashboard, aprilo automaticamente
    if "selected_cliente" in st.session_state:
        selected_id = st.session_state.pop("selected_cliente")
        if selected_id in df_cli["ClienteID"].values:
            cliente_row = df_cli[df_cli["ClienteID"] == selected_id].iloc[0]
            st.session_state["cliente_selezionato"] = cliente_row["RagioneSociale"]

    # 🔍 Ricerca cliente
    st.markdown("### 🔍 Cerca Cliente")
    search_query = st.text_input("Cerca cliente per nome o ID:")
    if search_query:
        filtered = df_cli[
            df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)
            | df_cli["ClienteID"].astype(str).str.contains(search_query, na=False)
        ]
    else:
        filtered = df_cli

    if filtered.empty:
        st.warning("Nessun cliente trovato.")
        return

    options = filtered["RagioneSociale"].tolist()
    sel_rag = st.selectbox(
        "Seleziona Cliente",
        options,
        index=options.index(st.session_state.get("cliente_selezionato", options[0])) if options else 0
    )

    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    # === HEADER ===
    col_header1, col_header2 = st.columns([4, 1])
    with col_header1:
        st.markdown(f"## 🏢 {cliente.get('RagioneSociale', '')}")
        st.caption(f"ClienteID: {sel_id}")
    with col_header2:
        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        if st.button("📄 Vai ai Contratti", use_container_width=True):
            st.session_state["selected_cliente"] = sel_id
            st.session_state["nav_target"] = "Contratti"
            st.rerun()

    # === INFO RAPIDE ===
    indirizzo = cliente.get("Indirizzo", "")
    citta = cliente.get("Citta", "")
    cap = cliente.get("CAP", "")
    persona = cliente.get("PersonaRiferimento", "")
    telefono = cliente.get("Telefono", "")
    cell = cliente.get("Cell", "")

    st.markdown(
        f"""
        <div style='font-size:15px; line-height:1.7;'>
            <b>📍 Indirizzo:</b> {indirizzo} – {citta} {cap}<br>
            <b>🧑‍💼 Referente:</b> {persona}<br>
            <b>📞 Telefono:</b> {telefono} — <b>📱 Cell:</b> {cell}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    # === DATE RECALL E VISITE ===
    st.markdown("### ⚡ Recall e Visite")

    def _safe_date(val):
        try:
            d = pd.to_datetime(val)
            return None if pd.isna(d) else d.date()
        except Exception:
            return None

    col1, col2, col3, col4 = st.columns(4)
    ur = col1.date_input("⏰ Ultimo Recall", value=_safe_date(cliente.get("UltimoRecall")))
    pr = col2.date_input("📅 Prossimo Recall", value=_safe_date(cliente.get("ProssimoRecall")))
    uv = col3.date_input("👣 Ultima Visita", value=_safe_date(cliente.get("UltimaVisita")))
    pv = col4.date_input("🗓️ Prossima Visita", value=_safe_date(cliente.get("ProssimaVisita")))

    if st.button("💾 Salva Aggiornamenti", use_container_width=True):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "UltimoRecall"] = fmt_date(ur)
        df_cli.loc[idx, "ProssimoRecall"] = fmt_date(pr)
        df_cli.loc[idx, "UltimaVisita"] = fmt_date(uv)
        df_cli.loc[idx, "ProssimaVisita"] = fmt_date(pv)
        save_clienti(df_cli)
        st.success("✅ Date aggiornate.")
        st.rerun()

    # === MODIFICA ANAGRAFICA COMPLETA ===
    st.divider()
    with st.expander("✏️ Modifica Anagrafica Completa"):
        with st.form(f"frm_anagrafica_{sel_id}"):
            col1, col2 = st.columns(2)
            with col1:
                indirizzo = st.text_input("📍 Indirizzo", cliente.get("Indirizzo", ""))
                citta = st.text_input("🏙️ Città", cliente.get("Citta", ""))
                cap = st.text_input("📮 CAP", cliente.get("CAP", ""))
                telefono = st.text_input("📞 Telefono", cliente.get("Telefono", ""))
                cell = st.text_input("📱 Cellulare", cliente.get("Cell", ""))
                email = st.text_input("✉️ Email", cliente.get("Email", ""))
                persona = st.text_input("👤 Persona Riferimento", cliente.get("PersonaRiferimento", ""))
            with col2:
                piva = st.text_input("💼 Partita IVA", cliente.get("PartitaIVA", ""))
                iban = st.text_input("🏦 IBAN", cliente.get("IBAN", ""))
                sdi = st.text_input("📡 SDI", cliente.get("SDI", ""))
                note = st.text_area("📝 Note Cliente", cliente.get("NoteCliente", ""), height=110)

            salva_btn = st.form_submit_button("💾 Salva Modifiche")
            if salva_btn:
                idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
                df_cli.loc[idx, "Indirizzo"] = indirizzo
                df_cli.loc[idx, "Citta"] = citta
                df_cli.loc[idx, "CAP"] = cap
                df_cli.loc[idx, "Telefono"] = telefono
                df_cli.loc[idx, "Cell"] = cell
                df_cli.loc[idx, "Email"] = email
                df_cli.loc[idx, "PersonaRiferimento"] = persona
                df_cli.loc[idx, "PartitaIVA"] = piva
                df_cli.loc[idx, "IBAN"] = iban
                df_cli.loc[idx, "SDI"] = sdi
                df_cli.loc[idx, "NoteCliente"] = note
                save_clienti(df_cli)
                st.success("✅ Anagrafica aggiornata.")
                st.rerun()

    st.divider()

    # =======================================================
    # 🧾 GESTIONE PREVENTIVI INTEGRATA
    # =======================================================
    st.markdown("### 🧾 Gestione Preventivi Cliente")

    TEMPLATES_DIR = STORAGE_DIR / "templates"
    PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
    PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)
    prev_csv = STORAGE_DIR / "preventivi.csv"

    TEMPLATE_OPTIONS = {
        "Offerta A4": "Offerte_A4.docx",
        "Offerta A3": "Offerte_A3.docx",
        "Centralino": "Offerta_Centralino.docx",
        "Varie": "Offerta_Varie.docx",
    }

    if prev_csv.exists():
        df_prev = pd.read_csv(prev_csv, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"])

    with st.form("frm_new_prev"):
        anno = datetime.now().year
        nome_cliente = cliente.get("RagioneSociale", "")
        nome_sicuro = "".join(c for c in nome_cliente if c.isalnum())[:6].upper()
        num_off = f"OFF-{anno}-{nome_sicuro}-{len(df_prev[df_prev['ClienteID'] == sel_id]) + 1:03d}"

        st.text_input("Numero Offerta", num_off, disabled=True)
        nome_file = st.text_input("Nome File", f"{num_off}.docx")
        template = st.selectbox("Template", list(TEMPLATE_OPTIONS.keys()))
        submit = st.form_submit_button("💾 Genera Preventivo")

        if submit:
            try:
                tpl = TEMPLATES_DIR / TEMPLATE_OPTIONS[template]
                if not tpl.exists():
                    st.error(f"❌ Template non trovato: {tpl}")
                else:
                    doc = Document(tpl)
                    mappa = {
                        "CLIENTE": cliente.get("RagioneSociale", ""),
                        "INDIRIZZO": cliente.get("Indirizzo", ""),
                        "CITTA": cliente.get("Citta", ""),
                        "NUMERO_OFFERTA": num_off,
                        "DATA": datetime.now().strftime("%d/%m/%Y"),
                        "ULTIMO_RECALL": fmt_date(cliente.get("UltimoRecall")),
                        "PROSSIMO_RECALL": fmt_date(cliente.get("ProssimoRecall")),
                        "ULTIMA_VISITA": fmt_date(cliente.get("UltimaVisita")),
                        "PROSSIMA_VISITA": fmt_date(cliente.get("ProssimaVisita")),
                    }
                    for p in doc.paragraphs:
                        for k, v in mappa.items():
                            p.text = p.text.replace(f"<<{k}>>", str(v))
                            for run in p.runs:
                                run.font.size = Pt(10)
                    out = PREVENTIVI_DIR / nome_file
                    doc.save(out)

                    nuova_riga = {
                        "ClienteID": sel_id,
                        "NumeroOfferta": num_off,
                        "Template": TEMPLATE_OPTIONS[template],
                        "NomeFile": nome_file,
                        "Percorso": str(out),
                        "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                    df_prev = pd.concat([df_prev, pd.DataFrame([nuova_riga])], ignore_index=True)
                    df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
                    st.success(f"✅ Preventivo generato: {out.name}")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Errore durante la creazione: {e}")

    st.divider()
    st.markdown("### 📂 Elenco Preventivi Cliente")

    prev_cli = df_prev[df_prev["ClienteID"] == sel_id]
    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        prev_cli = prev_cli.sort_values("DataCreazione", ascending=False)
        for i, r in prev_cli.iterrows():
            file_path = Path(r["Percorso"])
            col1, col2, col3 = st.columns([0.6, 0.25, 0.15])
            with col1:
                st.markdown(f"**{r['NumeroOfferta']}** — {r['Template']}  \n📅 {r['DataCreazione']}")
            with col2:
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        st.download_button(
                            "⬇️ Scarica",
                            f.read(),
                            file_name=file_path.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{r['NumeroOfferta']}"
                        )
            with col3:
                if role == "admin":
                    if st.button("🗑 Elimina", key=f"del_{r['NumeroOfferta']}_{i}"):
                        try:
                            if file_path.exists():
                                file_path.unlink()
                            df_prev = df_prev.drop(i)
                            df_prev.to_csv(prev_csv, index=False, encoding="utf-8-sig")
                            st.success(f"🗑 Preventivo '{r['NumeroOfferta']}' eliminato.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Errore eliminazione: {e}")

# =====================================
# PAGINA CONTRATTI (AgGrid + Esportazioni)
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    selected_cliente_id = st.session_state.pop("selected_cliente", None)
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    ids = df_cli["ClienteID"].astype(str).tolist()
    idx = ids.index(str(selected_cliente_id)) if selected_cliente_id and str(selected_cliente_id) in ids else 0
    sel_label = st.selectbox("Cliente", labels, index=idx)
    sel_id = ids[labels.tolist().index(sel_label)]
    cliente_info = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]
    rag_soc = cliente_info["RagioneSociale"]

    if selected_cliente_id:
        st.info(f"📌 Mostrati contratti per **{rag_soc}** (ID {sel_id})")

    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()

    # --- Nuovo contratto
    with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            num = c1.text_input("Numero Contratto")
            din = c2.date_input("Data inizio")
            durata = c3.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto", height=80)
            col_nf, col_ni, col_tot = st.columns(3)
            nf = col_nf.text_input("NOL_FIN")
            ni = col_ni.text_input("NOL_INT")
            tot = col_tot.text_input("TotRata")

            if st.form_submit_button("💾 Crea Contratto"):
                new_row = {
                    "ClienteID": sel_id,
                    "NumeroContratto": num,
                    "DataInizio": pd.to_datetime(din),
                    "DataFine": pd.to_datetime(din) + pd.DateOffset(months=int(durata)),
                    "Durata": durata,
                    "DescrizioneProdotto": desc,
                    "NOL_FIN": nf,
                    "NOL_INT": ni,
                    "TotRata": tot,
                    "Stato": "aperto",
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([new_row])], ignore_index=True)
                save_contratti(df_ct)
                st.success("✅ Contratto creato con successo.")
                st.rerun()

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp["TotRata"] = disp["TotRata"].apply(money)
    disp.drop(columns=["ClienteID"], inplace=True, errors="ignore")

    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(resizable=True, wrapText=True, autoHeight=True)
    js = JsCode("""
        function(p){
          const s=p.data.Stato?.toLowerCase();
          if(s==='chiuso')return{'backgroundColor':'#ffebee','color':'#b71c1c'};
          if(s==='aperto')return{'backgroundColor':'#e8f5e9','color':'#1b5e20'};
          return{};
        }""")
    gb.configure_grid_options(getRowStyle=js)
    AgGrid(disp, gridOptions=gb.build(), theme="balham", height=380, update_mode=GridUpdateMode.SELECTION_CHANGED, allow_unsafe_jscode=True)

    st.divider()
    c1, c2 = st.columns(2)

    # --- Excel export
    with c1:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
        from openpyxl.utils import get_column_letter
        from io import BytesIO
        wb = Workbook(); ws = wb.active; ws.title = f"Contratti {rag_soc}"
        ws.merge_cells("A1:G1")
        ws["A1"].value = f"Contratti - {rag_soc}"
        ws["A1"].font = Font(size=12, bold=True)
        ws["A1"].alignment = Alignment(horizontal="center")
        ws.append([]); headers = list(disp.columns)
        ws.append(headers)
        thin = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
        fill = PatternFill("solid", fgColor="2563EB")
        for c in ws[2]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = fill; c.border = thin; c.alignment = Alignment(horizontal="center", wrap_text=True)
        for _, r in disp.iterrows():
            ws.append(list(r))
            for c in ws[ws.max_row]: c.border = thin
        for i in range(1, ws.max_column + 1):
            ws.column_dimensions[get_column_letter(i)].width = 20
        bio = BytesIO(); wb.save(bio)
        st.download_button("📘 Esporta Excel", data=bio.getvalue(), file_name=f"contratti_{rag_soc}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

      # --- PDF export (corretto con safe text e UTF-8) ---
    with c2:
        from textwrap import wrap

        def safe_pdf_text(txt):
            if pd.isna(txt) or txt is None:
                return ""
            if not isinstance(txt, str):
                txt = str(txt)
            txt = txt.replace("€", "EUR").replace("–", "-").replace("—", "-")
            return txt.encode("latin-1", "replace").decode("latin-1")

        try:
            class PDF(FPDF):
                def header(self):
                    self.set_font("Arial", "B", 12)
                    self.cell(0, 10, safe_pdf_text(f"Contratti - {rag_soc}"), ln=1, align="C")
                    self.ln(3)

            pdf = PDF("L", "mm", "A4")
            pdf.add_page()
            pdf.set_font("Arial", size=9)

            widths = [35, 25, 25, 20, 140, 32]
            headers = ["Numero Contratto", "Data Inizio", "Data Fine", "Durata", "Descrizione Prodotto", "Tot Rata"]

            # intestazione
            pdf.set_fill_color(37, 99, 235)
            pdf.set_text_color(255, 255, 255)
            for i, h in enumerate(headers):
                pdf.cell(widths[i], 8, safe_pdf_text(h), border=1, align="C", fill=True)
            pdf.ln(8)
            pdf.set_text_color(0, 0, 0)

            for _, row in disp.iterrows():
                vals = [safe_pdf_text(row.get(c, "")) for c in [
                    "NumeroContratto", "DataInizio", "DataFine", "Durata", "DescrizioneProdotto", "TotRata"
                ]]
                desc_lines = wrap(vals[4], 110)
                row_h = max(len(desc_lines), 1) * 4
                x = 10
                y = pdf.get_y()
                for i, v in enumerate(vals):
                    a = "L" if i == 4 else "C"
                    pdf.set_xy(x, y)
                    pdf.multi_cell(widths[i], 4, v, border=1, align=a)
                    x += widths[i]
                pdf.set_y(y + row_h)

            pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")

            st.download_button(
                "📗 Esporta PDF",
                data=pdf_bytes,
                file_name=f"contratti_{rag_soc}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"❌ Errore durante la generazione del PDF: {e}")



# =====================================
# 📅 PAGINA RECALL E VISITE (stile originale migliorato)
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # --- Stile coerente e pulito ---
    st.markdown("""
    <style>
    .section-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .section-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #2563eb;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .section-title span {
        font-size: 1.3rem;
    }
    .tbl {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
    }
    .tbl th, .tbl td {
        border-bottom: 1px solid #e5e7eb;
        padding: 6px 10px;
        text-align: left;
    }
    .tbl th {
        background-color: #f3f4f6;
        font-weight: 600;
    }
    .tbl tr:hover td {
        background-color: #fef9c3;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Intestazione ---
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📅 Gestione Recall e Visite</h2>", unsafe_allow_html=True)
    st.divider()

    # --- FILTRO RICERCA ---
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'><span>🔍</span>Filtra clienti</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([0.4, 0.4, 0.2])
    with col1:
        filtro_nome = st.text_input("Cerca per nome cliente")
    with col2:
        filtro_citta = st.text_input("Cerca per città")
    with col3:
        if st.button("🔄 Pulisci filtri"):
            st.rerun()

    filtrato = df_cli.copy()
    if filtro_nome:
        filtrato = filtrato[filtrato["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        filtrato = filtrato[filtrato["Citta"].str.contains(filtro_citta, case=False, na=False)]

    if filtrato.empty:
        st.warning("❌ Nessun cliente trovato con i criteri di ricerca.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    st.markdown("</div>", unsafe_allow_html=True)

    # --- Conversione date con formato italiano ---
    for col in ["UltimoRecall", "UltimaVisita", "ProssimoRecall", "ProssimaVisita"]:
        filtrato[col] = pd.to_datetime(filtrato[col], errors="coerce", dayfirst=True)

    oggi = pd.Timestamp.now().normalize()

    # =====================================
    # 🔁 RECALL E VISITE IMMINENTI (entro 30 giorni)
    # =====================================
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'><span>🔁</span>Recall e Visite imminenti (entro 30 giorni)</div>", unsafe_allow_html=True)

    imminenti = filtrato[
        (filtrato["ProssimoRecall"].between(oggi, oggi + pd.DateOffset(days=30))) |
        (filtrato["ProssimaVisita"].between(oggi, oggi + pd.DateOffset(days=30)))
    ].copy()

    if imminenti.empty:
        st.success("✅ Nessun richiamo o visita imminente.")
    else:
        st.markdown("<table class='tbl'><thead><tr>"
                    "<th>Cliente</th><th>Prossimo Recall</th><th>Prossima Visita</th><th style='text-align:center'>Azione</th>"
                    "</tr></thead><tbody>", unsafe_allow_html=True)
        for i, r in imminenti.iterrows():
            cols = st.columns([2.5, 1.2, 1.2, 0.8])
            with cols[0]:
                st.markdown(f"**{r['RagioneSociale']}**")
            with cols[1]:
                st.markdown(fmt_date(r["ProssimoRecall"]))
            with cols[2]:
                st.markdown(fmt_date(r["ProssimaVisita"]))
            with cols[3]:
                if st.button("Apri", key=f"imm_{i}", use_container_width=True):
                    st.session_state["selected_cliente"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Clienti"
                    st.rerun()
        st.markdown("</tbody></table>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # =====================================
    # ⚠️ RECALL E VISITE IN RITARDO
    # =====================================
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'><span>⚠️</span>Recall e Visite in ritardo</div>", unsafe_allow_html=True)

    recall_vecchi = filtrato[
        filtrato["UltimoRecall"].notna() & (filtrato["UltimoRecall"] < oggi - pd.DateOffset(months=3))
    ]
    visite_vecchie = filtrato[
        filtrato["UltimaVisita"].notna() & (filtrato["UltimaVisita"] < oggi - pd.DateOffset(months=6))
    ]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📞 Recall > 3 mesi")
        if recall_vecchi.empty:
            st.info("✅ Nessun recall scaduto.")
        else:
            st.markdown("<table class='tbl'><thead><tr><th>Cliente</th><th>Ultimo Recall</th><th style='text-align:center'>Azione</th></tr></thead><tbody>", unsafe_allow_html=True)
            for i, r in recall_vecchi.iterrows():
                cols = st.columns([2.5, 1.2, 0.8])
                with cols[0]:
                    st.markdown(f"**{r['RagioneSociale']}**")
                with cols[1]:
                    st.markdown(fmt_date(r["UltimoRecall"]))
                with cols[2]:
                    if st.button("Apri", key=f"recold_{i}", use_container_width=True):
                        st.session_state["selected_cliente"] = r["ClienteID"]
                        st.session_state["nav_target"] = "Clienti"
                        st.rerun()
            st.markdown("</tbody></table>", unsafe_allow_html=True)

    with col2:
        st.markdown("### 👣 Visite > 6 mesi")
        if visite_vecchie.empty:
            st.info("✅ Nessuna visita scaduta.")
        else:
            st.markdown("<table class='tbl'><thead><tr><th>Cliente</th><th>Ultima Visita</th><th style='text-align:center'>Azione</th></tr></thead><tbody>", unsafe_allow_html=True)
            for i, r in visite_vecchie.iterrows():
                cols = st.columns([2.5, 1.2, 0.8])
                with cols[0]:
                    st.markdown(f"**{r['RagioneSociale']}**")
                with cols[1]:
                    st.markdown(fmt_date(r["UltimaVisita"]))
                with cols[2]:
                    if st.button("Apri", key=f"visold_{i}", use_container_width=True):
                        st.session_state["selected_cliente"] = r["ClienteID"]
                        st.session_state["nav_target"] = "Clienti"
                        st.rerun()
            st.markdown("</tbody></table>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # =====================================
    # 🧾 STORICO COMPLETO
    # =====================================
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'><span>🧾</span>Storico completo</div>", unsafe_allow_html=True)

    tabella = filtrato[[
        "RagioneSociale", "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"
    ]].copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        tabella[c] = tabella[c].apply(fmt_date)

    st.dataframe(tabella, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


# =====================================
# LISTA COMPLETA CLIENTI E CONTRATTI
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Lista completa Clienti e Contratti")
    col1, col2 = st.columns(2)
    filtro_nome = col1.text_input("Cerca per nome cliente")
    filtro_citta = col2.text_input("Cerca per città")
    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]], on="ClienteID", how="left")
    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]
    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged = merged[["RagioneSociale","Citta","NumeroContratto","DataInizio","DataFine","Stato"]].fillna("")
    st.dataframe(merged, use_container_width=True, hide_index=True)
    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_clienti_contratti.csv", "text/csv")

# =====================================
# MAIN
# =====================================
def main():
    user, role = do_login_fullscreen()
    st.sidebar.success(f"👤 Utente: {user} — Ruolo: {role}")
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Completa": page_lista_clienti
    }
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()), index=list(PAGES.keys()).index(default_page))
    df_cli = load_clienti()
    df_ct = load_contratti()
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
