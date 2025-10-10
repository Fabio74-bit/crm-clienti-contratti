# app.py — CRM Clienti & Contratti
# v3 FIX13  (CRUD + righe rosse + salva rapido + robust table + fix ClienteID)

import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from pathlib import Path
import re

st.set_page_config(page_title="CRM Clienti & Contratti — v3 FIX13", layout="wide")

# =========================
# Helpers & costanti
# =========================
DATE_FMT = "%d/%m/%Y"

SAFE_CONTRACT_COLS = [
    "NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]
EXPECTED_CLIENTI_COLS = [
    "ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall",
    "UltimaVisita","ProssimaVisita","Note"
]

def fmt_date(d):
    if pd.isna(d) or d is None or d == "": return ""
    if isinstance(d, str):
        for f in ["%Y-%m-%d","%d/%m/%Y","%d-%m-%Y","%m/%d/%Y"]:
            try: return datetime.strptime(d, f).strftime(DATE_FMT)
            except: pass
        return d
    if isinstance(d, (datetime, date)): return d.strftime(DATE_FMT)
    return str(d)

def numify(x):
    if x is None or (isinstance(x, float) and np.isnan(x)): return 0.0
    s = str(x).strip()
    if s == "" or s.lower()=="nan": return 0.0
    s = s.replace("€","").replace(" ","")
    if "," in s and "." in s: s = s.replace(".","").replace(",",".")
    elif "," in s and "." not in s: s = s.replace(",",".")
    try: return float(s)
    except: return 0.0

def euro(x):
    v = numify(x)
    if v == 0: return ""
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {s}"

def compute_tot(row):
    return round(numify(row.get("NOL_FIN")) + numify(row.get("NOL_INT")), 2)

# validazioni anagrafica
def valid_cap(s):  return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ","").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

# numerazione contratti
def next_contract_number(df_ct, cid):
    yy = date.today().strftime("%Y")
    prefix = f"CTR-{cid}-{yy}-"
    if df_ct.empty or "NumeroContratto" not in df_ct.columns: return prefix + "0001"
    mask = df_ct["NumeroContratto"].fillna("").astype(str).str.startswith(prefix)
    if not mask.any(): return prefix + "0001"
    last = sorted(df_ct.loc[mask,"NumeroContratto"].astype(str))[-1]
    n = int(last.split("-")[-1])
    return f"{prefix}{n+1:04d}"

# =========================
# Normalizzazioni tabelle
# =========================
def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(df).copy()
    if df.empty:
        return pd.DataFrame(columns=EXPECTED_CLIENTI_COLS)
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns: df[c] = None
    df["ClienteID"] = pd.to_numeric(df["ClienteID"], errors="coerce").astype("Int64")
    return df[EXPECTED_CLIENTI_COLS]

def sanitize_contracts_df(df) -> pd.DataFrame:
    """Rende la tabella contratti a prova di KeyError; NON contiene ClienteID."""
    df = pd.DataFrame(df).copy()
    for c in SAFE_CONTRACT_COLS:
        if c not in df.columns:
            df[c] = 0.0 if c in ["NOL_FIN","NOL_INT","TotRata"] else ""
    df = df[SAFE_CONTRACT_COLS]
    for c in ["NOL_FIN","NOL_INT","TotRata"]: df[c] = df[c].apply(numify)
    for dcol in ["DataInizio","DataFine"]: df[dcol] = df[dcol].apply(fmt_date)
    df["Stato"] = df["Stato"].astype(str).replace({"nan":""})
    return df

def ensure_contratti_cols(df) -> pd.DataFrame:
    """
    Garantisce la presenza di ClienteID + SAFE_CONTRACT_COLS e li ordina.
    """
    df = pd.DataFrame(df).copy()
    if "ClienteID" not in df.columns:
        df["ClienteID"] = None
    df["ClienteID"] = pd.to_numeric(df["ClienteID"], errors="coerce").astype("Int64")

    # applica la sanitizzazione sulle altre colonne
    core = sanitize_contracts_df(df)
    # unisci ClienteID conservando l'ordine
    out = pd.concat([df[["ClienteID"]].reset_index(drop=True), core.reset_index(drop=True)], axis=1)
    return out[["ClienteID"] + SAFE_CONTRACT_COLS]

# =========================
# Caricamento / Salvataggio
# =========================
@st.cache_data
def load_csv_with_fallback(main_path, fallbacks):
    p = Path(main_path)
    if p.exists(): return pd.read_csv(p)
    for fb in fallbacks:
        if Path(fb).exists(): return pd.read_csv(fb)
    return pd.DataFrame()

@st.cache_data
def load_data():
    # CLIENTI
    clienti = load_csv_with_fallback("clienti.csv",
               ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    clienti = ensure_clienti_cols(clienti)

    # CONTRATTI
    contratti = load_csv_with_fallback("contratti.csv",
                ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    contratti = ensure_contratti_cols(contratti)

    # ricalcolo TotRata dove serve
    tot_calc = contratti.apply(compute_tot, axis=1)
    mask_fix = contratti["TotRata"].isna() | (contratti["TotRata"] - tot_calc).abs().fillna(0) > 0.01
    contratti.loc[mask_fix, "TotRata"] = tot_calc

    return clienti, contratti

def save_csv(df, path): df.to_csv(path, index=False)

# =========================
# Auth minimale
# =========================
USERS = {
    "admin":{"password":"admin","role":"Admin"},
    "op":{"password":"op","role":"Operatore"},
    "view":{"password":"view","role":"Viewer"},
}
def do_login():
    st.title("Accesso CRM")
    u = st.text_input("Utente", value="admin")
    p = st.text_input("Password", type="password", value="admin")
    if st.button("Entra"):
        if u in USERS and USERS[u]["password"]==p:
            st.session_state["auth_user"]=u
            st.session_state["auth_role"]=USERS[u]["role"]
            st.rerun()
        else:
            st.error("Credenziali non valide.")

if "auth_user" not in st.session_state:
    do_login(); st.stop()
role = st.session_state.get("auth_role","Viewer")
editable = role in ["Admin","Operatore"]

# stato iniziale
clienti, contratti = load_data()
st.session_state.setdefault("clienti", clienti.copy())
st.session_state.setdefault("contratti", contratti.copy())

# =========================
# Metriche
# =========================
def monthly_revenue_open_client(df_ctr, cid):
    df = df_ctr[(df_ctr["ClienteID"]==int(cid)) & (df_ctr["Stato"].str.lower()=="aperto")]
    return float(df["TotRata"].sum())

def monthly_revenue_all_client(df_ctr, cid):
    df = df_ctr[df_ctr["ClienteID"]==int(cid)]
    return float(df["TotRata"].sum())

def monthly_revenue_open_all(df_ctr):
    df = df_ctr[df_ctr["Stato"].str.lower()=="aperto"]
    return float(df["TotRata"].sum())

# =========================
# Render tabella contratti (HTML con righe rosse)
# =========================
def contracts_html(df):
    df = sanitize_contracts_df(df)
    if df.empty:
        head = """
        <style>
          .ctr-table { width:100%; border-collapse:collapse; font-size:0.95rem; }
          .ctr-table th, .ctr-table td { border:1px solid #eee; padding:8px 10px; }
          .ctr-table th { background:#f7f7f9; text-align:left; }
          .row-chiuso { background:#ffecec; color:#7a0b0b; }
        </style>
        <table class="ctr-table">
          <thead><tr>{}</tr></thead>
          <tbody><tr><td colspan="9" style="text-align:center;color:#777;">Nessun contratto</td></tr></tbody>
        </table>
        """.format("".join([f"<th>{c}</th>" for c in SAFE_CONTRACT_COLS]))
        return head

    df2 = df.copy()
    df2["NOL_FIN"] = df2["NOL_FIN"].apply(euro)
    df2["NOL_INT"] = df2["NOL_INT"].apply(euro)
    df2["TotRata"] = df2["TotRata"].apply(euro)

    head = """
    <style>
      .ctr-table { width:100%; border-collapse:collapse; font-size:0.95rem; }
      .ctr-table th, .ctr-table td { border:1px solid #eee; padding:8px 10px; }
      .ctr-table th { background:#f7f7f9; text-align:left; }
      .row-chiuso { background:#ffecec; color:#7a0b0b; }
    </style>
    <table class="ctr-table">
      <thead><tr>{}</tr></thead><tbody>
    """.format("".join([f"<th>{c}</th>" for c in SAFE_CONTRACT_COLS]))

    rows = []
    for _, r in df2.iterrows():
        cls = "row-chiuso" if str(r["Stato"]).strip().lower()=="chiuso" else ""
        cells = "".join([f"<td>{r[c]}</td>" for c in SAFE_CONTRACT_COLS])
        rows.append(f"<tr class='{cls}'>{cells}</tr>")
    return head + "\n".join(rows) + "</tbody></table>"

# =========================
# Pagine
# =========================
def render_dashboard():
    st.title("📊 Dashboard")
    c1,c2,c3 = st.columns(3)
    c1.metric("Clienti", len(st.session_state["clienti"]))
    c2.metric("Contratti", len(st.session_state["contratti"]))
    c3.metric("Rata mensile (aperti)", euro(monthly_revenue_open_all(ensure_contratti_cols(st.session_state["contratti"]))))

    st.subheader("Promemoria (prossimo recall/visita)")
    cli = ensure_clienti_cols(st.session_state["clienti"])
    rem = cli[["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]].copy()
    st.dataframe(rem, use_container_width=True)

def render_clienti():
    # sempre normalize
    clienti  = ensure_clienti_cols(st.session_state["clienti"])
    ct       = ensure_contratti_cols(st.session_state["contratti"])

    st.title("👥 Clienti")

    # Aggiungi
    with st.expander("➕ Aggiungi cliente", expanded=False):
        with st.form("form_add_cliente"):
            col1,col2,col3 = st.columns(3)
            with col1:
                new_id = st.number_input("ClienteID (nuovo)", min_value=1, step=1)
                rs   = st.text_input("Ragione Sociale *")
                nome = st.text_input("Persona di riferimento")
                ind  = st.text_input("Indirizzo")
            with col2:
                citta = st.text_input("Città")
                cap   = st.text_input("CAP")
                tel   = st.text_input("Telefono")
                mail  = st.text_input("Email")
            with col3:
                piva = st.text_input("Partita IVA")
                iban = st.text_input("IBAN")
                sdi  = st.text_input("SDI")
                note = st.text_area("Note")
            ok = st.form_submit_button("Crea", disabled=not editable)
            if ok:
                if cap and not valid_cap(cap): st.error("CAP non valido (5 cifre)."); st.stop()
                if piva and not valid_piva(piva): st.error("P.IVA non valida (11 cifre)."); st.stop()
                if iban and not valid_iban_it(iban): st.error("IBAN IT non valido."); st.stop()
                if sdi and not valid_sdi(sdi): st.error("SDI non valido (7 char o 0000000)."); st.stop()
                if rs.strip()=="":
                    st.error("Ragione Sociale obbligatoria."); st.stop()
                if int(new_id) in clienti["ClienteID"].astype(int).tolist():
                    st.error("ClienteID già esistente."); st.stop()
                row = {
                    "ClienteID": int(new_id), "RagioneSociale": rs, "NomeCliente": nome,
                    "Indirizzo": ind, "Città": citta, "CAP": cap, "Telefono": tel, "Email": mail,
                    "PartitaIVA": piva, "IBAN": iban, "SDI": sdi,
                    "UltimoRecall":"", "ProssimoRecall":"", "UltimaVisita":"", "ProssimaVisita":"", "Note": note
                }
                st.session_state["clienti"] = pd.concat([clienti, pd.DataFrame([row])], ignore_index=True)
                st.success("Cliente creato. Ricorda di salvare.")

    # Elimina
    with st.expander("🗑️ Elimina cliente", expanded=False):
        ids = clienti["ClienteID"].astype(int).tolist()
        del_id = st.selectbox("Seleziona ClienteID da eliminare", ids) if ids else None
        if st.button("Elimina definitivamente", disabled=(not editable or del_id is None)):
            st.session_state["clienti"]   = clienti[clienti["ClienteID"].astype(int)!=int(del_id)]
            st.session_state["contratti"] = ct[ct["ClienteID"].astype(int)!=int(del_id)]
            st.warning("Cliente e relativi contratti eliminati. Ricorda di salvare.")

    if len(clienti)==0:
        st.info("Nessun cliente presente."); return

    det_id = st.number_input("Apri scheda ClienteID",
                             min_value=int(clienti["ClienteID"].min()),
                             max_value=int(clienti["ClienteID"].max()),
                             value=int(clienti["ClienteID"].min()),
                             step=1)
    dettaglio = clienti[clienti["ClienteID"]==int(det_id)]
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
    if (c["Note"] or "") != "": st.info(c["Note"])

    # contratti cliente (sempre tramite ensure_contratti_cols)
    ct = ensure_contratti_cols(st.session_state["contratti"])
    ct_cli = ct[ct["ClienteID"]==int(det_id)].copy()

    m1,m2,m3 = st.columns(3)
    m1.metric("Contratti", len(ct_cli))
    m2.metric("Rata mensile (Tutti)", euro(monthly_revenue_all_client(ct, det_id)))
    m3.metric("Rata mensile (Aperti)", euro(monthly_revenue_open_client(ct, det_id)))

    st.write("### Contratti (rosso = chiusi)")
    st.markdown(contracts_html(ct_cli), unsafe_allow_html=True)

    # Aggiungi contratto
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
                fin   = st.text_input("NOL_FIN", value="0")
                intr  = st.text_input("NOL_INT", value="0")
                stato = st.selectbox("Stato", ["aperto","chiuso","sospeso"], index=0)
            with col3:
                tot_auto = st.checkbox("TotRata = FIN + INT", value=True)
                tot = st.text_input("TotRata (se non auto)", value="0")
            ok = st.form_submit_button("Crea", disabled=not editable)
            if ok:
                tot_val = compute_tot({"NOL_FIN":fin,"NOL_INT":intr}) if tot_auto else numify(tot)
                new_row = {"ClienteID":int(det_id),"NumeroContratto":numero.strip(),
                           "DataInizio":fmt_date(d_in),"DataFine":fmt_date(d_fi),"Durata":durata,
                           "DescrizioneProdotto":descr,"NOL_FIN":numify(fin),"NOL_INT":numify(intr),
                           "TotRata":round(tot_val,2),"Stato":stato}
                st.session_state["contratti"] = pd.concat([ct, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Contratto creato. Ricorda di salvare.")

    # Modifica/chiudi
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
                    fin   = st.text_input("NOL_FIN", value=str(old["NOL_FIN"]))
                    intr  = st.text_input("NOL_INT", value=str(old["NOL_INT"]))
                    stato = st.selectbox("Stato", ["aperto","chiuso","sospeso"],
                            index=["aperto","chiuso","sospeso"].index(str(old["Stato"] or "aperto").lower()))
                with col3:
                    tot_auto = st.checkbox("TotRata = FIN + INT", value=True)
                    tot = st.text_input("TotRata", value=str(old["TotRata"]))
                ok = st.form_submit_button("Aggiorna", disabled=not editable)
                if ok:
                    tot_val = compute_tot({"NOL_FIN":fin,"NOL_INT":intr}) if tot_auto else numify(tot)
                    mask = (ct["ClienteID"].astype(int)==int(det_id)) & (ct["NumeroContratto"].astype(str)==str(target))
                    st.session_state["contratti"].loc[mask,
                        ["DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]] = \
                        [fmt_date(d_in), fmt_date(d_fi), durata, descr, numify(fin), numify(intr), round(tot_val,2), stato]
                    st.success("Contratto aggiornato. Ricorda di salvare.")
        else:
            st.info("Nessun contratto per questo cliente.")

    # Elimina
    with st.expander("🗑️ Elimina contratto", expanded=False):
        n2 = ct_cli["NumeroContratto"].astype(str).tolist()
        deln = st.selectbox("Numero contratto da eliminare", n2) if len(n2)>0 else None
        if st.button("Elimina questo contratto", disabled=(not editable or deln is None)):
            mask = ~((ct["ClienteID"].astype(int)==int(det_id)) & (ct["NumeroContratto"].astype(str)==str(deln)))
            st.session_state["contratti"] = ct[mask]
            st.warning("Contratto eliminato. Ricorda di salvare.")

    # Salvataggio rapido
    c1,c2 = st.columns(2)
    if c1.button("💾 Salva contratti adesso"):
        save_csv(ensure_contratti_cols(st.session_state["contratti"]), "contratti.csv")
        st.success("Contratti salvati (contratti.csv).")
    if c2.button("💾 Salva clienti adesso"):
        save_csv(ensure_clienti_cols(st.session_state["clienti"]), "clienti.csv")
        st.success("Clienti salvati (clienti.csv).")

def render_contratti():
    clienti = ensure_clienti_cols(st.session_state["clienti"])
    ct      = ensure_contratti_cols(st.session_state["contratti"])

    st.title("📃 Contratti per cliente")
    if len(clienti)==0:
        st.info("Nessun cliente caricato."); return

    opts = [(int(cid), nm if pd.notna(nm) else "") for cid,nm in zip(clienti["ClienteID"], clienti["RagioneSociale"])]
    labels = [f"{cid} — {nm}" for cid,nm in opts]
    choice = st.selectbox("Seleziona cliente", ["(seleziona)"] + labels, index=0)
    if choice == "(seleziona)":
        st.info("Seleziona un cliente per vedere i suoi contratti."); return
    try:
        sel_cid = int(str(choice).split(" — ")[0])
    except:
        st.warning("Selezione non valida."); return

    df = ct[ct["ClienteID"]==sel_cid].copy()
    st.markdown(contracts_html(df), unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    if c1.button("💾 Salva contratti adesso", key="save_contratti_page"):
        save_csv(ensure_contratti_cols(st.session_state["contratti"]), "contratti.csv")
        st.success("Contratti salvati (contratti.csv).")
    if c2.button("💾 Salva clienti adesso", key="save_clienti_page"):
        save_csv(ensure_clienti_cols(st.session_state["clienti"]), "clienti.csv")
        st.success("Clienti salvati (clienti.csv).")

def render_settings():
    st.title("⚙️ Impostazioni & Salvataggio")
    c1,c2 = st.columns(2)
    if c1.button("💾 Salva clienti.csv"):
        save_csv(ensure_clienti_cols(st.session_state["clienti"]), "clienti.csv"); st.toast("clienti.csv salvato.", icon="✅")
    if c2.button("💾 Salva contratti.csv"):
        save_csv(ensure_contratti_cols(st.session_state["contratti"]), "contratti.csv"); st.toast("contratti.csv salvato.", icon="✅")

    st.write("---")
    colA,colB = st.columns(2)
    uc = colA.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None:
        tmp = pd.read_csv(uc)
        st.session_state["clienti"] = ensure_clienti_cols(tmp)
        st.toast("Clienti caricati (ricordati di salvare).", icon="✅")

    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None:
        tmp = pd.read_csv(ut)
        tmp = ensure_contratti_cols(tmp)
        st.session_state["contratti"] = tmp
        st.toast("Contratti caricati (ricordati di salvare).", icon="✅")

# =========================
# Router
# =========================
st.sidebar.title("CRM")
page = st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti","Impostazioni"])

if page == "Dashboard":
    render_dashboard()
elif page == "Clienti":
    render_clienti()
elif page == "Contratti":
    render_contratti()
else:
    render_settings()
