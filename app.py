# app.py — SHT – Gestione Clienti (Streamlit 1.50 compatibile)

from __future__ import annotations
from pathlib import Path
from datetime import date
from typing import Optional, Dict, List
from io import BytesIO

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from docx import Document

# ------------------------------------------------------------------------------
# Config
# ------------------------------------------------------------------------------
st.set_page_config(page_title="SHT – Gestione Clienti", page_icon="🧭", layout="wide")
APP_TITLE = "SHT – Gestione Clienti"

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
TEMPLATES_DIR = STORAGE_DIR / "templates"

STORAGE_DIR.mkdir(exist_ok=True, parents=True)
TEMPLATES_DIR.mkdir(exist_ok=True, parents=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"

# ------------------------------------------------------------------------------
# CSV default
# ------------------------------------------------------------------------------
def _default_clienti() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
        "Telefono","Email","PartitaIVA","IBAN","SDI",
        "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
    ])

def _default_contratti() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
        "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
    ])

def _default_preventivi() -> pd.DataFrame:
    return pd.DataFrame(columns=["ClienteID","Numero","Data","Template","FileSalvato","Note"])

# ------------------------------------------------------------------------------
# IO CSV
# ------------------------------------------------------------------------------
def load_csv(path: Path, default_df: pd.DataFrame) -> pd.DataFrame:
    if not path.exists():
        default_df.to_csv(path, index=False, encoding="utf-8")
        return default_df.copy()
    try:
        return pd.read_csv(path, dtype=str, encoding="utf-8").fillna("")
    except Exception:
        return default_df.copy()

def save_csv(df: pd.DataFrame, path: Path):
    df = df.fillna("")
    df.to_csv(path, index=False, encoding="utf-8")

def load_clienti() -> pd.DataFrame: return load_csv(CLIENTI_CSV, _default_clienti())
def load_contratti() -> pd.DataFrame: return load_csv(CONTRATTI_CSV, _default_contratti())
def load_preventivi() -> pd.DataFrame: return load_csv(PREVENTIVI_CSV, _default_preventivi())

# ------------------------------------------------------------------------------
# Util
# ------------------------------------------------------------------------------
def _today_str() -> str:
    t = date.today()
    return f"{t.day:02d}/{t.month:02d}/{t.year}"

def _fmt_eur(x) -> str:
    try:
        s = str(x).strip()
        if not s:
            return ""
        v = float(s.replace(",", "."))
        return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

def do_rerun(): st.rerun()

# ------------------------------------------------------------------------------
# Template placeholders
# ------------------------------------------------------------------------------
PLACEHOLDERS = {
    "RAGIONE_SOCIALE": "RagioneSociale",
    "RIFERIMENTO": "PersonaRiferimento",
    "INDIRIZZO": "Indirizzo",
    "CITTA": "Citta",
    "CAP": "CAP",
    "PIVA": "PartitaIVA",
    "IBAN": "IBAN",
    "SDI": "SDI",
    "TELEFONO": "Telefono",
    "EMAIL": "Email",
    "DATA": None,
    "NUMERO": None,
}

# --- sostituzione robusta (runs) nei .docx ------------------------------------
def _replace_in_paragraph(par, mapping: Dict[str, str]):
    # ricompongo il testo del paragrafo, poi riscrivo in un run
    full_text = "".join(run.text for run in par.runs)
    for ph, val in mapping.items():
        full_text = full_text.replace("{"+ph+"}", str(val))
    # reset
    if par.runs:
        par.runs[0].text = full_text
        for r in par.runs[1:]:
            r.text = ""
    else:
        par.add_run(full_text)

def _replace_in_table(table, mapping: Dict[str, str]):
    for row in table.rows:
        for cell in row.cells:
            # su cella iteriamo i paragrafi
            for p in cell.paragraphs:
                _replace_in_paragraph(p, mapping)

