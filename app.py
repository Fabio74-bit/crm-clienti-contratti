# app.py — SHT – Gestione Clienti (Streamlit 1.50 compatibile)

from __future__ import annotations
import io
from pathlib import Path
from datetime import datetime
from typing import Tuple, Dict

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ======================================================================================
# ---------------------------------- CONFIG & PATHS ------------------------------------
# ======================================================================================

APP_TITLE = "SHT – Gestione Clienti"
STORAGE_DIR = Path("storage")
CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"

STORAGE_DIR.mkdir(exist_ok=True)

# ======================================================================================
# ---------------------------------- HTML UTILS / CSS ----------------------------------
# ======================================================================================

def show_html(html: str, *, height: int = 420):
    """Renderizza HTML/CSS in un iframe (evita i limiti di st.markdown su 1.50)."""
    components.html(html, height=height, scrolling=True)

TABLE_CSS = """
<style>
.ctr-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th, .ctr-table td {
  border: 1px solid #d0d7de; padding: 8px 10px; font-size: 13px; vertical-align: top;
}
.ctr-table th { background: #e3f2fd; font-weight: 700; }
.ctr-row-closed td { background: #ffefef; color: #8a0000; }
.ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
"""

KPI_CSS = """
<style>
.kpi {border-radius:16px; padding:14px 16px; border:1px solid #e6eefb;
      box-shadow:0 1px 2px rgba(0,0,0,.04) inset; font-size:14px;}
.kpi .v {font-size:32px; font-weight:800; line-height:1; margin-top:6px;}
.kpi.green  {background:#e8f5e9; border-color:#c8e6c9;}
.kpi.red    {background:#ffebee; border-color:#ffcdd2;}
.kpi.yellow {background:#fff8e1; border-color:#ffecb3;}
.kpi.blue   {background:#e3f2fd; border-color:#bbdefb;}
.badge {display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px}
.badge.red {background:#ffebee; color:#a30000; border:1px solid #ffcdd2}
.badge.green {background:#e8f5e9; color:#0a6b2d; border:1px solid #c8e6c9}
</style>
"""

# ======================================================================================
# ------------------------------------- DATE HELPERS -----------------------------------
# ======================================================================================

def to_date_series(s: pd.Series) -> pd.Series:
    """
    Converte una Series in Timestamp (dayfirst=True), ripulendo '', 'NaT', 'nan' -> NaT
    """
    s = s.astype(str).str.strip()
    s = s.replace({"": None, "NaT": None, "nan": None, "None": None})
    return pd.to_datetime(s, errors="coerce", dayfirst=True)

def fmt_date(d):
    """
    Ritorna dd/mm/yyyy oppure stringa vuota. Gestisce NaT, 'NaT', '', None, ecc.
    """
    try:
        if d is None:
            return ""
        if isinstance(d, pd.Timestamp):
            return "" if pd.isna(d) else d.strftime("%d/%m/%Y")
        d2 = pd.to_datetime(str(d).strip() or None, errors="coerce", dayfirst=True)
        return "" if pd.isna(d2) else d2.strftime("%d/%m/%Y")
    except Exception:
        return ""

# ======================================================================================
# -------------------------------------- STORAGE LAYER ---------------------------------
# ======================================================================================

def ensure_csv(file: Path, columns: list[str]):
    if not file.exists():
        df = pd.DataFrame(columns=columns)
        df.to_csv(file, index=False, encoding="utf-8")

def load_clienti() -> pd.DataFrame:
    cols = [
        "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
        "Telefono", "Email", "PartitaIVA", "IBAN", "SDI",
        "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"
    ]
    ensure_csv(CLIENTI_CSV, cols)
    df = pd.read_csv(CLIENTI_CSV, dtype=str).fillna("")
    # normalizza ID numerico/string
    if "ClienteID" in df.columns:
        # manteniamo tutto stringa per coerenza UI
        df["ClienteID"] = df["ClienteID"].astype(str)
    return df

def save_clienti(df: pd.DataFrame):
    df.to_csv(CLIENTI_CSV, index=False, encoding="utf-8")

def load_contratti() -> pd.DataFrame:
    cols = [
        "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
        "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
    ]
    ensure_csv(CONTRATTI_CSV, cols)
    df = pd.read_csv(CONTRATTI_CSV, dtype=str).fillna("")
    # salva TotRata numerico “pulito” per calcoli
    df["TotRata"] = pd.to_numeric(df["TotRata"], errors="coerce")
    return df

