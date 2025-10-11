# SHT – Gestione Clienti (Streamlit 1.50)

from __future__ import annotations
import io
import re
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Tuple, List

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from dateutil.relativedelta import relativedelta
from docx import Document

# -----------------------------------------------------------------------------
# Config / percorsi
# -----------------------------------------------------------------------------
STORAGE_DIR = Path("storage")
TPL_DIR = STORAGE_DIR / "templates"
PREV_DIR = STORAGE_DIR / "preventivi"
CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"

PREV_DIR.mkdir(parents=True, exist_ok=True)

DATE_FMT = "%d/%m/%Y"

# -----------------------------------------------------------------------------
# Utils
# -----------------------------------------------------------------------------
def _strp_ddmmyyyy(s: str | float | int) -> pd.Timestamp | pd.NaT:
    if pd.isna(s) or str(s).strip() == "":
        return pd.NaT
    return pd.to_datetime(str(s), dayfirst=True, errors="coerce")

def parse_import_date(s: str) -> str:
    """Normalizza in dd/mm/aaaa per UI/esportazioni."""
    ts = _strp_ddmmyyyy(s)
    return "" if pd.isna(ts) else ts.strftime(DATE_FMT)

def parse_durata_to_months(s: str | int | float) -> int:
    """
    Supporta '60 M', '60M', '60 m', '60', ecc. Ritorna mesi (int). Fallback 0.
    """
    if pd.isna(s):
        return 0
    ss = str(s).strip().lower()
    m = re.findall(r"\d+", ss)
    return int(m[0]) if m else 0

def fine_calcolata(row: pd.Series) -> pd.Timestamp | pd.NaT:
    """
    Fine calcolata = DataFine se c'è, altrimenti DataInizio + Durata(mesi).
    """
    di = _strp_ddmmyyyy(row.get("DataInizio", ""))
    df = _strp_ddmmyyyy(row.get("DataFine", ""))
    if not pd.isna(df):
        return df
    if pd.isna(di):
        return pd.NaT
    mesi = parse_durata_to_months(row.get("Durata", ""))
    try:
        return (di + relativedelta(months=+mesi)).normalize()
    except Exception:
        return pd.NaT

def money(x) -> str:
    if pd.isna(x) or str(x).strip() == "":
        return ""
    try:
        v = float(str(x).replace(",", "."))
    except Exception:
        return str(x)
    return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def status_chip(s: str) -> str:
    s = (s or "").strip().lower()
    if s == "chiuso":
        return '<span class="chip chip-red">chiuso</span>'
    return '<span class="chip chip-green">aperto</span>'

def st_html(html: str, height: int = 400):
    # compat con 1.50 (niente st.html)
    components.html(html, height=height, scrolling=True)

# -----------------------------------------------------------------------------
# Loader / Saver
# -----------------------------------------------------------------------------
def load_csv(p: Path, cols: List[str]) -> pd.DataFrame:
    if not p.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(p, dtype=str).fillna("")
    # garantisco tutte le colonne attese
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    # e tolgo extra columns sconosciute
    return df[cols].copy()

def save_csv(df: pd.DataFrame, p: Path):
    df.to_csv(p, index=False)

# -----------------------------------------------------------------------------
# Dati
# -----------------------------------------------------------------------------
COLS_CLIENTI = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Email","PartitaIVA","IBAN","SDI","UltimoRecall","ProssimoRecall",
    "UltimaVisita","ProssimaVisita","Note"
]
COLS_CONTRATTI = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
    "NOL_FIN","NOL_INT","TotRata","Stato"  # Stato: 'aperto'/'chiuso'
]
COLS_PREVENTIVI = ["ClienteID","NomeFile","Data","Template"]

@st.cache_data(ttl=60)
def load_all() -> Tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    df_cli = load_csv(CLIENTI_CSV, COLS_CLIENTI)
    df_ct  = load_csv(CONTRATTI_CSV, COLS_CONTRATTI)
    df_prev= load_csv(PREVENTIVI_CSV, COLS_PREVENTIVI)
    return df_cli, df_ct, df_prev

def persist_all(df_cli, df_ct, df_prev):
    save_csv(df_cli, CLIENTI_CSV)
    save_csv(df_ct, CONTRATTI_CSV)
    save_csv(df_prev, PREVENTIVI_CSV)
    load_all.clear()  # reset cache

