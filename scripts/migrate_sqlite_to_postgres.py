#!/usr/bin/env python3
"""Migrate data from a SQLite DB to a PostgreSQL DB, table-by-table.

Usage examples:
  # dry-run with local sqlite file
  ./scripts/migrate_sqlite_to_postgres.py --src ./giocatori.db --dry-run

  # apply using DATABASE_URL env var
  DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/giocatori \
    ./scripts/migrate_sqlite_to_postgres.py --src ./giocatori.db --apply

The script:
- Creates target tables in Postgres using the SQLAlchemy models in `app.models` (if missing)
- Copies rows preserving primary keys
- Sets Postgres sequences to the max(id) for tables with serial PK
- Supports dry-run mode to preview row counts

It is intended to be idempotent for repeated runs (inserts will skip duplicates when possible).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

from sqlalchemy import MetaData, Table, create_engine, insert, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, help="Path to source SQLite DB file")
    p.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Target SQLAlchemy DB URL (or set DATABASE_URL env var)",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Do not write to target, only report"
    )
    p.add_argument("--apply", action="store_true", help="Apply the migration")
    p.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Export first N rows per table to sample CSVs for review",
    )
    p.add_argument(
        "--backup-target",
        action="store_true",
        help="When used with --apply, run pg_dump to backup the target DB before writing",
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="After apply, verify row counts and checksums between source and target",
    )
    p.add_argument(
        "--verify-fail",
        action="store_true",
        help="Exit with non-zero status if any verification mismatch is detected",
    )
    p.add_argument(
        "--verify-method",
        choices=["python", "postgres"],
        default="python",
        help="Verification checksum method: 'python' (portable) or 'postgres' (DB-native, Postgres only)",
    )
    p.add_argument(
        "--verify-columns",
        help="Comma-separated list of columns to include in checksum/verification (default: all columns)",
    )
    return p.parse_args()


def ensure_engines(src_path: str, target_url: str) -> Tuple[Engine, Engine]:
    if not os.path.isfile(src_path):
        raise SystemExit(f"Source sqlite DB not found: {src_path}")
    sqlite_url = f"sqlite:///{os.path.abspath(src_path)}"
    src_engine = create_engine(sqlite_url)
    if not target_url:
        raise SystemExit(
            "Target database URL not provided. Use --database-url or set DATABASE_URL env var"
        )
    tgt_engine = create_engine(target_url)
    return src_engine, tgt_engine


def create_target_tables(tgt_engine: Engine):
    # import models and create tables in target if missing
    try:
        # Ensure repository root is on sys.path so `app` package is importable
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from app.models import Base  # type: ignore
    except Exception as e:
        raise SystemExit(f"Failed to import app.models: {e}")

    print("Ensuring target tables exist (create_all)")
    Base.metadata.create_all(bind=tgt_engine)


def ensure_logfile() -> str:
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_path = f"migration_{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stdout)],
    )
    logging.info("Migration log started")
    return log_path


def backup_target_db(database_url: str) -> Optional[str]:
    # Expect a postgresql URL like postgresql+psycopg2://user:pass@host:port/db
    if not shutil.which("pg_dump"):
        logging.error("pg_dump not found in PATH; cannot backup target DB")
        return None
    # Try to extract DB name and host from URL (simple parse)
    try:
        # remove 'postgresql+psycopg2://' prefix if present
        # Convert SQLAlchemy-style URL to libpq URL accepted by pg_dump
        libpq_url = database_url.replace("postgresql+psycopg2://", "postgresql://")
        # Try to extract dbname for filename
        parts = libpq_url.rsplit("/", 1)
        if len(parts) != 2:
            logging.error("Unexpected database URL format for pg_dump backup")
            return None
        dbname = parts[1]
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dumpfile = f"pg_dump_target_{dbname}_{ts}.sql"
        logging.info(f"Running pg_dump to {dumpfile}")
        # Pass the libpq-style URL as a single argument to pg_dump
        cmd = ["pg_dump", libpq_url]
        with open(dumpfile, "wb") as out:
            # pass list args and explicit shell=False to avoid shell injection
            # cmd is a list derived from a libpq URL and a fixed program name; using shell=False
            proc = subprocess.run(
                cmd, stdout=out, stderr=subprocess.PIPE
            )  # nosec: B603 - subprocess invoked with list args
            if proc.returncode != 0:
                logging.error(f"pg_dump failed: {proc.stderr.decode()}")
                return None
            logging.info(f"pg_dump wrote: {dumpfile}")
            return dumpfile
    except Exception as e:
        logging.error(f"Failed to run pg_dump: {e}")
        return None


def reflect_tables(engine: Engine, table_names: List[str]) -> MetaData:
    md = MetaData()
    md.reflect(bind=engine, only=table_names)
    return md


def compute_table_checksum(
    engine: Engine, table_name: str, columns: List[str] | None = None
) -> str:
    """Compute a deterministic checksum for a table using an incremental strategy.

    For large tables we compute an MD5 per-row (over the column values) and then
    mix that with the primary-key bytes into a global MD5. This reduces the size
    of data fed to the global hasher and keeps memory usage low by streaming rows.

    Returns a hex digest string.
    """
    md = MetaData()
    tbl = Table(table_name, md, autoload_with=engine)

    # determine ordering: prefer PK columns for deterministic order
    order_cols = list(tbl.primary_key.columns)
    if not order_cols:
        order_cols = list(tbl.columns)

    # select only requested columns if provided
    selected_cols = [c for c in tbl.columns if (columns is None or c.name in columns)]
    if not selected_cols:
        # nothing to hash
        return ""

    sel = select(*selected_cols).order_by(*order_cols)

    # Use SHA256 for stronger hashing; usedforsecurity flag set where supported.
    # We use hashlib.sha256 for streaming row mixing. This is not used for
    # cryptographic authentication, only for change-detection, but prefer
    # a stronger hash to satisfy static analyzers.
    global_h = hashlib.new("sha256")
    chunk = 500
    with engine.connect() as conn:
        # stream results to avoid pulling everything into memory
        result = conn.execution_options(stream_results=True).execute(sel)
        # use yield_per to fetch in chunks (SQLAlchemy provides this on Result)
        try:
            iterator = result.yield_per(chunk)
        except Exception as e:
            logging.exception(
                "yield_per not supported, falling back to iterator: %s", e
            )
            # fallback to plain iterator
            iterator = iter(result)

        for row in iterator:
            if hasattr(row, "_mapping"):
                mapping = row._mapping
            else:
                try:
                    mapping = dict(row)
                except Exception as e:
                    logging.debug(
                        "Row to dict failed, falling back to positional mapping: %s", e
                    )
                    mapping = {c.name: row[i] for i, c in enumerate(tbl.columns)}

            # per-row hash: MD5 over the concatenated column values (stable order)
            parts = []
            for c in selected_cols:
                v = mapping.get(c.name)
                parts.append("" if v is None else str(v))
            row_bytes = "|".join(parts).encode("utf-8")
            # per-row hash using sha256 (use hashlib.new with explicit name so
            # Bandit's plugin can reliably inspect the call)
            row_hash = hashlib.new("sha256", row_bytes).digest()

            # primary key bytes (concatenated) to mix into global hash
            pk_parts = []
            for c in tbl.primary_key.columns:
                pkv = mapping.get(c.name)
                pk_parts.append("" if pkv is None else str(pkv))
            pk_bytes = "|".join(pk_parts).encode("utf-8") if pk_parts else b""

            # Mix: global_h.update(pk_bytes + row_hash)
            if pk_bytes:
                global_h.update(pk_bytes)
            global_h.update(row_hash)

    return global_h.hexdigest()


def compute_table_checksum_postgres(
    engine: Engine, table_name: str, columns: List[str] | None = None
) -> str:
    """Compute a checksum using Postgres functions by hashing row text on the DB side.

    This executes a SQL query that concatenates columns into text and computes md5
    per-row then aggregates with string_agg to produce a deterministic checksum.
    This is Postgres-only and much faster for large tables since it runs in the DB.
    """
    if engine.dialect.name != "postgresql":
        raise RuntimeError(
            "Postgres checksum requested but target engine is not postgresql"
        )

    md = MetaData()
    tbl = Table(table_name, md, autoload_with=engine)

    # Build a SQL that computes per-row md5 of canonicalized column text, then
    # aggregates them in PK order to produce a deterministic checksum. We apply
    # DB-side canonicalization for json/jsonb and array types to ensure stable
    # textual representation across rows.
    col_names = [c.name for c in tbl.columns]
    pk_names = [c.name for c in tbl.primary_key.columns]
    if not col_names:
        return ""
    # honor columns filter if provided
    if columns is not None:
        col_names = [n for n in col_names if n in columns]

    concat_exprs = []
    from sqlalchemy.dialects.postgresql import ARRAY, JSON, JSONB

    for col in tbl.columns:
        name = col.name
        if columns is not None and name not in columns:
            continue
        # JSON/JSONB: cast to jsonb and use its text representation; md5 is applied later
        if isinstance(col.type, (JSON, JSONB)):
            # safe to reference column name directly after validation below
            expr = f"coalesce(({name}::jsonb)::text, '')"
        # ARRAY: sort elements and join to stable text representation
        elif isinstance(col.type, ARRAY):
            # unnest the array, order elements, aggregate back to text
            expr = f"coalesce((SELECT array_to_string(array_agg(e ORDER BY e), '|' ) FROM unnest({name}) e), '')"
        else:
            expr = f"coalesce({name}::text, '')"

        concat_exprs.append(expr)

    # Validate table and column identifiers to reduce injection risk
    ident_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    if not ident_re.match(table_name):
        raise ValueError("Invalid table name for postgres checksum")
    for nm in pk_names or col_names:
        if not ident_re.match(nm):
            raise ValueError("Invalid column name for postgres checksum")

    concat_cols = ", ".join(concat_exprs)

    # Note: we use md5 on the DB side for compatibility with Postgres md5();
    # this is DB-side-only and acceptable for integrity checks (not security).
    # All identifiers (table and columns) have been validated above; build final SQL safely
    sql = text(
        (
            "SELECT md5(string_agg(row_md5, '' ORDER BY pk_sort)) as checksum FROM ("
            "SELECT md5(concat_ws('|', "
            + concat_cols
            + ")) AS row_md5, concat_ws('|', "
            + (", ".join(pk_names or col_names))
            + ") AS pk_sort FROM "
            + table_name
            + ") s"
        )
    )

    with engine.connect() as conn:
        try:
            res = conn.execute(sql).scalar()
            return res or ""
        except SQLAlchemyError as e:
            logging.exception(
                "Postgres checksum query failed for %s: %s", table_name, e
            )
            return ""


def verify_table(
    src_engine: Engine,
    tgt_engine: Engine,
    table_name: str,
    columns: List[str] | None = None,
):
    """Return verification info: counts and checksums for source and target.

    Returns a dict with keys: src_count, tgt_count, count_match, src_checksum, tgt_checksum, checksum_match
    """
    src_md = MetaData()
    src_tbl = Table(table_name, src_md, autoload_with=src_engine)
    tgt_md = MetaData()
    tgt_tbl = Table(table_name, tgt_md, autoload_with=tgt_engine)

    with src_engine.connect() as s:
        try:
            src_count = (
                s.execute(select(text("count(*)")).select_from(src_tbl)).scalar() or 0
            )
        except Exception as e:
            logging.exception("Failed to get source count for %s: %s", table_name, e)
            src_count = 0

    with tgt_engine.connect() as t:
        try:
            tgt_count = (
                t.execute(select(text("count(*)")).select_from(tgt_tbl)).scalar() or 0
            )
        except Exception as e:
            logging.exception("Failed to get target count for %s: %s", table_name, e)
            tgt_count = 0

    count_match = int(src_count) == int(tgt_count)

    # compute checksums (may be slow) — default python implementation
    try:
        src_checksum = compute_table_checksum(src_engine, table_name, columns=columns)
    except Exception as e:
        logging.exception("Failed to compute source checksum for %s: %s", table_name, e)
        src_checksum = ""
    try:
        tgt_checksum = compute_table_checksum(tgt_engine, table_name, columns=columns)
    except Exception as e:
        logging.exception("Failed to compute target checksum for %s: %s", table_name, e)
        tgt_checksum = ""

    checksum_match = (src_checksum == tgt_checksum) and src_checksum != ""

    return {
        "src_count": int(src_count),
        "tgt_count": int(tgt_count),
        "count_match": count_match,
        "src_checksum": src_checksum,
        "tgt_checksum": tgt_checksum,
        "checksum_match": checksum_match,
    }


def copy_table(
    src_engine: Engine,
    tgt_engine: Engine,
    table_name: str,
    dry_run: bool = True,
    sample: int = 0,
):
    print(f"Processing table: {table_name}")
    logging.info(f"Processing table: {table_name}")
    src_md = MetaData()
    src_table = Table(table_name, src_md, autoload_with=src_engine)

    with src_engine.connect() as src_conn:
        try:
            src_count = src_conn.execute(
                select(text("count(*)")).select_from(src_table)
            ).scalar()
        except Exception as e:
            raise RuntimeError(f"Failed to read source table '{table_name}': {e}")

        print(f"  Source rows: {src_count}")
        logging.info(f"Source rows for {table_name}: {src_count}")
        if sample and src_count:
            # export first `sample` rows for review
            with src_engine.connect() as c:
                res = c.execute(select(src_table).limit(sample)).fetchall()
                sample_path = f"migration_sample_{table_name}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
                with open(sample_path, "w", newline="") as sf:
                    w = csv.writer(sf)
                    # Derive header from the reflected table columns (stable)
                    header = [c.name for c in src_table.columns]
                    if header:
                        w.writerow(header)
                        for r in res:
                            # Prefer Row._mapping when present (SQLAlchemy 1.4+)
                            if hasattr(r, "_mapping"):
                                mapping = r._mapping
                            else:
                                try:
                                    mapping = dict(r)
                                except (TypeError, ValueError) as e:
                                    # Fallback: enumerate positional values
                                    logging.debug(
                                        "Row to dict failed while writing sample for %s: %s",
                                        table_name,
                                        e,
                                    )
                                    mapping = {h: r[i] for i, h in enumerate(header)}
                            w.writerow([mapping.get(h) for h in header])
                    else:
                        w.writerow([])
                logging.info(f"Wrote sample rows to {sample_path}")

        if dry_run:
            # In dry-run mode return counts: (source_rows, inserted, skipped)
            return src_count, 0, 0

        rows = src_conn.execute(select(src_table)).fetchall()

    # Only reflect/load the target table when we will write to it
    tgt_md = MetaData()
    try:
        tgt_table = Table(table_name, tgt_md, autoload_with=tgt_engine)
    except Exception as e:
        raise RuntimeError(f"Failed to reflect target table '{table_name}': {e}")

    inserted = 0
    skipped = 0
    with tgt_engine.begin() as tgt_conn:
        for row in rows:
            # Normalize different Row shapes to a dict
            if hasattr(row, "_mapping"):
                data = dict(row._mapping)
            else:
                try:
                    data = {c.name: row[i] for i, c in enumerate(src_table.columns)}
                except Exception as e:
                    logging.debug(
                        "Falling back to positional mapping for row in %s: %s",
                        table_name,
                        e,
                    )
                    data = dict(row)

            # Build insert; prefer postgres ON CONFLICT DO NOTHING when available
            ins = insert(tgt_table).values(**data)
            if tgt_engine.dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                ins = pg_insert(tgt_table).values(**data).on_conflict_do_nothing()

            try:
                res = tgt_conn.execute(ins)
            except IntegrityError as ie:
                # For non-postgres DBs we may hit unique constraint violations; treat as skipped
                logging.warning(f"IntegrityError inserting into {table_name}: {ie}")
                skipped += 1
                continue

            # SQLAlchemy Result.rowcount should indicate whether a row was inserted
            try:
                rc = res.rowcount if hasattr(res, "rowcount") else None
            except Exception as e:
                logging.debug(
                    "Failed to obtain rowcount for insert result into %s: %s",
                    table_name,
                    e,
                )
                rc = None

            if rc is None:
                # Fallback: assume success
                inserted += 1
            elif rc > 0:
                inserted += rc
            else:
                skipped += 1

    logging.info(
        f"Inserted: {inserted}, Skipped (conflicts): {skipped} into {table_name}"
    )
    print(f"  Inserted: {inserted}, Skipped (conflicts): {skipped}")

    # If postgres, adjust sequence if there's an integer PK named 'id'
    if tgt_engine.dialect.name == "postgresql":
        with tgt_engine.connect() as conn:
            try:
                max_id = (
                    conn.execute(select(text("max(id)")))
                    .select_from(tgt_table)
                    .scalar()
                    or 0
                )
                seq_stmt = text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}','id'), :v, true)"
                )
                conn.execute(seq_stmt, {"v": int(max_id)})
                print(f"  Updated sequence for {table_name} to {max_id}")
            except Exception as e:
                logging.debug(f"Failed to update sequence for {table_name}: {e}")

    return src_count, inserted, skipped


def main():
    args = parse_args()
    log_path = ensure_logfile()
    logging.info(f"Args: {args}")
    # reference log_path so linters don't mark it as unused
    logging.info("Migration logfile: %s", log_path)
    src_engine, tgt_engine = ensure_engines(args.src, args.database_url)

    # order matters due to FKs: leagues -> teams -> players -> team_aliases -> canonical_mappings -> import_audit
    table_order = [
        "leagues",
        "teams",
        "players",
        "team_aliases",
        "canonical_mappings",
        "import_audit",
    ]

    print("Pre-check: will operate in dry-run mode unless --apply is provided")
    if args.dry_run and not args.apply:
        print("Dry-run: no changes will be applied")

    if args.apply:
        confirm = input(
            "Apply migration to target DB? This will write data. Type 'yes' to proceed: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted by user")
            logging.info("User aborted apply")
            sys.exit(1)

    # If apply and backup requested, attempt to backup the target DB
    if args.apply and args.backup_target:
        if args.database_url:
            bf = backup_target_db(args.database_url)
            if bf is None:
                print("Target backup failed or pg_dump not available. Aborting.")
                logging.error("Target backup failed; aborting apply")
                sys.exit(1)
        else:
            print("No database URL supplied; cannot backup target")
            logging.error("No database URL for target backup")
            sys.exit(1)

    # create target tables if applying
    if args.apply:
        create_target_tables(tgt_engine)

    # parse verify columns if provided
    # Support two formats:
    # - global comma list: "col1,col2"
    # - per-table mapping: "teams:id,name;players:id,name,team_id"
    cols = None
    per_table_cols = {}
    if getattr(args, "verify_columns", None):
        raw = args.verify_columns.strip()
        if ";" in raw or ":" in raw:
            # parse per-table mapping
            for part in raw.split(";"):
                part = part.strip()
                if not part:
                    continue
                if ":" not in part:
                    # malformed part; skip
                    continue
                tbl, clist = part.split(":", 1)
                tbl = tbl.strip()
                clist = [c.strip() for c in clist.split(",") if c.strip()]
                if tbl and clist:
                    per_table_cols[tbl] = clist
        else:
            cols = [c.strip() for c in raw.split(",") if c.strip()]

    total_rows = 0
    report_rows = []
    any_verification_mismatch = False
    for t in table_order:
        try:
            src_cnt, inserted, skipped = copy_table(
                src_engine, tgt_engine, t, dry_run=(not args.apply), sample=args.sample
            )
            total_rows += src_cnt or 0
            row = {
                "table": t,
                "source_rows": src_cnt or 0,
                "inserted": inserted,
                "skipped": skipped,
            }
            # optionally verify counts and checksums after apply
            if args.verify and args.apply:
                try:
                    # support different verification methods
                    if args.verify_method == "postgres":
                        # try to use DB-native checksum on target (Postgres)
                        if tgt_engine.dialect.name != "postgresql":
                            raise RuntimeError(
                                "verify-method=postgres requested but target DB is not Postgres"
                            )
                        # If source is also Postgres, compute DB-native there too for speed
                        # determine columns to use for this table (per-table override wins)
                        use_cols = per_table_cols.get(t, cols)
                        if src_engine.dialect.name == "postgresql":
                            src_checksum = compute_table_checksum_postgres(
                                src_engine, t, columns=use_cols
                            )
                        else:
                            src_checksum = compute_table_checksum(
                                src_engine, t, columns=use_cols
                            )
                        tgt_checksum = compute_table_checksum_postgres(
                            tgt_engine, t, columns=use_cols
                        )
                        v = {
                            "src_count": None,
                            "tgt_count": None,
                            "count_match": None,
                            "src_checksum": src_checksum,
                            "tgt_checksum": tgt_checksum,
                            "checksum_match": src_checksum == tgt_checksum,
                        }
                    else:
                        use_cols = per_table_cols.get(t, cols)
                        v = verify_table(src_engine, tgt_engine, t, columns=use_cols)
                    row.update(
                        {
                            "src_count": v.get("src_count"),
                            "tgt_count": v.get("tgt_count"),
                            "count_match": v.get("count_match"),
                            "src_checksum": v.get("src_checksum"),
                            "tgt_checksum": v.get("tgt_checksum"),
                            "checksum_match": v.get("checksum_match"),
                        }
                    )
                    # track mismatches immediately so we can fail-fast if requested
                    if (v.get("count_match") is False) or (
                        v.get("checksum_match") is False
                    ):
                        any_verification_mismatch = True
                    logging.info(
                        f"Verification for {t}: count_match={v.get('count_match')} checksum_match={v.get('checksum_match')}"
                    )
                except Exception as e:
                    logging.exception("Verification failed for %s: %s", t, e)
                    row.update({"verification_error": str(e)})
            report_rows.append(row)
        except Exception as e:
            logging.exception("Error copying table %s: %s", t, e)
            print(f"Error copying table {t}: {e}")
    print(f"Done. Processed approximate total rows: {total_rows}")

    # Write CSV report
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    report_path = f"migration_report_{ts}.csv"
    # Determine fieldnames dynamically to include optional verification fields
    base_fields = ["table", "source_rows", "inserted", "skipped"]
    extra_fields = []
    for r in report_rows:
        for k in r.keys():
            if k not in base_fields and k not in extra_fields:
                extra_fields.append(k)
    fieldnames = base_fields + extra_fields

    with open(report_path, "w", newline="") as cf:
        writer = csv.DictWriter(cf, fieldnames=fieldnames)
        writer.writeheader()
        for r in report_rows:
            # only write keys that are in the fieldnames to avoid errors
            row = {k: v for k, v in r.items() if k in fieldnames}
            writer.writerow(row)

    print(f"Wrote migration report: {report_path}")

    # If requested, fail the script when verification mismatches occurred
    if args.verify_fail:
        # scan report rows for checksum/count mismatches
        for r in report_rows:
            if r.get("count_match") is False or r.get("checksum_match") is False:
                any_verification_mismatch = True
                break

        if any_verification_mismatch:
            logging.error(
                "Verification mismatches detected; exiting with non-zero status as requested (--verify-fail)"
            )
            print(
                "Verification mismatches detected; see log/report. Exiting with status 2"
            )
            sys.exit(2)


if __name__ == "__main__":
    main()
