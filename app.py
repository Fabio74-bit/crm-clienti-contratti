# app.py — CRM Clienti & Contratti  (layout separato)
# v5.0

import os, io, sys, re
from pathlib import Path
from datetime import date, datetime

import streamlit as st
import pandas as pd
import numpy as np

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(page_title="CRM Clienti & Contratti", layout="wide")
print(">>> app.py v5.0", file=sys.stderr)

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

# ---------------- Utils base ----------------
def fmt_date(d):
    if pd.isna(d) or d is None or d == "": return ""
    if isinstance(d, str):
        s = d.strip()
        for f in ["%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%m/%d/%Y"]:
            try: return datetime.strptime(s, f).strftime(DATE_FMT)
            except: pass
        return s
    if isinstance(d, (datetime, date)): return d.strftime(DATE_FMT)
    return str(d)

def parse_date_safe(s):
    if s is None or str(s).strip()=="" or str(s).lower()=="nan": return None
    if isinstance(s, (datetime, date)): return s if isinstance(s, date) else s.date()
    ss = str(s).strip()
    for f in ["%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%m/%d/%Y"]:
        try: return datetime.strptime(ss, f).date()
        except: pass
    return None

def numify(x):
    if x is None or (isinstance(x, float) and np.isnan(x)): return 0.0
    s = str(x).strip()
    if s == "" or s.lower() == "nan": return 0.0
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

def compute_tot(row): return round(numify(row.get("NOL_FIN")) + numify(row.get("NOL_INT")), 2)

def valid_cap(s):  return bool(re.fullmatch(r"\d{5}", (s or "").strip()))
def valid_piva(s): return bool(re.fullmatch(r"\d{11}", (s or "").strip()))
def valid_iban_it(s):
    ss = (s or "").replace(" ","").upper()
    return ss.startswith("IT") and len(ss)==27 and ss.isalnum()
def valid_sdi(s):
    ss = (s or "").strip().upper()
    return ss=="0000000" or bool(re.fullmatch(r"[A-Z0-9]{7}", ss))

def next_contract_number(df_ct, cid):
    yy = date.today().strftime("%Y")
    prefix = f"CTR-{cid}-{yy}-"
    if df_ct.empty or "NumeroContratto" not in df_ct.columns: return prefix + "0001"
    mask = df_ct["NumeroContratto"].fillna("").astype(str).str.startswith(prefix)
    if not mask.any(): return prefix + "0001"
    last = sorted(df_ct.loc[mask,"NumeroContratto"].astype(str))[-1]
    n = int(last.split("-")[-1])
    return f"{prefix}{n+1:04d}"

# ---------------- Normalizzazione tabelle ----------------
def ensure_clienti_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(df).copy()
    if df.empty: return pd.DataFrame(columns=EXPECTED_CLIENTI_COLS)
    for c in EXPECTED_CLIENTI_COLS:
        if c not in df.columns: df[c] = None
    df["ClienteID"] = pd.to_numeric(df["ClienteID"], errors="coerce").astype("Int64")
    return df[EXPECTED_CLIENTI_COLS]

def sanitize_contracts_df(df) -> pd.DataFrame:
    if df is None: df = pd.DataFrame()
    if isinstance(df, pd.Series):
        df = df.to_frame().T
    elif isinstance(df, (list, dict)):
        df = pd.DataFrame(df)
    else:
        df = pd.DataFrame(df).copy()
    for c in SAFE_CONTRACT_COLS:
        if c not in df.columns:
            df[c] = 0.0 if c in ["NOL_FIN","NOL_INT","TotRata"] else ""
    df = df[[c for c in SAFE_CONTRACT_COLS]]
    for c in ["NOL_FIN","NOL_INT","TotRata"]:
        df[c] = df[c].apply(numify)
    for dcol in ["DataInizio","DataFine"]:
        df[dcol] = df[dcol].apply(fmt_date)
    df["Stato"] = df["Stato"].astype(str).replace({"nan":""})
    return df

