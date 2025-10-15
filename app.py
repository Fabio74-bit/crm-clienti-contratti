from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from docx import Document
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

# =========================================================
# CONFIGURAZIONE BASE
# =========================================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV = STORAGE_DIR / "preventivi.csv"

DURATE_MESI = ["12", "24", "36", "48", "60"]

# =========================================================
# FUNZIONI DI UTILITÀ
# =========================================================
def fmt_date(d):
    if pd.isna(d) or d == "":
        return ""
    try:
        return pd.to_datetime(d).strftime("%d/%m/%Y")
    except Exception:
        return str(d)

def money(x):
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        return f"{v:,.2f} €"
    except Exception:
        return ""

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]

# =========================================================
# I/O DATI
# =========================================================
def load_clienti():
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=["ClienteID", "RagioneSociale", "Citta", "Telefono", "Email", "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita", "Note"])
    df = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_clienti(df):
    out = df.copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=["ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata", "DescrizioneProdotto", "TotRata", "Stato"])
    df = pd.read_csv(CONTRATTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["DataInizio", "DataFine"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_contratti(df):
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# =========================================================
# LOGIN
# =========================================================
def do_login():
    users = st.secrets.get("auth", {}).get("users", {})
    if not users:
        return ("ospite", "viewer")

    if "auth_user" in st.session_state:
        return st.session_state["auth_user"], st.session_state["auth_role"]

    st.markdown(
        f"""
        <div style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:90vh;text-align:center;'>
            <img src="{LOGO_URL}" width="230" style="margin-bottom:30px;">
            <h2>🔐 Accesso al Gestionale SHT</h2>
            <p style='color:grey;'>Inserisci le tue credenziali per continuare</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    username = st.text_input("👤 Utente")
    password = st.text_input("🔒 Password", type="password")

    if st.button("Entra", use_container_width=True):
        if username in users and password == users[username].get("password"):
            st.session_state["auth_user"] = username
            st.session_state["auth_role"] = users[username].get("role", "viewer")
            st.rerun()
        else:
            st.error("❌ Credenziali errate.")

    st.stop()

# =========================================================
# DASHBOARD
# =========================================================
def page_dashboard(df_cli, df_ct, role):
    now = pd.Timestamp.now().normalize()
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:20px;">
            <img src="{LOGO_URL}" width="120">
            <h1 style="margin-top:15px;">SHT – CRM Dashboard</h1>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<hr>", unsafe_allow_html=True)
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()

    kpi = [
        ("Clienti", len(df_cli), "👥", "#2196F3"),
        ("Contratti Attivi", (stato != "chiuso").sum(), "📄", "#009688"),
        ("Contratti Chiusi", (stato == "chiuso").sum(), "❌", "#E53935"),
        ("Nuovi Anno", len(df_ct[df_ct["DataInizio"].dt.year == now.year]), "🆕", "#FFC107")
    ]
    c1, c2, c3, c4 = st.columns(4)
    for c, (lbl, val, ico, bg) in zip([c1, c2, c3, c4], kpi):
        c.markdown(f"""
        <div style="background:{bg};color:white;border-radius:10px;padding:14px;text-align:center;">
            <div style="font-size:30px;">{ico}</div>
            <div style="font-size:20px;font-weight:700;">{val}</div>
            <div>{lbl}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("### 📅 Contratti in Scadenza (entro 6 mesi)")
    prossimi = df_ct[(df_ct["DataFine"].notna()) & (df_ct["DataFine"] >= now) & (df_ct["DataFine"] <= now + pd.DateOffset(months=6))]
    if prossimi.empty:
        st.info("✅ Nessun contratto in scadenza.")
    else:
        m = prossimi.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        st.dataframe(m[["RagioneSociale", "NumeroContratto", "DataFine", "Stato"]].sort_values("DataFine").head(10), use_container_width=True)

    st.markdown("### ⏰ Contratti senza Data Fine (attivi da oggi)")
    senza = df_ct[df_ct["DataFine"].isna() & (df_ct["DataInizio"] >= now)]
    if senza.empty:
        st.info("✅ Nessun contratto senza data fine.")
    else:
        m2 = senza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        st.dataframe(m2[["RagioneSociale", "NumeroContratto", "DataInizio", "Stato"]].sort_values("DataInizio").head(10), use_container_width=True)

# =========================================================
# ANAGRAFICA CLIENTI
# =========================================================
def page_anagrafica(df_cli, df_ct, role):
    st.title("📇 Anagrafica Clienti")
    st.markdown("Gestisci qui l’elenco completo dei clienti.")

    if st.button("➕ Nuovo Cliente"):
        nuovo = {
            "ClienteID": str(int(datetime.now().timestamp())),
            "RagioneSociale": "",
            "Citta": "",
            "Telefono": "",
            "Email": "",
            "UltimoRecall": "",
            "ProssimoRecall": "",
            "UltimaVisita": "",
            "ProssimaVisita": "",
            "Note": ""
        }
        df_cli = pd.concat([df_cli, pd.DataFrame([nuovo])], ignore_index=True)
        save_clienti(df_cli)
        st.rerun()

    edited = st.data_editor(df_cli, num_rows="dynamic", use_container_width=True, key="edit_cli")
    if st.button("💾 Salva Modifiche"):
        save_clienti(edited)
        st.success("✅ Dati clienti salvati.")

# =========================================================
# PAGINA CLIENTE DETTAGLIO
# =========================================================
def page_clienti(df_cli, df_ct, role):
    st.title("🏢 Gestione Clienti e Preventivi")
    if df_cli.empty:
        st.warning("Nessun cliente registrato.")
        return

    cliente = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"])
    cli = df_cli[df_cli["RagioneSociale"] == cliente].iloc[0]
    cli_id = cli["ClienteID"]

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Città:** {cli.get('Citta','')}")
        st.write(f"**Telefono:** {cli.get('Telefono','')}")
        st.write(f"**Email:** {cli.get('Email','')}")
    with col2:
        st.write(f"**Ultimo Recall:** {fmt_date(cli.get('UltimoRecall'))}")
        st.write(f"**Prossimo Recall:** {fmt_date(cli.get('ProssimoRecall'))}")
        st.write(f"**Ultima Visita:** {fmt_date(cli.get('UltimaVisita'))}")

    st.divider()
    st.subheader("🗒️ Note Cliente")
    note = st.text_area("Note", cli.get("Note",""), height=100)
    if st.button("💾 Salva Note"):
        idx = df_cli.index[df_cli["ClienteID"] == cli_id][0]
        df_cli.loc[idx, "Note"] = note
        save_clienti(df_cli)
        st.success("Note salvate.")
        st.rerun()

    st.divider()
    st.subheader("📄 Contratti Cliente")
    contratti = df_ct[df_ct["ClienteID"] == cli_id]
    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        st.dataframe(contratti[["NumeroContratto","DataInizio","DataFine","Stato"]], use_container_width=True)

    # Preventivi
    st.divider()
    st.subheader("🧾 Preventivi Cliente")
    if PREVENTIVI_CSV.exists():
        df_prev = pd.read_csv(PREVENTIVI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df_prev = pd.DataFrame(columns=["ClienteID","NumeroOfferta","Template","NomeFile","Percorso","DataCreazione"])

    prev_cli = df_prev[df_prev["ClienteID"] == cli_id]
    if not prev_cli.empty:
        st.dataframe(prev_cli[["NumeroOfferta","Template","DataCreazione","NomeFile"]], use_container_width=True)
    else:
        st.info("Nessun preventivo per questo cliente.")

    st.markdown("### ➕ Crea nuovo preventivo")
    templates = {
        "Offerta – Centralino": "Offerta_Centralino.docx",
        "Offerta – Varie": "Offerta_Varie.docx",
        "Offerta – A3": "Offerte_A3.docx",
        "Offerta – A4": "Offerte_A4.docx",
    }
    with st.form("new_prev"):
        nome = st.text_input("Nome File (es. Offerta_SHT.docx)")
        template = st.selectbox("Template", list(templates.keys()))
        submit = st.form_submit_button("💾 Genera Preventivo")
        if submit:
            num = f"OFF-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            tpl_path = STORAGE_DIR / "templates" / templates[template]
            if not tpl_path.exists():
                st.error(f"Template mancante: {tpl_path}")
            else:
                dest = STORAGE_DIR / "preventivi"
                dest.mkdir(exist_ok=True)
                out = dest / (nome or f"{num}.docx")
                doc = Document(tpl_path)
                mapping = {
                    "CLIENTE": cli["RagioneSociale"],
                    "CITTA": cli.get("Citta",""),
                    "DATA": datetime.now().strftime("%d/%m/%Y"),
                    "NUMERO_OFFERTA": num,
                }
                for p in doc.paragraphs:
                    for k,v in mapping.items():
                        if f"<<{k}>>" in p.text:
                            p.text = p.text.replace(f"<<{k}>>", v)
                doc.save(out)
                nuovo = {
                    "ClienteID": cli_id,
                    "NumeroOfferta": num,
                    "Template": template,
                    "NomeFile": out.name,
                    "Percorso": str(out),
                    "DataCreazione": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                df_prev = pd.concat([df_prev,pd.DataFrame([nuovo])],ignore_index=True)
                df_prev.to_csv(PREVENTIVI_CSV,index=False,encoding="utf-8-sig")
                st.success(f"✅ Preventivo creato: {out.name}")
                st.rerun()

# =========================================================
# CONTRATTI
# =========================================================
def page_contratti(df_cli, df_ct, role):
    st.title("📜 Gestione Contratti")
    if df_cli.empty:
        st.warning("Nessun cliente registrato.")
        return

    cliente = st.selectbox("Cliente", df_cli["RagioneSociale"])
    cli = df_cli[df_cli["RagioneSociale"] == cliente].iloc[0]
    cli_id = cli["ClienteID"]

    with st.expander("➕ Nuovo Contratto"):
        with st.form("new_ct"):
            n = st.text_input("Numero Contratto")
            d_in = st.date_input("Data Inizio")
            dur = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto")
            tot = st.text_input("Tot Rata (€)")
            s = st.form_submit_button("💾 Crea Contratto")
            if s:
                df_ct = pd.concat([df_ct,pd.DataFrame([{
                    "ClienteID": cli_id,
                    "NumeroContratto": n,
                    "DataInizio": pd.to_datetime(d_in),
                    "DataFine": pd.to_datetime(d_in)+pd.DateOffset(months=int(dur)),
                    "Durata": dur,
                    "DescrizioneProdotto": desc,
                    "TotRata": tot,
                    "Stato": "aperto"
                }])], ignore_index=True)
                save_contratti(df_ct)
                st.success("Contratto creato.")
                st.rerun()

    contratti = df_ct[df_ct["ClienteID"] == cli_id]
    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
        return
    disp = contratti.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp["TotRata"] = disp["TotRata"].apply(money)
    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(resizable=True, sortable=True, filter=True)
    js = JsCode("""
    function(p){
      if(p.data.Stato=='chiuso') return {'backgroundColor':'#ffecec','color':'#a00'};
      if(p.data.Stato=='aperto') return {'backgroundColor':'#e8f5e9','color':'#006400'};
      return {};
    }""")
    gb.configure_grid_options(getRowStyle=js)
    AgGrid(disp, gridOptions=gb.build(), height=380, allow_unsafe_jscode=True)

# =========================================================
# LISTA COMPLETA
# =========================================================
def page_lista(df_cli, df_ct, role):
    st.title("📋 Lista Completa Clienti e Contratti")
    merged = df_ct.merge(df_cli[["ClienteID","RagioneSociale","Citta"]], on="ClienteID", how="left")
    merged["DataInizio"] = merged["DataInizio"].apply(fmt_date)
    merged["DataFine"] = merged["DataFine"].apply(fmt_date)
    st.dataframe(merged[["RagioneSociale","Citta","NumeroContratto","DataInizio","DataFine","Stato"]], use_container_width=True)
    st.download_button("⬇️ Esporta CSV", merged.to_csv(index=False,encoding="utf-8-sig"), "lista_clienti_contratti.csv")

# =========================================================
# MAIN APP
# =========================================================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    user, role = do_login()

    st.sidebar.image(LOGO_URL, width=150)
    st.sidebar.markdown(f"**Utente:** {user}")
    if st.sidebar.button("🚪 Logout"):
        for k in ["auth_user","auth_role"]:
            st.session_state.pop(k, None)
        st.rerun()

    pages = {
        "Dashboard": page_dashboard,
        "Anagrafica": page_anagrafica,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "Lista Completa": page_lista,
    }

    # Caricamento dati
    df_cli = load_clienti()
    df_ct = load_contratti()

    # Navigazione
    page = st.sidebar.radio("📂 Seleziona sezione", list(pages.keys()), index=0)

    # Esecuzione pagina
    pages[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