# -----------------------------------------------------------------------------
# UI helpers
# -----------------------------------------------------------------------------
def select_cliente(df_cli: pd.DataFrame, key: str) -> str | None:
    if df_cli.empty:
        st.warning("Nessun cliente presente.")
        return None
    opts = (
        df_cli[["ClienteID","RagioneSociale"]]
        .assign(label=lambda d: d["ClienteID"].astype(str)+" — "+d["RagioneSociale"])
        .to_dict(orient="records")
    )
    labels = [o["label"] for o in opts]
    default_idx = 0 if len(labels)>0 else None
    sel = st.selectbox("Cliente", labels, index=default_idx, key=key) if labels else None
    if not sel:
        return None
    # estrae il ClienteID dalla label
    cid_str = sel.split(" — ")[0].strip()
    return cid_str

def chip_css():
    return """
    <style>
      .chip {padding:2px 8px;border-radius:10px;font-size:12px;color:#fff}
      .chip-green {background:#2e7d32}
      .chip-red {background:#c62828}
      .ctr-table {border-collapse:collapse;width:100%}
      .ctr-table th,.ctr-table td {border:1px solid #ddd;padding:6px}
      .ctr-table th {background:#e3f2fd}
      .row-chiuso {background:#ffebee}
    </style>
    """

# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📊 Dashboard")

    # Prepara contratti con FineCalcolata + filtri
    ct = df_ct.copy()
    ct["__FineCalc"] = ct.apply(fine_calcolata, axis=1)
    # scade nei prossimi 6 mesi (ignorando chiusi)
    oggi = pd.Timestamp.today().normalize()
    limite = oggi + relativedelta(months=+6)
    mask = (ct["Stato"].str.lower().ne("chiuso")) & (ct["__FineCalc"].notna()) & (ct["__FineCalc"].between(oggi, limite))
    scadenze = ct.loc[mask].copy()
    # ordina e pick del primo per cliente
    scadenze = (
        scadenze.sort_values("__FineCalc")
        .groupby("ClienteID", as_index=False)
        .first()
    )
    scadenze = scadenze.merge(df_cli[["ClienteID","RagioneSociale"]], on="ClienteID", how="left")
    scadenze["Scadenza"] = scadenze["__FineCalc"].dt.strftime(DATE_FMT)

    st.markdown("### ⏳ Contratti in scadenza (entro 6 mesi)")
    st.dataframe(scadenze[["ClienteID","RagioneSociale","NumeroContratto","DescrizioneProdotto","Scadenza"]], use_container_width=True)

    # Recall > 3 mesi
    st.markdown("### ☎️ Recall più vecchi di 3 mesi")
    cli = df_cli.copy()
    cli["UltimoRecall_ts"] = pd.to_datetime(cli["UltimoRecall"], dayfirst=True, errors="coerce")
    mask_r = cli["UltimoRecall_ts"].notna() & (cli["UltimoRecall_ts"] <= oggi - relativedelta(months=+3))
    recall = cli.loc[mask_r, ["ClienteID","RagioneSociale","UltimoRecall","ProssimoRecall"]]
    st.dataframe(recall, use_container_width=True)

    # Visite > 6 mesi
    st.markdown("### 👣 Visite più vecchie di 6 mesi")
    cli["UltimaVisita_ts"] = pd.to_datetime(cli["UltimaVisita"], dayfirst=True, errors="coerce")
    mask_v = cli["UltimaVisita_ts"].notna() & (cli["UltimaVisita_ts"] <= oggi - relativedelta(months=+6))
    visite = cli.loc[mask_v, ["ClienteID","RagioneSociale","UltimaVisita","ProssimaVisita"]]
    st.dataframe(visite, use_container_width=True)

