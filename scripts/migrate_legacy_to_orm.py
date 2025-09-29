"""One-off migration helper: copy legacy tables into new ORM tables.

Usage:
    # dry-run (default)
    python3 scripts/migrate_legacy_to_orm.py --dry-run

    # actually migrate (make a backup of your DB first!)
    python3 scripts/migrate_legacy_to_orm.py --apply

It connects to `giocatori.db` by default (in repo root). It creates the ORM tables if they don't exist and then copies teams and players.
"""

# This script is a one-off migration helper. Keep linter warnings to a minimum
# but prefer explicit exceptions and careful validation instead of "noqa".

from __future__ import annotations

import argparse
import logging
import shutil
import sqlite3

# Ensure repo root is on sys.path so we can import `app.models` when running this script
import sys
from pathlib import Path
from pathlib import Path as _Path
from typing import Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.db import get_connection

_repo_root = _Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Import models from app
try:
    from app.models import Base, Player, Team
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
        # Validate table identifier to avoid SQL injection via legacy table names
        import re

        ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        if not ident_re.match(teams_table):
            raise ValueError("Detected teams table name is not a valid SQL identifier")
        cur.execute("SELECT COUNT(*) FROM " + teams_table)
        teams_count = cur.fetchone()[0]
    if players_table:
        # Validate players table identifier
        import re

        ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        if not ident_re.match(players_table):
            raise ValueError(
                "Detected players table name is not a valid SQL identifier"
            )
        cur.execute("SELECT COUNT(*) FROM " + players_table)
        players_count = cur.fetchone()[0]
    return teams_count, players_count


