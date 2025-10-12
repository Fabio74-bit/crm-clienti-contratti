# app.py — Gestionale Clienti SHT (dashboard “buona” + clienti + contratti NUOVO LAYOUT)
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Tuple, Dict, List

import pandas as pd
import streamlit as st
from docx import Document
import streamlit.components.v1 as components

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

# Cartella esterna (es. OneDrive). Se non impostata → usa STORAGE_DIR/preventivi
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
    "Offerta – Centralino": "Offerta_Centralino.docx",
    "Offerta – Varie":      "Offerta_Varie.docx",
    "Offerta – A3":         "Offerte_A3.docx",
    "Offerta – A4":         "Offerte_A4.docx",
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
.btn{border:1px solid var(--bd);border-radius:10px;padding:8px 12px;background:#fff;cursor:pointer}
.btn.primary{border-color:var(--b);box-shadow:0 0 0 2px #e0f2fe inset}
.hdr{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.hdr .title{font-size:18px;font-weight:800}
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
    """Tabella HTML + JS: doppio-click riga → mostra descrizione completa."""
    table_html = html_table(disp, closed_mask=closed_mask)

    # Prepara mappa idx -> descrizione (escape line-break fuori da f-string)
    mapping = {int(i): ("" if pd.isna(v) else str(v)).replace("\n", "<br>") for i, v in desc_series.items()}
    # Serializzo JS-safe
    items_js = ",".join(["{}: `{}`".format(k, mapping[k].replace("`","\\`")) for k in mapping])

    html = """
{table}
<div class="preview" id="descBox">Doppio-click su una riga per vedere la descrizione completa.</div>
<script>
const DESCR = {{{items}}};
const tbl = document.getElementById('tbl');
const box = document.getElementById('descBox');
if (tbl){
  tbl.addEventListener('dblclick', (e)=>{
    let tr = e.target.closest('tr');
    if (!tr) return;
    let key = tr.getAttribute('data-row');
    if (key in DESCR){
      box.innerHTML = DESCR[key] || "(nessuna descrizione)";
      box.scrollIntoView({behavior:'smooth', block:'nearest'});
    }
  });
}
</script>
""".format(table=table_html, items=items_js)

    components.html(html, height=460, scrolling=True)

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
# PAGINE (Dashboard / Clienti restano come nella tua versione stabile)
# ==========================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    # --- invariata rispetto alla versione buona ---
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
<div class="hdr"><div class="title"> </div></div>
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

# ----------- (pagina clienti invariata rispetto alla tua versione stabile precedente) -----------
# Per brevità la ometto qui: usa la tua versione “perfetta”.
# Se preferisci, puoi incollare qui la versione che ti ho dato nel messaggio precedente
# senza modifiche.

# ==========================
# CONTRATTI — NUOVO LAYOUT
# ==========================
def _export_table_bytes(df: pd.DataFrame, base_name: str) -> Tuple[bytes, str, str]:
    """Tenta XLSX (xlsxwriter), altrimenti CSV."""
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

    # selezione cliente (manteniamo eventuale selezione da altre pagine)
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
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        # comunque consenti inserimento nuovo
    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    ct["DataInizio"] = to_date_series(ct["DataInizio"])
    ct["DataFine"]   = to_date_series(ct["DataFine"])

    st.markdown(BASE_CSS, unsafe_allow_html=True)
    st.markdown(f"<div class='hdr'><div class='title'>Contratti di <span class='badge'>{ragione}</span></div></div>", unsafe_allow_html=True)

    # ====== BLOCCO AZIONI ======
    with st.container():
        c1, c2 = st.columns([0.50, 0.50])

        # --- Nuovo contratto ---
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

                    ok = st.form_submit_button("Salva contratto", type="primary", use_container_width=True)
                    if ok:
                        # validazioni semplici
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
                            df_ct = pd.read_csv(CONTRATTI_CSV, dtype=str, sep=",").fillna("") if CONTRATTI_CSV.exists() else pd.DataFrame(columns=CONTRATTI_COLS)
                            df_ct = ensure_columns(df_ct, CONTRATTI_COLS)
                            # coerci date a ISO per salvataggio
                            def _to_iso(x):
                                return "" if x=="" or pd.isna(x) else pd.to_datetime(x).strftime("%Y-%m-%d")
                            new_row = new.copy()
                            new_row["DataInizio"] = _to_iso(new_row["DataInizio"])
                            new_row["DataFine"]   = _to_iso(new_row["DataFine"])
                            df_ct = pd.concat([df_ct, pd.DataFrame([new_row])], ignore_index=True)
                            save_contratti(df_ct)
                            st.success("Contratto inserito.")
                            st.rerun()

        # --- Export / Stampa / Chiudi-Riapri ---
        with c2:
            with st.expander("⤓ Esporta / Stampa / Stato", expanded=False):
                all_disp = ct.copy()
                all_disp["DataInizio"] = all_disp["DataInizio"].apply(fmt_date)
                all_disp["DataFine"]   = all_disp["DataFine"].apply(fmt_date)
                all_disp["TotRata"]    = all_disp["TotRata"].apply(money)

                # selezione con multiselect per meno confusione
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

    # ====== TABELLA UNICA + DOPPIO-CLICK DESCRIZIONE ======
    disp = ct.copy()
    disp = disp[["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]]
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
    disp["TotRata"]    = disp["TotRata"].apply(money)
    closed_mask = ct["Stato"].str.lower()=="chiuso"

    st.markdown("### Elenco contratti")
    html_table_interactive(disp.drop(columns=["DescrizioneProdotto"]),
                           desc_series=ct["DescrizioneProdotto"],
                           closed_mask=closed_mask)

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

    PAGES = {
        "Dashboard": page_dashboard,
        # QUI inserisci la tua page_clienti “perfetta” (non la riscrivo per brevità)
        # Per continuare a usare quella già funzionante, assicurati che la funzione
        # page_clienti sia definita nel file (come nel tuo stato attuale).
        "Contratti": page_contratti
    }

    # se non definita (perché stai incollando questo file), crea una finta page_clienti minima
    if "page_clienti" not in globals():
        def page_clienti(df_cli, df_ct, role):
            st.info("Pagina Clienti non caricata in questo snippet. Usa la versione già funzionante.")
        PAGES["Clienti"] = page_clienti
    else:
        PAGES["Clienti"] = page_clienti  # type: ignore

    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("Menu", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)

    df_cli = load_clienti()
    df_ct  = load_contratti()
    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
