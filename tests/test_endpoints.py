import sqlite3

import pytest

from app import create_app


@pytest.fixture
def client(tmp_path):
    # create a temp DB path
    temp_db = tmp_path / "test_giocatori.db"
    # create a fresh empty DB for hermetic tests (do not copy repo DB which may contain
    # real/fuzzy state like low cassa values that break assertions)
    # the tests will create any needed tables/rows explicitly
    conn = sqlite3.connect(str(temp_db))
    conn.close()
    # create test app with overridden DB_PATH
    app = create_app({"DB_PATH": str(temp_db), "TESTING": True})
    # ensure templates/static resolution if needed
    with app.test_client() as client:
        yield client


def test_update_player_json_and_assign_form(client):
    # POST JSON to update_player with invalid id -> 400
    r = client.post("/update_player", json={"id": "not-a-number"})
    assert r.status_code == 400

    # Create a new player row and then update it using the configured DB path from app
    db_path = client.application.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        'CREATE TABLE IF NOT EXISTS giocatori ("Nome" TEXT, squadra TEXT, "Costo" REAL, anni_contratto INTEGER, opzione TEXT)'
    )
    cur.execute('INSERT INTO giocatori("Nome") VALUES (?)', ("Test Player",))
    rowid = cur.lastrowid
    conn.commit()

    # Update via JSON assign to a valid team
    squadre = client.application.config["SQUADRE"]
    payload = {
        "id": rowid,
        "squadra": squadre[0],
        "costo": "10",
        "anni_contratto": "1",
        "opzione": "SI",
    }
    r = client.post("/update_player", json=payload)
    assert r.status_code in (200, 201)
    data = r.get_json()
    assert data.get("id") == rowid

    # Now test form POST to /assegna_giocatore (form-encoded)
    form = {
        "id": rowid,
        "squadra": squadre[0],
        "costo": "5",
        "anni_contratto": "1",
        "opzione": "on",
    }
    r = client.post("/assegna_giocatore", data=form)
    # success should redirect to '/', so expect 302 or 200 depending on test client behavior
    if r.status_code not in (200, 302):
        # debug output for CI/test failure investigation
        print("DEBUG: assegna_giocatore returned", r.status_code)
        try:
            print("DEBUG BODY:", r.data.decode(errors="ignore")[:2000])
        except UnicodeDecodeError as e:
            print("DEBUG: failed to decode response body:", e)
        except Exception as e:
            print("DEBUG: unexpected error while printing body:", e)
    assert r.status_code in (200, 302)

    conn.close()