def fill_docx_template(tpl_path: Path, mapping: Dict[str, str], out_path: Path):
    doc = Document(tpl_path)
    for p in doc.paragraphs:
        _replace_in_paragraph(p, mapping)
    for t in doc.tables:
        _replace_in_table(t, mapping)
    doc.save(out_path)

# ------------------------------------------------------------------------------
# Login minimo (secrets opzionale)
# ------------------------------------------------------------------------------
def require_login():
    users = st.secrets.get("auth", {}).get("users", None)
    if not users:
        st.session_state.setdefault("user", "fabio")
        st.session_state.setdefault("role", "admin")
        return "fabio", "admin"

    if "user" in st.session_state and "role" in st.session_state:
        return st.session_state["user"], st.session_state["role"]

    st.info("Accedi per continuare")
    with st.form("f_login"):
        u = st.text_input("Utente")
        p = st.text_input("Password", type="password")
        ok = st.form_submit_button("Entra")
    if ok:
        if u in users and str(users[u].get("password","")) == str(p):
            st.session_state["user"] = u
            st.session_state["role"] = users[u].get("role", "viewer")
            st.success(f"Benvenuto, {u}!")
            do_rerun()
        else:
            st.error("Credenziali errate")
    st.stop()

def can_edit(role:str) -> bool:
    return role in ("admin","editor")

# ------------------------------------------------------------------------------
# Clienti helpers
# ------------------------------------------------------------------------------
def new_cliente_id(df_cli: pd.DataFrame) -> int:
    if df_cli.empty: return 1
    try: return int(df_cli["ClienteID"].astype(int).max())+1
    except: return 1

def upsert_cliente(df_cli: pd.DataFrame, row: dict, delete=False) -> pd.DataFrame:
    df2 = df_cli.copy()
    cid = str(row["ClienteID"])
    if delete:
        df2 = df2.loc[df2["ClienteID"].astype(str)!=cid]
    else:
        mask = df2["ClienteID"].astype(str)==cid
        if mask.any():
            for k,v in row.items(): df2.loc[mask,k]=str(v)
        else:
            df2 = pd.concat([df2, pd.DataFrame([row])], ignore_index=True)
    save_csv(df2, CLIENTI_CSV)
    return df2

# ------------------------------------------------------------------------------
# UI helpers
# ------------------------------------------------------------------------------
def header(t:str): st.markdown(f"## {t}")

def select_cliente(df_cli: pd.DataFrame, key="sel_cliente") -> Optional[dict]:
    if df_cli.empty:
        st.info("Nessun cliente.")
        return None
    df_cli = df_cli.copy()
    df_cli["__label"] = df_cli["ClienteID"].astype(str)+" — "+df_cli["RagioneSociale"].astype(str)
    labels = df_cli["__label"].tolist()

    default_label = None
    if "cliente_corrente_id" in st.session_state:
        try:
            cid = int(st.session_state["cliente_corrente_id"])
            r = df_cli.loc[df_cli["ClienteID"].astype(int)==cid]
            if not r.empty:
                default_label = f"{cid} — {r.iloc[0]['RagioneSociale']}"
        except:
            pass
    idx = labels.index(default_label) if default_label in labels else 0
    sel = st.selectbox("Cliente", labels, index=idx, key=key)
    cid = int(sel.split(" — ")[0])
    st.session_state["cliente_corrente_id"] = cid
    return df_cli.loc[df_cli["ClienteID"].astype(int)==cid].iloc[0].to_dict()

# ------------------------------------------------------------------------------
# Preventivi
# ------------------------------------------------------------------------------
def next_prev_number(df_prev: pd.DataFrame, cliente_id:int)->int:
    try:
        df = df_prev.loc[df_prev["ClienteID"].astype(str)==str(cliente_id)]
        if df.empty: return 1
        return int(df["Numero"].astype(int).max())+1
    except: return 1

