# app.py — SHT – Gestione Clienti
# Streamlit 1.50 compatibile

from __future__ import annotations
import os, io, re, shutil
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components  # per stampa HTML
from docx import Document
import xlsxwriter

# ===================== COSTANTI & PATH =====================
APP_TITLE = "SHT – Gestione Clienti"

BASE_DIR = Path(__file__).parent
STORAGE_DIR = BASE_DIR / "storage"
TEMPLATES_DIR = STORAGE_DIR / "templates"
PREVENTIVI_DIR = STORAGE_DIR / "preventivi"

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"   # log numerazioni/offerte

for p in [STORAGE_DIR, TEMPLATES_DIR, PREVENTIVI_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# ===================== THEME (facoltativo) =================
st.set_page_config(page_title=APP_TITLE, layout="wide")

# ===================== UTILITY =============================
def do_rerun():
    st.rerun()

def _today_str() -> str:
    return date.today().strftime("%d/%m/%Y")

def parse_it_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        d, m, y = s.split("/")
        return date(int(y), int(m), int(d))
    except Exception:
        return None

def add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, [31,
        29 if y % 4 == 0 and (y % 100 != 0 or y % 400 == 0) else 28,
        31,30,31,30,31,31,30,31,30,31][m-1])
    return date(y, m, day)

def months_ago(n: int) -> date:
    return add_months(date.today(), -n)

def can_edit(role: str) -> bool:
    return role in {"admin","editor"}

# ===================== I/O CSV =============================
def load_csv(path: Path, dtype=str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=dtype, keep_default_na=False)
    except Exception:
        return pd.DataFrame()

def save_csv(df: pd.DataFrame, path: Path):
    tmp = path.with_suffix(".tmp.csv")
    df.to_csv(tmp, index=False)
    tmp.replace(path)

def load_clienti() -> pd.DataFrame:
    df = load_csv(CLIENTI_CSV)
    # colonne minime attese
    for c in ["ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP","Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"]:
        if c not in df.columns:
            df[c] = ""
    return df

def load_contratti() -> pd.DataFrame:
    df = load_csv(CONTRATTI_CSV)
    for c in ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]:
        if c not in df.columns:
            df[c] = ""
    return df

def upsert_cliente(df_cli: pd.DataFrame, row: Dict):
    cid = str(row.get("ClienteID","")).strip()
    if not cid:
        # assegna nuovo id
        esist = pd.to_numeric(df_cli["ClienteID"], errors="coerce").fillna(0).astype(int)
        new_id = (esist.max() if len(esist)>0 else 0) + 1
        row["ClienteID"] = str(new_id)
        df_cli = pd.concat([df_cli, pd.DataFrame([row])], ignore_index=True)
    else:
        mask = df_cli["ClienteID"].astype(str) == cid
        if mask.any():
            for k,v in row.items():
                df_cli.loc[mask, k] = v
        else:
            df_cli = pd.concat([df_cli, pd.DataFrame([row])], ignore_index=True)
    save_csv(df_cli, CLIENTI_CSV)
    return df_cli

# ===================== AUTH SEMPLICE =======================
def require_login() -> Tuple[str,str]:
    # st.secrets["auth"]["users"][username] = {"password": "...","role":"admin|editor|contributor"}
    if "auth_ok" not in st.session_state:
        st.session_state["auth_ok"] = False
    if not st.session_state["auth_ok"]:
        st.info("Accedi per continuare.")
        with st.form("login"):
            u = st.text_input("Utente", "")
            p = st.text_input("Password", "", type="password")
            ok = st.form_submit_button("Entra")
        if ok:
            try:
                users = st.secrets["auth"]["users"]
                rec = users.get(u, None)
                if rec and rec.get("password","") == p:
                    st.session_state["auth_ok"] = True
                    st.session_state["user"] = u
                    st.session_state["role"] = rec.get("role","contributor")
                    st.success(f"Benvenuto, {u}!")
                    do_rerun()
                else:
                    st.error("Credenziali errate.")
            except Exception:
                st.error("Config auth mancante in Secrets.")
        st.stop()
    return st.session_state.get("user",""), st.session_state.get("role","contributor")

