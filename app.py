# app.py — Gestionale Clienti SHT (versione stabile con fix CSV, OneDrive, dashboard e contratti)
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Tuple, Dict
from io import BytesIO

import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF

# ==========================
# CONFIG / COSTANTI
# ==========================
APP_TITLE = "GESTIONALE CLIENTI – SHT"

STORAGE_DIR = Path(
    st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage"))
)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV     = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV   = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV  = STORAGE_DIR / "preventivi.csv"

EXTERNAL_PROPOSALS_DIR = Path(
    st.secrets.get("storage", {}).get("proposals_dir", (STORAGE_DIR / "preventivi"))
)
EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

ONEDRIVE_BASE_URL = "https://shtsrlit-my.sharepoint.com/personal/fabio_scaranello_shtsrl_com/Documents/OFFERTE"

CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]
PREVENTIVI_COLS = ["ClienteID", "NumeroOfferta", "Template", "NomeFile", "Percorso", "DataCreazione"]

# ==========================
# UTILS
# ==========================
def as_date(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    s = str(x).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return pd.NaT
    return pd.to_datetime(s, errors="coerce", dayfirst=True)

def to_date_series(s: pd.Series) -> pd.Series:
    return s.map(as_date) if s is not None else pd.Series([], dtype="datetime64[ns]")

def fmt_date(d):
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%d/%m/%Y")

def money(x):
    try:
        return f"{float(pd.to_numeric(x, errors='coerce')):.2f}"
    except Exception:
        return ""

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

# ==========================
# I/O DATI
# ==========================
def load_clienti() -> pd.DataFrame:
    """Carica i clienti e aggiunge automaticamente eventuali colonne mancanti."""
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str).fillna("")
        # aggiunge le colonne mancanti
        for col in CLIENTI_COLS:
            if col not in df.columns:
                df[col] = ""
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False)
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        if c in df.columns:
            df[c] = to_date_series(df[c])
    return ensure_columns(df, CLIENTI_COLS)

def save_clienti(df: pd.DataFrame):
    out = df.copy()
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False)

def load_contratti() -> pd.DataFrame:
    """Carica i contratti e aggiunge colonne mancanti se necessario."""
    if CONTRATTI_CSV.exists():
        df = pd.read_csv(CONTRATTI_CSV, dtype=str).fillna("")
        for col in CONTRATTI_COLS:
            if col not in df.columns:
                df[col] = ""
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
        df.to_csv(CONTRATTI_CSV, index=False)
    for c in ["DataInizio","DataFine"]:
        if c in df.columns:
            df[c] = to_date_series(df[c])
    return ensure_columns(df, CONTRATTI_COLS)

