# app.py — Gestionale Clienti SHT (dashboard, clienti+preventivi, contratti tabella unica)

from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime, date
from typing import Tuple, Dict

import pandas as pd
import streamlit as st
from docx import Document

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

# Cartella esterna (es. OneDrive). Se non impostata -> usa STORAGE_DIR/preventivi
EXTERNAL_PROPOSALS_DIR = Path(
    st.secrets.get("storage", {}).get("proposals_dir", (STORAGE_DIR / "preventivi"))
)
EXTERNAL_PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)

# colonne canoniche
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

# Mappa radio -> file template (nomi come in storage/templates)
TEMPLATE_OPTIONS: Dict[str, str] = {
    "Offerta – Centralino":     "Offerta_Centralino.docx",
    "Offerta – Varie":          "Offerta_Varie.docx",
    "Offerta – A3":             "Offerte_A3.docx",
    "Offerta – A4":             "Offerte_A4.docx",
}

# ==========================
# UTILS
# ==========================

def as_date(x):
    """Converte robustamente in Timestamp; supporto dd/mm/yyyy."""
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
        return f"{v:.2f}"
    except Exception:
        return ""

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def safe_text(v) -> str:
    """Restituisce stringa sicura per text_input (mai pd.NA/None)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    try:
        if pd.isna(v):  # pd.NA
            return ""
    except Exception:
        pass
    return str(v)

def safe_date_for_widget(v):
    """Restituisce date | None per date_input."""
    d = as_date(v)
    if pd.isna(d):
        return None
    return d.date()

def slugify_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:24] if s else "cliente"

# ==========================
# I/O DATI
# ==========================

def load_clienti() -> pd.DataFrame:
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",").fillna("")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False)
    df = ensure_columns(df, CLIENTI_COLS)
    # date
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        df[c] = to_date_series(df[c])
    return df

def save_clienti(df: pd.DataFrame):
    out = df.copy()
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False)

def load_contratti() -> pd.DataFrame:
    if CONTRATTI_CSV.exists():
        df = pd.read_csv(CONTRATTI_CSV, dtype=str, sep=",").fillna("")
    else:
        df = pd.DataFrame(columns=CONTRATTI_COLS)
        df.to_csv(CONTRATTI_CSV, index=False)
    df = ensure_columns(df, CONTRATTI_COLS)
    for c in ["DataInizio","DataFine"]:
        df[c] = to_date_series(df[c])
    return df

def save_contratti(df: pd.DataFrame):
    out = df.copy()
    for c in ["DataInizio","DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False)

def load_preventivi() -> pd.DataFrame:
    if PREVENTIVI_CSV.exists():
        df = pd.read_csv(PREVENTIVI_CSV, dtype=str, sep=",").fillna("")
    else:
        df = pd.DataFrame(columns=PREVENTIVI_COLS)
        df.to_csv(PREVENTIVI_CSV, index=False)
    return ensure_columns(df, PREVENTIVI_COLS)

def save_preventivi(df: pd.DataFrame):
    df.to_csv(PREVENTIVI_CSV, index=False)

# ==========================
# HTML TABLE COMPATIBILE
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
    thead = "<thead><tr>" + "".join("<th>{}</th>".format(c) for c in cols) + "</tr></thead>"

    rows = []
    for i, r in df.iterrows():
        closed = (closed_mask is not None) and bool(closed_mask.loc[i])
        trc = " class='ctr-row-closed'" if closed else ""
        tds = []
        for c in cols:
            sval = "" if pd.isna(r.get(c, "")) else str(r.get(c, ""))
            sval = sval.replace("\n", "<br>")
            tds.append("<td class='ellipsis'>{}</td>".format(sval))
        rows.append("<tr{}>{}</tr>".format(trc, "".join(tds)))

    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return TABLE_CSS + "<table class='ctr-table'>{}{}</table>".format(thead, tbody)

def _build_print_html(df: pd.DataFrame, titolo: str) -> str:
    cols = list(df.columns)
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>"
    rows = []
    for _, r in df.iterrows():
        tds = []
        for c in cols:
            sval = "" if pd.isna(r.get(c, "")) else str(r.get(c, ""))
            sval = sval.replace("\n", "<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows.append("<tr>" + "".join(tds) + "</tr>")
    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return f"""
    <div style="margin-bottom:10px;font-weight:700">{titolo}</div>
    {TABLE_CSS}
    <table class='ctr-table'>{thead}{tbody}</table>
    <div style="margin-top:12px;color:#666">Suggerimento: usa “Stampa” del browser per salvare in PDF.</div>
    """

# ==========================
# AUTH SEMPLICE
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
# PAGINE
# ==========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    # KPI
    today = pd.Timestamp.today().normalize()
    year_now = today.year
    stato = df_ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = int((stato != "chiuso").sum())
    contratti_chiusi = int((stato == "chiuso").sum())
    contratti_anno   = int((to_date_series(df_ct["DataInizio"]).dt.year == year_now).sum())
    clienti_attivi   = int(df_cli["ClienteID"].nunique())

    kpi_html = f"""
    <style>
      .kpi-row{{display:flex;gap:18px;flex-wrap:nowrap;margin:8px 0 16px 0}}
      .kpi{{width:260px;background:#fff;border:1px solid #d0d7de;border-radius:14px;padding:16px 18px}}
      .kpi .t{{color:#475569;font-weight:600;font-size:15px}}
      .kpi .v{{font-weight:800;font-size:28px;margin-top:6px}}
      .kpi.green{{box-shadow:0 0 0 2px #d1fae5 inset}}
      .kpi.red{{box-shadow:0 0 0 2px #fee2e2 inset}}
      .kpi.yellow{{box-shadow:0 0 0 2px #fef3c7 inset}}
      @media (max-width: 1200px) {{
        .kpi-row{{flex-wrap:wrap}}
        .kpi{{width:calc(50% - 9px)}}
      }}
      @media (max-width: 700px) {{
        .kpi{{width:100%}}
      }}
    </style>
    <div class="kpi-row">
      <div class="kpi"><div class="t">Clienti attivi</div><div class="v">{clienti_attivi}</div></div>
      <div class="kpi green"><div class="t">Contratti aperti</div><div class="v">{contratti_aperti}</div></div>
      <div class="kpi red"><div class="t">Contratti chiusi</div><div class="v">{contratti_chiusi}</div></div>
      <div class="kpi yellow"><div class="t">Contratti {year_now}</div><div class="v">{contratti_anno}</div></div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    # Ricerca rapida
    st.markdown("**Cerca cliente**")
    q = st.text_input("Digita il nome o l'ID cliente…", label_visibility="collapsed")
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

    # Contratti in scadenza entro 6 mesi (Cliente, DataFine, Descrizione, TotRata)
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

    disp = pd.DataFrame()
    if not scad.empty:
        labels = df_cli.set_index("ClienteID")["RagioneSociale"]
        disp = pd.DataFrame({
            "Cliente": scad["ClienteID"].map(labels).fillna(scad["ClienteID"].astype(str)),
            "DataFine": scad["DataFine"].apply(fmt_date),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "TotRata": scad["TotRata"].apply(money)
        })
    st.markdown(html_table(disp), unsafe_allow_html=True)

    st.divider()

    # Ultimi recall/visite
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

# ----- componenti riuso per Clienti -----
def _summary_box(row: pd.Series):
    st.markdown("### Riepilogo")
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

def _gen_offerta_number(df_prev: pd.DataFrame, cliente_id: str, ragsoc: str) -> str:
    sub = df_prev[df_prev["ClienteID"].astype(str) == str(cliente_id)]
    if sub.empty:
        seq = 1
    else:
        try:
            seq = max(int(x.split("-")[-1]) for x in sub["NumeroOfferta"].tolist() if "-" in x) + 1
        except Exception:
            seq = len(sub) + 1
    slug = slugify_name(ragsoc)
    return f"SHT-MI-{slug}-{seq:03d}"

def _replace_docx_placeholders(doc: Document, mapping: Dict[str, str]):
    def repl_in_paragraph(p):
        for run in p.runs:
            for key, val in mapping.items():
                token = f"<<{key}>>"
                if token in run.text:
                    run.text = run.text.replace(token, val)
    for p in doc.paragraphs:
        repl_in_paragraph(p)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    repl_in_paragraph(p)

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
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])

    row = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0]
    _summary_box(row)
    st.divider()

    # ---- NOTE fuori dall’anagrafica
    with st.form("frm_note", clear_on_submit=False, border=True):
        st.markdown("### Note cliente")
        note_val = st.text_area("Note", safe_text(row.get("Note","")), height=120, label_visibility="collapsed")
        if st.form_submit_button("Salva note"):
            idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
            df_cli.loc[idx_row, "Note"] = note_val
            save_clienti(df_cli)
            st.success("Note aggiornate.")
            st.rerun()

    # ---- Anagrafica modificabile (expander)
    with st.expander("Anagrafica (modificabile)", expanded=False):
        with st.form("frm_anagrafica"):
            ragsoc = st.text_input("Ragione sociale", safe_text(row.get("RagioneSociale","")))
            indir  = st.text_input("Indirizzo", safe_text(row.get("Indirizzo","")))
            cap    = st.text_input("CAP", safe_text(row.get("CAP","")))
            citta  = st.text_input("Città", safe_text(row.get("Citta","")))
            ref    = st.text_input("Persona di riferimento", safe_text(row.get("PersonaRiferimento","")))
            tel    = st.text_input("Telefono", safe_text(row.get("Telefono","")))
            cell   = st.text_input("Cell", safe_text(row.get("Cell","")))
            mail   = st.text_input("Email", safe_text(row.get("Email","")))
            piva   = st.text_input("Partita IVA", safe_text(row.get("PartitaIVA","")))
            sdi    = st.text_input("SDI", safe_text(row.get("SDI","")))

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                ult_recall   = st.date_input("Ultimo recall", value=safe_date_for_widget(row.get("UltimoRecall")))
            with c2:
                pross_recall = st.date_input("Prossimo recall", value=safe_date_for_widget(row.get("ProssimoRecall")))
            with c3:
                ult_visita   = st.date_input("Ultima visita", value=safe_date_for_widget(row.get("UltimaVisita")))
            with c4:
                pross_visita = st.date_input("Prossima visita", value=safe_date_for_widget(row.get("ProssimaVisita")))

            if st.form_submit_button("Salva modifiche", use_container_width=True):
                idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
                df_cli.loc[idx_row, "RagioneSociale"]     = ragsoc
                df_cli.loc[idx_row, "Indirizzo"]          = indir
                df_cli.loc[idx_row, "CAP"]                = cap
                df_cli.loc[idx_row, "Citta"]              = citta
                df_cli.loc[idx_row, "PersonaRiferimento"] = ref
                df_cli.loc[idx_row, "Telefono"]           = tel
                df_cli.loc[idx_row, "Cell"]               = cell
                df_cli.loc[idx_row, "Email"]              = mail
                df_cli.loc[idx_row, "PartitaIVA"]         = piva  # tenuta stringa (non perde zeri)
                df_cli.loc[idx_row, "SDI"]                = sdi
                # date
                df_cli.loc[idx_row, "UltimoRecall"]   = pd.to_datetime(ult_recall) if isinstance(ult_recall, date) else ""
                df_cli.loc[idx_row, "ProssimoRecall"] = pd.to_datetime(pross_recall) if isinstance(pross_recall, date) else ""
                df_cli.loc[idx_row, "UltimaVisita"]   = pd.to_datetime(ult_visita) if isinstance(ult_visita, date) else ""
                df_cli.loc[idx_row, "ProssimaVisita"] = pd.to_datetime(pross_visita) if isinstance(pross_visita, date) else ""
                save_clienti(df_cli)
                st.success("Dati cliente aggiornati.")
                st.rerun()

    st.divider()

    if st.button("Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = sel_id
        st.rerun()

    st.divider()

    # ---- Preventivi
    st.markdown("### Preventivi")
    df_prev = load_preventivi()

    tpl_label = st.radio("Seleziona template", list(TEMPLATE_OPTIONS.keys()), horizontal=True)
    tpl_file = TEMPLATE_OPTIONS[tpl_label]
    tpl_path = TEMPLATES_DIR / tpl_file

    col_a, col_b = st.columns([0.5, 0.5], gap="large")
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

                numero_offerta = _gen_offerta_number(df_prev, sel_id, safe_text(row.get("RagioneSociale","")))

                # prepara DOCX
                doc = Document(str(tpl_path))
                mapping = {
                    "CLIENTE": safe_text(row.get("RagioneSociale","")),
                    "INDIRIZZO": safe_text(row.get("Indirizzo","")),
                    "CITTA": f"{safe_text(row.get('CAP',''))} {safe_text(row.get('Citta',''))}".strip(),
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
        sub = df_prev[df_prev["ClienteID"].astype(str) == sel_id].copy()
        sub = sub.sort_values("DataCreazione", ascending=False)
        if sub.empty:
            st.info("Nessun preventivo per questo cliente.")
        else:
            for i, r in sub.iterrows():
                box = st.container(border=True)
                with box:
                    c1, c2, c3 = st.columns([0.55, 0.25, 0.20])
                    with c1:
                        st.markdown(f"**{r['NumeroOfferta']}** — {r['Template']}")
                        st.caption(r.get("DataCreazione",""))
                    with c2:
                        st.caption(r.get("NomeFile",""))
                        st.caption(Path(r["Percorso"]).parent.name)
                    with c3:
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
                            st.error("File non trovato (controlla percorso OneDrive).")

# --------- CONTRATTI: TABELLONE UNICO OPERATIVO ----------
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti")

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # selezione cliente
    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except Exception:
            idx = 0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    cliente_nome = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0]["RagioneSociale"]

    # dataset
    ct = df_ct[df_ct["ClienteID"].astype(str)==str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")

    # pulsanti
    colb1, colb2, colb3, colb4 = st.columns([0.22,0.22,0.22,0.34])
    with colb1:
        open_form = st.toggle("➕ Nuovo contratto", value=False, help="Apri il form per inserirne uno nuovo")
    with colb2:
        export_sel = st.button("Esporta Excel (selezionati)")
    with colb3:
        export_all = st.button("Esporta Excel (tutti)")
    with colb4:
        show_print = st.button("Vista stampa / PDF")

    # form nuovo contratto
    if open_form:
        with st.form("frm_new_contract", border=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                num_ctr  = st.text_input("Numero contratto")
                durata   = st.selectbox("Durata (mesi)", ["12","24","36","48","60","72"])
            with c2:
                data_in  = st.date_input("Data inizio", value=None)
            with c3:
                data_end = st.date_input("Data fine", value=None)
            with c4:
                stato    = st.selectbox("Stato", ["aperto","chiuso"], index=0)

            descr    = st.text_area("Descrizione prodotto")
            c5, c6, c7 = st.columns(3)
            with c5: nol_fin = st.text_input("NOL_FIN", value="")
            with c6: nol_int = st.text_input("NOL_INT", value="")
            with c7: tot_rata = st.text_input("TotRata", value="")

            if st.form_submit_button("Salva contratto", type="primary"):
                if not num_ctr.strip():
                    st.error("Numero contratto obbligatorio.")
                else:
                    new_ctr = {
                        "ClienteID": sel_id,
                        "NumeroContratto": num_ctr.strip(),
                        "DataInizio": pd.to_datetime(data_in) if isinstance(data_in, date) else "",
                        "DataFine":   pd.to_datetime(data_end) if isinstance(data_end, date) else "",
                        "Durata": durata,
                        "DescrizioneProdotto": descr,
                        "NOL_FIN": nol_fin, "NOL_INT": nol_int, "TotRata": tot_rata,
                        "Stato": stato,
                    }
                    df_ct2 = pd.concat([df_ct, pd.DataFrame([new_ctr])], ignore_index=True)
                    save_contratti(df_ct2)
                    st.success("Contratto creato.")
                    st.rerun()

    # tabella operativa
    if not ct.empty:
        disp = ct.copy()
        disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
        disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
        disp["TotRata"]    = disp["TotRata"].apply(money)

        df_view = disp.copy()
        df_view.insert(0, "Seleziona", False)

        st.markdown("### Contratti (tabella operativa)")
        edited = st.data_editor(
            df_view,
            hide_index=True,
            use_container_width=True,
            height=420,
            column_config={
                "Seleziona": st.column_config.CheckboxColumn(required=False),
                "DescrizioneProdotto": st.column_config.TextColumn(width="large"),
            },
            disabled=[c for c in df_view.columns if c != "Seleziona"],
            key=f"contr_{sel_id}"
        )

        # anteprima descrizione completa
        st.caption("Anteprima descrizione (seleziona la riga qui sotto)")
        scelte = [f"{r['NumeroContratto']} — {r['DataInizio'] or ''} / {r['DataFine'] or ''}"
                  for _, r in edited.iterrows()]
        if scelte:
            focus = st.selectbox("Riga in focus", scelte, index=0, label_visibility="collapsed")
            i_focus = scelte.index(focus)
            st.info(edited.iloc[i_focus]["DescrizioneProdotto"] or "")

        # export excel
        def _excel_download(df_to_xlsx: pd.DataFrame, name_suffix: str):
            from io import BytesIO
            out = BytesIO()
            with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
                workbook  = writer.book
                ws = workbook.add_worksheet("Contratti")
                title_fmt = workbook.add_format({"bold": True, "align": "center"})
                ws.merge_range(0, 0, 0, df_to_xlsx.shape[1]-1,
                               f"Cliente: {cliente_nome}", title_fmt)
                df_to_xlsx.to_excel(writer, sheet_name="Contratti", startrow=2, index=False)
            st.download_button(
                f"Scarica Excel {name_suffix}",
                data=out.getvalue(),
                file_name=f"Contratti_{sel_id}_{name_suffix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"xls_{name_suffix}"
            )

        if export_sel:
            sel_rows = edited[edited["Seleziona"] == True].drop(columns=["Seleziona"], errors="ignore")
            if sel_rows.empty:
                st.warning("Nessuna riga selezionata.")
            else:
                _excel_download(sel_rows, "selezionati")

        if export_all:
            _excel_download(edited.drop(columns=["Seleziona"], errors="ignore"), "tutti")

        # vista stampa / PDF
        if show_print:
            html = _build_print_html(
                edited.drop(columns=["Seleziona"], errors="ignore"),
                f"Cliente: {cliente_nome}"
            )
            st.markdown(html, unsafe_allow_html=True)

        st.divider()

        # azioni chiudi/riapri
        st.markdown("### Azioni per riga")
        for i, r in ct.iterrows():
            c1, c2, c3 = st.columns([0.05, 0.75, 0.20])
            with c1:
                st.write(" ")
            with c2:
                st.caption(f"{r.get('NumeroContratto','')} — {r.get('DescrizioneProdotto','')}")
            with c3:
                curr = (str(r.get("Stato","aperto")) or "aperto").lower()
                if curr == "chiuso":
                    if st.button("Riapri", key=f"open_{i}"):
                        df_ct.loc[i, "Stato"] = "aperto"
                        save_contratti(df_ct)
                        st.success("Contratto riaperto.")
                        st.rerun()
                else:
                    if st.button("Chiudi", key=f"close_{i}"):
                        df_ct.loc[i, "Stato"] = "chiuso"
                        save_contratti(df_ct)
                        st.success("Contratto chiuso.")
                        st.rerun()

# ==========================
# APP
# ==========================
def main():
    st.set_page_config(page_title="SHT – Gestionale", layout="wide")
    st.markdown(f"<h3 style='margin-top:8px'>{APP_TITLE}</h3>", unsafe_allow_html=True)

    # login
    user, role = do_login()
    if user and role:
        st.sidebar.success(f"Utente: {user} — Ruolo: {role}")
    else:
        st.sidebar.info("Accesso come ospite")

    # nav
    PAGES = {"Dashboard": page_dashboard, "Clienti": page_clienti, "Contratti": page_contratti}
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("Menu", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)

    # carica dati
    df_cli = load_clienti()
    df_ct  = load_contratti()

    # run pagina
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
