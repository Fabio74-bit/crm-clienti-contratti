import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
from pathlib import Path

st.set_page_config(page_title="CRM Clienti & Contratti", layout="wide")

# -------------------------
# Helpers: Data IO
# -------------------------
def load_csv_with_fallback(main_path: str, fallbacks: list[str]) -> pd.DataFrame:
    if Path(main_path).exists():
        return pd.read_csv(main_path)
    for fb in fallbacks:
        if Path(fb).exists():
            return pd.read_csv(fb)
    return pd.DataFrame()

@st.cache_data
def load_data():
    clienti = load_csv_with_fallback(
        "clienti.csv",
        ["clienti_batch1.csv", "clienti_normalizzati.csv", "preview_clienti.csv"]
    )
    contratti = load_csv_with_fallback(
        "contratti.csv",
        ["contratti_batch1.csv", "contratti_normalizzati.csv", "preview_contratti.csv"]
    )

    # Clienti: colonne attese
    exp_cli = ["ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","UltimoRecall","UltimaVisita","Note"]
    if clienti.empty:
        clienti = pd.DataFrame(columns=exp_cli)
    for c in exp_cli:
        if c not in clienti.columns:
            clienti[c] = None
    if "ClienteID" in clienti.columns:
        clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")

    # Contratti: colonne attese
    exp_ctr = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    if contratti.empty:
        contratti = pd.DataFrame(columns=exp_ctr)
    for c in exp_ctr:
        if c not in contratti.columns:
            contratti[c] = None
    if "ClienteID" in contratti.columns:
        contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    for col in ["DataInizio","DataFine"]:
        if col in contratti.columns:
            contratti[col] = pd.to_datetime(contratti[col], errors="coerce").dt.date
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        if col in contratti.columns:
            contratti[col] = pd.to_numeric(contratti[col], errors="coerce")

    # Demo minima se totalmente vuoti
    if clienti.empty:
        clienti = pd.DataFrame([{
            "ClienteID": 1, "RagioneSociale": "1 A 1 S.r.l.", "NomeCliente": "1 A 1 S.r.l.",
            "Indirizzo":"Via C. del Fante 4","Città":"Milano","CAP":"20122","Telefono":"34844005",
            "Email":None,"PartitaIVA":None,"UltimoRecall":None,"UltimaVisita":None,"Note":"Demo note"
        }])
    if contratti.empty:
        contratti = pd.DataFrame([{
            "ClienteID": 1, "NumeroContratto": "C-2025-001", "DataInizio": date(2025,1,1),
            "DataFine": date(2026,1,1), "Durata":"12 mesi", "DescrizioneProdotto":"Noleggio MFP",
            "NOL_FIN": 800.0, "NOL_INT": 0.0, "TotRata": 1200.0, "Stato":"Aperto"
        }])

    return clienti, contratti

def save_csv(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)

# -------------------------
# Auth (semplice)
# -------------------------
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

# -------------------------
# Sidebar
# -------------------------
def sidebar(role: str) -> str:
    st.sidebar.title("CRM")
    return st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti","Impostazioni"])

# -------------------------
# Dashboard
# -------------------------
def render_dashboard(clienti: pd.DataFrame, contratti: pd.DataFrame):
    st.title("📊 Dashboard")
    c1, c2, c3 = st.columns(3)
    c1.metric("Clienti", len(clienti))
    c2.metric("Contratti", len(contratti))
    attivi = (contratti["Stato"].fillna("").str.lower() == "aperto").sum()
    c3.metric("Contratti aperti", int(attivi))

    st.subheader("Indice clienti")
    idx = contratti.groupby("ClienteID").size().reset_index(name="NumContratti")
    tab = clienti[["ClienteID","RagioneSociale"]].merge(idx, on="ClienteID", how="left").fillna({"NumContratti":0}).sort_values("RagioneSociale")
    st.dataframe(tab, use_container_width=True)

