import os

import pandas as pd

from app.db import get_connection

# Percorso del file Excel
excel_path = os.path.join(
    os.path.dirname(__file__),
    "lista_calciatori_svincolati_classic_fantalega-darko-pancev.xlsx",
)
# Percorso del database SQLite
sqlite_path = os.path.join(os.path.dirname(__file__), "giocatori.db")

# Leggi il file Excel
print("Lettura file Excel...")
df = pd.read_excel(excel_path)
print(f"Trovate {len(df)} righe.")


# Crea il database SQLite e importa i dati
print("Creazione database SQLite...")
conn = get_connection(sqlite_path)

# Aggiungi la colonna anni_contratto se non esiste
cur = conn.cursor()
cur.execute("PRAGMA table_info(giocatori)")
columns = [row[1] for row in cur.fetchall()]
if "anni_contratto" not in columns:
    try:
        cur.execute(
            "ALTER TABLE giocatori ADD COLUMN anni_contratto INTEGER DEFAULT NULL"
        )
    except Exception:
        pass

# Aggiungi la colonna al DataFrame se non esiste
if "anni_contratto" not in df.columns:
    df["anni_contratto"] = None

df.to_sql("giocatori", conn, if_exists="replace", index=False)
conn.close()
print("Importazione completata!")
