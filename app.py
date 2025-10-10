# -*- coding: utf-8 -*-
"""
CRM Clienti & Contratti - Streamlit
Drop-in completo con:
- show_html via components.html
- go_to() in alto (niente NameError)
- date dd/mm/aaaa uniformi
- pagine Clienti / Contratti separate
- Preventivi con numerazione e storico
- Export contratti (Excel)
"""

from __future__ import annotations
import os, io, re, uuid, json, textwrap
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd
import numpy as np
import streamlit as st
from streamlit.components.v1 import html as components_html
import xlsxwriter

# =========================
# ---- Costanti / Setup ----
# =========================

APP_TITLE = "CRM Clienti & Contratti"
PAGES = ["Dashboard", "Clienti", "Contratti", "Impostazioni"]

DATA_DIR = Path(".")
STORAGE_DIR = Path(os.environ.get("LOCAL_STORAGE_DIR", "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV = DATA_DIR / "clienti.csv"
CONTRATTI_CSV = DATA_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = DATA_DIR / "preventivi.csv"

DATE_FMT = "%d/%m/%Y"

# ==========================================
# ---- Utility: Date, Money, File System ----
# ==========================================

def to_date(x) -> Optional[date]:
    """Parse qualunque formato comune in date; ritorna None se vuoto."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    s = str(x).strip()
    if not s or s.lower() in ("nan", "nat"):
        return None
    # Prova vari formati
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    # Prova parser numpy/pandas
    try:
        return pd.to_datetime(s, dayfirst=True).date()
    except Exception:
        return None

def fmt_date(x) -> str:
    d = to_date(x)
    return d.strftime(DATE_FMT) if d else ""

def money(x) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return ""
    try:
        val = float(str(x).replace(",", "."))
        return f"€ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return ""

def num(x) -> float:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return 0.0

def ensure_csv(path: Path, columns: List[str]) -> None:
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False, encoding="utf-8")

def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    except Exception:
        # fallback encoding
        return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="latin-1")

def save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8")

def next_progressive(prefix: str, existing: pd.Series) -> str:
    """
    Genera un numero progressivo: es. CTR-30-2025-0001
    Se prefix='CTR', prende anno corrente.
    """
    year = date.today().year
    serie = existing.fillna("").astype(str)
    patt = re.compile(rf"^{re.escape(prefix)}-{year}-(\d+)$")
    max_n = 0
    for val in serie:
        m = patt.match(val)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"{prefix}-{year}-{max_n+1:04d}"

# ===========================================
# ---- HTML Rendering (tabella contratti) ----
# ===========================================

def status_class(s: str) -> str:
    s = (s or "").strip().lower()
    if s == "chiuso":
        return "closed"
    if s == "aperto":
        return "open"
    return "neutral"

def contracts_html(df: pd.DataFrame) -> str:
    # Style semplice
    css = """
    <style>
    table.ctr-table{
        width:100%;
        border-collapse: collapse;
        font-size: 14px;
    }
    .ctr-table th, .ctr-table td{
        border: 1px solid #ddd;
        padding: 6px 8px;
        vertical-align: top;
    }
    .ctr-table thead th{
        background:#f6f7fa;
        text-align:left;
    }
    .ctr-table tr.closed{ background:#ffecec; }
    </style>
    """
    headers = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
               "NOL_FIN","NOL_INT","TotRata","Stato"]
    rows = []
    for _, r in df.iterrows():
        cls = status_class(r.get("Stato",""))
        rows.append(
            f"<tr class='{cls}'>"
            f"<td>{(r.get('NumeroContratto') or '').strip()}</td>"
            f"<td>{fmt_date(r.get('DataInizio'))}</td>"
            f"<td>{fmt_date(r.get('DataFine'))}</td>"
            f"<td>{(r.get('Durata') or '').strip()}</td>"
            f"<td>{(r.get('DescrizioneProdotto') or '').strip()}</td>"
            f"<td>{money(r.get('NOL_FIN'))}</td>"
            f"<td>{money(r.get('NOL_INT'))}</td>"
            f"<td>{money(r.get('TotRata'))}</td>"
            f"<td>{(r.get('Stato') or '').strip()}</td>"
            f"</tr>"
        )
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in headers) + "</tr></thead>"
    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return css + f"<table class='ctr-table'>{thead}{tbody}</table>"

def show_html(html: str, height: int = 420):
    # usa sempre il componente classico per compatibilità
    components_html(html, height=height, scrolling=True)

# ========================================
# ---- Navigazione (risolve NameError) ----
# ========================================

def go_to(page_name: str):
    st.session_state["nav_target"] = page_name
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()

# Init session keys
if "sidebar_page" not in st.session_state:
    st.session_state["sidebar_page"] = "Clienti"
if "nav_target" not in st.session_state:
    st.session_state["nav_target"] = None
if "selected_cliente" not in st.session_state:
    st.session_state["selected_cliente"] = None

# =========================
# ---- Data bootstrap  ----
# =========================

ensure_csv(CLIENTI_CSV, [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall",
    "UltimaVisita","ProssimaVisita","Note"
])

ensure_csv(CONTRATTI_CSV, [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
    "NOL_FIN","NOL_INT","TotRata","Stato"
])

ensure_csv(PREVENTIVI_CSV, [
    "NumeroPrev","ClienteID","Data","Template","FileName","Key"
])

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    clienti = read_csv(CLIENTI_CSV)
    contratti = read_csv(CONTRATTI_CSV)
    preventivi = read_csv(PREVENTIVI_CSV)
    return clienti, contratti, preventivi

def save_all(clienti: pd.DataFrame, contratti: pd.DataFrame, preventivi: pd.DataFrame):
    save_csv(clienti, CLIENTI_CSV)
    save_csv(contratti, CONTRATTI_CSV)
    save_csv(preventivi, PREVENTIVI_CSV)

# =================================
# ---- UI Helpers / Widgets   -----
# =================================

def clienti_selectbox(clienti: pd.DataFrame, key="sel_cliente") -> Optional[str]:
    if clienti.empty:
        st.info("Non ci sono clienti.")
        return None
    scelte = [f"{r['ClienteID']} — {r['RagioneSociale']}" for _, r in clienti.iterrows()]
    sel = st.selectbox("Seleziona cliente", scelte, key=key)
    return sel.split(" — ")[0] if sel else None

def tot_rata_row(fin, intr) -> float:
    return num(fin) + num(intr)

def add_spacer(h=8):
    st.write(f"<div style='height:{h}px'></div>", unsafe_allow_html=True)

# ===============================
# ---- Pagine: Dashboard   ------
# ===============================

def render_dashboard(clienti: pd.DataFrame):
    st.subheader("Promemoria in arrivo (30 giorni)")
    today = date.today()
    horizon = today + timedelta(days=30)

    # colonne: ProssimoRecall / ProssimaVisita
    work = clienti.copy()
    work["PR_dt"] = work["ProssimoRecall"].apply(to_date)
    work["PV_dt"] = work["ProssimaVisita"].apply(to_date)

    pr = work[(~work["PR_dt"].isna()) & (work["PR_dt"] >= today) & (work["PR_dt"] <= horizon)]
    pv = work[(~work["PV_dt"].isna()) & (work["PV_dt"] >= today) & (work["PV_dt"] <= horizon)]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Recall da fare (entro 30 giorni)**")
        if pr.empty:
            st.write("Nessun recall.")
        else:
            df = pr[["ClienteID","RagioneSociale"]].copy()
            df["ProssimoRecall"] = pr["PR_dt"].apply(lambda d: d.strftime(DATE_FMT))
            st.dataframe(df, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**Visite da fare (entro 30 giorni)**")
        if pv.empty:
            st.write("Nessuna visita.")
        else:
            df = pv[["ClienteID","RagioneSociale"]].copy()
            df["ProssimaVisita"] = pv["PV_dt"].apply(lambda d: d.strftime(DATE_FMT))
            st.dataframe(df, use_container_width=True, hide_index=True)

# ===============================
# ---- Pagine: Clienti     ------
# ===============================

def render_clienti(clienti: pd.DataFrame, contratti: pd.DataFrame, preventivi: pd.DataFrame):
    st.header("👥 Clienti")

    # barra strumenti
    with st.expander("➕ Aggiungi cliente"):
        with st.form("add_cli_form", clear_on_submit=True):
            new_id = st.text_input("ClienteID").strip()
            rs = st.text_input("Ragione sociale").strip()
            pr = st.text_input("Persona di riferimento").strip()
            ind = st.text_input("Indirizzo").strip()
            citta = st.text_input("Città").strip()
            cap = st.text_input("CAP").strip()
            tel = st.text_input("Telefono").strip()
            email = st.text_input("Email").strip()
            piva = st.text_input("Partita IVA").strip()
            iban = st.text_input("IBAN").strip()
            sdi = st.text_input("SDI").strip()
            note = st.text_area("Note")

            if st.form_submit_button("Crea cliente"):
                if not new_id or not rs:
                    st.error("ClienteID e Ragione sociale sono obbligatori.")
                elif (clienti["ClienteID"] == new_id).any():
                    st.error("ClienteID già esistente.")
                else:
                    row = dict(
                        ClienteID=new_id,RagioneSociale=rs,PersonaRiferimento=pr,Indirizzo=ind,
                        Citta=citta,CAP=cap,Telefono=tel,Email=email,PartitaIVA=piva,
                        IBAN=iban,SDI=sdi,UltimoRecall="",ProssimoRecall="",
                        UltimaVisita="",ProssimaVisita="",Note=note
                    )
                    clienti.loc[len(clienti)] = row
                    save_csv(clienti, CLIENTI_CSV)
                    st.success("Cliente creato.")
                    st.session_state["selected_cliente"] = new_id
                    st.rerun()

    with st.expander("🗑️ Elimina cliente"):
        del_id = st.text_input("Inserisci ClienteID da eliminare").strip()
        if st.button("Elimina definitivamente"):
            if not del_id:
                st.warning("Inserisci ClienteID.")
            else:
                if (clienti["ClienteID"] == del_id).any():
                    # non cancelliamo i contratti, solo cliente
                    clienti = clienti[clienti["ClienteID"] != del_id].copy()
                    save_csv(clienti, CLIENTI_CSV)
                    st.success("Cliente eliminato.")
                    if st.session_state.get("selected_cliente") == del_id:
                        st.session_state["selected_cliente"] = None
                    st.rerun()
                else:
                    st.info("ClienteID non trovato.")

    add_spacer(6)

    # Selezione cliente
    left, right = st.columns([1, 2])
    with left:
        cid = clienti_selectbox(clienti, key="clienti_select")
        if cid:
            st.session_state["selected_cliente"] = cid
    with right:
        st.info("Suggerimento: clicca sul bottone in basso per gestire i contratti del cliente selezionato.")

    sel_id = st.session_state.get("selected_cliente")

    add_spacer(8)

    if not sel_id:
        st.stop()

    # Dettaglio cliente
    row = clienti[clienti["ClienteID"] == sel_id]
    if row.empty:
        st.warning("Cliente non trovato.")
        st.stop()
    c = row.iloc[0].to_dict()

    st.subheader(f"{c['RagioneSociale']}")
    a1, a2 = st.columns(2)
    with a1:
        st.write(f"**Persona di riferimento:** {c.get('PersonaRiferimento','')}")
        st.write(f"**Indirizzo:** {c.get('Indirizzo','')}")
        st.write(f"**Città:** {c.get('Citta','')} **CAP:** {c.get('CAP','')}")
        st.write(f"**Telefono:** {c.get('Telefono','')}")
        st.write(f"**Email:** {c.get('Email','')}")
    with a2:
        st.write(f"**Partita IVA:** {c.get('PartitaIVA','')}")
        st.write(f"**IBAN:** {c.get('IBAN','')}")
        st.write(f"**SDI:** {c.get('SDI','')}")
        st.write(f"**Ultimo Recall:** {fmt_date(c.get('UltimoRecall'))}")
        st.write(f"**Prossimo Recall:** {fmt_date(c.get('ProssimoRecall'))}")
        st.write(f"**Ultima Visita:** {fmt_date(c.get('UltimaVisita'))}")
        st.write(f"**Prossima Visita:** {fmt_date(c.get('ProssimaVisita'))}")

    if c.get("Note","").strip():
        st.info(c["Note"])

    add_spacer(6)
    st.button("➡️ Vai alla gestione contratti di questo cliente", on_click=lambda: go_to("Contratti"))

    # Allegati cliente
    with st.expander("📎 Allegati cliente"):
        cust_dir = STORAGE_DIR / f"cliente_{sel_id}"
        cust_dir.mkdir(parents=True, exist_ok=True)
        up = st.file_uploader("Carica allegato", key="up_cli", accept_multiple_files=True)
        if up:
            for f in up:
                p = cust_dir / f.name
                p.write_bytes(f.getbuffer())
            st.success("Allegati salvati.")
        files = sorted([p.name for p in cust_dir.glob("*") if p.is_file()])
        if files:
            for name in files:
                p = cust_dir / name
                st.download_button("⬇️ "+name, data=p.read_bytes(), file_name=name, key=f"dwn_{name}")
        else:
            st.caption("Nessun allegato.")

    # Preventivi
    with st.expander("🧾 Preventivi"):
        # generazione
        st.markdown("**Genera preventivo**")
        colp1, colp2 = st.columns([2,1])
        with colp1:
            template = st.selectbox("Template DOCX", [f.name for f in Path(".").glob("*.docx")] or ["(Nessun .docx trovato)"])
        with colp2:
            data_prev = date.today().strftime(DATE_FMT)
            st.text_input("Data", value=data_prev, disabled=True)

        if st.button("Genera preventivo"):
            if not template or template.startswith("("):
                st.warning("Aggiungi un file .docx nella root del progetto.")
            else:
                numero = next_progressive("PRV", preventivi["NumeroPrev"])
                # Qui potresti aprire e riempire il docx (python-docx) con segnaposto,
                # per semplicità salviamo una copia con nuovo nome:
                src = Path(template)
                dst_name = f"{numero}_{sel_id}_{src.name}"
                dst = STORAGE_DIR / "preventivi" / dst_name
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    dst.write_bytes(src.read_bytes())
                except Exception:
                    # Se template bloccato, crea file vuoto
                    dst.write_text(f"Preventivo {numero} - Cliente {sel_id}")
                # registra su CSV
                rec = dict(NumeroPrev=numero, ClienteID=sel_id, Data=date.today().strftime(DATE_FMT),
                           Template=src.name, FileName=dst_name, Key=dst.as_posix())
                preventivi.loc[len(preventivi)] = rec
                save_csv(preventivi, PREVENTIVI_CSV)
                st.success(f"Preventivo {numero} creato.")
                st.experimental_rerun()

        st.markdown("---")
        st.markdown("**Storico preventivi**")
        stor = preventivi[preventivi["ClienteID"] == sel_id].sort_values("NumeroPrev")
        if stor.empty:
            st.caption("Nessun preventivo per questo cliente.")
        else:
            for _, r in stor.iterrows():
                c1, c2, c3 = st.columns([2,2,1])
                c1.write(r["NumeroPrev"])
                c2.write(r["Data"])
                fpath = Path(r["Key"])
                if fpath.exists():
                    c3.download_button("⬇️", data=fpath.read_bytes(), file_name=fpath.name, key=f"prv_{r['NumeroPrev']}")
                else:
                    c3.write("—")

# ===============================
# ---- Pagine: Contratti   ------
# ===============================

def render_contratti(clienti: pd.DataFrame, contratti: pd.DataFrame):
    st.header("📑 Contratti")

    cid = st.session_state.get("selected_cliente")
    if not cid:
        st.info("Seleziona prima un cliente nella pagina **Clienti**.")
        return

    row = clienti[clienti["ClienteID"] == cid]
    if row.empty:
        st.warning("Cliente non trovato.")
        return
    rag_soc = row.iloc[0]["RagioneSociale"]

    st.subheader(f"{rag_soc} — Contratti")

    df_cli = contratti[contratti["ClienteID"] == cid].copy()
    # Recompute TotRata sempre (fonte di verità FIN+INT)
    df_cli["TotRata"] = df_cli.apply(lambda r: tot_rata_row(r.get("NOL_FIN"), r.get("NOL_INT")), axis=1)

    # Tabella HTML
    add_spacer(6)
    st.markdown("**Contratti (rosso = chiusi)**")
    show_html(contracts_html(df_cli), height=min(460, 120 + 28*len(df_cli)))

    # Esporta / Stampa
    with st.expander("📤 Esporta / Stampa contratti"):
        sel_num = st.multiselect("Seleziona N. contratti (vuoto = tutti)", df_cli["NumeroContratto"].tolist())
        filtered = df_cli if not sel_num else df_cli[df_cli["NumeroContratto"].isin(sel_num)].copy()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("⬇️ Esporta in Excel"):
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                    filtered.to_excel(writer, index=False, sheet_name="Contratti")
                st.download_button("Scarica Excel", data=out.getvalue(),
                                   file_name=f"contratti_{cid}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c2:
            if st.button("🖨️ Stampa (PDF dal browser)"):
                st.info("Usa la funzione di stampa del browser (⌘P / Ctrl+P).")

    # Aggiungi contratto
    with st.expander("➕ Aggiungi contratto"):
        with st.form("add_ctr_form", clear_on_submit=True):
            numero = st.text_input("Numero contratto", value=next_progressive("CTR", df_cli["NumeroContratto"]))
            d_in = st.date_input("Data inizio")
            durata = st.text_input("Durata (es. 60 M)", value="60 M")
            descr = st.text_area("Descrizione / Prodotto")
            fin = st.text_input("NOL_FIN (€)", value="0")
            intr = st.text_input("NOL_INT (€)", value="0")
            stato = st.selectbox("Stato", ["aperto","chiuso"], index=0)

            if st.form_submit_button("Crea"):
                # Data fine opzionale da durata (se M)
                data_fine = ""
                try:
                    months = int(re.findall(r"\d+", durata)[0])
                    di = d_in
                    y = di.year + (di.month - 1 + months) // 12
                    m = (di.month - 1 + months) % 12 + 1
                    d = min(di.day, [31,29 if y%4==0 and (y%100!=0 or y%400==0) else 28,31,30,31,30,31,31,30,31,30,31][m-1])
                    data_fine = date(y,m,d).strftime(DATE_FMT)
                except Exception:
                    pass

                new = dict(
                    ClienteID=cid, NumeroContratto=numero,
                    DataInizio=d_in.strftime(DATE_FMT), DataFine=data_fine, Durata=durata,
                    DescrizioneProdotto=descr, NOL_FIN=fin, NOL_INT=intr,
                    TotRata=str(tot_rata_row(fin,intr)).replace(".",","), Stato=stato
                )
                contratti.loc[len(contratti)] = new
                save_csv(contratti, CONTRATTI_CSV)
                st.success("Contratto creato.")
                st.experimental_rerun()

    # Modifica/Chiudi contratto
    with st.expander("✏️ Modifica/Chiudi contratto"):
        nums = df_cli["NumeroContratto"].tolist()
        if not nums:
            st.caption("Nessun contratto.")
        else:
            sel = st.selectbox("Seleziona numero", nums, key="edit_ctr_sel")
            r = df_cli[df_cli["NumeroContratto"] == sel].iloc[0]

            with st.form("edit_ctr", clear_on_submit=False):
                di = st.text_input("Data inizio", value=fmt_date(r["DataInizio"]))
                df = st.text_input("Data fine", value=fmt_date(r["DataFine"]))
                durata = st.text_input("Durata", value=r["Durata"])
                desc = st.text_input("Descrizione", value=r["DescrizioneProdotto"])
                fin = st.text_input("NOL_FIN", value=str(r["NOL_FIN"]))
                intr = st.text_input("NOL_INT", value=str(r["NOL_INT"]))
                stato = st.selectbox("Stato", ["aperto","chiuso"], index=0 if (r["Stato"] or "").lower()=="aperto" else 1)
                tot = tot_rata_row(fin,intr)

                st.text_input("TotRata (auto FIN+INT)", value=money(tot), disabled=True)

                if st.form_submit_button("Aggiorna"):
                    idx = (contratti["ClienteID"]==cid) & (contratti["NumeroContratto"]==sel)
                    contratti.loc[idx, ["DataInizio","DataFine","Durata","DescrizioneProdotto",
                                        "NOL_FIN","NOL_INT","TotRata","Stato"]] = [
                        di, df, durata, desc, fin, intr, str(tot).replace(".",","), stato
                    ]
                    save_csv(contratti, CONTRATTI_CSV)
                    st.success("Contratto aggiornato.")
                    st.experimental_rerun()

    with st.expander("🗑️ Elimina contratto"):
        nums2 = df_cli["NumeroContratto"].tolist()
        deln = st.selectbox("Seleziona numero", nums2, key="del_ctr_sel")
        if st.button("Elimina"):
            contratti = contratti[~((contratti["ClienteID"]==cid)&(contratti["NumeroContratto"]==deln))].copy()
            save_csv(contratti, CONTRATTI_CSV)
            st.success("Contratto eliminato.")
            st.experimental_rerun()

# ===============================
# ---- Pagine: Impostazioni -----
# ===============================

def render_settings():
    st.header("⚙️ Impostazioni")
    st.write("Cartella storage:", f"`{STORAGE_DIR.as_posix()}`")
    st.caption("Puoi cambiarla impostando la variabile d'ambiente LOCAL_STORAGE_DIR prima di avviare l'app.")

# =========================
# ---- APP ENTRYPOINT  ----
# =========================

def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="📒", layout="wide")
    st.title(APP_TITLE)

    # Nav sidebar
    page = st.sidebar.radio("Navigazione", PAGES, index=PAGES.index(st.session_state["sidebar_page"]))
    # gestore salti da go_to()
    if st.session_state.get("nav_target"):
        page = st.session_state["nav_target"]
        st.session_state["nav_target"] = None

    st.session_state["sidebar_page"] = page

    clienti, contratti, preventivi = load_data()

    if page == "Dashboard":
        render_dashboard(clienti)
    elif page == "Clienti":
        render_clienti(clienti, contratti, preventivi)
    elif page == "Contratti":
        render_contratti(clienti, contratti)
    elif page == "Impostazioni":
        render_settings()

if __name__ == "__main__":
    main()
