# ============================================================
# CRM SHT CLIENTI - v7
# Gestione Clienti, Contratti e Preventivi
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

# ------------------------------------------------------------
# CONFIGURAZIONE & STILE
# ------------------------------------------------------------
st.set_page_config(page_title="CRM SHT CLIENTI", layout="wide")
PRIMARY_COLOR = "#0078A0"

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
# SCHEMA CLIENTI / CONTRATTI
# ------------------------------------------------------------
EXPECTED_CLIENTI_COLS = [
    "ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","UltimaVisita","Note"
]

EXPECTED_CONTRATTI_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]

# ------------------------------------------------------------
# FUNZIONI BASE
# ------------------------------------------------------------
DATE_FMT = "%d/%m/%Y"

def fmt_date(d):
    if pd.isna(d) or d in [None, ""]:
        return ""
    if isinstance(d, str):
        for f in ["%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%m/%d/%Y"]:
            try:
                return datetime.strptime(d.strip(),f).strftime(DATE_FMT)
            except:
                pass
        return d
    if isinstance(d,(datetime,date)):
        return d.strftime(DATE_FMT)
    return str(d)

def parse_date_str(s):
    if not s:
        return None
    for f in ["%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%m/%d/%Y"]:
        try:
            return datetime.strptime(s.strip(),f).date()
        except:
            pass
    return None

def euro(x):
    try:
        v = float(x)
    except:
        return "-"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    return f"€ {s}"

