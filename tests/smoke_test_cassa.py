import sqlite3
import shutil
import tempfile
import os
import threading
import pytest

# Quick smoke test for fantateam cassa atomic operations
# Usage: run from workspace root: python -m tests.smoke_test_cassa

DB_ORIG = os.path.join(os.path.dirname(__file__), "..", "giocatori.db")


def copy_db():
    td = tempfile.mkdtemp(prefix="ftest_")
    dst = os.path.join(td, "giocatori.db")
    shutil.copyfile(DB_ORIG, dst)
    return dst


@pytest.fixture
def db_path():
    """Provide a temporary copy of the working DB for tests and cleanup afterwards."""
    db = copy_db()
    try:
        yield db
    finally:
        # best-effort cleanup
        try:
            os.remove(db)
        except Exception:
            pass
        try:
            os.rmdir(os.path.dirname(db))
        except Exception:
            pass


def atomic_charge(db_path, team, amount):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "UPDATE fantateam SET cassa_attuale = cassa_attuale - ? WHERE squadra=? AND cassa_attuale >= ?",
        (amount, team, amount),
    )
    ok = cur.rowcount > 0
    conn.commit()
    conn.close()
    return ok


def refund(db_path, team, amount):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT carryover, cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?",
        (team,),
    )
    r = cur.fetchone()
    if r:
        cur_att = r[2]
        if cur_att is not None:
            new = float(cur_att) + amount
            cur.execute(
                "UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (new, team)
            )
        else:
            iniz = float(r[1]) if r[1] is not None else 300.0
            new = iniz + amount
            cur.execute(
                "UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (new, team)
            )
    else:
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            (team, 0, 300.0, 300.0 + amount),
        )
    conn.commit()
    conn.close()


def get_cash(db_path, team):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (team,)
    )
    r = cur.fetchone()
    conn.close()
    if r:
        return float(r[0]) if r[0] is not None else 300.0, (
            float(r[1])
            if r[1] is not None
            else (float(r[0]) if r[0] is not None else 300.0)
        )
    return 300.0, 300.0


def test_simple_sequence(db_path):
    team = "FC Bioparco"
    iniz, att = get_cash(db_path, team)
    print("Initial", team, "start=", iniz, "att=", att)
    ok = atomic_charge(db_path, team, 10)
    assert ok, "Should be able to deduct 10"
    _, att2 = get_cash(db_path, team)
    print("After -10, att=", att2)
    assert abs(att2 - (att - 10)) < 0.001
    refund(db_path, team, 5)
    _, att3 = get_cash(db_path, team)
    print("After refund 5, att=", att3)
    assert abs(att3 - (att2 + 5)) < 0.001


def test_concurrent_attempts(db_path):
    team = "Nova Spes"
    # ensure team has known cash
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (50, team))
    conn.commit()
    conn.close()

    results = []

    def try_buy(amount, idx):
        ok = atomic_charge(db_path, team, amount)
        results.append((idx, amount, ok))

    threads = []
    # start several concurrent threads attempting to buy 30 each (only one or maybe one should succeed)
    for i in range(3):
        t = threading.Thread(target=try_buy, args=(30, i))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    print("Concurrent results:", results)
    # Count how many succeeded
    succ = sum(1 for r in results if r[2])
    assert succ <= 1, "At most one purchase of 30 should succeed when cash=50"


if __name__ == "__main__":
    db = copy_db()
    print("Using temp DB:", db)
    test_simple_sequence(db)
    test_concurrent_attempts(db)
    print("Smoke tests passed")
