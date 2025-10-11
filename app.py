import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
# ---------- RENDER HTML in modo compatibile con Streamlit 1.50 ----------
def show_html(html: str, *, height: int = 420):
    """Renderizza HTML/CSS in un iframe (evita artefatti di st.markdown)."""
    components.html(html, height=height, scrolling=True)

# ---------- Helper date ----------
def to_date(x):
    """Trasforma vari formati in Timestamp; dd/mm/yyyy supportato."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return pd.NaT
    if isinstance(x, pd.Timestamp):
        return x
    try:
        return pd.to_datetime(str(x).strip(), errors="coerce", dayfirst=True)
    except Exception:
        return pd.NaT

def fmt_date(d):
    return "" if (d is None or pd.isna(d)) else pd.to_datetime(d).strftime("%d/%m/%Y")

# ---------- CSS e builder tabella HTML ----------
TABLE_CSS = """
<style>
.ctr-table { width: 100%; border-collapse: collapse; table-layout: fixed; }
.ctr-table th, .ctr-table td { border: 1px solid #d0d7de; padding: 8px 10px; font-size: 13px; vertical-align: top; }
.ctr-table th { background: #e3f2fd; font-weight: 600; }
.ctr-row-closed td { background: #ffefef; color: #8a0000; }
.ellipsis { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
"""

def html_table(df: pd.DataFrame, *, closed_mask: pd.Series | None = None) -> str:
    """Restituisce l'HTML della tabella (no backslash in f-string)."""
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
            # sostituisco \n fuori dalle f-string
            sval = sval.replace("\n", "<br>")
            tds.append(f"<td class='ellipsis'>{sval}</td>")
        rows_html.append(f"<tr{tr_class}>" + "".join(tds) + "</tr>")

    tbody = "<tbody>" + "".join(rows_html) + "</tbody>"
    return TABLE_CSS + f"<table class='ctr-table'>{thead}{tbody}</table>"
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Dashboard")

    # ----------------- KPI -----------------
    today = pd.Timestamp.today().normalize()
    year_now = today.year

    df_ct_local = df_ct.copy()
    stato = df_ct_local["Stato"].fillna("aperto").str.lower()
    contratti_aperti = (stato != "chiuso").sum()
    contratti_chiusi = (stato == "chiuso").sum()
    contratti_anno = (df_ct_local["DataInizio"].apply(to_date).dt.year == year_now).sum()
    clienti_attivi = df_cli["ClienteID"].nunique()

    k1, k2, k3, k4 = st.columns(4)
    with k1: st.metric("Clienti attivi", clienti_attivi)
    with k2: st.metric("Contratti aperti", contratti_aperti)
    with k3: st.metric("Contratti chiusi", contratti_chiusi)
    with k4: st.metric(f"Contratti {year_now}", contratti_anno)

    # ----------------- Ricerca rapida cliente -----------------
    st.markdown("**Cerca cliente**")
    q = st.text_input("Digita il nome o l'ID cliente...", label_visibility="collapsed")
    if q.strip():
        filt = df_cli[
            df_cli["RagioneSociale"].str.contains(q, case=False, na=False) |
            df_cli["ClienteID"].astype(str).str.contains(q, na=False)
        ]
        if not filt.empty:
            fid = str(filt.iloc[0]["ClienteID"])
            if st.button(f"Apri scheda cliente {fid}"):
                st.session_state["nav_target"] = "Clienti"        # tua pagina Clienti
                st.session_state["selected_client_id"] = fid       # passa id selezionato
                st.rerun()

    st.markdown("---")

    # ----------------- Contratti in scadenza (entro 6 mesi) -----------------
    st.markdown("### Contratti in scadenza (entro 6 mesi)")

    ct = df_ct.copy()
    ct["DataFine"] = ct["DataFine"].apply(to_date)
    open_mask = ct["Stato"].fillna("aperto").str.lower() != "chiuso"
    within_6m = (ct["DataFine"].notna() &
                 (ct["DataFine"] >= today) &
                 (ct["DataFine"] <= today + pd.DateOffset(months=6)))
    scad = ct[open_mask & within_6m].copy()

    # prendi il primo in scadenza per cliente (quello più vicino)
    if not scad.empty:
        scad = scad.sort_values(["ClienteID", "DataFine"])
        scad = scad.groupby("ClienteID", as_index=False).first()

    disp_scad = pd.DataFrame()
    if not scad.empty:
        labels = df_cli.set_index("ClienteID")["RagioneSociale"]
        disp_scad = pd.DataFrame({
            "Cliente": scad["ClienteID"].map(labels).fillna(scad["ClienteID"].astype(str)),
            "NumeroContratto": scad["NumeroContratto"].fillna(""),
            "DescrizioneProdotto": scad["DescrizioneProdotto"].fillna(""),
            "DataFine": scad["DataFine"].apply(fmt_date),
            "TotRata": scad["TotRata"].apply(lambda x: f"{pd.to_numeric(x, errors='coerce') or 0:.2f}")
        })

    show_html(html_table(disp_scad), height=240)

    # ----------------- Ultimi recall (> 3 mesi) e Ultime visite (> 6 mesi) -----------------
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Ultimi recall (> 3 mesi)")
        cli = df_cli.copy()
        cli["UltimoRecall"] = cli["UltimoRecall"].apply(to_date)
        soglia = today - pd.DateOffset(months=3)
        r = cli[cli["UltimoRecall"].notna() & (cli["UltimoRecall"] <= soglia)]
        tab = r.loc[:, ["ClienteID", "RagioneSociale", "UltimoRecall", "ProssimoRecall"]].copy()
        tab["UltimoRecall"] = tab["UltimoRecall"].apply(fmt_date)
        tab["ProssimoRecall"] = tab["ProssimoRecall"].apply(fmt_date)
        show_html(html_table(tab), height=260)

    with c2:
        st.markdown("### Ultime visite (> 6 mesi)")
        cli = df_cli.copy()
        cli["UltimaVisita"] = cli["UltimaVisita"].apply(to_date)
        soglia_v = today - pd.DateOffset(months=6)
        v = cli[cli["UltimaVisita"].notna() & (cli["UltimaVisita"] <= soglia_v)]
        tab = v.loc[:, ["ClienteID", "RagioneSociale", "UltimaVisita", "ProssimaVisita"]].copy()
        tab["UltimaVisita"] = tab["UltimaVisita"].apply(fmt_date)
        tab["ProssimaVisita"] = tab["ProssimaVisita"].apply(fmt_date)
        show_html(html_table(tab), height=260)
