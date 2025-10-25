# =====================================
# 📦 data_io.py — Gestione file CSV e storage (CRM SHT)
# =====================================
from __future__ import annotations
import pandas as pd
from pathlib import Path
import streamlit as st
from datetime import datetime

# =====================================
# CONFIGURAZIONE STORAGE
# =====================================
STORAGE_DIR = Path(st.secrets.get("LOCAL_STORAGE_DIR", "storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

CLIENTI_CSV = STORAGE_DIR / "clienti.csv"
CONTRATTI_CSV = STORAGE_DIR / "contratti_clienti.csv"

# =====================================
# COLONNE STANDARD
# =====================================
CLIENTI_COLS = [
    "ClienteID", "RagioneSociale", "PersonaRiferimento", "Indirizzo", "Citta", "CAP",
    "Telefono", "Cell", "Email", "PartitaIVA", "IBAN", "SDI",
    "UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita",
    "TMK", "NoteCliente"
]

CONTRATTI_COLS = [
    "ClienteID", "RagioneSociale", "NumeroContratto", "DataInizio", "DataFine", "Durata",
    "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata",
    "CopieBN", "EccBN", "CopieCol", "EccCol", "Stato"
]

# =====================================
# FUNZIONI UTILI
# =====================================
def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Assicura che il DataFrame contenga tutte le colonne richieste."""
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    return df[cols]


# =====================================
# CORREZIONE DATE (uso interno)
# =====================================
def fix_inverted_dates(series: pd.Series, col_name: str = "") -> pd.Series:
    """
    Corregge automaticamente le date invertite (MM/DD/YYYY → DD/MM/YYYY)
    e mostra un log nel frontend Streamlit.
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
# PARSE E FORMAT DATE (compatibile CSV)
# =====================================
def parse_date_safe(val: str) -> str:
    """Converte una data in formato coerente DD/MM/YYYY, accettando formati misti."""
    if not val or str(val).strip() in ["nan", "NaN", "None", "NaT", ""]:
        return ""
    val = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(val, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return val


def to_date_series(series: pd.Series) -> pd.Series:
    """Applica parse_date_safe a una serie pandas."""
    return series.apply(parse_date_safe)


# =====================================
# LETTURA / SCRITTURA CSV
# =====================================
def load_csv(path: Path, cols: list[str]) -> pd.DataFrame:
    """Carica un CSV, garantendo colonne standard."""
    if path.exists():
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=cols)
        df.to_csv(path, index=False, encoding="utf-8-sig")
    return ensure_columns(df, cols)


def save_csv(df: pd.DataFrame, path: Path, date_cols: list[str] | None = None):
    """Salva un DataFrame come CSV formattando le date."""
    out = df.copy()
    if date_cols:
        for c in date_cols:
            if c in out.columns:
                out[c] = out[c].apply(parse_date_safe)
    out.to_csv(path, index=False, encoding="utf-8-sig")


# =====================================
# SALVATAGGIO CON CONTROLLO MODIFICHE
# =====================================
def save_if_changed(df_new: pd.DataFrame, path: Path, original_df: pd.DataFrame) -> bool:
    """Salva solo se i dati sono effettivamente cambiati."""
    try:
        if not original_df.equals(df_new):
            df_new.to_csv(path, index=False, encoding="utf-8-sig")
            return True
        return False
    except Exception:
        df_new.to_csv(path, index=False, encoding="utf-8-sig")
        return True


# =====================================
# SALVATAGGIO CON CORREZIONE DATE
# =====================================
def save_clienti(df: pd.DataFrame):
    """Salva il CSV clienti correggendo e formattando le date."""
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        if c in df.columns:
            df[c] = fix_inverted_dates(df[c], col_name=c)
    save_csv(df, CLIENTI_CSV, date_cols=["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"])


def save_contratti(df: pd.DataFrame):
    """Salva il CSV contratti correggendo e formattando le date."""
    for c in ["DataInizio", "DataFine"]:
        if c in df.columns:
            df[c] = fix_inverted_dates(df[c], col_name=c)
    save_csv(df, CONTRATTI_CSV, date_cols=["DataInizio", "DataFine"])


# =====================================
# CARICAMENTO CLIENTI / CONTRATTI (VERSIONE 2025)
# =====================================
def normalize_cliente_id(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizza la colonna ClienteID rimuovendo zeri iniziali e spazi."""
    if "ClienteID" in df.columns:
        df["ClienteID"] = (
            df["ClienteID"].astype(str).str.strip().str.replace(r"^0+", "", regex=True).replace({"": None})
        )
    return df


def load_clienti() -> pd.DataFrame:
    """Carica i dati clienti dal CSV, con pulizia e formattazione coerente."""
    try:
        if CLIENTI_CSV.exists():
            df = pd.read_csv(
                CLIENTI_CSV,
                dtype=str,
                sep=None,
                engine="python",
                encoding="utf-8-sig",
                on_bad_lines="skip"
            )
        else:
            df = pd.DataFrame(columns=CLIENTI_COLS)
    except Exception as e:
        st.error(f"❌ Errore durante la lettura dei clienti: {e}")
        df = pd.DataFrame(columns=CLIENTI_COLS)

    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
    )
    df = ensure_columns(df, CLIENTI_COLS)
    df = normalize_cliente_id(df)
    for c in ["UltimoRecall", "ProssimoRecall", "UltimaVisita", "ProssimaVisita"]:
        if c in df.columns:
            df[c] = to_date_series(df[c])
    return df


def load_contratti() -> pd.DataFrame:
    """Carica i dati contratti dal CSV, con pulizia e formattazione coerente."""
    try:
        if CONTRATTI_CSV.exists():
            df = pd.read_csv(
                CONTRATTI_CSV,
                dtype=str,
                sep=None,
                engine="python",
                encoding="utf-8-sig",
                on_bad_lines="skip"
            )
        else:
            df = pd.DataFrame(columns=CONTRATTI_COLS)
    except Exception as e:
        st.error(f"❌ Errore durante la lettura dei contratti: {e}")
        df = pd.DataFrame(columns=CONTRATTI_COLS)

    df = (
        df.replace(to_replace=r"^(nan|NaN|None|NULL|null|NaT)$", value="", regex=True)
        .fillna("")
    )
    df = ensure_columns(df, CONTRATTI_COLS)
    df = normalize_cliente_id(df)
    for c in ["DataInizio", "DataFine"]:
        if c in df.columns:
            df[c] = to_date_series(df[c])
    return df
