# =====================================
# utils/dashboard_grafica.py — Dashboard Grafica SHT 2025
# =====================================
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from utils.formatting import fmt_date

LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"


# =====================================
# CARD KPI — elementi riassuntivi
# =====================================
def kpi_card(label: str, value, icon: str, color: str):
    return f"""
    <div style="
        background-color:{color};
        padding:20px;
        border-radius:16px;
        text-align:center;
        color:white;
        box-shadow:0 3px 12px rgba(0,0,0,0.12);
        min-height:120px;
    ">
        <div style="font-size:28px;">{icon}</div>
        <div style="font-size:26px;font-weight:700;margin-top:6px;">{value}</div>
        <div style="font-size:15px;margin-top:2px;">{label}</div>
    </div>
    """


# =====================================
# PAGINA: DASHBOARD GRAFICA
# =====================================
def page_dashboard_grafica(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=130)
    st.markdown("<h2>📊 Dashboard Grafica — Analisi Contratti</h2>", unsafe_allow_html=True)
    st.divider()

    # --- Calcolo KPI ---
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
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#2563EB"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#16A34A"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#DC2626"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Nuovi contratti anno", len(new_contracts), "⭐", "#FACC15"), unsafe_allow_html=True)
    st.divider()

    # --- GRAFICO 1: Contratti per TMK ---
    col1, col2 = st.columns(2)
    with col1:
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

    # --- GRAFICO 2: Stato contratti ---
    with col2:
        st.markdown("### 🟢 Stato contratti")
        df_stato = df_ct["Stato"].fillna("Non definito").value_counts().reset_index()
        df_stato.columns = ["Stato", "Totale"]
        fig_stato = px.pie(df_stato, names="Stato", values="Totale",
                           color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_stato.update_traces(textinfo="label+percent", pull=[0.1 if s.lower()=="chiuso" else 0 for s in df_stato["Stato"]])
        st.plotly_chart(fig_stato, use_container_width=True)

    # --- GRAFICO 3: Contratti per mese ---
    st.markdown("### 📆 Nuovi contratti per mese (ultimo anno)")
    df_ct_valid = df_ct[df_ct["DataInizio"].notna()].copy()
    df_ct_valid["Mese"] = df_ct_valid["DataInizio"].dt.to_period("M").astype(str)
    df_trend = df_ct_valid.groupby("Mese").size().reset_index(name="Totale")
    fig_trend = px.line(df_trend, x="Mese", y="Totale", markers=True,
                        line_shape="spline", color_discrete_sequence=["#2563EB"])
    fig_trend.update_layout(height=350, yaxis_title="Contratti", xaxis_title="")
    st.plotly_chart(fig_trend, use_container_width=True)

    st.divider()

    # --- SEZIONE INSIGHT ---
    st.markdown("### ⚙️ Insight Rapidi")
    cinfo1, cinfo2 = st.columns(2)
    with cinfo1:
        st.success(f"📈 Nuovi contratti nel {now.year}: {len(new_contracts)}")
        st.info(f"🏙️ Città servite: {df_cli['Citta'].nunique()}")
    with cinfo2:
        st.warning(f"💼 Totale clienti registrati: {total_clients}")
        st.info(f"⏰ Ultimo aggiornamento: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
