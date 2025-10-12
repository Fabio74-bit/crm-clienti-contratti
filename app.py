# app.py — Gestionale Clienti SHT
from __future__ import annotations

import html as pyhtml
from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import Tuple

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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

CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]

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
        return f"{v:.2f}"
    except Exception:
        return ""

def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols].copy()

def show_html(html: str, height: int = 420, scrolling: bool = True):
    components.html(html, height=height, scrolling=scrolling)

# ==========================
# I/O
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

# ==========================
# HTML TABLE SAFE + INTERACTIVE
# ==========================
TABLE_CSS = """
<style>
.ctr-table { width:100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th,.ctr-table td { border:1px solid #d0d7de; padding:8px 10px; font-size:13px; vertical-align:top; }
.ctr-table th { background:#eef7ff; font-weight:700; }
.ctr-row-closed td { background:#ffefef; color:#8a0000; }
.ellipsis { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.row-selected td { outline:2px solid #3b82f6; }
#descBox { margin-top:10px;padding:12px;border-radius:8px;background:#eaf2ff;min-height:20px; }
</style>
"""

def html_table(df: pd.DataFrame, *, closed_mask: pd.Series | None = None) -> str:
    if df is None or df.empty:
        return TABLE_CSS + "<div style='padding:8px;color:#666'>Nessun dato</div>"
    cols = list(df.columns)
    thead = "<thead><tr>" + "".join("<th>{}</th>".format(pyhtml.escape(c)) for c in cols) + "</tr></thead>"
    rows = []
    for i, r in df.iterrows():
        closed = (closed_mask is not None) and bool(closed_mask.loc[i])
        trc = " class='ctr-row-closed'" if closed else ""
        tds = []
        for c in cols:
            sval = r.get(c, "")
            sval = "" if pd.isna(sval) else str(sval)
            sval = sval.replace("\n", "<br>")
            tds.append("<td class='ellipsis'>{}</td>".format(pyhtml.escape(sval)))
        rows.append("<tr{}>{}</tr>".format(trc, "".join(tds)))
    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return TABLE_CSS + "<table class='ctr-table'>{}{}</table>".format(thead, tbody)

