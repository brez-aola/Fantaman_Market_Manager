import logging
import os
import shutil

import pytest

from app import create_app


@pytest.fixture()
def tmp_db_path(tmp_path):
    # create a temporary copy of the existing DB if present, otherwise create an empty DB
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src = os.path.join(repo_root, "giocatori.db")
    dest = tmp_path / "giocatori.db"
    if os.path.exists(src):
        shutil.copy(src, dest)
    else:
        # ensure file exists
        dest.write_text("")
        # create minimal schema expected by the app so CI doesn't fail
        import sqlite3

        conn = sqlite3.connect(str(dest))
        cur = conn.cursor()
        cur.execute(
            'CREATE TABLE IF NOT EXISTS giocatori (rowid INTEGER PRIMARY KEY, "Nome" TEXT, squadra TEXT, "Costo" REAL, anni_contratto INTEGER, opzione TEXT)'
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS fantateam (squadra TEXT PRIMARY KEY, carryover REAL DEFAULT 0, cassa_iniziale REAL DEFAULT 0, cassa_attuale REAL)"
        )
        conn.commit()
        conn.close()
    return str(dest)


@pytest.fixture()
def app(tmp_db_path):
    # create app configured to use the temp DB
    test_config = {
        "DB_PATH": tmp_db_path,
        "TESTING": True,
    }
    app = create_app(test_config)
    # ensure tables created via SQLAlchemy models if code expects them
    try:
        app.init_db()
    except Exception as e:
        # models may not be applied; log debug for visibility during CI runs
        logging.debug("app.init_db() failed during test setup: %s", e)
    yield app


def test_index_and_rose_endpoints(app):
    client = app.test_client()

    r = client.get("/")
    assert r.status_code == 200
    assert b"/static/css/main.css" in r.data

    r2 = client.get("/rose")
    assert r2.status_code == 200
    assert b"/static/css/main.css" in r2.data
