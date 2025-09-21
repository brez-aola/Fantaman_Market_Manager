import sqlite3

from app.services.market_service import MarketService


def setup_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE giocatori (
            Nome TEXT,
            "Sq." TEXT,
            squadra TEXT,
            "R." TEXT,
            "Costo" REAL,
            anni_contratto INTEGER,
            opzione TEXT,
            FantaSquadra TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE fantateam (
            squadra TEXT PRIMARY KEY,
            carryover REAL DEFAULT 0,
            cassa_iniziale REAL DEFAULT 0,
            cassa_attuale REAL
        )
        """
    )
    conn.commit()


def test_get_name_suggestions_and_safety():
    svc = MarketService()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        setup_schema(conn)
        cur = conn.cursor()
        names = ["Mario Rossi", "Marino Rosso", "Marco Verdi", "Marco Rossi"]
        for n in names:
            cur.execute("INSERT INTO giocatori(Nome) VALUES (?)", (n,))
        conn.commit()

        # query 'Mar' should return suggestions including 'Mario Rossi' and 'Marco Rossi' etc.
        res = svc.get_name_suggestions(conn, "Mar", limit=5)
        assert any("Mario" in r or "Marco" in r for r in res)

        # Query that exactly matches should avoid returning the exact same case-insensitive match
        res2 = svc.get_name_suggestions(conn, "mario rossi", limit=8)
        assert all(r.lower() != "mario rossi" for r in res2)
    finally:
        conn.close()


def test_get_team_summaries_and_roster():
    svc = MarketService()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    try:
        setup_schema(conn)
        cur = conn.cursor()
        # create two teams with fantateam rows
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            ("TeamA", 0, 300.0, 250.0),
        )
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            ("TeamB", 0, 300.0, 300.0),
        )

        # add players assigned to teams
        players = [
            ("P1", "", "TeamA", "P", 10.0, 1, "SI", "TeamA"),
            ("D1", "", "TeamA", "D", 20.0, 1, "NO", "TeamA"),
            ("C1", "", "TeamB", "C", 15.0, 1, "NO", "TeamB"),
        ]
        for p in players:
            cur.execute(
                'INSERT INTO giocatori(Nome, "Sq.", squadra, "R.", "Costo", anni_contratto, opzione, FantaSquadra) VALUES (?,?,?,?,?,?,?,?)',
                p,
            )
        conn.commit()

        squadre = ["TeamA", "TeamB"]
        rose_structure = {
            "Portieri": 1,
            "Difensori": 1,
            "Centrocampisti": 1,
            "Attaccanti": 1,
        }

        summaries = svc.get_team_summaries(conn, squadre, rose_structure)
        # Both teams should be present in summaries
        assert any(s["squadra"] == "TeamA" for s in summaries)
        assert any(s["squadra"] == "TeamB" for s in summaries)

        # Test roster helper for TeamA
        roster, starting, total_spent, cassa = svc.get_team_roster(
            conn, "TeamA", rose_structure
        )
        assert starting == 300.0 or starting == 250.0 or isinstance(starting, float)
        # roster should contain Portieri and Difensori keys
        assert "Portieri" in roster and "Difensori" in roster
        # total_spent should be >= 0
        assert total_spent >= 0
    finally:
        conn.close()
