# =====================================
# 📦 IMPORT PRINCIPALI E CONFIGURAZIONE BASE
# =====================================
import streamlit as st
st.write("🧠 Test secrets:", st.secrets)
st.stop()
import pandas as pd
from datetime import datetime
from pathlib import Path
from supabase import create_client, Client

# =====================================
# 🔗 CONNESSIONE SUPABASE
# =====================================
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["key"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================
# 🔧 FUNZIONE PER CORREGGERE OWNER SU SUPABASE (solo admin)
# =====================================
def fix_supabase_owner(admin_user: str):
    """Corregge la colonna 'owner' per clienti e contratti se mancante."""
    try:
        st.info("⚙️ Avvio controllo e correzione 'owner' su Supabase...")

        # --- CLIENTI ---
        res_cli = supabase.table("clienti").select("*").execute()
        data_cli = res_cli.data
        df_cli = pd.DataFrame(data_cli)

        if df_cli.empty:
            st.warning("⚠️ Nessun cliente trovato su Supabase.")
        elif "owner" not in df_cli.columns and "Owner" not in df_cli.columns:
            st.error("❌ La tabella 'clienti' non ha la colonna 'owner'. Aggiungila manualmente su Supabase.")
        else:
            if "Owner" in df_cli.columns:
                df_cli["owner"] = df_cli["Owner"]
            df_cli["owner"] = df_cli["owner"].fillna(admin_user)
            for _, row in df_cli.iterrows():
                supabase.table("clienti").update({"owner": row["owner"]}).eq("id", row["id"]).execute()
            st.success("✅ Colonna 'owner' corretta su tutti i clienti.")

        # --- CONTRATTI ---
        res_ct = supabase.table("contratti").select("*").execute()
        data_ct = res_ct.data
        df_ct = pd.DataFrame(data_ct)

        if df_ct.empty:
            st.warning("⚠️ Nessun contratto trovato su Supabase.")
        elif "owner" not in df_ct.columns and "Owner" not in df_ct.columns:
            st.error("❌ La tabella 'contratti' non ha la colonna 'owner'. Aggiungila manualmente su Supabase.")
        else:
            if "Owner" in df_ct.columns:
                df_ct["owner"] = df_ct["Owner"]
            df_ct["owner"] = df_ct["owner"].fillna(admin_user)
            for _, row in df_ct.iterrows():
                supabase.table("contratti").update({"owner": row["owner"]}).eq("id", row["id"]).execute()
            st.info("✅ Tutti i contratti hanno già un owner.")

        st.success("🎉 Correzione completata! Ricarica l'app per vedere i dati aggiornati.")

    except Exception as e:
        st.error(f"❌ Errore durante la correzione Supabase: {e}")


# =====================================
# 🧩 NORMALIZZAZIONE COLONNE (compatibilità Supabase)
# =====================================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {
        "clienteid": "ClienteID",
        "ragionesociale": "RagioneSociale",
        "personariferimento": "PersonaRiferimento",
        "indirizzo": "Indirizzo",
        "citta": "Citta",
        "cap": "CAP",
        "telefono": "Telefono",
        "cell": "Cell",
        "email": "Email",
        "partitaiva": "PartitaIVA",
        "iban": "IBAN",
        "sdi": "SDI",
        "ultimorecall": "UltimoRecall",
        "prossimorecall": "ProssimoRecall",
        "ultimavisita": "UltimaVisita",
        "prossimavisita": "ProssimaVisita",
        "tmk": "TMK",
        "notecliente": "NoteCliente",
        "numerocontratto": "NumeroContratto",
        "datainizio": "DataInizio",
        "datafine": "DataFine",
        "durata": "Durata",
        "descrizioneprodotto": "DescrizioneProdotto",
        "nol_fin": "NOL_FIN",
        "nol_int": "NOL_INT",
        "totrata": "TotRata",
        "copiebn": "CopieBN",
        "eccbn": "EccBN",
        "copiecol": "CopieCol",
        "ecccol": "EccCol",
        "stato": "Stato",
        "owner": "owner"
    }
    df = df.rename(columns={c: mapping.get(c.lower(), c) for c in df.columns})

    if "ClienteID" in df.columns:
        df["ClienteID"] = df["ClienteID"].astype(str)
    if "NumeroContratto" in df.columns:
        df["NumeroContratto"] = df["NumeroContratto"].astype(str)

    return df


