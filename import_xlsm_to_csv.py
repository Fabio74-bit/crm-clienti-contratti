import pandas as pd
from pathlib import Path
import datetime

# ==========================
# CONFIGURAZIONE
# ==========================
FILE_XLSM = "GESTIONE_CLIENTI.xlsm"
OUTPUT_DIR = Path("storage")
OUTPUT_DIR.mkdir(exist_ok=True)

CLIENTI_CSV = OUTPUT_DIR / "clienti.csv"
CONTRATTI_CSV = OUTPUT_DIR / "contratti_clienti.csv"

print(f"📘 Lettura del file: {FILE_XLSM}")
xls = pd.ExcelFile(FILE_XLSM)

clienti_data = []
contratti_data = []

# ==========================
# ELABORAZIONE FOGLI
# ==========================
for sheet in xls.sheet_names:
    if sheet.strip().lower() in ["indice", "statistiche", "cap_lista", "nuovocontratto", "log_aggiornamenti"]:
        continue

    print(f"➡️ Elaboro foglio cliente: {sheet}")
    try:
        # 🔹 Legge saltando le prime 20 righe, senza header
        df = pd.read_excel(FILE_XLSM, sheet_name=sheet, skiprows=20, header=None)
        print("   ➕ Prime 5 righe:", df.head(5).to_string(index=False))

        # Verifica che ci siano abbastanza colonne per la tabella contratti
        if df.shape[1] < 6:
            print("   ⚠️ Troppe poche colonne, salto.")
            continue

        # Imposta i nomi colonna standard
        df.columns = [
            "DataInizio", "DataFine", "Durata", "DescrizioneProdotto", "NOL_FIN",
            "NumeroContratto", "NOL_INT", "TotRata", "CopieBN", "EccBN",
            "CopieCol", "EccCol", "Stampa", "CTRChiuso"
        ][:df.shape[1]]

        # ✅ Conversione sicura
        def safe_str(x):
            if pd.isna(x) or x == pd.NaT:
                return ""
            if isinstance(x, (datetime.date, datetime.datetime)):
                return x.strftime("%d/%m/%Y")
            return str(x).strip()

        df = df.applymap(safe_str)

        # Filtra righe che sembrano contratti reali
        df_valid = df[
            (df["DescrizioneProdotto"].str.strip() != "") |
            (df["DataInizio"].str.contains("VENDITA", case=False, na=False))
        ].copy()

        if df_valid.empty:
            print("   ⚠️ Nessun contratto valido, salto.")
            continue

        clienti_data.append({"ClienteID": sheet.strip(), "RagioneSociale": sheet.strip()})

        for _, row in df_valid.iterrows():
            stato = "aperto"
            if "vendita" in row["DescrizioneProdotto"].lower():
                stato = "vendita"
            elif row.get("CTRChiuso", "").lower() in ["x", "chiuso", "si", "yes"]:
                stato = "chiuso"

            contratti_data.append({
                "ClienteID": sheet.strip(),
                "NumeroContratto": row.get("NumeroContratto", ""),
                "DataInizio": row.get("DataInizio", ""),
                "DataFine": row.get("DataFine", ""),
                "Durata": row.get("Durata", ""),
                "DescrizioneProdotto": row.get("DescrizioneProdotto", ""),
                "NOL_FIN": row.get("NOL_FIN", ""),
                "NOL_INT": row.get("NOL_INT", ""),
                "TotRata": row.get("TotRata", ""),
                "Stato": stato
            })

    except Exception as e:
        print(f"⚠️ Errore nel foglio {sheet}: {e}")

# ==========================
# SALVATAGGIO CSV
# ==========================
df_cli = pd.DataFrame(clienti_data).drop_duplicates(subset=["ClienteID"])
df_ct = pd.DataFrame(contratti_data)

if not df_ct.empty:
    df_ct = df_ct[df_ct["DescrizioneProdotto"].str.strip() != ""].copy()
    df_ct = df_ct.drop_duplicates(subset=["ClienteID", "NumeroContratto", "DescrizioneProdotto"])

df_cli.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
df_ct.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

print("\n✅ Esportazione completata:")
print(f"- Clienti: {len(df_cli)} -> {CLIENTI_CSV}")
print(f"- Contratti validi: {len(df_ct)} -> {CONTRATTI_CSV}")