def html_table_interactive_block(df: pd.DataFrame, *, closed_mask: pd.Series | None = None, id_col_desc="DescrizioneProdotto", height=420):
    if df is None or df.empty:
        show_html(TABLE_CSS + "<div style='padding:8px;color:#666'>Nessun dato</div>", height=120)
        return
    cols = list(df.columns)
    thead = "<thead><tr>" + "".join("<th>{}</th>".format(pyhtml.escape(c)) for c in cols) + "</tr></thead>"
    rows = []
    for idx, r in df.iterrows():
        closed = (closed_mask is not None) and bool(closed_mask.loc[idx])
        tr_class = "ctr-row-closed" if closed else ""
        desc_raw = r.get(id_col_desc, "")
        desc_str = "" if pd.isna(desc_raw) else str(desc_raw)
        desc_str = desc_str.replace("\n", "\\n")
        data_attr = ' data-desc="{}"'.format(pyhtml.escape(desc_str, quote=True))
        tds = []
        for c in cols:
            sval = r.get(c, "")
            sval = "" if pd.isna(sval) else str(sval)
            sval = sval.replace("\n", "<br>")
            tds.append("<td class='ellipsis'>{}</td>".format(pyhtml.escape(sval)))
        rows.append("<tr class='{cls}'{data}>{cells}</tr>".format(cls=tr_class, data=data_attr, cells="".join(tds)))
    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    js = """
<script>
(function(){
  const table = document.getElementById('ctrTbl');
  if(!table) return;
  let lastClick = 0;
  table.addEventListener('click', function(ev){
    const tr = ev.target.closest('tr');
    if(!tr) return;
    table.querySelectorAll('tr').forEach(row => row.classList.remove('row-selected'));
    tr.classList.add('row-selected');
    const now = Date.now();
    if (now - lastClick < 300){
      const desc = tr.getAttribute('data-desc') || '';
      const box = document.getElementById('descBox');
      if (box){
        box.innerHTML = desc.replace(/\\n/g,'<br>');
        box.scrollIntoView({behavior:'smooth', block:'nearest'});
      }
    }
    lastClick = now;
  });
})();
</script>
"""
    html = TABLE_CSS + "<table id='ctrTbl' class='ctr-table'>{}{}</table><div id='descBox'></div>{}".format(thead, tbody, js)
    show_html(html, height=height, scrolling=True)

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
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
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
# CLIENTI (nuovo + modifica anagrafica)
# ==========================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti")
    # ----- nuovo cliente -----
    with st.expander("+ Nuovo cliente", expanded=False):
        with st.form("frm_new_client"):
            ragsoc = st.text_input("Ragione sociale *", "")
            ref    = st.text_input("Persona di riferimento", "")
            indir  = st.text_input("Indirizzo", "")
            cap    = st.text_input("CAP", "")
            citta  = st.text_input("Città", "")
            tel    = st.text_input("Telefono", "")
            cell   = st.text_input("Cell", "")
            mail   = st.text_input("Email", "")
            piva   = st.text_input("Partita IVA", "")
            sdi    = st.text_input("SDI", "")
            note   = st.text_area("Note", "")
            crea_ctr = st.checkbox("Crea subito anche un contratto", value=False)
            if crea_ctr:
                st.markdown("**Dati contratto iniziale**")
                num = st.text_input("Numero contratto", "")
                din = st.text_input("Data inizio (dd/mm/aaaa)", "")
                dfi = st.text_input("Data fine (dd/mm/aaaa)", "")
                durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
                desc = st.text_area("Descrizione prodotto", "", height=100)
                nol_fin = st.text_input("NOL_FIN", "")
                nol_int = st.text_input("NOL_INT", "")
                tot = st.text_input("TotRata", "")
            if st.form_submit_button("Crea cliente"):
                if not ragsoc.strip():
                    st.error("Ragione sociale obbligatoria.")
                    st.stop()
                if df_cli.empty:
                    new_id = 1
                else:
                    new_id = int(pd.to_numeric(df_cli["ClienteID"], errors="coerce").fillna(0).max()) + 1
                new_row = {
                    "ClienteID": new_id,
                    "RagioneSociale": ragsoc.strip(),
                    "PersonaRiferimento": ref.strip(),
                    "Indirizzo": indir.strip(),
                    "Citta": citta.strip(),
                    "CAP": cap.strip(),
                    "Telefono": tel.strip(),
                    "Cell": cell.strip(),
                    "Email": mail.strip(),
                    "PartitaIVA": piva.strip(),
                    "IBAN": "",
                    "SDI": sdi.strip(),
                    "UltimoRecall": "",
                    "ProssimoRecall": "",
                    "UltimaVisita": "",
                    "ProssimaVisita": "",
                    "Note": note.strip()
                }
                df_cli = pd.concat([df_cli, pd.DataFrame([new_row])], ignore_index=True)
                save_clienti(df_cli)
                if crea_ctr:
                    di = as_date(din); df_f = as_date(dfi)
                    if (din.strip() and pd.isna(di)) or (dfi.strip() and pd.isna(df_f)):
                        st.warning("Cliente creato. Il contratto non è stato creato: data non valida.")
                    else:
                        new_c = {
                            "ClienteID": str(new_id),
                            "NumeroContratto": num.strip(),
                            "DataInizio": di,
                            "DataFine": df_f,
                            "Durata": durata,
                            "DescrizioneProdotto": desc.strip(),
                            "NOL_FIN": nol_fin.strip(),
                            "NOL_INT": nol_int.strip(),
                            "TotRata": tot.strip(),
                            "Stato": "aperto",
                        }
                        df_ct = pd.concat([df_ct, pd.DataFrame([new_c])], ignore_index=True)
                        save_contratti(df_ct)
                st.success(f"Cliente creato (ID {new_id}).")
                st.session_state["selected_client_id"] = str(new_id)
                st.rerun()

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    # selezione
    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try: idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except Exception: idx = 0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    row = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0]

    # Riepilogo
    st.markdown("### Riepilogo")
    c1,c2,c3 = st.columns(3)
    with c1:
        st.markdown(f"**ClienteID:** {row.get('ClienteID','')}")
        st.markdown(f"**Ragione Sociale:** {row.get('RagioneSociale','')}")
        st.markdown(f"**Riferimento:** {row.get('PersonaRiferimento','')}")
    with c2:
        st.markdown(f"**Indirizzo:** {row.get('Indirizzo','')}")
        st.markdown(f"**CAP/Città:** {row.get('CAP','')} {row.get('Citta','')}")
        st.markdown(f"**Telefono/Cell:** {row.get('Telefono','')} / {row.get('Cell','')}")
    with c3:
        st.markdown(f"**Email:** {row.get('Email','')}")
        st.markdown(f"**P.IVA:** {row.get('PartitaIVA','')}")
        st.markdown(f"**SDI:** {row.get('SDI','')}")
    st.markdown(f"**Note:** {row.get('Note','')}")

    # ----- modifica anagrafica (come prima)
    with st.expander("Anagrafica (modificabile)", expanded=False):
        with st.form("frm_edit_client"):
            ragsoc = st.text_input("Ragione sociale", row.get("RagioneSociale",""))
           ref_val = row.get("PersonaRiferimento", "")
