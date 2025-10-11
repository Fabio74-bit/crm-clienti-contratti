# app.py — Gestionale Clienti SHT (dashboard “buona” + clienti con preventivi)
from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict

import pandas as pd
import streamlit as st

# ==========================
# CONFIG / COSTANTI
# ==========================
APP_TITLE = "GESTIONALE CLIENTI – SHT"

# storage: da st.secrets, fallback a ./storage
STORAGE_DIR = Path(
    st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage"))
)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV     = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV   = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV  = STORAGE_DIR / "preventivi.csv"

# cartella template e cartella output preventivi
TEMPLATES_DIR = STORAGE_DIR / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# se presente ONEDRIVE_DIR nei secrets, usa quella cartella, altrimenti ./storage/preventivi
ONEDRIVE_DIR = Path(st.secrets.get("ONEDRIVE_DIR", (STORAGE_DIR / "preventivi")))
ONEDRIVE_DIR.mkdir(parents=True, exist_ok=True)

# colonne canoniche
CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cellulare", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]
PREVENTIVI_COLS = [
    "Numero", "ClienteID", "Data", "Template", "File", "Note"
]

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
    # tenta prima dayfirst
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

def normalize_piva(s: str) -> str:
    """Rende la P.IVA una stringa di sole cifre, preservando gli zeri iniziali."""
    if s is None:
        return ""
    s = str(s).strip()
    # se è stato salvato in formati tipo 1.23E+10, prova a prendere solo cifre
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits:
        s = digits
    # se plausibile 11 cifre italiane, pad a sinistra
    if 1 <= len(s) <= 11 and s.isdigit():
        s = s.zfill(11)
    return s

# ==========================
# I/O DATI
# ==========================

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def load_clienti() -> pd.DataFrame:
    if CLIENTI_CSV.exists():
        df = pd.read_csv(CLIENTI_CSV, dtype=str, sep=",").fillna("")
    else:
        df = pd.DataFrame(columns=CLIENTI_COLS)
        df.to_csv(CLIENTI_CSV, index=False)
    df = ensure_columns(df, CLIENTI_COLS)
    # normalizza date
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        df[c] = to_date_series(df[c])
    return df

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

def load_preventivi() -> pd.DataFrame:
    if PREVENTIVI_CSV.exists():
        df = pd.read_csv(PREVENTIVI_CSV, dtype=str, sep=",").fillna("")
    else:
        df = pd.DataFrame(columns=PREVENTIVI_COLS)
        df.to_csv(PREVENTIVI_CSV, index=False)
    df = ensure_columns(df, PREVENTIVI_COLS)
    return df

def save_clienti(df: pd.DataFrame):
    out = df.copy()
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False)