# =====================================
# 📦 CARICAMENTO DATI DA SUPABASE (versione robusta)
# =====================================
def carica_dati_supabase(user: str):
    """Scarica i dati di clienti e contratti da Supabase in modo sicuro."""
    try:
        data_cli = supabase.table("clienti").select("*").eq("owner", user).execute().data
        data_ct = supabase.table("contratti").select("*").eq("owner", user).execute().data

        df_cli = pd.DataFrame(data_cli)
        df_ct = pd.DataFrame(data_ct)

        # --- Normalizza colonne ---
        df_cli = normalize_columns(df_cli)
        df_ct = normalize_columns(df_ct)

        # --- Assicura presenza colonne chiave ---
        for col in ["ClienteID", "RagioneSociale"]:
            if col not in df_cli.columns:
                df_cli[col] = ""
        for col in ["ClienteID", "NumeroContratto", "DescrizioneProdotto", "Stato"]:
            if col not in df_ct.columns:
                df_ct[col] = ""

        # --- Conversione tipo sicura ---
        if "ClienteID" in df_cli.columns:
            df_cli["ClienteID"] = df_cli["ClienteID"].astype(str)
        if "ClienteID" in df_ct.columns:
            df_ct["ClienteID"] = df_ct["ClienteID"].astype(str)

        # --- Ritorna DataFrame puliti ---
        return df_cli.fillna(""), df_ct.fillna("")

    except Exception as e:
        st.error(f"❌ Errore nel caricamento da Supabase: {e}")
        return pd.DataFrame(), pd.DataFrame()


# =====================================
# 🧾 FUNZIONI UTILITY DI FORMATTAZIONE
# =====================================
def fmt_date(d) -> str:
    """Formatta le date in formato DD/MM/YYYY."""
    if d in (None, "", "nan", "NaN"):
        return ""
    try:
        parsed = pd.to_datetime(str(d), errors="coerce", dayfirst=True)
        return "" if pd.isna(parsed) else parsed.strftime("%d/%m/%Y")
    except Exception:
        return ""

def money(x):
    """Formatta numeri in valuta italiana."""
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        if pd.isna(v):
            return ""
        return f"{v:,.2f} €"
    except Exception:
        return ""

def safe_text(txt):
    """Rimuove caratteri non compatibili con PDF latin-1."""
    if pd.isna(txt) or txt is None:
        return ""
    s = str(txt)
    replacements = {"€": "EUR", "–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'"}
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")
# =====================================
# 🎨 KPI CARD — GRAFICA DASHBOARD
# =====================================
def kpi_card(titolo: str, valore, icona: str, colore: str = "#2563eb") -> str:
    return f"""
    <div style="
        background:{colore}10;
        border-left:6px solid {colore};
        border-radius:10px;
        padding:1rem 1.2rem;
        box-shadow:0 2px 8px rgba(0,0,0,0.06);
        height:100%;
    ">
        <div style="font-size:1.6rem;">{icona}</div>
        <div style="font-size:0.9rem;font-weight:600;color:#444;">{titolo}</div>
        <div style="font-size:1.8rem;font-weight:700;color:{colore};">{valore}</div>
    </div>
    """


