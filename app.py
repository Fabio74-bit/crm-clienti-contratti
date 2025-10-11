# app.py — Gestionale Clienti SHT (dashboard invariata + Preventivi in pagina Clienti)
from __future__ import annotations

from pathlib import Path
from typing import Tuple, Dict
import shutil
import io
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
PREVENTIVI_CSV  = STORAGE_DIR / "preventivi.csv"            # registro preventivi
TEMPLATE_DIR    = STORAGE_DIR / "templates"                 # .docx dei template
PREVENTIVI_DIR  = STORAGE_DIR / "preventivi"                # cartella file generati
PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)

# facoltativo: cartella OneDrive (esistente) dove copiare i preventivi generati
ONEDRIVE_DIR = Path(st.secrets.get("ONEDRIVE_DIR", st.secrets.get("onedrive", {}).get("dir", "")))
if str(ONEDRIVE_DIR).strip():
    ONEDRIVE_DIR.mkdir(parents=True, exist_ok=True)

# colonne canoniche (aggiunto 'Cellulare')
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

def sstr(x) -> str:
    """String safe: restituisce '' se x è mancante (NA/NaN/NaT/None)."""
    try:
        return "" if pd.isna(x) else str(x)
    except Exception:
        return "" if x is None else str(x)

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
    return ensure_columns(df, PREVENTIVI_COLS)

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
    df.to_csv(PREVENTIVI_CSV, index=False)

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
            sval = sstr(r.get(c, ""))
            sval = sval.replace("\n", "<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows.append(f"<tr{trc}>{''.join(tds)}</tr>")
    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return TABLE_CSS + f"<table class='ctr-table'>{thead}{tbody}</table>"

# ==========================
# AUTH (semplice)
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
# DOCX utilities (preventivi)
# ==========================
def _docx_available() -> bool:
    try:
        import docx  # noqa
        return True
    except Exception:
        return False

def _replace_in_docx(template_path: Path, mapping: Dict[str, str], out_path: Path):
    """Sostituisce i placeholder {{NOME}} in paragrafi e celle tabella."""
    from docx import Document
    doc = Document(str(template_path))

    def _repl_run(run_text: str) -> str:
        # sostituzione semplice {{KEY}}
        out = run_text
        for k, v in mapping.items():
            out = out.replace("{{" + k + "}}", v)
        return out

    # paragrafi
    for p in doc.paragraphs:
        for run in p.runs:
            run.text = _repl_run(run.text)

    # tabelle
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.text = _repl_run(run.text)

    doc.save(str(out_path))

def _next_preventivo_number(df_prev: pd.DataFrame) -> str:
    """Ritorna il prossimo numero sequenziale globale: SHT-MI-0001, 0002, ..."""
    if df_prev.empty:
        return "SHT-MI-0001"
    nums = []
    for x in df_prev["Numero"].astype(str):
        # estrae numero finale
        if x.startswith("SHT-MI-"):
            try:
                nums.append(int(x.split("-")[-1]))
            except Exception:
                pass
    nxt = (max(nums) + 1) if nums else 1
    return f"SHT-MI-{nxt:04d}"

def _list_templates() -> list[Path]:
    if TEMPLATE_DIR.exists():
        return sorted([p for p in TEMPLATE_DIR.glob("*.docx") if p.is_file()])
    return []

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

    # Contratti in scadenza entro 6 mesi (mostra il primo per cliente)
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
    else:
        disp = pd.DataFrame()
    st.markdown(html_table(disp), unsafe_allow_html=True)

    st.divider()

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
    row = df_cli[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0]

    st.markdown(f"**Ragione sociale:** {sstr(row.get('RagioneSociale'))}")
    st.markdown(f"**Persona di riferimento:** {sstr(row.get('PersonaRiferimento'))}")
    st.markdown(f"**Email:** {sstr(row.get('Email'))} — **Tel:** {sstr(row.get('Telefono'))}")

    if st.button("Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = str(sel_id)
        st.rerun()

    st.markdown("---")
    st.markdown("#### Modifica anagrafica")

    with st.form("edit_cli"):
        c1, c2, c3 = st.columns(3)
        with c1:
            rag   = st.text_input("Ragione sociale", sstr(row.get("RagioneSociale")))
            indir = st.text_input("Indirizzo",        sstr(row.get("Indirizzo")))
            citta = st.text_input("Città",            sstr(row.get("Citta")))
            cap   = st.text_input("CAP",              sstr(row.get("CAP")))
        with c2:
            persona = st.text_input("Persona di riferimento", sstr(row.get("PersonaRiferimento")))
            tel     = st.text_input("Telefono",               sstr(row.get("Telefono")))
            cell    = st.text_input("Cellulare",              sstr(row.get("Cellulare")))
            email   = st.text_input("Email",                  sstr(row.get("Email")))
        with c3:
            piva = st.text_input("Partita IVA", sstr(row.get("PartitaIVA")))
            iban = st.text_input("IBAN",        sstr(row.get("IBAN")))
            sdi  = st.text_input("SDI",         sstr(row.get("SDI")))

        c4, c5 = st.columns(2)
        with c4:
            ult_recall = st.date_input(
                "Ultimo recall",
                value=None if pd.isna(row.get("UltimoRecall")) else pd.to_datetime(row["UltimoRecall"]).date(),
                format="DD/MM/YYYY"
            )
            ult_visita = st.date_input(
                "Ultima visita",
                value=None if pd.isna(row.get("UltimaVisita")) else pd.to_datetime(row["UltimaVisita"]).date(),
                format="DD/MM/YYYY"
            )
        with c5:
            prox_recall = st.date_input(
                "Prossimo recall",
                value=None if pd.isna(row.get("ProssimoRecall")) else pd.to_datetime(row["ProssimoRecall"]).date(),
                format="DD/MM/YYYY"
            )
            prox_visita = st.date_input(
                "Prossima visita",
                value=None if pd.isna(row.get("ProssimaVisita")) else pd.to_datetime(row["ProssimaVisita"]).date(),
                format="DD/MM/YYYY"
            )

        note = st.text_area("Note", sstr(row.get("Note")), height=100)

        saved = st.form_submit_button("Salva modifiche", use_container_width=True)
        if saved:
            ridx = df_cli.index[df_cli["ClienteID"].astype(str)==str(sel_id)][0]
            df_cli.loc[ridx, "RagioneSociale"]   = rag
            df_cli.loc[ridx, "Indirizzo"]        = indir
            df_cli.loc[ridx, "Citta"]            = citta
            df_cli.loc[ridx, "CAP"]              = cap
            df_cli.loc[ridx, "PersonaRiferimento"] = persona
            df_cli.loc[ridx, "Telefono"]         = tel
            df_cli.loc[ridx, "Cellulare"]        = cell
            df_cli.loc[ridx, "Email"]            = email
            df_cli.loc[ridx, "PartitaIVA"]       = piva
            df_cli.loc[ridx, "IBAN"]             = iban
            df_cli.loc[ridx, "SDI"]              = sdi
            df_cli.loc[ridx, "UltimoRecall"]     = pd.to_datetime(ult_recall) if ult_recall else pd.NaT
            df_cli.loc[ridx, "UltimaVisita"]     = pd.to_datetime(ult_visita) if ult_visita else pd.NaT
            df_cli.loc[ridx, "ProssimoRecall"]   = pd.to_datetime(prox_recall) if prox_recall else pd.NaT
            df_cli.loc[ridx, "ProssimaVisita"]   = pd.to_datetime(prox_visita) if prox_visita else pd.NaT
            df_cli.loc[ridx, "Note"]             = note
            save_clienti(df_cli)
            st.success("Anagrafica aggiornata.")
            st.rerun()

    # ----------------- PREVENTIVI -----------------
    st.markdown("---")
    st.markdown("#### Preventivi")

    df_prev = load_preventivi()
    cli_prev = df_prev[df_prev["ClienteID"].astype(str) == str(sel_id)].copy()

    # Box elenco preventivi del cliente
    if cli_prev.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        cli_prev = cli_prev.sort_values("Numero")
        st.markdown("**Preventivi esistenti**")
        # Piccola tabellina con link download
        display = cli_prev[["Numero", "Data", "Template", "Note"]].copy()
        st.markdown(html_table(display), unsafe_allow_html=True)

        # bottoni download
        for _, r in cli_prev.iterrows():
            p = Path(r["File"])
            if p.exists():
                with open(p, "rb") as f:
                    st.download_button(
                        label=f"Scarica {r['Numero']}",
                        data=f.read(),
                        file_name=p.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_{r['Numero']}"
                    )

    st.markdown("—")
    st.markdown("**Crea nuovo preventivo**")

    templates = _list_templates()
    has_docx = _docx_available()

    colp1, colp2 = st.columns([0.5, 0.5])
    with colp1:
        tpl_name = st.selectbox(
            "Template",
            options=[t.name for t in templates] if templates else [],
            help="I template .docx devono essere in storage/templates/"
        )
        oggetto = st.text_input("Oggetto preventivo", "")
        note_p  = st.text_area("Note interne (opzionale)", "", height=80)
    with colp2:
        oggi_str = pd.Timestamp.today().strftime("%d/%m/%Y")
        st.write(f"Data documento: **{oggi_str}**")
        st.caption("Il numero verrà assegnato automaticamente (formato SHT-MI-NNNN).")

        if not has_docx:
            st.error("Modulo python-docx non disponibile. Aggiungi 'python-docx' a requirements.txt.")
        create_btn = st.button("Crea preventivo", use_container_width=True, disabled=not(has_docx and tpl_name))

    if create_btn and has_docx and tpl_name:
        # prepara numero e mappa campi
        new_num = _next_preventivo_number(df_prev)
        template_path = TEMPLATE_DIR / tpl_name
        out_filename  = f"Preventivo_{new_num}.docx"
        out_path      = PREVENTIVI_DIR / out_filename

        mapping = {
            # dati cliente
            "NUMERO": new_num,
            "DATA": oggi_str,
            "RAGIONE_SOCIALE": sstr(row.get("RagioneSociale")),
            "RIFERIMENTO": sstr(row.get("PersonaRiferimento")),
            "INDIRIZZO": sstr(row.get("Indirizzo")),
            "CAP": sstr(row.get("CAP")),
            "CITTA": sstr(row.get("Citta")),
            "PARTITA_IVA": sstr(row.get("PartitaIVA")),
            "IBAN": sstr(row.get("IBAN")),
            "SDI": sstr(row.get("SDI")),
            "EMAIL": sstr(row.get("Email")),
            "TELEFONO": sstr(row.get("Telefono")),
            "CELLULARE": sstr(row.get("Cellulare")),
            # campi documento
            "OGGETTO": oggetto,
            "NOTE": note_p,
        }

        try:
            _replace_in_docx(template_path, mapping, out_path)
        except Exception as e:
            st.error(f"Errore durante la generazione del DOCX: {e}")
        else:
            # aggiorna registro
            df_prev = load_preventivi()
            new_row = pd.DataFrame([{
                "Numero": new_num,
                "ClienteID": str(sel_id),
                "Data": pd.Timestamp.today().strftime("%Y-%m-%d"),
                "Template": tpl_name,
                "File": str(out_path),
                "Note": note_p
            }])
            df_prev = pd.concat([df_prev, new_row], ignore_index=True)
            save_preventivi(df_prev)

            # copia su OneDrive se configurato
            if str(ONEDRIVE_DIR).strip():
                try:
                    shutil.copy2(out_path, ONEDRIVE_DIR / out_filename)
                    st.success(f"Preventivo creato ({new_num}) e copiato in OneDrive.")
                except Exception as e:
                    st.warning(f"Creato, ma copia OneDrive non riuscita: {e}")
            else:
                st.success(f"Preventivo creato ({new_num}).")

            st.rerun()

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
    closed_mask = ct["Stato"].str.lower() == "chiuso"

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
            st.caption(f"{sstr(r['NumeroContratto'])} — {sstr(r['DescrizioneProdotto'])}")
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

    PAGES = {"Dashboard": page_dashboard, "Clienti": page_clienti, "Contratti": page_contratti}
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio(
        "Menu", list(PAGES.keys()),
        index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0
    )

    df_cli = load_clienti()
    df_ct  = load_contratti()

    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