def preventivi_panel(cliente:dict, role:str, df_prev:pd.DataFrame):
    st.markdown("### 🧾 Preventivi")
    my = df_prev.loc[df_prev["ClienteID"].astype(str)==str(cliente["ClienteID"])].copy()
    if not my.empty:
        my = my.sort_values(["Data","Numero"], ascending=[False,False])
        st.markdown("#### Elenco")
        for _, r in my.iterrows():
            file_name = r.get("FileSalvato","")
            path = (TEMPLATES_DIR/file_name) if file_name else None
            c = st.columns([4,2,3,2])
            c[0].write(f"**N° {r['Numero']}** – {r['Template']}")
            c[1].write(r.get("Data",""))
            c[2].write(file_name or "")
            if path and path.exists():
                with open(path,"rb") as f:
                    c[3].download_button("⬇️ Scarica", f.read(), file_name=file_name,
                                         mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                         key=f"dl_prev_{r['Numero']}")
            else:
                c[3].warning("file assente")

    st.markdown("---")
    tpls = [p.name for p in TEMPLATES_DIR.glob("*.docx")]
    if not tpls:
        st.info("Carica i template .docx in storage/templates/")
        return
    tpl = st.selectbox("Template", tpls, index=0)
    nro = st.number_input("Numero", min_value=1, step=1, value=next_prev_number(df_prev,int(cliente["ClienteID"])))
    data_p = st.text_input("Data", _today_str())
    if st.button("📄 Genera preventivo (Word)"):
        mapping={}
        for ph, fld in PLACEHOLDERS.items():
            if fld is None:
                mapping[ph] = data_p if ph=="DATA" else str(nro)
            else:
                mapping[ph] = str(cliente.get(fld,""))
        out_name = f"PREV_{cliente['ClienteID']}_{nro}.docx"
        out_path = TEMPLATES_DIR/out_name
        fill_docx_template(TEMPLATES_DIR/tpl, mapping, out_path)

        df2 = df_prev.copy()
        df2 = pd.concat([df2, pd.DataFrame([{
            "ClienteID":str(cliente["ClienteID"]),
            "Numero":str(nro),"Data":data_p,
            "Template":tpl,"FileSalvato":out_name,"Note":""
        }])], ignore_index=True)
        save_csv(df2, PREVENTIVI_CSV)
        st.success(f"Preventivo creato in storage/templates/{out_name}")
        with open(out_path,"rb") as f:
            st.download_button("⬇️ Scarica preventivo", f, file_name=out_name)
        do_rerun()

# ------------------------------------------------------------------------------
# HTML table (righe rosse per 'chiuso') + stampa
# ------------------------------------------------------------------------------
CSS_TABLE = """
<style>
.tbl {width:100%; border-collapse:collapse; font-family:system-ui, sans-serif; font-size:13px}
.tbl th, .tbl td {border:1px solid #ddd; padding:6px 8px; text-align:left}
.tbl thead th {background:#e3f2fd; font-weight:700}
.tbl tr.closed {background:#ffe5e5}
.title {text-align:center; font-weight:700; font-size:18px; margin:10px 0}
.sub {text-align:center; color:#555; margin-bottom:10px}
</style>
"""

def contracts_html(df: pd.DataFrame, client_name:str) -> str:
    cols = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    df = df.copy()
    for c in ("NOL_FIN","NOL_INT","TotRata"):
        if c in df.columns: df[c]=df[c].apply(_fmt_eur)
    rows=[]
    for _,r in df.iterrows():
        cls = "closed" if str(r.get("Stato","")).strip().lower()=="chiuso" else ""
        vals=[r.get(c,"") for c in cols]
        tds="".join(f"<td>{str(v)}</td>" for v in vals)
        rows.append(f"<tr class='{cls}'>{tds}</tr>")
    header = "".join(f"<th>{c}</th>" for c in cols)
    html = f"""{CSS_TABLE}
<div class="title">{client_name}</div>
<div class="sub">Contratti (rossi = chiusi)</div>
<table class="tbl">
<thead><tr>{header}</tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
"""
    return html