# -------------------------
# Clienti
# -------------------------
def render_clienti(clienti: pd.DataFrame, contratti: pd.DataFrame, role: str):
    st.title("👥 Clienti")
    editable = role in ["Admin","Operatore"]

    q = st.text_input("Cerca per ragione sociale / città / telefono")
    df = clienti.copy()
    if q:
        ql = q.lower()
        df = df[df.fillna("").apply(lambda r: any(ql in str(v).lower() for v in r[["RagioneSociale","Città","Telefono"]]), axis=1)]
    st.dataframe(df[["ClienteID","RagioneSociale","Città","Telefono"]].sort_values("RagioneSociale"), use_container_width=True, height=320)

    st.divider()
    colA, colB = st.columns([1,1])
    with colA:
        st.subheader("➕ Nuovo cliente")
        with st.form("new_client"):
            rs = st.text_input("Ragione sociale")
            contatto = st.text_input("Nome cliente / Contatto")
            indirizzo = st.text_input("Indirizzo")
            citta = st.text_input("Città")
            cap = st.text_input("CAP")
            tel = st.text_input("Telefono")
            email = st.text_input("Email")
            piva = st.text_input("Partita IVA")
            recall = st.text_input("Ultimo Recall (YYYY-MM-DD)")
            visita = st.text_input("Ultima Visita (YYYY-MM-DD)")
            note = st.text_area("Note")
            submitted = st.form_submit_button("Crea", disabled=not editable)
            if submitted:
                if not rs:
                    st.warning("Ragione sociale obbligatoria.")
                else:
                    next_id = (clienti["ClienteID"].max() or 0) + 1
                    new_row = {
                        "ClienteID": int(next_id), "RagioneSociale": rs, "NomeCliente": contatto,
                        "Indirizzo": indirizzo, "Città": citta, "CAP": cap, "Telefono": tel,
                        "Email": email, "PartitaIVA": piva, "UltimoRecall": recall, "UltimaVisita": visita, "Note": note
                    }
                    st.session_state["clienti"] = pd.concat([clienti, pd.DataFrame([new_row])], ignore_index=True)
                    st.success("Cliente creato. Ricordati di salvare nelle Impostazioni.")

    with colB:
        st.subheader("✏️ Modifica / ❌ Elimina")
        if len(clienti) == 0:
            st.info("Nessun cliente.")
        else:
            edit_id = st.number_input("ClienteID", min_value=int(clienti["ClienteID"].min()), max_value=int(clienti["ClienteID"].max()), step=1, value=int(clienti["ClienteID"].min()))
            tgt = clienti[clienti["ClienteID"] == int(edit_id)]
            if tgt.empty:
                st.info("Seleziona un ClienteID esistente.")
            else:
                row = tgt.iloc[0]
                with st.form("edit_client"):
                    rs = st.text_input("Ragione sociale", value=row["RagioneSociale"] or "")
                    contatto = st.text_input("Nome cliente / Contatto", value=row["NomeCliente"] or "")
                    indirizzo = st.text_input("Indirizzo", value=row["Indirizzo"] or "")
                    citta = st.text_input("Città", value=row["Città"] or "")
                    cap = st.text_input("CAP", value=row["CAP"] or "")
                    tel = st.text_input("Telefono", value=row["Telefono"] or "")
                    email = st.text_input("Email", value=row["Email"] or "")
                    piva = st.text_input("Partita IVA", value=row["PartitaIVA"] or "")
                    recall = st.text_input("Ultimo Recall (YYYY-MM-DD)", value=str(row["UltimoRecall"] or ""))
                    visita = st.text_input("Ultima Visita (YYYY-MM-DD)", value=str(row["UltimaVisita"] or ""))
                    note = st.text_area("Note", value=row["Note"] or "")
                    c1, c2 = st.columns(2)
                    save_btn = c1.form_submit_button("Salva modifiche", disabled=not editable)
                    del_btn = c2.form_submit_button("Elimina cliente", disabled=not editable)
                    if save_btn:
                        idx = clienti[clienti["ClienteID"] == int(edit_id)].index
                        if len(idx):
                            st.session_state["clienti"].loc[idx, ["RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","UltimoRecall","UltimaVisita","Note"]] = \
                                [rs,contatto,indirizzo,citta,cap,tel,email,piva,recall,visita,note]
                            st.success("Dati cliente aggiornati. Ricordati di salvare.")
                    if del_btn:
                        if (contratti["ClienteID"] == int(edit_id)).any():
                            st.warning("Impossibile eliminare: esistono contratti associati.")
                        else:
                            st.session_state["clienti"] = clienti[clienti["ClienteID"] != int(edit_id)]
                            st.success("Cliente eliminato. Ricordati di salvare.")

    st.divider()
    st.subheader("📄 Scheda cliente")
    if len(clienti) > 0:
        det_id = st.number_input("Apri scheda ClienteID", min_value=int(clienti["ClienteID"].min()), max_value=int(clienti["ClienteID"].max()), step=1, value=int(clienti["ClienteID"].min()), key="open_client")
        dettaglio = clienti[clienti["ClienteID"] == int(det_id)]
        if not dettaglio.empty:
            c = dettaglio.iloc[0]
            st.markdown(f"**{c['RagioneSociale']}** — {c['Città'] or ''}  \n📞 {c['Telefono'] or '-'} | 📧 {c['Email'] or '-'}")
            st.write("**Indirizzo:**", c["Indirizzo"] or "-")
            st.write("**Note:**")
            st.info(c["Note"] or "-")

            st.write("### Contratti di questo cliente")
            ct = contratti[contratti["ClienteID"] == int(det_id)].copy()
            st.dataframe(ct, use_container_width=True, height=240)

            if editable:
                st.write("#### ➕ Aggiungi contratto")
                with st.form("new_contract"):
                    num = st.text_input("Numero contratto")
                    d_in = st.date_input("Data inizio", value=date.today())
                    d_fin = st.date_input("Data fine", value=date.today())
                    durata = st.text_input("Durata (es. '12 mesi')")
                    desc = st.text_input("Descrizione prodotto")
                    nol_fin = st.number_input("NOL. FIN.", min_value=0.0, step=1.0)
                    nol_int = st.number_input("NOL. INT.", min_value=0.0, step=1.0)
                    tot = st.number_input("TOT. RATA", min_value=0.0, step=1.0)
                    stato = st.selectbox("Stato", ["Aperto","Chiuso","Sospeso"])
                    add_btn = st.form_submit_button("Aggiungi")
                    if add_btn:
                        new_row = {
                            "ClienteID": int(det_id), "NumeroContratto": num, "DataInizio": d_in,
                            "DataFine": d_fin, "Durata": durata, "DescrizioneProdotto": desc,
                            "NOL_FIN": float(nol_fin), "NOL_INT": float(nol_int), "TotRata": float(tot), "Stato": stato
                        }
                        st.session_state["contratti"] = pd.concat([contratti, pd.DataFrame([new_row])], ignore_index=True)
                        st.success("Contratto aggiunto. Ricordati di salvare.")

                st.write("#### ✏️ Modifica / ❌ Elimina contratto")
                if not ct.empty:
                    idx_row = st.number_input("Indice riga (0-based) nella tabella contratti sopra", min_value=0, max_value=len(ct)-1, step=1, value=0, key="edit_ct_idx")
                    row = ct.iloc[idx_row]
                    with st.form("edit_contract"):
                        num = st.text_input("Numero contratto", value=row["NumeroContratto"] or "")
                        d_in = st.date_input("Data inizio", value=row["DataInizio"] or date.today())
                        d_fin = st.date_input("Data fine", value=row["DataFine"] or date.today())
                        durata = st.text_input("Durata", value=row["Durata"] or "")
                        desc = st.text_input("Descrizione prodotto", value=row["DescrizioneProdotto"] or "")
                        nol_fin = st.number_input("NOL. FIN.", min_value=0.0, step=1.0, value=float(row["NOL_FIN"] or 0.0))
                        nol_int = st.number_input("NOL. INT.", min_value=0.0, step=1.0, value=float(row["NOL_INT"] or 0.0))
                        tot = st.number_input("TOT. RATA", min_value=0.0, step=1.0, value=float(row["TotRata"] or 0.0))
                        stato = st.selectbox("Stato", ["Aperto","Chiuso","Sospeso"], index=["Aperto","Chiuso","Sospeso"].index((row["Stato"] or "Aperto")))
                        c1, c2 = st.columns(2)
                        save_btn = c1.form_submit_button("Salva modifiche")
                        del_btn = c2.form_submit_button("Elimina contratto")
                        if save_btn:
                            abs_idx = contratti[(contratti["ClienteID"]==int(det_id))].index[idx_row]
                            st.session_state["contratti"].loc[abs_idx, ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]] = \
                                [num, d_in, d_fin, durata, desc, float(nol_fin), float(nol_int), float(tot), stato]
                            st.success("Contratto aggiornato. Ricordati di salvare.")
                        if del_btn:
                            abs_idx = contratti[(contratti["ClienteID"]==int(det_id))].index[idx_row]
                            st.session_state["contratti"] = contratti.drop(index=abs_idx)
                            st.success("Contratto eliminato. Ricordati di salvare.")

