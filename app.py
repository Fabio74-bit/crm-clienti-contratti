import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="CRM Clienti & Contratti — v3", layout="wide")

EXPECTED_CLIENTI_COLS = [
    "ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]

def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Garantisce che tutte le colonne cliente esistano anche se i CSV sono vuoti."""
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df


# =========================
# HELPERS & FORMATS
# =========================
DATE_FMT = "%d/%m/%Y"

def fmt_date(d):
    if pd.isna(d) or d is None or d == "":
        return ""
    if isinstance(d, str):
        for f in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"]:
            try:
                return datetime.strptime(d, f).strftime(DATE_FMT)
            except Exception:
                pass
        return d
    if isinstance(d, (datetime, date)):
        return d.strftime(DATE_FMT)
    return str(d)

def parse_date_str(s):
    if not s:
        return None
    s = s.strip()
    for f in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"]:
        try:
            return datetime.strptime(s, f).date()
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

def status_class(s):
    s = (s or "").strip().lower()
    if s == "chiuso":
        return "closed"
    if s == "aperto":
        return "open"
    if s == "sospeso":
        return "suspended"
    return "unknown"

def status_chip(s):
    m = status_class(s)
    color = {"open":"#16a34a","closed":"#b91c1c","suspended":"#d97706","unknown":"#64748b"}[m]
    return f"<span style='background:{color}22;color:{color};padding:2px 8px;border-radius:999px;font-size:12px'>{s or '-'}</span>"

# =========================
# VALIDAZIONI
# =========================
def valid_cap(s): return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ", "").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

# =========================
# QUOTE NUMBERS
# =========================
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

# =========================
# LOAD & SAVE DATA
# =========================
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
    clienti = load_csv_with_fallback("clienti.csv", ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    clienti = ensure_clienti_cols(clienti)
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")

    ctr_cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    contratti = load_csv_with_fallback("contratti.csv", ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    for c in ctr_cols:
        if c not in contratti.columns:
            contratti[c] = None
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = pd.to_numeric(contratti[col], errors="coerce")

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


# =========================
# LOGIN
# =========================
USERS = {
    "admin": {"password": "admin", "role": "Admin"},
    "op": {"password": "op", "role": "Operatore"},
    "view": {"password": "view", "role": "Viewer"},
}

def do_login():
    st.title("Accesso CRM")
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


# =========================
# SIDEBAR
# =========================
def sidebar(role):
    st.sidebar.title("CRM")
    st.sidebar.caption("v3 • validazioni, allegati, preventivi, Excel/print")
    return st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti","Impostazioni"])


# =========================
# DASHBOARD
# =========================
def monthly_revenue_open(contratti: pd.DataFrame) -> float:
    df = contratti.copy()
    return float(df[df["Stato"].fillna("").str.lower()=="aperto"]["TotRata"].fillna(0).sum())

def render_dashboard(clienti, contratti):
    clienti = ensure_clienti_cols(clienti)
    st.title("📊 Dashboard")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Clienti", len(clienti))
    c2.metric("Contratti", len(contratti))
    c3.metric("Aperti", int((contratti["Stato"].fillna('').str.lower()=="aperto").sum()))
    c4.metric("Rata mensile (aperti)", euro(monthly_revenue_open(contratti)))

    st.subheader("Prossimi promemoria")
    rem = clienti[["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]].copy()
    st.dataframe(rem, use_container_width=True)


# =========================
# CLIENTI
# =========================
def render_clienti(clienti, contratti, preventivi, role):
    clienti = ensure_clienti_cols(clienti)
    st.title("👥 Clienti")
    editable = role in ["Admin","Operatore"]
    list_tab, new_tab, edit_tab = st.tabs(["📄 Elenco", "➕ Nuovo", "✏️ Modifica / ❌ Elimina"])

    # Elenco
    with list_tab:
        q = st.text_input("Cerca (ragione sociale / città / telefono / P.IVA / SDI)")
        df = clienti.copy()
        if q:
            ql = q.lower()
            cols = ["RagioneSociale","Città","Telefono","PartitaIVA","SDI"]
            df = df[df.fillna("").apply(lambda r: any(ql in str(r[c]).lower() for c in cols), axis=1)]
        st.dataframe(df[["ClienteID","RagioneSociale","Città","Telefono","PartitaIVA","SDI"]]
                     .sort_values("RagioneSociale"),
                     use_container_width=True, height=380)

    # Nuovo cliente
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
                pr = st.text_input("Prossimo Recall (dd/mm/aaaa)")
                uv = st.text_input("Ultima Visita (dd/mm/aaaa)")
                pv = st.text_input("Prossima Visita (dd/mm/aaaa)")
            submitted = st.form_submit_button("Crea", disabled=not editable)
            if submitted:
                errs = []
                if not rs: errs.append("Ragione sociale obbligatoria.")
                if not valid_cap(cap): errs.append("CAP non valido (5 cifre).")
                if not valid_piva(piva): errs.append("Partita IVA non valida (11 cifre).")
                if not valid_iban_it(iban): errs.append("IBAN IT non valido (27 caratteri, inizia con IT).")
                if not valid_sdi(sdi): errs.append("SDI non valido (7 alfanumerico o 0000000).")
                ur_d, pr_d, uv_d, pv_d = parse_date_str(ur), parse_date_str(pr), parse_date_str(uv), parse_date_str(pv)
                if ur and not ur_d: errs.append("Formato data Ultimo Recall non valido (dd/mm/aaaa).")
                if pr and not pr_d: errs.append("Formato data Prossimo Recall non valido (dd/mm/aaaa).")
                if uv and not uv_d: errs.append("Formato data Ultima Visita non valido (dd/mm/aaaa).")
                if pv and not pv_d: errs.append("Formato data Prossima Visita non valido (dd/mm/aaaa).")
                if errs:
                    for e in errs: st.toast(e, icon="⚠️")
                else:
                    next_id = int((clienti["ClienteID"].max() or 0) + 1)
                    new_row = {
                        "ClienteID": next_id, "RagioneSociale": rs, "NomeCliente": contatto,
                        "Indirizzo": indirizzo, "Città": citta, "CAP": cap, "Telefono": tel,
                        "Email": email, "PartitaIVA": piva, "IBAN": iban, "SDI": sdi,
                        "UltimoRecall": fmt_date(ur_d), "ProssimoRecall": fmt_date(pr_d),
                        "UltimaVisita": fmt_date(uv_d), "ProssimaVisita": fmt_date(pv_d),
                        "Note": note
                    }
                    st.session_state["clienti"] = pd.concat([clienti, pd.DataFrame([new_row])], ignore_index=True)
                    st.toast("Cliente creato. Ricordati di salvare nelle Impostazioni.", icon="✅")

    # Modifica / Elimina cliente
    with edit_tab:
        if len(clienti)==0:
            st.info("Nessun cliente.")
        else:
            edit_id = st.number_input("ClienteID", min_value=int(clienti["ClienteID"].min()),
                                      max_value=int(clienti["ClienteID"].max()), step=1,
                                      value=int(clienti["ClienteID"].min()))
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
                        ur = st.text_input("Ultimo Recall (dd/mm/aaaa)", value=row["UltimoRecall"] or "")
                        pr = st.text_input("Prossimo Recall (dd/mm/aaaa)", value=row["ProssimoRecall"] or "")
                        uv = st.text_input("Ultima Visita (dd/mm/aaaa)", value=row["UltimaVisita"] or "")
                        pv = st.text_input("Prossima Visita (dd/mm/aaaa)", value=row["ProssimaVisita"] or "")
                    c1, c2 = st.columns(2)
                    save_btn = c1.form_submit_button("Salva modifiche", disabled=not editable)
                    del_btn = c2.form_submit_button("Elimina cliente", disabled=not editable)
                    if save_btn:
                        errs = []
                        if not rs: errs.append("Ragione sociale obbligatoria.")
                        if not valid_cap(cap): errs.append("CAP non valido (5 cifre).")
                        if not valid_piva(piva): errs.append("Partita IVA non valida (11 cifre).")
                        if not valid_iban_it(iban): errs.append("IBAN IT non valido (27 caratteri, inizia con IT).")
                        if not valid_sdi(sdi): errs.append("SDI non valido (7 alfanumerico o 0000000).")
                        ur_d, pr_d, uv_d, pv_d = parse_date_str(ur), parse_date_str(pr), parse_date_str(uv), parse_date_str(pv)
                        if ur and not ur_d: errs.append("Formato data Ultimo Recall non valido.")
                        if pr and not pr_d: errs.append("Formato data Prossimo Recall non valido.")
                        if uv and not uv_d: errs.append("Formato data Ultima Visita non valido.")
                        if pv and not pv_d: errs.append("Formato data Prossima Visita non valido.")
                        if errs:
                            for e in errs: st.toast(e, icon="⚠️")
                        else:
                            idx = clienti[clienti["ClienteID"] == int(edit_id)].index
                            if len(idx):
                                st.session_state["clienti"].loc[idx, EXPECTED_CLIENTI_COLS] = [
                                    edit_id, rs, contatto, indirizzo, citta, cap, tel, email, piva, iban, sdi,
                                    fmt_date(ur_d), fmt_date(pr_d), fmt_date(uv_d), fmt_date(pv_d), note
                                ]
                                st.toast("Dati cliente aggiornati. Ricordati di salvare.", icon="✅")
                    if del_btn:
                        if (contratti["ClienteID"] == int(edit_id)).any():
                            st.toast("Impossibile eliminare: esistono contratti associati.", icon="⚠️")
                        else:
                            st.session_state["clienti"] = clienti[clienti["ClienteID"] != int(edit_id)]
                            st.toast("Cliente eliminato. Ricordati di salvare.", icon="✅")


# =========================
# CONTRATTI / IMPOSTAZIONI (identiche all’originale)
# =========================
# (puoi mantenere le funzioni render_contratti e render_settings identiche al tuo file attuale)


# =========================
# MAIN
# =========================
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
if page == "Dashboard":
    render_dashboard(st.session_state["clienti"], st.session_state["contratti"])
elif page == "Clienti":
    render_clienti(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
elif page == "Contratti":
    render_contratti(st.session_state["clienti"], st.session_state["contratti"], role)
else:
    render_settings(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