# alias intestazioni da Excel/italiano
CONTRACT_ALIASES = {
    "NumeroContratto": ["NumeroContratto","N.CONTRATTO","N. CONTRATTO","N_CONTRATTO","NUMERO CONTRATTO","NUM_CONTRATTO"],
    "DataInizio":      ["DataInizio","DATA INIZIO","DATA_INIZIO","DATAINIZIO","Data inizio"],
    "DataFine":        ["DataFine","DATA FINE","DATA_FINE","DATAFINE","Data fine"],
    "Durata":          ["Durata","DURATA"],
    "DescrizioneProdotto": ["DescrizioneProdotto","DESCRIZIONE PRODOTTO","Descrizione prodotto","DESCRIZIONE"],
    "NOL_FIN":         ["NOL_FIN","NOL. FIN.","NOL. FIN","CANONE FIN","FIN","NOL FIN"],
    "NOL_INT":         ["NOL_INT","NOL. INT.","NOL. INT","CANONE INT","INT","NOL INT"],
    "TotRata":         ["TotRata","TOT. RATA","TOT RATA","RATA","RATA MENSILE","TOT_RATE","TOTALE RATA"],
    "Stato":           ["Stato","CTR Chiuso","STATO","STATO CONTRATTO"]
}

def normalize_contract_headers(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=["ClienteID"] + SAFE_CONTRACT_COLS)

    df = pd.DataFrame(raw).copy()
    if "ClienteID" not in df.columns:
        df["ClienteID"] = np.nan

    out = {}
    for std, aliases in CONTRACT_ALIASES.items():
        found = None
        for a in aliases:
            if a in df.columns:
                found = a; break
        out[std] = df[found] if found else np.nan

    out_df = pd.DataFrame(out)
    out_df.insert(0, "ClienteID", pd.to_numeric(df.get("ClienteID", np.nan), errors="coerce").astype("Int64"))

    # normalizzo numero contratto (tolgo eventuale "+")
    out_df["NumeroContratto"] = (
        out_df["NumeroContratto"].astype(str).str.strip().str.replace(r"^\+", "", regex=True)
    )
    out_df["DataInizio"] = out_df["DataInizio"].apply(fmt_date)
    out_df["DataFine"]   = out_df["DataFine"].apply(fmt_date)
    for c in ["NOL_FIN","NOL_INT","TotRata"]:
        out_df[c] = out_df[c].apply(numify)
    out_df["Stato"] = out_df["Stato"].astype(str).str.strip().str.lower().replace({"nan":"", "":""})
    out_df["Stato"] = out_df["Stato"].replace({"chiuso":"chiuso","aperto":"aperto","sospeso":"sospeso"})

    tot_calc = out_df.apply(compute_tot, axis=1)
    need_fix = (out_df["TotRata"].isna()
                | (out_df["TotRata"].apply(numify)==0)
                | ((out_df["TotRata"].apply(numify) - tot_calc).abs() > 0.01))
    out_df.loc[need_fix, "TotRata"] = tot_calc

    out_df = out_df[["ClienteID"] + SAFE_CONTRACT_COLS]
    return out_df

def ensure_contratti_cols(df) -> pd.DataFrame:
    df_norm = normalize_contract_headers(pd.DataFrame(df))
    core = sanitize_contracts_df(df_norm.drop(columns=["ClienteID"]))
    out = pd.concat([df_norm[["ClienteID"]].reset_index(drop=True),
                     core.reset_index(drop=True)], axis=1)
    return out[["ClienteID"] + SAFE_CONTRACT_COLS]

# ---------------- Load/save CSV ----------------
@st.cache_data
def load_csv_with_fallback(main_path, fallbacks):
    p = Path(main_path)
    if p.exists(): return pd.read_csv(p)
    for fb in fallbacks:
        if Path(fb).exists(): return pd.read_csv(fb)
    return pd.DataFrame()