# -------------------------
# Contratti (vista globale)
# -------------------------
def render_contratti(clienti: pd.DataFrame, contratti: pd.DataFrame, role: str):
    st.title("📃 Contratti")
    name_map = dict(zip(clienti["ClienteID"], clienti["RagioneSociale"]))
    df = contratti.copy()
    df["Cliente"] = df["ClienteID"].map(name_map)

    c1, c2, c3 = st.columns(3)
    f_cliente = c1.selectbox("Cliente", ["(tutti)"] + sorted([n for n in df["Cliente"].dropna().unique()]))
    f_stato = c2.selectbox("Stato", ["(tutti)","Aperto","Chiuso","Sospeso"])
    f_anno = c3.number_input("Anno inizio (0 = tutti)", min_value=0, step=1, value=0)

    if f_cliente != "(tutti)":
        df = df[df["Cliente"] == f_cliente]
    if f_stato != "(tutti)":
        df = df[df["Stato"].fillna("") == f_stato]
    if f_anno:
        df = df[pd.to_datetime(df["DataInizio"], errors="coerce").dt.year == f_anno]

    st.dataframe(df[["Cliente","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]], use_container_width=True)

# -------------------------
# Impostazioni (salvataggi)
# -------------------------
def render_settings(clienti: pd.DataFrame, contratti: pd.DataFrame, role: str):
    st.title("⚙️ Impostazioni & Salvataggio")
    c1, c2 = st.columns(2)
    if c1.button("💾 Salva clienti.csv", disabled=role=="Viewer"):
        save_csv(clienti, "clienti.csv")
        st.success("clienti.csv salvato.")
    if c2.button("💾 Salva contratti.csv", disabled=role=="Viewer"):
        save_csv(contratti, "contratti.csv")
        st.success("contratti.csv salvato.")

    st.write("---")
    uc = st.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None and role != "Viewer":
        st.session_state["clienti"] = pd.read_csv(uc)
        st.success("Clienti caricati (ricordati di salvare).")
    ut = st.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None and role != "Viewer":
        tmp = pd.read_csv(ut)
        for col in ["DataInizio","DataFine"]:
            if col in tmp.columns:
                tmp[col] = pd.to_datetime(tmp[col], errors="coerce").dt.date
        for col in ["NOL_FIN","NOL_INT","TotRata"]:
            if col in tmp.columns:
                tmp[col] = pd.to_numeric(tmp[col], errors="coerce")
        st.session_state["contratti"] = tmp
        st.success("Contratti caricati (ricordati di salvare).")

# -------------------------
# Main
# -------------------------
if "auth_user" not in st.session_state:
    do_login()
    st.stop()

role = st.session_state.get("auth_role", "Viewer")
cli, ctr = load_data()
if "clienti" not in st.session_state:
    st.session_state["clienti"] = cli.copy()
if "contratti" not in st.session_state:
    st.session_state["contratti"] = ctr.copy()

page = sidebar(role)
if page == "Dashboard":
    render_dashboard(st.session_state["clienti"], st.session_state["contratti"])
elif page == "Clienti":
    render_clienti(st.session_state["clienti"], st.session_state["contratti"], role)
elif page == "Contratti":
    render_contratti(st.session_state["clienti"], st.session_state["contratti"], role)
else:
    render_settings(st.session_state["clienti"], st.session_state["contratti"], role)
