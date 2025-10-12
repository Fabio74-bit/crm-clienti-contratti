import pandas as pd
from openpyxl import load_workbook
from pathlib import Path

EXCEL_PATH = "GESTIONE_CLIENTI .xlsm"
OUT_DIR = Path("storage")
OUT_DIR.mkdir(exist_ok=True)

CLIENTI_CSV = OUT_DIR / "clienti.csv"
CONTRATTI_CSV = OUT_DIR / "contratti_clienti.csv"

IGNORE_SHEETS = {
    "Indice", "STATISTICHE", "CAP_Lista", "Contatori", 
    "NuovoContratto", "LOG_AGGIORNAMENTI"
}

print(f"📘 Lettura del file: {EXCEL_PATH}")
wb = load_workbook(EXCEL_PATH, data_only=True)

clienti_data = []
contratti_data = []

for sheet_name in wb.sheetnames:
    if sheet_name in IGNORE_SHEETS:
        continue

    ws = wb[sheet_name]
    print(f"➡️ Elaboro foglio cliente: {sheet_name}")

    # === Anagrafica Cliente ===
    cliente_info = {"ClienteID": sheet_name, "RagioneSociale": sheet_name}
    for row in ws.iter_rows(min_row=1, max_row=15):
        for cell in row:
            val = str(cell.value).strip() if cell.value else ""
            if "p.iva" in val.lower():
                cliente_info["PartitaIVA"] = val.split(":")[-1].strip()
            elif "indirizzo" in val.lower():
                cliente_info["Indirizzo"] = val.split(":")[-1].strip()
            elif "citt" in val.lower():
                cliente_info["Citta"] = val.split(":")[-1].strip()
            elif "tel" in val.lower():
                cliente_info["Telefono"] = val.split(":")[-1].strip()
            elif "mail" in val.lower():
                cliente_info["Email"] = val.split(":")[-1].strip()
    clienti_data.append(cliente_info)

    # === Contratti (da riga 21 in poi) ===
    data_rows = []
    for r in ws.iter_rows(min_row=21, values_only=False):
        # Valori grezzi
        values = [cell.value for cell in r]

        # Scarta righe totalmente vuote o con troppi None
        if sum(v is not None and str(v).strip() != "" for v in values) < 3:
            continue

        # Serve almeno un riferimento a contratto o data
        testo_riga = " ".join(str(v).lower() for v in values if v)
        if not any(k in testo_riga for k in ["contratto", "offerta", "nolo", "202", "20/", "01/"]):
            continue

        stato = "aperto"
        # Rileva righe rosse (contratti chiusi)
        if any(
            cell.fill and cell.fill.start_color and
            str(cell.fill.start_color.rgb).upper().startswith("FF") and
            "FF0000" in str(cell.fill.start_color.rgb).upper()
            for cell in r
        ):
            stato = "chiuso"

        data_rows.append(values + [stato])

    # Intestazioni (riga 20)
    headers = [str(cell.value).strip() if cell.value else "" for cell in ws[20]]
    if not any(headers):
        continue

    # Normalizza e rendi uniche le intestazioni
    clean_headers = []
    seen = {}
    for h in headers:
        h = h.strip().replace(" ", "").replace(".", "").replace("-", "").lower() or "colonna"
        if h in seen:
            seen[h] += 1
            h = f"{h}_{seen[h]}"
        else:
            seen[h] = 1
        clean_headers.append(h)
    clean_headers.append("stato")

    # Costruisci DataFrame solo se ha contenuti veri
    if len(data_rows) < 1:
        continue

    try:
        df_ct = pd.DataFrame(data_rows, columns=clean_headers)
        df_ct["ClienteID"] = sheet_name

        # Rinomina colonne più comuni per compatibilità CRM
        rename_map = {
            "numerocontratto": "NumeroContratto",
            "datainizio": "DataInizio",
            "datafine": "DataFine",
            "descrizione": "DescrizioneProdotto",
            "totrata": "TotRata",
        }
        df_ct.rename(columns=rename_map, inplace=True)

        # Rimuovi colonne duplicate
        df_ct = df_ct.loc[:, ~df_ct.columns.duplicated()]

        # Filtra anche qui: serve almeno NumeroContratto o DataFine
        if not ("NumeroContratto" in df_ct.columns or "DataFine" in df_ct.columns):
            continue

        contratti_data.append(df_ct)
    except Exception as e:
        print(f"⚠️  Errore nel foglio {sheet_name}: {e}")

# === Salvataggio ===
df_cli = pd.DataFrame(clienti_data)

if contratti_data:
    # Unisci senza controlli sugli indici
    df_ct_all = pd.concat(contratti_data, ignore_index=True, sort=False)
    df_ct_all = df_ct_all.loc[:, ~df_ct_all.columns.duplicated()]  # ultima sicurezza
else:
    df_ct_all = pd.DataFrame()

df_cli.to_csv(CLIENTI_CSV, index=False, encoding="utf-8-sig")
df_ct_all.to_csv(CONTRATTI_CSV, index=False, encoding="utf-8-sig")

# === Riepilogo finale ===
print(f"\n✅ Importazione completata:")
print(f"- Clienti: {len(df_cli)} -> {CLIENTI_CSV}")
print(f"- Contratti: {len(df_ct_all)} -> {CONTRATTI_CSV}")

if not df_ct_all.empty and "stato" in df_ct_all.columns:
    aperti = (df_ct_all["stato"].str.lower() != "chiuso").sum()
    chiusi = (df_ct_all["stato"].str.lower() == "chiuso").sum()
    print(f"   • Contratti aperti: {aperti}")
    print(f"   • Contratti chiusi: {chiusi}")

