import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="Integration test requires DATABASE_URL env var pointing to a Postgres instance",
)


def test_migrate_and_verify_postgres_integration(tmp_path):
    # This test expects a running Postgres instance reachable via DATABASE_URL
    db_url = os.environ["DATABASE_URL"]
    # create a small sqlite source DB with a table
    src = tmp_path / "src_integ.db"
    from sqlalchemy import (
        Column,
        Integer,
        MetaData,
        String,
        Table,
        create_engine,
        insert,
    )

    src_engine = create_engine(f"sqlite:///{src}")
    md = MetaData()
    t = Table(
        "integ_items",
        md,
        Column("id", Integer, primary_key=True),
        Column("label", String),
    )
    md.create_all(bind=src_engine)
    with src_engine.begin() as c:
        c.execute(insert(t), [{"id": 1, "label": "one"}, {"id": 2, "label": "two"}])

    # run migration script with postgres verification method
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "migrate_sqlite_to_postgres.py"
    )
    cmd = [
        "python3",
        str(script),
        "--src",
        str(src),
        "--database-url",
        db_url,
        "--apply",
        "--verify",
        "--verify-method",
        "postgres",
    ]

    proc = subprocess.run(
        cmd, input=b"yes\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    assert proc.returncode == 0, f"Migration failed: {proc.stderr.decode()}"
