
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

st.set_page_config(page_title="CRM Clienti & Contratti — v3 FIX9 (CRUD)", layout="wide")

# =========================
# Helpers
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

def numify(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return 0.0
    s = s.replace("€", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0

def euro(x):
    v = numify(x)
    if v == 0: return ""
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"

def status_class(s):
    s = str(s or "").strip().lower()
    if s == "chiuso": return "closed"
    if s == "aperto": return "open"
    if s == "sospeso": return "suspended"
    return "unknown"

EXPECTED_CLIENTI_COLS = ["ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]

def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df)==0:
        return pd.DataFrame(columns=EXPECTED_CLIENTI_COLS)
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns: df[c] = None
    return df

def compute_tot(row):
    return round(numify(row.get("NOL_FIN")) + numify(row.get("NOL_INT")), 2)

def valid_cap(s):  return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ", "").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

def next_contract_number(df_ct, cid):
    yy = date.today().strftime("%Y")
    prefix = f"CTR-{cid}-{yy}-"
    if df_ct.empty or "NumeroContratto" not in df_ct.columns:
        return prefix + "0001"
    mask = df_ct["NumeroContratto"].fillna("").astype(str).str.startswith(prefix)
    if not mask.any(): return prefix + "0001"
    last = sorted(df_ct.loc[mask, "NumeroContratto"].astype(str))[-1]
    n = int(last.split("-")[-1])
    return f"{prefix}{n+1:04d}"

@st.cache_data
def load_csv_with_fallback(main_path, fallbacks):
    p = Path(main_path)
    if p.exists(): return pd.read_csv(p)
    for fb in fallbacks:
        if Path(fb).exists():
            return pd.read_csv(fb)
    return pd.DataFrame()

@st.cache_data
def load_data():
    clienti = load_csv_with_fallback("clienti.csv", ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    clienti = ensure_clienti_cols(clienti)
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")
    clienti = clienti[EXPECTED_CLIENTI_COLS]

    ctr_cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    contratti = load_csv_with_fallback("contratti.csv", ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    for c in ctr_cols:
        if c not in contratti.columns: contratti[c] = None
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    for dcol in ["DataInizio","DataFine"]:
        if dcol in contratti.columns:
            contratti[dcol] = contratti[dcol].apply(fmt_date)
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = contratti[col].apply(numify)
    contratti["TotRataCalc"] = contratti.apply(compute_tot, axis=1)
    diff = (contratti["TotRata"] - contratti["TotRataCalc"]).abs().fillna(0)
    contratti.loc[(contratti["TotRata"].isna()) | (diff > 0.01), "TotRata"] = contratti["TotRataCalc"]
    contratti["Stato"] = contratti["Stato"].astype(str).replace({"nan":""})
    contratti = contratti[ctr_cols]
    return clienti, contratti

def save_csv(df, path):
    df.to_csv(path, index=False)

USERS = {"admin":{"password":"admin","role":"Admin"},
         "op":{"password":"op","role":"Operatore"},
         "view":{"password":"view","role":"Viewer"}}

def do_login():
    st.title("Accesso CRM")
    u = st.text_input("Utente", value="admin")
    p = st.text_input("Password", type="password", value="admin")
    if st.button("Entra"):
        if u in USERS and USERS[u]["password"]==p:
            st.session_state["auth_user"]=u; st.session_state["auth_role"]=USERS[u]["role"]; st.rerun()
        else:
            st.error("Credenziali non valide.")

if "auth_user" not in st.session_state:
    do_login(); st.stop()
role = st.session_state.get("auth_role","Viewer")
editable = role in ["Admin","Operatore"]

clienti, contratti = load_data()
st.session_state.setdefault("clienti", clienti.copy())
st.session_state.setdefault("contratti", contratti.copy())

st.sidebar.title("CRM")
page = st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti","Impostazioni"])

def monthly_revenue_open_client(contratti, cid):
    df = contratti[(contratti["ClienteID"]==int(cid)) & (contratti["Stato"].str.lower()=="aperto")]
    return float(df["TotRata"].sum())

def monthly_revenue_all_client(contratti, cid):
    df = contratti[contratti["ClienteID"]==int(cid)]
    return float(df["TotRata"].sum())

def monthly_revenue_open_all(contratti):
    df = contratti[contratti["Stato"].str.lower()=="aperto"]
    return float(df["TotRata"].sum())

def render_dashboard():
    st.title("📊 Dashboard")
    c1,c2,c3 = st.columns(3)
    c1.metric("Clienti", len(st.session_state["clienti"]))
    c2.metric("Contratti", len(st.session_state["contratti"]))
    c3.metric("Rata mensile (aperti)", euro(monthly_revenue_open_all(st.session_state["contratti"])))
    st.subheader("Promemoria (prossimo recall/visita)")
    cli = ensure_clienti_cols(st.session_state["clienti"])
    rem = cli[["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]].copy()
    st.dataframe(rem, use_container_width=True)

def render_clienti():
    clienti = ensure_clienti_cols(st.session_state["clienti"])
    contratti = st.session_state["contratti"]

    st.title("👥 Clienti")

    with st.expander("➕ Aggiungi cliente", expanded=False):
        with st.form("form_add_cliente"):
            col1,col2,col3 = st.columns(3)
            with col1:
                new_id = st.number_input("ClienteID (nuovo)", min_value=1, step=1)
                rs = st.text_input("Ragione Sociale *")
                nome = st.text_input("Persona di riferimento")
                ind = st.text_input("Indirizzo")
            with col2:
                citta = st.text_input("Città")
                cap = st.text_input("CAP")
                tel = st.text_input("Telefono")
                mail = st.text_input("Email")
            with col3:
                piva = st.text_input("Partita IVA")
                iban = st.text_input("IBAN")
                sdi = st.text_input("SDI")
                note = st.text_area("Note")
            ok = st.form_submit_button("Crea", disabled=not editable)
            if ok:
                if (cap and not valid_cap(cap)): st.error("CAP non valido (5 cifre)."); st.stop()
                if (piva and not valid_piva(piva)): st.error("P.IVA non valida (11 cifre)."); st.stop()
                if (iban and not valid_iban_it(iban)): st.error("IBAN IT non valido."); st.stop()
                if (sdi and not valid_sdi(sdi)): st.error("SDI non valido (7 char o 0000000)."); st.stop()
                if rs.strip()=="":
                    st.error("Ragione Sociale obbligatoria."); st.stop()
                if int(new_id) in clienti["ClienteID"].astype(int).tolist():
                    st.error("ClienteID già esistente."); st.stop()
                row = {
                    "ClienteID": int(new_id),"RagioneSociale": rs,"NomeCliente": nome,"Indirizzo": ind,"Città": citta,
                    "CAP": cap,"Telefono": tel,"Email": mail,"PartitaIVA": piva,"IBAN": iban,"SDI": sdi,
                    "UltimoRecall": "","ProssimoRecall": "","UltimaVisita": "","ProssimaVisita": "","Note": note
                }
                st.session_state["clienti"] = pd.concat([clienti, pd.DataFrame([row])], ignore_index=True)
                st.success("Cliente creato. Ricorda di salvare in Impostazioni.")

    with st.expander("🗑️ Elimina cliente", expanded=False):
        ids = clienti["ClienteID"].astype(int).tolist()
        del_id = st.selectbox("Seleziona ClienteID da eliminare", ids) if ids else None
        if st.button("Elimina definitivamente", disabled=(not editable or del_id is None)):
            st.session_state["clienti"] = clienti[clienti["ClienteID"].astype(int)!=int(del_id)]
            st.session_state["contratti"] = contratti[contratti["ClienteID"].astype(int)!=int(del_id)]
            st.warning("Cliente e relativi contratti eliminati. Ricorda di salvare.")

    if len(clienti)==0:
        st.info("Nessun cliente presente."); return

    det_id = st.number_input("Apri scheda ClienteID", min_value=int(clienti["ClienteID"].min()), max_value=int(clienti["ClienteID"].max()), step=1, value=int(clienti["ClienteID"].min()))
    dettaglio = clienti[clienti["ClienteID"] == int(det_id)]
    if dettaglio.empty:
        st.info("Cliente non trovato."); return
    c = dettaglio.iloc[0]

    st.markdown(f"### {c['RagioneSociale']}")
    a1,a2 = st.columns(2)
    with a1:
        st.write(f"**Persona di riferimento:** {c['NomeCliente'] or ''}")
        st.write(f"**Indirizzo:** {c['Indirizzo'] or ''}")
        st.write(f"**Città:** {c['Città'] or ''}  **CAP:** {c['CAP'] or ''}")
        st.write(f"**Telefono:** {c['Telefono'] or ''}")
        st.write(f"**Email:** {c['Email'] or ''}")
    with a2:
        st.write(f"**Partita IVA:** {c['PartitaIVA'] or ''}")
        st.write(f"**IBAN:** {c['IBAN'] or ''}")
        st.write(f"**SDI:** {c['SDI'] or ''}")
        st.write(f"**Ultimo Recall:** {c['UltimoRecall'] or ''}")
        st.write(f"**Prossimo Recall:** {c['ProssimoRecall'] or ''}")
        st.write(f"**Ultima Visita:** {c['UltimaVisita'] or ''}")
        st.write(f"**Prossima Visita:** {c['ProssimaVisita'] or ''}")
    if (c["Note"] or "") != "":
        st.info(c["Note"])

    ct = st.session_state["contratti"]
    ct_cli = ct[ct["ClienteID"]==int(det_id)]
    m1,m2,m3 = st.columns(3)
    m1.metric("Contratti", len(ct_cli))
    m2.metric("Rata mensile (Tutti)", euro(monthly_revenue_all_client(ct, det_id)))
    m3.metric("Rata mensile (Aperti)", euro(monthly_revenue_open_client(ct, det_id)))

    st.write("### Contratti (rosso = chiusi)")
    df = ct_cli.copy().fillna("")
    df["NOL_FIN"] = df["NOL_FIN"].apply(euro)
    df["NOL_INT"] = df["NOL_INT"].apply(euro)
    df["TotRata"] = df["TotRata"].apply(euro)
    show = df[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]]
    st.dataframe(show, use_container_width=True)

    with st.expander("➕ Aggiungi contratto", expanded=False):
        with st.form("form_add_ctr"):
            col1,col2,col3 = st.columns(3)
            with col1:
                numero = st.text_input("Numero contratto", value=next_contract_number(ct_cli, int(det_id)))
                d_in = st.date_input("Data inizio", value=date.today())
                d_fi = st.date_input("Data fine", value=date.today())
                durata = st.text_input("Durata (es. 60 M)")
            with col2:
                descr = st.text_input("Descrizione prodotto")
                fin = st.text_input("NOL_FIN", value="0")
                intr = st.text_input("NOL_INT", value="0")
                stato = st.selectbox("Stato", ["aperto","chiuso","sospeso"], index=0)
            with col3:
                tot_auto = st.checkbox("TotRata = FIN + INT", value=True)
                tot = st.text_input("TotRata (se non auto)", value="0")
            ok = st.form_submit_button("Crea", disabled=not editable)
            if ok:
                tot_val = compute_tot({"NOL_FIN":fin,"NOL_INT":intr}) if tot_auto else numify(tot)
                new_row = {
                    "ClienteID": int(det_id),
                    "NumeroContratto": numero.strip(),
                    "DataInizio": fmt_date(d_in),
                    "DataFine": fmt_date(d_fi),
                    "Durata": durata,
                    "DescrizioneProdotto": descr,
                    "NOL_FIN": numify(fin),
                    "NOL_INT": numify(intr),
                    "TotRata": round(tot_val,2),
                    "Stato": stato
                }
                st.session_state["contratti"] = pd.concat([ct, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Contratto creato. Ricorda di salvare in Impostazioni.")

    with st.expander("✏️ Modifica/Chiudi contratto", expanded=False):
        nums = ct_cli["NumeroContratto"].astype(str).tolist()
        target = st.selectbox("Seleziona numero", nums) if len(nums)>0 else None
        if target:
            old = ct_cli[ct_cli["NumeroContratto"].astype(str)==str(target)].iloc[0]
            def parse_date_local(s):
                for f in ["%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%m/%d/%Y"]:
                    try: return datetime.strptime(str(s), f).date()
                    except: pass
                return date.today()
            with st.form("form_edit_ctr"):
                col1,col2,col3 = st.columns(3)
                with col1:
                    d_in = st.date_input("Data inizio", value=parse_date_local(old["DataInizio"]))
                    d_fi = st.date_input("Data fine", value=parse_date_local(old["DataFine"]))
                    durata = st.text_input("Durata", value=str(old["Durata"] or ""))
                with col2:
                    descr = st.text_input("Descrizione", value=str(old["DescrizioneProdotto"] or ""))
                    fin = st.text_input("NOL_FIN", value=str(old["NOL_FIN"]))
                    intr = st.text_input("NOL_INT", value=str(old["NOL_INT"]))
                    stato = st.selectbox("Stato", ["aperto","chiuso","sospeso"], index=["aperto","chiuso","sospeso"].index(str(old["Stato"] or "aperto").lower()))
                with col3:
                    tot_auto = st.checkbox("TotRata = FIN + INT", value=True)
                    tot = st.text_input("TotRata", value=str(old["TotRata"]))
                ok = st.form_submit_button("Aggiorna", disabled=not editable)
                if ok:
                    tot_val = compute_tot({"NOL_FIN":fin,"NOL_INT":intr}) if tot_auto else numify(tot)
                    mask = (ct["ClienteID"].astype(int)==int(det_id)) & (ct["NumeroContratto"].astype(str)==str(target))
                    st.session_state["contratti"].loc[mask, ["DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]] = [
                        fmt_date(d_in), fmt_date(d_fi), durata, descr, numify(fin), numify(intr), round(tot_val,2), stato
                    ]
                    st.success("Contratto aggiornato. Ricorda di salvare.")
        else:
            st.info("Nessun contratto per questo cliente.")

    with st.expander("🗑️ Elimina contratto", expanded=False):
        n2 = ct_cli["NumeroContratto"].astype(str).tolist()
        deln = st.selectbox("Numero contratto da eliminare", n2) if len(n2)>0 else None
        if st.button("Elimina questo contratto", disabled=(not editable or deln is None)):
            mask = ~((ct["ClienteID"].astype(int)==int(det_id)) & (ct["NumeroContratto"].astype(str)==str(deln)))
            st.session_state["contratti"] = ct[mask]
            st.warning("Contratto eliminato. Ricorda di salvare.")

def render_contratti():
    clienti = ensure_clienti_cols(st.session_state["clienti"])
    contratti = st.session_state["contratti"]
    st.title("📃 Contratti per cliente")
    if len(clienti)==0:
        st.info("Nessun cliente caricato."); return
    opts = [(int(cid), nm if pd.notna(nm) else "") for cid,nm in zip(clienti["ClienteID"], clienti["RagioneSociale"])]
    labels = [f"{cid} — {nm}" for cid, nm in opts]
    choice = st.selectbox("Seleziona cliente", ["(seleziona)"] + labels, index=0)
    if choice == "(seleziona)":
        st.info("Seleziona un cliente per vedere i suoi contratti."); return
    try:
        sel_cid = int(str(choice).split(" — ")[0])
    except Exception:
        st.warning("Selezione non valida."); return
    df = contratti[contratti["ClienteID"]==sel_cid].copy().fillna("")
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        df[col] = df[col].apply(euro)
    cols = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    st.dataframe(df[cols], use_container_width=True)

def render_settings():
    st.title("⚙️ Impostazioni & Salvataggio")
    c1,c2 = st.columns(2)
    if c1.button("💾 Salva clienti.csv", disabled=not editable):
        save_csv(st.session_state["clienti"], "clienti.csv"); st.toast("clienti.csv salvato.", icon="✅")
    if c2.button("💾 Salva contratti.csv", disabled=not editable):
        save_csv(st.session_state["contratti"], "contratti.csv"); st.toast("contratti.csv salvato.", icon="✅")
    st.write("---")
    colA, colB = st.columns(2)
    uc = colA.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None and editable:
        tmp = pd.read_csv(uc)
        st.session_state["clienti"] = ensure_clienti_cols(tmp)
        st.toast("Clienti caricati (ricordati di salvare).", icon="✅")
    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None and editable:
        tmp = pd.read_csv(ut)
        if "DataInizio" in tmp.columns: tmp["DataInizio"] = tmp["DataInizio"].apply(fmt_date)
        if "DataFine" in tmp.columns: tmp["DataFine"] = tmp["DataFine"].apply(fmt_date)
        for col in ["NOL_FIN","NOL_INT","TotRata"]:
            if col in tmp.columns: tmp[col] = tmp[col].apply(numify)
        if "NOL_FIN" in tmp.columns and "NOL_INT" in tmp.columns:
            calc = (tmp["NOL_FIN"].apply(numify) + tmp["NOL_INT"].apply(numify)).round(2)
            if "TotRata" in tmp.columns:
                mask = tmp["TotRata"].isna() | (tmp["TotRata"] - calc).abs().fillna(0) > 0.01
                tmp.loc[mask, "TotRata"] = calc
            else:
                tmp["TotRata"] = calc
        if "Stato" in tmp.columns: tmp["Stato"] = tmp["Stato"].astype(str).replace({"nan":""})
        st.session_state["contratti"] = tmp
        st.toast("Contratti caricati (ricordati di salvare).", icon="✅")

if page == "Dashboard":
    render_dashboard()
elif page == "Clienti":
    render_clienti()
elif page == "Contratti":
    render_contratti()
else:
    render_settings()
