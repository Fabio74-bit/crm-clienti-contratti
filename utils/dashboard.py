# =====================================
# utils/dashboard.py — Dashboard Avanzata 2025 (completa)
# =====================================
import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
from utils.formatting import fmt_date
from utils.exports import export_excel_contratti, export_pdf_contratti
from utils.data_io import save_clienti, save_contratti

LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"
DURATE_MESI = [12, 24, 36, 48, 60]


# =====================================
# KPI CARD — grafica moderna
# =====================================
def kpi_card(label: str, value, icon: str, color: str):
    return f"""
    <div style="
        background-color:{color};
        padding:20px;
        border-radius:14px;
        text-align:center;
        color:white;
        box-shadow:0 3px 12px rgba(0,0,0,0.12);
    ">
        <div style="font-size:30px;">{icon}</div>
        <div style="font-size:26px;font-weight:700;">{value}</div>
        <div style="font-size:15px;">{label}</div>
    </div>
    """


# =====================================
# DASHBOARD COMPLETA
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=130)
    st.markdown("<h2>📊 Dashboard Avanzata SHT 2025</h2>", unsafe_allow_html=True)
    st.divider()

    # === KPI principali ===
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

    # === GRAFICI ===
    colg1, colg2 = st.columns(2)

    with colg1:
        st.markdown("### 👩‍💼 Contratti per TMK")
        if "TMK" in df_cli.columns and not df_cli.empty:
            df_tmk = df_cli["TMK"].fillna("Non assegnato").value_counts().reset_index()
            df_tmk.columns = ["TMK", "Totale"]
            fig_tmk = px.bar(df_tmk, x="TMK", y="Totale", color="TMK",
                             color_discrete_sequence=px.colors.qualitative.Vivid, text_auto=True)
            fig_tmk.update_layout(height=350, xaxis_title="", yaxis_title="Clienti", showlegend=False)
            st.plotly_chart(fig_tmk, use_container_width=True)
        else:
            st.info("Nessun dato TMK disponibile.")

    with colg2:
        st.markdown("### 🟢 Stato contratti")
        df_stato = df_ct["Stato"].fillna("Non definito").value_counts().reset_index()
        df_stato.columns = ["Stato", "Totale"]
        fig_stato = px.pie(df_stato, names="Stato", values="Totale",
                           color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_stato.update_traces(textinfo="label+percent", pull=[0.1 if s.lower()=="chiuso" else 0 for s in df_stato["Stato"]])
        st.plotly_chart(fig_stato, use_container_width=True)

    st.markdown("### 📆 Contratti per mese (ultimo anno)")
    df_ct_valid = df_ct[df_ct["DataInizio"].notna()].copy()
    df_ct_valid["Mese"] = df_ct_valid["DataInizio"].dt.to_period("M").astype(str)
    df_trend = df_ct_valid.groupby("Mese").size().reset_index(name="Totale")
    fig_trend = px.line(df_trend, x="Mese", y="Totale", markers=True,
                        line_shape="spline", color_discrete_sequence=["#2563EB"])
    fig_trend.update_layout(height=350, yaxis_title="Nuovi contratti", xaxis_title="")
    st.plotly_chart(fig_trend, use_container_width=True)

    st.divider()
    st.markdown("### ⚙️ Insight rapidi")
    st.info(f"""
    • 📈 {len(new_contracts)} nuovi contratti nel {now.year}  
    • 🏙️ {df_cli['Citta'].nunique()} città servite  
    • 💼 Totale clienti registrati: **{total_clients}**  
    • ⏰ Ultimo aggiornamento: {datetime.now().strftime("%d/%m/%Y %H:%M")}
    """)

    # === SEZIONE OPERATIVA ===
    st.divider()
    st.markdown("## 🧾 Sezione Operativa")

    # --- Crea nuovo cliente + contratto ---
    with st.expander("➕ Crea Nuovo Cliente + Contratto"):
        with st.form("frm_new_cliente"):
            st.markdown("#### 📇 Dati Cliente")
            col1, col2 = st.columns(2)
            with col1:
                ragione = st.text_input("🏢 Ragione Sociale")
                persona = st.text_input("👤 Persona Riferimento")
                indirizzo = st.text_input("📍 Indirizzo")
                citta = st.text_input("🏙️ Città")
                cap = st.text_input("📮 CAP")
                telefono = st.text_input("📞 Telefono")
                cell = st.text_input("📱 Cellulare")
            with col2:
                email = st.text_input("✉️ Email")
                piva = st.text_input("💼 Partita IVA")
                iban = st.text_input("🏦 IBAN")
                sdi = st.text_input("📡 SDI")
                note = st.text_area("📝 Note Cliente", height=70)
                tmk = st.selectbox(
                    "👩‍💼 TMK di riferimento",
                    ["", "Giulia", "Antonella", "Annalisa", "Laura"],
                    index=0
                )

            st.markdown("#### 📄 Primo Contratto del Cliente")
            colc1, colc2, colc3 = st.columns(3)
            num = colc1.text_input("📄 Numero Contratto")
            data_inizio = colc2.date_input("📅 Data Inizio", format="DD/MM/YYYY")
            durata = colc3.selectbox("📆 Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("🧾 Descrizione Prodotto", height=80)
            colp1, colp2, colp3 = st.columns(3)
            nf = colp1.text_input("🏦 NOL_FIN")
            ni = colp2.text_input("🏢 NOL_INT")
            tot = colp3.text_input("💰 Tot Rata")
            colx1, colx2, colx3, colx4 = st.columns(4)
            copie_bn = colx1.text_input("📄 Copie incluse B/N", value="", key="copie_bn")
            ecc_bn = colx2.text_input("💰 Costo extra B/N (€)", value="", key="ecc_bn")
            copie_col = colx3.text_input("🖨️ Copie incluse Colore", value="", key="copie_col")
            ecc_col = colx4.text_input("💰 Costo extra Colore (€)", value="", key="ecc_col")

            if st.form_submit_button("💾 Crea Cliente e Contratto"):
                try:
                    new_id = str(len(df_cli) + 1)
                    nuovo_cliente = {
                        "ClienteID": new_id,
                        "RagioneSociale": ragione,
                        "PersonaRiferimento": persona,
                        "Indirizzo": indirizzo,
                        "Citta": citta,
                        "CAP": cap,
                        "Telefono": telefono,
                        "Cell": cell,
                        "Email": email,
                        "PartitaIVA": piva,
                        "IBAN": iban,
                        "SDI": sdi,
                        "UltimoRecall": "",
                        "ProssimoRecall": "",
                        "UltimaVisita": "",
                        "ProssimaVisita": "",
                        "TMK": tmk,
                        "NoteCliente": note
                    }
                    df_cli = pd.concat([df_cli, pd.DataFrame([nuovo_cliente])], ignore_index=True)
                    save_clienti(df_cli)

                    data_fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))
                    nuovo_contratto = {
                        "ClienteID": new_id,
                        "RagioneSociale": ragione,
                        "NumeroContratto": num,
                        "DataInizio": fmt_date(data_inizio),
                        "DataFine": fmt_date(data_fine),
                        "Durata": durata,
                        "DescrizioneProdotto": desc,
                        "NOL_FIN": nf,
                        "NOL_INT": ni,
                        "TotRata": tot,
                        "CopieBN": copie_bn,
                        "EccBN": ecc_bn,
                        "CopieCol": copie_col,
                        "EccCol": ecc_col,
                        "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([nuovo_contratto])], ignore_index=True)
                    save_contratti(df_ct)

                    st.success(f"✅ Cliente '{ragione}' e contratto creati correttamente!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore creazione cliente: {e}")

    # --- Contratti in scadenza ---
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
        st.success("✅ Nessun contratto attivo in scadenza nei prossimi 6 mesi.")
    else:
        st.warning(f"📅 {len(scadenze)} contratti in scadenza entro 6 mesi:")
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        st.dataframe(scadenze[["RagioneSociale", "NumeroContratto", "DataFine", "Stato"]])

    # --- Contratti senza data fine ---
    st.divider()
    st.markdown("### ⚠️ Contratti recenti senza data di fine")
    contratti_senza_fine = df_ct[
        (df_ct["DataFine"].isna()) &
        (df_ct["DataInizio"].notna()) &
        (df_ct["DataInizio"] >= oggi)
    ].copy()

    if contratti_senza_fine.empty:
        st.success("✅ Tutti i contratti recenti hanno una data di fine.")
    else:
        st.warning(f"⚠️ {len(contratti_senza_fine)} contratti inseriti da oggi non hanno ancora una data di fine:")
        contratti_senza_fine["DataInizio"] = contratti_senza_fine["DataInizio"].apply(fmt_date)
        st.dataframe(contratti_senza_fine[["RagioneSociale", "NumeroContratto", "DataInizio", "DescrizioneProdotto"]])
