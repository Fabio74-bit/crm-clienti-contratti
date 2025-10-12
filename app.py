# app.py — Gestionale Clienti SHT (versione completa e corretta)
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

def s(x) -> str:
    """Stringa sicura per Streamlit input (evita pd.NA / NaN)."""
    try:
        return "" if pd.isna(x) else str(x)
    except Exception:
        return "" if x is None else str(x)

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

    # KPI
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

    # Ricerca cliente
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
    """Sostituisce segnaposto <<...>> in tutto il documento, incluse run spezzate."""
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

def _gen_offerta_number(df_prev: pd.DataFrame, cliente_id: str, nome_cliente: str) -> str:
    sub = df_prev[df_prev["ClienteID"].astype(str) == str(cliente_id)]
    if sub.empty:
        seq = 1
    else:
        try:
            seq = max(int(x.split("-")[-1]) for x in sub["NumeroOfferta"].tolist() if "-" in x) + 1
        except Exception:
            seq = len(sub) + 1
    safe_name = "".join(ch if ch.isalnum() else "_" for ch in str(nome_cliente)).strip("_")
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
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    row = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0]

    # riepilogo
    st.markdown(f"### {s(row['RagioneSociale'])}")
    st.write(f"**ClienteID:** {s(row['ClienteID'])}")
    st.write(f"**Email:** {s(row['Email'])} — **Telefono:** {s(row['Telefono'])}")
    st.write(f"**Città:** {s(row['Citta'])} — **P.IVA:** {s(row['PartitaIVA'])}")

    st.divider()
    note_new = st.text_area("Note", s(row.get("Note", "")))
    if st.button("Salva note"):
        idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
        df_cli.loc[idx_row, "Note"] = note_new
        save_clienti(df_cli)
        st.success("Note aggiornate.")
        st.rerun()

    st.divider()
    with st.expander("Modifica anagrafica"):
        with st.form("frm_anagrafica"):
            ragsoc = st.text_input("Ragione sociale", s(row.get("RagioneSociale")))
            indir  = st.text_input("Indirizzo", s(row.get("Indirizzo")))
            cap    = st.text_input("CAP", s(row.get("CAP")))
            citta  = st.text_input("Città", s(row.get("Citta")))
            ref    = st.text_input("Persona di riferimento", s(row.get("PersonaRiferimento")))
            tel    = st.text_input("Telefono", s(row.get("Telefono")))
            cell   = st.text_input("Cell", s(row.get("Cell")))
            mail   = st.text_input("Email", s(row.get("Email")))
            piva   = st.text_input("Partita IVA", s(row.get("PartitaIVA")))
            sdi    = st.text_input("SDI", s(row.get("SDI")))

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                ult_recall = date_input_opt("Ultimo recall", row.get("UltimoRecall"), key="ur")
            with c2:
                pross_recall = date_input_opt("Prossimo recall", row.get("ProssimoRecall"), key="pr")
            with c3:
                ult_visita = date_input_opt("Ultima visita", row.get("UltimaVisita"), key="uv")
            with c4:
                pross_visita = date_input_opt("Prossima visita", row.get("ProssimaVisita"), key="pv")

            if st.form_submit_button("Salva anagrafica"):
                idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
                df_cli.loc[idx_row, ["RagioneSociale","Indirizzo","CAP","Citta","PersonaRiferimento",
                                     "Telefono","Cell","Email","PartitaIVA","SDI"]] = [
                    ragsoc, indir, cap, citta, ref, tel, cell, mail, piva, sdi
                ]
                df_cli.loc[idx_row, "UltimoRecall"] = pd.to_datetime(ult_recall) if ult_recall else ""
                df_cli.loc[idx_row, "ProssimoRecall"] = pd.to_datetime(pross_recall) if pross_recall else ""
                df_cli.loc[idx_row, "UltimaVisita"] = pd.to_datetime(ult_visita) if ult_visita else ""
                df_cli.loc[idx_row, "ProssimaVisita"] = pd.to_datetime(pross_visita) if pross_visita else ""
                save_clienti(df_cli)
                st.success("Dati aggiornati.")
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
        sub = df_prev[df_prev["ClienteID"].astype(str) == sel_id].copy().sort_values("DataCreazione", ascending=False)
        if sub.empty:
            st.info("Nessun preventivo per questo cliente.")
        else:
            for _, r in sub.iterrows():
                box = st.container(border=True)
                with box:
                    st.markdown(f"**{r['NumeroOfferta']}** — {r['Template']}")
                    st.caption(r.get("DataCreazione",""))
                    path = Path(r["Percorso"])
                    if path.exists():
                        with open(path, "rb") as fh:
                            st.download_button(
                                "Apri/Scarica",
                                data=fh.read(),
                                file_name=path.name,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            )
                    else:
                        st.error("File non trovato (verifica OneDrive).")


# ==========================
# CONTRATTI (versione con AgGrid + azioni + esportazione)
# ==========================
# ==========================
# CONTRATTI (versione estetica con AgGrid, stato e descrizione estesa)
# ==========================
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