ref = st.text_input("Persona di riferimento", "" if pd.isna(ref_val) else str(ref_val))

            indir  = st.text_input("Indirizzo", row.get("Indirizzo",""))
            cap    = st.text_input("CAP", row.get("CAP",""))
            citta  = st.text_input("Città", row.get("Citta",""))
            tel    = st.text_input("Telefono", row.get("Telefono",""))
            cell   = st.text_input("Cell", row.get("Cell",""))
            mail   = st.text_input("Email", row.get("Email",""))
            piva   = st.text_input("Partita IVA", str(row.get("PartitaIVA","")))
            sdi    = st.text_input("SDI", row.get("SDI",""))
            note   = st.text_area("Note", row.get("Note",""))

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
                df_cli.loc[idx_row, "PersonaRiferimento"]= ref
                df_cli.loc[idx_row, "Indirizzo"]         = indir
                df_cli.loc[idx_row, "CAP"]               = cap
                df_cli.loc[idx_row, "Citta"]             = citta
                df_cli.loc[idx_row, "Telefono"]          = tel
                df_cli.loc[idx_row, "Cell"]              = cell
                df_cli.loc[idx_row, "Email"]             = mail
                df_cli.loc[idx_row, "PartitaIVA"]        = piva
                df_cli.loc[idx_row, "SDI"]               = sdi
                df_cli.loc[idx_row, "Note"]              = note
                df_cli.loc[idx_row, "UltimoRecall"]      = pd.to_datetime(ult_recall) if ult_recall else ""
                df_cli.loc[idx_row, "ProssimoRecall"]    = pd.to_datetime(pross_recall) if pross_recall else ""
                df_cli.loc[idx_row, "UltimaVisita"]      = pd.to_datetime(ult_visita) if ult_visita else ""
                df_cli.loc[idx_row, "ProssimaVisita"]    = pd.to_datetime(pross_visita) if pross_visita else ""
                save_clienti(df_cli)
                st.success("Dati cliente aggiornati.")
                st.rerun()

    st.divider()
    if st.button("Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = sel_id
        st.rerun()

# ==========================
# PDF (FPDF) — opzionale
# ==========================
def generate_pdf_table(df: pd.DataFrame, title: str = "Contratti") -> bytes | None:
    try:
        from fpdf import FPDF
    except Exception:
        return None

    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 12)
            self.cell(0, 8, title, ln=1, align="C")
            self.ln(2)

    pdf = PDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_font("Arial", size=9)

    columns = [
        "NumeroContratto", "DataInizio", "DataFine", "Durata",
        "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
    ]
    col_widths = [30, 25, 25, 20, 120, 20, 20, 25, 20]  # descrizione più larga

    # Header
    for i, col in enumerate(columns):
        pdf.cell(col_widths[i], 8, col, border=1)
    pdf.ln()

    # Rows
    for _, row in df.iterrows():
        for i, col in enumerate(columns):
            text = str(row.get(col, "") if not pd.isna(row.get(col, "")) else "")
            if col == "DescrizioneProdotto":
                # multi_cell in-place
                x = pdf.get_x(); y = pdf.get_y()
                pdf.multi_cell(col_widths[i], 6, txt=text, border=1)
                h = pdf.get_y() - y
                # riposiziona per le celle successive della stessa riga
                pdf.set_xy(x + col_widths[i], y)
                # le altre celle della riga devono allinearsi in altezza:
                for j in range(i+1, len(columns)):
                    t2 = str(row.get(columns[j], "") if not pd.isna(row.get(columns[j], "")) else "")
                    pdf.cell(col_widths[j], h, t2, border=1)
                pdf.ln()
                break
            else:
                pdf.cell(col_widths[i], 6, text, border=1)
        # se non è passata dalla descrizione (riga senza descrizione)
        if "DescrizioneProdotto" not in columns:
            pdf.ln()

    return pdf.output(dest="S").encode("latin-1")