# =====================================
# 📊 PAGINA DASHBOARD PRINCIPALE
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(globals().get("LOGO_URL", ""), width=120)
    st.markdown("<h2>📊 Gestionale SHT</h2>", unsafe_allow_html=True)
    st.divider()

    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())
    now = pd.Timestamp.now().normalize()

    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    new_contracts = df_ct[
        (df_ct["DataInizio"].notna()) &
        (df_ct["DataInizio"] >= pd.Timestamp(year=now.year, month=1, day=1))
    ]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#1976D2"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#388E3C"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#D32F2F"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Nuovi contratti anno", len(new_contracts), "⭐", "#FBC02D"), unsafe_allow_html=True)
    st.divider()

    st.markdown("### ⚠️ Contratti in scadenza entro 6 mesi")
    oggi = pd.Timestamp.now().normalize()
    entro_6_mesi = oggi + pd.DateOffset(months=6)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    scadenze = df_ct[
        (df_ct["DataFine"].notna()) &
        (df_ct["DataFine"] >= oggi) &
        (df_ct["DataFine"] <= entro_6_mesi) &
        (df_ct["Stato"].astype(str).str.lower() != "chiuso")
    ].copy()

    if scadenze.empty:
        st.success("✅ Nessun contratto in scadenza nei prossimi 6 mesi.")
    else:
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        scadenze = scadenze.sort_values("DataFine")
        st.markdown(f"📅 **{len(scadenze)} contratti in scadenza:**")
        for i, r in scadenze.iterrows():
            cols = st.columns([2, 1, 1, 1])
            cols[0].markdown(f"**{r.get('RagioneSociale','—')}**")
            cols[1].markdown(r.get("NumeroContratto", "—"))
            cols[2].markdown(fmt_date(r.get("DataFine")))
            cols[3].markdown(r.get("Stato", "—"))


# =====================================
# 🧾 PAGINA CLIENTI (Gestione completa)
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Gestione Clienti")

    search_query = st.text_input("🔍 Cerca cliente per nome o ID")
    if search_query:
        filtered = df_cli[
            df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False)
            | df_cli["ClienteID"].astype(str).str.contains(search_query, na=False)
        ]
    else:
        filtered = df_cli.copy()

    if filtered.empty:
        st.warning("❌ Nessun cliente trovato.")
        return

    options = filtered["RagioneSociale"].tolist()
    selected_name = st.selectbox("Seleziona Cliente", options)
    cliente = filtered[filtered["RagioneSociale"] == selected_name].iloc[0]
    sel_id = cliente["ClienteID"]

    st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
    st.caption(f"ID Cliente: {sel_id}")

    colA, colB = st.columns(2)
    with colA:
        st.markdown(f"**📞 Telefono:** {cliente.get('Telefono','')} — **Cell:** {cliente.get('Cell','')}")
        st.markdown(f"**✉️ Email:** {cliente.get('Email','')}")
        st.markdown(f"**👩‍💼 TMK:** {cliente.get('TMK','')}")
    with colB:
        st.markdown(f"**📍 Indirizzo:** {cliente.get('Indirizzo','')} {cliente.get('Citta','')} {cliente.get('CAP','')}")
        st.markdown(f"**💼 P.IVA:** {cliente.get('PartitaIVA','')}")
        st.markdown(f"**🏦 IBAN:** {cliente.get('IBAN','')} — **SDI:** {cliente.get('SDI','')}")

    st.divider()
    st.markdown("### 📝 Note Cliente")
    note = st.text_area("Note", cliente.get("NoteCliente", ""), height=150)
    if st.button("💾 Salva Note Cliente"):
        idx = df_cli.index[df_cli["ClienteID"] == sel_id][0]
        df_cli.loc[idx, "NoteCliente"] = note
        save_clienti(df_cli)
        st.success("✅ Note aggiornate.")


