# =====================================
# utils/dashboard.py — Dashboard Operativa 2025 (migliorata)
# =====================================
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.formatting import fmt_date
from utils.data_io import save_clienti, save_contratti

LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"
DURATE_MESI = [12, 24, 36, 48, 60]


# =====================================
# DASHBOARD OPERATIVA PRINCIPALE
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=130)
    st.markdown("<h2>📋 Dashboard Operativa — Gestionale SHT</h2>", unsafe_allow_html=True)
    st.divider()

    # === SEZIONE: CREAZIONE NUOVO CLIENTE + CONTRATTO ===
    with st.expander("➕ Crea Nuovo Cliente + Contratto", expanded=False):
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

            if st.form_submit_button("💾 Crea Cliente e Contratto", use_container_width=True):
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
                    st.session_state.update({
                        "selected_cliente": new_id,
                        "nav_target": "Contratti",
                        "_go_contratti_now": True
                    })
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Errore creazione cliente: {e}")

    # === CONTRATTI IN SCADENZA ENTRO 6 MESI ===
    st.divider()
    st.markdown("### ⏳ Contratti in scadenza entro 6 mesi")

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
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        scadenze = scadenze.sort_values("DataFine")
        st.markdown(f"📅 **{len(scadenze)} contratti in scadenza entro 6 mesi:**")

        for i, r in scadenze.iterrows():
            bg = "#f9fafb" if i % 2 == 0 else "#ffffff"
            col1, col2, col3, col4, col5 = st.columns([2.5, 1.2, 1.2, 1, 0.8])
            with col1:
                st.markdown(f"<div style='background:{bg};padding:6px'><b>{r.get('RagioneSociale','—')}</b></div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('NumeroContratto','—')}</div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('DataFine','—')}</div>", unsafe_allow_html=True)
            with col4:
                st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('Stato','—')}</div>", unsafe_allow_html=True)
            with col5:
                if st.button("📂 Apri", key=f"open_scad_{i}", use_container_width=True):
                    for k in list(st.session_state.keys()):
                        if k.startswith("edit_ct_") or k.startswith("edit_cli_"):
                            del st.session_state[k]
                    st.session_state.update({
                        "selected_cliente": str(r.get("ClienteID")),
                        "nav_target": "Contratti",
                        "_go_contratti_now": True
                    })
                    st.rerun()

    # === CONTRATTI SENZA DATA FINE ===
    st.divider()
    st.markdown("### ⚠️ Contratti recenti senza data di fine")

    oggi = pd.Timestamp.now().normalize()
    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)

    contratti_senza_fine = df_ct[
        (df_ct["DataFine"].isna()) &
        (df_ct["DataInizio"].notna()) &
        (df_ct["DataInizio"] >= oggi - pd.DateOffset(days=7))
    ].copy()

    if contratti_senza_fine.empty:
        st.success("✅ Tutti i contratti recenti hanno una data di fine.")
    else:
        st.warning(f"⚠️ {len(contratti_senza_fine)} contratti inseriti di recente non hanno ancora una data di fine:")

        for i, r in contratti_senza_fine.iterrows():
            bg = "#fff9f0" if i % 2 == 0 else "#ffffff"
            col1, col2, col3, col4, col5 = st.columns([2.5, 1.2, 1.2, 2.5, 0.8])
            with col1:
                st.markdown(f"<div style='background:{bg};padding:6px'><b>{r.get('RagioneSociale','—')}</b></div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div style='background:{bg};padding:6px'>{r.get('NumeroContratto','—')}</div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div style='background:{bg};padding:6px'>{fmt_date(r.get('DataInizio'))}</div>", unsafe_allow_html=True)
            with col4:
                desc = str(r.get('DescrizioneProdotto', '—'))
                if len(desc) > 60:
                    desc = desc[:60] + "…"
                st.markdown(f"<div style='background:{bg};padding:6px'>{desc}</div>", unsafe_allow_html=True)
            with col5:
                if st.button("📂 Apri", key=f"open_ndf_{i}", use_container_width=True):
                    for k in list(st.session_state.keys()):
                        if k.startswith("edit_ct_") or k.startswith("edit_cli_"):
                            del st.session_state[k]
                    st.session_state.update({
                        "selected_cliente": str(r.get("ClienteID")),
                        "nav_target": "Contratti",
                        "_go_contratti_now": True
                    })
                    st.rerun()