# -----------------------------------------------------------------------------
# Clienti
# -----------------------------------------------------------------------------
PIVA_RE = re.compile(r"^\d{11}$")
CAP_RE  = re.compile(r"^\d{5}$")
SDI_RE  = re.compile(r"^[A-Z0-9]{7}$", re.I)
IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", re.I)

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("👥 Clienti")

    col_new, col_sel = st.columns([1,2])
    with col_new:
        with st.expander("➕ Nuovo cliente + primo contratto"):
            with st.form("form_nuovo_cliente", clear_on_submit=True):
                st.markdown("**Anagrafica**")
                cid = st.text_input("ClienteID", value="")
                rag = st.text_input("Ragione Sociale", "")
                rif = st.text_input("Persona di riferimento", "")
                ind = st.text_input("Indirizzo", "")
                citta = st.text_input("Città", "")
                cap = st.text_input("CAP", "")
                tel = st.text_input("Telefono", "")
                ema = st.text_input("Email", "")
                piva = st.text_input("Partita IVA", "")
                iban = st.text_input("IBAN", "")
                sdi = st.text_input("SDI", "")
                nota = st.text_area("Note", "")

                st.markdown("---")
                st.markdown("**Primo contratto**")
                di = st.text_input("Data inizio (gg/mm/aaaa)", parse_import_date(date.today().strftime(DATE_FMT)))
                durata = st.text_input("Durata (es. '60 M')", "60 M")
                descr = st.text_input("Descrizione prodotto", "")
                fin = st.text_input("NOL_FIN", "")
                intr = st.text_input("NOL_INT", "")
                rata = st.text_input("TotRata", "")
                stato = st.selectbox("Stato", ["aperto","chiuso"], index=0)

                inviato = st.form_submit_button("Crea")
                if inviato:
                    # Validazioni
                    errs = []
                    if not cid.strip():
                        errs.append("ClienteID obbligatorio.")
                    if cap.strip() and not CAP_RE.match(cap.strip()):
                        errs.append("CAP non valido (5 cifre).")
                    if piva.strip() and not PIVA_RE.match(piva.strip()):
                        errs.append("P.IVA non valida (11 cifre).")
                    if iban.strip() and not IBAN_RE.match(iban.strip()):
                        errs.append("IBAN non valido.")
                    if sdi.strip() and not SDI_RE.match(sdi.strip()):
                        errs.append("SDI non valido (7 caratteri).")

                    if errs:
                        st.error(" • " + "\n • ".join(errs))
                    else:
                        # aggiunge cliente
                        r = {
                            "ClienteID":cid.strip(),
                            "RagioneSociale":rag,"PersonaRiferimento":rif,"Indirizzo":ind,"Citta":citta,"CAP":cap,
                            "Telefono":tel,"Email":ema,"PartitaIVA":piva,"IBAN":iban,"SDI":sdi,
                            "UltimoRecall":"","ProssimoRecall":"","UltimaVisita":"","ProssimaVisita":"",
                            "Note":nota
                        }
                        st.session_state._df_cli = pd.concat([st.session_state._df_cli, pd.DataFrame([r])], ignore_index=True)

                        # aggiunge contratto
                        c = {
                            "ClienteID":cid.strip(),"NumeroContratto":"","DataInizio":di,"DataFine":"",
                            "Durata":durata,"DescrizioneProdotto":descr,"NOL_FIN":fin,"NOL_INT":intr,
                            "TotRata":rata,"Stato":stato
                        }
                        st.session_state._df_ct = pd.concat([st.session_state._df_ct, pd.DataFrame([c])], ignore_index=True)
                        persist_all(st.session_state._df_cli, st.session_state._df_ct, st.session_state._df_prev)
                        st.success("Cliente e contratto creati.")

    with col_sel:
        cid = select_cliente(df_cli, key="cli_sel")
        if cid:
            cli = df_cli.loc[df_cli["ClienteID"]==cid].iloc[0].to_dict()
            st.markdown("### Anagrafica")
            st.write(cli["RagioneSociale"])
            c1,c2,c3 = st.columns(3)
            with c1:
                st.write(f"**P.IVA:** {cli.get('PartitaIVA','')}")
                st.write(f"**Indirizzo:** {cli.get('Indirizzo','')}")
                st.write(f"**CAP:** {cli.get('CAP','')}  **Città:** {cli.get('Citta','')}")
            with c2:
                st.write(f"**Telefono:** {cli.get('Telefono','')}")
                st.write(f"**Email:** {cli.get('Email','')}")
            with c3:
                st.write(f"**IBAN:** {cli.get('IBAN','')}")
                st.write(f"**SDI:** {cli.get('SDI','')}")

            st.markdown("#### Note")
            new_note = st.text_area("Note cliente", value=cli.get("Note",""), key=f"note_{cid}")
            if st.button("💾 Salva note", key=f"save_note_{cid}"):
                st.session_state._df_cli.loc[st.session_state._df_cli["ClienteID"]==cid,"Note"] = new_note
                persist_all(st.session_state._df_cli, st.session_state._df_ct, st.session_state._df_prev)
                st.success("Note aggiornate.")

