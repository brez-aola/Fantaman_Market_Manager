import sqlite3

from app.services.market_service import MarketService


def setup_memory_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # minimal giocatori table used by service
    cur.execute(
        """
        CREATE TABLE giocatori (
            Nome TEXT,
            Costo REAL,
            squadra TEXT,
            anni_contratto INTEGER,
            opzione TEXT
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
    return conn


def test_atomic_charge_and_refund():
    svc = MarketService()
    conn = setup_memory_db()
    try:
        # charge 50 from TeamA (no row exists -> row created with 300 then charged)
        ok = svc.atomic_charge_team(conn, "TeamA", 50)
        assert ok is True
        start, att = svc.get_team_cash(conn, "TeamA")
        assert start == 300.0
        assert att == 250.0
        # refund back
        svc.refund_team(conn, "TeamA", 50)
        start2, att2 = svc.get_team_cash(conn, "TeamA")
        assert att2 == 300.0
    finally:
        conn.close()


def test_assign_player_insufficient_funds():
    svc = MarketService()
    conn = setup_memory_db()
    try:
        cur = conn.cursor()
        # create team with small balance
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            ("PoorTeam", 0, 100.0, 10.0),
        )
        # create a player row
        cur.execute(
            "INSERT INTO giocatori(Nome, Costo, squadra) VALUES (?,?,?)",
            ("Mario", 0.0, None),
        )
        pid = cur.lastrowid
        conn.commit()
        res = svc.assign_player(conn, pid, "PoorTeam", 50, 1, "SI")
        assert res.get("success") is False
        assert "available" in res
        assert res["available"] == 10.0
    finally:
        conn.close()


def test_assign_and_move_refunds():
    svc = MarketService()
    conn = setup_memory_db()
    try:
        cur = conn.cursor()
        # create two teams
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            ("TeamOld", 0, 300.0, 100.0),
        )
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            ("TeamNew", 0, 300.0, 300.0),
        )
        # create player assigned to TeamOld with cost 20
        cur.execute(
            "INSERT INTO giocatori(Nome, Costo, squadra) VALUES (?,?,?)",
            ("Luigi", 20.0, "TeamOld"),
        )
        pid = cur.lastrowid
        conn.commit()
        # move player to TeamNew with cost 30
        res = svc.assign_player(conn, pid, "TeamNew", 30, 1, "SI")
        assert res.get("success") is True
        # TeamOld should have been refunded 20 -> its cassa_attuale increases from 100 to 120
        start_old, att_old = svc.get_team_cash(conn, "TeamOld")
        assert att_old == 120.0
        # TeamNew should be charged 30 -> 300 - 30 = 270
        start_new, att_new = svc.get_team_cash(conn, "TeamNew")
        assert att_new == 270.0
    finally:
        conn.close()


def test_unassign_refunds():
    svc = MarketService()
    conn = setup_memory_db()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            ("TeamX", 0, 300.0, 250.0),
        )
        cur.execute(
            "INSERT INTO giocatori(Nome, Costo, squadra) VALUES (?,?,?)",
            ("Peach", 50.0, "TeamX"),
        )
        pid = cur.lastrowid
        conn.commit()
        # unassign player (squadra=None) -> refund 50
        res = svc.assign_player(conn, pid, None, None, None, None)
        assert res.get("success") is True
        start, att = svc.get_team_cash(conn, "TeamX")
        # will be refunded to 300.0
        assert att == 300.0
    finally:
        conn.close()
