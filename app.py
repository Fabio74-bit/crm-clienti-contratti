# =====================================
# app.py — Gestionale Clienti SHT (VERSIONE 2025 OTTIMIZZATA)
# =====================================
from __future__ import annotations
import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
from fpdf import FPDF
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from docx import Document
from docx.shared import Pt

# =====================================
# CONFIGURAZIONE STREAMLIT E STILE BASE
# =====================================
st.set_page_config(page_title="GESTIONALE CLIENTI – SHT", layout="wide")

st.markdown("""
<style>
.block-container {
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 100% !important;
}
section.main > div:first-child {
    margin-top: 0 !important;
    padding-top: 0 !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<script>
    window.addEventListener('load', function() {
        window.scrollTo(0, 0);
    });
</script>
""", unsafe_allow_html=True)

# =====================================
# COSTANTI GLOBALI
# =====================================
APP_TITLE = "GESTIONALE CLIENTI – SHT"
LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"
STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATES_DIR = Path("templates")  # <- cartella accanto ad app.py
DURATE_MESI = ["12", "24", "36", "48", "60", "72"]

# =====================================
# FUNZIONI UTILITY
# =====================================
def fmt_date(d) -> str:
    """Ritorna una data in formato DD/MM/YYYY"""
    import datetime as dt
    if d in (None, "", "nan", "NaN"):
        return ""
    try:
        if isinstance(d, (dt.date, dt.datetime, pd.Timestamp)):
            return pd.to_datetime(d).strftime("%d/%m/%Y")
        parsed = pd.to_datetime(str(d), errors="coerce", dayfirst=True)
        return "" if pd.isna(parsed) else parsed.strftime("%d/%m/%Y")
    except Exception:
        return ""

def money(x):
    """Formatta numeri in valuta italiana"""
    try:
        v = float(pd.to_numeric(x, errors="coerce"))
        if pd.isna(v): return ""
        return f"{v:,.2f} €"
    except Exception:
        return ""

def safe_text(txt):
    """Rimuove caratteri non compatibili con PDF latin-1"""
    if pd.isna(txt) or txt is None: return ""
    s = str(txt)
    replacements = {"€": "EUR", "–": "-", "—": "-", "“": '"', "”": '"', "‘": "'", "’": "'"}
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")

def ensure_columns(df, cols):
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]

# =====================================
# CARICAMENTO E SALVATAGGIO DATI
# =====================================
def load_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    if path.exists():
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(path, index=False, encoding="utf-8-sig")
    df = ensure_columns(df, cols)
    return df

def save_csv(df: pd.DataFrame, path: Path, date_cols=None):
    out = df.copy()
    if date_cols:
        for c in date_cols:
            out[c] = out[c].apply(fmt_date)
    out.to_csv(path, index=False, encoding="utf-8-sig")

def load_clienti():
    cols = [
        "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
        "Telefono","Cell","Email","PartitaIVA","IBAN","SDI",
        "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","NoteCliente"
    ]
    return load_csv(CLIENTI_CSV, cols)

def load_contratti():
    cols = [
        "ClienteID","RagioneSociale","NumeroContratto","DataInizio","DataFine","Durata",
        "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","CopieBN","EccBN",
        "CopieCol","EccCol","Stato"
    ]
    return load_csv(CONTRATTI_CSV, cols)

def save_clienti(df): save_csv(df, CLIENTI_CSV, ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"])
def save_contratti(df): save_csv(df, CONTRATTI_CSV, ["DataInizio","DataFine"])

# =====================================
# LOGIN FULLSCREEN
# =====================================
def do_login_fullscreen():
    """Login elegante con sfondo fullscreen"""
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

    login_col1, login_col2, _ = st.columns([1,2,1])
    with login_col2:
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.image(LOGO_URL, width=140)
        st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)
        username = st.text_input("Nome utente", key="login_user").strip().lower()
        password = st.text_input("Password", type="password", key="login_pass")
        login_btn = st.button("Entra")
        st.markdown("</div>", unsafe_allow_html=True)

    if login_btn or (username and password and not st.session_state.get("_login_checked")):
        st.session_state["_login_checked"] = True
        users = st.secrets["auth"]["users"]
        if username in users and users[username]["password"] == password:
            st.session_state.update({
                "user": username,
                "role": users[username].get("role", "viewer"),
                "logged_in": True
            })
            st.success(f"✅ Benvenuto {username}!")
            time.sleep(0.3)
            st.rerun()
        else:
            st.error("❌ Credenziali non valide.")
            st.session_state["_login_checked"] = False

    st.stop()