# -----------------------------------------------------------------------------
# Contratti
# -----------------------------------------------------------------------------
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("🧾 Contratti (rosso = chiusi)")
    st.markdown(chip_css(), unsafe_allow_html=True)

    cid = select_cliente(df_cli, key="ctr_cli_sel")
    if not cid:
        return

    ct = df_ct.loc[df_ct["ClienteID"]==cid].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    # colonne visualizzate
    ct["__sel"] = False
    ct["__FineCalc"] = ct.apply(fine_calcolata, axis=1)
    ct["Scadenza"] = ct["__FineCalc"].apply(lambda x: "" if pd.isna(x) else x.strftime(DATE_FMT))
    ct["_st"] = ct["Stato"].apply(status_chip)

    show = ct[[
        "__sel","NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto",
        "NOL_FIN","NOL_INT","TotRata","_st","Scadenza"
    ]].rename(columns={"_st":"Stato"})

    edited = st.data_editor(
        show,
        hide_index=True,
        use_container_width=True,
        column_config={
            "__sel": st.column_config.CheckboxColumn("Seleziona"),
            "NOL_FIN": st.column_config.TextColumn("NOL_FIN"),
            "NOL_INT": st.column_config.TextColumn("NOL_INT"),
            "TotRata": st.column_config.TextColumn("TotRata"),
        },
        key=f"ctr_editor_{cid}"
    )

    # Aggiorna eventuali edit su NOL/TotRata/Date ecc.
    upd = edited.copy()
    upd = upd.rename(columns={"Stato":"_st"})  # torna allineamento
    # riversa nel df_ct originale
    for idx, row in upd.iterrows():
        ridx = ct.index[idx]
        for col in ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata"]:
            st.session_state._df_ct.at[ridx, col] = str(row[col])

    c1,c2,c3 = st.columns([1,1,2])
    with c1:
        if st.button("🔒 Chiudi selezionati"):
            sel_mask = edited["__sel"].fillna(False)
            if sel_mask.any():
                rows = ct.loc[sel_mask]
                st.session_state._df_ct.loc[rows.index, "Stato"] = "chiuso"
                persist_all(st.session_state._df_cli, st.session_state._df_ct, st.session_state._df_prev)
                st.success(f"Chiusi {sel_mask.sum()} contratti.")
            else:
                st.warning("Seleziona almeno una riga.")

    with c2:
        if st.button("🖨️ Stampa selezionati (PDF/HTML)"):
            sel_mask = edited["__sel"].fillna(False)
            rows = ct.loc[sel_mask]
            if rows.empty:
                st.warning("Seleziona almeno una riga.")
            else:
                head = f"<h3 style='text-align:center'>{df_cli.loc[df_cli['ClienteID']==cid,'RagioneSociale'].iloc[0]}</h3>"
                html = [chip_css(), head, "<table class='ctr-table'><thead><tr>"]
                cols = ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
                for c in cols: html.append(f"<th>{c}</th>")
                html.append("</tr></thead><tbody>")
                for _, r in rows.iterrows():
                    row_class = "row-chiuso" if (r.get("Stato","").lower()=="chiuso") else ""
                    html.append(f"<tr class='{row_class}'>")
                    html.append(f"<td>{r.get('NumeroContratto','')}</td>")
                    html.append(f"<td>{r.get('DataInizio','')}</td>")
                    html.append(f"<td>{r.get('DataFine','')}</td>")
                    html.append(f"<td>{r.get('Durata','')}</td>")
                    html.append(f"<td>{r.get('DescrizioneProdotto','')}</td>")
                    html.append(f"<td>{money(r.get('NOL_FIN',''))}</td>")
                    html.append(f"<td>{money(r.get('NOL_INT',''))}</td>")
                    html.append(f"<td>{money(r.get('TotRata',''))}</td>")
                    html.append(f"<td>{r.get('Stato','')}</td>")
                    html.append("</tr>")
                html.append("</tbody></table>")
                st_html("".join(html), height=320)

    with c3:
        if st.button("⬇️ Esporta selezionati (Excel)"):
            sel_mask = edited["__sel"].fillna(False)
            rows = ct.loc[sel_mask]
            if rows.empty:
                st.warning("Seleziona almeno una riga.")
            else:
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine="xlsxwriter") as xw:
                    rows_out = rows[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]].copy()
                    rows_out.to_excel(xw, index=False, sheet_name="Contratti")
                    ws = xw.sheets["Contratti"]
                    ws.write(0, 4, df_cli.loc[df_cli["ClienteID"]==cid,"RagioneSociale"].iloc[0])  # intestazione in alto
                st.download_button("Scarica Excel", data=out.getvalue(), file_name=f"contratti_{cid}.xlsx")

    st.info("Righe 'chiuso' sono evidenziate in rosso.")