# ===================== RENDER HELPERS ======================
CSS = """
<style>
.table-ctr { width: 100%; border-collapse: collapse; font-size: 14px;}
.table-ctr th, .table-ctr td { border:1px solid #ddd; padding:6px 8px; }
.table-ctr th { background:#e3f2fd; text-align:left; }
.tr-closed { background: #ffebee; }  /* rosino */
.badge { padding:2px 8px; border-radius:12px; font-size:12px; border:1px solid #ccc; }
.badge-open { background:#e8f5e9; border-color:#66bb6a; }
.badge-closed { background:#ffebee; border-color:#ef5350; }
</style>
"""
def status_badge(s: str) -> str:
    s = (s or "").strip().lower()
    if s == "chiuso":
        return "<span class='badge badge-closed'>chiuso</span>"
    return "<span class='badge badge-open'>aperto</span>"

def contracts_html(df: pd.DataFrame) -> str:
    cols = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    df = df.copy()
    for c in cols:
        if c not in df.columns: df[c]=""
    th = "".join(f"<th>{c}</th>" for c in cols)
    rows = []
    for _, r in df.iterrows():
        closed = str(r.get("Stato","")).strip().lower()=="chiuso"
        trc = " class='tr-closed'" if closed else ""
        tds = []
        for c in cols:
            val = r.get(c,"")
            if c=="Stato": val = status_badge(val)
            tds.append(f"<td>{val}</td>")
        rows.append(f"<tr{trc}>{''.join(tds)}</tr>")
    body = "".join(rows)
    return CSS + f"<table class='table-ctr'><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"

def header(title: str):
    st.markdown(f"### {title}")

# ===================== DASHBOARD ==========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("📊 Dashboard")

    # -------- Contratti in scadenza entro 6 mesi (1 per cliente) --------
    st.markdown("#### ⏳ Contratti in scadenza (entro 6 mesi)")
    open_ct = df_ct.loc[df_ct["Stato"].str.lower().ne("chiuso")].copy()

    fine = []
    for _, r in open_ct.iterrows():
        dfine = parse_it_date(r.get("DataFine",""))
        if dfine: fine.append(dfine); continue
        din = parse_it_date(r.get("DataInizio",""))
        mons = None
        dur = (r.get("Durata","") or "").lower().replace(" mesi","").replace(" mese","").replace("m"," ").strip()
        for t in dur.split():
            if t.isdigit(): mons = int(t); break
        fine.append(add_months(din, mons) if (din and mons) else None)
    open_ct["__FineCalc"] = fine

    today = date.today()
    sixm = add_months(today, 6)
    due = open_ct.dropna(subset=["__FineCalc"])
    due = due[(due["__FineCalc"] >= today) & (due["__FineCalc"] <= sixm)].copy()
    due = due.sort_values("__FineCalc").drop_duplicates("ClienteID", keep="first")

    if due.empty:
        st.info("Nessun contratto in scadenza entro 6 mesi.")
    else:
        nm = df_cli[["ClienteID","RagioneSociale"]].copy()
        nm["ClienteID"] = nm["ClienteID"].astype(str)
        due["ClienteID"] = due["ClienteID"].astype(str)
        due = due.merge(nm, on="ClienteID", how="left")
        show = due[["RagioneSociale","NumeroContratto","DescrizioneProdotto","DataInizio","DataFine","Durata"]].copy()
        show["Scadenza"] = due["__FineCalc"].dt.strftime("%d/%m/%Y")
        st.dataframe(show, use_container_width=True, height=260)
        st.markdown("##### Apri cliente")
        for _, r in due.iterrows():
            c = st.columns([5,2])
            c[0].write(f"**{r['RagioneSociale']}** – scade il **{r['__FineCalc'].strftime('%d/%m/%Y')}**")
            if c[1].button("Apri contratti", key=f"open_due_{r['ClienteID']}"):
                st.session_state["cliente_corrente_id"] = int(r["ClienteID"])
                st.session_state["nav_page"] = "Contratti"
                do_rerun()

    st.markdown("---")

    # -------- Recall da fare (>3 mesi) --------
    st.markdown("#### ☎️ Recall da fare (UltimoRecall più vecchio di 3 mesi)")
    three = months_ago(3)
    need_rec = []
    for _, r in df_cli.iterrows():
        last = parse_it_date(r.get("UltimoRecall",""))
        if last is None or last <= three:
            need_rec.append(r)
    if not need_rec:
        st.info("Nessun recall scaduto.")
    else:
        for r in need_rec:
            c = st.columns([6,2,2])
            c[0].write(f"**{r['RagioneSociale']}** – Ultimo: {r.get('UltimoRecall','—')}")
            if c[1].button("Fatto ora", key=f"recall_{r['ClienteID']}"):
                rr = r.to_dict(); rr["UltimoRecall"] = _today_str()
                upsert_cliente(df_cli, rr); do_rerun()
            if c[2].button("Apri cliente", key=f"recall_open_{r['ClienteID']}"):
                st.session_state["cliente_corrente_id"] = int(r["ClienteID"])
                st.session_state["nav_page"] = "Clienti"; do_rerun()

    st.markdown("---")

    # -------- Visite da fare (>6 mesi) --------
    st.markdown("#### 👣 Visite da fare (UltimaVisita più vecchia di 6 mesi)")
    six = months_ago(6)
    need_vis = []
    for _, r in df_cli.iterrows():
        last = parse_it_date(r.get("UltimaVisita",""))
        if last is None or last <= six:
            need_vis.append(r)
    if not need_vis:
        st.info("Nessuna visita scaduta.")
    else:
        for r in need_vis:
            c = st.columns([6,2,2])
            c[0].write(f"**{r['RagioneSociale']}** – Ultima: {r.get('UltimaVisita','—')}")
            if c[1].button("Fatta ora", key=f"vis_{r['ClienteID']}"):
                rr = r.to_dict(); rr["UltimaVisita"] = _today_str()
                upsert_cliente(df_cli, rr); do_rerun()
            if c[2].button("Apri cliente", key=f"visit_open_{r['ClienteID']}"):
                st.session_state["cliente_corrente_id"] = int(r["ClienteID"])
                st.session_state["nav_page"] = "Clienti"; do_rerun()