@st.cache_data
def load_data():
    clienti = load_csv_with_fallback("clienti.csv",
             ["clienti_batch1.csv","clienti_normalizzati.csv","preview_clienti.csv"])
    clienti = ensure_clienti_cols(clienti)

    contratti = load_csv_with_fallback("contratti.csv",
              ["contratti_batch1.csv","contratti_normalizzati.csv","preview_contratti.csv"])
    contratti = ensure_contratti_cols(contratti)

    tot_calc = contratti.apply(compute_tot, axis=1)
    need_fix = (
        contratti["TotRata"].isna()
        | (contratti["TotRata"].apply(numify)==0)
        | ((contratti["TotRata"].apply(numify) - tot_calc).abs() > 0.01)
    )
    contratti.loc[need_fix, "TotRata"] = tot_calc
    return clienti, contratti

def save_csv(df, path): df.to_csv(path, index=False)

# ---------------- Storage (Local / S3 / Dropbox) ----------------
class StorageBase:
    def upload(self, key:str, data:bytes): raise NotImplementedError
    def list(self, prefix:str): raise NotImplementedError
    def download(self, key:str)->bytes: raise NotImplementedError

class LocalStorage(StorageBase):
    def __init__(self, base_dir="allegati"):
        self.base = Path(base_dir); self.base.mkdir(exist_ok=True)
    def upload(self, key, data):
        p = self.base / key; p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f: f.write(data)
    def list(self, prefix):
        folder = self.base / prefix
        if not folder.exists(): return []
        return [str(Path(prefix)/f.name) for f in folder.iterdir() if f.is_file()]
    def download(self, key):
        return (self.base / key).read_bytes()

class S3Storage(StorageBase):
    def __init__(self):
        import boto3
        self.bucket = os.environ["S3_BUCKET"]
        self.prefix = os.environ.get("S3_PREFIX","")
        self.s3 = boto3.client("s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_DEFAULT_REGION"))
    def _fullkey(self, key): return f"{self.prefix}/{key}" if self.prefix else key
    def upload(self, key, data): self.s3.put_object(Bucket=self.bucket, Key=self._fullkey(key), Body=data)
    def list(self, prefix):
        full = self._fullkey(prefix)
        resp = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=full)
        if "Contents" not in resp: return []
        keys=[]
        for obj in resp["Contents"]:
            k = obj["Key"]
            if k.endswith("/"): continue
            keys.append(k[len(self.prefix)+1:] if self.prefix and k.startswith(self.prefix+"/") else k)
        return keys
    def download(self, key):
        obj = self.s3.get_object(Bucket=self.bucket, Key=self._fullkey(key))
        return obj["Body"].read()

class DropboxStorage(StorageBase):
    def __init__(self):
        import dropbox
        self.dbx = dropbox.Dropbox(os.environ["DROPBOX_TOKEN"])
        self.prefix = os.environ.get("DROPBOX_PREFIX","/allegati")
        if not self.prefix.startswith("/"): self.prefix="/"+self.prefix
    def _full(self, key): return f"{self.prefix}/{key}".replace("//","/")
    def upload(self, key, data):
        import dropbox
        self.dbx.files_upload(data, self._full(key), mode=dropbox.files.WriteMode("overwrite"))
    def list(self, prefix):
        path = self._full(prefix)
        try: res = self.dbx.files_list_folder(path)
        except Exception: return []
        return [f"{prefix}/{e.name}".replace("//","/") for e in res.entries if hasattr(e,"name")]
    def download(self, key):
        meta, resp = self.dbx.files_download(self._full(key))
        return resp.content

def make_storage():
    backend = os.environ.get("STORAGE_BACKEND","local").lower()
    try:
        if backend=="s3": return S3Storage()
        if backend=="dropbox": return DropboxStorage()
    except Exception as e:
        st.warning(f"Storage {backend} non inizializzato: {e}. Uso locale.")
    return LocalStorage()

STORAGE = make_storage()
PREVENTIVI_CSV = "preventivi.csv"

@st.cache_data
def load_preventivi():
    p = Path(PREVENTIVI_CSV)
    if p.exists(): df = pd.read_csv(p)
    else: df = pd.DataFrame(columns=["NumeroPrev","ClienteID","Data","Template","FileName","Key"])
    if "ClienteID" in df.columns:
        df["ClienteID"] = pd.to_numeric(df["ClienteID"], errors="coerce").astype("Int64")
    return df
