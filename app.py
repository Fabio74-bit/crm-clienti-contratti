from __future__ import annotations

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict

import pandas as pd
import streamlit as st
from fpdf import FPDF  # per esportazione PDF

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
# ==========================
# HTML TABLE SAFE
# ==========================

TABLE_CSS = """
<style>
.ctr-table { width:100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th,.ctr-table td { border:1px solid #d0d7de; padding:8px 10px; font-size:13px; vertical-align:top; }
.ctr-table th { background:#eef7ff; font-weight:700; }
.ctr-row-closed td { background:#ffefef; color:#8a0000; }
.ellipsis { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.smallcaps { color:#475569; font-size:12px; }
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
            sval = r.get(c, "")
            sval = "" if pd.isna(sval) else str(sval)
            sval = sval.replace("\n", "<br>")
            tds.append("<td class='ellipsis'>{}</td>".format(sval))
        rows.append("<tr{}>{}</tr>".format(trc, "".join(tds)))

    tbody = "<tbody>" + "".join(rows) + "</tbody>"
    return TABLE_CSS + "<table class='ctr-table'>{}{}</table>".format(thead, tbody)

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
# ==========================
# CLIENTI
# ==========================
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

    # riepilogo compatto
    st.markdown("### Riepilogo")
    c1, c2, c3 = st.columns(3)
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

    st.divider()
    if st.button("Vai ai contratti di questo cliente"):
        st.session_state["nav_target"] = "Contratti"
        st.session_state["selected_client_id"] = sel_id
        st.rerun()
from fpdf import FPDF

def generate_pdf_table(df: pd.DataFrame, title: str = "Contratti") -> bytes:
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 12)
            self.cell(0, 10, title, ln=1, align="C")
            self.ln(2)

    pdf = PDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_font("Arial", size=9)

    col_widths = [30, 25, 25, 20, 90, 20, 20, 25, 20]
    columns = [
        "NumeroContratto", "DataInizio", "DataFine", "Durata",
        "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
    ]

    for i, col in enumerate(columns):
        pdf.cell(col_widths[i], 8, col, border=1)
    pdf.ln()

    for _, row in df.iterrows():
        for i, col in enumerate(columns):
            text = str(row.get(col, ""))
            if col == "DescrizioneProdotto":
                pdf.multi_cell(col_widths[i], 6, text, border=1, ln=3, max_line_height=pdf.font_size)
            else:
                pdf.cell(col_widths[i], 6, text, border=1)
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1")


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
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    ragione = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0].get("RagioneSociale","")

    ct = df_ct[df_ct["ClienteID"].astype(str)==sel_id].copy()
    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    ct["DataInizio"] = to_date_series(ct["DataInizio"])
    ct["DataFine"]   = to_date_series(ct["DataFine"])

    st.markdown(f"<div style='display:flex;gap:10px;align-items:center;flex-wrap:wrap'><div style='font-size:18px;font-weight:800'>Contratti di</div> <span class='badge'>{ragione}</span></div>", unsafe_allow_html=True)
    st.divider()

    with st.expander("➕ Nuovo contratto"):
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

            if st.form_submit_button("Salva contratto", type="primary"):
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
                    df_full = load_contratti()
                    df_full = ensure_columns(df_full, CONTRATTI_COLS)
                    new["DataInizio"] = fmt_date(new["DataInizio"])
                    new["DataFine"]   = fmt_date(new["DataFine"])
                    df_full = pd.concat([df_full, pd.DataFrame([new])], ignore_index=True)
                    save_contratti(df_full)
                    st.success("Contratto inserito.")
                    st.rerun()

    st.divider()

    if ct.empty:
        st.info("Nessun contratto trovato.")
        return

    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
    disp["TotRata"]    = disp["TotRata"].apply(money)
    closed_mask = disp["Stato"].str.lower() == "chiuso"

    st.markdown("### Elenco contratti")
    st.markdown(html_table(disp), unsafe_allow_html=True)

    st.markdown("### Azioni")

    idx_to_label = {i: f"{fmt_date(r['DataInizio'])} — {r.get('NumeroContratto','')}" for i, r in ct.iterrows()}
    if idx_to_label:
        i_sel = st.selectbox("Seleziona riga", list(idx_to_label.keys()), format_func=lambda k: idx_to_label[k])
        curr = (ct.loc[i_sel,"Stato"] or "aperto").lower()
        c1, c2, c3 = st.columns(3)
        with c1:
            if curr == "chiuso":
                if st.button("Riapri contratto"):
                    df_ct.loc[i_sel, "Stato"] = "aperto"
                    save_contratti(df_ct)
                    st.success("Contratto riaperto.")
                    st.rerun()
            else:
                if st.button("Chiudi contratto"):
                    df_ct.loc[i_sel, "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.success("Contratto chiuso.")
                    st.rerun()
        with c2:
            csv = disp.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Esporta CSV (Excel)", data=csv,
                               file_name=f"contratti_cliente_{sel_id}.csv", mime="text/csv")
        with c3:
            if st.button("📄 Esporta PDF A4 Orizzontale"):
                pdf_bytes = generate_pdf_table(disp)
                st.download_button("Scarica PDF", data=pdf_bytes,
                                   file_name=f"contratti_{sel_id}.pdf", mime="application/pdf")
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

    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
    }

    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("Menu", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)

    df_cli = load_clienti()
    df_ct  = load_contratti()

    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
