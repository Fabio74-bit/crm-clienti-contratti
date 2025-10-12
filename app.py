# app.py — Gestionale Clienti SHT (dashboard “buona” + clienti + contratti nuovo layout)
from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Tuple, Dict

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from docx import Document

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
TEMPLATES_DIR   = STORAGE_DIR / "templates"

EXTERNAL_PROPOSALS_DIR = Path(
    st.secrets.get("storage", {}).get("proposals_dir", (STORAGE_DIR / "preventivi"))
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
    "Offerta – Varie":      "Offerta_Varie.docx",
    "Offerta – A3":         "Offerte_A3.docx",
    "Offerta – A4":         "Offerte_A4.docx",
}

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
        return f"{v:.2f}"
    except Exception:
        return ""

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def _safe_txt(x: object) -> str:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ""
    s = str(x)
    return "" if s.lower() in ("nan", "nat", "none") else s

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
# HTML TABLE
# ==========================
BASE_CSS = """
<style>
:root{--b:#0ea5e9;--g:#22c55e;--y:#f59e0b;--r:#ef4444;--bd:#d0d7de}
.card{background:#fff;border:1px solid var(--bd);border-radius:14px;padding:16px 18px}
.badge{display:inline-block;padding:8px 12px;border-radius:12px;background:#e8f0fe;color:#1d4ed8;font-weight:700}
.ctr-table{width:100%;border-collapse:collapse;table-layout:fixed}
.ctr-table th,.ctr-table td{border:1px solid var(--bd);padding:8px 10px;font-size:13px;vertical-align:top}
.ctr-table th{background:#f1f5f9;font-weight:700;color:#0f172a}
.ctr-row-closed td{background:#ffefef;color:#8a0000}
.ellipsis{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.preview{margin-top:10px;border-radius:12px;background:#e7f0ff;padding:12px 14px}
</style>
"""

def html_table(df: pd.DataFrame, *, closed_mask: pd.Series | None = None) -> str:
    if df is None or df.empty:
        return BASE_CSS + "<div style='padding:8px;color:#666'>Nessun dato</div>"

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
        rows.append("<tr{} data-row='{}'>{}</tr>".format(trc, i, "".join(tds)))

    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return BASE_CSS + "<table class='ctr-table' id='tbl'>{}{}</table>".format(thead, tbody)