def save_preventivi(df): df.to_csv(PREVENTIVI_CSV, index=False)
def next_quote_number(df_prev: pd.DataFrame) -> str:
    yy = date.today().strftime("%Y")
    prefix = f"PRV-{yy}-"
    if df_prev.empty or "NumeroPrev" not in df_prev.columns: return prefix + "0001"
    mask = df_prev["NumeroPrev"].fillna("").astype(str).str.startswith(prefix)
    if not mask.any(): return prefix + "0001"
    last = sorted(df_prev.loc[mask,"NumeroPrev"].astype(str))[-1]
    n = int(last.split("-")[-1])
    return f"{prefix}{n+1:04d}"

# ---------------- Word template replace ----------------
def _replace_in_paragraph(paragraph, mapping: dict):
    for k, v in mapping.items():
        if k in paragraph.text:
            inline = paragraph.runs
            text = paragraph.text.replace(k, v)
            for i in range(len(inline)-1, -1, -1):
                paragraph.runs[i].clear()
            paragraph.text = text
def _replace_in_table(table, mapping: dict):
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                _replace_in_paragraph(paragraph, mapping)
def fill_docx_template(template_bytes: bytes, mapping: dict) -> bytes:
    tmp = io.BytesIO(template_bytes)
    doc = Document(tmp)
    for p in doc.paragraphs: _replace_in_paragraph(p, mapping)
    for t in doc.tables: _replace_in_table(t, mapping)
    out = io.BytesIO(); doc.save(out); return out.getvalue()

# ---------------- Auth minima ----------------
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
        else: st.error("Credenziali non valide.")

if "auth_user" not in st.session_state:
    do_login(); st.stop()
role = st.session_state.get("auth_role","Viewer")
editable = role in ["Admin","Operatore"]

# ---------------- Helper UI ----------------
def show_html(html: str, **kw):
    if hasattr(st, "html"): st.html(html, **kw)
    else: st.markdown(html, unsafe_allow_html=True)

PAGES = ["Dashboard","Clienti","Contratti","Impostazioni"]
if "sidebar_page" not in st.session_state: st.session_state["sidebar_page"] = "Clienti"
def go_to(page_name: str):
    st.session_state["sidebar_page"] = page_name
    st.rerun()

# ---------------- Stato ----------------
clienti, contratti = load_data()
st.session_state.setdefault("clienti", clienti.copy())
st.session_state.setdefault("contratti", contratti.copy())
st.session_state.setdefault("selected_client_id", int(clienti["ClienteID"].min()) if len(clienti) else 1)

# ---------------- Metriche ----------------
def monthly_revenue_open_client(df_ctr, cid):
    df = df_ctr[(df_ctr["ClienteID"]==int(cid)) & (df_ctr["Stato"].str.lower()=="aperto")]
    return float(df["TotRata"].sum())
def monthly_revenue_all_client(df_ctr, cid):
    df = df_ctr[df_ctr["ClienteID"]==int(cid)]
    return float(df["TotRata"].sum())
def monthly_revenue_open_all(df_ctr):
    df = df_ctr[df_ctr["Stato"].str.lower()=="aperto"]
    return float(df["TotRata"].sum())

# ---------------- HTML Tabella contratti ----------------
def contracts_html(df):
    df = sanitize_contracts_df(df).copy()
    df = df.where(df.notna(), "")
    for c in df.columns:
        df[c] = df[c].apply(lambda x: "" if str(x).strip().lower()=="nan" else x)
    css = """
    <style>
      .ctr-table { width:100%; border-collapse:collapse; font-size:0.95rem; }
      .ctr-table th, .ctr-table td { border:1px solid #eee; padding:8px 10px; }
      .ctr-table th { background:#f7f7f9; text-align:left; }
      .row-chiuso { background:#ffecec; color:#7a0b0b; }
    </style>
    """
    header = "".join(f"<th>{c}</th>" for c in SAFE_CONTRACT_COLS)
    if df.empty:
        return css + '<table class="ctr-table"><thead><tr>'+header+'</tr></thead>' \
               + '<tbody><tr><td colspan="9" style="text-align:center;color:#777;">Nessun contratto</td></tr></tbody></table>'
    df2 = df.copy()
    for c in ["NOL_FIN","NOL_INT","TotRata"]:
        if c in df2.columns: df2[c] = df2[c].apply(lambda v: euro(v) if numify(v)!=0 else "")
    rows=[]
    for _, r in df2.iterrows():
        stato=(str(r.get("Stato","")) or "").strip().lower()
        cls = "row-chiuso" if stato=="chiuso" else ""
        cells="".join(f"<td>{r.get(c,'') or ''}</td>" for c in SAFE_CONTRACT_COLS)
        rows.append(f"<tr class='{cls}'>{cells}</tr>")
    return css + '<table class="ctr-table"><thead><tr>'+header+'</tr></thead><tbody>' \
           + "\n".join(rows) + "</tbody></table>"