# =====================================
# KPI CARD (riutilizzata)
# =====================================
def kpi_card(label: str, value, icon: str, color: str) -> str:
    return f"""
    <div style="
        background-color:{color};
        padding:18px;
        border-radius:12px;
        text-align:center;
        color:white;">
        <div style="font-size:26px;">{icon}</div>
        <div style="font-size:22px;font-weight:700;">{value}</div>
        <div style="font-size:14px;">{label}</div>
    </div>
    """

# =====================================
# PAGINA DASHBOARD
# =====================================
# =====================================
# PAGINA DASHBOARD
# =====================================
def page_dashboard(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📊 Dashboard Gestionale</h2>", unsafe_allow_html=True)
    st.divider()

    # === KPI principali ===
    stato = df_ct["Stato"].fillna("").astype(str).str.lower()
    total_clients = len(df_cli)
    active_contracts = int((stato != "chiuso").sum())
    closed_contracts = int((stato == "chiuso").sum())
    now = pd.Timestamp.now().normalize()

    df_ct["DataInizio"] = pd.to_datetime(df_ct["DataInizio"], errors="coerce", dayfirst=True)
    new_contracts = df_ct[(df_ct["DataInizio"].notna()) & (df_ct["DataInizio"] >= pd.Timestamp(year=now.year, month=1, day=1))]

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Clienti attivi", total_clients, "👥", "#1976D2"), unsafe_allow_html=True)
    c2.markdown(kpi_card("Contratti attivi", active_contracts, "📄", "#388E3C"), unsafe_allow_html=True)
    c3.markdown(kpi_card("Contratti chiusi", closed_contracts, "❌", "#D32F2F"), unsafe_allow_html=True)
    c4.markdown(kpi_card("Nuovi contratti anno", len(new_contracts), "⭐", "#FBC02D"), unsafe_allow_html=True)
    st.divider()

    # === CREAZIONE NUOVO CLIENTE + CONTRATTO ===
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

            st.markdown("#### 📄 Primo Contratto del Cliente")
            colc1, colc2, colc3 = st.columns(3)
            num = colc1.text_input("Numero Contratto")
            data_inizio = colc2.date_input("Data Inizio", format="DD/MM/YYYY")
            durata = colc3.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione Prodotto", height=80)
            colp1, colp2, colp3 = st.columns(3)
            nf = colp1.text_input("NOL_FIN")
            ni = colp2.text_input("NOL_INT")
            tot = colp3.text_input("Tot Rata")

            if st.form_submit_button("💾 Crea Cliente e Contratto"):
                try:
                    new_id = str(len(df_cli) + 1)
                    nuovo_cliente = {
                        "ClienteID": new_id, "RagioneSociale": ragione, "PersonaRiferimento": persona,
                        "Indirizzo": indirizzo, "Citta": citta, "CAP": cap,
                        "Telefono": telefono, "Cell": cell, "Email": email,
                        "PartitaIVA": piva, "IBAN": iban, "SDI": sdi,
                        "UltimoRecall": "", "ProssimoRecall": "", "UltimaVisita": "",
                        "ProssimaVisita": "", "NoteCliente": note
                    }
                    df_cli = pd.concat([df_cli, pd.DataFrame([nuovo_cliente])], ignore_index=True)
                    save_clienti(df_cli)

                    data_fine = pd.to_datetime(data_inizio) + pd.DateOffset(months=int(durata))
                    nuovo_contratto = {
                        "ClienteID": new_id, "RagioneSociale": ragione, "NumeroContratto": num,
                        "DataInizio": fmt_date(data_inizio), "DataFine": fmt_date(data_fine),
                        "Durata": durata, "DescrizioneProdotto": desc,
                        "NOL_FIN": nf, "NOL_INT": ni, "TotRata": tot, "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([nuovo_contratto])], ignore_index=True)
                    save_contratti(df_ct)

                    st.success(f"✅ Cliente '{ragione}' e contratto creati correttamente!")
                    st.session_state.update({"selected_cliente": new_id, "nav_target": "Contratti", "_go_contratti_now": True})
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore creazione cliente: {e}")

    st.divider()

    # === CONTRATTI IN SCADENZA ENTRO 6 MESI ===
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

    # Se manca RagioneSociale nei contratti, la aggiunge dal CSV clienti
    if "RagioneSociale" not in scadenze.columns:
        scadenze = scadenze.merge(df_cli[["ClienteID", "RagioneSociale"]], on="ClienteID", how="left")

    if scadenze.empty:
        st.success("✅ Nessun contratto attivo in scadenza nei prossimi 6 mesi.")
    else:
        scadenze["DataFine"] = scadenze["DataFine"].apply(fmt_date)
        scadenze = scadenze.sort_values("DataFine")

        st.markdown(f"**🔢 {len(scadenze)} contratti in scadenza entro 6 mesi:**")

        for i, r in scadenze.iterrows():
            rag = r.get("RagioneSociale", "—")
            num = r.get("NumeroContratto", "—")
            fine = r.get("DataFine", "—")
            stato = r.get("Stato", "—")

            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 0.8, 0.8])
            with col1: st.markdown(f"**{rag}**")
            with col2: st.markdown(num or "—")
            with col3: st.markdown(fine or "—")
            with col4: st.markdown(stato or "—")
            with col5:
                if st.button("📂 Apri", key=f"open_scad_{i}", use_container_width=True):
                    st.session_state.update({
                        "selected_cliente": r.get("ClienteID"),
                        "nav_target": "Contratti",
                        "_go_contratti_now": True
                    })
                    st.rerun()


