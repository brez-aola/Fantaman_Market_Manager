import sqlite3
from app.services.market_service import MarketService


def test_get_name_suggestions_basic():
    svc = MarketService()
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE giocatori (Nome TEXT)")
    conn.executemany("INSERT INTO giocatori (Nome) VALUES (?)", [("Mario",), ("Marco",), ("Mariano",)])
    conn.commit()
    res = svc.get_name_suggestions(conn, "Mar")
    # expect suggestions include names with Mar prefix
    assert any("Mar" in n for n in res)
    conn.close()


def test_get_name_suggestions_db_error():
    svc = MarketService()
    # create a connection and then close it to provoke an error path
    conn = sqlite3.connect(":memory:")
    conn.close()
    # Should not raise, should return empty list on db errors
    res = svc.get_name_suggestions(conn, "Ma")
    assert res == []
