# import_xlsm_to_csv.py
from __future__ import annotations
import re
from pathlib import Path
import pandas as pd

# ========= CONFIG =========
SRC_XLSM = Path("GESTIONE_CLIENTI .xlsm")  # attenzione allo spazio prima di .xlsm
OUT_DIR  = Path("storage")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CLIENTI   = OUT_DIR / "clienti.csv"
OUT_CONTRATTI = OUT_DIR / "contratti_clienti.csv"
OUT_PREV      = OUT_DIR / "preventivi.csv"

SKIP_PATTERNS = [
    r"^indice$", r"^statistiche$", r"cap(_lista)?", r"nuovocontratto",
    r"nuovocliente", r"contatori", r"log", r"amanuel"
]

CLIENTI_COLS = [
    "ClienteID","RagioneSociale","PersonaRiferimento","Indirizzo","Citta","CAP",
    "Telefono","Cell","Email","PartitaIVA","IBAN","SDI",
    "UltimoRecall","ProssimoRecall","UltimaVisita","ProssimaVisita","Note"
]
CONTRATTI_COLS = [
    "ClienteID","NumeroContratto","DataInizio","DataFine","Durata",
    "DescrizioneProdotto","NOL_FIN","NOL_INT","TotRata","Stato"
]
PREVENTIVI_COLS = ["ClienteID","NumeroOfferta","Template","NomeFile","Percorso","DataCreazione"]

def should_skip(sheet_name: str) -> bool:
    low = sheet_name.strip().lower()
    return any(re.search(p, low) for p in SKIP_PATTERNS)

def to_ddmmyyyy(x) -> str:
    """Converte in dd/mm/yyyy; se non interpretabile -> vuoto."""
    if x in (None, ""):
        return ""
    try:
        d = pd.to_datetime(x, errors="coerce", dayfirst=True)
        if pd.isna(d):
            d = pd.to_datetime(x, errors="coerce")
        return "" if pd.isna(d) else d.strftime("%d/%m/%Y")
    except Exception:
        return ""

