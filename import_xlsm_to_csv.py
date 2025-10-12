import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter
from datetime import datetime

# === Funzioni di supporto ===

def excel_to_date(val):
    """Converte valori Excel in datetime o stringa vuota."""
    if pd.isna(val) or str(val).strip() == "":
        return ""
    try:
        if isinstance(val, (float, int)):
            return datetime(1899, 12, 30) + pd.to_timedelta(val, unit="D")
        elif isinstance(val, str):
            return pd.to_datetime(val, errors="coerce", dayfirst=True)
        elif isinstance(val, datetime):
            return val
    except Exception:
        return ""
    return ""


def fmt_date(val):
    """Restituisce una data formattata dd/mm/yyyy"""
    if pd.isna(val) or val == "":
        return ""
    try:
        return pd.to_datetime(val).strftime("%d/%m/%Y")
    except Exception:
        return ""


# === Lettura file principale ===

file_path = "GESTIONE_CLIENTI .xlsm"
print(f"\n📘 Lettura del file: {file_path}")
xls = pd.ExcelFile(file_path)

clienti_data = []
contratti_data = []

for sheet in xls.sheet_names:
    if sheet in ["Indice", "STATISTICHE", "CAP_Lista", "NuovoContratto", "Contatori", "LOG_AGGIORNAMENTI"]:
        continue

    try:
        df = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=str)
    except Exception:
        continue

    # Cerca la riga intestazione (dove inizia "Contratti di Noleggio")
    start_idx = None
    for i in range(len(df)):
        if df.iloc[i].astype(str).str.contains("Contratti di Noleggio", case=False, na=False).any():
            start_idx = i + 1
            break

    # Leggi anagrafica cliente
    try:
        nome = df.iloc[3, 1] if df.shape[0] > 3 else sheet
        telefono = df.iloc[8, 1] if df.shape[0] > 8 else ""
        citta = df.iloc[6, 1] if df.shape[0] > 6 else ""
        cap = str(df.iloc[7, 1]).strip() if df.shape[0] > 7 else ""
        piva = str(df.iloc[13, 1]).strip() if df.shape[0] > 13 else ""
        mail = df.iloc[14, 1] if df.shape[0] > 14 else ""
    except Exception:
        nome, telefono, citta, cap, piva, mail = sheet, "", "", "", "", ""

    clienti_data.append({
        "RagioneSociale": nome,
        "Telefono": telefono,
        "Citta": citta,
        "CAP": cap,
        "PartitaIVA": piva,
        "Email": mail
    })

    # Sezione contratti
    if start_idx is None:
        continue

    contratti = df.iloc[start_idx + 1:, :13]
    contratti.columns = [
        "DATA INIZIO", "DATA FINE", "DURATA", "Descrizione prodotto",
        "NOL. FIN.", "N.CONTRATTO", "NOL. INT.", "TOT. RATA",
        "COPIE B/N", "ECC. B/N", "COPIE COL.", "ECC. COL.", "Stato"
    ]

    for _, contr in contratti.iterrows():
        contr = contr.fillna("")
        descr = str(contr.get("Descrizione prodotto", "")).strip()

        # Filtro righe realmente valide
        valido = False
        if contr.get("N.CONTRATTO") not in (None, "", " "):
            valido = True
        elif descr != "":
            valido = True
        elif "VENDITA" in str(contr.get("DATA INIZIO", "")).upper():
            valido = True

        if not valido:
            continue

        stato = "vendita" if "VENDITA" in str(contr.get("DATA INIZIO", "")).upper() else str(contr.get("Stato", "")).lower()
        stato = "chiuso" if "x" in stato else stato

        contratti_data.append({
            "Cliente": nome,
            "NumeroContratto": str(contr.get("N.CONTRATTO", "")).strip(),
            "DataInizio": excel_to_date(contr.get("DATA INIZIO")),
            "DataFine": excel_to_date(contr.get("DATA FINE")),
            "Durata": contr.get("DURATA", ""),
            "DescrizioneProdotto": descr,
            "TotRata": contr.get("TOT. RATA", ""),
            "Stato": stato
        })

# === Esporta i dati ===

df_cli_all = pd.DataFrame(clienti_data)
df_ct_all = pd.DataFrame(contratti_data)

# Converte le date nel formato richiesto
df_ct_all["DataInizio"] = df_ct_all["DataInizio"].apply(fmt_date)
df_ct_all["DataFine"] = df_ct_all["DataFine"].apply(fmt_date)

# Salva nei file CSV
df_cli_all.to_csv("storage/clienti.csv", index=False)
df_ct_all.to_csv("storage/contratti_clienti.csv", index=False)

print("\n✅ Esportazione completata:")
print(f"- Clienti: {len(df_cli_all)} -> storage/clienti.csv")
print(f"- Contratti validi: {len(df_ct_all)} -> storage/contratti_clienti.csv\n")

