# SHT – Gestione Clienti
# App Streamlit completa con:
# - Tema blu chiaro
# - Clienti / Contratti / Preventivi / Impostazioni
# - CSV import/export, allegati, docx template, export Excel
# - Ruoli semplici da secrets

from __future__ import annotations

import io
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import numpy as np
import streamlit as st

# ---------- PAGE CONFIG + THEME ----------
st.set_page_config(
    page_title="SHT – Gestione Clienti",
    page_icon="👤",
    layout="wide"
)

PRIMARY = "#1e88e5"       # blu medio
PRIMARY_SOFT = "#e3f2fd"  # blu chiarissimo
ACCENT = "#42a5f5"        # blu più chiaro
OK = "#2e7d32"
ERR = "#c62828"
TEXT = "#0d1117"
CARD_BG = "#ffffff"

st.markdown(
    f"""
    <style>
      html, body, [data-testid="stAppViewContainer"] {{
        background: {PRIMARY_SOFT};
      }}
      h1, h2, h3, h4 {{ color:{PRIMARY}; }}
      .stButton>button {{
        background:{PRIMARY}; color:white; border:0; border-radius:10px;
      }}
      .stButton>button:hover {{ background:{ACCENT}; }}
      .chip {{ display:inline-block; padding:.2rem .55rem; border-radius:999px;
               font-weight:600; font-size:.85rem }}
      .chip-open  {{ background:#e3f7e9; color:{OK};  border:1px solid #a5d6a7 }}
      .chip-close {{ background:#fdecea; color:{ERR}; border:1px solid #ef9a9a }}
      .chip-new   {{ background:#e3f2fd; color:{PRIMARY}; border:1px solid #90caf9 }}
      table.ctr-table {{ width:100%; border-collapse:collapse; background:{CARD_BG} }}
      table.ctr-table th {{
        background:{PRIMARY}; color:white; padding:.55rem; text-align:left;
      }}
      table.ctr-table td {{ padding:.5rem; border-bottom:1px solid #e0e0e0; }}
      tr.row-closed td {{ background:#fff5f5; }}
      .note-box {{ background:white; border:1px solid #e0e0e0; padding:.5rem; border-radius:8px }}
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- PATHS ----------
STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage")).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV     = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV   = STORAGE_DIR / "contratti_clienti.csv"
PREVENTIVI_CSV  = STORAGE_DIR / "preventivi.csv"
ALLEGATI_DIR    = STORAGE_DIR / "allegati"
PREV_DOCS_DIR   = STORAGE_DIR / "preventivi_docs"
TEMPLATES_DIR   = STORAGE_DIR / "templates"
for d in [ALLEGATI_DIR, PREV_DOCS_DIR, TEMPLATES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ---------- HELPERS ----------
def show_html(html: str, **kw):
    if hasattr(st, "html"): st.html(html, **kw)
    else: st.markdown(html, unsafe_allow_html=True)

def go_to(page_name: str):
    st.session_state["nav_target"] = page_name
    st.rerun()

def load_csv(path: Path, **kw) -> pd.DataFrame:
    if not path.exists(): return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False, **kw)

def save_csv(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)

def to_date_ddmmyyyy(v: str|None) -> Optional[date]:
    if v is None or str(v).strip()=="" or str(v).lower()=="nan": return None
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None

def fmt_date(d: Optional[date]) -> str:
    return d.strftime("%d/%m/%Y") if d else ""

def num_or_none(x) -> Optional[float]:
    try:
        if x is None: return None
        s = str(x).replace("€","").replace(".","").replace(",",".").strip()
        if s=="": return None
        return float(s)
    except Exception:
        return None

def money(v: Optional[float]) -> str:
    if v is None: return ""
    return "€ {:,.2f}".format(v).replace(",", "X").replace(".", ",").replace("X", ".")

def status_class(s: str) -> str:
    s = (s or "").strip().lower()
    if s in ("chiuso","closed"): return "chip-close"
    if s in ("aperto","open"):   return "chip-open"
    return "chip-new"

def status_chip(s: str) -> str:
    label = (s or "").strip().lower()
    title = {"aperto":"aperto","chiuso":"chiuso"}.get(label, "nuovo")
    return f'<span class="chip {status_class(s)}">{title}</span>'

def ensure_columns(df: pd.DataFrame, cols: Dict[str,str]) -> pd.DataFrame:
    for c,default in cols.items():
        if c not in df.columns:
            df[c] = default
    return df

# ---------- DATA (default columns) ----------
DEF_CLIENTI_COLS = {
    "ClienteID":"", "RagioneSociale":"", "PersonaRiferimento":"",
    "Indirizzo":"", "Citta":"", "CAP":"", "Telefono":"", "Email":"",
    "PartitaIVA":"", "IBAN":"", "SDI":"", "UltimoRecall":"", "ProssimoRecall":"",
    "UltimaVisita":"", "ProssimaVisita":"", "Note":""
}
DEF_CONTRATTI_COLS = {
    "ClienteID":"", "NumeroContratto":"", "DataInizio":"", "DataFine":"",
    "Durata":"", "DescrizioneProdotto":"", "NOL_FIN":"", "NOL_INT":"",
    "TotRata":"", "Stato":""
}
DEF_PREVENTIVI_COLS = {"NumeroPrev":"", "ClienteID":"", "Data":"", "Template":"", "FileName":"", "Key":""}

def read_all() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cl = ensure_columns(load_csv(CLIENTI_CSV), DEF_CLIENTI_COLS)
    ct = ensure_columns(load_csv(CONTRATTI_CSV), DEF_CONTRATTI_COLS)
    pr = ensure_columns(load_csv(PREVENTIVI_CSV), DEF_PREVENTIVI_COLS)
    return cl, ct, pr

# ---------- AUTH (semplice) ----------
def load_users_from_secrets() -> Dict[str, Dict[str,str]]:
    users = {}
    auth = st.secrets.get("auth", {})
    users_section = auth.get("users", {})
    # supporto anche a [auth.users.fabio] (come proposto)
    for key, val in users_section.items():
        # val = {"password":"...", "role":"admin|editor|contributor"}
        if isinstance(val, dict) and "password" in val and "role" in val:
            users[key.lower()] = {"password": val["password"], "role": val["role"].lower()}
    # fallback: se non definito nulla
    if not users:
        users["admin"] = {"password": "admin", "role": "admin"}
    return users

def login_box():
    users = load_users_from_secrets()
    if "user" in st.session_state and st.session_state.get("role"): return
    st.markdown("### 🔐 Login")
    u = st.text_input("Utente", key="login_u")
    p = st.text_input("Password", type="password", key="login_p")
    if st.button("Entra"):
        info = users.get(u.lower())
        if info and info["password"] == p:
            st.session_state["user"] = u
            st.session_state["role"] = info["role"]
            st.success(f"Benvenuto, {u} ({info['role']})")
            st.experimental_rerun()
        else:
            st.error("Credenziali non valide")

def require_login():
    if "user" not in st.session_state:
        login_box()
        st.stop()

def is_admin() -> bool:
    return st.session_state.get("role","") == "admin"

def can_edit() -> bool:
    return st.session_state.get("role") in ("admin","editor")

def can_contribute() -> bool:
    return st.session_state.get("role") in ("admin","editor","contributor")

# ---------- RENDER: DASHBOARD ----------
def render_dashboard(clienti: pd.DataFrame, contratti: pd.DataFrame):
    st.header("📊 Dashboard")
    today = date.today()
    horizon = today + timedelta(days=30)

    # prossime date recall/visita
    clienti = clienti.copy()
    for col in ["UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]:
        clienti[col+"_dt"] = clienti[col].apply(to_date_ddmmyyyy)

    st.subheader("Promemoria in arrivo (30 giorni)")
    mask = clienti["ProssimaVisita_dt"].notna() & clienti["ProssimaVisita_dt"].apply(lambda d: today <= d <= horizon)
    pr_vis = clienti.loc[mask, ["ClienteID","RagioneSociale","ProssimaVisita_dt"]].sort_values("ProssimaVisita_dt")
    pr_vis["ProssimaVisita"] = pr_vis["ProssimaVisita_dt"].apply(fmt_date)
    st.dataframe(pr_vis[["ClienteID","RagioneSociale","ProssimaVisita"]],
                 use_container_width=True)

    st.subheader("Contratti aperti per cliente (rata totale)")
    contratti = contratti.copy()
    contratti["StatoNorm"] = contratti["Stato"].str.lower().fillna("")
    ctr_open = contratti[contratti["StatoNorm"]!="chiuso"].copy()
    ctr_open["NOL_FIN_v"] = ctr_open["NOL_FIN"].apply(num_or_none)
    ctr_open["NOL_INT_v"] = ctr_open["NOL_INT"].apply(num_or_none)
    ctr_open["Tot_v"] = ctr_open.apply(
        lambda r: num_or_none(r["TotRata"]) if num_or_none(r["TotRata"]) is not None
                  else (r["NOL_FIN_v"] or 0) + (r["NOL_INT_v"] or 0), axis=1
    )
    agg = ctr_open.groupby("ClienteID", as_index=False)["Tot_v"].sum()
    agg["Totale"] = agg["Tot_v"].apply(money)
    st.dataframe(agg[["ClienteID","Totale"]], use_container_width=True)

# ---------- RENDER: CLIENTI ----------
def render_clienti(clienti: pd.DataFrame, contratti: pd.DataFrame, preventivi: pd.DataFrame):
    st.header("👥 Clienti")

    # elenco clienti a sinistra
    left, right = st.columns([1.2, 3.2])
    with left:
        q = st.text_input("Cerca ragione sociale…")
        if q:
            rows = clienti[clienti["RagioneSociale"].str.contains(q, case=False, na=False)]
        else:
            rows = clienti
        rows = rows.copy()
        rows["__lbl__"] = rows.apply(lambda r: f'{r["ClienteID"]} — {r["RagioneSociale"]}', axis=1)
        sel = st.selectbox("Seleziona cliente", [""] + rows["__lbl__"].tolist())
        sel_id = None
        if sel:
            try:
                sel_id = int(sel.split(" — ")[0])
            except Exception:
                pass
        if st.button("➕ Aggiungi cliente") and can_edit():
            # nuovo ID
            next_id = 1
            if len(clienti):
                try:
                    next_id = max(pd.to_numeric(clienti["ClienteID"], errors="coerce").fillna(0)) + 1
                except Exception:
                    pass
            st.session_state["new_cli_id"] = int(next_id)

        if "new_cli_id" in st.session_state and can_edit():
            with st.form("new_client"):
                st.markdown("#### Nuovo cliente")
                nid = st.text_input("ClienteID", value=str(st.session_state["new_cli_id"]))
                nm  = st.text_input("Ragione sociale")
                ref = st.text_input("Persona di riferimento")
                indir= st.text_input("Indirizzo")
                citta= st.text_input("Città")
                cap  = st.text_input("CAP")
                tel  = st.text_input("Telefono")
                eml  = st.text_input("Email")
                piva = st.text_input("Partita IVA")
                iban = st.text_input("IBAN")
                sdi  = st.text_input("SDI")
                note = st.text_area("Note")
                ok = st.form_submit_button("Crea")
                if ok:
                    new = pd.DataFrame([{
                        **DEF_CLIENTI_COLS,
                        "ClienteID": nid.strip(),
                        "RagioneSociale": nm.strip(),
                        "PersonaRiferimento": ref.strip(),
                        "Indirizzo": indir.strip(), "Citta": citta.strip(),
                        "CAP": cap.strip(), "Telefono": tel.strip(), "Email": eml.strip(),
                        "PartitaIVA": piva.strip(), "IBAN": iban.strip(), "SDI": sdi.strip(),
                        "Note": note.strip()
                    }])
                    out = pd.concat([clienti, new], ignore_index=True)
                    save_csv(out, CLIENTI_CSV)
                    del st.session_state["new_cli_id"]
                    st.success("Cliente creato")
                    st.experimental_rerun()

    with right:
        if not sel_id:
            st.info("Seleziona un cliente a sinistra per vedere/modificare l’anagrafica.")
            return

        r = clienti[clienti["ClienteID"].astype(str)==str(sel_id)]
        if r.empty:
            st.warning("Cliente non trovato")
            return
        r = r.iloc[0]

        st.subheader(r["RagioneSociale"])
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("**Persona di riferimento:**", r["PersonaRiferimento"] or "—")
            st.write("**Indirizzo:**", r["Indirizzo"] or "—")
            st.write("**Città/CAP:**", f'{r["Citta"] or "—"} {r["CAP"] or ""}')
            st.write("**Telefono:**", r["Telefono"] or "—")
            st.write("**Email:**", r["Email"] or "—")
        with col2:
            st.write("**Partita IVA:**", r["PartitaIVA"] or "—")
            st.write("**IBAN:**", r["IBAN"] or "—")
            st.write("**SDI:**", r["SDI"] or "—")
            st.write("**Ultimo Recall:**", r["UltimoRecall"] or "—")
            st.write("**Prossimo Recall:**", r["ProssimoRecall"] or "—")
        with col3:
            st.write("**Ultima Visita:**", r["UltimaVisita"] or "—")
            st.write("**Prossima Visita:**", r["ProssimaVisita"] or "—")
            if st.button("➡️ Vai alla gestione contratti di questo cliente"):
                st.session_state["selected_cliente"] = str(sel_id)
                go_to("Contratti")

        # Note / promemoria in formato dd/mm/aaaa
        st.markdown("#### Note & Promemoria")
        with st.form("note_form"):
            nr = st.text_area("Note cliente", value=r["Note"] or "")
            ur = st.text_input("Ultimo Recall (dd/mm/aaaa)", value=r["UltimoRecall"] or "")
            pr = st.text_input("Prossimo Recall (dd/mm/aaaa)", value=r["ProssimoRecall"] or "")
            uv = st.text_input("Ultima Visita (dd/mm/aaaa)", value=r["UltimaVisita"] or "")
            pv = st.text_input("Prossima Visita (dd/mm/aaaa)", value=r["ProssimaVisita"] or "")
            ok = st.form_submit_button("Salva note/promemoria", disabled=not can_contribute())
            if ok:
                clienti.loc[clienti["ClienteID"].astype(str)==str(sel_id), ["Note","UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita"]] = [nr, ur, pr, uv, pv]
                save_csv(clienti, CLIENTI_CSV)
                st.success("Salvato.")
                st.experimental_rerun()

        # Allegati
        st.markdown("#### 📎 Allegati cliente")
        files = list((ALLEGATI_DIR/str(sel_id)).glob("*"))
        if files:
            for f in files:
                st.write("•", f.name)
        up = st.file_uploader("Carica allegato", key=f"up_{sel_id}")
        if up and can_contribute():
            dest_dir = ALLEGATI_DIR/str(sel_id); dest_dir.mkdir(parents=True, exist_ok=True)
            (dest_dir / up.name).write_bytes(up.getbuffer())
            st.success("Allegato caricato.")
            st.experimental_rerun()

        if can_edit() and st.button("🗑️ Elimina cliente"):
            # elimina anche contratti e allegati
            c = st.session_state.get("_confirm_del", False)
            if not c:
                st.session_state["_confirm_del"] = True
                st.warning("Premi di nuovo per confermare eliminazione DEFINITIVA.")
            else:
                new_cl = clienti[clienti["ClienteID"].astype(str)!=str(sel_id)]
                save_csv(new_cl, CLIENTI_CSV)
                new_ct = contratti[contratti["ClienteID"].astype(str)!=str(sel_id)]
                save_csv(new_ct, CONTRATTI_CSV)
                # remove allegati
                try:
                    import shutil
                    shutil.rmtree(ALLEGATI_DIR/str(sel_id), ignore_errors=True)
                except Exception:
                    pass
                st.success("Cliente eliminato.")
                st.experimental_rerun()

# ---------- CONTRATTI ----------
def contracts_html(df: pd.DataFrame) -> str:
    # HTML con righe rosse per chiusi
    headers = "".join(f"<th>{c}</th>" for c in ["NumeroContratto","DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"])
    rows = []
    for _,r in df.iterrows():
        cls = "row-closed" if (r.get("Stato","").strip().lower()=="chiuso") else ""
        chip = status_chip(r.get("Stato",""))
        rows.append(
            f"<tr class='{cls}'>"
            f"<td>{r.get('NumeroContratto','')}</td>"
            f"<td>{r.get('DataInizio','')}</td>"
            f"<td>{r.get('DataFine','')}</td>"
            f"<td>{r.get('Durata','')}</td>"
            f"<td>{r.get('DescrizioneProdotto','')}</td>"
            f"<td>{r.get('NOL_FIN','')}</td>"
            f"<td>{r.get('NOL_INT','')}</td>"
            f"<td>{r.get('TotRata','')}</td>"
            f"<td>{chip}</td>"
            f"</tr>"
        )
    body = "".join(rows)
    return f"<table class='ctr-table'><thead><tr>{headers}</tr></thead><tbody>{body}</tbody></table>"

def export_excel(df: pd.DataFrame, file_name="contratti.xlsx"):
    import xlsxwriter as xw
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Contratti", index=False)
    st.download_button("⬇️ Esporta in Excel", data=out.getvalue(), file_name=file_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def render_contratti(clienti: pd.DataFrame, contratti: pd.DataFrame):
    st.header("🧾 Contratti (rosso = chiusi)")

    # selezione cliente
    lcol, rcol = st.columns([1.2, 3.2])
    with lcol:
        cid_session = st.session_state.get("selected_cliente")
        clist = clienti.copy()
        clist["__lbl__"] = clist.apply(lambda r: f'{r["ClienteID"]} — {r["RagioneSociale"]}', axis=1)
        opt = ["(tutti)"] + clist["__lbl__"].tolist()
        default_idx = 0
        if cid_session:
            for i, v in enumerate(opt):
                if v.startswith(f"{cid_session} —"):
                    default_idx = i
                    break
        pick = st.selectbox("Cliente", opt, index=default_idx)
        cid = None
        if pick != "(tutti)":
            try: cid = pick.split(" — ")[0]
            except: pass
        anno = st.number_input("Anno inizio (0 = tutti)", min_value=0, max_value=9999, value=0, step=1)

    df = contratti.copy()
    if cid:
        df = df[df["ClienteID"].astype(str)==str(cid)]
    if anno>0:
        df = df[df["DataInizio"].apply(lambda s: to_date_ddmmyyyy(s) and to_date_ddmmyyyy(s).year==anno)]

    # TotRata calcolato se vuoto
    df["NOL_FIN_v"] = df["NOL_FIN"].apply(num_or_none)
    df["NOL_INT_v"] = df["NOL_INT"].apply(num_or_none)
    def calc_tot(r):
        base = num_or_none(r["TotRata"])
        if base is not None: return money(base)
        somma = (r["NOL_FIN_v"] or 0) + (r["NOL_INT_v"] or 0)
        return money(somma) if somma>0 else ""
    df["TotRata"] = df.apply(calc_tot, axis=1)

    # KPI
    st.metric("Contratti", len(df))
    st.metric("Aperti", int((df["Stato"].str.lower()!="chiuso").sum()))

    # tabella
    show_html(contracts_html(df), height=180+28*len(df))

    # azioni
    with st.expander("🖨️ Esporta/Stampa contratti (selezione)"):
        # selezione per numero
        numbers = df["NumeroContratto"].dropna().tolist()
        sel = st.multiselect("Scegli contratti (vuoto = tutti)", numbers)
        to_print = df if not sel else df[df["NumeroContratto"].isin(sel)]
        export_excel(to_print, file_name=f"contratti_{cid or 'tutti'}.xlsx")
        st.caption("Per la stampa: usa Esporta → apri l’Excel → stampa dal tuo editor.")

    if can_edit():
        with st.expander("➕ Aggiungi contratto"):
            with st.form("add_ctr"):
                csel = st.selectbox("Cliente", clist["__lbl__"].tolist())
                c_id = csel.split(" — ")[0]
                ncontr = st.text_input("Numero contratto")
                din = st.text_input("Data inizio (dd/mm/aaaa)")
                dfin= st.text_input("Data fine (dd/mm/aaaa)")
                dur = st.text_input("Durata (es. 60 M)")
                desc= st.text_area("Descrizione prodotto")
                fin = st.text_input("NOL_FIN (es. 45,90)")
                intr= st.text_input("NOL_INT (es. 0,00)")
                stato= st.selectbox("Stato", ["aperto","chiuso","nuovo"], index=0)
                ok = st.form_submit_button("Aggiungi")
                if ok:
                    new = pd.DataFrame([{
                        **DEF_CONTRATTI_COLS,
                        "ClienteID": c_id, "NumeroContratto": ncontr,
                        "DataInizio": din, "DataFine": dfin, "Durata": dur,
                        "DescrizioneProdotto": desc, "NOL_FIN": fin, "NOL_INT": intr,
                        "Stato": stato
                    }])
                    out = pd.concat([contratti, new], ignore_index=True)
                    save_csv(out, CONTRATTI_CSV)
                    st.success("Contratto aggiunto.")
                    st.experimental_rerun()

        with st.expander("✏️ Modifica/Chiudi contratto"):
            # scegli numero contratto del cliente corrente (se presente)
            filt = contratti if not cid else contratti[contratti["ClienteID"].astype(str)==str(cid)]
            nums = filt["NumeroContratto"].dropna().tolist()
            if not nums:
                st.info("Nessun contratto disponibile.")
            else:
                pickn = st.selectbox("Seleziona numero", nums)
                row = contratti[contratti["NumeroContratto"]==pickn].iloc[0]
                with st.form("edit_ctr"):
                    din = st.text_input("Data inizio", value=row["DataInizio"])
                    dfin= st.text_input("Data fine", value=row["DataFine"])
                    dur = st.text_input("Durata", value=row["Durata"])
                    desc= st.text_input("Descrizione", value=row["DescrizioneProdotto"])
                    fin = st.text_input("NOL_FIN", value=row["NOL_FIN"])
                    intr= st.text_input("NOL_INT", value=row["NOL_INT"])
                    stato= st.selectbox("Stato", ["aperto","chiuso","nuovo"], index={"aperto":0,"chiuso":1}.get(row["Stato"],2))
                    ok = st.form_submit_button("Aggiorna")
                    if ok:
                        idx = contratti.index[contratti["NumeroContratto"]==pickn][0]
                        contratti.loc[idx, ["DataInizio","DataFine","Durata","DescrizioneProdotto","NOL_FIN","NOL_INT","Stato"]] = [din,dfin,dur,desc,fin,intr,stato]
                        save_csv(contratti, CONTRATTI_CSV)
                        st.success("Aggiornato. Ricorda che le righe chiuse appaiono in rosso.")
                        st.experimental_rerun()

        with st.expander("🗑️ Elimina contratto"):
            nums = df["NumeroContratto"].dropna().tolist()
            sel_del = st.selectbox("Scegli numero da eliminare", [""]+nums)
            if sel_del and st.button("Elimina DEFINITIVAMENTE"):
                out = contratti[contratti["NumeroContratto"]!=sel_del].copy()
                save_csv(out, CONTRATTI_CSV)
                st.success("Contratto eliminato.")
                st.experimental_rerun()

# ---------- PREVENTIVI ----------
def next_prev_number(prev: pd.DataFrame) -> str:
    yy = date.today().year
    mask = prev["NumeroPrev"].str.contains(f"PRV-{yy}-", na=False)
    series = prev.loc[mask, "NumeroPrev"].str.extract(rf"PRV-{yy}-(\d+)")
    try:
        last = series[0].astype(int).max()
        nxt = last + 1
    except Exception:
        nxt = 1
    return f"PRV-{yy}-{nxt:04d}"

def fill_docx_template(template_path: Path, mapping: Dict[str,str], out_path: Path):
    from docx import Document
    doc = Document(str(template_path))
    def rep(text):
        if not text: return text
        for k,v in mapping.items():
            text = text.replace(f"{{{{{k}}}}}", v)
        return text
    for p in doc.paragraphs:
        p.text = rep(p.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell.text = rep(cell.text)
    doc.save(str(out_path))

def render_preventivi(clienti: pd.DataFrame, preventivi: pd.DataFrame):
    st.header("📝 Preventivi")
    if not len(list(TEMPLATES_DIR.glob("*.docx"))):
        st.info(f"Nessun template .docx trovato in `{TEMPLATES_DIR}`. Caricane uno.")
    tpls = {p.name: p for p in TEMPLATES_DIR.glob("*.docx")}
    col1, col2 = st.columns(2)
    with col1:
        clist = clienti.copy()
        clist["__lbl__"] = clist.apply(lambda r: f'{r["ClienteID"]} — {r["RagioneSociale"]}', axis=1)
        sel = st.selectbox("Cliente", clist["__lbl__"].tolist() if len(clist) else [])
    with col2:
        tpl_name = st.selectbox("Template", list(tpls.keys()))
    if sel and tpl_name and can_contribute():
        if st.button("📄 Genera preventivo"):
            cid = sel.split(" — ")[0]
            row = clienti[clienti["ClienteID"].astype(str)==str(cid)].iloc[0]
            num = next_prev_number(preventivi)
            mapping = {
                "RAGIONE_SOCIALE": row["RagioneSociale"] or "",
                "PERSONA_RIF": row["PersonaRiferimento"] or "",
                "INDIRIZZO": row["Indirizzo"] or "",
                "CITTA": row["Citta"] or "",
                "CAP": row["CAP"] or "",
                "PIVA": row["PartitaIVA"] or "",
                "SDI": row["SDI"] or "",
                "DATA_OGGI": fmt_date(date.today()),
                "NUM_PREVENTIVO": num,
            }
            out_name = f"{num}_{cid}_{tpl_name}"
            out_path = PREV_DOCS_DIR / out_name
            fill_docx_template(tpls[tpl_name], mapping, out_path)
            # append su preventivi.csv
            new = pd.DataFrame([{
                "NumeroPrev": num, "ClienteID": cid, "Data": fmt_date(date.today()),
                "Template": tpl_name, "FileName": out_name, "Key": str(out_path)
            }])
            out = pd.concat([preventivi, new], ignore_index=True)
            save_csv(out, PREVENTIVI_CSV)
            st.success(f"Preventivo creato: {out_name}")

    st.markdown("---")
    st.subheader("Elenco preventivi")
    st.dataframe(preventivi, use_container_width=True)
    for _,r in preventivi.iterrows():
        p = Path(r["Key"]) if r["Key"] else None
        if p and p.exists():
            with open(p, "rb") as f:
                st.download_button(f"⬇️ Scarica {r['FileName']}", f.read(), file_name=r["FileName"])

# ---------- IMPOSTAZIONI ----------
def render_settings(clienti: pd.DataFrame, contratti: pd.DataFrame, preventivi: pd.DataFrame):
    st.header("⚙️ Impostazioni")
    st.write("Cartella storage:", f"`{STORAGE_DIR.as_posix()}`")

    st.markdown("### CSV – Import/Export")
    colA, colB, colC = st.columns(3)

    # CLIENTI
    with colA:
        st.caption("**clienti.csv**")
        st.download_button("⬇️ Scarica clienti.csv",
                           data=clienti.to_csv(index=False).encode("utf-8"),
                           file_name="clienti.csv", mime="text/csv")
        up_cli = st.file_uploader("Carica clienti.csv", type=["csv"], key="up_cli_csv")
        if up_cli is not None and st.button("Sostituisci clienti.csv"):
            try:
                df = pd.read_csv(up_cli, dtype=str, keep_default_na=False)
                needed = {"ClienteID","RagioneSociale"}
                if not needed.issubset(set(df.columns)):
                    st.error(f"clienti.csv deve contenere almeno: {sorted(needed)}")
                else:
                    save_csv(df, CLIENTI_CSV); st.success("clienti.csv sostituito."); st.experimental_rerun()
            except Exception as e:
                st.error(f"Errore: {e}")

    # CONTRATTI
    with colB:
        st.caption("**contratti_clienti.csv**")
        st.download_button("⬇️ Scarica contratti_clienti.csv",
                           data=contratti.to_csv(index=False).encode("utf-8"),
                           file_name="contratti_clienti.csv", mime="text/csv")
        up_ctr = st.file_uploader("Carica contratti_clienti.csv", type=["csv"], key="up_ctr_csv")
        if up_ctr is not None and st.button("Sostituisci contratti_clienti.csv"):
            try:
                df = pd.read_csv(up_ctr, dtype=str, keep_default_na=False)
                needed = {"ClienteID","NumeroContratto"}
                if not needed.issubset(set(df.columns)):
                    st.error(f"contratti_clienti.csv deve contenere almeno: {sorted(needed)}")
                else:
                    save_csv(df, CONTRATTI_CSV); st.success("contratti_clienti.csv sostituito."); st.experimental_rerun()
            except Exception as e:
                st.error(f"Errore: {e}")

    # PREVENTIVI
    with colC:
        st.caption("**preventivi.csv**")
        st.download_button("⬇️ Scarica preventivi.csv",
                           data=preventivi.to_csv(index=False).encode("utf-8"),
                           file_name="preventivi.csv", mime="text/csv")
        up_prv = st.file_uploader("Carica preventivi.csv", type=["csv"], key="up_prv_csv")
        if up_prv is not None and st.button("Sostituisci preventivi.csv"):
            try:
                df = pd.read_csv(up_prv, dtype=str, keep_default_na=False)
                needed = {"NumeroPrev","ClienteID"}
                if not needed.issubset(set(df.columns)):
                    st.error(f"preventivi.csv deve contenere almeno: {sorted(needed)}")
                else:
                    save_csv(df, PREVENTIVI_CSV); st.success("preventivi.csv sostituito."); st.experimental_rerun()
            except Exception as e:
                st.error(f"Errore: {e}")

    st.markdown("---")
    dsn = st.secrets.get("mysql", {}).get("dsn") if "mysql" in st.secrets else None
    try:
        from sqlalchemy import create_engine
        HAS_SQLALCH = True
    except Exception:
        HAS_SQLALCH = False

    if is_admin() and dsn and HAS_SQLALCH:
        st.markdown("### Database MySQL")
        st.caption("Esporta i CSV attuali su MySQL (sovrascrive le tabelle).")
        if st.button("Esporta su MySQL"):
            try:
                engine = create_engine(dsn)
                clienti.to_sql("clienti", engine, if_exists="replace", index=False)
                contratti.to_sql("contratti_clienti", engine, if_exists="replace", index=False)
                preventivi.to_sql("preventivi", engine, if_exists="replace", index=False)
                st.success("Esportazione completata.")
            except Exception as e:
                st.error(f"Errore MySQL: {e}")
    elif is_admin():
        st.caption("Per attivare MySQL: in Secrets aggiungi\n`[mysql]\ndsn=\"mysql+pymysql://user:pwd@host:3306/db\"`\n"
                   "e aggiungi `sqlalchemy` e `pymysql` al requirements.txt")

# ---------- MAIN ----------
PAGES = ["Dashboard","Clienti","Contratti","Preventivi","Impostazioni"]

def main():
    require_login()

    # sidebar
    st.sidebar.title("SHT – Gestione Clienti")
    user = st.session_state.get("user","")
    role = st.session_state.get("role","")
    st.sidebar.write(f"👤 {user} — **{role}**")
    current = st.session_state.get("sidebar_page","Clienti")
    target = st.session_state.pop("nav_target", None)
    if target in PAGES:
        current = target
    choice = st.sidebar.radio("Naviga", PAGES, index=PAGES.index(current) if current in PAGES else 1, key="sidebar_page")

    # carica dati
    clienti, contratti, preventivi = read_all()

    if choice=="Dashboard":
        render_dashboard(clienti, contratti)
    elif choice=="Clienti":
        render_clienti(clienti, contratti, preventivi)
    elif choice=="Contratti":
        render_contratti(clienti, contratti)
    elif choice=="Preventivi":
        render_preventivi(clienti, preventivi)
    elif choice=="Impostazioni":
        render_settings(clienti, contratti, preventivi)

if __name__ == "__main__":
    main()