def html_table_interactive(disp: pd.DataFrame, *, desc_series: pd.Series, closed_mask: pd.Series) -> None:
    """Tabella HTML + JS: doppio-click riga → mostra descrizione completa (safe via JSON)."""
    table_html = html_table(disp, closed_mask=closed_mask)

    # mappa idx -> descrizione (con <br>)
    mapping = {int(i): ("" if pd.isna(v) else str(v)).replace("\n", "<br>") for i, v in desc_series.items()}
    # serializzazione in JSON (evita backslash nelle f-string)
    items_json = json.dumps(mapping, ensure_ascii=False)

    html = f"""
{table_html}
<div class="preview" id="descBox">Doppio-click su una riga per vedere la descrizione completa.</div>
<script>
const DESCR = {items_json};
const tbl = document.getElementById('tbl');
const box = document.getElementById('descBox');
if (tbl){{
  tbl.addEventListener('dblclick', (e)=>{{
    let tr = e.target.closest('tr');
    if (!tr) return;
    let key = tr.getAttribute('data-row');
    if (key in DESCR){{
      box.innerHTML = DESCR[key] || "(nessuna descrizione)";
      box.scrollIntoView({{behavior:'smooth', block:'nearest'}});
    }}
  }});
}}
</script>
"""
    components.html(html, height=460, scrolling=True)

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
# PAGINE
# ==========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    today = pd.Timestamp.today().normalize()
    year_now = today.year
    stato = df_ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = int((stato != "chiuso").sum())
    contratti_chiusi = int((stato == "chiuso").sum())
    contratti_anno   = int((to_date_series(df_ct["DataInizio"]).dt.year == year_now).sum())
    clienti_attivi   = int(df_cli["ClienteID"].nunique())

    kpi_html = f"""
{BASE_CSS}
<div style="display:flex;gap:18px;flex-wrap:wrap;margin:8px 0 16px 0">
  <div class="card" style="width:260px"><div>Clienti attivi</div><div style="font-weight:800;font-size:28px">{clienti_attivi}</div></div>
  <div class="card" style="width:260px;box-shadow:0 0 0 2px #d1fae5 inset"><div>Contratti aperti</div><div style="font-weight:800;font-size:28px">{contratti_aperti}</div></div>
  <div class="card" style="width:260px;box-shadow:0 0 0 2px #fee2e2 inset"><div>Contratti chiusi</div><div style="font-weight:800;font-size:28px">{contratti_chiusi}</div></div>
  <div class="card" style="width:260px;box-shadow:0 0 0 2px #fef3c7 inset"><div>Contratti {year_now}</div><div style="font-weight:800;font-size:28px">{contratti_anno}</div></div>
</div>
"""
    st.markdown(kpi_html, unsafe_allow_html=True)

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
def _summary_box(row: pd.Series):
    st.markdown("### Riepilogo")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**ClienteID:** {_safe_txt(row.get('ClienteID'))}")
        st.markdown(f"**Ragione Sociale:** {_safe_txt(row.get('RagioneSociale'))}")
        st.markdown(f"**Riferimento:** {_safe_txt(row.get('PersonaRiferimento'))}")
    with c2:
        st.markdown(f"**Indirizzo:** {_safe_txt(row.get('Indirizzo'))}")
        st.markdown(f"**CAP/Città:** {_safe_txt(row.get('CAP'))} {_safe_txt(row.get('Citta'))}")
        st.markdown(f"**Telefono/Cell:** {_safe_txt(row.get('Telefono'))} / {_safe_txt(row.get('Cell'))}")
    with c3:
        st.markdown(f"**Email:** {_safe_txt(row.get('Email'))}")
        st.markdown(f"**P.IVA:** {_safe_txt(row.get('PartitaIVA'))}")
        st.markdown(f"**SDI:** {_safe_txt(row.get('SDI'))}")

