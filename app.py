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
# =========================================================
# DASHBOARD – aggiornata con recall colorati e link ai clienti
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
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce")
    prossimi = df_ct[
        (df_ct["DataFine"].notna()) &
        (df_ct["DataFine"] >= now) &
        (df_ct["DataFine"] <= now + pd.DateOffset(months=6)) &
        (df_ct["Stato"].fillna("").str.lower() != "chiuso")
    ]

    if prossimi.empty:
        st.info("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        m = prossimi.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        m = m.sort_values("DataFine").drop_duplicates("ClienteID")  # ✅ un solo contratto per cliente
        m["DataFine"] = m["DataFine"].dt.strftime("%d/%m/%Y")

        # Mostra come tabella cliccabile
        for _, r in m.iterrows():
            col1, col2, col3 = st.columns([0.5, 0.3, 0.2])
            with col1:
                if st.button(r["RagioneSociale"], key=f"dashcli_{r['ClienteID']}"):
                    st.session_state["selected_client_id"] = r["ClienteID"]
                    st.session_state["nav_target"] = "Clienti"
                    st.rerun()
            with col2:
                st.write(r["NumeroContratto"])
            with col3:
                st.write(r["DataFine"])

    st.markdown("### ⏰ Contratti senza Data Fine (attivi da oggi in poi)")
    senza = df_ct[df_ct["DataFine"].isna() & (df_ct["DataInizio"] >= now) & (df_ct["Stato"].fillna("").str.lower() != "chiuso")]
    if senza.empty:
        st.info("✅ Nessun contratto senza data fine.")
    else:
        m2 = senza.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
        m2["DataInizio"] = pd.to_datetime(m2["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
        st.dataframe(m2[["RagioneSociale", "NumeroContratto", "DataInizio", "Stato"]].sort_values("DataInizio"), use_container_width=True)

    st.markdown("### 📞 Prossimi Recall e Visite")
    def color_row(date):
        if pd.isna(date):
            return "⚪ Nessuna data"
        diff = (date - now).days
        if diff <= 7:
            return f"🔴 {date.strftime('%d/%m/%Y')}"
        elif diff <= 30:
            return f"🟡 {date.strftime('%d/%m/%Y')}"
        else:
            return f"🟢 {date.strftime('%d/%m/%Y')}"

    df_cli["ProssimoRecallFmt"] = df_cli["ProssimoRecall"].apply(color_row)
    df_cli["ProssimaVisitaFmt"] = df_cli["ProssimaVisita"].apply(color_row)
    colR, colV = st.columns(2)
    with colR:
        st.markdown("#### 🔁 Recall")
        st.dataframe(df_cli[["RagioneSociale", "ProssimoRecallFmt"]].dropna().head(10), use_container_width=True)
    with colV:
        st.markdown("#### 🚗 Visite")
        st.dataframe(df_cli[["RagioneSociale", "ProssimaVisitaFmt"]].dropna().head(10), use_container_width=True)


# =========================================================
# ANAGRAFICA CLIENTI – versione aggiornata
# =========================================================
def page_anagrafica(df_cli, df_ct, role):
    st.title("📇 Anagrafica Clienti")
    st.markdown("Gestisci qui l’elenco completo dei clienti. Puoi modificare direttamente i dati nella tabella.")

    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

    # Crea nuovo cliente
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
        st.success("✅ Nuovo cliente aggiunto.")
        st.rerun()

    # Impostazioni AgGrid
    gb = GridOptionsBuilder.from_dataframe(df_cli)
    gb.configure_default_column(editable=True, resizable=True, filter=True, sortable=True, wrapText=True, autoHeight=True)
    gb.configure_grid_options(domLayout='autoHeight')
    grid = AgGrid(
        df_cli,
        gridOptions=gb.build(),
        theme="balham",
        update_mode=GridUpdateMode.VALUE_CHANGED,
        allow_unsafe_jscode=True,
        height=450,
        fit_columns_on_grid_load=True,
    )

    # Salvataggio
    if st.button("💾 Salva modifiche"):
        new_df = pd.DataFrame(grid["data"])
        save_clienti(new_df)
        st.success("✅ Dati clienti aggiornati.")
        st.rerun()


# =========================================================
# PAGINA CLIENTE DETTAGLIO
# =========================================================
# =========================================================
# CLIENTI COMPLETI – aggiornata con nuovi campi + preventivo scaricabile
# =========================================================
def page_clienti(df_cli, df_ct, role):
    st.title("🏢 Gestione Clienti Completa")

    if df_cli.empty:
        st.warning("Nessun cliente registrato.")
        return

    pre = st.session_state.get("selected_client_id")
    if pre:
        cli = df_cli[df_cli["ClienteID"] == pre].iloc[0]
        idx = df_cli.index[df_cli["ClienteID"] == pre][0]
    else:
        cliente = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"])
        cli = df_cli[df_cli["RagioneSociale"] == cliente].iloc[0]
        idx = df_cli.index[df_cli["RagioneSociale"] == cliente][0]

    cli_id = cli["ClienteID"]

    st.markdown("---")
    st.subheader("📇 Dati Anagrafici")

    col1, col2, col3 = st.columns(3)
    with col1:
        rag = st.text_input("Ragione Sociale", cli.get("RagioneSociale", ""))
        citta = st.text_input("Città", cli.get("Citta", ""))
        tel = st.text_input("Telefono", cli.get("Telefono", ""))
        cell = st.text_input("Cellulare", cli.get("Cellulare", ""))
    with col2:
        email = st.text_input("Email", cli.get("Email", ""))
        pr1 = st.text_input("Persona di Riferimento", cli.get("PersonaRiferimento", ""))
        pr2 = st.text_input("Persona di Riferimento 2", cli.get("PersonaRiferimento2", ""))
        iban = st.text_input("IBAN", cli.get("IBAN", ""))
    with col3:
        sdi = st.text_input("SDI", cli.get("SDI", ""))
        ult_rec = st.date_input("Ultimo Recall", cli.get("UltimoRecall") if not pd.isna(cli.get("UltimoRecall")) else datetime.now())
        pro_rec = st.date_input("Prossimo Recall", cli.get("ProssimoRecall") if not pd.isna(cli.get("ProssimoRecall")) else datetime.now() + timedelta(days=30))
        ult_vis = st.date_input("Ultima Visita", cli.get("UltimaVisita") if not pd.isna(cli.get("UltimaVisita")) else datetime.now())
        pro_vis = st.date_input("Prossima Visita", cli.get("ProssimaVisita") if not pd.isna(cli.get("ProssimaVisita")) else datetime.now() + timedelta(days=30))

    if st.button("💾 Salva Dati Anagrafici"):
        for k, v in {
            "RagioneSociale": rag, "Citta": citta, "Telefono": tel, "Cellulare": cell,
            "Email": email, "PersonaRiferimento": pr1, "PersonaRiferimento2": pr2,
            "IBAN": iban, "SDI": sdi, "UltimoRecall": ult_rec, "ProssimoRecall": pro_rec,
            "UltimaVisita": ult_vis, "ProssimaVisita": pro_vis
        }.items():
            df_cli.loc[idx, k] = v
        save_clienti(df_cli)
        st.success("✅ Dati anagrafici aggiornati.")
        st.rerun()

    st.markdown("---")
    st.subheader("🗒️ Note Cliente")
    note = st.text_area("Note", cli.get("Note", ""), height=120)
    if st.button("💾 Salva Note Cliente"):
        df_cli.loc[idx, "Note"] = note
        save_clienti(df_cli)
        st.success("✅ Note salvate.")
        st.rerun()

    # =========================
    # CONTRATTI CLIENTE
    # =========================
    st.markdown("---")
    st.subheader("📜 Contratti del Cliente")
    contratti = df_ct[df_ct["ClienteID"] == cli_id]
    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
        contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
        contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
        gb = GridOptionsBuilder.from_dataframe(contratti)
        gb.configure_default_column(editable=True, resizable=True, sortable=True, filter=True)
        grid = AgGrid(contratti, gridOptions=gb.build(), theme="balham", update_mode=GridUpdateMode.VALUE_CHANGED, height=380)

        if st.button("💾 Salva modifiche ai contratti"):
            new_df = pd.DataFrame(grid["data"])
            for c in ["DataInizio", "DataFine"]:
                new_df[c] = pd.to_datetime(new_df[c], errors="coerce", dayfirst=True)
            save_contratti(new_df)
            st.success("✅ Contratti aggiornati.")
            st.rerun()

    # =========================
    # PREVENTIVI CLIENTE
    # =========================
    st.markdown("---")
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
            count = len(df_prev) + 1
            cliente_sicuro = "".join(c for c in cli["RagioneSociale"].upper() if c.isalnum())[:15]
            num = f"SHT-{cliente_sicuro}-{count:03d}"
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
                


# =========================================================
# CONTRATTI – versione aggiornata
# =========================================================
def page_contratti(df_cli, df_ct, role):
    st.title("📜 Gestione Contratti")
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

    if df_cli.empty:
        st.warning("Nessun cliente registrato.")
        return

    # Selezione cliente
    cliente = st.selectbox("Cliente", df_cli["RagioneSociale"])
    cli = df_cli[df_cli["RagioneSociale"] == cliente].iloc[0]
    cli_id = cli["ClienteID"]

    # --- Creazione nuovo contratto
    with st.expander("➕ Nuovo Contratto"):
        with st.form("new_ct"):
            n = st.text_input("Numero Contratto")
            d_in = st.date_input("Data Inizio")
            dur = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto")
            tot = st.text_input("Tot Rata (€)")
            s = st.form_submit_button("💾 Crea Contratto")
            if s:
                df_ct = pd.concat([df_ct, pd.DataFrame([{
                    "ClienteID": cli_id,
                    "NumeroContratto": n,
                    "DataInizio": pd.to_datetime(d_in),
                    "DataFine": pd.to_datetime(d_in) + pd.DateOffset(months=int(dur)),
                    "Durata": dur,
                    "DescrizioneProdotto": desc,
                    "TotRata": tot,
                    "Stato": "aperto"
                }])], ignore_index=True)
                save_contratti(df_ct)
                st.success("✅ Contratto creato.")
                st.rerun()

    contratti = df_ct[df_ct["ClienteID"] == cli_id].copy()
    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    # Formattazione date e importi
    contratti["DataInizio"] = contratti["DataInizio"].apply(fmt_date)
    contratti["DataFine"] = contratti["DataFine"].apply(fmt_date)
    contratti["TotRata"] = contratti["TotRata"].apply(money)

    # --- AGGRID EDITABILE
    gb = GridOptionsBuilder.from_dataframe(contratti)
    gb.configure_default_column(editable=True, resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True)

    # Colorazione righe per stato
    js = JsCode("""
    function(p){
      if(p.data.Stato == 'chiuso'){return {'backgroundColor':'#ffecec','color':'#a00'};}
      if(p.data.Stato == 'aperto'){return {'backgroundColor':'#e8f5e9','color':'#006400'};}
      return {};
    }
    """)
    gb.configure_grid_options(getRowStyle=js)
    gb.configure_grid_options(domLayout='autoHeight')

    grid = AgGrid(
        contratti,
        gridOptions=gb.build(),
        theme="balham",
        update_mode=GridUpdateMode.VALUE_CHANGED,
        allow_unsafe_jscode=True,
        height=420,
        fit_columns_on_grid_load=True,
    )

    st.divider()

    # --- Pulsanti di chiusura / riapertura
    st.markdown("### ⚙️ Gestione Stato Contratti")
    for i, r in contratti.iterrows():
        c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
        with c2:
            st.caption(f"{r['NumeroContratto']} — {r.get('DescrizioneProdotto','')[:60]}")
        with c3:
            if r["Stato"].lower() == "chiuso":
                if st.button("🔓 Riapri", key=f"open_{i}"):
                    df_ct.loc[df_ct.index == r.name, "Stato"] = "aperto"
                    save_contratti(df_ct)
                    st.rerun()
            else:
                if st.button("❌ Chiudi", key=f"close_{i}"):
                    df_ct.loc[df_ct.index == r.name, "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.rerun()

    st.divider()

    # --- Salvataggio modifiche AgGrid
    if st.button("💾 Salva modifiche ai contratti"):
        new_df = pd.DataFrame(grid["data"])
        # Re-converti le date per sicurezza
        for c in ["DataInizio", "DataFine"]:
            new_df[c] = pd.to_datetime(new_df[c], errors="coerce", dayfirst=True)
        save_contratti(new_df)
        st.success("✅ Modifiche ai contratti salvate.")
        st.rerun()


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
# MAIN APP – aggiornato (senza pagina Anagrafica)
# =========================================================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    user, role = do_login()

    st.sidebar.image(LOGO_URL, width=150)
    st.sidebar.markdown(f"**Utente:** {user}")
    if st.sidebar.button("🚪 Logout"):
        for k in ["auth_user", "auth_role"]:
            st.session_state.pop(k, None)
        st.rerun()

    # Pagine disponibili (senza "Anagrafica")
    pages = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,          # ✅ scheda completa
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