# stampa-selezione: restituisce html pronto
def contracts_html_selection(df: pd.DataFrame, client_name:str) -> str:
    return contracts_html(df, client_name)

# ------------------------------------------------------------------------------
# Excel con intestazione centrata + header colorato
# ------------------------------------------------------------------------------
def export_excel_styled(df: pd.DataFrame, client_name: str) -> bytes:
    out=BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as xw:
        sh_name="Contratti"
        # scrivo a partire dalla riga 4 per lasciare spazio al titolo
        df.to_excel(xw, sheet_name=sh_name, index=False, startrow=4)
        wb = xw.book
        ws = xw.sheets[sh_name]
        # titolo
        title_fmt = wb.add_format({"bold":True,"align":"center","valign":"vcenter","font_size":14})
        ws.merge_range(0,0,2,df.shape[1]-1, client_name, title_fmt)
        # header
        header_fmt = wb.add_format({"bold":True,"bg_color":"#E3F2FD","border":1})
        for col, name in enumerate(df.columns):
            ws.write(4, col, name, header_fmt)
        # formato euro
        money = wb.add_format({"num_format":"€ #,##0.00"})
        for col_name in ("NOL_FIN","NOL_INT","TotRata"):
            if col_name in df.columns:
                col_idx = list(df.columns).index(col_name)
                ws.set_column(col_idx, col_idx, 14, money)
        ws.set_column(0, df.shape[1]-1, 20)  # larghezze di base
    out.seek(0)
    return out.read()

