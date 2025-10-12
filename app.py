# app.py — Gestionale Clienti SHT (dashboard “buona” + clienti + contratti corretti)
from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict

import pandas as pd
import streamlit as st

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

CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
]
CONTRATTI_COLS = [
    "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
]

# Durate consentite per il menu
DURATE_MESI = ["12", "24", "36", "48", "60", "72"]

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
# DASHBOARD (invariata)
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

    # prossime scadenze (entro 6 mesi) — mostro anche NOME cliente
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
            "TotRata": scad["TotRata"].apply(money),
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
        })[["Cliente","NumeroContratto","DataFine","DescrizioneProdotto","TotRata"]]
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
# CLIENTI (invariato dall’ultima buona)
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

# ==========================
# CONTRATTI (layout pulito + fix richiesti)
# ==========================

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
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])

    st.caption(f"Contratti di **{sel_label.split('—',1)[-1].strip()}**")

    # ================= Nuovo contratto (form compatto)
    with st.expander("+ Nuovo contratto", expanded=False):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            with c1:
                num = st.text_input("Numero contratto", "")
            with c2:
                din = st.text_input("Data inizio (dd/mm/aaaa)", "")
            with c3:
                dfi = st.text_input("Data fine (dd/mm/aaaa)", "")

            c4, c5, c6 = st.columns(3)
            with c4:
                durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)  # 36 predefinito
            with c5:
                nol_fin = st.text_input("NOL_FIN", "")
            with c6:
                nol_int = st.text_input("NOL_INT", "")

            desc = st.text_area("Descrizione prodotto", "", height=100)
            tot   = st.text_input("TotRata", "")

            submitted = st.form_submit_button("Crea contratto")
            if submitted:
                # parse date dd/mm/aaaa
                di = as_date(din)
                df = as_date(dfi)
                if pd.isna(di) and din.strip():
                    st.error("Formato Data inizio non valido (usa dd/mm/aaaa).")
                    st.stop()
                if pd.isna(df) and dfi.strip():
                    st.error("Formato Data fine non valido (usa dd/mm/aaaa).")
                    st.stop()

                new = {
                    "ClienteID": sel_id,
                    "NumeroContratto": num.strip(),
                    "DataInizio": di,
                    "DataFine": df,
                    "Durata": durata,
                    "DescrizioneProdotto": desc.strip(),
                    "NOL_FIN": nol_fin.strip(),
                    "NOL_INT": nol_int.strip(),
                    "TotRata": tot.strip(),
                    "Stato": "aperto",
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([new])], ignore_index=True)
                save_contratti(df_ct)
                st.success("Contratto creato.")
                st.rerun()

    # ================= Elenco contratti (tabella unica, leggibile)
    ct = df_ct[df_ct["ClienteID"].astype(str)==str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    # stato normalizzato + mask chiusi (per riga rossa)
    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    closed_mask = ct["Stato"].str.lower()=="chiuso"

    # display table con DescrizioneProdotto presente
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"]   = disp["DataFine"].apply(fmt_date)
    disp["TotRata"]    = disp["TotRata"].apply(money)

    # ORDINE COLONNE leggibile
    cols = ["NumeroContratto","DataInizio","DataFine","Durata",
            "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"]
    disp = disp[cols]

    st.markdown("### Elenco contratti")
    st.markdown(html_table(disp, closed_mask=closed_mask), unsafe_allow_html=True)

    # preview descrizione “on click” (radio)
    st.markdown("#### Anteprima descrizione (seleziona la riga)")
    opzioni = [f"{fmt_date(r['DataInizio'])} / {r['NumeroContratto'] or ''}" for _, r in ct.iterrows()]
    if opzioni:
        scelta = st.selectbox("", opzioni, label_visibility="collapsed")
        idx_sel = opzioni.index(scelta)
        riga = ct.iloc[idx_sel]
        st.info(riga.get("DescrizioneProdotto", ""))

    st.divider()

    # ================= Azioni: chiudi/riapri + esporta
    st.markdown("### Azioni")
    # selettore riga rapida
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
            # Esporta tutta la tabella in CSV (Excel la apre)
            csv = disp.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Esporta tabella (CSV/Excel)", data=csv, file_name=f"contratti_cliente_{sel_id}.csv",
                               mime="text/csv")
        with c3:
            # Esporta solo riga selezionata
            csv_row = disp.iloc[[list(ct.index).index(i_sel)]].to_csv(index=False).encode("utf-8-sig")
            st.download_button("Esporta riga selezionata", data=csv_row,
                               file_name=f"contratto_{ct.loc[i_sel,'NumeroContratto'] or 'selezione'}.csv",
                               mime="text/csv")

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
