# app.py — SHT – Gestione Clienti (Streamlit 1.50 compatibile)
from __future__ import annotations

import io
import re
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, Tuple, List

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components  # per futura compatibilità
from docx import Document
import xlsxwriter

# ------------------------------------------------------------------------------
# Config & Paths
# ------------------------------------------------------------------------------
st.set_page_config(page_title="SHT – Gestione Clienti", layout="wide")

STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage")).resolve()
TEMPLATES_DIR = STORAGE_DIR / "templates"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

PATH_CLIENTI = STORAGE_DIR / "clienti.csv"
PATH_CONTRATTI = STORAGE_DIR / "contratti_clienti.csv"
PATH_PREVENTIVI = STORAGE_DIR / "preventivi.csv"

# ------------------------------------------------------------------------------
# Utility: date & money
# ------------------------------------------------------------------------------
DATE_FMT = "%d/%m/%Y"

def to_date(s: str | float | int | None) -> pd.Timestamp | pd.NaT:
    if pd.isna(s) or s is None or str(s).strip() == "":
        return pd.NaT
    s = str(s).strip()
    # prova dd/mm/yyyy, yyyy-mm-dd
    for fmt in (DATE_FMT, "%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return pd.to_datetime(s, format=fmt, dayfirst=True)
        except Exception:
            pass
    # fallback generico
    try:
        return pd.to_datetime(s, dayfirst=True, errors="coerce")
    except Exception:
        return pd.NaT

def fmt_date(x) -> str:
    if pd.isna(x) or x is None:
        return ""
    # supporta sia Timestamp che stringhe “ISO”
    try:
        if not isinstance(x, (pd.Timestamp, datetime, date)):
            x = to_date(x)
        return x.strftime(DATE_FMT) if pd.notna(x) else ""
    except Exception:
        return ""

def to_float(s) -> float:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return 0.0
    ss = str(s).strip()
    if ss == "":
        return 0.0
    ss = ss.replace("€", "").replace(".", "").replace(",", ".")
    try:
        return float(ss)
    except Exception:
        return 0.0

# ------------------------------------------------------------------------------
# I/O CSV
# ------------------------------------------------------------------------------
def _ensure_csv(path: Path, header: List[str]):
    if not path.exists():
        path.write_text(",".join(header) + "\n", encoding="utf-8")

def load_clienti() -> pd.DataFrame:
    _ensure_csv(
        PATH_CLIENTI,
        [
            "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP","Telefono",
            "Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall","UltimaVisita",
            "ProssimaVisita","Note",
        ],
    )
    df = pd.read_csv(PATH_CLIENTI, dtype=str, keep_default_na=False)
    for c in ("UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"):
        df[c] = df[c].apply(to_date)
    # normalizza ClienteID come int-like string
    if "ClienteID" not in df.columns:
        df["ClienteID"] = ""
    df["ClienteID"] = df["ClienteID"].astype(str).str.replace(r"\.0$","", regex=True)
    return df

def save_clienti(df: pd.DataFrame):
    df_to = df.copy()
    for c in ("UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"):
        df_to[c] = df_to[c].apply(fmt_date)
    df_to.to_csv(PATH_CLIENTI, index=False, encoding="utf-8")

def load_contratti() -> pd.DataFrame:
    _ensure_csv(
        PATH_CONTRATTI,
        ["ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
         "NOL_FIN","NOL_INT","TotRata","Stato"],
    )
    df = pd.read_csv(PATH_CONTRATTI, dtype=str, keep_default_na=False)
    for c in ("DataInizio","DataFine"):
        df[c] = df[c].apply(to_date)
    for c in ("NOL_FIN","NOL_INT","TotRata"):
        df[c] = df[c].apply(to_float)
    if "Stato" not in df.columns:
        df["Stato"] = "aperto"
    df["ClienteID"] = df["ClienteID"].astype(str).str.replace(r"\.0$","", regex=True)
    return df

def save_contratti(df: pd.DataFrame):
    df_to = df.copy()
    for c in ("DataInizio","DataFine"):
        df_to[c] = df_to[c].apply(fmt_date)
    for c in ("NOL_FIN","NOL_INT","TotRata"):
        df_to[c] = df_to[c].astype(float)
    df_to.to_csv(PATH_CONTRATTI, index=False, encoding="utf-8")

def load_preventivi() -> pd.DataFrame:
    _ensure_csv(PATH_PREVENTIVI, ["ClienteID","Data","Numero","Template","File"])
    df = pd.read_csv(PATH_PREVENTIVI, dtype=str, keep_default_na=False)
    df["Data"] = df["Data"].apply(to_date)
    df["ClienteID"] = df["ClienteID"].astype(str).str.replace(r"\.0$","", regex=True)
    return df

def save_preventivi(df: pd.DataFrame):
    df_to = df.copy()
    df_to["Data"] = df_to["Data"].apply(fmt_date)
    df_to.to_csv(PATH_PREVENTIVI, index=False, encoding="utf-8")

# ------------------------------------------------------------------------------
# HTML TABLE RENDER (no f-string con backslash!)
# ------------------------------------------------------------------------------
CSS_TABLE = """
<style>
.ctr-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th, .ctr-table td { border: 1px solid #d0d7de; padding: 8px 10px; font-size: 13px; vertical-align: top; }
.ctr-table th { background: #e3f2fd; font-weight: 600; }
.ctr-row-closed td { background: #ffecec; color: #8a0000; }
.ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
"""

def html_table(df: pd.DataFrame, closed_mask: pd.Series | None = None) -> str:
    """
    Rende una tabella HTML leggibile e veloce, evitando f-string con backslash nella replace.
    """
    if df.empty:
        return CSS_TABLE + "<div>Nessun dato</div>"
    cols = list(df.columns)
    # header
    ths = "".join("<th>{}</th>".format(c) for c in cols)
    rows = []
    for i, r in df.iterrows():
        tds = "".join(
            "<td>{}</td>".format((str(r.get(c, "")) or "").replace("\n", "<br>"))
            for c in cols
        )
        cls = ""
        if closed_mask is not None:
            try:
                if bool(closed_mask.iloc[i]):
                    cls = " class='ctr-row-closed'"
            except Exception:
                pass
        rows.append("<tr{}>{}</tr>".format(cls, tds))
    body = "".join(rows)
    return CSS_TABLE + "<table class='ctr-table'><thead><tr>{}</tr></thead><tbody>{}</tbody></table>".format(ths, body)

# ------------------------------------------------------------------------------
# KPI Cards
# ------------------------------------------------------------------------------
def kpi_card(label: str, value: str | int, color: str):
    # piccola card con colore
    st.markdown(
        f"""
        <div style="
            display:inline-block; min-width:220px; margin:10px 10px 10px 0;
            padding:16px 20px; border-radius:14px; background:{color};
            color:#0d1117; border:1px solid rgba(0,0,0,0.05);
        ">
          <div style="font-size:16px; opacity:.75; margin-bottom:6px;">{label}</div>
          <div style="font-size:32px; font-weight:700;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------------------
# PREVENTIVI: numerazione e generazione
# ------------------------------------------------------------------------------
def next_preventivo_number(df_prev: pd.DataFrame) -> str:
    # formato SHT-MI-0001
    base = "SHT-MI-"
    if df_prev.empty:
        return base + "0001"
    nums = []
    for s in df_prev["Numero"].astype(str):
        m = re.search(r"SHT-MI-(\d+)", s)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 1
    return base + f"{nxt:04d}"

def generate_preventivo_word(cliente_row: pd.Series, tpl_path: Path, numero: str) -> Path:
    doc = Document(str(tpl_path))
    # rimpiazzi semplici nei paragrafi
    repl = {
        "{{RAGIONE_SOCIALE}}": cliente_row.get("RagioneSociale",""),
        "{{INDIRIZZO}}": cliente_row.get("Indirizzo",""),
        "{{CITTA}}": cliente_row.get("Citta",""),
        "{{CAP}}": cliente_row.get("CAP",""),
        "{{PIVA}}": cliente_row.get("PartitaIVA",""),
        "{{DATA}}": fmt_date(pd.Timestamp.today()),
        "{{NUMERO}}": numero,
        "{{REFERENTE}}": cliente_row.get("PersonaRiferimento",""),
        "{{EMAIL}}": cliente_row.get("Email",""),
        "{{TELEFONO}}": cliente_row.get("Telefono",""),
    }
    for p in doc.paragraphs:
        for k,v in repl.items():
            if k in p.text:
                p.text = p.text.replace(k, v)

    out_dir = STORAGE_DIR / "preventivi_files"
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{numero}_{pd.Timestamp.today().strftime('%Y%m%d_%H%M%S')}.docx"
    out_path = out_dir / filename
    doc.save(str(out_path))
    return out_path

# ------------------------------------------------------------------------------
# Pagine
# ------------------------------------------------------------------------------
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame):
    st.markdown("## Dashboard")

    # KPI
    today = pd.Timestamp.today().normalize()
    year = today.year

    n_clienti = len(df_cli)
    n_ct_aperti = (df_ct["Stato"].str.lower() != "chiuso").sum()
    n_ct_chiusi = (df_ct["Stato"].str.lower() == "chiuso").sum()
    n_ct_year = df_ct[df_ct["DataInizio"].dt.year == year].shape[0]

    kpi_card("Clienti attivi", n_clienti, "#E3F2FD")        # blu chiaro
    kpi_card("Contratti aperti", n_ct_aperti, "#E6F4EA")    # verde chiaro
    kpi_card("Contratti chiusi", n_ct_chiusi, "#FFE8E8")    # rosso chiaro
    kpi_card(f"Contratti {year}", n_ct_year, "#FFF7D6")     # giallo chiaro

    # cerca cliente → apri scheda cliente
    st.markdown("### Cerca cliente")
    opts = (
        df_cli.assign(lbl=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"])
        .sort_values("lbl")
    )
    lbl = st.selectbox("Digita e scegli…", opts["lbl"].tolist(), index=None, placeholder="Seleziona cliente…")
    if lbl:
        sel_id = opts.loc[opts["lbl"] == lbl, "ClienteID"].iloc[0]
        st.session_state["nav_page"] = "Clienti"
        st.session_state["open_client_id"] = str(sel_id)
        st.experimental_rerun()

    # contratti in scadenza (entro 6 mesi) — mostra uno per cliente (il più vicino)
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    horizon = today + pd.DateOffset(months=6)
    df_ct2 = df_ct.copy()
    df_ct2["FineCalc"] = df_ct2["DataFine"]
    due = df_ct2["FineCalc"]
    mask = (df_ct2["Stato"].str.lower() != "chiuso") & due.notna() & (due >= today) & (due <= horizon)
    df_due = df_ct2[mask].copy()
    # pick earliest per cliente
    df_due = df_due.sort_values(["ClienteID","FineCalc"]).groupby("ClienteID").head(1)
    df_due["Cliente"] = df_due["ClienteID"].map(
        df_cli.set_index("ClienteID")["RagioneSociale"].to_dict()
    )
    df_due = df_due[["Cliente","NumeroContratto","DescrizioneProdotto","DataFine","TotRata"]]
    df_due["DataFine"] = df_due["DataFine"].apply(fmt_date)
    st.markdown(html_table(df_due))

    cols = st.columns(2)
    with cols[0]:
        st.markdown("### Ultimi recall (> 3 mesi)")
        thre = today - pd.DateOffset(months=3)
        m = df_cli["UltimoRecall"].notna() & (df_cli["UltimoRecall"] <= thre)
        recall = df_cli.loc[m, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]].copy()
        recall["UltimoRecall"] = recall["UltimoRecall"].apply(fmt_date)
        recall["ProssimoRecall"] = recall["ProssimoRecall"].apply(fmt_date)
        st.markdown(html_table(recall))

    with cols[1]:
        st.markdown("### Ultime visite (> 6 mesi)")
        thre = today - pd.DateOffset(months=6)
        m = df_cli["UltimaVisita"].notna() & (df_cli["UltimaVisita"] <= thre)
        visite = df_cli.loc[m, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]].copy()
        visite["UltimaVisita"] = visite["UltimaVisita"].apply(fmt_date)
        visite["ProssimaVisita"] = visite["ProssimaVisita"].apply(fmt_date)
        st.markdown(html_table(visite))

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, df_prev: pd.DataFrame):
    st.markdown("## Clienti")

    opts = df_cli.assign(lbl=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"]).sort_values("lbl")
    default_idx = None
    if "open_client_id" in st.session_state:
        oc = str(st.session_state["open_client_id"])
        where = list(opts["ClienteID"].astype(str))
        if oc in where:
            default_idx = where.index(oc)
    lbl = st.selectbox("Cliente", opts["lbl"].tolist(), index=default_idx, placeholder="Seleziona…")
    if lbl:
        sel_id = opts.loc[opts["lbl"] == lbl, "ClienteID"].iloc[0]
        row = df_cli[df_cli["ClienteID"] == str(sel_id)].iloc[0]

        # anagrafica
        st.markdown("### Anagrafica")
        c1,c2,c3,c4 = st.columns(4)
        with c1:
            st.write("**ClienteID**", str(row["ClienteID"]))
            rag = st.text_input("Ragione sociale", row["RagioneSociale"])
            ref = st.text_input("Persona di riferimento", row.get("PersonaRiferimento",""))
        with c2:
            ind = st.text_input("Indirizzo", row.get("Indirizzo",""))
            citta = st.text_input("Città", row.get("Citta",""))
            cap = st.text_input("CAP", row.get("CAP",""))
        with c3:
            tel = st.text_input("Telefono", row.get("Telefono",""))
            email = st.text_input("Email", row.get("Email",""))
            piva = st.text_input("Partita IVA", row.get("PartitaIVA",""))
        with c4:
            iban = st.text_input("IBAN", row.get("IBAN",""))
            sdi = st.text_input("SDI", row.get("SDI",""))

        c5,c6,c7,c8 = st.columns(4)
        with c5:
            ur = st.date_input("Ultimo recall", row["UltimoRecall"] if pd.notna(row["UltimoRecall"]) else None, format="DD/MM/YYYY")
        with c6:
            pr = st.date_input("Prossimo recall", row["ProssimoRecall"] if pd.notna(row["ProssimoRecall"]) else None, format="DD/MM/YYYY")
        with c7:
            uv = st.date_input("Ultima visita", row["UltimaVisita"] if pd.notna(row["UltimaVisita"]) else None, format="DD/MM/YYYY")
        with c8:
            pv = st.date_input("Prossima visita", row["ProssimaVisita"] if pd.notna(row["ProssimaVisita"]) else None, format="DD/MM/YYYY")

        note = st.text_area("Note", row.get("Note",""), height=100)

        if st.button("💾 Salva anagrafica"):
            idx = df_cli.index[df_cli["ClienteID"] == str(sel_id)][0]
            for k,v in {
                "RagioneSociale":rag, "PersonaRiferimento":ref, "Indirizzo":ind, "Citta":citta, "CAP":cap,
                "Telefono":tel, "Email":email, "PartitaIVA":piva, "IBAN":iban, "SDI":sdi,
                "UltimoRecall": ur, "ProssimoRecall":pr, "UltimaVisita":uv, "ProssimaVisita":pv, "Note":note
            }.items():
                df_cli.loc[idx,k] = fmt_date(v) if k in ("UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita") else v
            save_clienti(df_cli)
            st.success("Anagrafica aggiornata.")

        # pulsante per andare a contratti del cliente
        if st.button("➡️ Vai alla gestione contratti di questo cliente"):
            st.session_state["nav_page"] = "Contratti"
            st.session_state["open_client_id"] = str(sel_id)
            st.experimental_rerun()

        # PREVENTIVI
        st.markdown("---")
        st.markdown("### Preventivi")
        # lista
        prev_cli = df_prev[df_prev["ClienteID"] == str(sel_id)].copy()
        if not prev_cli.empty:
            prev_cli = prev_cli.sort_values("Data", ascending=False)
            prev_cli["Data"] = prev_cli["Data"].apply(fmt_date)
            st.markdown(html_table(prev_cli[["Data","Numero","Template","File"]]))
        else:
            st.info("Nessun preventivo per questo cliente.")

        # genera
        st.markdown("#### Genera nuovo preventivo")
        tpls = [p.name for p in sorted(TEMPLATES_DIR.glob("*.docx"))]
        tpl = st.selectbox("Template", tpls, index=0 if tpls else None)
        if st.button("📄 Genera preventivo"):
            if not tpl:
                st.warning("Nessun template trovato in storage/templates.")
            else:
                numero = next_preventivo_number(df_prev)
                out = generate_preventivo_word(row, TEMPLATES_DIR / tpl, numero)
                df_prev = load_preventivi()
                df_prev.loc[len(df_prev)] = [str(sel_id), pd.Timestamp.today(), numero, tpl, str(out.name)]
                save_preventivi(df_prev)
                st.success(f"Preventivo generato: {out.name}")

    st.markdown("---")
    st.markdown("### Nuovo cliente + primo contratto")
    with st.form("new_cli_form"):
        nc1,nc2,nc3 = st.columns(3)
        with nc1:
            n_rag = st.text_input("Ragione sociale *", "")
            n_ref = st.text_input("Persona di riferimento", "")
            n_ind = st.text_input("Indirizzo", "")
        with nc2:
            n_citta = st.text_input("Città", "")
            n_cap = st.text_input("CAP", "")
            n_tel = st.text_input("Telefono", "")
            n_email = st.text_input("Email", "")
        with nc3:
            n_piva = st.text_input("Partita IVA", "")
            n_iban = st.text_input("IBAN", "")
            n_sdi = st.text_input("SDI", "")

        st.markdown("**Primo contratto**")
        cc1,cc2,cc3,cc4 = st.columns(4)
        with cc1:
            n_inizio = st.date_input("Data inizio", value=None, format="DD/MM/YYYY")
        with cc2:
            n_fine = st.date_input("Data fine", value=None, format="DD/MM/YYYY")
        with cc3:
            n_durata = st.selectbox("Durata (mesi)", [12,24,36,48,60,72], index=4)
        with cc4:
            n_desc = st.text_input("Descrizione prodotto", "")
        cc5,cc6,cc7 = st.columns(3)
        with cc1:
            pass
        with cc5:
            n_fin = st.number_input("NOL_FIN", min_value=0.0, step=1.0, value=0.0)
        with cc6:
            n_int = st.number_input("NOL_INT", min_value=0.0, step=1.0, value=0.0)
        with cc7:
            n_tot = st.number_input("TotRata", min_value=0.0, step=1.0, value=float(n_fin+n_int))
        submitted = st.form_submit_button("Crea cliente e contratto")
        if submitted:
            # nuovo ClienteID
            ex = pd.to_numeric(df_cli["ClienteID"], errors="coerce")
            new_id = int(np.nanmax(ex) + 1) if df_cli.shape[0] else 1
            df_cli.loc[len(df_cli)] = [
                str(new_id), n_rag, n_ref, n_ind, n_citta, n_cap, n_tel, n_email, n_piva,
                n_iban, n_sdi, "", "", "", "", ""
            ]
            save_clienti(df_cli)

            df_ct.loc[len(df_ct)] = [
                str(new_id), "", n_inizio, n_fine, str(n_durata), n_desc, float(n_fin), float(n_int),
                float(n_tot), "aperto"
            ]
            save_contratti(df_ct)
            st.success("Cliente e contratto creati.")
            st.session_state["open_client_id"] = str(new_id)
            st.experimental_rerun()

def _export_selection_excel(cliente_row: pd.Series, df_sel: pd.DataFrame) -> bytes:
    # crea excel in memoria con intestazione al centro
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_out = df_sel.copy()
        for c in ("DataInizio","DataFine"):
            df_out[c] = df_out[c].apply(fmt_date)
        df_out.to_excel(writer, index=False, sheet_name="Contratti", startrow=4)
        wb = writer.book
        ws = writer.sheets["Contratti"]

        title = f"{cliente_row.get('ClienteID','')} – {cliente_row.get('RagioneSociale','')}"
        ws.merge_range(0, 0, 0, max(0, df_out.shape[1]-1), title, wb.add_format({
            "align": "center", "bold": True, "font_size": 14
        }))
        # header format
        header_fmt = wb.add_format({"bold":True, "bg_color":"#E3F2FD", "border":1})
        for col_idx, col_name in enumerate(df_out.columns):
            ws.write(4, col_idx, col_name, header_fmt)
        # column autosize
        for i, col in enumerate(df_out.columns):
            width = max(12, min(60, int(df_out[col].astype(str).map(len).max()) + 2))
            ws.set_column(i, i, width)
    return output.getvalue()

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame):
    st.markdown("## Contratti (rosso = chiusi)")

    opts = df_cli.assign(lbl=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"]).sort_values("lbl")
    default_idx = None
    if "open_client_id" in st.session_state:
        oc = str(st.session_state["open_client_id"])
        if oc in list(opts["ClienteID"].astype(str)):
            default_idx = list(opts["ClienteID"].astype(str)).index(oc)
    lbl = st.selectbox("Cliente", opts["lbl"].tolist(), index=default_idx, placeholder="Seleziona cliente…")
    if not lbl:
        return
    sel_id = opts.loc[opts["lbl"] == lbl, "ClienteID"].iloc[0]
    row_cli = df_cli[df_cli["ClienteID"] == str(sel_id)].iloc[0]

    subset = df_ct[df_ct["ClienteID"] == str(sel_id)].copy()
    if subset.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    # Sezione selezione/chiusura righe
    st.markdown("### Selezione/chiusura righe")
    for i, r in subset.reset_index().iterrows():
        left, right = st.columns([0.9, 0.1])
        with left:
            txt = f"— {r['DescrizioneProdotto']}"
            periodo = f" dal {fmt_date(r['DataInizio'])} al {fmt_date(r['DataFine'])}"
            st.checkbox(txt + periodo, key=f"sel_{r['index']}", value=False)
        with right:
            if st.button("Chiudi", key=f"chiudi_{r['index']}"):
                ridx = r["index"]
                df_ct.loc[ridx, "Stato"] = "chiuso"
                save_contratti(df_ct)
                st.success("Contratto chiuso.")
                st.experimental_rerun()

    # Tabella completa
    st.markdown("### Tabella completa")
    show = subset.copy()
    show["DataInizio"] = show["DataInizio"].apply(fmt_date)
    show["DataFine"] = show["DataFine"].apply(fmt_date)
    closed_mask = (subset["Stato"].str.lower() == "chiuso").reset_index(drop=True)
    st.markdown(html_table(show[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]], closed_mask=closed_mask))

    st.markdown("### Esporta / Stampa selezione")
    if st.button("Esporta selezione in Excel"):
        choose_idx = []
        for i, r in subset.reset_index().iterrows():
            if st.session_state.get(f"sel_{r['index']}", False):
                choose_idx.append(r["index"])
        if not choose_idx:
            st.warning("Seleziona almeno una riga sopra.")
        else:
            df_sel = df_ct.loc[choose_idx].copy()
            xlsx = _export_selection_excel(row_cli, df_sel)
            st.download_button(
                "Scarica Excel",
                data=xlsx,
                file_name=f"Contratti_{row_cli['ClienteID']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            st.info("Per la stampa PDF puoi usare la stampa del browser o esportare l’Excel e stamparlo da lì.")

# ------------------------------------------------------------------------------
# Router
# ------------------------------------------------------------------------------
def main():
    df_cli = load_clienti()
    df_ct = load_contratti()
    df_prev = load_preventivi()

    pages = ["Dashboard","Clienti","Contratti"]
    if "nav_page" not in st.session_state:
        st.session_state["nav_page"] = "Dashboard"
    st.sidebar.title("SHT – Gestione Clienti")
    st.sidebar.write(" ")
    st.session_state["nav_page"] = st.sidebar.radio("Navigazione", pages, index=pages.index(st.session_state["nav_page"]))

    if st.session_state["nav_page"] == "Dashboard":
        page_dashboard(df_cli, df_ct)
    elif st.session_state["nav_page"] == "Clienti":
        page_clienti(df_cli, df_ct, df_prev)
    elif st.session_state["nav_page"] == "Contratti":
        page_contratti(df_cli, df_ct)

if __name__ == "__main__":
    main()
