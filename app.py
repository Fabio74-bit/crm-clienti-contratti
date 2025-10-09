# ============================================================
#  CRM SHT CLIENTI - v4 FIX
#  Gestione Clienti, Contratti e Preventivi - Streamlit Cloud
#  Autore: Fabio Scaranello / SHT srl
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

# ------------------------------------------------------------
# CONFIGURAZIONE PAGINA
# ------------------------------------------------------------
st.set_page_config(page_title="CRM SHT CLIENTI", layout="wide")

PRIMARY_COLOR = "#0078A0"

# ------------------------------------------------------------
# STILI GLOBALI (blu aziendale)
# ------------------------------------------------------------
st.markdown(f"""
    <style>
    h1, h2, h3, h4, h5, h6 {{ color: {PRIMARY_COLOR} !important; }}
    div.stButton > button:first-child {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.4em 1em;
    }}
    div.stButton > button:hover {{
        background-color: #005f80;
        color: white;
    }}
    .metric-label, .stMetricLabel {{ color: {PRIMARY_COLOR} !important; }}
    </style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# COLONNE PREVISTE
# ------------------------------------------------------------
EXPECTED_CLIENTI_COLS = [
    "ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","UltimaVisita","Note"
]

def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df

# ------------------------------------------------------------
# FORMATI E FUNZIONI UTILI
# ------------------------------------------------------------
DATE_FMT = "%d/%m/%Y"

def fmt_date(d):
    if pd.isna(d) or d is None or d == "":
        return ""
    if isinstance(d, str):
        for f in ["%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%m/%d/%Y"]:
            try:
                return datetime.strptime(d,f).strftime(DATE_FMT)
            except Exception:
                pass
        return d
    if isinstance(d,(datetime,date)):
        return d.strftime(DATE_FMT)
    return str(d)

def parse_date_str(s):
    if not s:
        return None
    s = s.strip()
    for f in ["%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%m/%d/%Y"]:
        try:
            return datetime.strptime(s,f).date()
        except Exception:
            pass
    return None

def euro(x):
    try:
        v = float(x)
    except Exception:
        return "-"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    return f"€ {s}"

# ------------------------------------------------------------
# VALIDAZIONI
# ------------------------------------------------------------
def valid_cap(s): return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ", "").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

# ------------------------------------------------------------
# PARSER IMPORTI (gestisce anche formati italiani)
# ------------------------------------------------------------
def parse_money(x):
    if x is None or (isinstance(x, float) and np.isnan(x)) or (isinstance(x, str) and x.strip()==""):
        return np.nan
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    s = s.replace("€", "").replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return float(s)
    except Exception:
        return np.nan

# ------------------------------------------------------------
# NUMERAZIONE PREVENTIVI
# ------------------------------------------------------------
def next_quote_number(df_quotes: pd.DataFrame) -> str:
    today = date.today()
    yy = today.strftime("%Y")
    if df_quotes.empty:
        return f"PRE-{yy}-0001"
    mask = df_quotes["Numero"].fillna("").str.startswith(f"PRE-{yy}-")
    last = df_quotes[mask]["Numero"].sort_values().iloc[-1] if mask.any() else None
    if not last:
        return f"PRE-{yy}-0001"
    n = int(last.split("-")[-1])
    return f"PRE-{yy}-{n+1:04d}"

# ------------------------------------------------------------
# CARICAMENTO / SALVATAGGIO DATI
# ------------------------------------------------------------
@st.cache_data
def load_csv_with_fallback(main_path, fallbacks):
    p = Path(main_path)
    if p.exists():
        return pd.read_csv(p)
    for fb in fallbacks:
        if Path(fb).exists():
            return pd.read_csv(fb)
    return pd.DataFrame()

@st.cache_data
def load_data():
    cli_cols = EXPECTED_CLIENTI_COLS
    clienti = load_csv_with_fallback("clienti.csv",
        ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    clienti = ensure_clienti_cols(clienti)
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")

    ctr_cols = ["ClienteID","NumeroContratto","DataInizio","DataFine",
                "Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    contratti = load_csv_with_fallback("contratti.csv",
        ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    for c in ctr_cols:
        if c not in contratti.columns:
            contratti[c] = None
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = contratti[col].apply(parse_money)

    q_cols = ["ClienteID","Numero","Data","Template","FileName"]
    preventivi = load_csv_with_fallback("preventivi.csv", [])
    if preventivi.empty:
        preventivi = pd.DataFrame(columns=q_cols)
    for c in q_cols:
        if c not in preventivi.columns:
            preventivi[c] = None
    preventivi = preventivi[q_cols]

    return clienti, contratti, preventivi

def save_csv(df, path):
    df.to_csv(path, index=False)
# ============================================================
# PARTE 2 - AUTENTICAZIONE, SIDEBAR E DASHBOARD
# ============================================================

# ------------------------------------------------------------
# AUTENTICAZIONE
# ------------------------------------------------------------
USERS = {
    "admin": {"password": "admin", "role": "Admin"},
    "op": {"password": "op", "role": "Operatore"},
    "view": {"password": "view", "role": "Viewer"},
}

def do_login():
    st.title("Accesso CRM SHT CLIENTI")
    u = st.text_input("Utente", value="admin")
    p = st.text_input("Password", type="password", value="admin")
    if st.button("Entra"):
        if u in USERS and USERS[u]["password"] == p:
            st.session_state["auth_user"] = u
            st.session_state["auth_role"] = USERS[u]["role"]
            st.success(f"Benvenuto, {u}!")
            st.rerun()
        else:
            st.error("Credenziali non valide.")

# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------
def sidebar(role):
    st.sidebar.title("CRM SHT CLIENTI")
    st.sidebar.caption("Gestione Clienti, Contratti e Preventivi • v4")
    return st.sidebar.radio(
        "Naviga",
        ["Dashboard","Clienti","Scheda Cliente","Contratti","Impostazioni"],
        key="page"
    )

# ------------------------------------------------------------
# UTILITY
# ------------------------------------------------------------
def monthly_revenue_open(contratti: pd.DataFrame) -> float:
    df = contratti.copy()
    open_mask = df["Stato"].astype(str).str.lower().eq("aperto")
    tot = df.loc[open_mask, "TotRata"]
    fallback = df.loc[open_mask, "NOL_FIN"].fillna(0) + df.loc[open_mask, "NOL_INT"].fillna(0)
    tot = tot.where(~tot.isna(), fallback)
    return float(tot.fillna(0).sum())

# ------------------------------------------------------------
# DASHBOARD PRINCIPALE
# ------------------------------------------------------------
def render_dashboard(clienti, contratti):
    clienti = ensure_clienti_cols(clienti)
    st.title("🧭 CRM SHT CLIENTI")

    # --- Metriche principali
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clienti", len(clienti))
    c2.metric("Contratti", len(contratti))
    c3.metric("Aperti", int((contratti["Stato"].fillna('').str.lower()=="aperto").sum()))
    c4.metric("Rata mensile (aperti)", euro(monthly_revenue_open(contratti)))

    # ------------------------------------------------------------
    # 🔍 Ricerca cliente
    # ------------------------------------------------------------
    st.markdown("### 🔍 Ricerca cliente per Ragione Sociale o Città")

    query = st.text_input("Cerca cliente", placeholder="Es. Rossi SRL o Verona")
    if query:
        ql = query.lower()
        risultati = clienti[
            clienti.fillna("").apply(
                lambda r: ql in str(r["RagioneSociale"]).lower() or ql in str(r["Città"]).lower(),
                axis=1
            )
        ]

        if risultati.empty:
            st.warning("Nessun cliente trovato.")
        elif len(risultati) == 1:
            riga = risultati.iloc[0]
            st.success(f"Trovato: {riga['RagioneSociale']}")
            if st.button(f"Apri scheda cliente: {riga['RagioneSociale']}"):
                st.session_state["open_client"] = int(riga["ClienteID"])
                st.session_state["page"] = "Scheda Cliente"
                st.rerun()
        else:
            sel = st.selectbox("Seleziona cliente", risultati["RagioneSociale"].tolist())
            scelto = risultati[risultati["RagioneSociale"] == sel].iloc[0]
            if st.button("Apri scheda cliente selezionato"):
                st.session_state["open_client"] = int(scelto["ClienteID"])
                st.session_state["page"] = "Scheda Cliente"
                st.rerun()

    # ------------------------------------------------------------
    # 📅 Promemoria
    # ------------------------------------------------------------
    st.markdown("### 📅 Ultimi Recall e Visite")

    rem = clienti[["ClienteID","RagioneSociale","UltimoRecall","UltimaVisita"]].copy().fillna("")
    st.dataframe(rem, use_container_width=True, height=400)
# ============================================================
# PARTE 3 - SCHEDA CLIENTE DEDICATA
# ============================================================

def render_scheda_cliente(clienti, contratti, preventivi, role):
    st.title("👤 Scheda Cliente")

    # --- Se non c'è cliente selezionato
    if "open_client" not in st.session_state or st.session_state["open_client"] not in clienti["ClienteID"].values:
        st.info("Seleziona un cliente dalla Dashboard o dall'elenco per aprire la scheda.")
        return

    det_id = int(st.session_state["open_client"])
    dettaglio = clienti[clienti["ClienteID"] == det_id]
    if dettaglio.empty:
        st.warning("Cliente non trovato.")
        return

    c = dettaglio.iloc[0]

    # ------------------------------------------------------------
    # ANAGRAFICA CLIENTE
    # ------------------------------------------------------------
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown(f"### 🏢 {c['RagioneSociale']}")
        st.caption(f"{c['Città'] or ''}  ·  📞 {c['Telefono'] or '-'}  ·  📧 {c['Email'] or '-'}")
        st.write(f"**Indirizzo:** {c['Indirizzo'] or '-'}  ·  **CAP:** {c['CAP'] or '-'}")
        st.write(f"**P.IVA:** {c['PartitaIVA'] or '-'}  ·  **SDI:** {c['SDI'] or '-'}")
        st.write(f"**IBAN:** {c['IBAN'] or '-'}")
        st.write("**Note:**")
        st.info(c["Note"] or "–")

    with col2:
        ct = contratti[contratti["ClienteID"] == det_id].copy()
        aperti = ct[ct["Stato"].fillna("").str.lower()=="aperto"]
        tot_series = aperti["TotRata"]
        fallback = aperti["NOL_FIN"].fillna(0) + aperti["NOL_INT"].fillna(0)
        tot_series = tot_series.where(~tot_series.isna(), fallback)

        st.metric("Contratti totali", len(ct))
        st.metric("Contratti aperti", len(aperti))
        st.metric("Tot. rata (aperti)", euro(tot_series.fillna(0).sum()))

    # ------------------------------------------------------------
    # PROMEMORIA COLORATI
    # ------------------------------------------------------------
    st.markdown("### 📅 Promemoria cliente")

    def color_for_date(d):
        if not d:
            return "gray"
        parsed = parse_date_str(d)
        if not parsed:
            return "gray"
        delta = (date.today() - parsed).days
        if delta <= 90:
            return "green"
        else:
            return "red"

    colA, colB = st.columns(2)
    with colA:
        col = color_for_date(c["UltimoRecall"])
        st.markdown(
            f"<div style='background:{col}22;padding:10px;border-radius:8px;'>🕓 <b>Ultimo Recall:</b> {c['UltimoRecall'] or '–'}</div>",
            unsafe_allow_html=True
        )
    with colB:
        col = color_for_date(c["UltimaVisita"])
        st.markdown(
            f"<div style='background:{col}22;padding:10px;border-radius:8px;'>👣 <b>Ultima Visita:</b> {c['UltimaVisita'] or '–'}</div>",
            unsafe_allow_html=True
        )

    # ------------------------------------------------------------
    # CONTRATTI CLIENTE
    # ------------------------------------------------------------
    st.markdown("### 📃 Contratti del cliente")

    ct = contratti[contratti["ClienteID"] == det_id].copy().fillna("")
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        def status_color(s):
            s = (s or "").lower()
            if s == "chiuso": return "#fee2e2"
            if s == "aperto": return "#ecfdf5"
            if s == "sospeso": return "#ffedd5"
            return "#f1f5f9"

        st.dataframe(ct, use_container_width=True, height=350)

        out = BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            ct.to_excel(writer, index=False, sheet_name="Contratti")
        st.download_button(
            "⬇️ Scarica contratti (Excel)",
            data=out.getvalue(),
            file_name=f"contratti_cliente_{det_id}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # ------------------------------------------------------------
    # PREVENTIVI (WORD)
    # ------------------------------------------------------------
    st.markdown("### 🧾 Preventivi (Word)")

    templates = st.session_state.get("quote_templates", [])
    if not isinstance(templates, list):
        templates = []

    if templates:
        tnames = [t[0] for t in templates]
        tsel = st.selectbox("Scegli template", tnames, key=f"tpl_{det_id}")
        if st.button("Crea preventivo (Word)", key=f"gen_{det_id}"):
            numero = next_quote_number(st.session_state.get("preventivi", pd.DataFrame(columns=["ClienteID","Numero","Data","Template","FileName"])))
            try:
                from docx import Document  # richiede python-docx
                tdata = dict(templates)[tsel]
                doc = Document(BytesIO(tdata))
                for p in doc.paragraphs:
                    if "{{" in p.text:
                        p.text = (p.text
                            .replace("{{NUMERO}}", numero)
                            .replace("{{CLIENTE}}", str(c["RagioneSociale"]))
                            .replace("{{DATA}}", fmt_date(date.today())))
                for tbl in doc.tables:
                    for row in tbl.rows:
                        for cell in row.cells:
                            if "{{" in cell.text:
                                cell.text = (cell.text
                                    .replace("{{NUMERO}}", numero)
                                    .replace("{{CLIENTE}}", str(c["RagioneSociale"]))
                                    .replace("{{DATA}}", fmt_date(date.today())))
                out_doc = BytesIO()
                fname = f"Preventivo_{numero}.docx"
                doc.save(out_doc)

                prev_df = st.session_state.get("preventivi", pd.DataFrame(columns=["ClienteID","Numero","Data","Template","FileName"]))
                new_q = {"ClienteID": det_id, "Numero": numero, "Data": fmt_date(date.today()), "Template": tsel, "FileName": fname}
                st.session_state["preventivi"] = pd.concat([prev_df, pd.DataFrame([new_q])], ignore_index=True)

                st.download_button("⬇️ Scarica preventivo (Word)", data=out_doc.getvalue(),
                    file_name=fname, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                st.toast("Preventivo generato.", icon="✅")
            except Exception:
                st.error("Per generare i preventivi serve aggiungere 'python-docx' a requirements.txt.")
    else:
        st.info("Carica i template .docx nella pagina Impostazioni per abilitare i preventivi.")

    # ------------------------------------------------------------
    # ALLEGATI PREVENTIVI
    # ------------------------------------------------------------
    st.markdown("#### 📎 Allegati preventivi del cliente")

    if "attachments_prev" not in st.session_state:
        st.session_state["attachments_prev"] = {}

    up_prev = st.file_uploader("Carica preventivi esistenti (.docx/.pdf)", type=["docx","pdf"], accept_multiple_files=True, key=f"up_prev_{det_id}")
    if up_prev:
        al = st.session_state["attachments_prev"].get(det_id, [])
        for f in up_prev:
            al.append((f.name, f.read()))
        st.session_state["attachments_prev"][det_id] = al
        st.toast(f"{len(up_prev)} file caricati.", icon="✅")

    for (name, data) in st.session_state["attachments_prev"].get(det_id, []):
        st.download_button(f"Scarica {name}", data=data, file_name=name)
# ============================================================
# PARTE 4 - CONTRATTI, IMPOSTAZIONI E MAIN
# ============================================================

# ------------------------------------------------------------
# CONTRATTI
# ------------------------------------------------------------
def render_contratti(clienti, contratti, role):
    st.title("📃 Contratti")
    name_map = dict(zip(clienti["ClienteID"], clienti["RagioneSociale"]))
    df = contratti.copy()
    df["Cliente"] = df["ClienteID"].map(name_map)

    clienti_opts = sorted([n for n in df["Cliente"].dropna().unique()])
    f_cliente = st.selectbox("Seleziona cliente", ["(seleziona)"] + clienti_opts)

    if f_cliente == "(seleziona)":
        st.info("Seleziona un cliente per visualizzare i contratti.")
        return

    df = df[df["Cliente"] == f_cliente]
    f_stato = st.selectbox("Stato", ["(tutti)","Aperto","Chiuso","Sospeso"])
    if f_stato != "(tutti)":
        df = df[df["Stato"].fillna("") == f_stato]

    st.markdown(f"### Contratti di {f_cliente}")
    df_view = df.copy().fillna("")
    st.dataframe(df_view, use_container_width=True, height=400)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Scarica CSV", data=csv, file_name=f"contratti_{f_cliente}.csv", mime="text/csv")

# ------------------------------------------------------------
# IMPOSTAZIONI
# ------------------------------------------------------------
def render_settings(clienti, contratti, preventivi, role):
    st.title("⚙️ Impostazioni e salvataggio dati")
    c1, c2, c3 = st.columns(3)

    if c1.button("💾 Salva clienti.csv", disabled=role=="Viewer"):
        save_csv(clienti, "clienti.csv")
        st.toast("clienti.csv salvato.", icon="✅")

    if c2.button("💾 Salva contratti.csv", disabled=role=="Viewer"):
        save_csv(contratti, "contratti.csv")
        st.toast("contratti.csv salvato.", icon="✅")

    if c3.button("💾 Salva preventivi.csv", disabled=role=="Viewer"):
        save_csv(preventivi, "preventivi.csv")
        st.toast("preventivi.csv salvato.", icon="✅")

    st.markdown("---")
    st.subheader("📄 Importa CSV aggiornati")

    colA, colB = st.columns(2)
    uc = colA.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None and role != "Viewer":
        st.session_state["clienti"] = pd.read_csv(uc)
        st.toast("Clienti caricati (ricordati di salvare).", icon="✅")

    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None and role != "Viewer":
        tmp = pd.read_csv(ut)
        tmp["DataInizio"] = tmp["DataInizio"].apply(fmt_date)
        tmp["DataFine"] = tmp["DataFine"].apply(fmt_date)
        for col in ["NOL_FIN","NOL_INT","TotRata"]:
            if col in tmp.columns:
                tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        st.session_state["contratti"] = tmp
        st.toast("Contratti caricati (ricordati di salvare).", icon="✅")

    # Upload template preventivi
    st.markdown("---")
    st.subheader("📄 Template preventivi (Word .docx)")
    tpls = st.file_uploader(
        "Carica template .docx (usa segnaposto {{NUMERO}}, {{CLIENTE}}, {{DATA}})",
        type=["docx"], accept_multiple_files=True
    )
    if tpls:
        st.session_state["quote_templates"] = [(f.name, f.read()) for f in tpls]
        st.toast(f"{len(tpls)} template caricati.", icon="✅")

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if "auth_user" not in st.session_state:
    do_login()
    st.stop()

role = st.session_state.get("auth_role", "Viewer")

clienti, contratti, preventivi = load_data()
clienti = ensure_clienti_cols(clienti)

if "clienti" not in st.session_state:
    st.session_state["clienti"] = clienti.copy()
if "contratti" not in st.session_state:
    st.session_state["contratti"] = contratti.copy()
if "preventivi" not in st.session_state:
    st.session_state["preventivi"] = preventivi.copy()

page = sidebar(role)
current_page = st.session_state.get("page", page)

if current_page == "Dashboard":
    render_dashboard(st.session_state["clienti"], st.session_state["contratti"])
elif current_page == "Clienti":
    # qui puoi aggiungere eventuale gestione elenco o creazione
    st.info("Funzionalità elenco e creazione clienti gestite nella versione principale.")
elif current_page == "Scheda Cliente":
    render_scheda_cliente(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
elif current_page == "Contratti":
    render_contratti(st.session_state["clienti"], st.session_state["contratti"], role)
else:
    render_settings(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
