# app.py — Gestionale Clienti SHT (dashboard “buona” + login + clienti + contratti + preventivi)
from __future__ import annotations

from pathlib import Path
from datetime import datetime, date
from typing import Tuple, Dict
import re

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

# Mappa radio -> file template (metti questi file in storage/templates)
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

def safe_str(v) -> str:
    """Restituisce sempre una stringa 'pulita' per i widget Streamlit (evita pd.NA)."""
    try:
        return "" if (v is None or pd.isna(v)) else str(v)
    except Exception:
        return ""

def to_date_widget(x):
    """Per i widget Streamlit: None oppure datetime.date (evita errori con pd.NaT)."""
    d = as_date(x)
    if d is None or pd.isna(d):
        return None
    try:
        return pd.to_datetime(d).date()
    except Exception:
        return None

def slugify_name(name: str) -> str:
    s = (name or "").upper().strip()
    s = re.sub(r"[^A-Z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:24] if len(s) > 24 else s

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
# HTML TABLE (vista "bella")
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
            sval = safe_str(r.get(c, ""))
            sval = sval.replace("\n", "<br>")
            tds.append("<td class='ellipsis'>{}</td>".format(sval))
        rows.append("<tr{}>{}</tr>".format(trc, "".join(tds)))

    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return TABLE_CSS + "<table class='ctr-table'>{}{}</table>".format(thead, tbody)

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

    # KPI
    today = pd.Timestamp.today().normalize()
    year_now = today.year
    stato = df_ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = int((stato != "chiuso").sum())
    contratti_chiusi = int((stato == "chiuso").sum())
    contratti_anno   = int((to_date_series(df_ct["DataInizio"]).dt.year == year_now).sum())
    clienti_attivi   = int(df_cli["ClienteID"].nunique())

    # KPI cards (layout “buono”)
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

    # Scadenze (Cliente + DataFine + Descrizione + TotRata)
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

    # Ultimi recall / visite
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

def _summary_box(row: pd.Series):
    st.markdown("### Riepilogo")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**ClienteID:** {safe_str(row.get('ClienteID'))}")
        st.markdown(f"**Ragione Sociale:** {safe_str(row.get('RagioneSociale'))}")
        st.markdown(f"**Riferimento:** {safe_str(row.get('PersonaRiferimento'))}")
    with c2:
        st.markdown(f"**Indirizzo:** {safe_str(row.get('Indirizzo'))}")
        st.markdown(f"**CAP/Città:** {safe_str(row.get('CAP'))} {safe_str(row.get('Citta'))}")
        st.markdown(f"**Telefono/Cell:** {safe_str(row.get('Telefono'))} / {safe_str(row.get('Cell'))}")
    with c3:
        st.markdown(f"**Email:** {safe_str(row.get('Email'))}")
        st.markdown(f"**P.IVA:** {safe_str(row.get('PartitaIVA'))}")
        st.markdown(f"**SDI:** {safe_str(row.get('SDI'))}")

def _gen_offerta_number(df_prev: pd.DataFrame, cliente_id: str, cliente_nome: str) -> str:
    """Numerazione per cliente basata sul nome (slug): SHT-MI-<NOME>-NNN"""
    slug = slugify_name(cliente_nome) or f"ID{cliente_id}"
    sub = df_prev[(df_prev["ClienteID"].astype(str) == str(cliente_id)) |
                  (df_prev["NumeroOfferta"].fillna("").str.contains(f"SHT-MI-{slug}-"))]
    if sub.empty:
        seq = 1
    else:
        try:
            seq = max(int(x.split("-")[-1]) for x in sub["NumeroOfferta"].tolist() if "-" in x) + 1
        except Exception:
            seq = len(sub) + 1
    return f"SHT-MI-{slug}-{seq:03d}"

def _replace_docx_placeholders(doc: Document, mapping: Dict[str, str]):
    """Sostituisce segnaposto <<...>> in paragrafi e celle tabella (run-safe)."""
    def repl_in_paragraph(p):
        full_text = "".join(run.text for run in p.runs)
        changed = False
        for key, val in mapping.items():
            token = f"<<{key}>>"
            if token in full_text:
                full_text = full_text.replace(token, val)
                changed = True
        if changed:
            p.clear()
            p.add_run(full_text)

    for p in doc.paragraphs:
        repl_in_paragraph(p)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    repl_in_paragraph(p)

def _form_nuovo_cliente_primo_contratto(df_cli: pd.DataFrame, df_ct: pd.DataFrame):
    st.markdown("### ➕ Nuovo cliente + primo contratto")
    with st.form("frm_new_cli_ctr"):
        c1, c2 = st.columns(2)
        with c1:
            cliente_id = st.text_input("ClienteID (obbligatorio)")
            ragsoc    = st.text_input("Ragione sociale (obbligatorio)")
            ref       = st.text_input("Persona di riferimento", "")
            indir     = st.text_input("Indirizzo", "")
            cap       = st.text_input("CAP", "")
            citta     = st.text_input("Città", "")
            tel       = st.text_input("Telefono", "")
            cell      = st.text_input("Cell", "")
            mail      = st.text_input("Email", "")
            piva      = st.text_input("Partita IVA", "")
            iban      = st.text_input("IBAN", "")
            sdi       = st.text_input("SDI", "")
            note      = st.text_area("Note", "")
        with c2:
            st.markdown("**Primo contratto**")
            num_ctr   = st.text_input("Numero Contratto", "")
            data_in   = st.date_input("Data inizio", value=None)
            data_end  = st.date_input("Data fine", value=None)
            durata    = st.selectbox("Durata (mesi)", ["", "12", "24", "36", "48", "60", "72"], index=0)
            descr     = st.text_area("Descrizione prodotto", "")
            nol_fin   = st.text_input("NOL_FIN", "")
            nol_int   = st.text_input("NOL_INT", "")
            tot_rata  = st.text_input("TotRata", "")
            stato     = st.selectbox("Stato", ["aperto", "chiuso"], index=0)

        if st.form_submit_button("Crea"):
            if not cliente_id.strip() or not ragsoc.strip():
                st.error("ClienteID e Ragione sociale sono obbligatori.")
            elif cliente_id in df_cli["ClienteID"].astype(str).tolist():
                st.error("ClienteID già esistente.")
            else:
                # aggiungi cliente
                new_cli = {
                    "ClienteID": cliente_id, "RagioneSociale": ragsoc, "PersonaRiferimento": ref,
                    "Indirizzo": indir, "Citta": citta, "CAP": cap, "Telefono": tel, "Cell": cell,
                    "Email": mail, "PartitaIVA": piva, "IBAN": iban, "SDI": sdi,
                    "UltimoRecall": "", "ProssimoRecall": "", "UltimaVisita": "", "ProssimaVisita": "", "Note": note
                }
                df_cli2 = pd.concat([df_cli, pd.DataFrame([new_cli])], ignore_index=True)
                save_clienti(df_cli2)

                # aggiungi contratto (se compilato almeno descrizione o data)
                if descr.strip() or data_in or data_end or num_ctr.strip():
                    new_ctr = {
                        "ClienteID": cliente_id,
                        "NumeroContratto": num_ctr,
                        "DataInizio": pd.to_datetime(data_in) if data_in else "",
                        "DataFine":   pd.to_datetime(data_end) if data_end else "",
                        "Durata": durata,
                        "DescrizioneProdotto": descr,
                        "NOL_FIN": nol_fin,
                        "NOL_INT": nol_int,
                        "TotRata": tot_rata,
                        "Stato": stato
                    }
                    df_ct2 = pd.concat([df_ct, pd.DataFrame([new_ctr])], ignore_index=True)
                    save_contratti(df_ct2)

                st.success("Cliente (e primo contratto) creati.")
                st.session_state["selected_client_id"] = str(cliente_id)
                st.rerun()

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # --- Nuovo cliente + primo contratto ---
    with st.expander("➕ Nuovo cliente + primo contratto", expanded=False):
        _form_nuovo_cliente_primo_contratto(df_cli, df_ct)

    # selezione (mantiene eventuale selezione dalla dashboard)
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

    # ---- RIEPILOGO ----
    st.markdown("### Riepilogo")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**ClienteID:** {safe_str(row.get('ClienteID'))}")
        st.markdown(f"**Ragione Sociale:** {safe_str(row.get('RagioneSociale'))}")
        st.markdown(f"**Riferimento:** {safe_str(row.get('PersonaRiferimento'))}")
    with c2:
        st.markdown(f"**Indirizzo:** {safe_str(row.get('Indirizzo'))}")
        st.markdown(f"**CAP/Città:** {safe_str(row.get('CAP'))} {safe_str(row.get('Citta'))}")
        st.markdown(f"**Telefono/Cell:** {safe_str(row.get('Telefono'))} / {safe_str(row.get('Cell'))}")
    with c3:
        st.markdown(f"**Email:** {safe_str(row.get('Email'))}")
        st.markdown(f"**P.IVA:** {safe_str(row.get('PartitaIVA'))}")
        st.markdown(f"**SDI:** {safe_str(row.get('SDI'))}")

    # ---- NOTE FUORI DALL’EXPANDER ----
    st.markdown("### Note cliente")
    note_cache_key = f"note_{sel_id}"
    default_note = st.session_state.get(note_cache_key, safe_str(row.get("Note")))
    new_note = st.text_area(" ", value=default_note, height=140, label_visibility="collapsed")
    cns1, cns2 = st.columns([0.18, 0.82])
    with cns1:
        if st.button("Salva note", key=f"save_note_{sel_id}"):
            idx_row = df_cli.index[df_cli["ClienteID"].astype(str)==sel_id][0]
            df_cli.loc[idx_row, "Note"] = new_note
            save_clienti(df_cli)
            st.session_state[note_cache_key] = new_note
            st.success("Note aggiornate.")

    st.divider()

    # ---- ANAGRAFICA (MODIFICABILE) ----
    with st.expander("Anagrafica (modificabile)", expanded=False):
        with st.form("frm_anagrafica"):
            ragsoc = st.text_input("Ragione sociale", safe_str(row.get("RagioneSociale")))
            indir  = st.text_input("Indirizzo", safe_str(row.get("Indirizzo")))
            cap    = st.text_input("CAP", safe_str(row.get("CAP")))
            citta  = st.text_input("Città", safe_str(row.get("Citta")))
            ref    = st.text_input("Persona di riferimento", safe_str(row.get("PersonaRiferimento")))
            tel    = st.text_input("Telefono", safe_str(row.get("Telefono")))
            cell   = st.text_input("Cell", safe_str(row.get("Cell")))
            mail   = st.text_input("Email", safe_str(row.get("Email")))
            piva   = st.text_input("Partita IVA", safe_str(row.get("PartitaIVA")))  # stringa -> mantiene zeri
            sdi    = st.text_input("SDI", safe_str(row.get("SDI")))
            # Note fuori dall’expander

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                ult_recall   = st.date_input("Ultimo recall",   value=to_date_widget(row.get("UltimoRecall")))
            with c2:
                pross_recall = st.date_input("Prossimo recall", value=to_date_widget(row.get("ProssimoRecall")))
            with c3:
                ult_visita   = st.date_input("Ultima visita",   value=to_date_widget(row.get("UltimaVisita")))
            with c4:
                pross_visita = st.date_input("Prossima visita", value=to_date_widget(row.get("ProssimaVisita")))

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
                df_cli.loc[idx_row, "PartitaIVA"]         = piva
                df_cli.loc[idx_row, "SDI"]                = sdi
                # Note: non tocchiamo "Note" qui
                df_cli.loc[idx_row, "UltimoRecall"]       = pd.to_datetime(ult_recall) if ult_recall else ""
                df_cli.loc[idx_row, "ProssimoRecall"]     = pd.to_datetime(pross_recall) if pross_recall else ""
                df_cli.loc[idx_row, "UltimaVisita"]       = pd.to_datetime(ult_visita) if ult_visita else ""
                df_cli.loc[idx_row, "ProssimaVisita"]     = pd.to_datetime(pross_visita) if pross_visita else ""
                save_clienti(df_cli)
                st.success("Dati cliente aggiornati.")
                st.rerun()

    st.divider()

    # ---- LINK AI CONTRATTI ----
    if st.button("Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = sel_id
        st.rerun()

    st.divider()

    # ---- PREVENTIVI ----
    st.markdown("### Preventivi")
    df_prev = load_preventivi()
    tpl_label = st.radio("Seleziona template", list(TEMPLATE_OPTIONS.keys()), horizontal=True)
    tpl_file = TEMPLATE_OPTIONS[tpl_label]
    tpl_path = TEMPLATES_DIR / tpl_file

    col_a, col_b = st.columns([0.5, 0.5], gap="large")
    with col_a:
        st.caption("Campi compilati automaticamente")
        st.write(f"**Cliente:** {safe_str(row.get('RagioneSociale'))}")
        st.write(f"**Indirizzo:** {safe_str(row.get('Indirizzo'))} — {safe_str(row.get('CAP'))} {safe_str(row.get('Citta'))}")
        st.write("**Data documento:** oggi")

        if st.button("Genera preventivo", type="primary"):
            if not tpl_path.exists():
                st.error(f"Template non trovato: {tpl_file}")
            else:
                client_folder = EXTERNAL_PROPOSALS_DIR / str(sel_id)
                client_folder.mkdir(parents=True, exist_ok=True)

                numero_offerta = _gen_offerta_number(
                    df_prev, sel_id, safe_str(row.get("RagioneSociale"))
                )

                doc = Document(str(tpl_path))
                mapping = {
                    "CLIENTE": safe_str(row.get("RagioneSociale")),
                    "INDIRIZZO": safe_str(row.get("Indirizzo")),
                    "CITTA": f"{safe_str(row.get('CAP'))} {safe_str(row.get('Citta'))}".strip(),
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
                        st.markdown(f"**{safe_str(r['NumeroOfferta'])}** — {safe_str(r['Template'])}")
                        st.caption(safe_str(r.get("DataCreazione","")))
                    with c2:
                        st.caption(safe_str(r.get("NomeFile","")))
                        try:
                            st.caption(Path(safe_str(r["Percorso"])).parent.name)
                        except Exception:
                            st.caption("")
                    with c3:
                        path = Path(safe_str(r["Percorso"]))
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
    sel_id = df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"]

    ct = df_ct[df_ct["ClienteID"].astype(str)==str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    closed_mask = ct["Stato"].str.lower()=="chiuso"

    # --------- VISTA "BELLA" (HTML) con riga rossa per chiusi ---------
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
    disp["TotRata"]    = disp["TotRata"].apply(money)
    st.markdown("### Elenco contratti (vista grafica)")
    st.markdown(html_table(
        disp[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]],
        closed_mask=closed_mask
    ), unsafe_allow_html=True)

    st.divider()

    # --------- VISTA SELEZIONABILE (data_editor) per stampa/esporta ---------
    st.markdown("### Selezione per stampa / esportazione")
    df_view = disp.copy()
    df_view.insert(0, "Seleziona", False)
    edited = st.data_editor(
        df_view,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Seleziona": st.column_config.CheckboxColumn(required=False),
            "DescrizioneProdotto": st.column_config.TextColumn(width="medium"),
        },
        disabled=[c for c in df_view.columns if c != "Seleziona"],
        height=360,
        key=f"edit_{sel_id}"
    )

    # Azioni su righe selezionate
    selected_mask = edited["Seleziona"] == True
    selected_rows = edited[selected_mask].copy()

    cexp1, cexp2, cexp3 = st.columns([0.25,0.25,0.50])
    with cexp1:
        if st.button("Esporta selezionati in Excel"):
            if selected_rows.empty:
                st.warning("Nessuna riga selezionata.")
            else:
                # crea file XLSX con intestazione cliente
                from io import BytesIO
                output = BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    # prima riga: intestazione con nome cliente
                    workbook  = writer.book
                    worksheet = workbook.add_worksheet("Contratti")
                    title_fmt = workbook.add_format({"bold": True, "align": "center"})
                    worksheet.merge_range(0, 0, 0, selected_rows.shape[1]-1, f"Cliente: {df_cli[df_cli['ClienteID'].astype(str)==str(sel_id)].iloc[0]['RagioneSociale']}", title_fmt)
                    # tabella
                    selected_rows.drop(columns=["Seleziona"], errors="ignore").to_excel(writer, sheet_name="Contratti", startrow=2, index=False)
                st.download_button(
                    "Scarica Excel",
                    data=output.getvalue(),
                    file_name=f"Contratti_{sel_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # --------- Chiudi/Riapri singola riga (bottoni) ---------
    st.markdown("### Azioni per riga")
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.75, 0.20])
        with c1:
            st.write(" ")
        with c2:
            st.caption(f"{safe_str(r['NumeroContratto'])} — {safe_str(r['DescrizioneProdotto'])}")
        with c3:
            curr = (safe_str(r["Stato"]).lower() or "aperto")
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
