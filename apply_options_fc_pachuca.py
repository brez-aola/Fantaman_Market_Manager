#!/usr/bin/env python3
import shutil
import os
import datetime
import unicodedata
import re
from app.db import get_connection

DB = os.path.join(os.path.dirname(__file__), "giocatori.db")
# Backup
now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = DB + f".backup.{now}"
shutil.copy2(DB, backup)
print("Backup created:", backup)

# Players list provided by user for FC Pachuca
targets = [
    "Sommer",
    "Cambiaso",
    "Holm",
    "Dodo'",
    "Kone'",
    "Baldanzi",
    "Colombo",
    "Dovbik",
    "Piccoli",
    "Belotti",
]
FANTASY = "FC Pachuca"

# normalization helper
_combo_re = re.compile(r"\s+")


def normalize(s):
    if s is None:
        return ""
    s = str(s)
    # remove dots, commas, apostrophes and question marks
    s = s.replace(".", " ").replace(",", " ").replace("'", " ").replace("?", " ")
    # unicode normalize
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    s = _combo_re.sub(" ", s)
    return s


conn = get_connection(DB)
cur = conn.cursor()
cur.execute(
    'SELECT rowid, "Nome", "Sq.", squadra, opzione, anni_contratto FROM giocatori'
)
rows = cur.fetchall()
# build normalized map
norm_map = {}
for r in rows:
    n = normalize(r["Nome"])
    norm_map.setdefault(n, []).append(r)

updated = []
not_found = []
ambiguities = {}
for t in targets:
    tn = normalize(t)
    matches = norm_map.get(tn, [])
    method = "exact"
    if not matches:
        # try startswith
        matches = [r for k in norm_map for r in norm_map[k] if k.startswith(tn)]
        if matches:
            method = "startswith"
    if not matches:
        # try contains
        matches = [r for k in norm_map for r in norm_map[k] if tn in k]
        if matches:
            method = "contains"
    if not matches:
        not_found.append(t)
        print(f"NOT FOUND: {t}")
        continue
    if len(matches) > 1:
        ambiguities[t] = matches
        print(f'AMBIGUOUS ({method}) for "{t}" -> {len(matches)} matches:')
        for r in matches:
            print(
                "  ",
                r["rowid"],
                "|",
                r["Nome"],
                "| Sq.:",
                r["Sq."],
                "| squadra:",
                r["squadra"],
                "| opzione:",
                r["opzione"],
                "| anni:",
                r["anni_contratto"],
            )
    else:
        print(f'FOUND ({method}) for "{t}":', matches[0]["rowid"], matches[0]["Nome"])
    # update all matched rowids
    ids = [r["rowid"] for r in matches]
    placeholders = ",".join("?" for _ in ids)
    sql = f"UPDATE giocatori SET opzione = ?, anni_contratto = ?, squadra = ? WHERE rowid IN ({placeholders})"
    params = ["SI", None, FANTASY] + ids
    cur.execute(sql, params)
    conn.commit()
    updated.extend([(t, r["rowid"], r["Nome"]) for r in matches])

print("\nSummary:")
print("Total targets:", len(targets))
print("Updated rows:", len(updated))
print("Not found:", len(not_found))
if not_found:
    for n in not_found:
        print("  -", n)
if ambiguities:
    print("\nAmbiguities (multiple matches):")
    for k, v in ambiguities.items():
        print(" ", k, "->", [(r["rowid"], r["Nome"]) for r in v])

# show changed rows for verification
if updated:
    print("\nUpdated rows detail:")
    q = (
        'SELECT rowid, "Nome", "Sq.", squadra, opzione, anni_contratto FROM giocatori WHERE rowid IN ('
        + ",".join("?" for _ in updated)
        + ")"
    )
    ids = [u[1] for u in updated]
    cur.execute(q, ids)
    for r in cur.fetchall():
        print(
            " ",
            r["rowid"],
            "|",
            r["Nome"],
            "|",
            r["Sq."],
            "| squadra:",
            r["squadra"],
            "| opzione:",
            r["opzione"],
            "| anni:",
            r["anni_contratto"],
        )

conn.close()
print("\nDone.")