def save_contratti(df: pd.DataFrame):
    out = df.copy()
    for c in ["DataInizio","DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False)

def load_preventivi() -> pd.DataFrame:
    if PREVENTIVI_CSV.exists():
        df = pd.read_csv(PREVENTIVI_CSV, dtype=str).fillna("")
        for col in PREVENTIVI_COLS:
            if col not in df.columns:
                df[col] = ""
    else:
        df = pd.DataFrame(columns=PREVENTIVI_COLS)
        df.to_csv(PREVENTIVI_CSV, index=False)
    return ensure_columns(df, PREVENTIVI_COLS)

def save_preventivi(df: pd.DataFrame):
    df.to_csv(PREVENTIVI_CSV, index=False)

# ==========================
# HTML TABLE
# ==========================
def html_table(df: pd.DataFrame, *, closed_mask: pd.Series | None = None) -> str:
    css = """
    <style>
    .ctr-table {width:100%;border-collapse:collapse;}
    .ctr-table th,.ctr-table td {border:1px solid #ccc;padding:6px 8px;font-size:13px;}
    .ctr-table th {background:#e3f2fd;}
    .ctr-row-closed td {background:#ffefef;color:#8a0000;}
    </style>
    """
    if df is None or df.empty:
        return css + "<div style='padding:8px;color:#777'>Nessun dato</div>"
    rows = []
    for i, r in df.iterrows():
        trc = " class='ctr-row-closed'" if (closed_mask is not None and bool(closed_mask.loc[i])) else ""
        cells = "".join(f"<td>{r[c]}</td>" for c in df.columns)
        rows.append(f"<tr{trc}>{cells}</tr>")
    return css + "<table class='ctr-table'><thead><tr>" + "".join(
        f"<th>{c}</th>" for c in df.columns) + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"

# ==========================
# DASHBOARD
# ==========================
def page_dashboard(df_cli, df_ct, role):
    st.subheader("Dashboard")

    today = pd.Timestamp.today().normalize()
    year_now = today.year
    stato = df_ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = (stato != "chiuso").sum()
    contratti_chiusi = (stato == "chiuso").sum()
    contratti_anno   = (to_date_series(df_ct["DataInizio"]).dt.year == year_now).sum()
    clienti_attivi   = df_cli["ClienteID"].nunique()

    st.markdown(f"""
    <style>.kpi{{display:inline-block;background:#fff;padding:12px 20px;border-radius:12px;
    border:1px solid #ddd;margin-right:10px;box-shadow:0 2px 4px #00000010}}
    .kpi span{{display:block;text-align:center}}</style>
    <div>
    <div class='kpi'><span><b>Clienti attivi</b></span><span style='font-size:22px'>{clienti_attivi}</span></div>
    <div class='kpi'><span><b>Contratti aperti</b></span><span style='font-size:22px'>{contratti_aperti}</span></div>
    <div class='kpi'><span><b>Contratti chiusi</b></span><span style='font-size:22px'>{contratti_chiusi}</span></div>
    <div class='kpi'><span><b>Contratti {year_now}</b></span><span style='font-size:22px'>{contratti_anno}</span></div>
    </div>""", unsafe_allow_html=True)

    st.divider()
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    ct = df_ct.copy()
    ct["DataFine"] = to_date_series(ct["DataFine"])
    mask = (ct["Stato"].fillna("aperto").str.lower() != "chiuso") & (
        (ct["DataFine"] >= today) & (ct["DataFine"] <= today + pd.DateOffset(months=6))
    )
    scad = ct[mask].sort_values("DataFine")
    if scad.empty:
        st.info("Nessun contratto in scadenza.")
    else:
        st.markdown(html_table(scad[["ClienteID","NumeroContratto","DataFine","TotRata"]]), unsafe_allow_html=True)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        soglia = today - pd.DateOffset(months=3)
        rec = df_cli[df_cli["UltimoRecall"].notna() & (df_cli["UltimoRecall"] <= soglia)]
        if not rec.empty:
            st.markdown(html_table(rec[["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]]), unsafe_allow_html=True)
        else:
            st.info("Nessun recall da più di 3 mesi.")
    with col2:
        st.markdown("### Ultime visite (> 6 mesi)")
        soglia_v = today - pd.DateOffset(months=6)
        vis = df_cli[df_cli["UltimaVisita"].notna() & (df_cli["UltimaVisita"] <= soglia_v)]
        if not vis.empty:
            st.markdown(html_table(vis[["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]]), unsafe_allow_html=True)
        else:
            st.info("Nessuna visita da più di 6 mesi.")

# (continua nella parte 2: Clienti, Preventivi, Contratti, main)
# ==========================
# CLIENTI + PREVENTIVI (OneDrive)
# ==========================
def _summary_box(row: pd.Series):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**ClienteID:** {row.get('ClienteID','')}")
        st.markdown(f"**Ragione Sociale:** {row.get('RagioneSociale','')}")
        st.markdown(f"**Riferimento:** {row.get('PersonaRiferimento','')}")
    with c2:
        st.markdown(f"**Indirizzo:** {row.get('Indirizzo','')}")
        st.markdown(f"**CAP/Città:** {row.get('CAP','')} {row.get('Citta','')}")
        st.markdown(f"**Telefono/Cell:** {row.get('Telefono','')} / {row.get('Cell','')}")
    with c3:
        st.markdown(f"**Email:** {row.get('Email','')}")
        st.markdown(f"**P.IVA:** {row.get('PartitaIVA','')}")
        st.markdown(f"**SDI:** {row.get('SDI','')}")

def page_clienti(df_cli, df_ct, role):
    st.subheader("Clienti")
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try: idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except Exception: idx = 0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    row = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0]
    _summary_box(row)

    note_new = st.text_area("Note", row.get("Note",""))
    if st.button("💾 Salva note"):
        idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
        df_cli.loc[idx_row, "Note"] = note_new
        save_clienti(df_cli)
        st.success("Note aggiornate.")
        st.rerun()

    st.divider()
    st.markdown("### ✏️ Anagrafica")

    with st.form("frm_anagrafica"):
        col1, col2, col3 = st.columns(3)
        with col1:
            ragsoc = st.text_input("Ragione sociale", str(row.get("RagioneSociale","")))
            indir  = st.text_input("Indirizzo", str(row.get("Indirizzo","")))
            cap    = st.text_input("CAP", str(row.get("CAP","")))
        with col2:
            citta  = st.text_input("Città", str(row.get("Citta","")))
            ref    = st.text_input("Persona di riferimento", str(row.get("PersonaRiferimento","")))
            tel    = st.text_input("Telefono", str(row.get("Telefono","")))
        with col3:
            cell   = st.text_input("Cell", str(row.get("Cell","")))
            mail   = st.text_input("Email", str(row.get("Email","")))
            piva   = st.text_input("Partita IVA", str(row.get("PartitaIVA","")))

        c4, c5, c6 = st.columns(3)
        with c4:
            sdi = st.text_input("SDI", str(row.get("SDI","")))
        with c5:
            ult_recall = st.date_input("Ultimo recall", value=as_date(row.get("UltimoRecall")))
        with c6:
            ult_visita = st.date_input("Ultima visita", value=as_date(row.get("UltimaVisita")))

        if st.form_submit_button("💾 Salva anagrafica", use_container_width=True):
            idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
            df_cli.loc[idx_row, "RagioneSociale"] = ragsoc
            df_cli.loc[idx_row, "Indirizzo"] = indir
            df_cli.loc[idx_row, "CAP"] = cap
            df_cli.loc[idx_row, "Citta"] = citta
            df_cli.loc[idx_row, "PersonaRiferimento"] = ref
            df_cli.loc[idx_row, "Telefono"] = tel
            df_cli.loc[idx_row, "Cell"] = cell
            df_cli.loc[idx_row, "Email"] = mail
            df_cli.loc[idx_row, "PartitaIVA"] = piva
            df_cli.loc[idx_row, "SDI"] = sdi
            df_cli.loc[idx_row, "UltimoRecall"] = pd.to_datetime(ult_recall)
            df_cli.loc[idx_row, "UltimaVisita"] = pd.to_datetime(ult_visita)
            df_cli.loc[idx_row, "ProssimoRecall"] = pd.to_datetime(ult_recall) + pd.DateOffset(months=3)
            df_cli.loc[idx_row, "ProssimaVisita"] = pd.to_datetime(ult_visita) + pd.DateOffset(months=6)
            save_clienti(df_cli)
            st.success("✅ Dati aggiornati con prossime date automatiche.")
            st.rerun()

    st.divider()
    if st.button("📄 Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = sel_id
        st.rerun()

    st.divider()
    st.markdown("### 📑 Preventivi (OneDrive)")

    df_prev = load_preventivi()
    tpl_file = "Offerta_Base.docx"
    tpl_path = STORAGE_DIR / "templates" / tpl_file

    if not tpl_path.exists():
        st.warning(f"Template mancante: {tpl_file}")
    else:
        if st.button("📝 Genera nuovo preventivo"):
            safe_name = "".join(ch if ch.isalnum() else "_" for ch in str(row["RagioneSociale"])).strip("_")
            client_dir = EXTERNAL_PROPOSALS_DIR / safe_name
            client_dir.mkdir(parents=True, exist_ok=True)
            numero = f"SHT-MI-{safe_name}-{sel_id}-{datetime.now().strftime('%Y%m%d%H%M')}"
            doc = Document(str(tpl_path))
            for p in doc.paragraphs:
                for token, val in {
                    "<<CLIENTE>>": row["RagioneSociale"],
                    "<<DATA>>": datetime.today().strftime("%d/%m/%Y"),
                    "<<NUMERO>>": numero,
                }.items():
                    if token in p.text:
                        p.text = p.text.replace(token, val)
            out_path = client_dir / f"{numero}.docx"
            doc.save(out_path)
            new_row = {
                "ClienteID": sel_id,
                "NumeroOfferta": numero,
                "Template": tpl_file,
                "NomeFile": out_path.name,
                "Percorso": str(out_path),
                "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            df_prev = pd.concat([df_prev, pd.DataFrame([new_row])], ignore_index=True)
            save_preventivi(df_prev)
            st.success(f"✅ Preventivo creato: {out_path.name}")
            st.rerun()

    sub = df_prev[df_prev["ClienteID"].astype(str) == sel_id].copy()
    if sub.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        for _, r in sub.iterrows():
            c1, c2 = st.columns([0.7, 0.3])
            with c1:
                st.markdown(f"**{r['NumeroOfferta']}** — {r['DataCreazione']}")
            with c2:
                path = Path(r["Percorso"])
                if path.exists():
                    with open(path, "rb") as fh:
                        st.download_button("⬇️ Scarica", data=fh.read(), file_name=path.name)
            safe_name = "".join(ch if ch.isalnum() else "_" for ch in str(row["RagioneSociale"])).strip("_")
            url = f"{ONEDRIVE_BASE_URL}/{safe_name}"
            st.markdown(f"[📂 Apri cartella OneDrive]({url})")

# ==========================
# CONTRATTI
# ==========================
def page_contratti(df_cli, df_ct, role):
    st.subheader("Contratti")
    if df_cli.empty:
        st.info("Nessun cliente presente."); return

    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try: idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except Exception: idx = 0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"]
    rag_soc = df_cli[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0]["RagioneSociale"]
    st.caption(f"Contratti di **{rag_soc}**")

    with st.expander("➕ Nuovo contratto"):
        with st.form("frm_new_contract"):
            num = st.text_input("Numero contratto")
            din = st.date_input("Data inizio")
            durata = st.selectbox("Durata (mesi)", [12,24,36,48,60,72])
            desc = st.text_area("Descrizione prodotto")
            tot = st.text_input("TotRata")
            if st.form_submit_button("Crea contratto"):
                fine = pd.to_datetime(din) + pd.DateOffset(months=int(durata))
                new_row = {
                    "ClienteID": sel_id,
                    "NumeroContratto": num,
                    "DataInizio": pd.to_datetime(din),
                    "DataFine": fine,
                    "Durata": durata,
                    "DescrizioneProdotto": desc,
                    "TotRata": tot,
                    "Stato": "aperto"
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([new_row])], ignore_index=True)
                save_contratti(df_ct)
                st.success("Contratto creato.")
                st.rerun()

    ct = df_ct[df_ct["ClienteID"].astype(str)==str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    closed_mask = ct["Stato"].str.lower()=="chiuso"
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp["TotRata"] = disp["TotRata"].apply(money)

    st.markdown("### 📋 Elenco contratti")
    st.markdown(html_table(
        disp[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","TotRata","Stato"]],
        closed_mask=closed_mask
    ), unsafe_allow_html=True)

    st.divider()
    st.markdown("### 🔁 Chiudi / Riapri contratto")
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.1, 0.7, 0.2])
        with c1:
            st.caption(r["NumeroContratto"])
        with c2:
            st.caption(r["DescrizioneProdotto"])
        with c3:
            stato = (r["Stato"] or "aperto").lower()
            if stato == "chiuso":
                if st.button("Riapri", key=f"open_{i}"):
                    df_ct.loc[i,"Stato"]="aperto"; save_contratti(df_ct); st.rerun()
            else:
                if st.button("Chiudi", key=f"close_{i}"):
                    df_ct.loc[i,"Stato"]="chiuso"; save_contratti(df_ct); st.rerun()

    st.divider()
    st.download_button(
        "📊 Esporta Excel",
        data=disp.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"contratti_{rag_soc}.csv",
        mime="text/csv"
    )

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, f"Contratti - {rag_soc}", ln=1, align="C")
    pdf.set_font("Arial", size=9)
    for _, row in disp.iterrows():
        pdf.cell(0, 8, f"{row['NumeroContratto']} - {row['DescrizioneProdotto']} ({row['Stato']})", ln=1)
    pdf_output = pdf.output(dest="S").encode("latin-1", errors="ignore")
    st.download_button("📄 Esporta PDF", data=pdf_output, file_name=f"contratti_{rag_soc}.pdf", mime="application/pdf")

# ==========================
# APP PRINCIPALE
# ==========================
def main():
    st.set_page_config(page_title="SHT – Gestionale", layout="wide")
    st.markdown(f"<h3 style='margin-top:8px'>{APP_TITLE}</h3>", unsafe_allow_html=True)

    user, role = ("fabio", "admin")
    st.sidebar.success(f"Utente: {user} — Ruolo: {role}")

    PAGES = {"Dashboard": page_dashboard, "Clienti": page_clienti, "Contratti": page_contratti}
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("Menu", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)

    df_cli = load_clienti()
    df_ct = load_contratti()
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