# ------------------------------------------------------------------------------
# Pagine
# ------------------------------------------------------------------------------
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("👥 Clienti")

    # — Aggiungi
    with st.expander("➕ Aggiungi nuovo cliente", expanded=False):
        c1,c2 = st.columns(2)
        with c1:
            rag = st.text_input("Ragione Sociale *")
            rif = st.text_input("Persona di riferimento")
            ind = st.text_input("Indirizzo")
            citta = st.text_input("Città")
            cap = st.text_input("CAP")
            tel = st.text_input("Telefono")
            email = st.text_input("Email")
        with c2:
            piva = st.text_input("Partita IVA")
            iban = st.text_input("IBAN")
            sdi = st.text_input("SDI")
            ult_rec = st.text_input("Ultimo Recall (dd/mm/aaaa)")
            pro_rec = st.text_input("Prossimo Recall (dd/mm/aaaa)")
            ult_vis = st.text_input("Ultima Visita (dd/mm/aaaa)")
            pro_vis = st.text_input("Prossima Visita (dd/mm/aaaa)")
        note_new = st.text_area("Note")

        if can_edit(role) and st.button("💾 Crea cliente"):
            if not rag.strip():
                st.error("Ragione Sociale obbligatoria")
            else:
                cid = new_cliente_id(df_cli)
                row = {
                    "ClienteID":str(cid),"RagioneSociale":rag,"PersonaRiferimento":rif,"Indirizzo":ind,
                    "Citta":citta,"CAP":cap,"Telefono":tel,"Email":email,"PartitaIVA":piva,"IBAN":iban,"SDI":sdi,
                    "UltimoRecall":ult_rec,"ProssimoRecall":pro_rec,"UltimaVisita":ult_vis,"ProssimaVisita":pro_vis,
                    "Note":note_new
                }
                upsert_cliente(df_cli,row)
                st.session_state["cliente_corrente_id"]=cid
                st.success("Cliente creato.")
                do_rerun()

    # — Scheda
    cliente = select_cliente(df_cli, key="cli_page")
    if not cliente: return

    st.markdown("#### Anagrafica")
    L,R = st.columns(2)
    with L:
        st.write(f"**Ragione Sociale**: {cliente['RagioneSociale']}")
        st.write(f"**Persona di riferimento**: {cliente.get('PersonaRiferimento','')}")
        st.write(f"**Indirizzo**: {cliente.get('Indirizzo','')}")
        st.write(f"**Città**: {cliente.get('Citta','')}  **CAP**: {cliente.get('CAP','')}")
        st.write(f"**Telefono**: {cliente.get('Telefono','')}")
        st.write(f"**Email**: {cliente.get('Email','')}")
    with R:
        st.write(f"**P.IVA**: {cliente.get('PartitaIVA','')}")
        st.write(f"**IBAN**: {cliente.get('IBAN','')}")
        st.write(f"**SDI**: {cliente.get('SDI','')}")
        st.write(f"**Ultimo Recall**: {cliente.get('UltimoRecall','')}")
        st.write(f"**Prossimo Recall**: {cliente.get('ProssimoRecall','')}")
        st.write(f"**Ultima Visita**: {cliente.get('UltimaVisita','')}")
        st.write(f"**Prossima Visita**: {cliente.get('ProssimaVisita','')}")

    # NOTE — box dedicato
    st.markdown("#### 📝 Note cliente")
    note_curr = st.text_area("Note", value=str(cliente.get("Note","")), height=120, key="note_box")
    if can_edit(role) and st.button("💾 Salva note"):
        r = cliente.copy()
        r["Note"]=note_curr
        upsert_cliente(df_cli, r)
        st.success("Note aggiornate.")

    # Modifica/Elimina completo (se necessario)
    with st.expander("✏️ Modifica / 🗑️ Elimina anagrafica", expanded=False):
        cols = _default_clienti().columns.tolist()
        row={}
        for c in cols:
            row[c]=st.text_input(c, value=str(cliente.get(c,"")), key=f"edit_{c}")
        cL,cR = st.columns(2)
        with cL:
            if can_edit(role) and st.button("💾 Salva anagrafica"):
                upsert_cliente(df_cli,row)
                st.success("Anagrafica aggiornata.")
                do_rerun()
        with cR:
            if can_edit(role) and st.button("🗑️ Elimina cliente"):
                upsert_cliente(df_cli,row,delete=True)
                st.session_state.pop("cliente_corrente_id",None)
                st.success("Cliente eliminato.")
                do_rerun()

    st.markdown("---")
    if st.button("➡️ Vai alla gestione contratti di questo cliente"):
        st.session_state["nav_page"]="Contratti"
        do_rerun()

    # Preventivi
    preventivi_panel(cliente, st.session_state.get("role","viewer"), load_preventivi())

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("📑 Contratti (rosso = chiusi)")

    cliente = select_cliente(df_cli, key="cli_in_contratti")
    if not cliente: return

    cid = int(cliente["ClienteID"])
    rag_soc = cliente["RagioneSociale"]
    ct_cli = df_ct.loc[df_ct["ClienteID"].astype(str)==str(cid)].copy()

    st.markdown("#### Elenco (tabella semplice)")
    df_show = ct_cli.copy()
    for c in ("NOL_FIN","NOL_INT","TotRata"):
        if c in df_show.columns: df_show[c]=df_show[c].apply(_fmt_eur)
    st.dataframe(df_show[["NumeroContratto","DataInizio","DataFine","Durata",
                          "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]],
                 use_container_width=True)

    # tabella HTML con righe rosse
    st.markdown("#### Vista con evidenza chiusi")
    html = contracts_html(ct_cli, rag_soc)
    height = 180 + 28*len(ct_cli)
    components.html(html, height=max(220, min(height, 900)))  # render sicuro

    # selezione righe
    st.markdown("#### Seleziona righe per stampa/esportazione")
    # id riga sicuro anche quando NumeroContratto è vuoto
    ct_cli = ct_cli.reset_index(drop=True)
    ct_cli["__RID"] = ct_cli.index.astype(str)
    labels = (ct_cli["NumeroContratto"].replace("", "(senza numero)") + " — " +
              ct_cli["DescrizioneProdotto"].str.slice(0,60)).tolist()
    rid_to_label = dict(zip(ct_cli["__RID"], labels))
    sel = st.multiselect("Righe", options=ct_cli["__RID"].tolist(),
                         default=ct_cli["__RID"].tolist(), format_func=lambda r: rid_to_label[r])

    sel_df = ct_cli.loc[ct_cli["__RID"].isin(sel)].drop(columns=["__RID"])

    c1,c2,c3 = st.columns(3)
    with c1:
        # stampa = HTML pronto → PDF da browser
        if st.button("🖨️ Stampa selezionati (HTML)"):
            html_print = contracts_html_selection(sel_df, rag_soc)
            components.html(html_print, height=220 + 28*len(sel_df))
            st.info("Usa il comando Stampa del browser per salvare in PDF.")
    with c2:
        # Excel styled
        xls = export_excel_styled(sel_df, rag_soc)
        st.download_button("⬇️ Esporta selezionati in Excel", data=xls,
                           file_name=f"contratti_{cid}_selezione.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c3:
        xls_all = export_excel_styled(ct_cli.drop(columns=["__RID"]), rag_soc)
        st.download_button("⬇️ Esporta tutti in Excel", data=xls_all,
                           file_name=f"contratti_{cid}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # CRUD contratti
    if not can_edit(role):
        st.warning("Solo Admin/Editor possono modificare i contratti.")
        return

    st.markdown("---")
    st.markdown("#### ➕ Aggiungi / ✏️ Modifica / 🗑️ Elimina contratto")

    a,b,c = st.columns(3)
    with a:
        numero = st.text_input("NumeroContratto")
        datainizio = st.text_input("DataInizio (dd/mm/aaaa)", value=_today_str())
        datafine = st.text_input("DataFine (dd/mm/aaaa)", value="")
        durata = st.text_input("Durata (es. 60 M)", value="")
    with b:
        descr = st.text_input("DescrizioneProdotto", value="")
        fin = st.text_input("NOL_FIN (mensile)", value="")
        intr = st.text_input("NOL_INT (mensile)", value="")
        tot = st.text_input("TotRata", value="")
    with c:
        stato = st.selectbox("Stato", ["aperto","chiuso"], index=0)

    cL,cR = st.columns(2)
    with cL:
        if st.button("💾 Salva/aggiorna"):
            df2 = df_ct.copy()
            mask = (df2["ClienteID"].astype(str)==str(cid)) & (df2["NumeroContratto"].astype(str)==numero)
            row = {"ClienteID":str(cid),"NumeroContratto":numero,"DataInizio":datainizio,"DataFine":datafine,
                   "Durata":durata,"DescrizioneProdotto":descr,"NOL_FIN":fin,"NOL_INT":intr,"TotRata":tot,"Stato":stato}
            if mask.any(): df2.loc[mask, list(row.keys())]=list(row.values())
            else: df2 = pd.concat([df2, pd.DataFrame([row])], ignore_index=True)
            save_csv(df2, CONTRATTI_CSV); st.success("Contratto salvato."); do_rerun()
    with cR:
        if st.button("🗑️ Elimina (per NumeroContratto)"):
            df2 = df_ct.copy()
            mask = (df2["ClienteID"].astype(str)==str(cid)) & (df2["NumeroContratto"].astype(str)==numero)
            df2 = df2.loc[~mask]
            save_csv(df2, CONTRATTI_CSV); st.success("Contratto eliminato."); do_rerun()

# ------------------------------------------------------------------------------
# Nav
# ------------------------------------------------------------------------------
PAGES = ["Clienti","Contratti"]

def main():
    user, role = require_login()
    st.sidebar.title("📚 Navigazione")
    if "nav_page" not in st.session_state: st.session_state["nav_page"]="Clienti"
    page = st.sidebar.radio("Vai a:", PAGES, index=PAGES.index(st.session_state["nav_page"]))
    st.session_state["nav_page"]=page

    df_cli = load_clienti()
    df_ct = load_contratti()

    st.markdown(f"### {APP_TITLE}")

    if page=="Clienti": page_clienti(df_cli, df_ct, role)
    elif page=="Contratti": page_contratti(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