# =====================================
# PAGINA CLIENTI (OTTIMIZZATA)
# =====================================
def page_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.subheader("📋 Gestione Clienti")

    # Pre-selezione cliente
    if "selected_cliente" in st.session_state:
        sel_id = str(st.session_state.pop("selected_cliente"))
        cli_ids = df_cli["ClienteID"].astype(str)
        if sel_id in set(cli_ids):
            riga = df_cli.loc[cli_ids == sel_id].iloc[0]
            st.session_state["cliente_selezionato"] = riga["RagioneSociale"]

    search_query = st.text_input("🔍 Cerca cliente per nome o ID", key="search_cli")
    if search_query:
        filtered = df_cli[
            df_cli["RagioneSociale"].str.contains(search_query, case=False, na=False) |
            df_cli["ClienteID"].astype(str).str.contains(search_query, na=False)
        ]
    else:
        filtered = df_cli

    if filtered.empty:
        st.warning("❌ Nessun cliente trovato.")
        return

    options = filtered["RagioneSociale"].tolist()
    selected_name = st.session_state.get("cliente_selezionato", options[0])
    sel_rag = st.selectbox("Seleziona Cliente", options, index=options.index(selected_name), key="sel_cli_box")

    cliente = filtered[filtered["RagioneSociale"] == sel_rag].iloc[0]
    sel_id = cliente["ClienteID"]

    st.markdown(f"## 🏢 {cliente['RagioneSociale']}")
    st.caption(f"ID Cliente: {sel_id}")

    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("📄 Contratti", use_container_width=True):
            st.session_state.update({"selected_cliente": sel_id, "nav_target": "Contratti", "_go_contratti_now": True})
            st.rerun()
        if st.button("✏️ Modifica", use_container_width=True, key=f"edit_{sel_id}"):
            st.session_state[f"edit_cli_{sel_id}"] = not st.session_state.get(f"edit_cli_{sel_id}", False)
            st.rerun()
        if role == "admin" and st.button("🗑️ Elimina", use_container_width=True, key=f"del_cli_{sel_id}"):
            st.warning(f"⚠️ Eliminare definitivamente **{cliente['RagioneSociale']}**?")
            if st.button("❌ Conferma", use_container_width=True, key=f"conf_del_{sel_id}"):
                df_cli = df_cli[df_cli["ClienteID"] != sel_id]
                df_ct = df_ct[df_ct["ClienteID"] != sel_id]
                save_clienti(df_cli); save_contratti(df_ct)
                st.success("✅ Cliente eliminato.")
                st.rerun()
