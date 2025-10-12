# app.py — Gestionale Clienti SHT (completo, con anagrafica, dashboard, esportazioni, preventivi)
from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict

import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF

# ==========================
# CONFIG / COSTANTI
# ==========================
APP_TITLE = "GESTIONALE CLIENTI – SHT"

# storage root (da secrets, fallback a ./storage)
STORAGE_DIR = Path(
    st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage"))
)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV     = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV   = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV  = STORAGE_DIR / "preventivi.csv"
TEMPLATES_DIR   = STORAGE_DIR / "templates"

EXTERNAL_PROPOSALS_DIR = Path(
    st.secrets.get("storage", {}).get("proposals_dir") or (STORAGE_DIR / "preventivi")
)
EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

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

TEMPLATE_OPTIONS: Dict[str, str] = {
    "Offerta – Centralino": "Offerta_Centralino.docx",
    "Offerta – Varie": "Offerta_Varie.docx",
    "Offerta – A3": "Offerte_A3.docx",
    "Offerta – A4": "Offerte_A4.docx",
}

DURATE_MESI = ["12", "24", "36", "48", "60", "72"]

# ==========================
# UTILS
# ==========================
def as_date(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    if isinstance(x, (pd.Timestamp, pd.NaT.__class__)):
        return x
    s = str(x).strip()
    if not s or s.lower() in ("nan", "nat", "none"):
        return pd.NaT
    d = pd.to_datetime(s, errors="coerce", dayfirst=True)
    if pd.isna(d):
        d = pd.to_datetime(s, errors="coerce")
    return d

def to_date_series(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series([], dtype="datetime64[ns]")
    return s.map(as_date)

def fmt_date(d) -> str:
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%d/%m/%Y")

def money(x):
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        return f"{v:,.2f} €"
    except Exception:
        return ""

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def date_input_opt(label: str, current, *, key: str):
    d = as_date(current)
    try:
        if pd.isna(d):
            return st.date_input(label, key=key, format="DD/MM/YYYY")
        else:
            return st.date_input(label, value=d.to_pydatetime().date(), key=key, format="DD/MM/YYYY")
    except TypeError:
        if pd.isna(d):
            return st.date_input(label, key=key)
        else:
            return st.date_input(label, value=d.to_pydatetime().date(), key=key)

# ==========================
# I/O DATI
# ==========================
def load_clienti() -> pd.DataFrame:
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
    df = ensure_columns(df, CLIENTI_COLS)
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        df[c] = to_date_series(df[c])
    return df

def save_clienti(df: pd.DataFrame):
    out = df.copy()
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti() -> pd.DataFrame:
    if CONTRATTI_CSV.exists():
        df = pd.read_csv(CONTRATTI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
        df.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")
    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio","DataFine"]:
        df[c] = to_date_series(df[c])
    return df

def save_contratti(df: pd.DataFrame):
    out = df.copy()
    for c in ["DataInizio","DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

def load_preventivi() -> pd.DataFrame:
    if PREVENTIVI_CSV.exists():
        df = pd.read_csv(PREVENTIVI_CSV, dtype=str, sep=",", encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=PREVENTIVI_COLS)
        df.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")
    return ensure_columns(df, PREVENTIVI_COLS)

def save_preventivi(df: pd.DataFrame):
    df.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8-sig")

# ==========================
# HTML TABLE
# ==========================
TABLE_CSS = """
<style>
.ctr-table { width:100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th,.ctr-table td { border:1px solid #d0d7de; padding:8px 10px; font-size:13px; vertical-align:top; }
.ctr-table th { background:#e3f2fd; font-weight:600; }
.ctr-row-closed td { background:#ffefef; color:#8a0000; }
.ellipsis { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
</style>
"""

def html_table(df: pd.DataFrame, *, closed_mask: pd.Series | None = None) -> str:
    if df is None or df.empty:
        return TABLE_CSS + "<div style='padding:8px;color:#666'>Nessun dato</div>"
    cols = list(df.columns)
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>"
    rows = []
    for i, r in df.iterrows():
        closed = (closed_mask is not None) and bool(closed_mask.loc[i])
        trc = " class='ctr-row-closed'" if closed else ""
        tds = []
        for c in cols:
            sval = "" if pd.isna(r.get(c, "")) else str(r.get(c, ""))
            sval = sval.replace("\n", "<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows.append(f"<tr{trc}>{''.join(tds)}</tr>")
    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return TABLE_CSS + f"<table class='ctr-table'>{thead}{tbody}</table>"

# ==========================
# AUTH
# ==========================
def do_login() -> Tuple[str, str]:
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")
    st.sidebar.subheader("Login")
    usr = st.sidebar.selectbox("Utente", list(users.keys()))
    pwd = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Entra", use_container_width=True):
        true_pwd = users[usr].get("password", "")
        role = users[usr].get("role", "viewer")
        if pwd == true_pwd:
            st.session_state["auth_user"] = usr
            st.session_state["auth_role"] = role
            st.rerun()
        else:
            st.sidebar.error("Password errata")
    if "auth_user" in st.session_state:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))
    return ("", "")

# ==========================
# DASHBOARD
# ==========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    today = pd.Timestamp.today().normalize()
    year_now = today.year
    stato = df_ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = int((stato != "chiuso").sum())
    contratti_chiusi = int((stato == "chiuso").sum())
    contratti_anno = int((to_date_series(df_ct["DataInizio"]).dt.year == year_now).sum())
    clienti_attivi = int(df_cli["ClienteID"].nunique())

    kpi_html = f"""
    <style>
      .kpi-row{{display:flex;gap:18px;flex-wrap:wrap;margin:8px 0 16px 0}}
      .kpi{{flex:1;min-width:230px;background:#fff;border:1px solid #d0d7de;
             border-radius:14px;padding:16px 18px;box-shadow:0 0 0 2px #f8fafc inset}}
      .kpi .t{{color:#475569;font-weight:600;font-size:15px}}
      .kpi .v{{font-weight:800;font-size:28px;margin-top:6px}}
    </style>
    <div class="kpi-row">
      <div class="kpi"><div class="t">Clienti attivi</div><div class="v">{clienti_attivi}</div></div>
      <div class="kpi"><div class="t">Contratti aperti</div><div class="v">{contratti_aperti}</div></div>
      <div class="kpi"><div class="t">Contratti chiusi</div><div class="v">{contratti_chiusi}</div></div>
      <div class="kpi"><div class="t">Contratti {year_now}</div><div class="v">{contratti_anno}</div></div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    st.markdown("**Cerca cliente**")
    q = st.text_input("Digita il nome o l'ID cliente…", label_visibility="collapsed", placeholder="Nome o ID")
    if q.strip():
        filt = df_cli[
            df_cli["RagioneSociale"].str.contains(q, case=False, na=False) |
            df_cli["ClienteID"].astype(str).str.contains(q, na=False)
        ]
        if not filt.empty:
            sel_id = str(filt.iloc[0]["ClienteID"])
            if st.button(f"Apri scheda cliente {sel_id}"):
                st.session_state["nav_target"] = "Clienti"
                st.session_state["selected_client_id"] = sel_id
                st.rerun()

    st.divider()
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    ct = df_ct.copy()
    ct["DataFine"] = to_date_series(ct["DataFine"])
    open_mask = ct["Stato"].fillna("aperto").str.lower() != "chiuso"
    within_6m = (ct["DataFine"].notna() &
                 (ct["DataFine"] >= today) &
                 (ct["DataFine"] <= today + pd.DateOffset(months=6)))
    scad = ct[open_mask & within_6m].copy()
    if not scad.empty:
        scad = scad.sort_values(["ClienteID", "DataFine"]).groupby("ClienteID", as_index=False).first()
        disp = pd.DataFrame({
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
            "DataFine": scad["DataFine"].apply(fmt_date),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "TotRata": scad["TotRata"].apply(money)
        })
        st.markdown(html_table(disp), unsafe_allow_html=True)
    else:
        st.info("Nessun contratto in scadenza entro 6 mesi.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecall"] = to_date_series(cli["UltimoRecall"])
        soglia = pd.Timestamp.today().normalize() - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall"].notna() & (cli["UltimoRecall"] <= soglia)]
        tab = r.loc[:, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]].copy()
        tab["UltimoRecall"] = tab["UltimoRecall"].apply(fmt_date)
        tab["ProssimoRecall"] = to_date_series(tab["ProssimoRecall"]).apply(fmt_date)
        st.markdown(html_table(tab), unsafe_allow_html=True)

    with c2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisita"] = to_date_series(cli["UltimaVisita"])
        soglia_v = pd.Timestamp.today().normalize() - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita"].notna() & (cli["UltimaVisita"] <= soglia_v)]
        tab = v.loc[:, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]].copy()
        tab["UltimaVisita"] = tab["UltimaVisita"].apply(fmt_date)
        tab["ProssimaVisita"] = to_date_series(tab["ProssimaVisita"]).apply(fmt_date)
        st.markdown(html_table(tab), unsafe_allow_html=True)
# ==========================
# CLIENTI
# ==========================
def _replace_docx_placeholders(doc: Document, mapping: Dict[str, str]):
    """Sostituisce <<...>> in tutto il documento, anche se spezzati in più run."""
    for p in doc.paragraphs:
        full_text = "".join(run.text for run in p.runs)
        for key, val in mapping.items():
            token = f"<<{key}>>"
            if token in full_text:
                full_text = full_text.replace(token, val)
        for i in range(len(p.runs)):
            p.runs[i].text = ""
        if p.runs:
            p.runs[0].text = full_text
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                _replace_docx_placeholders(cell, mapping)

def _gen_offerta_number(df_prev: pd.DataFrame, cliente_id: str, nome_cliente: str) -> str:
    sub = df_prev[df_prev["ClienteID"].astype(str) == str(cliente_id)]
    if sub.empty:
        seq = 1
    else:
        try:
            seq = max(int(x.split("-")[-1]) for x in sub["NumeroOfferta"].tolist() if "-" in x) + 1
        except Exception:
            seq = len(sub) + 1
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in str(nome_cliente))[:20].strip("_")
    return f"SHT-MI-{safe_name}-{cliente_id}-{seq:03d}"

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except Exception:
            idx = 0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=min(idx, len(labels)-1))
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    row = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0]

    # riepilogo
    st.markdown("### Riepilogo cliente")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**ID:** {row['ClienteID']}  ")
        st.markdown(f"**Ragione Sociale:** {row['RagioneSociale']}")
        st.markdown(f"**Referente:** {row['PersonaRiferimento']}")
    with c2:
        st.markdown(f"**Indirizzo:** {row['Indirizzo']}")
        st.markdown(f"**Città:** {row['CAP']} {row['Citta']}")
        st.markdown(f"**Telefono/Cell:** {row['Telefono']} / {row['Cell']}")
    with c3:
        st.markdown(f"**Email:** {row['Email']}")
        st.markdown(f"**P.IVA:** {row['PartitaIVA']}")
        st.markdown(f"**SDI:** {row['SDI']}")

    # note modificabili
    note_new = st.text_area("Note", row.get("Note",""))
    if st.button("Salva note"):
        idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
        df_cli.loc[idx_row, "Note"] = note_new
        save_clienti(df_cli)
        st.success("Note aggiornate.")
        st.rerun()

    st.divider()
    with st.expander("Modifica anagrafica", expanded=False):
        with st.form("frm_anagrafica"):
            c1, c2, c3 = st.columns(3)
            with c1:
                ragsoc = st.text_input("Ragione sociale", row.get("RagioneSociale",""))
                indir = st.text_input("Indirizzo", row.get("Indirizzo",""))
                cap = st.text_input("CAP", row.get("CAP",""))
            with c2:
                citta = st.text_input("Città", row.get("Citta",""))
                ref = st.text_input("Persona di riferimento", row.get("PersonaRiferimento",""))
                tel = st.text_input("Telefono", row.get("Telefono",""))
            with c3:
                cell = st.text_input("Cell", row.get("Cell",""))
                mail = st.text_input("Email", row.get("Email",""))
                piva = st.text_input("Partita IVA", str(row.get("PartitaIVA","")))
            c1b, c2b, c3b, c4b = st.columns(4)
            with c1b:
                ult_recall = date_input_opt("Ultimo recall", row.get("UltimoRecall"), key=f"ur_{sel_id}")
            with c2b:
                pross_recall = date_input_opt("Prossimo recall", row.get("ProssimoRecall"), key=f"pr_{sel_id}")
            with c3b:
                ult_visita = date_input_opt("Ultima visita", row.get("UltimaVisita"), key=f"uv_{sel_id}")
            with c4b:
                pross_visita = date_input_opt("Prossima visita", row.get("ProssimaVisita"), key=f"pv_{sel_id}")

            if st.form_submit_button("Salva modifiche", use_container_width=True):
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
                df_cli.loc[idx_row, "UltimoRecall"] = pd.to_datetime(ult_recall) if ult_recall else ""
                df_cli.loc[idx_row, "ProssimoRecall"] = pd.to_datetime(pross_recall) if pross_recall else ""
                df_cli.loc[idx_row, "UltimaVisita"] = pd.to_datetime(ult_visita) if ult_visita else ""
                df_cli.loc[idx_row, "ProssimaVisita"] = pd.to_datetime(pross_visita) if pross_visita else ""
                save_clienti(df_cli)
                st.success("Anagrafica aggiornata.")
                st.rerun()

    st.divider()
    if st.button("Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = sel_id
        st.rerun()

    st.divider()
    st.markdown("### Preventivi")
    df_prev = load_preventivi()
    tpl_label = st.radio("Seleziona template", list(TEMPLATE_OPTIONS.keys()), horizontal=True)
    tpl_file = TEMPLATE_OPTIONS[tpl_label]
    tpl_path = TEMPLATES_DIR / tpl_file

    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("Campi compilati automaticamente")
        st.write(f"**Cliente:** {row.get('RagioneSociale','')}")
        st.write(f"**Indirizzo:** {row.get('Indirizzo','')} — {row.get('CAP','')} {row.get('Citta','')}")
        st.write("**Data documento:** oggi")
        if st.button("Genera preventivo", type="primary"):
            if not tpl_path.exists():
                st.error(f"Template non trovato: {tpl_file}")
            else:
                client_folder = EXTERNAL_PROPOSALS_DIR / str(sel_id)
                client_folder.mkdir(parents=True, exist_ok=True)
                numero_offerta = _gen_offerta_number(df_prev, sel_id, row.get("RagioneSociale",""))
                doc = Document(str(tpl_path))
                mapping = {
                    "CLIENTE": row.get("RagioneSociale",""),
                    "INDIRIZZO": row.get("Indirizzo",""),
                    "CITTA": f"{row.get('CAP','')} {row.get('Citta','')}".strip(),
                    "DATA": datetime.today().strftime("%d/%m/%Y"),
                    "NUMERO_OFFERTA": numero_offerta,
                }
                _replace_docx_placeholders(doc, mapping)
                filename = f"{numero_offerta}.docx"
                out_path = client_folder / filename
                doc.save(str(out_path))
                new_row = {
                    "ClienteID": sel_id,
                    "NumeroOfferta": numero_offerta,
                    "Template": tpl_file,
                    "NomeFile": filename,
                    "Percorso": str(out_path),
                    "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                df_prev = pd.concat([df_prev, pd.DataFrame([new_row])], ignore_index=True)
                save_preventivi(df_prev)
                st.success(f"Preventivo creato: {filename}")
                st.rerun()

    with col_b:
        st.caption("Elenco preventivi del cliente")
        sub = df_prev[df_prev["ClienteID"].astype(str)==sel_id].copy().sort_values("DataCreazione", ascending=False)
        if sub.empty:
            st.info("Nessun preventivo per questo cliente.")
        else:
            for i, r in sub.iterrows():
                box = st.container(border=True)
                with box:
                    c1, c2 = st.columns([0.7, 0.3])
                    with c1:
                        st.markdown(f"**{r['NumeroOfferta']}** — {r['Template']}")
                        st.caption(r.get("DataCreazione",""))
                    with c2:
                        path = Path(r["Percorso"])
                        if path.exists():
                            with open(path, "rb") as fh:
                                st.download_button(
                                    "Apri/Scarica",
                                    data=fh.read(),
                                    file_name=path.name,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_{i}"
                                )
                        else:
                            st.error("File non trovato (es. OneDrive).")

# ==========================
# CONTRATTI
# ==========================
def _xlsx_bytes_from_df(df_disp: pd.DataFrame):
    try:
        import xlsxwriter
    except Exception:
        return None
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df_disp.to_excel(writer, sheet_name="Contratti", index=False)
        wb = writer.book
        ws = writer.sheets["Contratti"]
        ws.set_landscape(); ws.set_paper(9)
        wrap = wb.add_format({"text_wrap": True, "valign": "top"})
        header = wb.add_format({"bold": True, "bg_color": "#EEF7FF", "border": 1})
        for c, name in enumerate(df_disp.columns):
            ws.write(0, c, name, header)
            if "descrizione" in str(name).lower():
                ws.set_column(c, c, 60, wrap)
            else:
                ws.set_column(c, c, 14)
    bio.seek(0)
    return bio.getvalue()

def generate_pdf_table(df: pd.DataFrame, title: str) -> bytes | None:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, title, ln=True, align="C")
    pdf.set_font("Arial", size=9)
    cols = list(df.columns)
    widths = [30, 25, 25, 20, 120, 20, 20, 25, 20]
    for i, c in enumerate(cols):
        pdf.cell(widths[i], 8, c, border=1)
    pdf.ln()
    for _, row in df.iterrows():
        for i, c in enumerate(cols):
            val = "" if pd.isna(row.get(c,"")) else str(row.get(c,""))
            pdf.cell(widths[i], 6, val, border=1)
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti")
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return
    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except Exception:
            idx = 0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=min(idx, len(labels)-1))
    sel_id = df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"]
    rag_soc = df_cli[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0]["RagioneSociale"]

    with st.expander(f"Nuovo contratto per «{rag_soc}»"):
        with st.form("frm_new_contract"):
            num = st.text_input("Numero contratto")
            din = st.date_input("Data inizio", format="DD/MM/YYYY")
            durata = st.selectbox("Durata (mesi)", [12,24,36,48,60,72], index=0)
            desc = st.text_area("Descrizione prodotto")
            nol_fin = st.text_input("NOL_FIN")
            nol_int = st.text_input("NOL_INT")
            tota = st.text_input("TotRata")
            if st.form_submit_button("Crea contratto"):
                row = {
                    "ClienteID": str(sel_id),
                    "NumeroContratto": num,
                    "DataInizio": pd.to_datetime(din),
                    "DataFine": pd.to_datetime(din) + pd.DateOffset(months=int(durata)),
                    "Durata": str(durata),
                    "DescrizioneProdotto": desc,
                    "NOL_FIN": nol_fin,
                    "NOL_INT": nol_int,
                    "TotRata": tota,
                    "Stato": "aperto",
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([row])], ignore_index=True)
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
    st.markdown(html_table(disp[["NumeroContratto","DataInizio","DataFine","Durata",
                 "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]],
                 closed_mask=closed_mask), unsafe_allow_html=True)

    st.divider()
    st.markdown("### Azioni")
    i_sel = st.selectbox("Seleziona contratto", list(ct.index), format_func=lambda i: f"{ct.loc[i,'NumeroContratto']} – {fmt_date(ct.loc[i,'DataInizio'])}")
    curr = (ct.loc[i_sel, "Stato"] or "aperto").lower()
    c1, c2, c3 = st.columns(3)
    with c1:
        if curr == "chiuso":
            if st.button("Riapri contratto"):
                df_ct.loc[i_sel, "Stato"] = "aperto"
                save_contratti(df_ct)
                st.success("Contratto riaperto.")
                st.rerun()
        else:
            if st.button("Chiudi contratto"):
                df_ct.loc[i_sel, "Stato"] = "chiuso"
                save_contratti(df_ct)
                st.success("Contratto chiuso.")
                st.rerun()
    with c2:
        xlsx_bytes = _xlsx_bytes_from_df(disp)
        if xlsx_bytes:
            st.download_button("Esporta Excel", data=xlsx_bytes,
                               file_name=f"contratti_{rag_soc}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c3:
        pdf_bytes = generate_pdf_table(disp, f"Contratti – {rag_soc}")
        if pdf_bytes:
            st.download_button("Scarica PDF", data=pdf_bytes,
                               file_name=f"contratti_{rag_soc}.pdf", mime="application/pdf")

# ==========================
# APP
# ==========================
def main():
    st.set_page_config(page_title="SHT – Gestionale", layout="wide")
    st.markdown(f"<h3 style='margin-top:8px'>{APP_TITLE}</h3>", unsafe_allow_html=True)
    user, role = do_login()
    if user and role:
        st.sidebar.success(f"Utente: {user} — Ruolo: {role}")
    else:
        st.sidebar.info("Accesso come ospite")

    PAGES = {"Dashboard": page_dashboard, "Clienti": page_clienti, "Contratti": page_contratti}
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("Menu", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)

    df_cli = load_clienti()
    df_ct = load_contratti()
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
