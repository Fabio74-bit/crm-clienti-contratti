# =====================================
# utils/dashboard.py — nuova dashboard grafica SHT 2025
# =====================================
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.formatting import fmt_date
from utils.exports import export_excel_contratti, export_pdf_contratti
import plotly.express as px

# =====================================
# KPI CARD — migliorata
# =====================================
def kpi_card(label: str, value, icon: str, color: str):
    st.markdown(f"""
    <div style="
        background-color:{color};
        padding:22px;
        border-radius:14px;
        text-align:center;
        color:white;
        box-shadow:0 3px 12px rgba(0,0,0,0.12);
    ">
        <div style="font-size:30px;">{icon}</div>
        <div style="font-size:26px;font-weight:700;">{value}</div>
        <div style="font-size:15px;">{label}</div>
    </div>
    """, unsafe_allow_html=True)

# =====================================
# DASHBOARD PRINCIPALE
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image("https://www.shtsrl.com/template/images/logo.png", width=130)
    st.markdown("<h2 style='margin-top:10px;'>📊 Dashboard Gestionale SHT</h2>", unsafe_allow_html=True)
    st.divider()

    # === KPI principali ===
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())

    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    now = pd.Timestamp.now().normalize()
    new_contracts = df_ct[
        (df_ct["DataInizio"].notna()) &
        (df_ct["DataInizio"] >= pd.Timestamp(year=now.year, month=1, day=1))
    ]

    col1, col2, col3, col4 = st.columns(4)
    kpi_card("Clienti attivi", total_clients, "👥", "#1976D2")
    kpi_card("Contratti attivi", active_contracts, "📄", "#388E3C")
    kpi_card("Contratti chiusi", closed_contracts, "❌", "#D32F2F")
    kpi_card("Nuovi contratti anno", len(new_contracts), "⭐", "#FBC02D")
    st.divider()

    # === GRAFICO 1: Contratti per TMK ===
    st.markdown("### 👩‍💼 Contratti per TMK")
    if "TMK" in df_cli.columns and not df_cli.empty:
        df_tmk = (
            df_cli["TMK"]
            .fillna("Non assegnato")
            .value_counts()
            .reset_index()
            .rename(columns={"index": "TMK", "TMK": "Totale"})
        )
        fig_tmk = px.bar(df_tmk, x="TMK", y="Totale", color="TMK",
                         color_discrete_sequence=px.colors.qualitative.Vivid,
                         text_auto=True)
        fig_tmk.update_layout(height=380, title="", xaxis_title="", yaxis_title="Numero Clienti")
        st.plotly_chart(fig_tmk, use_container_width=True)
    else:
        st.info("Nessun dato TMK disponibile.")

    # === GRAFICO 2: Stato contratti (aperti/chiusi) ===
    st.markdown("### 🟢 Stato dei contratti")
    df_stato = df_ct["Stato"].fillna("Non definito").value_counts().reset_index()
    df_stato.columns = ["Stato", "Totale"]
    fig_stato = px.pie(df_stato, names="Stato", values="Totale",
                       color_discrete_sequence=px.colors.qualitative.Pastel)
    fig_stato.update_traces(textinfo="label+percent", pull=[0.1 if s.lower() == "chiuso" else 0 for s in df_stato["Stato"]])
    st.plotly_chart(fig_stato, use_container_width=True)

    # === GRAFICO 3: Contratti per mese (timeline) ===
    st.markdown("### 📆 Contratti per mese (ultimo anno)")
    df_ct_valid = df_ct[df_ct["DataInizio"].notna()].copy()
    df_ct_valid["Mese"] = df_ct_valid["DataInizio"].dt.to_period("M").astype(str)
    df_trend = df_ct_valid.groupby("Mese").size().reset_index(name="Totale")
    fig_trend = px.line(df_trend, x="Mese", y="Totale", markers=True,
                        line_shape="spline", color_discrete_sequence=["#2563EB"])
    fig_trend.update_layout(height=350, yaxis_title="Nuovi contratti", xaxis_title="")
    st.plotly_chart(fig_trend, use_container_width=True)

    # === INSIGHT RAPIDO ===
    st.divider()
    st.markdown("### ⚙️ Insight rapidi")
    st.info(f"""
    • 📈 {len(new_contracts)} nuovi contratti nel {now.year}  
    • 🏙️ {df_cli['Citta'].nunique()} città servite  
    • 💼 Totale clienti registrati: **{total_clients}**  
    • ⏰ Ultimo aggiornamento: {datetime.now().strftime("%d/%m/%Y %H:%M")}
    """)

    st.divider()
    st.caption("© 2025 SHT Gestionale CRM — versione dashboard grafica")

