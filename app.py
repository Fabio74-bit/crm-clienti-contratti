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
    return df

# =========================================================
# I/O DATI
# =========================================================
def load_clienti():
    base_cols = [
        "ClienteID", "RagioneSociale", "Citta", "Telefono", "Cellulare",
        "PersonaRiferimento2", "Email", "UltimoRecall", "ProssimoRecall",
        "UltimaVisita", "ProssimaVisita", "IBAN", "SDI", "Note"
    ]
    if not CLIENTI_CSV.exists():
        return pd.DataFrame(columns=base_cols)

    df = pd.read_csv(CLIENTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    df = ensure_columns(df, base_cols)

    # parsing date
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_clienti(df):
    out = df.copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) or d == "" else pd.to_datetime(d).strftime("%Y-%m-%d"))
    out.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")

def load_contratti():
    if not CONTRATTI_CSV.exists():
        return pd.DataFrame(columns=[
            "ClienteID", "NumeroContratto", "DataInizio", "DataFine", "Durata",
            "DescrizioneProdotto", "TotRata", "Stato"
        ])
    df = pd.read_csv(CONTRATTI_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    for c in ["DataInizio", "DataFine"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)
    return df

def save_contratti(df):
    out = df.copy()
    for c in ["DataInizio", "DataFine"]:
        out[c] = out[c].apply(lambda d: "" if pd.isna(d) or d == "" else pd.to_datetime(d).strftime("%Y-%m-%d"))
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

    # ---------------------------------------------------------
    # CONTRATTI IN SCADENZA
    # ---------------------------------------------------------
    st.markdown("### 📅 Contratti in Scadenza (entro 6 mesi)")
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce")

    scadenza = (
        df_ct[(df_ct["DataFine"].notna()) &
              (df_ct["DataFine"] >= now) &
              (df_ct["DataFine"] <= now + pd.DateOffset(months=6)) &
              (df_ct["Stato"].fillna("").str.lower() != "chiuso")]
        .merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")
    )

    if scadenza.empty:
        st.info("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        scadenza = scadenza.drop_duplicates(subset="ClienteID")
        scadenza["DataFine"] = scadenza["DataFine"].dt.strftime("%d/%m/%Y")

        for _, r in scadenza.iterrows():
            key = f"open_{r['ClienteID']}"
            if st.button(f"🔎 {r['RagioneSociale']} – Scade il {r['DataFine']}", key=key, use_container_width=True):
                st.session_state["selected_client_id"] = r["ClienteID"]
                st.session_state["nav_target"] = "Clienti"
                st.rerun()

    # ---------------------------------------------------------
    # PROSSIMI RECALL E VISITE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📅 Prossimi Recall e Visite")

    def color_for_date(d):
        if pd.isna(d): return "grey"
        days = (pd.Timestamp.now() - d).days
        if days > 30: return "green"
        elif days > 7: return "orange"
        else: return "red"

    recall = df_cli[["RagioneSociale", "ProssimoRecall"]].dropna().copy()
    recall["Colore"] = recall["ProssimoRecall"].apply(color_for_date)

    visite = df_cli[["RagioneSociale", "ProssimaVisita"]].dropna().copy()
    visite["Colore"] = visite["ProssimaVisita"].apply(color_for_date)

    col_r, col_v = st.columns(2)
    with col_r:
        st.markdown("#### 📞 Recall")
        for _, r in recall.sort_values("ProssimoRecall").head(10).iterrows():
            color = r["Colore"]
            st.markdown(f"<span style='color:{color}'>• {r['RagioneSociale']} – {fmt_date(r['ProssimoRecall'])}</span>", unsafe_allow_html=True)
    with col_v:
        st.markdown("#### 🚗 Visite")
        for _, r in visite.sort_values("ProssimaVisita").head(10).iterrows():
            color = r["Colore"]
            st.markdown(f"<span style='color:{color}'>• {r['RagioneSociale']} – {fmt_date(r['ProssimaVisita'])}</span>", unsafe_allow_html=True)
# =========================================================
# CLIENTI COMPLETI – anagrafica + note + contratti + preventivi
# =========================================================
def page_clienti(df_cli, df_ct, role):
    st.title("🏢 Gestione Clienti Completa")

    if df_cli.empty:
        st.warning("Nessun cliente registrato.")
        return

    # ---------------------------------------------------------
    # SELEZIONE CLIENTE
    # ---------------------------------------------------------
    cliente = st.selectbox("Seleziona Cliente", df_cli["RagioneSociale"])
    cli = df_cli[df_cli["RagioneSociale"] == cliente].iloc[0]
    cli = cli.fillna("")  # converte eventuali pd.NA in stringhe vuote

    cli_id = cli["ClienteID"]

    st.markdown("---")
    st.subheader("📇 Dati Anagrafici")

         # ---------------------------------------------------------
    # SEZIONE ANAGRAFICA MODIFICABILE
    # ---------------------------------------------------------
    col1, col2, col3 = st.columns(3)

    with col1:
        rag = st.text_input("Ragione Sociale", str(cli.get("RagioneSociale") or ""))
        citta = st.text_input("Città", str(cli.get("Citta") or ""))
        tel = st.text_input("Telefono", str(cli.get("Telefono") or ""))
        cell = st.text_input("Cellulare", str(cli.get("Cellulare") or ""))

    with col2:
        ref2 = st.text_input("Persona di Riferimento 2", str(cli.get("PersonaRiferimento2") or ""))
        email = st.text_input("Email", str(cli.get("Email") or ""))
        iban = st.text_input("IBAN", str(cli.get("IBAN") or ""))
        sdi = st.text_input("SDI", str(cli.get("SDI") or ""))

    with col3:
        # Conversione sicura da qualsiasi tipo → datetime.date
        def safe_date(val, fallback_days=0):
            if pd.isna(val) or val == "":
                return (datetime.now() + timedelta(days=fallback_days)).date()
            try:
                return pd.to_datetime(val).date()
            except Exception:
                return (datetime.now() + timedelta(days=fallback_days)).date()

        ult_rec = st.date_input("Ultimo Recall", safe_date(cli.get("UltimoRecall")))
        pro_rec = st.date_input("Prossimo Recall", safe_date(cli.get("ProssimoRecall"), 30))
        ult_vis = st.date_input("Ultima Visita", safe_date(cli.get("UltimaVisita")))
        pro_vis = st.date_input("Prossima Visita", safe_date(cli.get("ProssimaVisita"), 30))

    if st.button("💾 Salva Dati Anagrafici"):
        idx = df_cli.index[df_cli["ClienteID"] == cli_id][0]
        df_cli.loc[idx, ["RagioneSociale", "Citta", "Telefono", "Cellulare", "PersonaRiferimento2", "Email", "IBAN", "SDI"]] = [
            rag, citta, tel, cell, ref2, email, iban, sdi
        ]
        df_cli.loc[idx, ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]] = [
            pd.to_datetime(ult_rec), pd.to_datetime(pro_rec),
            pd.to_datetime(ult_vis), pd.to_datetime(pro_vis)
        ]
        save_clienti(df_cli)
        st.success("✅ Dati anagrafici aggiornati.")
        st.rerun()

    # ---------------------------------------------------------
    # NOTE CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("🗒️ Note Cliente")

    note_corrente = str(cli.get("Note") or "")
    note = st.text_area("Note", note_corrente, height=140)

    if st.button("💾 Salva Note Cliente"):
        idx = df_cli.index[df_cli["ClienteID"] == cli_id][0]
        df_cli.loc[idx, "Note"] = note
        save_clienti(df_cli)
        st.success("✅ Note salvate con successo.")
        st.rerun()


       # ---------------------------------------------------------
    # CONTRATTI CLIENTE
    # ---------------------------------------------------------
    st.markdown("---")
    st.subheader("📜 Contratti del Cliente")

    contratti = df_ct[df_ct["ClienteID"] == cli_id].copy()

    if contratti.empty:
        st.info("Nessun contratto per questo cliente.")
    else:
        from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

        # normalizza date e importi
        contratti["DataInizio"] = pd.to_datetime(contratti["DataInizio"], errors="coerce")
        contratti["DataFine"] = pd.to_datetime(contratti["DataFine"], errors="coerce")
        contratti["TotRata"] = contratti["TotRata"].apply(money)
        contratti["Stato"] = contratti["Stato"].fillna("aperto")

        # crea tabella modificabile
        gb = GridOptionsBuilder.from_dataframe(contratti)
        gb.configure_default_column(editable=True, resizable=True, filter=True, sortable=True, wrapText=True, autoHeight=True)
        gb.configure_grid_options(domLayout="autoHeight")

        js_style = JsCode("""
        function(params) {
            if (!params.data.Stato) return {};
            const stato = params.data.Stato.toLowerCase();
            if (stato.includes('chiuso')) {
                return { 'backgroundColor': '#ffebee', 'color': '#b71c1c', 'fontWeight': 'bold' };
            } else if (stato.includes('aperto')) {
                return { 'backgroundColor': '#e8f5e9', 'color': '#1b5e20' };
            }
            return {};
        }
        """)
        gb.configure_grid_options(getRowStyle=js_style)

        grid = AgGrid(
            contratti,
            gridOptions=gb.build(),
            theme="balham",
            update_mode=GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            height=420,
            fit_columns_on_grid_load=True,
        )

        # ---------------------------------------------------------
        # SALVATAGGIO MODIFICHE INLINE
        # ---------------------------------------------------------
        if st.button("💾 Salva modifiche ai contratti"):
            nuovi_dati = pd.DataFrame(grid["data"])
            for c in ["DataInizio", "DataFine"]:
                nuovi_dati[c] = pd.to_datetime(nuovi_dati[c], errors="coerce", dayfirst=True)
            df_ct.update(nuovi_dati)
            save_contratti(df_ct)
            st.success("✅ Contratti aggiornati.")
            st.rerun()

        # ---------------------------------------------------------
        # GESTIONE STATO CONTRATTI
        # ---------------------------------------------------------
        st.divider()
        st.markdown("### ⚙️ Stato contratti")

        for i, r in contratti.iterrows():
            c1, c2, c3 = st.columns([0.05, 0.7, 0.25])
            with c2:
                st.caption(f"{r['NumeroContratto']} — {str(r.get('DescrizioneProdotto',''))[:60]}")
            with c3:
                stato = (r["Stato"] or "aperto").lower()
                if stato == "chiuso":
                    if st.button("🔓 Riapri", key=f"open_{i}"):
                        df_ct.loc[df_ct.index == r.name, "Stato"] = "aperto"
                        save_contratti(df_ct)
                        st.success("✅ Contratto riaperto.")
                        st.rerun()
                else:
                    if st.button("❌ Chiudi", key=f"close_{i}"):
                        df_ct.loc[df_ct.index == r.name, "Stato"] = "chiuso"
                        save_contratti(df_ct)
                        st.success("✅ Contratto chiuso.")
                        st.rerun()


# =========================================================
# LISTA COMPLETA CLIENTI E CONTRATTI
# =========================================================
def page_lista(df_cli, df_ct, role):
    st.title("📋 Lista Completa Clienti e Contratti")

    st.markdown("### 🔍 Filtra Clienti")
    col1, col2 = st.columns(2)
    with col1:
        filtro_nome = st.text_input("Cerca per nome cliente")
    with col2:
        filtro_citta = st.text_input("Cerca per città")

    merged = df_ct.merge(df_cli[["ClienteID", "RagioneSociale", "Citta"]], on="ClienteID", how="left")

    if filtro_nome:
        merged = merged[merged["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        merged = merged[merged["Citta"].str.contains(filtro_citta, case=False, na=False)]

    merged["DataInizio"] = pd.to_datetime(merged["DataInizio"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged["DataFine"] = pd.to_datetime(merged["DataFine"], errors="coerce").dt.strftime("%d/%m/%Y")
    merged = merged[["RagioneSociale", "Citta", "NumeroContratto", "DataInizio", "DataFine", "Stato"]].fillna("")
    st.dataframe(merged, use_container_width=True, hide_index=True)

    csv = merged.to_csv(index=False, encoding="utf-8-sig")
    st.download_button("⬇️ Esporta CSV", csv, "lista_clienti_contratti.csv", "text/csv")

# =========================================================
# MAIN APP
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

    # Routing
    pages = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "Lista Completa": page_lista,
    }

    df_cli = load_clienti()
    df_ct = load_contratti()

    page = st.sidebar.radio("📂 Seleziona sezione", list(pages.keys()), index=0)
    if page == "Clienti" and "selected_client_id" in st.session_state:
        cid = st.session_state["selected_client_id"]
        if cid in df_cli["ClienteID"].values:
            cliente_nome = df_cli.loc[df_cli["ClienteID"] == cid, "RagioneSociale"].values[0]
            st.session_state.pop("selected_client_id", None)
            st.session_state["cliente_default"] = cliente_nome
    pages[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