def save_contratti(df: pd.DataFrame):
    df_out = df.copy()
    # quando salviamo, scriviamo TotRata numerico (vuoto-> '')
    df_out["TotRata"] = df_out["TotRata"].apply(lambda x: "" if pd.isna(x) else x)
    df_out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8")

def load_preventivi() -> pd.DataFrame:
    cols = ["ClienteID", "Numero", "Data", "Titolo", "File"]
    ensure_csv(PREVENTIVI_CSV, cols)
    return pd.read_csv(PREVENTIVI_CSV, dtype=str).fillna("")

def save_preventivi(df: pd.DataFrame):
    df.to_csv(PREVENTIVI_CSV, index=False, encoding="utf-8")

# ======================================================================================
# -------------------------------- TABLE HTML RENDER -----------------------------------
# ======================================================================================

def html_table(df: pd.DataFrame, *, closed_mask: pd.Series | None = None) -> str:
    """Restituisce l'HTML della tabella con righe chiuse evidenziate."""
    if df is None or df.empty:
        return TABLE_CSS + "<div style='padding:8px;color:#666'>Nessun dato</div>"

    cols = list(df.columns)
    thead = "<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>"

    rows_html = []
    for i, row in df.iterrows():
        tr_class = " class='ctr-row-closed'" if (closed_mask is not None and bool(closed_mask.loc[i])) else ""
        tds = []
        for c in cols:
            val = row.get(c, "")
            sval = "" if pd.isna(val) else str(val)
            sval = sval.replace("\n", "<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows_html.append(f"<tr{tr_class}>" + "".join(tds) + "</tr>")

    tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
    return TABLE_CSS + f"<table class='ctr-table'>{thead}{tbody}</table>"

# ======================================================================================
# ----------------------------------------- LOGIN --------------------------------------
# ======================================================================================

def secrets_users() -> Dict[str, Dict[str, str]]:
    # struttura attesa:
    # [auth.users.fabio]
    # password="admin"
    # role="admin"
    try:
        users = st.secrets["auth"]["users"]
        # st.secrets in 1.50 non supporta dict nested diretto? gestiamo flatten:
        # se è Secretdict -> convertiamo
        out = {}
        for k in users:
            out[k] = {"password": users[k]["password"], "role": users[k].get("role", "viewer")}
        return out
    except Exception:
        # fallback
        return {
            "fabio": {"password": "admin", "role": "admin"}
        }

def login_box() -> Tuple[str | None, str | None]:
    st.title("SHT – Gestione Clienti")
    st.subheader("Login")

    users = secrets_users()
    u = st.text_input("Utente", value="fabio")
    p = st.text_input("Password", type="password", value="admin")
    ok = st.button("Entra")

    if ok:
        if u in users and users[u]["password"] == p:
            st.session_state["user"] = u
            st.session_state["role"] = users[u]["role"]
            st.success(f"Benvenuto, {u}!")
            st.rerun()
        else:
            st.error("Credenziali non valide.")
    return None, None

def require_login() -> Tuple[str, str]:
    if "user" in st.session_state and "role" in st.session_state:
        return st.session_state["user"], st.session_state["role"]
    else:
        login_box()
        st.stop()

# ======================================================================================
# --------------------------------------- DASHBOARD ------------------------------------
# ======================================================================================

def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")
    st.markdown(KPI_CSS, unsafe_allow_html=True)

    today = pd.Timestamp.today().normalize()
    year_now = today.year

    ct = df_ct.copy()
    ct["Stato"] = ct["Stato"].fillna("").str.lower()
    di = to_date_series(ct["DataInizio"])
    contratti_anno = (di.dt.year == year_now).sum()
    contratti_aperti = (ct["Stato"] != "chiuso").sum()
    contratti_chiusi = (ct["Stato"] == "chiuso").sum()
    clienti_attivi = df_cli["ClienteID"].astype(str).nunique()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="kpi blue">Clienti attivi<div class="v">{}</div></div>'.format(clienti_attivi),
                    unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="kpi green">Contratti aperti<div class="v">{}</div></div>'.format(contratti_aperti),
                    unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="kpi red">Contratti chiusi<div class="v">{}</div></div>'.format(contratti_chiusi),
                    unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="kpi yellow">Contratti {y}<div class="v">{n}</div></div>'.format(y=year_now, n=contratti_anno),
                    unsafe_allow_html=True)

    # Ricerca rapida cliente
    st.markdown("**Cerca cliente**")
    q = st.text_input("Digita il nome o l'ID cliente...", label_visibility="collapsed")
    if q.strip():
        filt = df_cli[
            df_cli["RagioneSociale"].astype(str).str.contains(q, case=False, na=False) |
            df_cli["ClienteID"].astype(str).str.contains(q, na=False)
        ]
        if not filt.empty:
            fid = str(filt.iloc[0]["ClienteID"])
            if st.button(f"Apri scheda cliente {fid}"):
                st.session_state["nav_target"] = "Clienti"
                st.session_state["selected_client_id"] = fid
                st.rerun()

    st.markdown("---")

    # Contratti in scadenza entro 6 mesi
    st.markdown("### Contratti in scadenza (entro 6 mesi)")
    ct2 = df_ct.copy()
    ct2["DataFine"] = to_date_series(ct2["DataFine"])
    ct2["Stato"] = ct2["Stato"].fillna("").str.lower()
    open_mask = ct2["Stato"] != "chiuso"
    within_6m = (ct2["DataFine"].notna() &
                 (ct2["DataFine"] >= today) &
                 (ct2["DataFine"] <= today + pd.DateOffset(months=6)))
    scad = ct2[open_mask & within_6m].copy()
    if not scad.empty:
        scad = scad.sort_values(["ClienteID", "DataFine"])
        scad = scad.groupby("ClienteID", as_index=False).first()

    disp_scad = pd.DataFrame()
    if not scad.empty:
        labels = df_cli.set_index(df_cli["ClienteID"].astype(str))["RagioneSociale"]
        disp_scad = pd.DataFrame({
            "Cliente": scad["ClienteID"].astype(str).map(labels).fillna(scad["ClienteID"].astype(str)),
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "DataFine": scad["DataFine"].apply(fmt_date),
            "TotRata": pd.to_numeric(scad["TotRata"], errors="coerce").fillna(0).map(lambda x: f"{x:.2f}")
        })
    show_html(html_table(disp_scad), height=240)

    # Ultimi recall (> 3 mesi) e Ultime visite (> 6 mesi)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecall"] = to_date_series(cli["UltimoRecall"])
        cli["ProssimoRecall"] = to_date_series(cli["ProssimoRecall"])
        soglia = today - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall"].notna() & (cli["UltimoRecall"] <= soglia)]
        tab = r.loc[:, ["ClienteID", "RagioneSociale", "UltimoRecall", "ProssimoRecall"]].copy()
        tab["UltimoRecall"] = tab["UltimoRecall"].apply(fmt_date)
        tab["ProssimoRecall"] = tab["ProssimoRecall"].apply(fmt_date)
        show_html(html_table(tab), height=260)

    with c2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisita"] = to_date_series(cli["UltimaVisita"])
        cli["ProssimaVisita"] = to_date_series(cli["ProssimaVisita"])
        soglia_v = today - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita"].notna() & (cli["UltimaVisita"] <= soglia_v)]
        tab = v.loc[:, ["ClienteID", "RagioneSociale", "UltimaVisita", "ProssimaVisita"]].copy()
        tab["UltimaVisita"] = tab["UltimaVisita"].apply(fmt_date)
        tab["ProssimaVisita"] = tab["ProssimaVisita"].apply(fmt_date)
        show_html(html_table(tab), height=260)