# =====================================
# 📄 PAGINA CONTRATTI
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📄 Gestione Contratti")

    if df_ct.empty:
        st.info("Nessun contratto disponibile.")
        return

    clienti_labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    sel_label = st.selectbox("Seleziona Cliente", clienti_labels)
    sel_id = sel_label.split(" — ")[0]
    rag_soc = sel_label.split(" — ")[1]

    ct = df_ct[df_ct["ClienteID"].astype(str) == sel_id].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["TotRata"] = ct["TotRata"].apply(money)
    ct["DataInizio"] = ct["DataInizio"].apply(fmt_date)
    ct["DataFine"] = ct["DataFine"].apply(fmt_date)

    st.dataframe(ct[[
        "NumeroContratto", "DataInizio", "DataFine", "TotRata", "Stato", "DescrizioneProdotto"
    ]], use_container_width=True, hide_index=True)


# =====================================
# 📅 PAGINA RECALL E VISITE
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(globals().get("LOGO_URL", ""), width=120)
    st.markdown("<h2>📅 Gestione Recall e Visite</h2>", unsafe_allow_html=True)
    st.divider()

    oggi = pd.Timestamp.now().normalize()
    df = df_cli.copy()
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True)

    imminenti = df[
        (df["ProssimoRecall"].between(oggi, oggi + pd.DateOffset(days=30))) |
        (df["ProssimaVisita"].between(oggi, oggi + pd.DateOffset(days=30)))
    ]
    if imminenti.empty:
        st.success("✅ Nessun richiamo o visita imminente.")
    else:
        for _, r in imminenti.iterrows():
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.markdown(f"**{r['RagioneSociale']}**")
            c2.markdown(fmt_date(r["ProssimoRecall"]))
            c3.markdown(fmt_date(r["ProssimaVisita"]))


# =====================================
# 📋 PAGINA LISTA CLIENTI E SCADENZE
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Scadenze")
    oggi = pd.Timestamp.now().normalize()

    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    attivi = df_ct[df_ct["Stato"].astype(str).str.lower() != "chiuso"]
    prime_scadenze = (
        attivi.groupby("ClienteID")["DataFine"]
        .min().reset_index().rename(columns={"DataFine": "PrimaScadenza"})
    )

    merged = df_cli.merge(prime_scadenze, on="ClienteID", how="left")
    merged["GiorniMancanti"] = (merged["PrimaScadenza"] - oggi).dt.days

    def badge(row):
        if pd.isna(row["PrimaScadenza"]):
            return "⚪ Nessuna"
        giorni = row["GiorniMancanti"]
        data_fmt = fmt_date(row["PrimaScadenza"])
        if giorni < 0:
            return f"⚫ Scaduto ({data_fmt})"
        elif giorni <= 30:
            return f"🔴 {data_fmt}"
        elif giorni <= 90:
            return f"🟡 {data_fmt}"
        else:
            return f"🟢 {data_fmt}"

    merged["Badge"] = merged.apply(badge, axis=1)
    for _, r in merged.iterrows():
        c1, c2, c3 = st.columns([2, 1.5, 1])
        c1.markdown(f"**{r['RagioneSociale']}**")
        c2.markdown(r.get("Citta", "—"))
        c3.markdown(r["Badge"])
