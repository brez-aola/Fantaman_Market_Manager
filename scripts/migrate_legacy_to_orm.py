"""One-off migration helper: copy legacy tables into new ORM tables.

Usage:
    # dry-run (default)
    python3 scripts/migrate_legacy_to_orm.py --dry-run

    # actually migrate (make a backup of your DB first!)
    python3 scripts/migrate_legacy_to_orm.py --apply

It connects to `giocatori.db` by default (in repo root). It creates the ORM tables if they don't exist and then copies teams and players.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path
from typing import Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure repo root is on sys.path so we can import `app.models` when running this script
import sys
from pathlib import Path as _Path
_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Import models from app
try:
    from app.models import Base, Team, Player
except Exception as e:
    raise RuntimeError("Unable to import ORM models from app.models: " + str(e))

REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_DB = REPO_ROOT / "giocatori.db"
TMP_DB = REPO_ROOT / "giocatori.db.migrate.tmp"


def copy_db(src: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    shutil.copy2(src, dest)


def legacy_counts(conn: sqlite3.Connection) -> Tuple[int, int]:
    cur = conn.cursor()
    # detect legacy tables; common names may be 'fantateam' and 'giocatori' - fallbacks
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = {r[0] for r in cur.fetchall()}
    teams_table = None
    players_table = None
    for t in ("fantateam", "team", "squadre", "fantasquadre"):
        if t in tables:
            teams_table = t
            break
    for p in ("giocatori", "players", "calciatori"):
        if p in tables:
            players_table = p
            break
    # fallback to any tables with suspect names
    if not teams_table:
        for t in tables:
            if "team" in t.lower() or "squad" in t.lower():
                teams_table = t
                break
    if not players_table:
        for p in tables:
            if "gioc" in p.lower() or "player" in p.lower() or "calci" in p.lower():
                players_table = p
                break
    teams_count = 0
    players_count = 0
    if teams_table:
        cur.execute(f"SELECT COUNT(*) FROM {teams_table}")
        teams_count = cur.fetchone()[0]
    if players_table:
        cur.execute(f"SELECT COUNT(*) FROM {players_table}")
        players_count = cur.fetchone()[0]
    return teams_count, players_count


def migrate(dry_run: bool = True, src_db: Path | None = None) -> None:
    src_db = src_db or LEGACY_DB
    if not src_db.exists():
        raise FileNotFoundError(f"Legacy DB not found: {src_db}")

    print(f"Using legacy DB: {src_db}")
    copy_db(src_db, TMP_DB)
    print(f"Created temporary DB copy at: {TMP_DB}")

    conn = sqlite3.connect(TMP_DB)
    teams_count, players_count = legacy_counts(conn)
    print(f"Legacy counts - teams: {teams_count}, players: {players_count}")

    # Prepare ORM DB (we'll write back to TMP_DB using SQLAlchemy)
    engine = create_engine(f"sqlite:///{TMP_DB}")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = Session()
    try:
        # Try to detect legacy tables again and copy rows in a best-effort manner
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = {r[0] for r in cur.fetchall()}
        teams_table = None
        players_table = None
        for t in ("fantateam", "team", "squadre", "fantasquadre"):
            if t in tables:
                teams_table = t
                break
        for p in ("giocatori", "players", "calciatori"):
            if p in tables:
                players_table = p
                break
        if not teams_table:
            for t in tables:
                if "team" in t.lower() or "squad" in t.lower():
                    teams_table = t
                    break
        if not players_table:
            for p in tables:
                if "gioc" in p.lower() or "player" in p.lower() or "calci" in p.lower():
                    players_table = p
                    break

        print(f"Detected legacy tables: teams='{teams_table}', players='{players_table}'")

        # Copy teams
        migrated_teams = 0
        inserted_teams = 0
        if teams_table:
            cur.execute(f"PRAGMA table_info('{teams_table}')")
            cols = [r[1] for r in cur.fetchall()]
            name_col = None
            cash_col = None
            for c in cols:
                if c.lower() in ("name", "nome", "team_name"):
                    name_col = c
                if c.lower() in ("cash", "soldi", "credito"):
                    cash_col = c
            if not name_col:
                # try first text column
                cur.execute(f"SELECT * FROM {teams_table} LIMIT 1")
                row = cur.fetchone()
                if row:
                    name_col = cols[1] if len(cols) > 1 else cols[0]
            q = f"SELECT * FROM {teams_table}"
            cur.execute(q)
            for row in cur.fetchall():
                row_d = dict(zip(cols, row))
                team_name = row_d.get(name_col) or row_d.get('name') or 'Unknown'
                # prefer cassa_attuale or cassa_iniziale if present in legacy
                team_cash = None
                for cand in ('cassa_attuale', 'cassa_iniziale', cash_col):
                    if cand and cand in row_d and row_d.get(cand) is not None:
                        try:
                            team_cash = int(float(row_d.get(cand)))
                            break
                        except Exception:
                            pass
                if team_cash is None:
                    team_cash = int(row_d.get(cash_col, 0) or 0)
                if dry_run:
                    migrated_teams += 1
                else:
                    t = Team(name=str(team_name), cash=team_cash)
                    session.add(t)
                    inserted_teams += 1
            print(f"Teams to migrate: {migrated_teams}")

        # Copy players
        migrated_players = 0
        inserted_players = 0
        if players_table:
            cur.execute(f"PRAGMA table_info('{players_table}')")
            cols = [r[1] for r in cur.fetchall()]
            name_col = None
            role_col = None
            team_ref_col = None
            costo_col = None
            anni_col = None
            opzione_col = None
            squadra_reale_col = None
            for c in cols:
                if c.lower() in ("name", "nome"):
                    name_col = c
                if c.lower() in ("role", "ruolo", "position"):
                    role_col = c
                if c.lower() in ("team_id", "squadra_id", "idteam", "team"):
                    team_ref_col = c
                if c.lower() in ("costo", "cost", "prezzo"):
                    costo_col = c
                if c.lower() in ("anni_contratto", "anni", "years"):
                    anni_col = c
                if c.lower() in ("opzione", "opz", "option"):
                    opzione_col = c
                if c.lower() in ("sq", "squadra", "squadra_reale", "squadra_reale"):
                    squadra_reale_col = c
            if not name_col:
                cur.execute(f"SELECT * FROM {players_table} LIMIT 1")
                row = cur.fetchone()
                if row:
                    name_col = cols[1] if len(cols) > 1 else cols[0]
            q = f"SELECT * FROM {players_table}"
            cur.execute(q)
            legacy_rows = cur.fetchall()
            # Ensure temp DB players table has the new columns required by ORM inserts
            existing_player_cols = set()
            cur.execute("PRAGMA table_info('players')")
            for r in cur.fetchall():
                existing_player_cols.add(r[1])
            needed = {
                'costo': 'INTEGER',
                'anni_contratto': 'INTEGER',
                'opzione': 'TEXT',
                'squadra_reale': 'TEXT',
            }
            for col, coltype in needed.items():
                if col not in existing_player_cols:
                    try:
                        cur.execute(f"ALTER TABLE players ADD COLUMN {col} {coltype}")
                    except Exception:
                        # SQLite sometimes disallows certain ALTERs; ignore and let SQLAlchemy handle via metadata
                        pass
            # refresh connection for SQLAlchemy to see schema changes
            conn.commit()
            for row in legacy_rows:
                row_d = dict(zip(cols, row))
                player_name = row_d.get(name_col) or 'Unknown'
                player_role = row_d.get(role_col)
                team_ref = row_d.get(team_ref_col)
                if dry_run:
                    migrated_players += 1
                else:
                    p = Player(name=str(player_name), role=str(player_role) if player_role else None)
                    # populate new fields when available
                    try:
                        if costo_col and row_d.get(costo_col) is not None:
                            p.costo = int(float(str(row_d.get(costo_col)).replace(',', '').replace('€','').strip()))
                    except Exception:
                        p.costo = None
                    try:
                        if anni_col and row_d.get(anni_col) is not None:
                            p.anni_contratto = int(row_d.get(anni_col))
                    except Exception:
                        p.anni_contratto = None
                    try:
                        if opzione_col and row_d.get(opzione_col) is not None:
                            p.opzione = str(row_d.get(opzione_col))
                    except Exception:
                        p.opzione = None
                    try:
                        if squadra_reale_col and row_d.get(squadra_reale_col) is not None:
                            p.squadra_reale = str(row_d.get(squadra_reale_col))
                    except Exception:
                        p.squadra_reale = None
                    # try to link to team by name or id
                    if team_ref is not None:
                        # if team_ref is numeric, try to find team by id, else by name
                        try:
                            candidate = session.query(Team).get(int(team_ref))
                            if candidate:
                                p.team_id = candidate.id
                        except Exception:
                            # try by name
                            candidate = session.query(Team).filter(Team.name == str(team_ref)).first()
                            if candidate:
                                p.team_id = candidate.id
                    session.add(p)
                    inserted_players += 1
                # end for each legacy player row
            print(f"Players to migrate: {migrated_players}")

        if not dry_run:
            session.commit()
            # report ORM-visible counts
            try:
                check_s = Session()
                try:
                    tcount = check_s.query(Team).count()
                    pcount = check_s.query(Player).count()
                finally:
                    check_s.close()
            except Exception:
                tcount = inserted_teams
                pcount = inserted_players
            print(f"Migration applied to temporary DB. Teams inserted: {inserted_teams} (orm={tcount}), Players inserted: {inserted_players} (orm={pcount}). Review and move the file to replace your original DB if desired.")
        else:
            print("Dry-run completed. No changes written.")
    finally:
        session.close()
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Actually write to the temporary DB (non-dry-run)')
    parser.add_argument('--src', type=str, default=None, help='Path to legacy DB')
    args = parser.parse_args()
    migrate(dry_run=not args.apply, src_db=Path(args.src) if args.src else None)
