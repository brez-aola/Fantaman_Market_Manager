#!/usr/bin/env python3
import sqlite3
from pathlib import Path
from app.db import get_connection

DB = Path("/mnt/c/work/fantacalcio/giocatori.db")

if not DB.exists():
    print("Database not found at", DB)
    raise SystemExit(2)

conn = get_connection(str(DB))
cur = conn.cursor()


def show_all_teams():
    cur.execute(
        "SELECT squadra, carryover, cassa_iniziale, cassa_attuale FROM fantateam"
    )
    rows = cur.fetchall()
    print("Existing fantateam rows:")
    for r in rows:
        print(
            " -",
            r["squadra"],
            "cassa_iniziale=",
            r["cassa_iniziale"],
            "cassa_attuale=",
            r["cassa_attuale"],
        )


print("\nBefore update:")
show_all_teams()

# Find candidate teams matching 'bioparco' (case-insensitive)
cur.execute("SELECT squadra FROM fantateam")
teams = [r["squadra"] for r in cur.fetchall()]
matches = [t for t in teams if "bioparco" in t.lower()]
if not matches:
    print('\nNo fantateam row matching "bioparco" found. Exiting.')
    conn.close()
    raise SystemExit(3)

print("\nTeams matched for update:", matches)

NEW = 31.0
for team in matches:
    # compute spent for verification
    cur.execute(
        """SELECT COALESCE(SUM(CAST(REPLACE(REPLACE(REPLACE(COALESCE("Costo","0"), ",", ""), "%", ""), " ", "") AS REAL)),0) as spent FROM giocatori WHERE squadra=?""",
        (team,),
    )
    spent_row = cur.fetchone()
    spent = (
        float(spent_row["spent"])
        if spent_row and spent_row["spent"] is not None
        else 0.0
    )

    cur.execute(
        "SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (team,)
    )
    r = cur.fetchone()
    before_iniz = (
        float(r["cassa_iniziale"]) if r and r["cassa_iniziale"] is not None else None
    )
    before_att = (
        float(r["cassa_attuale"]) if r and r["cassa_attuale"] is not None else None
    )

    print(
        f"\nUpdating team '{team}': before cassa_attuale={before_att}, starting={before_iniz}, spent={spent}"
    )
    cur.execute("UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (NEW, team))
    conn.commit()

    cur.execute(
        "SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (team,)
    )
    r2 = cur.fetchone()
    after_att = (
        float(r2["cassa_attuale"]) if r2 and r2["cassa_attuale"] is not None else None
    )
    print(f"Updated '{team}': after cassa_attuale={after_att}")

print("\nAfter update:")
show_all_teams()

conn.close()

print("\nDone.")
