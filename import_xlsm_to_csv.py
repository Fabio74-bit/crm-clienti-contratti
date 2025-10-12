import pandas as pd
from openpyxl import load_workbook
from datetime import datetime

FILE_XLSM = "GESTIONE_CLIENTI .xlsm"
OUT_CLIENTI = "storage/clienti.csv"
OUT_CONTRATTI = "storage/contratti_clienti.csv"

def excel_to_date(value):
    if pd.isna(value) or str(value).strip() == "":
        return ""
    try:
        if isinstance(value, (int, float)):
            return pd.to_datetime("1899-12-30") + pd.to_timedelta(int(value), "D")
        d = pd.to_datetime(value, errors="coerce", dayfirst=True)
        return d if pd.notna(d) else ""
    except Exception:
        return ""

def fmt_date(value):
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d/%m/%Y")
    return ""

print(f"📘 Lettura del file: {FILE_XLSM}")
wb = load_workbook(FILE_XLSM, data_only=True)
skip_sheets = {"Indice", "STATISTICHE", "CAP_Lista", "Contatori", "NuovoContratto", "LOG_AGGIORNAMENTI"}

clienti_data, contratti_data = [], []

for sheet_name in wb.sheetnames:
    if sheet_name in skip_sheets:
        continue
    ws = wb[sheet_name]
    print(f"➡️ Elaboro foglio cliente: {sheet_name}")

    # === Lettura anagrafica ===
    cliente = {"RagioneSociale": sheet_name}
    for row in ws.iter_rows(min_row=1, max_row=30, max_col=2, values_only=True):
        key, val = row
        if not key:
            continue
        k = str(key).strip().lower()
        if "iva" in k:
            cliente["PIVA"] = str(val or "")
        elif "indirizzo" in k:
            cliente["Indirizzo"] = str(val or "")
        elif "cap" in k and not "recap" in k:
            cliente["CAP"] = str(val or "")
        elif "città" in k or "comune" in k:
            cliente["Citta"] = str(val or "")
        elif "telefono" in k:
            cliente["Telefono"] = str(val or "")
        elif "email" in k:
            cliente["Email"] = str(val or "")
        elif "ultimo recall" in k:
            cliente["UltimoRecall"] = fmt_date(excel_to_date(val))
        elif "ultima visita" in k:
            cliente["UltimaVisita"] = fmt_date(excel_to_date(val))
        elif "prossimo recall" in k:
            cliente["ProssimoRecall"] = fmt_date(excel_to_date(val))
        elif "prossima visita" in k:
            cliente["ProssimaVisita"] = fmt_date(excel_to_date(val))

    clienti_data.append(cliente)

    # === Lettura tabella contratti ===
    start_row = 21
    headers = [cell.value for cell in ws[start_row - 1] if cell.value]
    if not headers:
        continue

    valid_ct = 0
    for r in range(start_row, ws.max_row + 1):
        values = [c.value for c in ws[r][:len(headers)]]
        if all(v in (None, "", " ") for v in values):
            continue

        contr = dict(zip(headers, values))
        contr["Cliente"] = sheet_name

        # Filtro righe utili: accettiamo anche VENDITA
        if not contr.get("DATA INIZIO") and not contr.get("N.CONTRATTO") and "VENDITA" not in str(contr.get("Descrizione prodotto", "")).upper():
            continue

        # Stato contratto
        stato = "aperto"
        if str(contr.get("CTR Chiuso", "")).strip().lower() in ("x", "chiuso", "1", "si"):
            stato = "chiuso"

        fill_colors = [c.fill.start_color.index for c in ws[r][:len(headers)]]
        if any("FF0000" in str(col) for col in fill_colors):
            stato = "chiuso"

        if str(contr.get("DATA INIZIO", "")).strip().upper() == "VENDITA" or "VENDITA" in str(contr.get("Descrizione prodotto", "")).upper():
            stato = "vendita"

        contr["Stato"] = stato
        contr["DataInizio"] = fmt_date(excel_to_date(contr.get("DATA INIZIO")))
        contr["DataFine"] = fmt_date(excel_to_date(contr.get("DATA FINE")))

        contratti_data.append(contr)
        valid_ct += 1

    print(f"   ➕ {valid_ct} contratti trovati")

df_cli = pd.DataFrame(clienti_data).fillna("")
df_ct = pd.DataFrame(contratti_data).fillna("")

df_cli.to_csv(OUT_CLIENTI, index=False)
df_ct.to_csv(OUT_CONTRATTI, index=False)

print("\n✅ Esportazione completata:")
print(f"- Clienti: {len(df_cli)} -> {OUT_CLIENTI}")
print(f"- Contratti validi: {len(df_ct)} -> {OUT_CONTRATTI}")