# ---------------- Dashboard ----------------
def render_dashboard():
    st.title("📊 Dashboard")
    c1,c2,c3 = st.columns(3)
    c1.metric("Clienti", len(st.session_state["clienti"]))
    c2.metric("Contratti", len(st.session_state["contratti"]))
    c3.metric("Rata mensile (aperti)", euro(monthly_revenue_open_all(
        ensure_contratti_cols(st.session_state["contratti"])
    )))
    st.subheader("Promemoria in arrivo (30 giorni)")
    cli = ensure_clienti_cols(st.session_state["clienti"]).copy()
    today = date.today(); horizon = date.fromordinal(today.toordinal()+30)
    cli["PR_dt"] = cli["ProssimoRecall"].apply(parse_date_safe)
    cli["PV_dt"] = cli["ProssimaVisita"].apply(parse_date_safe)
    def in_range(d): return isinstance(d, date) and (today <= d <= horizon)
    mask = cli["PR_dt"].apply(in_range) | cli["PV_dt"].apply(in_range)
    upcoming = cli.loc[mask, ["ClienteID","RagioneSociale","ProssimoRecall","ProssimaVisita"]] \
                 .sort_values(by=["ProssimoRecall","ProssimaVisita"], na_position="last")
    st.dataframe(upcoming, use_container_width=True)

