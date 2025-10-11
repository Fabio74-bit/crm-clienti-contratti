# app.py — Gestionale Clienti SHT (Dashboard invariata, Clienti potenziata)
from __future__ import annotations

import os
import re
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict

import pandas as pd
import streamlit as st
from docx import Document

# ==========================
# CONFIG / COSTANTI
# ==========================
APP_TITLE = "GESTIONALE CLIENTI – SHT"

# storage base (secrets -> fallback ./storage)
STORAGE_DIR = Path(
    st.secrets.get("LOCAL_STORAGE_DIR", st.secrets.get("storage", {}).get("dir", "storage"))
)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV     = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV   = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV  = STORAGE_DIR / "preventivi.csv"    # archivio metadata preventivi

TEMPLATES_DIR   = STORAGE_DIR / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# cartella OneDrive dove scrivere i preventivi (puoi metterla nei secrets)
ONEDRIVE_DIR = Path(st.secrets.get("ONEDRIVE_DIR", STORAGE_DIR / "onedrive_out"))
ONEDRIVE_DIR.mkdir(parents=True, exist_ok=True)

# colonne canoniche
CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento",
    "Indirizzo", "Citta", "CAP",
    "Telefono", "Cellulare", "Email",   # <-- aggiunto Cellulare
    "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita",
    "Note",
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]
PREVENTIVI_COLS = ["PreventivoID", "ClienteID", "Data", "Template", "File", "Totale"]

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

def ymd(d) -> str:
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%Y-%m-%d")

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
    # mantieni solo l’ordine desiderato
    return df[cols].copy()

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
        out[c] = out[c].apply(ymd)
    out.to_csv(CLIENTI_CSV, index=False)

def save_contratti(df: pd.DataFrame):
    out = df.copy()
    for c in ["DataInizio","DataFine"]:
        out[c] = out[c].apply(ymd)
    out.to_csv(CONTRATTI_CSV, index=False)

def save_preventivi(df: pd.DataFrame):
    df.to_csv(PREVENTIVI_CSV, index=False)