# =====================================
# PAGINA CONTRATTI
# =====================================
def page_contratti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.markdown("<h2>📄 Contratti</h2>", unsafe_allow_html=True)

    if df_cli.empty:
        st.info("Nessun cliente presente.")
        return

    labels = df_cli.apply(lambda r: f"{r['ClienteID']} — {r['RagioneSociale']}", axis=1)
    cliente_ids = df_cli["ClienteID"].astype(str).tolist()

    selected_cliente_id = st.session_state.pop("selected_cliente", None)
    if selected_cliente_id and str(selected_cliente_id) in cliente_ids:
        sel_index = cliente_ids.index(str(selected_cliente_id))
    else:
        sel_index = 0

    sel_label = st.selectbox("Cliente", labels.tolist(), index=sel_index)
    sel_id = cliente_ids[labels.tolist().index(sel_label)]
    rag_soc = df_cli.loc[df_cli["ClienteID"] == sel_id, "RagioneSociale"].iloc[0]

    ct = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()

    # === NUOVO CONTRATTO ===
    with st.expander(f"➕ Nuovo contratto per «{rag_soc}»"):
        with st.form(f"frm_new_contract_{sel_id}"):
            c1, c2, c3 = st.columns(3)
            num = c1.text_input("Numero Contratto")
            din = c2.date_input("Data inizio", format="DD/MM/YYYY")
            durata = c3.selectbox("Durata (mesi)", DURATE_MESI, index=2)
            desc = st.text_area("Descrizione prodotto", height=100)
            nf, ni, tot = st.columns(3)
            nf = nf.text_input("NOL_FIN")
            ni = ni.text_input("NOL_INT")
            tot = tot.text_input("TotRata")
            if st.form_submit_button("💾 Crea contratto"):
                try:
                    data_fine = pd.to_datetime(din) + pd.DateOffset(months=int(durata))
                    new_row = {
                        "ClienteID": sel_id, "RagioneSociale": rag_soc, "NumeroContratto": num,
                        "DataInizio": fmt_date(din), "DataFine": fmt_date(data_fine),
                        "Durata": durata, "DescrizioneProdotto": desc,
                        "NOL_FIN": nf, "NOL_INT": ni, "TotRata": tot, "Stato": "aperto"
                    }
                    df_ct = pd.concat([df_ct, pd.DataFrame([new_row])], ignore_index=True)
                    save_contratti(df_ct)
                    st.success("✅ Contratto creato con successo.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore creazione contratto: {e}")

    if ct.empty:
        st.info("Nessun contratto per questo cliente.")
        return

    # === TABELLA CONTRATTI ===
    ct["Stato"] = ct["Stato"].replace("", "aperto").fillna("aperto")
    disp = ct.copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)
    for c in ["TotRata", "NOL_FIN", "NOL_INT"]:
        disp[c] = disp[c].apply(money)

    gb = GridOptionsBuilder.from_dataframe(disp)
    gb.configure_default_column(resizable=True, sortable=True, filter=True, wrapText=True, autoHeight=True)
    gb.configure_column("DescrizioneProdotto", wrapText=True, autoHeight=True, width=300)
    gb.configure_column("Stato", width=100)
    gb.configure_column("TotRata", width=110)
    gb.configure_column("DataInizio", width=110)
    gb.configure_column("DataFine", width=110)
    gb.configure_grid_options(getRowStyle=JsCode("""
        function(params) {
            if (!params.data.Stato) return {};
            const s = params.data.Stato.toLowerCase();
            if (s === 'chiuso') return {'backgroundColor': '#ffebee', 'color': '#b71c1c', 'fontWeight': 'bold'};
            if (s === 'aperto' || s === 'attivo') return {'backgroundColor': '#e8f5e9', 'color': '#1b5e20'};
            return {};
        }"""))
    st.markdown("### 📑 Elenco Contratti")
    AgGrid(disp, gridOptions=gb.build(), theme="balham", height=400, allow_unsafe_jscode=True)

    st.divider()
    c1, c2 = st.columns(2)

    # === EXPORT EXCEL ===
    with c1:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
        from openpyxl.utils import get_column_letter
        from io import BytesIO
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = f"Contratti {rag_soc}"
            ws.merge_cells("A1:M1")
            title = ws["A1"]
            title.value = f"Contratti - {rag_soc}"
            title.font = Font(size=12, bold=True, color="2563EB")
            title.alignment = Alignment(horizontal="center", vertical="center")
            ws.append([])
            headers = list(disp.columns)
            ws.append(headers)
            bold = Font(bold=True, color="FFFFFF")
            center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            thin = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
            fill = PatternFill("solid", fgColor="2563EB")
            for i, h in enumerate(headers, 1):
                c = ws.cell(row=2, column=i)
                c.font, c.fill, c.alignment, c.border = bold, fill, center, thin
            for _, r in disp.iterrows():
                ws.append([str(r.get(h, "")) for h in headers])
            for i in range(1, ws.max_column + 1):
                width = max(len(str(ws.cell(row=j, column=i).value)) for j in range(1, ws.max_row + 1)) + 2
                ws.column_dimensions[get_column_letter(i)].width = min(width, 50)
            bio = BytesIO(); wb.save(bio)
            st.download_button("📘 Esporta Excel", bio.getvalue(),
                               file_name=f"contratti_{rag_soc}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True, key=f"xlsx_{sel_id}")
        except Exception as e:
            st.error(f"❌ Errore export Excel: {e}")

    # === EXPORT PDF ===
    with c2:
        from io import BytesIO
        try:
            pdf = FPDF(orientation="L", unit="mm", format="A4")
            pdf.add_page()
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, safe_text(f"Contratti - {rag_soc}"), ln=1, align="C")
            pdf.set_font("Arial", "", 8)
            headers = ["NumeroContratto", "DataInizio", "DataFine", "Durata",
                       "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata", "Stato"]
            widths = [25, 25, 25, 15, 90, 20, 20, 25, 25]
            pdf.set_fill_color(37, 99, 235)
            pdf.set_text_color(255)
            for i, h in enumerate(headers):
                pdf.cell(widths[i], 6, safe_text(h), border=1, align="C", fill=True)
            pdf.ln()
            pdf.set_text_color(0)
            for _, row in disp.iterrows():
                vals = [safe_text(row.get(h, "")) for h in headers]
                for i, v in enumerate(vals):
                    align = "L" if headers[i] == "DescrizioneProdotto" else "C"
                    pdf.cell(widths[i], 5, v, border=1, align=align)
                pdf.ln()
            pdf_bytes = pdf.output(dest="S").encode("latin-1", errors="replace")
            st.download_button("📗 Esporta PDF", data=pdf_bytes,
                               file_name=f"contratti_{rag_soc}.pdf",
                               mime="application/pdf", use_container_width=True, key=f"pdf_{sel_id}")
        except Exception as e:
            st.error(f"❌ Errore export PDF: {e}")

