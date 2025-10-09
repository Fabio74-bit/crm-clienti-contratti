
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

st.set_page_config(page_title="CRM Clienti & Contratti — v3", layout="wide")
# ---- HOTFIX for missing columns from old CSV/session ----
EXPECTED_CLIENTI_COLS = ["ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]

def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df

# call this right after we pull from session/loaders

# =========================
# Helpers & Config
# =========================
DATE_FMT = "%d/%m/%Y"  # dd/mm/aaaa

def fmt_date(d):
    if pd.isna(d) or d is None or d == "":
        return ""
    if isinstance(d, str):
        # Try parse in many formats
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
    # returns date or None
    if not s:
        return None
    s = s.strip()
    for f in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"]:
        try:
            return datetime.strptime(s, f).date()
        except Exception:
            pass
    return None

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

def euro(x):
    try:
        v = float(x)
    except Exception:
        return "-"
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    return f"€ {s}"

# Validation masks (basic)
def valid_cap(s):  # Italian CAP: 5 digits
    return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s):  # Partita IVA: 11 digits
    return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):  # very basic: starts IT and 27 chars alnum
    ss = (s or "").replace(" ", "").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):  # Codice destinatario (SDI): 7 alfanumerico (o 0000000)
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

# Progressive number for quotes: PRE-YYYY-0001
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
    # clienti extended schema
    cli_cols = ["ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]
    clienti = load_csv_with_fallback("clienti.csv", ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    for c in cli_cols:
        if c not in clienti.columns:
            clienti[c] = None
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")
    clienti = clienti[cli_cols]

    ctr_cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    contratti = load_csv_with_fallback("contratti.csv", ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    for c in ctr_cols:
        if c not in contratti.columns:
            contratti[c] = None
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    # store dates as strings dd/mm/yyyy for display
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = pd.to_numeric(contratti[col], errors="coerce")
    contratti = contratti[ctr_cols]

    # quotes registry (simple CSV)
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
# Auth (simple)
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
# Attachments storage (session; for persistence use DB/object storage in prod)
# =========================
if "attachments" not in st.session_state:
    st.session_state["attachments"] = {}  # {ClienteID: [(name, bytes), ...]}

# =========================
# UI Pages
# =========================
def sidebar(role):
    st.sidebar.title("CRM")
    st.sidebar.caption("v3 • validazioni, allegati, preventivi, Excel/print")
    return st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti","Impostazioni"])

def monthly_revenue_open(contratti: pd.DataFrame) -> float:
    df = contratti.copy()
    return float(df[df["Stato"].fillna("").str.lower()=="aperto"]["TotRata"].fillna(0).sum())

def render_dashboard(clienti, contratti):
    st.title("📊 Dashboard")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Clienti", len(clienti))
    c2.metric("Contratti", len(contratti))
    c3.metric("Aperti", int((contratti["Stato"].fillna("").str.lower()=="aperto").sum()))
    c4.metric("Rata mensile (aperti)", euro(monthly_revenue_open(contratti)))
    st.subheader("Prossimi promemoria")
    rem = clienti[["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]].copy()
    st.dataframe(rem, use_container_width=True)

def render_clienti(clienti, contratti, preventivi, role):
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
        st.dataframe(df[["ClienteID","RagioneSociale","Città","Telefono","PartitaIVA","SDI"]].sort_values("RagioneSociale"), use_container_width=True, height=380)

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
                # parse dates
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

    with edit_tab:
        if len(clienti)==0:
            st.info("Nessun cliente.")
        else:
            edit_id = st.number_input("ClienteID", min_value=int(clienti["ClienteID"].min()), max_value=int(clienti["ClienteID"].max()), step=1, value=int(clienti["ClienteID"].min()))
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
                        if ur and not ur_d: errs.append("Formato data Ultimo Recall non valido (dd/mm/aaaa).")
                        if pr and not pr_d: errs.append("Formato data Prossimo Recall non valido (dd/mm/aaaa).")
                        if uv and not uv_d: errs.append("Formato data Ultima Visita non valido (dd/mm/aaaa).")
                        if pv and not pv_d: errs.append("Formato data Prossima Visita non valido (dd/mm/aaaa).")
                        if errs:
                            for e in errs: st.toast(e, icon="⚠️")
                        else:
                            idx = clienti[clienti["ClienteID"] == int(edit_id)].index
                            if len(idx):
                                st.session_state["clienti"].loc[idx, ["RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]] =                                     [rs,contatto,indirizzo,citta,cap,tel,email,piva,iban,sdi,fmt_date(ur_d),fmt_date(pr_d),fmt_date(uv_d),fmt_date(pv_d),note]
                                st.toast("Dati cliente aggiornati. Ricordati di salvare.", icon="✅")
                    if del_btn:
                        if (contratti["ClienteID"] == int(edit_id)).any():
                            st.toast("Impossibile eliminare: esistono contratti associati.", icon="⚠️")
                        else:
                            st.session_state["clienti"] = clienti[clienti["ClienteID"] != int(edit_id)]
                            st.toast("Cliente eliminato. Ricordati di salvare.", icon="✅")

    # Quick card + Scheda cliente completa
    st.divider()
    st.subheader("📄 Scheda cliente")
    if len(clienti)>0:
        det_id = st.number_input("Apri scheda ClienteID", min_value=int(clienti["ClienteID"].min()), max_value=int(clienti["ClienteID"].max()), step=1, value=int(clienti["ClienteID"].min()), key="open_client")
        dettaglio = clienti[clienti["ClienteID"] == int(det_id)]
        if not dettaglio.empty:
            c = dettaglio.iloc[0]
            left, right = st.columns([2,1])
            with left:
                st.markdown(f"### {c['RagioneSociale']}")
                st.caption(f"{c['Città'] or ''} · 📞 {c['Telefono'] or '-'} · 📧 {c['Email'] or '-'}")
                st.write("**P.IVA:**", c["PartitaIVA"] or "-"," | **IBAN:**", c["IBAN"] or "-"," | **SDI:**", c["SDI"] or "-")
                st.write("**Note:**")
                st.info(c["Note"] or "-")
            with right:
                ct = contratti[contratti["ClienteID"] == int(det_id)].copy()
                st.metric("Contratti", len(ct))
                st.metric("Aperti", int((ct["Stato"].fillna('').str.lower()=="aperto").sum()))
                st.metric("Rata mensile (aperti)", euro(ct[ct["Stato"].fillna('').str.lower()=="aperto"]["TotRata"].fillna(0).sum()))

            # --- Contratti table with red rows for closed
            st.write("### Contratti (rosso = chiusi)")
            ct = contratti[contratti["ClienteID"] == int(det_id)].copy()
            # Build HTML table with row classes
            def row_html(row):
                cls = "row " + status_class(row.get("Stato",""))
                cells = "".join([f"<td>{row.get(col,'')}</td>" for col in ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]])
                return f"<tr class='{cls}'>{cells}</tr>"
            header = "<tr>" + "".join([f"<th>{h}</th>" for h in ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]]) + "</tr>"
            rows = "\n".join([row_html(r) for _,r in ct.iterrows()])
            st.markdown("""
<style>
.table-ctr table {border-collapse: collapse; width: 100%;}
.table-ctr th, .table-ctr td {border:1px solid #e5e7eb; padding:6px 8px; font-size:14px;}
.table-ctr tr.closed {background: #fee2e2;}  /* RED for closed */
.table-ctr tr.open {background: #ecfdf5;}    /* GREEN-ish */
.table-ctr tr.suspended {background: #ffedd5;} /* amber */
.table-ctr tr.unknown {}
.print-header {text-align:center; font-weight:700; font-size:18px; margin-bottom:8px;}
@media print {.no-print {display:none;} .print-only {display:block;}}
@media screen {.print-only {display:none;}}
</style>
""", unsafe_allow_html=True)
            st.markdown(f"<div class='table-ctr'><table>{header}{rows}</table></div>", unsafe_allow_html=True)

            editable = role in ["Admin","Operatore"]
            if editable:
                st.write("#### ➕ Aggiungi / ✏️ Modifica / ❌ Elimina contratto")
                with st.form("edit_add_contract_v3"):
                    col1, col2, col3 = st.columns(3)
                    num = col1.text_input("Numero contratto *")
                    d_in = col2.text_input("Data inizio (dd/mm/aaaa)", value="")
                    d_fin = col3.text_input("Data fine (dd/mm/aaaa)", value="")
                    durata = st.text_input("Durata (es. '12 mesi')", value="")
                    desc = st.text_input("Descrizione prodotto", value="")
                    nol_fin = st.number_input("NOL. FIN.", min_value=0.0, step=1.0, value=0.0)
                    nol_int = st.number_input("NOL. INT.", min_value=0.0, step=1.0, value=0.0)
                    tot = st.number_input("TOT. RATA", min_value=0.0, step=1.0, value=0.0)
                    stato = st.selectbox("Stato", ["Aperto","Chiuso","Sospeso"], index=0)
                    cA, cB, cC = st.columns(3)
                    add_btn = cA.form_submit_button("Aggiungi")
                    upd_btn = cB.form_submit_button("Aggiorna (match su Numero contratto)")
                    del_btn = cC.form_submit_button("Elimina (match su Numero contratto)")

                    if add_btn:
                        # validate
                        errs = []
                        if not num: errs.append("Numero contratto obbligatorio.")
                        if not parse_date_str(d_in): errs.append("Data inizio non valida (dd/mm/aaaa).")
                        if d_fin and not parse_date_str(d_fin): errs.append("Data fine non valida (dd/mm/aaaa).")
                        if contratti[(contratti["ClienteID"]==int(det_id)) & (contratti["NumeroContratto"]==num)].any().any():
                            errs.append("Numero contratto già esistente per questo cliente.")
                        if errs: 
                            for e in errs: st.toast(e, icon="⚠️")
                        else:
                            new_row = {
                                "ClienteID": int(det_id), "NumeroContratto": num,
                                "DataInizio": fmt_date(parse_date_str(d_in)),
                                "DataFine": fmt_date(parse_date_str(d_fin)),
                                "Durata": durata, "DescrizioneProdotto": desc,
                                "NOL_FIN": float(nol_fin), "NOL_INT": float(nol_int), "TotRata": float(tot),
                                "Stato": stato
                            }
                            st.session_state["contratti"] = pd.concat([contratti, pd.DataFrame([new_row])], ignore_index=True)
                            st.toast("Contratto aggiunto. Ricordati di salvare.", icon="✅")
                    if upd_btn:
                        idx = contratti[(contratti["ClienteID"]==int(det_id)) & (contratti["NumeroContratto"]==num)].index
                        if len(idx)==0:
                            st.toast("Nessun contratto con quel numero per questo cliente.", icon="⚠️")
                        else:
                            st.session_state["contratti"].loc[idx, ["DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]] =                                 [fmt_date(parse_date_str(d_in)), fmt_date(parse_date_str(d_fin)), durata, desc, float(nol_fin), float(nol_int), float(tot), stato]
                            st.toast("Contratto aggiornato. Ricordati di salvare.", icon="✅")
                    if del_btn:
                        idx = contratti[(contratti["ClienteID"]==int(det_id)) & (contratti["NumeroContratto"]==num)].index
                        if len(idx)==0:
                            st.toast("Nessun contratto con quel numero per questo cliente.", icon="⚠️")
                        else:
                            st.session_state["contratti"] = contratti.drop(index=idx)
                            st.toast("Contratto eliminato. Ricordati di salvare.", icon="✅")

                # Close selected contract quickly
                with st.form("close_contract_quick"):
                    num_close = st.text_input("Chiudi contratto (inserisci Numero contratto)")
                    close_btn = st.form_submit_button("Chiudi ora → stato 'Chiuso' e DataFine = oggi")
                    if close_btn:
                        idx = contratti[(contratti["ClienteID"]==int(det_id)) & (contratti["NumeroContratto"]==num_close)].index
                        if len(idx)==0:
                            st.toast("Numero contratto non trovato.", icon="⚠️")
                        else:
                            today = fmt_date(date.today())
                            st.session_state["contratti"].loc[idx, ["Stato","DataFine"]] = ["Chiuso", today]
                            st.toast("Contratto chiuso (e riga sarà rossa). Ricordati di salvare.", icon="✅")

            # --- Export contracts (Excel open/download)
            st.write("#### Esporta contratti (solo tabella)")
            export_df = contratti[contratti["ClienteID"] == int(det_id)].copy()
            # selection for print/export
            sel_nums = st.multiselect("Seleziona N. contratti da esportare/stampare (vuoto = tutti)", export_df["NumeroContratto"].tolist())
            if sel_nums:
                export_df = export_df[export_df["NumeroContratto"].isin(sel_nums)]
            # Excel download
            out = BytesIO()
            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                export_df.to_excel(writer, index=False, sheet_name="Contratti")
            st.download_button("⬇️ Scarica Excel dei contratti", data=out.getvalue(), file_name=f"contratti_{int(det_id)}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # Print-friendly HTML with client name centered
            html_rows = "".join([
                f"<tr><td>{r['NumeroContratto']}</td><td>{r['DataInizio']}</td><td>{r['DataFine']}</td><td>{r['Durata']}</td><td>{r['DescrizioneProdotto']}</td><td>{euro(r['NOL_FIN'])}</td><td>{euro(r['NOL_INT'])}</td><td>{euro(r['TotRata'])}</td><td>{r['Stato']}</td></tr>"
                for _,r in export_df.iterrows()
            ])
            printable = f"""
            <div class='print-header'>{c['RagioneSociale']}</div>
            <table border='1' cellspacing='0' cellpadding='6' style='width:100%;border-collapse:collapse;font-size:14px'>
                <tr><th>Numero</th><th>Inizio</th><th>Fine</th><th>Durata</th><th>Descrizione</th><th>NOL_FIN</th><th>NOL_INT</th><th>TOT RATA</th><th>Stato</th></tr>
                {html_rows}
            </table>
            <script>
                window.onload = function() {{ window.print(); }}
            </script>
            """
            if st.button("🖨️ Stampa contratti selezionati"):
                st.components.v1.html(printable, height=600, scrolling=True)

            # --- Attachments
            st.write("#### 📎 Allegati cliente")
            up = st.file_uploader("Carica allegati (PDF/IMG/Doc)", accept_multiple_files=True)
            if up:
                al = st.session_state["attachments"].get(int(det_id), [])
                for f in up:
                    al.append((f.name, f.read()))
                st.session_state["attachments"][int(det_id)] = al
                st.toast(f"{len(up)} allegati aggiunti (non persistono senza DB).", icon="✅")
            al = st.session_state["attachments"].get(int(det_id), [])
            if al:
                for i,(name, data) in enumerate(al):
                    st.download_button(f"Scarica {name}", data=data, file_name=name)

            # --- Preventivi (quotes) with templates
            st.write("#### 🧾 Preventivi (Word)")
            # Templates upload in settings; here just list and generate
            templates = st.session_state.get("quote_templates", [])
            if templates:
                tnames = [t[0] for t in templates]
                tsel = st.selectbox("Scegli template", tnames)
                gen = st.button("Crea preventivo da template")
                if gen:
                    # generate progressive number and fill basic placeholders
                    numero = next_quote_number(preventivi)
                    # Try python-docx
                    try:
                        from docx import Document  # requires python-docx in requirements
                        tdata = dict(templates)[tsel]
                        bio = BytesIO(tdata)
                        doc = Document(bio)
                        # replace placeholders in paragraphs (simple)
                        for p in doc.paragraphs:
                            if "{{" in p.text:
                                p.text = p.text.replace("{{NUMERO}}", numero).replace("{{CLIENTE}}", str(c["RagioneSociale"])).replace("{{DATA}}", fmt_date(date.today()))
                        # tables cell replace
                        for tbl in doc.tables:
                            for row in tbl.rows:
                                for cell in row.cells:
                                    if "{{" in cell.text:
                                        cell.text = cell.text.replace("{{NUMERO}}", numero).replace("{{CLIENTE}}", str(c["RagioneSociale"])).replace("{{DATA}}", fmt_date(date.today()))
                        out_doc = BytesIO()
                        fname = f"Preventivo_{numero}.docx"
                        doc.save(out_doc)
                        # save registry row
                        new_q = {"ClienteID": int(det_id), "Numero": numero, "Data": fmt_date(date.today()), "Template": tsel, "FileName": fname}
                        st.session_state["preventivi"] = pd.concat([preventivi, pd.DataFrame([new_q])], ignore_index=True)
                        st.download_button("⬇️ Scarica preventivo (Word)", data=out_doc.getvalue(), file_name=fname, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                        st.toast("Preventivo generato. (Per apertura automatica Word, scaricare il file.)", icon="✅")
                    except Exception as e:
                        st.error("Per i preventivi Word serve aggiungere 'python-docx' a requirements.txt.")
            else:
                st.info("Carica i 4 template .docx nella pagina Impostazioni per abilitare i preventivi. Usa segnaposto {{NUMERO}}, {{CLIENTE}}, {{DATA}}.")

def render_contratti(clienti, contratti, role):
    st.title("📃 Contratti")
    name_map = dict(zip(clienti["ClienteID"], clienti["RagioneSociale"]))
    df = contratti.copy()
    df["Cliente"] = df["ClienteID"].map(name_map)

    c1,c2,c3,c4 = st.columns(4)
    f_cliente = c1.selectbox("Cliente", ["(tutti)"] + sorted([n for n in df["Cliente"].dropna().unique()]))
    f_stato = c2.selectbox("Stato", ["(tutti)","Aperto","Chiuso","Sospeso"])
    f_anno = c3.number_input("Anno inizio (0 = tutti)", min_value=0, step=1, value=0)
    export = c4.button("⬇️ Esporta CSV (filtrato)")

    if f_cliente != "(tutti)":
        df = df[df["Cliente"] == f_cliente]
    if f_stato != "(tutti)":
        df = df[df["Stato"].fillna("") == f_stato]
    if f_anno:
        def year_of(s): 
            d = parse_date_str(s)
            return d.year if d else None
        df = df[df["DataInizio"].apply(lambda x: year_of(x)==f_anno)]

    st.write(df.assign(_st=df["Stato"].apply(status_chip)).drop(columns=["Stato"]).rename(columns={"_st":"Stato"}).to_html(escape=False, index=False), unsafe_allow_html=True)
    if export:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Scarica contratti filtrati (CSV)", data=csv, file_name="contratti_filtrati.csv", mime="text/csv")

def render_settings(clienti, contratti, preventivi, role):
    st.title("⚙️ Impostazioni & Salvataggio")
    c1,c2,c3 = st.columns(3)
    if c1.button("💾 Salva clienti.csv", disabled=role=="Viewer"):
        save_csv(clienti, "clienti.csv")
        st.toast("clienti.csv salvato.", icon="✅")
    if c2.button("💾 Salva contratti.csv", disabled=role=="Viewer"):
        save_csv(contratti, "contratti.csv")
        st.toast("contratti.csv salvato.", icon="✅")
    if c3.button("💾 Salva preventivi.csv", disabled=role=="Viewer"):
        df = st.session_state.get("preventivi", preventivi)
        save_csv(df, "preventivi.csv")
        st.toast("preventivi.csv salvato.", icon="✅")

    st.write("---")
    st.write("Carica CSV aggiornati:")
    colA, colB, colC = st.columns(3)
    uc = colA.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None and role != "Viewer":
        st.session_state["clienti"] = pd.read_csv(uc)
        st.toast("Clienti caricati (ricordati di salvare).", icon="✅")
    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None and role != "Viewer":
        tmp = pd.read_csv(ut)
        # normalize date strings to dd/mm/yyyy
        tmp["DataInizio"] = tmp["DataInizio"].apply(fmt_date)
        tmp["DataFine"] = tmp["DataFine"].apply(fmt_date)
        for col in ["NOL_FIN","NOL_INT","TotRata"]:
            if col in tmp.columns:
                tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        st.session_state["contratti"] = tmp
        st.toast("Contratti caricati (ricordati di salvare).", icon="✅")

    # Quote templates upload
    st.subheader("📄 Template preventivi (Word .docx)")
    tpls = st.file_uploader("Carica i 4 template (.docx) con segnaposto {{NUMERO}}, {{CLIENTE}}, {{DATA}}", type=["docx"], accept_multiple_files=True)
    if tpls:
        st.session_state["quote_templates"] = [(f.name, f.read()) for f in tpls]
        st.toast(f"{len(tpls)} template caricati (non persistono senza storage).", icon="✅")

# =========================
# Main
# =========================
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
if page == "Dashboard":
    render_dashboard(st.session_state["clienti"], st.session_state["contratti"])
elif page == "Clienti":
    render_clienti(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
elif page == "Contratti":
    render_contratti(st.session_state["clienti"], st.session_state["contratti"], role)
else:
    render_settings(st.session_state["clienti"], st.session_state["contratti"], st.session_state["preventivi"], role)
