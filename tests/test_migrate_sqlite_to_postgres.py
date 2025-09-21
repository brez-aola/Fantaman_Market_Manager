import os
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import MetaData, Table, Column, Integer, String, create_engine, insert, select

from scripts import migrate_sqlite_to_postgres as migr


def test_copy_table_dry_run_and_sample(tmp_path, monkeypatch):
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        # create source sqlite file
        src_file = tmp_path / "src.db"
        src_url = f"sqlite:///{src_file}"
        src_engine = create_engine(src_url)

        md = MetaData()
        t = Table("mytable", md, Column("id", Integer, primary_key=True), Column("name", String))
        md.create_all(bind=src_engine)

        with src_engine.begin() as conn:
            conn.execute(insert(t), [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}, {"id": 3, "name": "carol"}])

        # target engine can be an in-memory sqlite (not used in dry-run)
        tgt_engine = create_engine("sqlite:///:memory:")

        src_cnt, inserted, skipped = migr.copy_table(src_engine, tgt_engine, "mytable", dry_run=True, sample=2)

        assert src_cnt == 3
        assert inserted == 0
        assert skipped == 0

        # verify a sample CSV was written
        files = list(tmp_path.glob("migration_sample_mytable_*.csv"))
        assert len(files) == 1
    finally:
        os.chdir(cwd)


def test_copy_table_apply_inserts(tmp_path):
    # create source sqlite
    src_file = tmp_path / "src_apply.db"
    src_url = f"sqlite:///{src_file}"
    src_engine = create_engine(src_url)

    md_src = MetaData()
    t_src = Table("items", md_src, Column("id", Integer, primary_key=True), Column("value", String))
    md_src.create_all(bind=src_engine)
    with src_engine.begin() as conn:
        conn.execute(insert(t_src), [{"id": 10, "value": "x"}, {"id": 11, "value": "y"}])

    # create target sqlite file and same table
    tgt_file = tmp_path / "tgt_apply.db"
    tgt_url = f"sqlite:///{tgt_file}"
    tgt_engine = create_engine(tgt_url)
    md_tgt = MetaData()
    t_tgt = Table("items", md_tgt, Column("id", Integer, primary_key=True), Column("value", String))
    md_tgt.create_all(bind=tgt_engine)

    src_cnt, inserted, skipped = migr.copy_table(src_engine, tgt_engine, "items", dry_run=False, sample=0)

    # Two rows existed in source
    assert src_cnt == 2
    assert inserted == 2
    assert skipped == 0

    # verify target rows
    with tgt_engine.connect() as c:
        res = c.execute(select(t_tgt)).fetchall()
        assert len(res) == 2


def test_backup_target_db_monkeypatched(tmp_path, monkeypatch):
    # Ensure working dir is tmp_path so dumpfile is written there
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        # simulate pg_dump present
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pg_dump")

        class DummyProc:
            def __init__(self):
                self.returncode = 0
                self.stderr = b""

        def fake_run(cmd, stdout=None, stderr=None):
            # write a small SQL file to stdout path
            if isinstance(stdout, (io.BufferedWriter,)):
                stdout.write(b"-- dummy pg_dump output\n")
            return DummyProc()

        # Avoid importing io in module scope; import here
        import io

        monkeypatch.setattr(subprocess, "run", fake_run)

        url = "postgresql+psycopg2://user:pass@localhost:5432/mydb"
        dumpfile = migr.backup_target_db(url)
        assert dumpfile is not None
        assert Path(dumpfile).exists()
    finally:
        os.chdir(cwd)


def test_verify_table_checksums_match(tmp_path):
    # create source sqlite with a table
    src_file = tmp_path / "src_verify.db"
    src_url = f"sqlite:///{src_file}"
    src_engine = create_engine(src_url)

    md = MetaData()
    t = Table("things", md, Column("id", Integer, primary_key=True), Column("a", String), Column("b", String))
    md.create_all(bind=src_engine)
    with src_engine.begin() as c:
        c.execute(insert(t), [{"id": 1, "a": "x", "b": "y"}, {"id": 2, "a": "p", "b": "q"}])

    # create target sqlite with identical rows
    tgt_file = tmp_path / "tgt_verify.db"
    tgt_url = f"sqlite:///{tgt_file}"
    tgt_engine = create_engine(tgt_url)
    md2 = MetaData()
    t2 = Table("things", md2, Column("id", Integer, primary_key=True), Column("a", String), Column("b", String))
    md2.create_all(bind=tgt_engine)
    with tgt_engine.begin() as c:
        c.execute(insert(t2), [{"id": 1, "a": "x", "b": "y"}, {"id": 2, "a": "p", "b": "q"}])

    # import the verify function from the script
    from scripts.migrate_sqlite_to_postgres import verify_table

    res = verify_table(src_engine, tgt_engine, "things")
    assert res["src_count"] == 2
    assert res["tgt_count"] == 2
    assert res["count_match"] is True
    assert res["checksum_match"] is True


