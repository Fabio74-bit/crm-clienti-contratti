from fpdf import FPDF

def generate_pdf_table(df: pd.DataFrame, title: str = "Contratti") -> bytes:
    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 12)
            self.cell(0, 10, title, ln=1, align="C")
            self.ln(2)

    pdf = PDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_font("Arial", size=9)

    # Define column widths
    col_widths = [30, 25, 25, 20, 90, 20, 20, 25, 20]
    columns = [
        "NumeroContratto", "DataInizio", "DataFine", "Durata",
        "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
    ]

    # Header
    for i, col in enumerate(columns):
        pdf.cell(col_widths[i], 8, col, border=1)
    pdf.ln()

    # Rows
    for _, row in df.iterrows():
        for i, col in enumerate(columns):
            text = str(row.get(col, ""))
            if col == "DescrizioneProdotto":
                pdf.multi_cell(col_widths[i], 6, text, border=1, ln=3, max_line_height=pdf.font_size)
            else:
                pdf.cell(col_widths[i], 6, text, border=1)
        pdf.ln()
    return pdf.output(dest="S").encode("latin-1")
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("Contratti")

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    pre = st.session_state.get("selected_client_id")
    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    idx = 0
    if pre:
        try:
            idx = int(df_cli.index[df_cli["ClienteID"].astype(str)==str(pre)][0])
        except Exception:
            idx = 0
    sel_label = st.selectbox("Cliente", labels.tolist(), index=idx if idx < len(labels) else 0)
    sel_id = str(df_cli.iloc[labels[labels==sel_label].index[0]]["ClienteID"])
    ragione = df_cli[df_cli["ClienteID"].astype(str)==sel_id].iloc[0].get("RagioneSociale","")

    st.caption(f"Contratti di **{ragione}**")

    with st.expander("+ Nuovo contratto", expanded=False):
        with st.form("frm_new_contract"):
            c1, c2, c3 = st.columns(3)
            with c1:
                num = st.text_input("Numero contratto", "")
            with c2:
                din = st.text_input("Data inizio (dd/mm/aaaa)", "")
            with c3:
                dfi = st.text_input("Data fine (dd/mm/aaaa)", "")
            c4, c5, c6 = st.columns(3)
            with c4:
                durata = st.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            with c5:
                nol_fin = st.text_input("NOL_FIN", "")
            with c6:
                nol_int = st.text_input("NOL_INT", "")
            desc = st.text_area("Descrizione prodotto", "", height=100)
            tot = st.text_input("TotRata", "")
            submitted = st.form_submit_button("Crea contratto")
            if submitted:
                di = as_date(din)
                df = as_date(dfi)
                if pd.isna(di) and din.strip():
                    st.error("Formato Data inizio non valido (usa dd/mm/aaaa).")
                    st.stop()
                if pd.isna(df) and dfi.strip():
                    st.error("Formato Data fine non valido (usa dd/mm/aaaa).")
                    st.stop()

                new = {
                    "ClienteID": sel_id,
                    "NumeroContratto": num.strip(),
                    "DataInizio": di,
                    "DataFine": df,
                    "Durata": durata,
                    "DescrizioneProdotto": desc.strip(),
                    "NOL_FIN": nol_fin.strip(),
                    "NOL_INT": nol_int.strip(),
                    "TotRata": tot.strip(),
                    "Stato": "aperto",
                }
                df_ct = pd.concat([df_ct, pd.DataFrame([new])], ignore_index=True)
                save_contratti(df_ct)
                st.success("Contratto creato.")
                st.rerun()
    # ================= Elenco contratti (tabella + anteprima + azioni)
    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    closed_mask = ct["Stato"].str.lower() == "chiuso"

    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    disp["TotRata"] = disp["TotRata"].apply(money)

    cols = ["NumeroContratto", "DataInizio", "DataFine", "Durata",
            "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"]
    disp = disp[cols]

    st.markdown("### Elenco contratti")
    st.markdown(html_table(disp, closed_mask=closed_mask), unsafe_allow_html=True)

    st.markdown("#### Anteprima descrizione (seleziona una riga)")
    opzioni = [f"{fmt_date(r['DataInizio'])} / {r['NumeroContratto'] or ''}" for _, r in ct.iterrows()]
    if opzioni:
        scelta = st.selectbox("", opzioni, label_visibility="collapsed")
        idx_sel = opzioni.index(scelta)
        riga = ct.iloc[idx_sel]
        st.info(riga.get("DescrizioneProdotto", "Nessuna descrizione."))

    st.divider()

    st.markdown("### Azioni")
    idx_to_label = {i: f"{fmt_date(r['DataInizio'])} — {r.get('NumeroContratto','')}" for i, r in ct.iterrows()}
    if idx_to_label:
        i_sel = st.selectbox("Seleziona riga", list(idx_to_label.keys()), format_func=lambda k: idx_to_label[k])
        curr = (ct.loc[i_sel, "Stato"] or "aperto").lower()
        c1, c2, c3 = st.columns(3)
        with c1:
            if curr == "chiuso":
                if st.button("Riapri contratto"):
                    df_ct.loc[i_sel, "Stato"] = "aperto"
                    save_contratti(df_ct)
                    st.success("Contratto riaperto.")
                    st.rerun()
            else:
                if st.button("Chiudi contratto"):
                    df_ct.loc[i_sel, "Stato"] = "chiuso"
                    save_contratti(df_ct)
                    st.success("Contratto chiuso.")
                    st.rerun()
        with c2:
            csv = disp.to_csv(index=False).encode("utf-8-sig")
            st.download_button("Esporta tutti i contratti (Excel)", data=csv,
                               file_name=f"contratti_cliente_{sel_id}.csv",
                               mime="text/csv")
        with c3:
            csv_row = disp.iloc[[list(ct.index).index(i_sel)]].to_csv(index=False).encode("utf-8-sig")
            st.download_button("Esporta riga selezionata", data=csv_row,
                               file_name=f"contratto_{ct.loc[i_sel,'NumeroContratto'] or 'selezione'}.csv",
                               mime="text/csv")

    # PDF EXPORT
    from fpdf import FPDF

    class PDF(FPDF):
        def header(self):
            self.set_font("Arial", "B", 12)
            self.cell(0, 10, f"Contratti – {ragione}", ln=1, align="C")
            self.ln(4)

    def generate_pdf_table(df: pd.DataFrame) -> bytes:
        pdf = PDF(orientation="L", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=10)
        pdf.set_font("Arial", size=9)

        col_widths = [30, 25, 25, 20, 90, 20, 20, 25, 20]
        columns = [
            "NumeroContratto", "DataInizio", "DataFine", "Durata",
            "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"
        ]

        for i, col in enumerate(columns):
            pdf.cell(col_widths[i], 8, col, border=1)
        pdf.ln()

        for _, row in df.iterrows():
            for i, col in enumerate(columns):
                text = str(row.get(col, ""))
                if col == "DescrizioneProdotto":
                    pdf.multi_cell(col_widths[i], 6, text, border=1, ln=3, max_line_height=pdf.font_size)
                else:
                    pdf.cell(col_widths[i], 6, text, border=1)
            pdf.ln()
        return pdf.output(dest="S").encode("latin-1")

    st.markdown("### 📄 Esporta PDF")
    if st.button("Scarica PDF A4 Orizzontale"):
        pdf_bytes = generate_pdf_table(disp)
        st.download_button("Download PDF", data=pdf_bytes,
                           file_name=f"contratti_{sel_id}.pdf",
                           mime="application/pdf")
# ==========================
# APP
# ==========================

def main():
    st.set_page_config(page_title="SHT – Gestionale", layout="wide")
    st.markdown(f"<h3 style='margin-top:8px'>{APP_TITLE}</h3>", unsafe_allow_html=True)

    # login
    user, role = do_login()
    if user and role:
        st.sidebar.success(f"Utente: {user} — Ruolo: {role}")
    else:
        st.sidebar.info("Accesso come ospite")

    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
    }
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("Menu", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)

    df_cli = load_clienti()
    df_ct  = load_contratti()

    PAGES[page](df_cli, df_ct, role)

if __name__ == "__main__":
    main()