# -----------------------------------------------------------------------------
# Preventivi
# -----------------------------------------------------------------------------
PLACEHOLDERS = {
    "{{RagioneSociale}}": "RagioneSociale",
    "{{ClienteID}}": "ClienteID",
    "{{Data}}": None,  # oggi
}

def page_preventivi(df_cli: pd.DataFrame, df_prev: pd.DataFrame, role: str):
    st.subheader("📝 Preventivi")

    if not TPL_DIR.exists():
        st.warning("Crea la cartella `storage/templates` e carica i tuoi .docx.")
        return

    cid = select_cliente(df_cli, key="prev_cli_sel")
    if not cid:
        return

    tpl_files = [p.name for p in TPL_DIR.glob("*.docx")]
    if not tpl_files:
        st.info("Nessun template .docx trovato in `storage/templates`.")
        return

    tpl_name = st.selectbox("Template", tpl_files, index=0)
    if st.button("🧾 Genera preventivo"):
        # Carica dati cliente
        cli = df_cli.loc[df_cli["ClienteID"]==cid].iloc[0].to_dict()
        # Crea documento
        doc = Document(TPL_DIR / tpl_name)

        def repl_in_paragraph(par):
            for ph, col in PLACEHOLDERS.items():
                val = datetime.today().strftime(DATE_FMT) if col is None else cli.get(col, "")
                if ph in par.text:
                    par.text = par.text.replace(ph, str(val))

        for p in doc.paragraphs:
            repl_in_paragraph(p)
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        repl_in_paragraph(p)

        fname = f"Preventivo_{cid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
        out_path = PREV_DIR / fname
        doc.save(out_path)

        # traccia su preventivi.csv
        rec = {"ClienteID":cid, "NomeFile":fname, "Data": datetime.now().strftime(DATE_FMT), "Template": tpl_name}
        st.session_state._df_prev = pd.concat([st.session_state._df_prev, pd.DataFrame([rec])], ignore_index=True)
        persist_all(st.session_state._df_cli, st.session_state._df_ct, st.session_state._df_prev)

        with open(out_path, "rb") as f:
            st.download_button("⬇️ Scarica preventivo", data=f.read(), file_name=fname)

    st.markdown("### Storico preventivi")
    prev_cli = df_prev.loc[df_prev["ClienteID"]==cid].copy()
    st.dataframe(prev_cli.sort_values("Data", ascending=False), use_container_width=True)

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="SHT – Gestione Clienti", layout="wide")
    st.title("SHT – Gestione Clienti")

    # Carica in sessione (scrivibile)
    if "_df_cli" not in st.session_state:
        df_cli, df_ct, df_prev = load_all()
        st.session_state._df_cli = df_cli.copy()
        st.session_state._df_ct = df_ct.copy()
        st.session_state._df_prev = df_prev.copy()

    df_cli = st.session_state._df_cli
    df_ct  = st.session_state._df_ct
    df_prev= st.session_state._df_prev

    with st.sidebar:
        page = st.radio("Navigazione", ["Dashboard","Clienti","Contratti","Preventivi"])

    if page == "Dashboard":
        page_dashboard(df_cli, df_ct, role="admin")
    elif page == "Clienti":
        page_clienti(df_cli, df_ct, role="admin")
    elif page == "Contratti":
        page_contratti(df_cli, df_ct, role="admin")
    elif page == "Preventivi":
        page_preventivi(df_cli, df_prev, role="admin")

if __name__ == "__main__":
    main()