# =====================================
# PAGINA RECALL E VISITE
# =====================================
def page_richiami_visite(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.image(LOGO_URL, width=120)
    st.markdown("<h2>📅 Recall e Visite</h2>", unsafe_allow_html=True)
    st.divider()
    filtro_nome = st.text_input("🔍 Cerca per nome cliente")
    filtro_citta = st.text_input("🏙️ Cerca per città")
    df = df_cli.copy()
    if filtro_nome:
        df = df[df["RagioneSociale"].str.contains(filtro_nome, case=False, na=False)]
    if filtro_citta:
        df = df[df["Citta"].str.contains(filtro_citta, case=False, na=False)]
    if df.empty:
        st.warning("❌ Nessun cliente trovato.")
        return
    oggi = pd.Timestamp.now().normalize()
    df["UltimoRecall"] = pd.to_datetime(df["UltimoRecall"], errors="coerce", dayfirst=True)
    df["ProssimoRecall"] = pd.to_datetime(df["ProssimoRecall"], errors="coerce", dayfirst=True)
    df["UltimaVisita"] = pd.to_datetime(df["UltimaVisita"], errors="coerce", dayfirst=True)
    df["ProssimaVisita"] = pd.to_datetime(df["ProssimaVisita"], errors="coerce", dayfirst=True)
    imminenti = df[
        (df["ProssimoRecall"].between(oggi, oggi + pd.DateOffset(days=30))) |
        (df["ProssimaVisita"].between(oggi, oggi + pd.DateOffset(days=30)))
    ]
    st.markdown("### 🔔 Imminenti (entro 30 giorni)")
    if imminenti.empty:
        st.success("✅ Nessun richiamo o visita imminente.")
    else:
        for i, r in imminenti.iterrows():
            c1, c2, c3, c4 = st.columns([2, 1, 1, 0.7])
            c1.markdown(f"**{r['RagioneSociale']}**")
            c2.markdown(fmt_date(r["ProssimoRecall"]))
            c3.markdown(fmt_date(r["ProssimaVisita"]))
            if c4.button("Apri", key=f"imm_{i}", use_container_width=True):
                st.session_state.update({"selected_cliente": r["ClienteID"], "nav_target": "Clienti", "_go_clienti_now": True})
                st.rerun()

# =====================================
# LISTA COMPLETA CLIENTI
# =====================================
def page_lista_clienti(df_cli: pd.DataFrame, df_ct: pd.DataFrame, role: str):
    st.title("📋 Lista Completa Clienti e Scadenze")
    oggi = pd.Timestamp.now().normalize()
    df_ct = df_ct.copy()
    df_ct["DataFine"] = pd.to_datetime(df_ct["DataFine"], errors="coerce", dayfirst=True)
    attivi = df_ct[df_ct["Stato"].astype(str).str.lower() != "chiuso"]
    prime_scadenze = attivi.groupby("ClienteID")["DataFine"].min().reset_index().rename(columns={"DataFine": "PrimaScadenza"})
    merged = df_cli.merge(prime_scadenze, on="ClienteID", how="left")
    merged["GiorniMancanti"] = (merged["PrimaScadenza"] - oggi).dt.days
    def badge(row):
        if pd.isna(row["PrimaScadenza"]): return "⚪ Nessuna"
        g, d = row["GiorniMancanti"], fmt_date(row["PrimaScadenza"])
        if g < 0: return f"⚫ Scaduto ({d})"
        if g <= 30: return f"🔴 {d}"
        if g <= 90: return f"🟡 {d}"
        return f"🟢 {d}"
    merged["ScadenzaBadge"] = merged.apply(badge, axis=1)
    for i, r in merged.iterrows():
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.2, 0.7])
        c1.markdown(f"**{r['RagioneSociale']}**")
        c2.markdown(r.get("Citta", "") or "—")
        c3.markdown(r["ScadenzaBadge"])
        if c4.button("📂 Apri", key=f"apri_cli_{i}", use_container_width=True):
            st.session_state.update({"selected_cliente": r["ClienteID"], "nav_target": "Clienti", "_go_clienti_now": True})
            st.rerun()

# =====================================
# MAIN APP
# =====================================
def main():
    user, role = do_login_fullscreen()
    if not user: st.stop()
    st.sidebar.success(f"👤 {user} — Ruolo: {role}")
    PAGES = {
        "Dashboard": page_dashboard,
        "Clienti": page_clienti,
        "Contratti": page_contratti,
        "📅 Recall e Visite": page_richiami_visite,
        "📋 Lista Clienti": page_lista_clienti
    }
    default_page = st.session_state.pop("nav_target", "Dashboard")
    page = st.sidebar.radio("📂 Menu principale", list(PAGES.keys()),
                            index=list(PAGES.keys()).index(default_page) if default_page in PAGES else 0)
    if st.session_state.get("_go_contratti_now"):
        st.session_state["_go_contratti_now"] = False
        page = "Contratti"
    if st.session_state.get("_go_clienti_now"):
        st.session_state["_go_clienti_now"] = False
        page = "Clienti"
    df_cli, df_ct = load_clienti(), load_contratti()
    if page in PAGES:
        PAGES[page](df_cli, df_ct, role)

# =====================================
# AVVIO
# =====================================
if __name__ == "__main__":
    main()