def save_contratti(df: pd.DataFrame):
    out = df.copy()
    for c in ["DataInizio","DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False)

def save_preventivi(df: pd.DataFrame):
    out = df.copy()
    out.to_csv(PREVENTIVI_CSV, index=False)

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
            val = r.get(c, "")
            sval = "" if pd.isna(val) else str(val)
            sval = sval.replace("\n", "<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows.append(f"<tr{trc}>{''.join(tds)}</tr>")
    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return TABLE_CSS + f"<table class='ctr-table'>{thead}{tbody}</table>"

# ==========================
# AUTH (semplice, opzionale)
# ==========================

def do_login() -> Tuple[str, str]:
    """
    Login semplice basato su st.secrets['auth']['users'].
    Ritorna (username, ruolo). Se non configurato, entra come ospite.
    """
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        # Nessun auth configurato: accesso libero
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

    # già loggato?
    if "auth_user" in st.session_state:
        return (st.session_state["auth_user"], st.session_state.get("auth_role", "viewer"))

    # non ancora loggato
    return ("", "")

# ==========================
# DOCX REPLACE (robusto)
# ==========================

def _replace_in_docx(template_path: Path, mapping: Dict[str, str], out_path: Path):
    """Sostituisce i placeholder {{KEY}} gestendo i 'run split' di Word."""
    from docx import Document
    doc = Document(str(template_path))

    def replace_in_paragraph(p):
        if not p.runs:
            return
        full = "".join(r.text for r in p.runs)
        for k, v in mapping.items():
            full = full.replace("{{" + k + "}}", v)
        p.runs[0].text = full
        for r in p.runs[1:]:
            r.text = ""

    # paragrafi
    for p in doc.paragraphs:
        replace_in_paragraph(p)

    # tabelle
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    replace_in_paragraph(p)

    doc.save(str(out_path))

# ==========================
# PAGINE
# ==========================

def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    # --- KPI (calcoli) ---
    today = pd.Timestamp.today().normalize()
    year_now = today.year
    stato = df_ct["Stato"].fillna("aperto").str.lower()
    contratti_aperti = int((stato != "chiuso").sum())
    contratti_chiusi = int((stato == "chiuso").sum())
    contratti_anno   = int((to_date_series(df_ct["DataInizio"]).dt.year == year_now).sum())
    clienti_attivi   = int(df_cli["ClienteID"].nunique())

    # --- KPI (render in UN SOLO blocco HTML) ---
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
      <div class="kpi">
        <div class="t">Clienti attivi</div><div class="v">{clienti_attivi}</div>
      </div>
      <div class="kpi green">
        <div class="t">Contratti aperti</div><div class="v">{contratti_aperti}</div>
      </div>
      <div class="kpi red">
        <div class="t">Contratti chiusi</div><div class="v">{contratti_chiusi}</div>
      </div>
      <div class="kpi yellow">
        <div class="t">Contratti {year_now}</div><div class="v">{contratti_anno}</div>
      </div>
    </div>
    """
    st.markdown(kpi_html, unsafe_allow_html=True)

    # -------------- Ricerca cliente --------------
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

    # -------------- Contratti in scadenza (entro 6 mesi) --------------
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    ct = df_ct.copy()
    ct["DataFine"] = to_date_series(ct["DataFine"])
    open_mask = ct["Stato"].fillna("aperto").str.lower() != "chiuso"
    within_6m = (ct["DataFine"].notna() &
                 (ct["DataFine"] >= today) &
                 (ct["DataFine"] <= today + pd.DateOffset(months=6)))
    scad = ct[open_mask & within_6m].copy()
    if not scad.empty:
        scad = scad.sort_values(["ClienteID", "DataFine"])
        scad = scad.groupby("ClienteID", as_index=False).first()

    disp = pd.DataFrame()
    if not scad.empty:
        disp = pd.DataFrame({
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
            "DataFine": scad["DataFine"].apply(fmt_date),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "TotRata": scad["TotRata"].apply(money)
        })
    st.markdown(html_table(disp), unsafe_allow_html=True)

    st.divider()

    # -------------- Ultimi recall (> 3 mesi) --------------
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecall"] = to_date_series(cli["UltimoRecall"])
        soglia = today - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall"].notna() & (cli["UltimoRecall"] <= soglia)]
        tab = r.loc[:, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]].copy()
        tab["UltimoRecall"] = tab["UltimoRecall"].apply(fmt_date)
        tab["ProssimoRecall"] = to_date_series(tab["ProssimoRecall"]).apply(fmt_date)
        st.markdown(html_table(tab), unsafe_allow_html=True)

    # -------------- Ultime visite (> 6 mesi) --------------
    with col2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisita"] = to_date_series(cli["UltimaVisita"])
        soglia_v = today - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita"].notna() & (cli["UltimaVisita"] <= soglia_v)]
        tab = v.loc[:, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]].copy()
        tab["UltimaVisita"] = tab["UltimaVisita"].apply(fmt_date)
        tab["ProssimaVisita"] = to_date_series(tab["ProssimaVisita"]).apply(fmt_date)
        st.markdown(html_table(tab), unsafe_allow_html=True)

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")
    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # selezione preimpostata dalla dashboard
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

    # riga selezionata
    row = df_cli[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0]
    ridx = row.name

    st.markdown("### Anagrafica (modificabile)")
    with st.form("anag"):
        rsoc   = st.text_input("Ragione sociale", row.get("RagioneSociale",""))
        ref    = st.text_input("Persona di riferimento", row.get("PersonaRiferimento",""))
        ind    = st.text_input("Indirizzo", row.get("Indirizzo",""))
        citta  = st.text_input("Città", row.get("Citta",""))
        cap    = st.text_input("CAP", row.get("CAP",""))
        tel    = st.text_input("Telefono", row.get("Telefono",""))
        cell   = st.text_input("Cellulare", row.get("Cellulare",""))
        email  = st.text_input("Email", row.get("Email",""))
        piva   = st.text_input("Partita IVA", row.get("PartitaIVA",""))
        iban   = st.text_input("IBAN", row.get("IBAN",""))
        sdi    = st.text_input("SDI", row.get("SDI",""))
        note   = st.text_area("Note", row.get("Note",""), height=80)

        st.markdown("#### Recall / Visite")
        colA, colB = st.columns(2)
        with colA:
            ult_recall = st.date_input("Ultimo recall", value=row.get("UltimoRecall"))
            pro_recall = st.date_input("Prossimo recall", value=row.get("ProssimoRecall"))
        with colB:
            ult_visita = st.date_input("Ultima visita", value=row.get("UltimaVisita"))
            pro_visita = st.date_input("Prossima visita", value=row.get("ProssimaVisita"))

        saved = st.form_submit_button("Salva anagrafica")
    if saved:
        df_cli.loc[ridx, "RagioneSociale"]     = rsoc
        df_cli.loc[ridx, "PersonaRiferimento"] = ref
        df_cli.loc[ridx, "Indirizzo"]          = ind
        df_cli.loc[ridx, "Citta"]              = citta
        df_cli.loc[ridx, "CAP"]                = cap
        df_cli.loc[ridx, "Telefono"]           = tel
        df_cli.loc[ridx, "Cellulare"]          = cell
        df_cli.loc[ridx, "Email"]              = email
        df_cli.loc[ridx, "PartitaIVA"]         = normalize_piva(piva)
        df_cli.loc[ridx, "IBAN"]               = iban
        df_cli.loc[ridx, "SDI"]                = sdi
        df_cli.loc[ridx, "Note"]               = note

        df_cli.loc[ridx, "UltimoRecall"]   = pd.to_datetime(ult_recall) if ult_recall else pd.NaT
        df_cli.loc[ridx, "ProssimoRecall"] = pd.to_datetime(pro_recall) if pro_recall else pd.NaT
        df_cli.loc[ridx, "UltimaVisita"]   = pd.to_datetime(ult_visita) if ult_visita else pd.NaT
        df_cli.loc[ridx, "ProssimaVisita"] = pd.to_datetime(pro_visita) if pro_visita else pd.NaT

        save_clienti(df_cli)
        st.success("Anagrafica salvata.")
        st.rerun()

    # vai ai contratti
    if st.button("Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = str(sel_id)
        st.rerun()

    st.divider()
    st.markdown("### Preventivi")

    # carica preventivi
    df_prev = load_preventivi()

    # genera preventivo
    with st.form("form_prev"):
        col1, col2, col3 = st.columns([0.35, 0.35, 0.30])
        with col1:
            templ_opts = sorted([p.name for p in TEMPLATES_DIR.glob("*.docx")])
            template_name = st.selectbox("Template", templ_opts, index=0 if templ_opts else None)
        with col2:
            data_prev = st.date_input("Data preventivo", value=datetime.today())
        with col3:
            note_prev = st.text_input("Note (facoltative)", "")

        create_btn = st.form_submit_button("Crea preventivo")

    if create_btn:
        if not template_name:
            st.error("Seleziona un template.")
        else:
            # numerazione per cliente: SHT-MI-<ClienteID>-NNNN
            cli_id_str = str(sel_id)
            prefix = f"SHT-MI-{cli_id_str}-"
            df_prev_cli = df_prev[df_prev["ClienteID"].astype(str) == cli_id_str].copy()
            if df_prev_cli.empty:
                next_n = 1
            else:
                # estrae ultima parte numerica delle stringhe Numero che iniziano con prefix
                nums = []
                for s in df_prev_cli["Numero"]:
                    s = str(s)
                    if s.startswith(prefix):
                        m = re.search(rf"^{re.escape(prefix)}(\d+)$", s)
                        if m:
                            nums.append(int(m.group(1)))
                next_n = (max(nums) + 1) if nums else 1
            new_num = f"{prefix}{next_n:04d}"

            out_dir = ONEDRIVE_DIR / cli_id_str
            out_dir.mkdir(parents=True, exist_ok=True)
            out_filename = f"{new_num}.docx"
            out_path = out_dir / out_filename

            mapping = {
                "NUMERO_PREVENTIVO": new_num,
                "DATA": datetime.strptime(str(data_prev), "%Y-%m-%d").strftime("%d/%m/%Y"),
                "RAGIONE_SOCIALE": row.get("RagioneSociale",""),
                "REFERENTE": row.get("PersonaRiferimento",""),
                "INDIRIZZO": row.get("Indirizzo",""),
                "CITTA": row.get("Citta",""),
                "CAP": row.get("CAP",""),
                "EMAIL": row.get("Email",""),
                "TELEFONO": row.get("Telefono",""),
                "CELLULARE": row.get("Cellulare",""),
                "PARTITA_IVA": normalize_piva(row.get("PartitaIVA","")),
                "IBAN": row.get("IBAN",""),
                "SDI": row.get("SDI",""),
            }

            try:
                _replace_in_docx(TEMPLATES_DIR / template_name, mapping, out_path)
            except Exception as e:
                st.error(f"Errore nella generazione del DOCX: {e}")
            else:
                # aggiorna CSV preventivi
                new_row = {
                    "Numero": new_num,
                    "ClienteID": cli_id_str,
                    "Data": datetime.strptime(str(data_prev), "%Y-%m-%d").strftime("%Y-%m-%d"),
                    "Template": template_name,
                    "File": str(out_path),
                    "Note": note_prev,
                }
                df_prev = pd.concat([df_prev, pd.DataFrame([new_row])], ignore_index=True)
                save_preventivi(df_prev)
                st.success(f"Preventivo {new_num} creato.")

                # download immediato
                if out_path.exists():
                    with open(out_path, "rb") as _f:
                        st.download_button(
                            "Apri/Scarica subito",
                            data=_f.read(),
                            file_name=out_filename,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_now_{new_num}"
                        )

    # elenco preventivi del cliente
    cli_prev = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)].copy()
    if not cli_prev.empty:
        cli_prev = cli_prev.sort_values("Numero")
        st.markdown("**Preventivi esistenti**")
        display = cli_prev[["Numero", "Data", "Template", "Note"]].copy()
        st.markdown(html_table(display), unsafe_allow_html=True)

        # pulsanti Apri/Scarica per ogni riga
        for _, r in cli_prev.iterrows():
            p = Path(r["File"])
            cols = st.columns([0.75, 0.25])
            with cols[0]:
                st.caption(f"{r['Numero']} — {r['Template']} — {r['Data']}")
            with cols[1]:
                if p.exists():
                    with open(p, "rb") as f:
                        st.download_button(
                            label="Apri/Scarica",
                            data=f.read(),
                            file_name=p.name,
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key=f"dl_{r['Numero']}"
                        )

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
    sel_id = df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"]

    ct = df_ct[df_ct["ClienteID"].astype(str)==str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    closed_mask = ct["Stato"].str.lower()=="chiuso"

    # tabella
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
    disp["TotRata"]    = disp["TotRata"].apply(money)

    st.markdown(html_table(
        disp[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]],
        closed_mask=closed_mask
    ), unsafe_allow_html=True)

    st.markdown("— Seleziona una riga qui sotto per **Chiudere/Riaprire**:")
    for i, r in ct.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.75, 0.20])
        with c1:
            st.write(" ")
        with c2:
            st.caption(f"{r['NumeroContratto'] or ''} — {r['DescrizioneProdotto'] or ''}")
        with c3:
            curr = (r["Stato"] or "aperto").lower()
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

    # login (opzionale)
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

    # load dati
    df_cli = load_clienti()
    df_ct  = load_contratti()

    # run pagina
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