# =====================================
# 🔐 LOGIN FULLSCREEN (versione finale)
# =====================================
def do_login_fullscreen():
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    st.markdown("""
    <style>
    div[data-testid="stAppViewContainer"] {padding-top:0 !important;}
    .block-container {
        display:flex;flex-direction:column;justify-content:center;
        align-items:center;height:100vh;background-color:#f8fafc;
    }
    .login-card {
        background:#fff;border:1px solid #e5e7eb;border-radius:12px;
        box-shadow:0 4px 16px rgba(0,0,0,0.08);
        padding:2rem 2.5rem;width:360px;text-align:center;
    }
    .login-title {font-size:1.3rem;font-weight:600;color:#2563eb;margin:1rem 0 1.4rem;}
    .stButton>button {
        width:260px;font-size:0.9rem;background-color:#2563eb;color:white;
        border:none;border-radius:6px;padding:0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.image("https://www.shtsrl.com/template/images/logo.png", width=140)
    st.markdown("<div class='login-title'>Accedi al CRM SHT</div>", unsafe_allow_html=True)

    username = st.text_input("Nome utente").strip().lower()
    password = st.text_input("Password", type="password")
    login_btn = st.button("Entra")
    st.markdown("</div>", unsafe_allow_html=True)

    if login_btn and username and password:
        users = st.secrets["auth"]["users"]
        if username in users and users[username]["password"] == password:
            st.session_state.update({
                "user": username,
                "role": users[username].get("role", "viewer"),
                "logged_in": True
            })
            st.success(f"✅ Benvenuto {username}")
            st.rerun()
        else:
            st.error("❌ Credenziali non valide.")
    st.stop()


# =====================================
# 🚀 MAIN APP (robusta, senza CSV locali)
# =====================================
def main():
    st.write("🚀 Avvio funzione main()...")

    global LOGO_URL
    LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

    # --- LOGIN ---
    user, role = do_login_fullscreen()
    st.write(f"✅ Login completato — utente: {user}, ruolo: {role}")

    if not user:
        st.stop()

    # --- Ruoli e diritti ---
    if user in ["fabio", "emanuela", "claudia"]:
        ruolo_scrittura = "full"
    else:
        ruolo_scrittura = "limitato"

    # --- Scelta visibilità ---
    if user in ["fabio", "giulia", "antonella"]:
        visibilita_opzioni = ["Miei", "Tutti"]
        visibilita_scelta = st.sidebar.radio("📂 Visualizza clienti di:", visibilita_opzioni, index=0)
    else:
        visibilita_scelta = "Miei"

    # --- Caricamento dati da Supabase ---
    df_cli_main, df_ct_main = carica_dati_supabase(user)

    if df_cli_main.empty or df_ct_main.empty:
        st.warning("⚠️ Nessun dato trovato su Supabase. L'app si aprirà in modalità vuota.")
        df_cli_main, df_ct_main = pd.DataFrame(), pd.DataFrame()


    # --- Applica filtro visibilità ---
    df_cli, df_ct = df_cli_main, df_ct_main
    if visibilita_scelta == "Tutti" and user == "fabio":
        try:
            # Carica tutti i record, senza filtro per owner
            all_cli = supabase.table("clienti").select("*").execute().data
            all_ct = supabase.table("contratti").select("*").execute().data
            df_cli = normalize_columns(pd.DataFrame(all_cli)).fillna("")
            df_ct = normalize_columns(pd.DataFrame(all_ct)).fillna("")
        except Exception as e:
            st.warning(f"⚠️ Errore caricamento vista 'Tutti': {e}")

    # --- Fix date invertite una sola volta ---
    if not st.session_state.get("_date_fix_done", False):
        try:
            for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
                if c in df_cli.columns:
                    df_cli[c] = fix_inverted_dates(df_cli[c], col_name=c)
            for c in ["DataInizio", "DataFine"]:
                if c in df_ct.columns:
                    df_ct[c] = fix_inverted_dates(df_ct[c], col_name=c)
            st.session_state["_date_fix_done"] = True
        except Exception as e:
            st.warning(f"⚠️ Correzione automatica date non completata: {e}")

    # --- Sidebar info ---
    st.sidebar.success(f"👤 {user} — Ruolo: {role}")
    st.sidebar.info(f"📂 Vista: {visibilita_scelta}")

    # --- Routing tra pagine ---
    st.write("📦 Dati caricati —", len(df_cli), "clienti,", len(df_ct), "contratti")

    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti,
    }

    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()), index=0)
    if "nav_target" in st.session_state:
        target = st.session_state.pop("nav_target")
        if target in PAGES:
            page = target

    # --- Esegui pagina selezionata ---
    if page in PAGES:
        PAGES[page](df_cli, df_ct, ruolo_scrittura)
