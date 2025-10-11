# SHT – Gestione Clienti (Streamlit 1.50 compatibile)
from __future__ import annotations

import re
from pathlib import Path
from datetime import datetime, date
from typing import Dict, List

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from docx import Document
import xlsxwriter

# -----------------------------------------------------------------------------
# Percorsi e costanti
# -----------------------------------------------------------------------------
DATA_DIR = Path("storage")
TEMPLATES_DIR = DATA_DIR / "templates"
PREVENTIVI_DIR = DATA_DIR / "preventivi"
EXPORT_DIR = DATA_DIR / "export"

CLIENTI_CSV = DATA_DIR / "clienti.csv"
CONTRATTI_CSV = DATA_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = DATA_DIR / "preventivi.csv"

for p in [DATA_DIR, TEMPLATES_DIR, PREVENTIVI_DIR, EXPORT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Stile (azzurro chiaro)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="SHT – Gestione Clienti", layout="wide")
st.markdown(
    """
    <style>
      :root { --sht-blue:#1e88e5; --sht-bg:#e3f2fd; --sht-soft:#ffffff; }
      .main  { background:var(--sht-bg) !important; }
      header { background:var(--sht-soft) !important; }
      .sht-title { font-weight:800; font-size:28px; color:#0d1117; }
      .chip-green { background:#e8f5e9; color:#1b5e20; padding:2px 8px; border-radius:10px; }
      .chip-red   { background:#ffebee; color:#b71c1c; padding:2px 8px; border-radius:10px; }
      .row-closed { background:#ffe6e6 !important; }
      table.ctr { width:100%; border-collapse:collapse; background:white; }
      table.ctr th, table.ctr td { border:1px solid #e0e0e0; padding:6px 8px; font-size:13px; }
      table.ctr thead th { background:#bbdefb; color:#0d1117; font-weight:700; }
      .btn-small { padding:2px 6px; border:0; border-radius:6px; background:#1e88e5; color:white;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Helper caricamento/salvataggio
# -----------------------------------------------------------------------------
def ensure_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df

def load_clienti() -> pd.DataFrame:
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=[
            "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
            "Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall",
            "UltimaVisita","ProssimaVisita","Note"])
    df = pd.read_csv(CLIENTI_CSV, dtype=str, keep_default_na=False)
    # normalizza
    df = ensure_columns(df, [
        "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
        "Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall",
        "UltimaVisita","ProssimaVisita","Note"
    ])
    # id numerico (se possibile)
    with pd.option_context("future.no_silent_downcasting", True):
        df["ClienteID"] = pd.to_numeric(df["ClienteID"], errors="coerce").astype("Int64")
    return df

def save_clienti(df: pd.DataFrame):
    df.to_csv(CLIENTI_CSV, index=False)

def load_contratti() -> pd.DataFrame:
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=[
            "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
            "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
        ])
    df = pd.read_csv(CONTRATTI_CSV, dtype=str, keep_default_na=False)
    df = ensure_columns(df, [
        "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
        "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
    ])
    # date
    for c in ["DataInizio","DataFine"]:
        df[c] = pd.to_datetime(df[c], dayfirst=True, errors="coerce")
    # numerici
    for c in ["NOL_FIN","NOL_INT","TotRata"]:
        with pd.option_context("future.no_silent_downcasting", True):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    with pd.option_context("future.no_silent_downcasting", True):
        df["ClienteID"] = pd.to_numeric(df["ClienteID"], errors="coerce").astype("Int64")
    return df

def save_contratti(df: pd.DataFrame):
    # mantieni formato data dd/mm/aaaa alla scrittura
    tmp = df.copy()
    for c in ["DataInizio","DataFine"]:
        tmp[c] = tmp[c].dt.strftime("%d/%m/%Y").fillna("")
    tmp.to_csv(CONTRATTI_CSV, index=False)

def load_preventivi() -> pd.DataFrame:
    if not PREVENTIVI_CSV.exists():
        return pd.DataFrame(columns=["Numero","ClienteID","Data","Template","Path"])
    df = pd.read_csv(PREVENTIVI_CSV, dtype=str, keep_default_na=False)
    return ensure_columns(df, ["Numero","ClienteID","Data","Template","Path"])

def save_preventivi(df: pd.DataFrame):
    df.to_csv(PREVENTIVI_CSV, index=False)

# -----------------------------------------------------------------------------
# Utility UI
# -----------------------------------------------------------------------------
def safe_selectbox(label: str, options: List[str]):
    idx = 0 if len(options) > 0 else None
    return st.selectbox(label, options, index=idx)

def status_chip(s: str) -> str:
    s = (s or "").strip().lower()
    if s == "chiuso":
        return "<span class='chip-red'>chiuso</span>"
    return "<span class='chip-green'>aperto</span>"

def fmt(x):
    if pd.isna(x):
        return ""
    if isinstance(x, (pd.Timestamp, np.datetime64)):
        try:
            return pd.to_datetime(x).strftime("%d/%m/%Y")
        except Exception:
            return ""
    return x

def contracts_html(ct: pd.DataFrame) -> str:
    # prepara dataframe “safe”
    cols = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    ct = ct.copy()
    for c in ["DataInizio","DataFine"]:
        if c in ct.columns:
            ct[c] = pd.to_datetime(ct[c], errors="coerce")
    # generazione righe
    head = "<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>"
    rows = []
    for _, r in ct.iterrows():
        closed = (str(r.get("Stato","")).strip().lower() == "chiuso")
        tr_class = "row-closed" if closed else ""
        cells = []
        for c in cols:
            if c == "Stato":
                cells.append(f"<td>{status_chip(r.get(c,''))}</td>")
            else:
                cells.append(f"<td>{fmt(r.get(c,''))}</td>")
        rows.append(f"<tr class='{tr_class}'>" + "".join(cells) + "</tr>")
    return f"<table class='ctr'><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table>"

def show_html(html: str, height: int = 420):
    components.html(html, height=height, scrolling=True)

def esporta_xlsx_con_intestazione(cliente: Dict, df: pd.DataFrame, path: Path):
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        workbook  = writer.book
        sheetname = "Contratti"
        worksheet = workbook.add_worksheet(sheetname)
        writer.sheets[sheetname] = worksheet

        title_fmt = workbook.add_format({"bold":True, "align":"center", "valign":"vcenter", "font_size":14})
        headers_fmt = workbook.add_format({"bold":True, "bg_color":"#bbdefb", "border":1})

        title = f"{cliente.get('RagioneSociale','')}"
        width = max(df.shape[1]-1, 0)
        worksheet.merge_range(0, 0, 0, width, title, title_fmt)

        # scrivi header
        for j, col in enumerate(df.columns):
            worksheet.write(2, j, col, headers_fmt)

        # scrivi dati
        for i, (_, row) in enumerate(df.iterrows(), start=3):
            for j, col in enumerate(df.columns):
                val = row[col]
                if isinstance(val, (pd.Timestamp, np.datetime64)):
                    val = pd.to_datetime(val).strftime("%d/%m/%Y") if not pd.isna(val) else ""
                worksheet.write(i, j, "" if pd.isna(val) else val)

# -----------------------------------------------------------------------------
# Preventivi – sostituzione segnaposto
# -----------------------------------------------------------------------------
def fill_docx_placeholders(doc: Document, mapping: Dict[str, str]):
    def replace_run(run):
        for k, v in mapping.items():
            run.text = run.text.replace(f"<<{k}>>", str(v))
    # paragrafi
    for p in doc.paragraphs:
        for r in p.runs:
            replace_run(r)
    # tabelle
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        replace_run(r)

def genera_preventivo(cliente: Dict, template_name: str) -> Path:
    template_path = TEMPLATES_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template non trovato: {template_path}")

    # numero progressivo “locale”
    next_num = int(st.session_state.get("NEXT_OFFERTA", 1))
    st.session_state["NEXT_OFFERTA"] = next_num + 1

    mapping = {
        "CLIENTE": cliente.get("RagioneSociale",""),
        "INDIRIZZO": cliente.get("Indirizzo",""),
        "CITTA": cliente.get("Citta",""),
        "NUMERO_OFFERTA": str(next_num),
        "DATA": datetime.now().strftime("%d/%m/%Y"),
    }
    doc = Document(str(template_path))
    fill_docx_placeholders(doc, mapping)

    out = PREVENTIVI_DIR / f"Preventivo_{next_num}_{datetime.now():%Y%m%d_%H%M%S}.docx"
    doc.save(out)

    # log su CSV opzionale
    prev = load_preventivi()
    row = {"Numero":str(next_num),"ClienteID":str(cliente.get("ClienteID","")),
           "Data":datetime.now().strftime("%Y-%m-%d"),"Template":template_name,"Path":str(out)}
    prev = pd.concat([prev, pd.DataFrame([row])], ignore_index=True)
    save_preventivi(prev)
    return out

# -----------------------------------------------------------------------------
# Pagine
# -----------------------------------------------------------------------------
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("### 📊 Dashboard")

    # normalizza date
    for c in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        df_cli[c] = pd.to_datetime(df_cli[c], dayfirst=True, errors="coerce")
    for c in ["DataInizio","DataFine"]:
        df_ct[c] = pd.to_datetime(df_ct[c], dayfirst=True, errors="coerce")

    oggi = pd.Timestamp.today().normalize()
    entro6 = oggi + pd.DateOffset(months=6)

    # contratti in scadenza entro 6 mesi, esclusi “chiusi”
    aperti = df_ct["Stato"].str.lower().ne("chiuso")
    mask_scad = df_ct["DataFine"].notna() & df_ct["DataFine"].between(oggi, entro6) & aperti
    scad = df_ct[mask_scad].copy()
    scad = scad.merge(df_cli[["ClienteID","RagioneSociale"]], on="ClienteID", how="left")
    scad["Scadenza"] = scad["DataFine"].dt.strftime("%d/%m/%Y")
    scad = scad[["RagioneSociale","NumeroContratto","Scadenza","DescrizioneProdotto","TotRata"]].sort_values("Scadenza")

    # recall > 3 mesi
    r3 = oggi - pd.DateOffset(months=3)
    rec = df_cli[df_cli["UltimoRecall"].notna() & (df_cli["UltimoRecall"] < r3)][["RagioneSociale","UltimoRecall"]].copy()
    rec["UltimoRecall"] = rec["UltimoRecall"].dt.strftime("%d/%m/%Y")

    # visite > 6 mesi
    v6 = oggi - pd.DateOffset(months=6)
    vis = df_cli[df_cli["UltimaVisita"].notna() & (df_cli["UltimaVisita"] < v6)][["RagioneSociale","UltimaVisita"]].copy()
    vis["UltimaVisita"] = vis["UltimaVisita"].dt.strftime("%d/%m/%Y")

    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.markdown("#### 🕒 Contratti in scadenza (entro 6 mesi)")
        st.dataframe(scad, use_container_width=True, hide_index=True)
    with c2:
        st.markdown("#### ☎️ Ultimi recall > 3 mesi")
        st.dataframe(rec, use_container_width=True, hide_index=True)
    with c3:
        st.markdown("#### 👣 Ultime visite > 6 mesi")
        st.dataframe(vis, use_container_width=True, hide_index=True)

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("### 👥 Clienti")

    opts = df_cli.assign(label=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"].fillna("")).sort_values("label")
    labels = opts["label"].tolist()
    sel = safe_selectbox("Cliente", labels)
    if sel is None:
        st.info("Nessun cliente.")
        return
    sel_id = int(opts.loc[opts["label"].eq(sel), "ClienteID"].iloc[0])

    cli = df_cli.loc[df_cli["ClienteID"].eq(sel_id)].iloc[0].to_dict()
    st.markdown(f"**{cli.get('RagioneSociale','')}**")
    cols = st.columns(3)
    cols[0].write(f"**Persona di riferimento:** {cli.get('PersonaRiferimento','') or ''}")
    cols[1].write(f"**Indirizzo:** {cli.get('Indirizzo','') or ''} — {cli.get('Citta','') or ''} ({cli.get('CAP','') or ''})")
    cols[2].write(f"**P.IVA:** {cli.get('PartitaIVA','') or ''} — **SDI:** {cli.get('SDI','') or ''}")

    # NOTE
    st.markdown("**Note**")
    note = st.text_area("Aggiungi/Modifica note", value=cli.get("Note",""), height=80, label_visibility="collapsed")
    if st.button("Salva note"):
        df_cli.loc[df_cli["ClienteID"].eq(sel_id), "Note"] = note
        save_clienti(df_cli)
        st.success("Note salvate.")

    # Genera preventivo
    st.markdown("#### 🧾 Preventivi")
    tpl = st.selectbox("Template", ["Offerte_A4.docx","Offerte_A3.docx","Offerta_Varie.docx","Offerta_Centralino.docx"])
    if st.button("Genera preventivo"):
        out = genera_preventivo(cli, tpl)
        with open(out, "rb") as f:
            st.download_button("Scarica preventivo", f, file_name=out.name, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.success("Preventivo creato.")

    # Bozza: Nuovo cliente + primo contratto
    st.markdown("#### ➕ Nuovo cliente + primo contratto")
    with st.form("new_client_contract"):
        c1, c2, c3 = st.columns(3)
        rag = c1.text_input("Ragione sociale", "")
        piva = c2.text_input("Partita IVA", "")
        sdi  = c3.text_input("SDI", "")
        ind  = c1.text_input("Indirizzo", "")
        citta= c2.text_input("Città", "")
        cap  = c3.text_input("CAP", "")
        iban = c1.text_input("IBAN", "")
        pers = c2.text_input("Persona di riferimento", "")
        tel  = c3.text_input("Telefono", "")
        mail = c1.text_input("Email", "")

        # Validazioni minime
        if piva and not re.fullmatch(r"\d{11}", piva):
            st.warning("P.IVA non valida (11 cifre).")
        if cap and not re.fullmatch(r"\d{5}", cap):
            st.warning("CAP non valido (5 cifre).")
        if iban and not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{1,30}", iban, flags=re.I):
            st.warning("IBAN non valido.")

        st.markdown("**Primo contratto**")
        nct = st.text_input("Numero contratto", "")
        di  = st.date_input("Data inizio", date.today())
        df_ = st.date_input("Data fine", None)
        dur = st.text_input("Durata", "")
        desc= st.text_area("Descrizione prodotto", "")
        fin = st.number_input("NOL_FIN", min_value=0.0, step=1.0)
        inte= st.number_input("NOL_INT", min_value=0.0, step=1.0)
        tot = st.number_input("TotRata", min_value=0.0, step=1.0)

        submitted = st.form_submit_button("Crea cliente e contratto")
        if submitted:
            if not rag:
                st.error("Ragione sociale obbligatoria.")
            else:
                next_id = int(df_cli["ClienteID"].max()) + 1 if len(df_cli) else 1
                new_cli = {
                    "ClienteID": next_id, "RagioneSociale": rag, "PersonaRiferimento": pers, "Indirizzo": ind,
                    "Citta": citta, "CAP": cap, "Telefono": tel, "Email": mail, "PartitaIVA": piva,
                    "IBAN": iban, "SDI": sdi
                }
                df_cli2 = pd.concat([df_cli, pd.DataFrame([new_cli])], ignore_index=True)
                save_clienti(df_cli2)

                new_ct = {
                    "ClienteID": next_id, "NumeroContratto": nct,
                    "DataInizio": pd.to_datetime(di), "DataFine": pd.to_datetime(df_) if df_ else pd.NaT,
                    "Durata": dur, "DescrizioneProdotto": desc, "NOL_FIN":fin, "NOL_INT":inte,
                    "TotRata":tot, "Stato":"aperto"
                }
                df_ct2 = pd.concat([df_ct, pd.DataFrame([new_ct])], ignore_index=True)
                save_contratti(df_ct2)

                st.success("Cliente e contratto creati.")
                st.experimental_rerun()

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("### 🧾 Contratti (rosso = chiusi)")

    # Selettore cliente robusto
    opts = df_cli.assign(label=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"].fillna("")).sort_values("label")
    labels = opts["label"].tolist()
    sel = safe_selectbox("Cliente", labels)
    if sel is None:
        st.info("Nessun cliente.")
        return
    sel_id = int(opts.loc[opts["label"].eq(sel), "ClienteID"].iloc[0])

    ct_cli = df_ct[df_ct["ClienteID"].eq(sel_id)].copy().reset_index(drop=True)

    # Tabella con checkbox e bottone chiudi
    st.markdown("#### Selezione/chiusura righe")
    idx_selected = []
    for i, r in ct_cli.iterrows():
        closed = (str(r.get("Stato","")).strip().lower()=="chiuso")
        row_bg = "background-color: #ffe6e6;" if closed else ""
        with st.container():
            c1, c2, c3, c4 = st.columns([0.6, 4, 3, 1.2])
            with c1:
                checked = st.checkbox("", key=f"sel_{i}", value=False, help="Seleziona riga")
                if checked:
                    idx_selected.append(i)
            with c2:
                st.markdown(f"<div style='{row_bg}'><b>{r.get('NumeroContratto','')}</b> — {r.get('DescrizioneProdotto','')}</div>", unsafe_allow_html=True)
            with c3:
                di = fmt(r.get("DataInizio"))
                df_ = fmt(r.get("DataFine"))
                st.write(f"dal {di} al {df_} · {r.get('Durata','')}")
            with c4:
                if not closed and st.button("Chiudi", key=f"chiudi_{i}"):
                    ct_cli.loc[i, "Stato"] = "chiuso"
                    # salva nel master
                    df_ct.loc[df_ct["ClienteID"].eq(sel_id) & (df_ct["NumeroContratto"]==r.get("NumeroContratto")), "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.success("Contratto chiuso.")
                    st.experimental_rerun()

    st.divider()
    st.markdown("#### Tabella completa")
    show_html(contracts_html(ct_cli), height=240)

    # Esporta/ Stampa selezione
    st.markdown("#### Esporta / Stampa selezione")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Esporta selezione in Excel"):
            if len(idx_selected)==0:
                st.warning("Seleziona almeno una riga.")
            else:
                out = EXPORT_DIR / f"Contratti_{sel_id}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
                cli = df_cli.loc[df_cli["ClienteID"].eq(sel_id)].iloc[0].to_dict()
                esporta_xlsx_con_intestazione(cli, ct_cli.iloc[idx_selected].copy(), out)
                with open(out, "rb") as f:
                    st.download_button("Scarica Excel", f, file_name=out.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with c2:
        st.info("La stampa PDF può essere effettuata dal file Excel o tramite stampa del browser.")

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    st.markdown("<div class='sht-title'>SHT – Gestione Clienti</div>", unsafe_allow_html=True)

    # carica dataset
    df_cli = load_clienti()
    df_ct  = load_contratti()

    # Navigazione
    page = st.sidebar.radio("Naviga", ["Dashboard","Clienti","Contratti"])
    role = "admin"  # se vuoi, in futuro aggiungiamo login/ruoli reali

    if page == "Dashboard":
        page_dashboard(df_cli, df_ct, role)
    elif page == "Clienti":
        page_clienti(df_cli, df_ct, role)
    else:
        page_contratti(df_cli, df_ct, role)

if __name__ == "__main__":
    main()
