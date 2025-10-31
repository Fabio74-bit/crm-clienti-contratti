import pandas as pd
import mysql.connector
from pathlib import Path

# === Percorsi ===
base = Path(__file__).parent / "storage"
main_cli = base / "clienti.csv"
main_ct = base / "contratti.csv"
gab_cli = base / "gabriele" / "clienti.csv"
gab_ct = base / "gabriele" / "contratti.csv"

# === Connessione MySQL ===
conn = mysql.connector.connect(
    host="10.10.12.25",
    user="fabio",
    password="fabio",
    database="crm_sht",
    port=3306
)
cur = conn.cursor()

def import_csv_to_table(csv_path, table_name):
    """Importa un CSV in una tabella MySQL (REPLACE INTO)."""
    df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig").fillna("")
    print(f"📥 Import {len(df)} righe in {table_name} ...")
    cols = df.columns.tolist()
    col_list = ",".join([f"`{c}`" for c in cols])
    placeholders = ",".join(["%s"] * len(cols))
    for _, row in df.iterrows():
        cur.execute(f"REPLACE INTO {table_name} ({col_list}) VALUES ({placeholders})", tuple(row))
    conn.commit()
    print(f"✅ Completato: {table_name}")

# === Importa tutti ===
import_csv_to_table(main_cli, "clienti")
import_csv_to_table(main_ct, "contratti")
import_csv_to_table(gab_cli, "clienti_gabriele")
import_csv_to_table(gab_ct, "contratti_gabriele")

conn.close()
print("🎯 Importazione terminata con successo.")