def safe_text(txt):
    return str(txt).encode("latin-1", "replace").decode("latin-1")

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2 style='margin-top:0'>📄 Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # Selezione cliente
    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str) == str(pre)][0])
        except Exception:
            idx = 0

    sel_label = st.selectbox("Seleziona cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = df_cli.iloc[labels[labels == sel_label].index[0]]["ClienteID"]
    rag_soc = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0]["RagioneSociale"]

    # --- Nuovo contratto ---
    with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            with c1:
                num = st.text_input("Numero Contratto")
            with c2:
                din = st.date_input("Data inizio", format="DD/MM/YYYY")
            with c3:
                durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto", height=100)
            nol_fin, nol_int, tota = st.columns(3)
            with nol_fin: nf = st.text_input("NOL_FIN")
            with nol_int: ni = st.text_input("NOL_INT")
            with tota: tot = st.text_input("TotRata")

            if st.form_submit_button("💾 Crea contratto"):
                row = {
                    "ClienteID": str(sel_id),
                    "NumeroContratto": num,
                    "DataInizio": pd.to_datetime(din),
                    "DataFine": pd.to_datetime(din) + pd.DateOffset(months=int(durata)),
                    "Durata": durata,
                    "DescrizioneProdotto": desc,
                    "NOL_FIN": nf,
                    "NOL_INT": ni,
                    "TotRata": tot,
                    "Stato": "aperto"
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([row])], ignore_index=True)
                save_contratti(df_ct)
                st.success("✅ Contratto creato con successo.")
                st.rerun()

    # --- Tabella contratti ---
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")

    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp["TotRata"] = disp["TotRata"].apply(money)

    # Nascondi ClienteID
    disp = disp.drop(columns=["ClienteID"], errors="ignore")

    st.divider()
    st.markdown(f"<h4>📋 Elenco contratti di <b>{rag_soc}</b></h4>", unsafe_allow_html=True)

    # Configurazione AgGrid
    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True)
    gb.configure_selection(selection_mode="single", use_checkbox=False)

    # Colorazione righe chiuse
    js_code = JsCode("""
    function(params) {
        if (params.data.Stato && params.data.Stato.toLowerCase() === 'chiuso') {
            return { 'backgroundColor': '#ffe5e5', 'color': '#a10000' };
        }
        return {};
    }
    """)

    gb.configure_grid_options(getRowStyle=js_code)
    grid_opts = gb.build()

    grid_resp = AgGrid(
        disp,
        gridOptions=grid_opts,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True,
        theme="balham",
        height=350
    )

    selected = grid_resp.get("selected_rows")
    if selected:
        sel = selected[0]
        st.markdown("### 📝 Descrizione completa")
        st.info(sel.get("DescrizioneProdotto", ""))

    # --- Azioni Chiudi/Riapri ---
    st.divider()
    st.markdown("### ⚙️ Gestione stato contratti")
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
        with c1:
            st.write(" ")
        with c2:
            st.caption(f"{r['NumeroContratto']} — {r['DescrizioneProdotto'][:60]}")
        with c3:
            curr = (r["Stato"] or "aperto").lower()
            if curr == "chiuso":
                if st.button("🔓 Riapri", key=f"open_{i}"):
                    df_ct.loc[i, "Stato"] = "aperto"
                    save_contratti(df_ct)
                    st.success(f"Contratto {r['NumeroContratto']} riaperto.")
                    st.rerun()
            else:
                if st.button("❌ Chiudi", key=f"close_{i}"):
                    df_ct.loc[i, "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.success(f"Contratto {r['NumeroContratto']} chiuso.")
                    st.rerun()

    # --- Esportazioni ---
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        csv = disp.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📄 Esporta CSV", csv, f"contratti_{rag_soc}.csv", "text/csv")
    with c2:
        try:
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", size=9)
            pdf.cell(0, 8, safe_text(f"Contratti - {rag_soc}"), ln=1, align="C")
            for _, row in disp.iterrows():
                pdf.cell(35, 6, safe_text(row["NumeroContratto"]), 1)
                pdf.cell(25, 6, safe_text(row["DataInizio"]), 1)
                pdf.cell(25, 6, safe_text(row["DataFine"]), 1)
                pdf.cell(20, 6, safe_text(row["Durata"]), 1)
                pdf.cell(80, 6, safe_text(row["DescrizioneProdotto"])[:60], 1)
                pdf.cell(20, 6, safe_text(row["TotRata"]), 1)
                pdf.cell(20, 6, safe_text(row["Stato"]), 1)
                pdf.ln()
            pdf_bytes = pdf.output(dest="S").encode("latin-1", "replace")
            st.download_button("📘 Esporta PDF", pdf_bytes,
                               f"contratti_{rag_soc}.pdf", "application/pdf")
        except Exception as e:
            st.error(f"Errore PDF: {e}")


# ==========================
# MAIN APP
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