def test_verify_fail_exit_on_mismatch(tmp_path):
    # create source sqlite with a table
    src_file = tmp_path / "src_mismatch.db"
    src_url = f"sqlite:///{src_file}"
    src_engine = create_engine(src_url)

    md = MetaData()
    # Use a table that the migration script actually processes
    t = Table("canonical_mappings", md, Column("id", Integer, primary_key=True), Column("variant", String), Column("canonical", String))
    md.create_all(bind=src_engine)
    with src_engine.begin() as c:
        c.execute(insert(t), [{"id": 1, "variant": "v1", "canonical": "c1"}])

    # create target sqlite with a different row to force mismatch
    tgt_file = tmp_path / "tgt_mismatch.db"
    tgt_url = f"sqlite:///{tgt_file}"
    tgt_engine = create_engine(tgt_url)
    md2 = MetaData()
    t2 = Table("canonical_mappings", md2, Column("id", Integer, primary_key=True), Column("variant", String), Column("canonical", String))
    md2.create_all(bind=tgt_engine)
    with tgt_engine.begin() as c:
        c.execute(insert(t2), [{"id": 1, "variant": "v1", "canonical": "DIFFERENT"}])

    # run the migration script with --verify --verify-fail; point to local DBs
    script = Path(__file__).resolve().parents[1] / "scripts" / "migrate_sqlite_to_postgres.py"
    cmd = [
        "python3",
        str(script),
        "--src",
        str(src_file),
        "--database-url",
        f"sqlite:///{tgt_file}",
        "--apply",
        "--verify",
        "--verify-fail",
    ]

    # Run and expect a non-zero exit (2) due to verification mismatch
    import subprocess

    proc = subprocess.run(cmd, input=b"yes\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.returncode != 0


def test_verify_columns_exclude_column(tmp_path):
    # create source sqlite with an extra volatile column
    src_file = tmp_path / "src_cols.db"
    src_engine = create_engine(f"sqlite:///{src_file}")
    md = MetaData()
    t = Table("canonical_mappings", md, Column("id", Integer, primary_key=True), Column("variant", String), Column("canonical", String), Column("volatile", String))
    md.create_all(bind=src_engine)
    with src_engine.begin() as c:
        c.execute(insert(t), [{"id": 1, "variant": "v1", "canonical": "c1", "volatile": "a"}])

    tgt_file = tmp_path / "tgt_cols.db"
    tgt_engine = create_engine(f"sqlite:///{tgt_file}")
    md2 = MetaData()
    t2 = Table("canonical_mappings", md2, Column("id", Integer, primary_key=True), Column("variant", String), Column("canonical", String), Column("volatile", String))
    md2.create_all(bind=tgt_engine)
    with tgt_engine.begin() as c:
        # same except volatile differs
        c.execute(insert(t2), [{"id": 1, "variant": "v1", "canonical": "c1", "volatile": "b"}])

    # verify using only variant+canonical columns
    from scripts.migrate_sqlite_to_postgres import compute_table_checksum, verify_table

    cols = ["variant", "canonical"]
    ssum = compute_table_checksum(src_engine, "canonical_mappings", columns=cols)
    tsum = compute_table_checksum(tgt_engine, "canonical_mappings", columns=cols)
    assert ssum == tsum
    res = verify_table(src_engine, tgt_engine, "canonical_mappings", columns=cols)
    assert res["checksum_match"] is True


import pytest


@pytest.mark.cli
def test_cli_verify_columns_per_table(tmp_path):
    # Ensure the script accepts per-table verify-columns mapping and that it causes verification to pass
    src_file = tmp_path / "src_cli_cols.db"
    src_engine = create_engine(f"sqlite:///{src_file}")
    md = MetaData()
    t = Table("canonical_mappings", md, Column("id", Integer, primary_key=True), Column("variant", String), Column("canonical", String), Column("volatile", String))
    md.create_all(bind=src_engine)
    with src_engine.begin() as c:
        c.execute(insert(t), [{"id": 1, "variant": "v1", "canonical": "c1", "volatile": "a"}])

    tgt_file = tmp_path / "tgt_cli_cols.db"
    tgt_engine = create_engine(f"sqlite:///{tgt_file}")
    md2 = MetaData()
    t2 = Table("canonical_mappings", md2, Column("id", Integer, primary_key=True), Column("variant", String), Column("canonical", String), Column("volatile", String))
    md2.create_all(bind=tgt_engine)
    with tgt_engine.begin() as c:
        c.execute(insert(t2), [{"id": 1, "variant": "v1", "canonical": "c1", "volatile": "b"}])

    script = Path(__file__).resolve().parents[1] / "scripts" / "migrate_sqlite_to_postgres.py"
    # per-table mapping: only include variant and canonical for canonical_mappings
    mapping = "canonical_mappings:variant,canonical"
    cmd = [
        "python3",
        str(script),
        "--src",
        str(src_file),
        "--database-url",
        f"sqlite:///{tgt_file}",
        "--apply",
        "--verify",
        "--verify-method",
        "python",
        "--verify-columns",
        mapping,
    ]

    proc = subprocess.run(cmd, input=b"yes\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Expect success (exit code 0) because verification uses only variant+canonical which match
    assert proc.returncode == 0