# ---------------- Clienti (anagrafica + promemoria + preventivi) ----------------
def render_clienti():
    clienti  = ensure_clienti_cols(st.session_state["clienti"])
    ct       = ensure_contratti_cols(st.session_state["contratti"])

    st.title("👥 Clienti")

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
                row = {"ClienteID":int(new_id),"RagioneSociale":rs,"NomeCliente":nome,"Indirizzo":ind,"Città":citta,
                       "CAP":cap,"Telefono":tel,"Email":mail,"PartitaIVA":piva,"IBAN":iban,"SDI":sdi,
                       "UltimoRecall":"","ProssimoRecall":"","UltimaVisita":"","ProssimaVisita":"","Note":note}
                st.session_state["clienti"] = pd.concat([clienti, pd.DataFrame([row])], ignore_index=True)
                st.success("Cliente creato. Ricorda di salvare.")

    with st.expander("🗑️ Elimina cliente", expanded=False):
        ids = clienti["ClienteID"].astype(int).tolist()
        del_id = st.selectbox("Seleziona ClienteID da eliminare", ids) if ids else None
        if st.button("Elimina definitivamente", disabled=(not editable or del_id is None)):
            st.session_state["clienti"]   = clienti[clienti["ClienteID"].astype(int)!=int(del_id)]
            st.session_state["contratti"] = ct[ct["ClienteID"].astype(int)!=int(del_id)]
            st.warning("Cliente e relativi contratti eliminati. Ricorda di salvare.")

    if len(clienti)==0: st.info("Nessun cliente presente."); return

    # selezione cliente memorizzata (riusata in 'Contratti')
    det_id = st.number_input("Apri scheda ClienteID",
                             min_value=int(clienti["ClienteID"].min()),
                             max_value=int(clienti["ClienteID"].max()),
                             value=int(st.session_state["selected_client_id"]),
                             step=1)
    st.session_state["selected_client_id"] = int(det_id)

    dettaglio = clienti[clienti["ClienteID"]==int(det_id)]
    if dettaglio.empty: st.info("Cliente non trovato."); return
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

    with st.expander("📝 Note cliente", expanded=bool(c["Note"])):
        new_note = st.text_area("Note", value=str(c["Note"] or ""), height=120)
        if st.button("Aggiorna note", disabled=not editable, key=f"upd_note_{det_id}"):
            mask = st.session_state["clienti"]["ClienteID"].astype(int)==int(det_id)
            st.session_state["clienti"].loc[mask, "Note"] = new_note
            st.success("Note aggiornate. Ricorda di salvare (💾).")

    # PROMEMORIA
    with st.expander("🔔 Promemoria cliente (recall / visite)", expanded=False):
        colp1, colp2 = st.columns(2)
        with colp1: pross_recall = st.date_input("Prossimo Recall", value=None, key=f"recall_{det_id}")
        with colp2: pross_visita = st.date_input("Prossima Visita", value=None, key=f"visita_{det_id}")
        if st.button("Aggiorna promemoria", disabled=not editable, key=f"upd_prom_{det_id}"):
            mask = st.session_state["clienti"]["ClienteID"].astype(int)==int(det_id)
            st.session_state["clienti"].loc[mask,"ProssimoRecall"] = fmt_date(pross_recall) if pross_recall else ""
            st.session_state["clienti"].loc[mask,"ProssimaVisita"] = fmt_date(pross_visita) if pross_visita else ""
            st.success("Promemoria aggiornati. Ricorda di salvare (💾).")

    # PREVENTIVI (colonna sx lista, colonna dx azioni)
    st.subheader("🧾 Preventivi")
    c_left, c_right = st.columns([0.45, 0.55])

    with c_left:
        df_prev_all = load_preventivi()
        df_prev_cli = df_prev_all[df_prev_all["ClienteID"]==int(det_id)].sort_values("Data", ascending=False)
        st.markdown("**Storico preventivi**")
        if len(df_prev_cli):
            for _, rowp in df_prev_cli.iterrows():
                key=rowp["Key"]
                try:
                    data = STORAGE.download(key)
                    st.write(f"• **{rowp['NumeroPrev']}** — {rowp['Data']} — {rowp['FileName']}")
                    st.download_button("⬇️", data=data, file_name=rowp["FileName"], key=f"dl_prev2_{rowp['FileName']}")
                except Exception as e:
                    st.warning(f"File non disponibile: {key} ({e})")
        else:
            st.info("Nessun preventivo per questo cliente.")

    with c_right:
        st.write("Carica un **template .docx** (segnaposto <<...>> o {{...}}) e genera il preventivo.")
        tmpl = st.file_uploader("Template .docx", type=["docx"], key=f"tmpl_{det_id}")
        df_prev = load_preventivi()
        prossimo_num = next_quote_number(df_prev)
        rif_pers = st.text_input("Riferimento/Contatto", value=str(c["NomeCliente"] or ""))
        if st.button("Genera preventivo", disabled=(tmpl is None)):
            mapping = {
                "<<CLIENTE>>":           str(c["RagioneSociale"] or ""),
                "<<INDIRIZZO>>":         str(c["Indirizzo"] or ""),
                "<<CITTA>>":             str(c["Città"] or ""),
                "<<CAP>>":               str(c["CAP"] or ""),
                "<<RIFERIMENTO>>":       rif_pers or "",
                "<<NUMERO_OFFERTA>>":    prossimo_num,
                "<<DATA>>":              fmt_date(date.today()),
                "{{RAGIONE_SOCIALE}}":   str(c["RagioneSociale"] or ""),
                "{{CLIENTE_ID}}":        str(int(det_id)),
                "{{DATA}}":              fmt_date(date.today()),
                "{{NUMERO_PREVENTIVO}}": prossimo_num,
                "{{INDIRIZZO}}":         str(c["Indirizzo"] or ""),
                "{{CITTA}}":             str(c["Città"] or ""),
                "{{CAP}}":               str(c["CAP"] or ""),
                "{{RIFERIMENTO}}":       rif_pers or "",
            }
            out_bytes = fill_docx_template(tmpl.getbuffer(), mapping)
            key = f"CLI-{det_id}/PREVENTIVI/{prossimo_num}__CLI-{det_id}.docx"
            STORAGE.upload(key, out_bytes)
            rec = {"NumeroPrev":prossimo_num,"ClienteID":int(det_id),"Data":fmt_date(date.today()),
                   "Template":tmpl.name,"FileName":key.split("/")[-1],"Key":key}
            df_prev = pd.concat([df_prev, pd.DataFrame([rec])], ignore_index=True)
            save_preventivi(df_prev)
            st.success(f"Preventivo generato: {rec['FileName']}")
            st.download_button("⬇️ Scarica", data=out_bytes, file_name=rec["FileName"], key=f"dl_prev_{rec['FileName']}")

    st.write("---")
    colS1,colS2 = st.columns(2)
    if colS1.button("💾 Salva clienti adesso"):
        save_csv(ensure_clienti_cols(st.session_state["clienti"]), "clienti.csv"); st.success("clienti.csv salvato.")
    if colS2.button("➡️ Vai alla gestione contratti di questo cliente"):
        go_to("Contratti")