def migrate(dry_run: bool = True, src_db: Path | None = None) -> None:
    """Copy legacy data from a sqlite DB into ORM tables on a temporary DB.

    This function is defensive: it validates table/column identifiers before
    constructing any SQL, it parses numeric fields carefully and supports a
    dry-run mode which only reports what would be migrated.
    """
    import re

    src_db = src_db or LEGACY_DB
    if not src_db.exists():
        raise FileNotFoundError(f"Legacy DB not found: {src_db}")

    print(f"Using legacy DB: {src_db}")
    copy_db(src_db, TMP_DB)
    print(f"Created temporary DB copy at: {TMP_DB}")

    conn = get_connection(str(TMP_DB))
    teams_count, players_count = legacy_counts(conn)
    print(f"Legacy counts - teams: {teams_count}, players: {players_count}")

    # Prepare ORM DB (we'll write back to TMP_DB using SQLAlchemy)
    engine = create_engine(f"sqlite:///{TMP_DB}")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = Session()
    try:
        cur = conn.cursor()

        # Detect legacy table names
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = {r[0] for r in cur.fetchall()}
        teams_table = next(
            (
                t
                for t in ("fantateam", "team", "squadre", "fantasquadre")
                if t in tables
            ),
            None,
        )
        players_table = next(
            (p for p in ("giocatori", "players", "calciatori") if p in tables),
            None,
        )

        print(
            f"Detected legacy tables: teams='{teams_table}', players='{players_table}'"
        )

        # Helper to validate SQL identifiers
        ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

        # small helper to coerce numeric-like values into int when possible
        def _to_int(v: object) -> Optional[int]:
            try:
                return int(float(str(v).replace(",", "").replace("\u20ac", "").strip()))
            except (ValueError, TypeError):
                try:
                    # mypy: ignore type check for this fallback conversion
                    return int(v)  # type: ignore[call-overload]
                except (ValueError, TypeError):
                    return None

        # Migrate teams
        migrated_teams = 0
        inserted_teams = 0
        if teams_table:
            if not ident_re.match(teams_table):
                raise ValueError(
                    "Detected teams table name is not a valid SQL identifier"
                )
            cur.execute(f"PRAGMA table_info('{teams_table}')")
            cols = [r[1] for r in cur.fetchall()]
            # Determine name and cash columns heuristically
            name_col = next((c for c in cols if c.lower() in ("name", "nome")), None)
            cash_col = next(
                (
                    c
                    for c in cols
                    if c.lower()
                    in ("cassa_attuale", "cassa_iniziale", "cash", "credito", "soldi")
                ),
                None,
            )
            if not name_col:
                # fallback to first or second column
                name_col = cols[1] if len(cols) > 1 else cols[0]

            cur.execute(
                f"SELECT * FROM {teams_table}"
            )  # nosec: B608 - identifier validated
            for row in cur.fetchall():
                row_d = dict(zip(cols, row))
                team_name = row_d.get(name_col) or row_d.get("name") or "Unknown"
                team_cash = 0
                if (
                    cash_col
                    and cash_col in row_d
                    and row_d.get(cash_col) not in (None, "")
                ):
                    try:
                        team_cash = int(
                            float(
                                str(row_d.get(cash_col))
                                .replace(",", "")
                                .replace("€", "")
                                .strip()
                            )
                        )
                    except Exception:
                        team_cash = int(row_d.get(cash_col) or 0)
                if dry_run:
                    migrated_teams += 1
                else:
                    t = Team(name=str(team_name), cash=team_cash)
                    session.add(t)
                    inserted_teams += 1

        print(
            f"Teams to migrate (dry-run={dry_run}): {migrated_teams if dry_run else inserted_teams}"
        )

        # Migrate players
        migrated_players = 0
        inserted_players = 0
        if players_table:
            if not ident_re.match(players_table):
                raise ValueError(
                    "Detected players table name is not a valid SQL identifier"
                )
            cur.execute(f"PRAGMA table_info('{players_table}')")
            cols = [r[1] for r in cur.fetchall()]

            name_col = next((c for c in cols if c.lower() in ("name", "nome")), None)
            role_col = next(
                (c for c in cols if c.lower() in ("role", "ruolo", "position")), None
            )
            team_ref_col = next(
                (
                    c
                    for c in cols
                    if c.lower() in ("team_id", "squadra_id", "idteam", "team")
                ),
                None,
            )
            costo_col = next(
                (c for c in cols if c.lower() in ("costo", "cost", "prezzo")), None
            )
            anni_col = next(
                (c for c in cols if c.lower() in ("anni_contratto", "anni", "years")),
                None,
            )
            opzione_col = next(
                (c for c in cols if c.lower() in ("opzione", "opz", "option")), None
            )
            squadra_reale_col = next(
                (c for c in cols if c.lower() in ("sq", "squadra", "squadra_reale")),
                None,
            )

            if not name_col:
                name_col = cols[1] if len(cols) > 1 else cols[0]

            cur.execute(
                f"SELECT * FROM {players_table}"
            )  # nosec: B608 - identifier validated
            legacy_rows = cur.fetchall()
            # Ensure temp DB players table has the new columns required by ORM inserts
            cur.execute("PRAGMA table_info('players')")
            existing_player_cols = {r[1] for r in cur.fetchall()}
            needed = {
                "costo": "INTEGER",
                "anni_contratto": "INTEGER",
                "opzione": "TEXT",
                "squadra_reale": "TEXT",
            }
            for col, coltype in needed.items():
                if col not in existing_player_cols:
                    try:
                        if not ident_re.match(col):
                            raise ValueError(
                                f"Invalid column name for ALTER TABLE: {col}"
                            )
                        cur.execute(f"ALTER TABLE players ADD COLUMN {col} {coltype}")
                    except Exception as exc:
                        logging.debug(
                            "ALTER TABLE add column %s failed (ignoring): %s", col, exc
                        )
                        pass
            conn.commit()

            for row in legacy_rows:
                row_d = dict(zip(cols, row))
                player_name = row_d.get(name_col) or "Unknown"
                player_role = row_d.get(role_col)
                team_ref = row_d.get(team_ref_col) if team_ref_col in row_d else None

                if dry_run:
                    migrated_players += 1
                    continue

                p = Player(
                    name=str(player_name),
                    role=str(player_role) if player_role else None,
                )
                # populate optional fields when available
                if costo_col and row_d.get(costo_col) not in (None, ""):
                    try:
                        p.costo = int(  # type: ignore[assignment]
                            float(
                                str(row_d.get(costo_col))
                                .replace(",", "")
                                .replace("€", "")
                                .strip()
                            )
                        )
                    except (ValueError, TypeError):
                        p.costo = None  # type: ignore[assignment]

                if anni_col and row_d.get(anni_col) not in (None, ""):
                    try:
                        anni_val = row_d.get(anni_col)
                        p.anni_contratto = int(anni_val) if anni_val is not None else None  # type: ignore[assignment,arg-type]
                    except (ValueError, TypeError):
                        p.anni_contratto = None  # type: ignore[assignment]

                if opzione_col and row_d.get(opzione_col) not in (None, ""):
                    try:
                        p.opzione = str(row_d.get(opzione_col))  # type: ignore[assignment]
                    except (ValueError, TypeError):
                        p.opzione = None  # type: ignore[assignment]

                if squadra_reale_col and row_d.get(squadra_reale_col) not in (None, ""):
                    try:
                        p.squadra_reale = str(row_d.get(squadra_reale_col))  # type: ignore[assignment]
                    except (ValueError, TypeError):
                        p.squadra_reale = None  # type: ignore[assignment]

                # attempt to resolve team reference: numeric id first, then by name/alias
                if team_ref is not None:
                    resolved = None
                    # numeric id
                    try:
                        idx = int(team_ref)
                        resolved = session.query(Team).get(idx)
                    except (ValueError, TypeError):
                        # try by name/alias
                        try:
                            from app.utils.team_utils import resolve_team_by_alias

                            resolved = resolve_team_by_alias(session, str(team_ref))
                        except Exception:
                            resolved = None
                    if resolved:
                        p.team_id = resolved.id

                session.add(p)
                inserted_players += 1

        print(
            f"Players to migrate (dry-run={dry_run}): {migrated_players if dry_run else inserted_players}"
        )

        if not dry_run:
            try:
                session.commit()
            except SQLAlchemyError:
                logging.exception("session.commit() failed during migration")
                session.rollback()
                raise
            try:
                check_s = Session()
                try:
                    tcount = check_s.query(Team).count()
                    pcount = check_s.query(Player).count()
                finally:
                    check_s.close()
            except SQLAlchemyError:
                logging.exception("Failed to query ORM counts after migration")
                tcount = inserted_teams
                pcount = inserted_players
            print(
                f"Migration applied to temporary DB. Teams inserted: {inserted_teams} (orm={tcount}), Players inserted: {inserted_players} (orm={pcount}). Review and move the file to replace your original DB if desired."
            )
        else:
            print("Dry-run completed. No changes written.")
    finally:
        session.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write to the temporary DB (non-dry-run)",
    )
    parser.add_argument("--src", type=str, default=None, help="Path to legacy DB")
    args = parser.parse_args()
    migrate(dry_run=not args.apply, src_db=Path(args.src) if args.src else None)