# ==========================
# HTML TABLE per presentazione
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
    Login semplice su st.secrets['auth']['users'].
    Ritorna (username, ruolo). Se non configurato -> ospite.
    """
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
# DOCX Template helpers (preventivi)
# ==========================

PLACEHOLDERS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento",
    "Indirizzo", "Citta", "CAP",
    "Telefono", "Cellulare", "Email",
    "PartitaIVA", "IBAN", "SDI",
    "DataOggi", "NumeroPreventivo"
]

def _replace_text_in_paragraph(par, mapping: Dict[str, str]):
    for k, v in mapping.items():
        if not k.startswith("{{"):  # accetta sia chiave "RagioneSociale" che "{{RagioneSociale}}"
            key = "{{" + k + "}}"
        else:
            key = k
        if key in par.text:
            inline = par.runs
            # ricostruisci il testo per non rompere i run
            txt = par.text.replace(key, v)
            for i in range(len(inline)-1, -1, -1):
                p = inline[i]._r
                p.getparent().remove(p)
            par.add_run(txt)

def _replace_all(document: Document, mapping: Dict[str, str]):
    for p in document.paragraphs:
        _replace_text_in_paragraph(p, mapping)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _replace_text_in_paragraph(p, mapping)

def next_preventivo_id(df_prev: pd.DataFrame) -> str:
    """Restituisce il prossimo ID con formato SHT-MI-0001"""
    if df_prev.empty:
        return "SHT-MI-0001"
    nums = []
    for s in df_prev["PreventivoID"]:
        m = re.search(r"(\d+)$", str(s))
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 1
    return f"SHT-MI-{nxt:04d}"

# ==========================
# PAGINE
# ==========================

def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # === Dashboard INVARIATA (come da tua versione “buona”) ===
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

    # Ricerca cliente
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

    # Contratti in scadenza entro 6 mesi (mostra primo per cliente)
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    ct = df_ct.copy()
    ct["DataFine"] = to_date_series(ct["DataFine"])
    open_mask  = ct["Stato"].fillna("aperto").str.lower() != "chiuso"
    within_6m  = (ct["DataFine"].notna() &
                  (ct["DataFine"] >= today) &
                  (ct["DataFine"] <= today + pd.DateOffset(months=6)))
    scad = ct[open_mask & within_6m].copy()
    if not scad.empty:
        scad = scad.sort_values(["ClienteID", "DataFine"]).groupby("ClienteID", as_index=False).first()

    disp = pd.DataFrame()
    if not scad.empty:
        disp = pd.DataFrame({
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
            "DataFine": scad["DataFine"].apply(fmt_date),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "TotRata": scad["TotRata"].apply(money),
        })
    st.markdown(html_table(disp), unsafe_allow_html=True)

    st.divider()

    # Ultimi recall (> 3 mesi)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecall"] = to_date_series(cli["UltimoRecall"])
        soglia = pd.Timestamp.today().normalize() - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall"].notna() & (cli["UltimoRecall"] <= soglia)]
        tab = r.loc[:, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]].copy()
        tab["UltimoRecall"]   = tab["UltimoRecall"].apply(fmt_date)
        tab["ProssimoRecall"] = to_date_series(tab["ProssimoRecall"]).apply(fmt_date)
        st.markdown(html_table(tab), unsafe_allow_html=True)

    # Ultime visite (> 6 mesi)
    with col2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisita"] = to_date_series(cli["UltimaVisita"])
        soglia_v = pd.Timestamp.today().normalize() - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita"].notna() & (cli["UltimaVisita"] <= soglia_v)]
        tab = v.loc[:, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]].copy()
        tab["UltimaVisita"]   = tab["UltimaVisita"].apply(fmt_date)
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

    # riga cliente
    row_idx = df_cli.index[df_cli["ClienteID"].astype(str)==str(sel_id)][0]
    row     = df_cli.loc[row_idx]

    # === FORM ANAGRAFICA MODIFICABILE ===
    st.markdown("#### Anagrafica")
    with st.form("edit_cli"):
        c1, c2, c3 = st.columns(3)
        with c1:
            rag = st.text_input("Ragione sociale", row.get("RagioneSociale",""))
            indir = st.text_input("Indirizzo", row.get("Indirizzo",""))
            citta = st.text_input("Città", row.get("Citta",""))
            cap   = st.text_input("CAP", row.get("CAP",""))
        with c2:
            persona = st.text_input("Persona di riferimento", row.get("PersonaRiferimento",""))
            tel     = st.text_input("Telefono", row.get("Telefono",""))
            cell    = st.text_input("Cellulare", row.get("Cellulare",""))  # nuovo campo
            email   = st.text_input("Email", row.get("Email",""))
        with c3:
            piva  = st.text_input("Partita IVA", row.get("PartitaIVA",""))
            iban  = st.text_input("IBAN", row.get("IBAN",""))
            sdi   = st.text_input("SDI", row.get("SDI",""))

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

        note = st.text_area("Note", row.get("Note",""), height=100)

        saved = st.form_submit_button("Salva modifiche", use_container_width=True)
        if saved:
            df_cli.loc[row_idx, "RagioneSociale"]      = rag
            df_cli.loc[row_idx, "Indirizzo"]           = indir
            df_cli.loc[row_idx, "Citta"]               = citta
            df_cli.loc[row_idx, "CAP"]                 = cap
            df_cli.loc[row_idx, "PersonaRiferimento"]  = persona
            df_cli.loc[row_idx, "Telefono"]            = tel
            df_cli.loc[row_idx, "Cellulare"]           = cell
            df_cli.loc[row_idx, "Email"]               = email
            df_cli.loc[row_idx, "PartitaIVA"]          = piva
            df_cli.loc[row_idx, "IBAN"]                = iban
            df_cli.loc[row_idx, "SDI"]                 = sdi
            df_cli.loc[row_idx, "UltimoRecall"]        = pd.to_datetime(ult_recall) if ult_recall else pd.NaT
            df_cli.loc[row_idx, "ProssimoRecall"]      = pd.to_datetime(prox_recall) if prox_recall else pd.NaT
            df_cli.loc[row_idx, "UltimaVisita"]        = pd.to_datetime(ult_visita) if ult_visita else pd.NaT
            df_cli.loc[row_idx, "ProssimaVisita"]      = pd.to_datetime(prox_visita) if prox_visita else pd.NaT
            df_cli.loc[row_idx, "Note"]                = note
            save_clienti(df_cli)
            st.success("Anagrafica salvata.")
            st.rerun()

    # Pulsante scorciatoia a Contratti
    if st.button("Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = str(sel_id)
        st.rerun()

    st.divider()

    # === PREVENTIVI ===
    st.markdown("#### Preventivi")
    df_prev = load_preventivi()

    # elenco templates disponibili (.docx in storage/templates)
    templates = sorted([p.name for p in TEMPLATES_DIR.glob("*.docx")])
    if not templates:
        st.warning("Nessun template .docx trovato in 'storage/templates'. Copia qui i tuoi modelli (Offerta_*.docx).")
    else:
        with st.form("new_prev"):
            c1, c2, c3 = st.columns([0.4, 0.3, 0.3])
            with c1:
                tpl = st.selectbox("Scegli un template", templates)
            with c2:
                data_prev = st.date_input("Data preventivo", value=datetime.today().date(), format="DD/MM/YYYY")
            with c3:
                tot_prev  = st.text_input("Totale preventivo (opzionale)", "")

            gen = st.form_submit_button("Genera preventivo", use_container_width=True)
            if gen:
                # calcola nuovo numero
                new_id = next_preventivo_id(df_prev)
                # mappa valori
                mapping = {
                    "NumeroPreventivo": new_id,
                    "DataOggi": datetime.today().strftime("%d/%m/%Y"),
                    "ClienteID": str(row.get("ClienteID","")),
                    "RagioneSociale": row.get("RagioneSociale",""),
                    "PersonaRiferimento": row.get("PersonaRiferimento",""),
                    "Indirizzo": row.get("Indirizzo",""),
                    "Citta": row.get("Citta",""),
                    "CAP": row.get("CAP",""),
                    "Telefono": row.get("Telefono",""),
                    "Cellulare": row.get("Cellulare",""),
                    "Email": row.get("Email",""),
                    "PartitaIVA": row.get("PartitaIVA",""),
                    "IBAN": row.get("IBAN",""),
                    "SDI": row.get("SDI",""),
                }

                # carica e sostituisci
                doc = Document(TEMPLATES_DIR / tpl)
                _replace_all(doc, mapping)

                # salva su OneDrive
                fname = f"Preventivo_{new_id}_{datetime.today().strftime('%Y%m%d')}.docx"
                out_path = ONEDRIVE_DIR / fname
                doc.save(out_path)

                # registra metadata
                new_row = {
                    "PreventivoID": new_id,
                    "ClienteID": str(sel_id),
                    "Data": pd.to_datetime(data_prev).strftime("%Y-%m-%d"),
                    "Template": tpl,
                    "File": str(out_path),
                    "Totale": tot_prev.strip(),
                }
                df_prev = pd.concat([df_prev, pd.DataFrame([new_row])], ignore_index=True)
                save_preventivi(df_prev)
                st.success(f"Preventivo creato: {new_id}")
                st.rerun()

    # box elenco preventivi del cliente
    prev_cli = df_prev[df_prev["ClienteID"].astype(str)==str(sel_id)].copy().sort_values("Data", ascending=False)
    if prev_cli.empty:
        st.info("Nessun preventivo per questo cliente.")
    else:
        # mostro tabella e bottoni download
        show = prev_cli.copy()
        show["Data"] = pd.to_datetime(show["Data"]).dt.strftime("%d/%m/%Y")
        st.markdown(html_table(show[["PreventivoID","Data","Template","Totale","File"]]), unsafe_allow_html=True)

        # download ultimi file (in modo semplice: primo rigo)
        for i, r in prev_cli.iterrows():
            path = Path(r["File"])
            if path.exists():
                with open(path, "rb") as f:
                    st.download_button(
                        label=f"Scarica {r['PreventivoID']}",
                        data=f.read(),
                        file_name=path.name,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dl_{i}"
                    )

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

    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
    disp["TotRata"]    = disp["TotRata"].apply(money)

    st.markdown(html_table(
        disp[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]],
        closed_mask=closed_mask
    ), unsafe_allow_html=True)

    st.markdown("— Seleziona per **Chiudere/Riaprire**:")
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

    # login prima di entrare
    user, role = do_login()
    if not user:     # blocca finché non loggato
        st.stop()
    else:
        st.sidebar.success(f"Utente: {user} — Ruolo: {role}")

    # nav
    PAGES = {"Dashboard": page_dashboard, "Clienti": page_clienti, "Contratti": page_contratti}
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio(
        "Menu", list(PAGES.keys()),
        index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0
    )

    # load dati
    df_cli = load_clienti()
    df_ct  = load_contratti()

    # run pagina
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
