import sqlite3
import tempfile
from app import create_app


def test_assignment_shows_on_team_page():
    tf = tempfile.NamedTemporaryFile(delete=False)
    dbp = tf.name
    tf.close()

    app = create_app({"DB_PATH": dbp, "TESTING": True})
    with app.test_client() as client:
        conn = sqlite3.connect(dbp)
        cur = conn.cursor()
        # create minimal tables required for assignment
        cur.execute(
            'CREATE TABLE IF NOT EXISTS fantateam (squadra TEXT PRIMARY KEY, carryover REAL, cassa_iniziale REAL, cassa_attuale REAL)'
        )
        cur.execute(
            "INSERT OR REPLACE INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            ("FC Bioparco", 0, 300.0, 300.0),
        )
        cur.execute(
            'CREATE TABLE IF NOT EXISTS giocatori ("Nome" TEXT, squadra TEXT, "R." TEXT, "Costo" REAL, anni_contratto INTEGER, opzione TEXT)'
        )
        cur.execute('INSERT INTO giocatori("Nome", "R.") VALUES (?,?)', ("INT_TEST_PLAYER", "C"))
        pid = cur.lastrowid
        conn.commit()
        conn.close()

        squadre = client.application.config["SQUADRE"]
        form = {"id": pid, "squadra": squadre[0], "costo": "1", "anni_contratto": "1", "opzione": "on"}
        resp = client.post("/assegna_giocatore", data=form, follow_redirects=False)
        assert resp.status_code in (301, 302, 302, 303, 200)

        team_resp = client.get(f"/squadra/{squadre[0]}")
        assert team_resp.status_code == 200
        body = team_resp.data.decode(errors="ignore")
        assert "INT_TEST_PLAYER" in body
