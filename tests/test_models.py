import sqlite3

from app import create_app


def test_init_db_creates_tables(tmp_path):
    db_file = tmp_path / "test_giocatori.db"
    cfg = {"DB_PATH": str(db_file), "TESTING": True}
    app = create_app(cfg)

    # should create SQLAlchemy tables without raising
    app.init_db()

    # check sqlite_master to ensure tables exist
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    conn.close()

    assert "teams" in tables
    assert "players" in tables