# ======================================================================================
# ----------------------------------------- CLIENTI ------------------------------------
# ======================================================================================

def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Clienti 👥")

    # Selezione cliente
    opts = df_cli.assign(label=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"].astype(str))
    default_idx = 0
    if "selected_client_id" in st.session_state:
        try:
            default_idx = int(opts.index[opts["ClienteID"].astype(str) == str(st.session_state["selected_client_id"])][0])
        except Exception:
            default_idx = 0
    label_sel = st.selectbox("Cliente", opts["label"].tolist(), index=default_idx if len(opts)>0 else 0)
    if len(opts)==0:
        st.info("Nessun cliente. Usa il form sotto per crearne uno.")
        cliente = None
    else:
        sel_id = opts.iloc[[opts["label"].tolist().index(label_sel)]]["ClienteID"].iloc[0]
        st.session_state["selected_client_id"] = str(sel_id)
        cliente = df_cli[df_cli["ClienteID"].astype(str) == str(sel_id)].iloc[0].to_dict()

    # Card anagrafica + modifica "Persona di riferimento"
    if cliente:
        st.markdown("### Anagrafica")
        c1, c2, c3 = st.columns([1.2, 1, 1])
        with c1:
            st.write("**Ragione Sociale:**", cliente.get("RagioneSociale",""))
            st.write("**Indirizzo:**", cliente.get("Indirizzo",""), cliente.get("CAP",""), cliente.get("Citta",""))
            st.write("**Telefono:**", cliente.get("Telefono",""))
            st.write("**Email:**", cliente.get("Email",""))
        with c2:
            st.write("**P.IVA:**", cliente.get("PartitaIVA",""))
            st.write("**IBAN:**", cliente.get("IBAN",""))
            st.write("**SDI:**", cliente.get("SDI",""))
        with c3:
            new_ref = st.text_input("Persona di riferimento", value=cliente.get("PersonaRiferimento",""))
            if st.button("Salva"):
                df_cli.loc[df_cli["ClienteID"].astype(str)==str(cliente["ClienteID"]), "PersonaRiferimento"] = new_ref
                save_clienti(df_cli)
                st.success("Salvato.")
                st.rerun()

        st.markdown(
            f'<span class="badge green">Cliente {cliente["ClienteID"]}</span> '
            f'<span class="badge">Contratti: {(df_ct["ClienteID"].astype(str)==str(cliente["ClienteID"])).sum()}</span>',
            unsafe_allow_html=True
        )

        # Pulsante per andare ai contratti del cliente
        if st.button("➡ Vai alla gestione contratti di questo cliente"):
            st.session_state["nav_target"] = "Contratti"
            st.session_state["selected_client_id"] = str(cliente["ClienteID"])
            st.rerun()

    st.markdown("---")

    # Wizard: Nuovo cliente + primo contratto
    st.markdown("### ➕ Nuovo cliente + primo contratto")
    with st.form("nuovo_cliente_form"):
        col1, col2 = st.columns(2)
        with col1:
            rs = st.text_input("Ragione sociale *")
            ref = st.text_input("Persona di riferimento")
            indir = st.text_input("Indirizzo")
            citta = st.text_input("Città")
            cap = st.text_input("CAP")
            tel = st.text_input("Telefono")
            email = st.text_input("Email")
        with col2:
            piva = st.text_input("Partita IVA")
            iban = st.text_input("IBAN")
            sdi = st.text_input("SDI")
            # Primo contratto
            numero = st.text_input("Numero contratto (opz.)")
            dinizio = st.text_input("Data inizio (gg/mm/aaaa)")
            durata = st.selectbox("Durata (mesi)", ["", "12", "24", "36", "48", "60", "72"])
            dfine = st.text_input("Data fine (gg/mm/aaaa)")
            descr = st.text_area("Descrizione prodotto")
            tot = st.text_input("TotRata (numero)")

        invia = st.form_submit_button("Crea cliente e contratto")
        if invia:
            if not rs.strip():
                st.warning("Ragione sociale obbligatoria.")
            else:
                # genera ClienteID progressivo
                if df_cli.empty:
                    new_id = "1"
                else:
                    new_id = str(int(pd.to_numeric(df_cli["ClienteID"], errors="coerce").fillna(0).max()) + 1)
                row = {
                    "ClienteID": new_id, "RagioneSociale": rs, "PersonaRiferimento": ref,
                    "Indirizzo": indir, "Citta": citta, "CAP": cap, "Telefono": tel, "Email": email,
                    "PartitaIVA": piva, "IBAN": iban, "SDI": sdi,
                    "UltimoRecall": "", "ProssimoRecall": "", "UltimaVisita": "", "ProssimaVisita": "", "Note": ""
                }
                df_cli = pd.concat([df_cli, pd.DataFrame([row])], ignore_index=True)
                save_clienti(df_cli)

                if any([numero, dinizio, dfine, durata, descr, tot]):
                    crow = {
                        "ClienteID": new_id,
                        "NumeroContratto": numero,
                        "DataInizio": dinizio,
                        "DataFine": dfine,
                        "Durata": durata,
                        "DescrizioneProdotto": descr,
                        "NOL_FIN": "", "NOL_INT": "",
                        "TotRata": pd.to_numeric(tot.replace(",", ".") if tot else "", errors="coerce"),
                        "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([crow])], ignore_index=True)
                    save_contratti(df_ct)
                st.success("Cliente e contratto creati.")
                st.session_state["selected_client_id"] = new_id
                st.rerun()

# ======================================================================================
# ---------------------------------------- CONTRATTI -----------------------------------
# ======================================================================================

def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti (rosso = chiusi) 🧾")

    # filtro cliente
    opts = df_cli.assign(label=lambda d: d["ClienteID"].astype(str) + " — " + d["RagioneSociale"].astype(str))
    default_idx = 0
    if "selected_client_id" in st.session_state:
        try:
            default_idx = int(opts.index[opts["ClienteID"].astype(str) == str(st.session_state["selected_client_id"])][0])
        except Exception:
            default_idx = 0
    label_sel = st.selectbox("Cliente", opts["label"].tolist(), index=default_idx if len(opts)>0 else 0)
    if len(opts)==0:
        st.info("Nessun cliente.")
        return
    sel_id = opts.iloc[[opts["label"].tolist().index(label_sel)]]["ClienteID"].iloc[0]
    st.session_state["selected_client_id"] = str(sel_id)

    # subset contratti cliente
    ct_cli = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    ct_cli.reset_index(drop=True, inplace=True)

    # maschera righe chiuse
    closed_mask = ct_cli["Stato"].fillna("").str.lower() == "chiuso"

    # riga: selezione + bottone chiudi
    st.markdown("#### Selezione/chiusura righe")
    if ct_cli.empty:
        st.info("Nessun contratto per questo cliente. Usa la pagina Clienti per crearne uno.")
    else:
        sel_flags = []
        for i, r in ct_cli.iterrows():
            c1, c2, c3 = st.columns([0.1, 0.05, 0.85])
            with c1:
                sel = st.checkbox("", key=f"chk_{i}")
                sel_flags.append(sel)
            with c2:
                st.write("ℹ️")
            with c3:
                dd = f"dal {fmt_date(r['DataInizio'])} al {fmt_date(r['DataFine'])}"
                st.write(f"— {r['DescrizioneProdotto'] or ''}  \n*{dd}*")
                if st.button("Chiudi", key=f"close_{i}"):
                    df_ct.loc[
                        (df_ct["ClienteID"].astype(str)==str(sel_id)) &
                        (df_ct["NumeroContratto"].astype(str)==str(r["NumeroContratto"]))
                        , "Stato"
                    ] = "chiuso"
                    save_contratti(df_ct)
                    st.success("Contratto chiuso.")
                    st.rerun()

    st.markdown("---")

    # Tabella completa “ben definita”
    st.markdown("### Tabella completa")
    disp = ct_cli.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp["TotRata"] = pd.to_numeric(disp["TotRata"], errors="coerce").fillna(0).map(lambda x: f"{x:.2f}")
    show_html(html_table(disp, closed_mask=closed_mask), height=360)

    st.markdown("### Esporta / Stampa selezione")
    export_sel = st.button("Esporta selezione in Excel")
    if export_sel and not ct_cli.empty:
        # usa i checkbox creati sopra
        chosen_idx = [i for i in range(len(ct_cli)) if st.session_state.get(f"chk_{i}", False)]
        if not chosen_idx:
            st.warning("Nessuna riga selezionata.")
        else:
            out = ct_cli.iloc[chosen_idx].copy()
            out["DataInizio"] = out["DataInizio"].apply(fmt_date)
            out["DataFine"] = out["DataFine"].apply(fmt_date)

            # intestazione cliente in prima riga
            cli = df_cli[df_cli["ClienteID"].astype(str)==str(sel_id)].iloc[0]
            header = pd.DataFrame([[f"{cli['ClienteID']} — {cli['RagioneSociale']}"]], columns=["Cliente"])
            # writer in memoria
            with pd.ExcelWriter("selezione.xlsx", engine="xlsxwriter") as writer:
                header.to_excel(writer, sheet_name="Selezione", index=False)
                out.to_excel(writer, sheet_name="Selezione", index=False, startrow=2)
                writer.book.close()
            with open("selezione.xlsx","rb") as f:
                st.download_button("Scarica Excel", f, file_name="selezione.xlsx")

            st.info("La stampa PDF può essere fatta dall'Excel o con la stampa del browser.")

# ======================================================================================
# ------------------------------------------- MAIN -------------------------------------
# ======================================================================================

PAGES = {
    "Dashboard": page_dashboard,
    "Clienti": page_clienti,
    "Contratti": page_contratti,
}

def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    user, role = require_login()

    # carica dataset
    df_cli = load_clienti()
    df_ct = load_contratti()

    # sidebar
    st.sidebar.title(APP_TITLE)
    page = st.sidebar.radio("Navigazione", list(PAGES.keys()), index=0)

    # routing manuale (per pulsanti “vai a …”)
    if "nav_target" in st.session_state:
        page = st.session_state.pop("nav_target")

    # render pagina
    page_fn = PAGES[page]
    page_fn(df_cli, df_ct, role)

    st.sidebar.markdown("---")
    if st.sidebar.button("Logout"):
        for k in ("user","role","selected_client_id"):
            st.session_state.pop(k, None)
        st.experimental_rerun()

if __name__ == "__main__":
    main()