def parse_client_sheet(df_raw: pd.DataFrame) -> tuple[dict, list[dict]]:
    """
    Ritorna (record_cliente, lista_contratti) estratti da un foglio 'per cliente'.
    Layout atteso:
      - prime ~80 righe: anagrafica in colonna 0 (etichetta) e colonna 1 (valore)
      - riga header contratti: contiene "data inizio", "data fine", "durata", "descrizione prodotto", ecc.
    """
    df = df_raw.copy()

    # --- Anagrafica (col0=chiave, col1=valore)
    kv = {}
    nscan = min(120, len(df))
    for i in range(nscan):
        k = str(df.iloc[i,0]).strip()
        v = "" if (1 >= df.shape[1] or pd.isna(df.iloc[i,1])) else str(df.iloc[i,1]).strip()
        if k and k.lower() != "nan":
            kv[k.strip().lower()] = v

    nome       = kv.get("nome cliente", kv.get("cliente","")).strip()
    indirizzo  = kv.get("indirizzo","")
    citta      = kv.get("città", kv.get("citta",""))
    cap        = kv.get("cap","")
    tel        = kv.get("telefono","")
    rif1       = kv.get("rif.", kv.get("rif", kv.get("riferimento","")))
    rif2       = kv.get("rif 2.", kv.get("rif 2",""))
    persona    = " / ".join([x for x in [rif1, rif2] if x])
    iban       = kv.get("iban","")
    piva       = kv.get("partita iva","")
    email      = kv.get("email","")
    sdi        = kv.get("sdi","")

    # optional
    ult_recall = to_ddmmyyyy(kv.get("ultimo recall",""))
    ult_visita = to_ddmmyyyy(kv.get("ultima visita",""))

    record_cliente = {
        "RagioneSociale": nome,
        "PersonaRiferimento": persona,
        "Indirizzo": indirizzo,
        "Citta": citta,
        "CAP": cap,
        "Telefono": tel,
        "Cell": "",
        "Email": email,
        "PartitaIVA": piva,
        "IBAN": iban,
        "SDI": sdi,
        "UltimoRecall": ult_recall,
        "ProssimoRecall": "",
        "UltimaVisita": ult_visita,
        "ProssimaVisita": "",
        "Note": ""
    }

    # --- Trova intestazione tabella contratti
    header_row = None
    for i in range(len(df)):
        rowvals = df.iloc[i, :15].astype(str).str.lower().tolist()
        row_join = " | ".join(rowvals)
        if ("data inizio" in row_join and "data fine" in row_join and "descrizione" in row_join) \
           or ("descrizione prodotto" in row_join):
            header_row = i
            break

    contratti = []
    if header_row is not None:
        headers = df.iloc[header_row,:].astype(str).str.strip().str.lower().tolist()
        colmap = {}
        for idx, h in enumerate(headers):
            h2 = re.sub(r"\s+"," ", h)
            if "data inizio" in h2: colmap["DataInizio"] = idx
            elif "data fine" in h2: colmap["DataFine"] = idx
            elif "durata" in h2: colmap["Durata"] = idx
            elif "descrizione" in h2: colmap["DescrizioneProdotto"] = idx
            elif "n.contratto" in h2 or ("numero" in h2 and "contratto" in h2): colmap["NumeroContratto"] = idx
            elif "nol" in h2 and "fin" in h2: colmap["NOL_FIN"] = idx
            elif "nol" in h2 and "int" in h2: colmap["NOL_INT"] = idx
            elif "tot" in h2 and "rata" in h2: colmap["TotRata"] = idx
            elif "stato" in h2: colmap["Stato"] = idx

        r = header_row + 1
        while r < len(df):
            row = df.iloc[r,:]
            # riga vuota = stop
            if row.iloc[:4].isna().all():
                break

            def getc(key):
                idx = colmap.get(key)
                if idx is None:
                    return ""
                val = row.iloc[idx]
                return "" if pd.isna(val) else str(val).strip()

            d_inizio = to_ddmmyyyy(getc("DataInizio"))
            d_fine   = to_ddmmyyyy(getc("DataFine"))
            durata   = getc("Durata")
            desc     = getc("DescrizioneProdotto")
            num      = getc("NumeroContratto")
            nf       = getc("NOL_FIN")
            ni       = getc("NOL_INT")
            tot      = getc("TotRata")

            stato = getc("Stato").lower()
            if not stato:
                # prova a dedurre presenza di 'chiuso' nei valori della riga
                if any(isinstance(x,str) and "chiuso" in x.lower() for x in row.astype(str).tolist()):
                    stato = "chiuso"
                else:
                    stato = "aperto"

            contratti.append({
                "NumeroContratto": num,
                "DataInizio": d_inizio,
                "DataFine": d_fine,
                "Durata": durata,
                "DescrizioneProdotto": desc,
                "NOL_FIN": nf,
                "NOL_INT": ni,
                "TotRata": tot,
                "Stato": stato
            })
            r += 1

    return record_cliente, contratti

def main():
    if not SRC_XLSM.exists():
        raise FileNotFoundError(f"File non trovato: {SRC_XLSM}")

    xl = pd.ExcelFile(SRC_XLSM)
    clienti_records = []
    contratti_records = []
    cliente_id = 1

    for sheet in xl.sheet_names:
        if should_skip(sheet):
            continue
        try:
            df = pd.read_excel(SRC_XLSM, sheet_name=sheet, header=None)
        except Exception:
            continue

        rec_cli, rec_ct = parse_client_sheet(df)

        # se manca la ragione sociale, salta il foglio
        if not rec_cli.get("RagioneSociale","").strip():
            continue

        rec_cli_full = {"ClienteID": cliente_id, **rec_cli}
        clienti_records.append(rec_cli_full)

        for c in rec_ct:
            contratti_records.append({"ClienteID": cliente_id, **c})

        cliente_id += 1

    # DataFrame finali ordinati nelle colonne attese
    df_cli = pd.DataFrame(clienti_records, columns=CLIENTI_COLS)
    df_ct  = pd.DataFrame(contratti_records, columns=CONTRATTI_COLS)
    df_prev = pd.DataFrame(columns=PREVENTIVI_COLS)  # se servirà in futuro

    # Salva i CSV (UTF-8 BOM per compatibilità Excel)
    df_cli.to_csv(OUT_CLIENTI, index=False, encoding="utf-8-sig")
    df_ct.to_csv(OUT_CONTRATTI, index=False, encoding="utf-8-sig")
    df_prev.to_csv(OUT_PREV, index=False, encoding="utf-8-sig")

    print("OK ✅")
    print(f"- Clienti:   {len(df_cli):>5} righe -> {OUT_CLIENTI}")
    print(f"- Contratti: {len(df_ct):>5} righe -> {OUT_CONTRATTI}")
    print(f"- Preventivi:{len(df_prev):>5} righe -> {OUT_PREV}")

if __name__ == "__main__":
    main()