# ---------------- Contratti (solo gestione) ----------------
def render_contratti():
    clienti = ensure_clienti_cols(st.session_state["clienti"])
    ct      = ensure_contratti_cols(st.session_state["contratti"])
    st.title("📃 Contratti")

    if len(clienti)==0: st.info("Nessun cliente caricato."); return

    # cliente preselezionato dalla pagina "Clienti"
    opts = [(int(cid), nm if pd.notna(nm) else "") for cid,nm in zip(clienti["ClienteID"], clienti["RagioneSociale"])]
    labels = [f"{cid} — {nm}" for cid,nm in opts]
    def _lbl(cid): 
        row = clienti[clienti["ClienteID"]==cid]
        if row.empty: return labels[0]
        return f"{cid} — {row.iloc[0]['RagioneSociale']}"
    default_label = _lbl(int(st.session_state["selected_client_id"])) if len(labels) else "(seleziona)"
    choice = st.selectbox("Cliente", labels, index=labels.index(default_label) if default_label in labels else 0)
    sel_cid = int(str(choice).split(" — ")[0])
    st.session_state["selected_client_id"] = sel_cid

    df_cli = ct[ct["ClienteID"]==sel_cid].copy()
    st.markdown("**Elenco contratti (rosso = chiusi)**")
    show_html(contracts_html(df_cli), height=min(460, 120 + 28*len(df_cli)))

    # Export / Stampa
    with st.expander("📤 Esporta / Stampa (selezione)", expanded=False):
        nums = df_cli["NumeroContratto"].astype(str).tolist()
        sel = st.multiselect("Numeri contratto da stampare (vuoto = tutti)", nums, default=[])
        df_sel = df_cli.copy()
        if sel: df_sel = df_sel[df_sel["NumeroContratto"].astype(str).isin(sel)]
        # Excel
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine="openpyxl") as writer:
            df_sel[SAFE_CONTRACT_COLS].to_excel(writer, index=False, sheet_name="Contratti")
        st.download_button("⬇️ Esporta Excel", data=b.getvalue(),
                           file_name=f"contratti_CLI-{sel_cid}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        # PDF
        def pdf_bytes(ragione, df):
            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
            styles = getSampleStyleSheet()
            story = [Paragraph(f"<b>{ragione}</b>", styles["Title"]), Spacer(1,12),
                     Paragraph("Contratti", styles["h2"]), Spacer(1,6)]
            data = [SAFE_CONTRACT_COLS] + df[SAFE_CONTRACT_COLS].astype(str).values.tolist()
            tbl = Table(data, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 0.25, colors.grey),
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2f2f7")),
                ("ALIGN", (0,0), (-1,0), "LEFT"),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0), (-1,-1), 9),
            ]))
            story.append(tbl); doc.build(story); return buf.getvalue()
        rag = clienti.loc[clienti["ClienteID"]==sel_cid, "RagioneSociale"].values[0]
        st.download_button("🖨️ Stampa PDF", data=pdf_bytes(rag, df_sel),
                           file_name=f"contratti_CLI-{sel_cid}.pdf", mime="application/pdf")

    # CRUD
    with st.expander("➕ Aggiungi contratto", expanded=False):
        with st.form("form_add_ctr"):
            col1,col2,col3 = st.columns(3)
            with col1:
                numero = st.text_input("Numero contratto", value=next_contract_number(df_cli, int(sel_cid)))
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
                new_row = {"ClienteID":int(sel_cid),"NumeroContratto":numero.strip(),
                           "DataInizio":fmt_date(d_in),"DataFine":fmt_date(d_fi),"Durata":durata,
                           "DescrizioneProdotto":descr,"NOL_FIN":numify(fin),"NOL_INT":numify(intr),
                           "TotRata":round(tot_val,2),"Stato":stato}
                st.session_state["contratti"] = pd.concat([ct, pd.DataFrame([new_row])], ignore_index=True)
                st.success("Contratto creato. Ricorda di salvare.")

    with st.expander("✏️ Modifica/Chiudi contratto", expanded=False):
        nums2 = df_cli["NumeroContratto"].astype(str).tolist()
        target = st.selectbox("Seleziona numero", nums2) if len(nums2)>0 else None
        if target:
            old = df_cli[df_cli["NumeroContratto"].astype(str)==str(target)].iloc[0]
            with st.form("form_edit_ctr"):
                col1,col2,col3 = st.columns(3)
                with col1:
                    d_in = st.date_input("Data inizio", value=parse_date_safe(old["DataInizio"]) or date.today())
                    d_fi = st.date_input("Data fine", value=parse_date_safe(old["DataFine"]) or date.today())
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
                    mask = (ct["ClienteID"].astype(int)==int(sel_cid)) & (ct["NumeroContratto"].astype(str)==str(target))
                    st.session_state["contratti"].loc[mask,
                        ["DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]] = \
                        [fmt_date(d_in), fmt_date(d_fi), durata, descr, numify(fin), numify(intr), round(tot_val,2), stato]
                    st.success("Contratto aggiornato. Ricorda di salvare.")
        else:
            st.info("Nessun contratto per questo cliente.")

    with st.expander("🗑️ Elimina contratto", expanded=False):
        n2 = df_cli["NumeroContratto"].astype(str).tolist()
        deln = st.selectbox("Numero contratto da eliminare", n2) if len(n2)>0 else None
        if st.button("Elimina questo contratto", disabled=(not editable or deln is None)):
            mask = ~((ct["ClienteID"].astype(int)==int(sel_cid)) & (ct["NumeroContratto"].astype(str)==str(deln)))
            st.session_state["contratti"] = ct[mask]
            st.warning("Contratto eliminato. Ricorda di salvare.")

    colS1,colS2 = st.columns(2)
    if colS1.button("💾 Salva contratti adesso"):
        save_csv(ensure_contratti_cols(st.session_state["contratti"]), "contratti.csv"); st.success("contratti.csv salvato.")
    if colS2.button("⬅️ Torna alla scheda cliente"):
        go_to("Clienti")

# ---------------- Impostazioni ----------------
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
        tmp = pd.read_csv(uc); st.session_state["clienti"] = ensure_clienti_cols(tmp)
        st.toast("Clienti caricati (ricordati di salvare).", icon="✅")
    ut = colB.file_uploader("Carica contratti.csv", type=["csv"])
    if ut is not None:
        tmp = pd.read_csv(ut); st.session_state["contratti"] = ensure_contratti_cols(tmp)
        st.toast("Contratti caricati (ricordati di salvare).", icon="✅")

# ---------------- Router ----------------
st.sidebar.title("CRM")
page = st.sidebar.radio("Naviga", PAGES, index=PAGES.index(st.session_state["sidebar_page"]),
                        key="sidebar_page")

if page=="Dashboard": render_dashboard()
elif page=="Clienti": render_clienti()
elif page=="Contratti": render_contratti()
else: render_settings()