def parse_money(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("€","").replace(" ","")
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except:
        return np.nan

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
# LETTURA CSV "INTELLIGENTE"
# ------------------------------------------------------------
def read_csv_smart(path_or_file):
    """Prova automaticamente vari separatori e codifiche"""
    for sep in [",",";","\t"]:
        try:
            df = pd.read_csv(path_or_file, sep=sep, encoding="utf-8-sig")
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    try:
        df = pd.read_csv(path_or_file, sep=",", encoding="latin1")
        if df.shape[1] > 1:
            return df
    except Exception:
        pass
    return pd.DataFrame()  # fallback vuoto

def ensure_clienti_cols(df):
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df[EXPECTED_CLIENTI_COLS]

def ensure_contratti_cols(df):
    for c in EXPECTED_CONTRATTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df[EXPECTED_CONTRATTI_COLS]

# ------------------------------------------------------------
# CARICAMENTO DATI
# ------------------------------------------------------------
@st.cache_data
def load_csv_with_fallback(main_path, fallbacks):
    p = Path(main_path)
    if p.exists():
        return read_csv_smart(p)
    for fb in fallbacks:
        if Path(fb).exists():
            return read_csv_smart(fb)
    return pd.DataFrame()

@st.cache_data
def load_data():
    clienti = load_csv_with_fallback("clienti.csv", [])
    clienti = ensure_clienti_cols(clienti)
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")

    contratti = load_csv_with_fallback("contratti.csv", [])
    contratti = ensure_contratti_cols(contratti)
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = contratti[col].apply(parse_money)
    # calcolo TotRata mancante
    contratti["TotRata"] = contratti["TotRata"].fillna(
        contratti["NOL_FIN"].fillna(0) + contratti["NOL_INT"].fillna(0)
    )

    preventivi = load_csv_with_fallback("preventivi.csv", [])
    if preventivi.empty:
        preventivi = pd.DataFrame(columns=["ClienteID","Numero","Data","Template","FileName"])
    return clienti, contratti, preventivi

def save_csv(df, path):
    df.to_csv(path, index=False)
# ------------------------------------------------------------
# FINE PARTE 1
# ------------------------------------------------------------
# ============================================================
# PARTE 2 - LOGIN, SIDEBAR, DASHBOARD, CLIENTI
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
    st.sidebar.caption("Gestione Clienti, Contratti e Preventivi • v7")
    return st.sidebar.radio(
        "Naviga",
        ["Dashboard","Clienti","Scheda Cliente","Contratti","Impostazioni"]
    )

# ------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------
def monthly_revenue_open(contratti: pd.DataFrame) -> float:
    df = contratti.copy()
    open_mask = df["Stato"].astype(str).str.lower().eq("aperto")
    tot = df.loc[open_mask, "TotRata"]
    fallback = df.loc[open_mask, "NOL_FIN"].fillna(0) + df.loc[open_mask, "NOL_INT"].fillna(0)
    tot = tot.where(~tot.isna(), fallback)
    return float(tot.fillna(0).sum())

def render_dashboard(clienti, contratti):
    st.title("🧭 CRM SHT CLIENTI")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clienti", len(clienti))
    c2.metric("Contratti", len(contratti))
    c3.metric("Aperti", int((contratti["Stato"].fillna('').str.lower()=="aperto").sum()))
    c4.metric("Rata mensile (aperti)", euro(monthly_revenue_open(contratti)))

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
        else:
            sel = st.selectbox("Seleziona cliente", risultati["RagioneSociale"].tolist())
            scelto = risultati[risultati["RagioneSociale"] == sel].iloc[0]
            if st.button("Apri scheda cliente"):
                st.session_state["open_client"] = int(scelto["ClienteID"])
                st.session_state["next_page"] = "Scheda Cliente"
                st.rerun()

# ------------------------------------------------------------
# PAGINA CLIENTI
# ------------------------------------------------------------
def render_clienti(clienti, contratti, role):
    st.title("👥 Clienti")
    editable = role in ["Admin","Operatore"]

    list_tab, new_tab, edit_tab = st.tabs(["📄 Elenco", "➕ Nuovo", "✏️ Modifica / ❌ Elimina"])

    with list_tab:
        q = st.text_input("Cerca (ragione sociale / città / telefono / P.IVA / SDI)")
        df = clienti.copy()
        if q:
            ql = q.lower()
            cols = ["RagioneSociale","Città","Telefono","PartitaIVA","SDI"]
            df = df[df.fillna("").apply(lambda r: any(ql in str(r[c]).lower() for c in cols), axis=1)]
        st.dataframe(
            df[["ClienteID","RagioneSociale","Città","Telefono","PartitaIVA","SDI"]]
            .sort_values("RagioneSociale"),
            use_container_width=True, height=380
        )

    with new_tab:
        with st.form("new_client"):
            colA, colB, colC = st.columns(3)
            with colA:
                rs = st.text_input("Ragione sociale *")
                contatto = st.text_input("Nome cliente / Contatto")
                indirizzo = st.text_input("Indirizzo")
                citta = st.text_input("Città")
                cap = st.text_input("CAP *")
                tel = st.text_input("Telefono")
            with colB:
                email = st.text_input("Email")
                piva = st.text_input("Partita IVA *")
                iban = st.text_input("IBAN (IT) *")
                sdi = st.text_input("SDI *")
                note = st.text_area("Note")
            with colC:
                ur = st.text_input("Ultimo Recall (dd/mm/aaaa)")
                uv = st.text_input("Ultima Visita (dd/mm/aaaa)")
            submitted = st.form_submit_button("Crea", disabled=not editable)
            if submitted:
                errs = []
                if not rs: errs.append("Ragione sociale obbligatoria.")
                if not valid_cap(cap): errs.append("CAP non valido (5 cifre).")
                if not valid_piva(piva): errs.append("Partita IVA non valida (11 cifre).")
                if not valid_iban_it(iban): errs.append("IBAN IT non valido (27 caratteri).")
                if not valid_sdi(sdi): errs.append("SDI non valido (7 alfanumerico o 0000000).")
                ur_d, uv_d = parse_date_str(ur), parse_date_str(uv)
                if ur and not ur_d: errs.append("Formato data Ultimo Recall non valido.")
                if uv and not uv_d: errs.append("Formato data Ultima Visita non valido.")
                if errs:
                    for e in errs: st.warning(e)
                else:
                    next_id = int((clienti["ClienteID"].max() or 0) + 1)
                    new_row = {
                        "ClienteID": next_id, "RagioneSociale": rs, "NomeCliente": contatto,
                        "Indirizzo": indirizzo, "Città": citta, "CAP": cap, "Telefono": tel,
                        "Email": email, "PartitaIVA": piva, "IBAN": iban, "SDI": sdi,
                        "UltimoRecall": fmt_date(ur_d), "UltimaVisita": fmt_date(uv_d),
                        "Note": note
                    }
                    st.session_state["clienti"] = pd.concat(
                        [clienti, pd.DataFrame([new_row])], ignore_index=True
                    )
                    st.success("Cliente creato. Ricordati di salvare nelle Impostazioni.")

    with edit_tab:
        if len(clienti)==0:
            st.info("Nessun cliente.")
        else:
            edit_id = st.number_input(
                "ClienteID", min_value=int(clienti["ClienteID"].min()),
                max_value=int(clienti["ClienteID"].max()), step=1,
                value=int(clienti["ClienteID"].min())
            )
            tgt = clienti[clienti["ClienteID"] == int(edit_id)]
            if tgt.empty:
                st.info("Seleziona un ClienteID esistente.")
            else:
                row = tgt.iloc[0]
                with st.form("edit_client"):
                    colA, colB, colC = st.columns(3)
                    with colA:
                        rs = st.text_input("Ragione sociale *", value=row["RagioneSociale"] or "")
                        contatto = st.text_input("Nome cliente / Contatto", value=row["NomeCliente"] or "")
                        indirizzo = st.text_input("Indirizzo", value=row["Indirizzo"] or "")
                        citta = st.text_input("Città", value=row["Città"] or "")
                        cap = st.text_input("CAP *", value=row["CAP"] or "")
                        tel = st.text_input("Telefono", value=row["Telefono"] or "")
                    with colB:
                        email = st.text_input("Email", value=row["Email"] or "")
                        piva = st.text_input("Partita IVA *", value=row["PartitaIVA"] or "")
                        iban = st.text_input("IBAN (IT) *", value=row["IBAN"] or "")
                        sdi = st.text_input("SDI *", value=row["SDI"] or "")
                        note = st.text_area("Note", value=row["Note"] or "")
                    with colC:
                        ur = st.text_input("Ultimo Recall", value=row["UltimoRecall"] or "")
                        uv = st.text_input("Ultima Visita", value=row["UltimaVisita"] or "")
                    c1, c2 = st.columns(2)
                    save_btn = c1.form_submit_button("Salva modifiche", disabled=not editable)
                    del_btn = c2.form_submit_button("Elimina cliente", disabled=not editable)
                    if save_btn:
                        idx = clienti[clienti["ClienteID"] == int(edit_id)].index
                        if len(idx):
                            st.session_state["clienti"].loc[idx, [
                                "RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono",
                                "Email","PartitaIVA","IBAN","SDI","UltimoRecall","UltimaVisita","Note"
                            ]] = [
                                rs, contatto, indirizzo, citta, cap, tel, email,
                                piva, iban, sdi, fmt_date(parse_date_str(ur)), fmt_date(parse_date_str(uv)), note
                            ]
                            st.success("Cliente aggiornato.")
                    if del_btn:
                        if (contratti["ClienteID"] == int(edit_id)).any():
                            st.warning("Impossibile eliminare: esistono contratti associati.")
                        else:
                            st.session_state["clienti"] = clienti[clienti["ClienteID"] != int(edit_id)]
                            st.success("Cliente eliminato.")
# ------------------------------------------------------------
# FINE PARTE 2
# ------------------------------------------------------------
# ============================================================
# PARTE 3 - SCHEDA CLIENTE, CONTRATTI, IMPOSTAZIONI, MAIN
# ============================================================

# ------------------------------------------------------------
# SCHEDA CLIENTE
# ------------------------------------------------------------
def render_scheda_cliente(clienti, contratti, preventivi, role):
    st.title("📋 Scheda Cliente")
    if len(clienti) == 0:
        st.info("Nessun cliente disponibile.")
        return

    det_id = st.number_input(
        "Apri scheda ClienteID",
        min_value=int(clienti["ClienteID"].min()),
        max_value=int(clienti["ClienteID"].max()),
        step=1,
        value=int(clienti["ClienteID"].min())
    )

    dettaglio = clienti[clienti["ClienteID"] == int(det_id)]
    if dettaglio.empty:
        st.warning("Cliente non trovato.")
        return

    c = dettaglio.iloc[0]
    left, right = st.columns([2, 1])
    with left:
        st.markdown(f"### {c['RagioneSociale']}")
        st.caption(f"{c['Città'] or ''} · 📞 {c['Telefono'] or '-'} · 📧 {c['Email'] or '-'}")
        st.write("**P.IVA:**", c["PartitaIVA"] or "-", " | **IBAN:**", c["IBAN"] or "-", " | **SDI:**", c["SDI"] or "-")
        st.write("**Note:**")
        st.info(c["Note"] or "-")
    with right:
        ct = contratti[contratti["ClienteID"] == int(det_id)].copy()
        st.metric("Contratti", len(ct))
        st.metric("Aperti", int((ct["Stato"].fillna('').str.lower() == "aperto").sum()))
        st.metric("Rata mensile (aperti)", euro(ct[ct["Stato"].fillna('').str.lower() == "aperto"]["TotRata"].fillna(0).sum()))

    st.divider()
    st.write("### 📑 Contratti cliente")
    ct = contratti[contratti["ClienteID"] == int(det_id)].copy()
    if len(ct) == 0:
        st.info("Nessun contratto per questo cliente.")
    else:
        st.dataframe(
            ct[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]],
            use_container_width=True
        )

    st.divider()
    st.write("### 🧾 Preventivi (Word)")
    templates = st.session_state.get("quote_templates", [])
    if templates:
        tnames = [t[0] for t in templates]
        tsel = st.selectbox("Scegli template", tnames)
        gen = st.button("Crea preventivo da template")
        if gen:
            numero = f"PRE-{date.today().year}-{len(preventivi)+1:04d}"
            try:
                from docx import Document
                tdata = dict(templates)[tsel]
                from io import BytesIO
                bio = BytesIO(tdata)
                doc = Document(bio)
                for p in doc.paragraphs:
                    if "{{" in p.text:
                        p.text = (
                            p.text.replace("{{NUMERO}}", numero)
                            .replace("{{CLIENTE}}", str(c["RagioneSociale"]))
                            .replace("{{DATA}}", fmt_date(date.today()))
                        )
                for tbl in doc.tables:
                    for row in tbl.rows:
                        for cell in row.cells:
                            if "{{" in cell.text:
                                cell.text = (
                                    cell.text.replace("{{NUMERO}}", numero)
                                    .replace("{{CLIENTE}}", str(c["RagioneSociale"]))
                                    .replace("{{DATA}}", fmt_date(date.today()))
                                )
                out_doc = BytesIO()
                fname = f"Preventivo_{numero}.docx"
                doc.save(out_doc)
                new_q = {
                    "ClienteID": int(det_id),
                    "Numero": numero,
                    "Data": fmt_date(date.today()),
                    "Template": tsel,
                    "FileName": fname
                }
                st.session_state["preventivi"] = pd.concat(
                    [preventivi, pd.DataFrame([new_q])], ignore_index=True
                )
                st.download_button(
                    "⬇️ Scarica preventivo (Word)",
                    data=out_doc.getvalue(),
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            except Exception:
                st.error("Per i preventivi serve 'python-docx' nel requirements.txt.")
    else:
        st.info("Carica i template .docx nella pagina Impostazioni per generare preventivi.")

# ------------------------------------------------------------
# PAGINA CONTRATTI
# ------------------------------------------------------------
def render_contratti(clienti, contratti):
    st.title("📃 Contratti")
    name_map = dict(zip(clienti["ClienteID"], clienti["RagioneSociale"]))
    df = contratti.copy()
    df["Cliente"] = df["ClienteID"].map(name_map)

    c1, c2, c3, c4 = st.columns(4)
    f_cliente = c1.selectbox("Cliente", ["(tutti)"] + sorted(df["Cliente"].dropna().unique().tolist()))
    f_stato = c2.selectbox("Stato", ["(tutti)","Aperto","Chiuso","Sospeso"])
    f_anno = c3.number_input("Anno inizio (0 = tutti)", min_value=0, step=1, value=0)
    export = c4.button("⬇️ Esporta CSV (filtrato)")

    if f_cliente != "(tutti)":
        df = df[df["Cliente"] == f_cliente]
    if f_stato != "(tutti)":
        df = df[df["Stato"].fillna("") == f_stato]
    if f_anno:
        df = df[df["DataInizio"].apply(lambda x: parse_date_str(x).year if parse_date_str(x) else None) == f_anno]

    st.dataframe(df, use_container_width=True)

    if export:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Scarica contratti filtrati (CSV)", data=csv, file_name="contratti_filtrati.csv", mime="text/csv")

# ------------------------------------------------------------
# PAGINA IMPOSTAZIONI
# ------------------------------------------------------------
def render_settings(clienti, contratti, preventivi, role):
    st.title("⚙️ Impostazioni & Salvataggio")
    c1, c2, c3 = st.columns(3)
    if c1.button("💾 Salva clienti.csv", disabled=role=="Viewer"):
        save_csv(clienti, "clienti.csv")
        st.success("clienti.csv salvato.")
    if c2.button("💾 Salva contratti.csv", disabled=role=="Viewer"):
        save_csv(contratti, "contratti.csv")
        st.success("contratti.csv salvato.")
    if c3.button("💾 Salva preventivi.csv", disabled=role=="Viewer"):
        save_csv(preventivi, "preventivi.csv")
        st.success("preventivi.csv salvato.")

    st.write("---")
    st.write("Carica CSV aggiornati:")
    colA, colB = st.columns(2)
    uc = colA.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None and role != "Viewer":
        st.session_state["clienti"] = read_csv_smart(uc)
        st.session_state["clienti"] = ensure_clienti_cols(st.session_state["clienti"])
        st.success("Clienti caricati.")

    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None and role != "Viewer":
        tmp = read_csv_smart(ut)
        tmp = ensure_contratti_cols(tmp)
        tmp["DataInizio"] = tmp["DataInizio"].apply(fmt_date)
        tmp["DataFine"] = tmp["DataFine"].apply(fmt_date)
        for col in ["NOL_FIN","NOL_INT","TotRata"]:
            tmp[col] = tmp[col].apply(parse_money)
        tmp["TotRata"] = tmp["TotRata"].fillna(tmp["NOL_FIN"].fillna(0) + tmp["NOL_INT"].fillna(0))
        st.session_state["contratti"] = tmp
        st.success("Contratti caricati.")

    st.subheader("📄 Template preventivi (Word .docx)")
    tpls = st.file_uploader("Carica template .docx con segnaposto {{NUMERO}}, {{CLIENTE}}, {{DATA}}", type=["docx"], accept_multiple_files=True)
    if tpls:
        st.session_state["quote_templates"] = [(f.name, f.read()) for f in tpls]
        st.success(f"{len(tpls)} template caricati (non persistono senza storage).")

# ------------------------------------------------------------
# MAIN APP
# ------------------------------------------------------------
if "auth_user" not in st.session_state:
    do_login()
    st.stop()

role = st.session_state.get("auth_role", "Viewer")
clienti, contratti, preventivi = load_data()
if "clienti" not in st.session_state:
    st.session_state["clienti"] = clienti.copy()
if "contratti" not in st.session_state:
    st.session_state["contratti"] = contratti.copy()
if "preventivi" not in st.session_state:
    st.session_state["preventivi"] = preventivi.copy()

page = sidebar(role)

if "next_page" in st.session_state:
    page = st.session_state.pop("next_page")

if page == "Dashboard":
    render_dashboard(st.session_state["clienti"], st.session_state["contratti"])
elif page == "Clienti":
    render_clienti(st.session_state["clienti"], st.session_state["contratti"], role)
elif page == "Scheda Cliente":
    render_scheda_cliente(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
elif page == "Contratti":
    render_contratti(st.session_state["clienti"], st.session_state["contratti"])
else:
    render_settings(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
