# =====================================
# utils/fixes.py — funzioni di correzione e normalizzazione dati
# =====================================
import pandas as pd
import streamlit as st
from datetime import datetime
from pathlib import Path

# =====================================
# 1️⃣ Correzione date invertite o errate
# =====================================
def fix_inverted_dates(series: pd.Series, col_name: str = "") -> pd.Series:
    """
    Corregge automaticamente date invertite (es. 03/25/2024 → 25/03/2024)
    e converte tutto in formato DD/MM/YYYY.
    Mostra anche un log in Streamlit con il numero di date corrette.
    """
    fixed = []
    fixed_count = 0
    total = len(series)

    for val in series:
        if pd.isna(val) or str(val).strip() == "":
            fixed.append("")
            continue

        s = str(val).strip()
        parsed = None

        try:
            # tenta entrambe le interpretazioni
            d1 = pd.to_datetime(s, dayfirst=True, errors="coerce")
            d2 = pd.to_datetime(s, dayfirst=False, errors="coerce")

            if not pd.isna(d1) and not pd.isna(d2) and d1 != d2:
                if d1.day <= 12 and d2.day > 12:
                    parsed = d2
                    fixed_count += 1
                else:
                    parsed = d1
            elif not pd.isna(d1):
                parsed = d1
            elif not pd.isna(d2):
                parsed = d2
        except Exception:
            parsed = None

        if parsed is not None:
            fixed.append(parsed.strftime("%d/%m/%Y"))
        else:
            fixed.append("")

    if fixed_count > 0:
        st.info(f"🔄 {fixed_count}/{total} date corrette automaticamente nella colonna **{col_name}**.")

    return pd.Series(fixed)


# =====================================
# 2️⃣ Parser sicuro per formati data misti
# =====================================
def parse_date_safe(val: str) -> str:
    """
    Converte qualsiasi formato data in DD/MM/YYYY.
    Gestisce formati misti come 'YYYY-MM-DD', 'MM/DD/YYYY', ecc.
    """
    if not val or str(val).strip() in ["nan", "NaN", "None", "NaT", ""]:
        return ""
    val = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(val, errors="coerce", dayfirst=True)
        if not pd.isna(parsed):
            return parsed.strftime("%d/%m/%Y")
    except Exception:
        pass
    return val


def to_date_series(series: pd.Series) -> pd.Series:
    """Applica parse_date_safe a un'intera colonna pandas."""
    return series.apply(parse_date_safe)


# =====================================
# 3️⃣ Normalizzazione ID cliente
# =====================================
def normalize_cliente_id(df: pd.DataFrame) -> pd.DataFrame:
    """Rimuove zeri iniziali e spazi dal campo ClienteID."""
    if "ClienteID" in df.columns:
        df["ClienteID"] = (
            df["ClienteID"].astype(str).str.strip().str.replace(r"^0+", "", regex=True).replace({"": None})
        )
    return df


# =====================================
# 4️⃣ Correzione completa di un CSV
# =====================================
def fix_dates_in_csv(csv_path: Path, date_cols: list[str]) -> bool:
    """
    Corregge tutte le date in un CSV, salvando le modifiche solo se necessario.
    Restituisce True se il file è stato modificato.
    """
    try:
        df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig").fillna("")
    except Exception as e:
        st.error(f"❌ Errore durante la lettura del file {csv_path.name}: {e}")
        return False

    df_before = df.copy()
    for c in date_cols:
        if c in df.columns:
            df[c] = fix_inverted_dates(df[c], col_name=c)

    # Normalizza ID se esiste
    df = normalize_cliente_id(df)

    if not df.equals(df_before):
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        st.success(f"✅ Corrette le date nel file {csv_path.name}")
        return True
    else:
        st.info(f"ℹ️ Nessuna modifica necessaria per {csv_path.name}")
        return False


# =====================================
# 5️⃣ Correzione globale (Clienti + Contratti)
# =====================================
def fix_all_data(base_dir: Path):
    """
    Corregge automaticamente tutti i file principali del CRM.
    (clienti.csv e contratti_clienti.csv)
    """
    clienti_path = base_dir / "clienti.csv"
    contratti_path = base_dir / "contratti_clienti.csv"

    if clienti_path.exists():
        fix_dates_in_csv(clienti_path, ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"])
    if contratti_path.exists():
        fix_dates_in_csv(contratti_path, ["DataInizio", "DataFine"])