# ==========================
# EXCEL (xlsxwriter) — fallback CSV
# ==========================
def _xlsx_bytes_from_df(df_disp: pd.DataFrame):
    try:
        import xlsxwriter  # noqa
    except Exception:
        return None
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df_disp.to_excel(writer, sheet_name="Contratti", index=False)
        wb = writer.book
        ws = writer.sheets["Contratti"]
        ws.set_landscape(); ws.set_paper(9); ws.set_margins(left=0.3, right=0.3, top=0.4, bottom=0.4)
        wrap = wb.add_format({"text_wrap": True, "valign": "top"})
        header = wb.add_format({"bold": True, "bg_color": "#EEF7FF", "border":1})
        for c, name in enumerate(df_disp.columns):
            ws.write(0, c, name, header)
            if str(name).lower().startswith("descrizione"):
                ws.set_column(c, c, 60, wrap)
            else:
                ws.set_column(c, c, 14)
    bio.seek(0)
    return bio.getvalue()

def _make_printable_html(df_disp: pd.DataFrame, titolo: str = "Contratti") -> str:
    head = """
<!doctype html><html><head><meta charset="utf-8">
<style>
@page { size: A4 landscape; margin: 10mm; }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
h2 { margin: 0 0 12px 0; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th, td { border: 1px solid #999; padding: 6px 8px; font-size: 12px; vertical-align: top; }
th { background: #eef7ff; }
.wrap { white-space: normal; word-wrap: break-word; }
</style></head><body>
"""
    thead = "<thead><tr>" + "".join("<th>{}</th>".format(pyhtml.escape(c)) for c in df_disp.columns) + "</tr></thead>"
    rows = []
    for _, r in df_disp.iterrows():
        tds = []
        for c in df_disp.columns:
            v = r.get(c, "")
            v = "" if pd.isna(v) else str(v)
            if c.lower().startswith("descrizione"):
                tds.append("<td class='wrap'>{}</td>".format(pyhtml.escape(v)))
            else:
                tds.append("<td>{}</td>".format(pyhtml.escape(v)))
        rows.append("<tr>{}</tr>".format("".join(tds)))
    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return head + "<h2>{}</h2><table>{}{}</table></body></html>".format(pyhtml.escape(titolo), thead, tbody)