# ===================== CLIENTI =============================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("👥 Clienti")

    # Selezione cliente
    opts = df_cli[["ClienteID","RagioneSociale"]].copy()
    opts["label"] = opts["ClienteID"].astype(str) + " — " + opts["RagioneSociale"]
    default_idx = 0
    if "cliente_corrente_id" in st.session_state:
        cid = str(st.session_state["cliente_corrente_id"])
        try:
            default_idx = opts.index[opts["ClienteID"].astype(str)==cid][0]
        except Exception:
            default_idx = 0
    sel = st.selectbox("Cliente", opts["label"].tolist(), index=default_idx if len(opts)>0 else 0)
    if len(opts)==0:
        st.warning("Nessun cliente. Aggiungine uno.")
        return

    sel_id = int(opts.iloc[[opts.index[opts["label"]==sel][0]]]["ClienteID"])
    c_row = df_cli.loc[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0].to_dict()

    # Anagrafica sintetica
    st.markdown(f"**{c_row['RagioneSociale']}** – {c_row.get('Indirizzo','')} — {c_row.get('Citta','')} {c_row.get('CAP','')}")
    st.markdown(f"**Persona di riferimento:** {c_row.get('PersonaRiferimento','')}  |  **P.IVA:** {c_row.get('PartitaIVA','')}")
    st.markdown(f"**IBAN:** {c_row.get('IBAN','')}  |  **SDI:** {c_row.get('SDI','')}")
    st.markdown(f"**Ultimo Recall:** {c_row.get('UltimoRecall','')}  |  **Ultima Visita:** {c_row.get('UltimaVisita','')}")

    # Note (box)
    st.markdown("#### 📝 Note cliente")
    note = st.text_area("Note (salvate su CSV)", value=c_row.get("Note",""), height=120)
    if can_edit(role) and st.button("Salva note"):
        c_row["Note"] = note
        upsert_cliente(df_cli, c_row)
        st.success("Note salvate.")

    # Link contratti
    if st.button("Vai alla gestione contratti di questo cliente"):
        st.session_state["cliente_corrente_id"] = int(sel_id)
        st.session_state["nav_page"] = "Contratti"; do_rerun()

# ===================== PREVENTIVI ==========================
PLACEHOLDERS = {
    "{{RagioneSociale}}": "RagioneSociale",
    "{{DataOggi}}": None,
    "{{NumeroOfferta}}": None,
}

