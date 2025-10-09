
import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re

st.set_page_config(page_title="CRM Clienti & Contratti — v3 FIX5", layout="wide")

# =========================
# Helpers & Config
# =========================
DATE_FMT = "%d/%m/%Y"  # dd/mm/aaaa

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

# --- NUMERIC NORMALIZER robust to '€ 1.234,56' etc. ---
def numify(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return 0.0
    s = s.replace("€","").replace(" ", "")
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
    if v == 0: 
        return ""
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    return f"€ {s}"

def status_class(s):
    s = str(s or "").strip().lower()
    if s == "chiuso": return "closed"
    if s == "aperto": return "open"
    if s == "sospeso": return "suspended"
    return "unknown"

# ---- columns safeguard ----
EXPECTED_CLIENTI_COLS = ["ClienteID","RagioneSociale","NomeCliente","Indirizzo","Città","CAP","Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]

def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or len(df)==0:
        return pd.DataFrame(columns=EXPECTED_CLIENTI_COLS)
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns:
            df[c] = None
    return df

# Validation masks
def valid_cap(s):  return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ", "").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

# Progressive quote number PRE-YYYY-0001
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
    clienti = load_csv_with_fallback("clienti.csv", ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    clienti = ensure_clienti_cols(clienti)
    clienti["ClienteID"] = pd.to_numeric(clienti["ClienteID"], errors="coerce").astype("Int64")
    clienti = clienti[EXPECTED_CLIENTI_COLS]

    ctr_cols = ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    contratti = load_csv_with_fallback("contratti.csv", ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    for c in ctr_cols:
        if c not in contratti.columns:
            contratti[c] = None
    contratti["ClienteID"] = pd.to_numeric(contratti["ClienteID"], errors="coerce").astype("Int64")
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        contratti[col] = contratti[col].apply(numify)
    contratti["Stato"] = contratti["Stato"].astype(str).replace({"nan":""})
    contratti = contratti[ctr_cols]

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
USERS = {"admin": {"password": "admin", "role": "Admin"},
         "op": {"password": "op", "role": "Operatore"},
         "view": {"password": "view", "role": "Viewer"}}

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
# Main session bootstrap
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
if "attachments" not in st.session_state:
    st.session_state["attachments"] = {}

# =========================
# Sidebar
# =========================
st.sidebar.title("CRM")
page = st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti","Impostazioni"])

# =========================
# Dashboard
# =========================
def monthly_revenue_open_client(contratti, cid):
    df = contratti[(contratti["ClienteID"]==int(cid)) & (contratti["Stato"].str.lower()=="aperto")]
    return float(sum(df["TotRata"].apply(numify)))

def monthly_revenue_open_all(contratti):
    df = contratti[contratti["Stato"].str.lower()=="aperto"]
    return float(sum(df["TotRata"].apply(numify)))

def render_dashboard():
    st.title("📊 Dashboard")
    c1,c2,c3 = st.columns(3)
    c1.metric("Clienti", len(st.session_state["clienti"]))
    c2.metric("Contratti", len(st.session_state["contratti"]))
    c3.metric("Rata mensile (aperti)", euro(monthly_revenue_open_all(st.session_state["contratti"])))

    st.subheader("Prossimi promemoria")
    cli = ensure_clienti_cols(st.session_state["clienti"])
    rem = cli[["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]].copy()
    st.dataframe(rem, use_container_width=True)

# =========================
# Clienti
# =========================
def render_clienti():
    clienti = ensure_clienti_cols(st.session_state["clienti"])
    contratti = st.session_state["contratti"]
    preventivi = st.session_state["preventivi"]
    role = st.session_state.get("auth_role","Viewer")
    editable = role in ["Admin","Operatore"]

    st.title("👥 Clienti")

    if len(clienti)==0:
        st.info("Nessun cliente caricato.")
        return

    det_id = st.number_input("Apri scheda ClienteID", min_value=int(clienti["ClienteID"].min()), max_value=int(clienti["ClienteID"].max()), step=1, value=int(clienti["ClienteID"].min()))
    dettaglio = clienti[clienti["ClienteID"] == int(det_id)]
    if dettaglio.empty:
        st.info("Cliente non trovato.")
        return
    c = dettaglio.iloc[0]

    # ANAGRAFICA completa (Persona di riferimento inclusa)
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

    right_col = st.columns(3)
    with right_col[0]:
        ct_cli = contratti[contratti["ClienteID"] == int(det_id)].copy()
        st.metric("Contratti", len(ct_cli))
    with right_col[1]:
        st.metric("Aperti", int((ct_cli["Stato"].str.lower()=="aperto").sum()))
    with right_col[2]:
        st.metric("Rata mensile (aperti)", euro(monthly_revenue_open_client(contratti, det_id)))

    # Tabella contratti del cliente (celle vuote nascoste, euro formattati)
    st.write("### Contratti (rosso = chiusi)")
    ct_cli = ct_cli.fillna("")
    def fmt_cell(val, money=False):
        if val in [None, "", np.nan, "nan"]:
            return ""
        return euro(val) if money else str(val)
    def row_html(row):
        cls = "row " + status_class(row.get("Stato",""))
        cells = "".join([
            f"<td>{fmt_cell(row.get('NumeroContratto'))}</td>",
            f"<td>{fmt_cell(row.get('DataInizio'))}</td>",
            f"<td>{fmt_cell(row.get('DataFine'))}</td>",
            f"<td>{fmt_cell(row.get('Durata'))}</td>",
            f"<td>{fmt_cell(row.get('DescrizioneProdotto'))}</td>",
            f"<td>{fmt_cell(row.get('NOL_FIN'), True)}</td>",
            f"<td>{fmt_cell(row.get('NOL_INT'), True)}</td>",
            f"<td>{fmt_cell(row.get('TotRata'), True)}</td>",
            f"<td>{fmt_cell(row.get('Stato'))}</td>",
        ])
        return f"<tr class='{cls}'>{cells}</tr>"
    header = "<tr>" + "".join([f"<th>{h}</th>" for h in ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]]) + "</tr>"
    rows = "\n".join([row_html(r) for _,r in ct_cli.iterrows()])
    st.markdown("""
    <style>
    .table-ctr table {border-collapse: collapse; width: 100%;}
    .table-ctr th, .table-ctr td {border:1px solid #e5e7eb; padding:6px 8px; font-size:14px;}
    .table-ctr tr.closed {background: #fee2e2;}
    .table-ctr tr.open {background: #ecfdf5;}
    .table-ctr tr.suspended {background: #ffedd5;}
    </style>
    """, unsafe_allow_html=True)
    st.markdown(f"<div class='table-ctr'><table>{header}{rows}</table></div>", unsafe_allow_html=True)

    # Export/Stampa selezione
    st.write("#### Esporta/Stampa contratti (selezione)")
    export_df = ct_cli.copy()
    sel_nums = st.multiselect("Seleziona N. contratti (vuoto = tutti)", export_df["NumeroContratto"].tolist())
    if sel_nums:
        export_df = export_df[export_df["NumeroContratto"].isin(sel_nums)]
    # Excel
    try:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Contratti")
        st.download_button("⬇️ Scarica Excel dei contratti", data=out.getvalue(), file_name=f"contratti_{int(det_id)}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception:
        csv = export_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Scarica CSV dei contratti", data=csv, file_name=f"contratti_{int(det_id)}.csv", mime="text/csv")

    # Print-friendly
    html_rows = "".join([
        f"<tr><td>{r['NumeroContratto']}</td><td>{r['DataInizio']}</td><td>{r['DataFine']}</td><td>{r['Durata']}</td><td>{r['DescrizioneProdotto']}</td><td>{euro(r['NOL_FIN'])}</td><td>{euro(r['NOL_INT'])}</td><td>{euro(r['TotRata'])}</td><td>{r['Stato']}</td></tr>"
        for _,r in export_df.iterrows()
    ])
    printable = f"""
    <div style='text-align:center;font-weight:700;font-size:18px;margin-bottom:8px'>{c['RagioneSociale']}</div>
    <table border='1' cellspacing='0' cellpadding='6' style='width:100%;border-collapse:collapse;font-size:14px'>
        <tr><th>Numero</th><th>Inizio</th><th>Fine</th><th>Durata</th><th>Descrizione</th><th>NOL_FIN</th><th>NOL_INT</th><th>TOT RATA</th><th>Stato</th></tr>
        {html_rows}
    </table>
    <script>window.onload = function() {{ window.print(); }}</script>
    """
    if st.button("🖨️ Stampa contratti selezionati"):
        st.components.v1.html(printable, height=600, scrolling=True)

# =========================
# Contratti (per cliente) — robust against None selection
# =========================
def render_contratti():
    clienti = ensure_clienti_cols(st.session_state["clienti"])
    contratti = st.session_state["contratti"]
    st.title("📃 Contratti per cliente")

    if len(clienti)==0:
        st.info("Nessun cliente caricato.")
        return

    opts = [(int(cid), nm if pd.notna(nm) else "") for cid, nm in zip(clienti["ClienteID"], clienti["RagioneSociale"])]
    labels = [f"{cid} — {nm}" for cid, nm in opts]
    choice = st.selectbox("Seleziona cliente", ["(seleziona)"] + labels, index=0)
    if not choice or choice == "(seleziona)":
        st.info("Seleziona un cliente per vedere i suoi contratti.")
        return
    try:
        sel_cid = int(str(choice).split(" — ")[0])
    except Exception:
        st.warning("Selezione non valida.")
        return

    df = contratti[contratti["ClienteID"]==sel_cid].copy()
    df_display = df.copy()
    for col in ["NOL_FIN","NOL_INT","TotRata"]:
        df_display[col] = df_display[col].apply(euro)
    st.dataframe(df_display, use_container_width=True)

    if st.button("⬇️ Esporta CSV contratti cliente"):
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Scarica contratti (CSV)", data=csv, file_name=f"contratti_cliente_{sel_cid}.csv", mime="text/csv")

# =========================
# Impostazioni (load/save + template preventivi)
# =========================
def render_settings():
    role = st.session_state.get("auth_role","Viewer")
    st.title("⚙️ Impostazioni & Salvataggio")
    c1,c2,c3 = st.columns(3)
    if c1.button("💾 Salva clienti.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["clienti"], "clienti.csv")
        st.toast("clienti.csv salvato.", icon="✅")
    if c2.button("💾 Salva contratti.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["contratti"], "contratti.csv")
        st.toast("contratti.csv salvato.", icon="✅")
    if c3.button("💾 Salva preventivi.csv", disabled=role=="Viewer"):
        save_csv(st.session_state["preventivi"], "preventivi.csv")
        st.toast("preventivi.csv salvato.", icon="✅")

    st.write("---")
    colA, colB, colC = st.columns(3)
    uc = colA.file_uploader("Carica clienti.csv", type=["csv"])
    if uc is not None and role != "Viewer":
        tmp = pd.read_csv(uc)
        st.session_state["clienti"] = ensure_clienti_cols(tmp)
        st.toast("Clienti caricati (ricordati di salvare).", icon="✅")
    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None and role != "Viewer":
        tmp = pd.read_csv(ut)
        tmp["DataInizio"] = tmp["DataInizio"].apply(fmt_date)
        tmp["DataFine"] = tmp["DataFine"].apply(fmt_date)
        for col in ["NOL_FIN","NOL_INT","TotRata"]:
            tmp[col] = tmp[col].apply(numify)
        tmp["Stato"] = tmp["Stato"].astype(str).replace({"nan":""})
        st.session_state["contratti"] = tmp
        st.toast("Contratti caricati (ricordati di salvare).", icon="✅")

    # Template preventivi
    st.subheader("📄 Template preventivi (Word .docx)")
    tpls = colC.file_uploader("Carica template (.docx) con {{NUMERO}}, {{CLIENTE}}, {{DATA}}", type=["docx"], accept_multiple_files=True)
    if tpls:
        st.session_state["quote_templates"] = [(f.name, f.read()) for f in tpls]
        st.toast(f"{len(tpls)} template caricati (temporanei).", icon="✅")

# =========================
# Router
# =========================
if page == "Dashboard":
    render_dashboard()
elif page == "Clienti":
    render_clienti()
elif page == "Contratti":
    render_contratti()
else:
    render_settings()