def _gen_offerta_number(df_prev: pd.DataFrame, cliente_id: str, ragione: str) -> str:
    sub = df_prev[df_prev["ClienteID"].astype(str) == str(cliente_id)]
    if sub.empty:
        seq = 1
    else:
        try:
            seq = max(int(x.split("-")[-1]) for x in sub["NumeroOfferta"].tolist() if "-" in x) + 1
        except Exception:
            seq = len(sub) + 1
    slug = "".join(ch for ch in ragione.upper() if ch.isalnum())[:12] or str(cliente_id)
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

    with st.expander("Anagrafica (modificabile)", expanded=False):
        with st.form("frm_anagrafica"):
            ragsoc = st.text_input("Ragione sociale", _safe_txt(row.get("RagioneSociale")))
            indir  = st.text_input("Indirizzo", _safe_txt(row.get("Indirizzo")))
            cap    = st.text_input("CAP", _safe_txt(row.get("CAP")))
            citta  = st.text_input("Città", _safe_txt(row.get("Citta")))
            ref    = st.text_input("Persona di riferimento", _safe_txt(row.get("PersonaRiferimento")))
            tel    = st.text_input("Telefono", _safe_txt(row.get("Telefono")))
            cell   = st.text_input("Cell", _safe_txt(row.get("Cell")))
            mail   = st.text_input("Email", _safe_txt(row.get("Email")))
            piva   = st.text_input("Partita IVA", _safe_txt(row.get("PartitaIVA")))
            sdi    = st.text_input("SDI", _safe_txt(row.get("SDI")))

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                ult_recall   = st.date_input("Ultimo recall", value=as_date(row.get("UltimoRecall")))
            with c2:
                pross_recall = st.date_input("Prossimo recall", value=as_date(row.get("ProssimoRecall")))
            with c3:
                ult_visita   = st.date_input("Ultima visita", value=as_date(row.get("UltimaVisita")))
            with c4:
                pross_visita = st.date_input("Prossima visita", value=as_date(row.get("ProssimaVisita")))

            if st.form_submit_button("Salva modifiche", use_container_width=True):
                idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
                df_cli.loc[idx_row, "RagioneSociale"]    = ragsoc
                df_cli.loc[idx_row, "Indirizzo"]         = indir
                df_cli.loc[idx_row, "CAP"]               = cap
                df_cli.loc[idx_row, "Citta"]             = citta
                df_cli.loc[idx_row, "PersonaRiferimento"]= ref
                df_cli.loc[idx_row, "Telefono"]          = tel
                df_cli.loc[idx_row, "Cell"]              = cell
                df_cli.loc[idx_row, "Email"]             = mail
                df_cli.loc[idx_row, "PartitaIVA"]        = piva
                df_cli.loc[idx_row, "SDI"]               = sdi
                df_cli.loc[idx_row, "UltimoRecall"]      = pd.to_datetime(ult_recall) if ult_recall else ""
                df_cli.loc[idx_row, "ProssimoRecall"]    = pd.to_datetime(pross_recall) if pross_recall else ""
                df_cli.loc[idx_row, "UltimaVisita"]      = pd.to_datetime(ult_visita) if ult_visita else ""
                df_cli.loc[idx_row, "ProssimaVisita"]    = pd.to_datetime(pross_visita) if pross_visita else ""
                save_clienti(df_cli)
                st.success("Dati cliente aggiornati.")
                st.rerun()

    note_new = st.text_area("Note", _safe_txt(row.get("Note")))
    if st.button("Salva note"):
        idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
        df_cli.loc[idx_row, "Note"] = note_new
        save_clienti(df_cli)
        st.success("Note aggiornate.")
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

    col_a, col_b = st.columns([0.5, 0.5], gap="large")
    with col_a:
        st.caption("Campi compilati automaticamente")
        st.write(f"**Cliente:** {_safe_txt(row.get('RagioneSociale'))}")
        st.write(f"**Indirizzo:** {_safe_txt(row.get('Indirizzo'))} — {_safe_txt(row.get('CAP'))} {_safe_txt(row.get('Citta'))}")
        st.write("**Data documento:** oggi")

        if st.button("Genera preventivo", type="primary"):
            if not tpl_path.exists():
                st.error(f"Template non trovato: {tpl_file}")
            else:
                client_folder = EXTERNAL_PROPOSALS_DIR / str(sel_id)
                client_folder.mkdir(parents=True, exist_ok=True)

                numero_offerta = _gen_offerta_number(df_prev, sel_id, _safe_txt(row.get("RagioneSociale")))
                doc = Document(str(tpl_path))
                mapping = {
                    "CLIENTE": _safe_txt(row.get("RagioneSociale")),
                    "INDIRIZZO": _safe_txt(row.get("Indirizzo")),
                    "CITTA": f"{_safe_txt(row.get('CAP'))} {_safe_txt(row.get('Citta'))}".strip(),
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

# ==========================
# CONTRATTI — NUOVO LAYOUT
# ==========================
def _export_table_bytes(df: pd.DataFrame, base_name: str) -> Tuple[bytes, str, str]:
    try:
        import xlsxwriter  # noqa: F401
        bio = BytesIO()
        with pd.ExcelWriter(bio, engine="xlsxwriter") as xw:
            df.to_excel(xw, index=False, sheet_name="Contratti")
        return bio.getvalue(), f"{base_name}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    except Exception:
        return df.to_csv(index=False).encode("utf-8-sig"), f"{base_name}.csv", "text/csv"

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
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    ragione = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0].get("RagioneSociale","")

    ct = df_ct[df_ct["ClienteID"].astype(str)==sel_id].copy()
    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    ct["DataInizio"] = to_date_series(ct["DataInizio"])
    ct["DataFine"]   = to_date_series(ct["DataFine"])

    st.markdown(BASE_CSS, unsafe_allow_html=True)
    st.markdown(f"<div style='display:flex;gap:10px;align-items:center;flex-wrap:wrap'><div style='font-size:18px;font-weight:800'>Contratti di</div> <span class='badge'>{ragione}</span></div>", unsafe_allow_html=True)

    c1, c2 = st.columns([0.50, 0.50])
    with c1:
        with st.expander("➕ Nuovo contratto", expanded=False):
            with st.form("frm_new_contract"):
                num   = st.text_input("Numero contratto").strip()
                di    = st.date_input("Data inizio", value=None)
                dfine = st.date_input("Data fine",  value=None)
                dura  = st.text_input("Durata (mesi/anni)", "")
                desc  = st.text_area("Descrizione prodotto")
                nol_f = st.text_input("NOL_FIN", "")
                nol_i = st.text_input("NOL_INT", "")
                rata  = st.text_input("TotRata", "")
                stato = st.selectbox("Stato", ["aperto","chiuso"], index=0)

                if st.form_submit_button("Salva contratto", type="primary", use_container_width=True):
                    if not num:
                        st.error("Numero contratto obbligatorio.")
                    else:
                        new = {
                            "ClienteID": sel_id,
                            "NumeroContratto": num,
                            "DataInizio": pd.to_datetime(di) if di else "",
                            "DataFine":   pd.to_datetime(dfine) if dfine else "",
                            "Durata": dura,
                            "DescrizioneProdotto": desc,
                            "NOL_FIN": nol_f,
                            "NOL_INT": nol_i,
                            "TotRata": rata,
                            "Stato": stato
                        }
                        df_full = load_contratti()
                        df_full = ensure_columns(df_full, CONTRATTI_COLS)
                        def _iso(x): return "" if x=="" or pd.isna(x) else pd.to_datetime(x).strftime("%Y-%m-%d")
                        new["DataInizio"] = _iso(new["DataInizio"])
                        new["DataFine"]   = _iso(new["DataFine"])
                        df_full = pd.concat([df_full, pd.DataFrame([new])], ignore_index=True)
                        save_contratti(df_full)
                        st.success("Contratto inserito.")
                        st.rerun()

    with c2:
        with st.expander("⤓ Esporta / Stampa / Stato", expanded=False):
            all_disp = ct.copy()
            all_disp["DataInizio"] = all_disp["DataInizio"].apply(fmt_date)
            all_disp["DataFine"]   = all_disp["DataFine"].apply(fmt_date)
            all_disp["TotRata"]    = all_disp["TotRata"].apply(money)

            opts = all_disp["NumeroContratto"].tolist()
            sel_multi = st.multiselect("Seleziona contratti", opts)

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if st.button("Esporta selezionati"):
                    out = all_disp[all_disp["NumeroContratto"].isin(sel_multi)] if sel_multi else all_disp
                    if out.empty:
                        st.warning("Nessuna riga da esportare.")
                    else:
                        data, fname, mime = _export_table_bytes(out, f"contratti_{sel_id}")
                        st.download_button("Scarica file", data=data, file_name=fname, mime=mime, key="dl_export")
            with col_b:
                if st.button("Stampa (HTML)"):
                    out = all_disp[all_disp["NumeroContratto"].isin(sel_multi)] if sel_multi else all_disp
                    if out.empty:
                        st.warning("Nessuna riga da stampare.")
                    else:
                        html = "<h3>Contratti selezionati</h3>" + html_table(out, closed_mask=(out["Stato"].str.lower()=="chiuso"))
                        st.download_button("Scarica HTML", data=html.encode("utf-8"),
                                           file_name=f"contratti_{sel_id}.html", mime="text/html", key="dl_html")
            with col_c:
                az = st.selectbox("Azione stato", ["Chiudi", "Riapri"])
                if st.button("Applica"):
                    if not sel_multi:
                        st.warning("Seleziona almeno un contratto.")
                    else:
                        df_full = load_contratti()
                        mask_cli = df_full["ClienteID"].astype(str)==sel_id
                        mask_sel = df_full["NumeroContratto"].isin(sel_multi)
                        df_full.loc[mask_cli & mask_sel, "Stato"] = "chiuso" if az=="Chiudi" else "aperto"
                        save_contratti(df_full)
                        st.success("Aggiornato lo stato.")
                        st.rerun()

    st.divider()

    disp = ct.copy()
    disp = disp[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]]
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
    disp["TotRata"]    = disp["TotRata"].apply(money)
    closed_mask = ct["Stato"].str.lower()=="chiuso"

    st.markdown("### Elenco contratti")
    html_table_interactive(
        disp.drop(columns=["DescrizioneProdotto"]),
        desc_series=ct["DescrizioneProdotto"],
        closed_mask=closed_mask
    )

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
    df_ct  = load_contratti()
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