# ==========================
# CONTRATTI
# ==========================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti")
    if df_cli.empty:
        st.info("Nessun cliente presente."); return

    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try: idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except Exception: idx = 0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    rag_soc = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0].get("RagioneSociale","")

    st.caption(f"Contratti di **{rag_soc}**")

    # Nuovo contratto
    with st.expander("+ Nuovo contratto", expanded=False):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            with c1: num = st.text_input("Numero contratto", "")
            with c2: din = st.text_input("Data inizio (dd/mm/aaaa)", "")
            with c3: dfi = st.text_input("Data fine (dd/mm/aaaa)", "")
            c4, c5, c6 = st.columns(3)
            with c4: durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            with c5: nol_fin = st.text_input("NOL_FIN", "")
            with c6: nol_int = st.text_input("NOL_INT", "")
            desc = st.text_area("Descrizione prodotto", "", height=110)
            tot  = st.text_input("TotRata", "")
            if st.form_submit_button("Crea contratto"):
                di = as_date(din); df_f = as_date(dfi)
                if (din.strip() and pd.isna(di)) or (dfi.strip() and pd.isna(df_f)):
                    st.error("Formato data non valido. Usa dd/mm/aaaa."); st.stop()
                new = {
                    "ClienteID": sel_id, "NumeroContratto": num.strip(),
                    "DataInizio": di, "DataFine": df_f, "Durata": durata,
                    "DescrizioneProdotto": desc.strip(),
                    "NOL_FIN": nol_fin.strip(), "NOL_INT": nol_int.strip(),
                    "TotRata": tot.strip(), "Stato": "aperto",
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([new])], ignore_index=True)
                save_contratti(df_ct)
                st.success("Contratto creato."); st.rerun()

    ct = df_ct[df_ct["ClienteID"].astype(str)==sel_id].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente."); return
    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    closed_mask = ct["Stato"].str.lower()=="chiuso"

    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
    disp["TotRata"]    = disp["TotRata"].apply(money)
    disp = disp[["NumeroContratto","DataInizio","DataFine","Durata",
                 "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]]

    st.markdown("### Elenco contratti")
    show_preview = st.checkbox("Mostra anteprima descrizione (doppio-click)", value=True)
    if show_preview:
        html_table_interactive_block(disp, closed_mask=closed_mask, height=420)
    else:
        st.markdown(html_table(disp, closed_mask=closed_mask), unsafe_allow_html=True)

    st.divider()
    st.markdown("### Azioni")
    idx_to_label = {i: f"{fmt_date(r['DataInizio'])} — {r.get('NumeroContratto','')}" for i, r in ct.iterrows()}
    if idx_to_label:
        i_sel = st.selectbox("Seleziona riga", list(idx_to_label.keys()), format_func=lambda k: idx_to_label[k])
        curr = (ct.loc[i_sel,"Stato"] or "aperto").lower()
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if curr == "chiuso":
                if st.button("Riapri contratto"):
                    df_ct.loc[i_sel,"Stato"] = "aperto"; save_contratti(df_ct); st.success("Riaperto."); st.rerun()
            else:
                if st.button("Chiudi contratto"):
                    df_ct.loc[i_sel,"Stato"] = "chiuso"; save_contratti(df_ct); st.success("Chiuso."); st.rerun()
        with c2:
            xlsx_bytes = _xlsx_bytes_from_df(disp)
            if xlsx_bytes:
                st.download_button("Esporta Excel (A4 orizz.)", data=xlsx_bytes,
                                   file_name=f"contratti_{rag_soc}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                csv = disp.to_csv(index=False).encode("utf-8-sig")
                st.download_button("Esporta CSV", data=csv,
                                   file_name=f"contratti_{rag_soc}.csv", mime="text/csv")
        with c3:
            # PDF con FPDF (se disponibile), altrimenti HTML da stampare
            pdf_bytes = generate_pdf_table(disp, f"Contratti — {rag_soc}")
            if pdf_bytes:
                st.download_button("Scarica PDF (FPDF)", data=pdf_bytes,
                                   file_name=f"contratti_{rag_soc}.pdf", mime="application/pdf")
            else:
                printable_html = _make_printable_html(disp, f"Contratti — {rag_soc}")
                st.download_button("Scarica PDF (HTML A4)", data=printable_html.encode("utf-8"),
                                   file_name=f"contratti_{rag_soc}.html", mime="text/html")
        with c4:
            st.caption("Suggerimento: usa il doppio-click sulla riga per leggere tutta la descrizione.")

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