def next_offer_number(df_prev: pd.DataFrame) -> str:
    # OFF-YYYY-#### progressivo
    year = datetime.now().strftime("%Y")
    mask = df_prev["Numero"].astype(str).str.contains(f"OFF-{year}-", na=False)
    if mask.any():
        nums = df_prev.loc[mask, "Numero"].str.extract(rf"OFF-{year}-(\d+)", expand=False).fillna("0").astype(int)
        n = nums.max() + 1
    else:
        n = 1
    return f"OFF-{year}-{n:04d}"

def generate_preventivo(c_row: Dict, template_path: Path, df_prev: pd.DataFrame) -> Tuple[Path, Dict]:
    num = next_offer_number(df_prev)
    doc = Document(str(template_path))
    # sostituzioni semplici
    for p in doc.paragraphs:
        for k, col in PLACEHOLDERS.items():
            val = (_today_str() if k=="{{DataOggi}}" else (num if k=="{{NumeroOfferta}}" else c_row.get(col,"")))
            if k in p.text:
                inline = p.runs
                text = p.text.replace(k, str(val))
                for i in range(len(inline)-1, -1, -1):
                    p.runs[i].text = ""
                p.add_run(text)
    # salva
    out_dir = PREVENTIVI_DIR / datetime.now().strftime("%Y%m%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{num} - {c_row.get('RagioneSociale','')}.docx"
    doc.save(str(out_path))
    # copia su OneDrive se configurato
    try:
        od = st.secrets.get("ONEDRIVE_DIR","")
        if od:
            dest = Path(od) / out_path.name
            shutil.copy2(out_path, dest)
    except Exception:
        pass
    row = {"Data": _today_str(), "ClienteID": c_row["ClienteID"], "Numero": num, "Template": template_path.name, "Path": str(out_path)}
    return out_path, row

# ===================== CONTRATTI ===========================
def export_excel_contratti(df: pd.DataFrame, intestazione: str) -> bytes:
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True})
    ws = wb.add_worksheet("Contratti")
    fmt_title = wb.add_format({"bold": True, "font_size": 14, "align": "center"})
    fmt_head  = wb.add_format({"bold": True, "bg_color": "#e3f2fd", "border":1})
    fmt_cell  = wb.add_format({"border":1})
    # titolo
    cols = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    ws.merge_range(0, 0, 0, len(cols)-1, intestazione, fmt_title)
    # header
    for j,c in enumerate(cols):
        ws.write(2, j, c, fmt_head)
        ws.set_column(j, j, 22)
    # body
    for i,(_,r) in enumerate(df.iterrows(), start=3):
        for j,c in enumerate(cols):
            ws.write(i, j, r.get(c,""), fmt_cell)
    wb.close()
    output.seek(0)
    return output.read()

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    header("📄 Contratti (rosso = chiusi)")

    # selettore cliente
    opts = df_cli[["ClienteID","RagioneSociale"]].copy()
    opts["label"] = opts["ClienteID"].astype(str) + " — " + opts["RagioneSociale"]
    default_idx = 0
    if "cliente_corrente_id" in st.session_state:
        cid = str(st.session_state["cliente_corrente_id"])
        try:
            default_idx = opts.index[opts["ClienteID"].astype(str)==cid][0]
        except Exception:
            default_idx = 0
    sel = st.selectbox("Cliente", opts["label"].tolist(), index=default_idx if len(opts)>0 else 0)
    if len(opts)==0: st.warning("Nessun cliente"); return
    sel_id = int(opts.iloc[[opts.index[opts["label"]==sel][0]]]["ClienteID"])

    ct_cli = df_ct.loc[df_ct["ClienteID"].astype(str)==str(sel_id)].copy()

    # tabella HTML con righe rosse
    st.markdown(contracts_html(ct_cli), unsafe_allow_html=True)

    # --- Export / Stampa selettiva
    st.markdown("#### Esporta / Stampa (selezione)")
    numeri = ct_cli["NumeroContratto"].astype(str).replace({"": "(senza numero)"}).tolist()
    selez = st.multiselect("Seleziona contratti (vuoto = tutti)", numeri, default=[])
    if selez:
        mask = ct_cli["NumeroContratto"].astype(str).replace({"": "(senza numero)" }).isin(selez)
        df_sel = ct_cli.loc[mask].copy()
    else:
        df_sel = ct_cli.copy()

    intest = df_cli.loc[df_cli["ClienteID"].astype(str)==str(sel_id),"RagioneSociale"].iloc[0]
    col1, col2 = st.columns(2)
    if col1.button("⬇️ Esporta Excel"):
        xls = export_excel_contratti(df_sel, intestazione=intest)
        st.download_button("Scarica XLSX", xls, file_name=f"Contratti_{intest}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if col2.button("🖨️ Stampa (HTML)"):
        html = contracts_html(df_sel)
        components.html(html, height=480, scrolling=True)

    # --- Azioni rapide Chiudi / Riapri
    st.markdown("#### Azioni rapide")
    if ct_cli.empty:
        st.info("Nessun contratto.")
    else:
        for idx, r in ct_cli.reset_index(drop=True).iterrows():
            info = f"**{r.get('NumeroContratto','(senza numero)')}** – {r.get('DescrizioneProdotto','')}"
            stato = (r.get("Stato","") or "").strip().lower() or "aperto"
            cA, cB, cC = st.columns([7,1.5,1.5])
            cA.write(info)
            cB.write(f"Stato: **{stato}**")
            if can_edit(role) and stato != "chiuso":
                if cC.button("Chiudi", key=f"close_{sel_id}_{idx}"):
                    df2 = df_ct.copy()
                    mask = (df2["ClienteID"].astype(str)==str(sel_id)) & (df2["NumeroContratto"].astype(str)==str(r.get("NumeroContratto","")))
                    df2.loc[mask,"Stato"]="chiuso"; save_csv(df2, CONTRATTI_CSV)
                    st.success("Contratto chiuso."); do_rerun()
            elif can_edit(role) and stato == "chiuso":
                if cC.button("Riapri", key=f"open_{sel_id}_{idx}"):
                    df2 = df_ct.copy()
                    mask = (df2["ClienteID"].astype(str)==str(sel_id)) & (df2["NumeroContratto"].astype(str)==str(r.get("NumeroContratto","")))
                    df2.loc[mask,"Stato"]="aperto"; save_csv(df2, CONTRATTI_CSV)
                    st.success("Contratto riaperto."); do_rerun()

    st.markdown("---")

    # --- Preventivi
    st.markdown("#### 🧾 Preventivi")
    c_row = df_cli.loc[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0].to_dict()
    tpl_list = sorted([p for p in TEMPLATES_DIR.glob("*.docx")], key=lambda x: x.name.lower())
    if tpl_list:
        tpl_names = [p.name for p in tpl_list]
        tpl_name = st.selectbox("Template", tpl_names, index=0)
        if st.button("Crea preventivo da template"):
            df_prev = load_csv(PREVENTIVI_CSV)
            out, row = generate_preventivo(c_row, TEMPLATES_DIR / tpl_name, df_prev if not df_prev.empty else pd.DataFrame(columns=["Data","ClienteID","Numero","Template","Path"]))
            # logga
            df_prev = pd.concat([df_prev, pd.DataFrame([row])], ignore_index=True)
            save_csv(df_prev, PREVENTIVI_CSV)
            with open(out, "rb") as f:
                st.download_button("Scarica preventivo", f.read(), file_name=out.name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            st.success(f"Generato: {out.name}")
    else:
        st.info("Carica prima dei template .docx in storage/templates.")

# ===================== MAIN NAV ===========================
PAGES = ["Dashboard","Clienti","Contratti"]

def main():
    user, role = require_login()
    st.sidebar.title("📚 Navigazione")
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Dashboard"
    page = st.sidebar.radio("Vai a:", PAGES, index=PAGES.index(st.session_state["nav_page"]))
    st.session_state["nav_page"] = page

    df_cli = load_clienti()
    df_ct  = load_contratti()

    st.markdown(f"## {APP_TITLE}")

    if page == "Dashboard":
        page_dashboard(df_cli, df_ct, role)
    elif page == "Clienti":
        page_clienti(df_cli, df_ct, role)
    elif page == "Contratti":
        page_contratti(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
