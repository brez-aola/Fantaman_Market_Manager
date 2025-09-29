import sqlite3

from app.services.market_service import MarketService


def test_normalize_assignment_values_parsing():
    svc = MarketService()
    # numeric formats
    s, c, a, o = svc.normalize_assignment_values("Team", "1,234.56", "1", "SI")
    assert s == "Team"
    assert isinstance(c, float)

    s, c, a, o = svc.normalize_assignment_values("Team", "1.234,56", "2", "NO")
    assert isinstance(c, float)

    # empty custo
    s, c, a, o = svc.normalize_assignment_values("Team", "", "1", "SI")
    assert c == 0.0


def test_prev_cost_parsing_from_db():
    svc = MarketService()
    # prepare in-memory sqlite DB and table
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE giocatori (squadra TEXT, FantaSquadra TEXT, Costo TEXT)")
    cur.execute(
        "INSERT INTO giocatori (squadra, FantaSquadra, Costo) VALUES (?, ?, ?)",
        ("A", "B", "12.5"),
    )
    conn.commit()
    # use _table_has_column to ensure FantaSquadra is visible
    assert svc._table_has_column(conn, "giocatori", "FantaSquadra")
    # simulate assign_player reading prev_cost (no exception should be raised)
    res = svc.assign_player(conn, 1, "TeamX", "10", "1", "NO")
    # assign_player returns dict; success True/False depending on funds, but the function should run
    assert isinstance(res, dict)
    conn.close()
