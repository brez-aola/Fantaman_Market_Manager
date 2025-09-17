import sqlite3
from typing import Optional, Dict, Any


class InsufficientFunds(Exception):
    def __init__(self, needed: float, available: float):
        self.needed = needed
        self.available = available
        super().__init__(f"Insufficient funds: needed={needed} available={available}")


class MarketService:
    """Service encapsulating market/business rules operating over a sqlite3 connection.

    Methods are written to receive an active `sqlite3.Connection` so tests can inject
    an in-memory DB session.
    """

    def validate_player_assignment(
        self, id: str, squadra: Optional[str], costo: Optional[str], anni_contratto: Optional[str]
    ) -> Optional[str]:
        if not id or not str(id).isdigit():
            return "ID giocatore non valido."
        if squadra and squadra not in []:  # team set validation should be done by caller if needed
            # keep lightweight here; the web-layer will check canonical teams
            pass
        try:
            costo_val = (
                float(str(costo).replace(",", "").replace("€", "").strip())
                if costo not in (None, "")
                else 0.0
            )
            if costo_val < 0 or costo_val > 1000:
                return "Il costo deve essere tra 0 e 1000."
        except Exception:
            return "Costo non valido."
        if anni_contratto and str(anni_contratto) not in ["1", "2", "3"]:
            return "Anni contratto non valido."
        return None

    def normalize_assignment_values(self, squadra, costo, anni_contratto, opzione):
        if costo in (None, ""):
            costo_val = 0.0
        else:
            try:
                costo_val = float(str(costo).replace(",", "").replace("€", "").strip())
            except Exception:
                costo_val = 0.0
        if not squadra:
            squadra_val = None
            anni_contratto = None
            opzione = None
        else:
            squadra_val = squadra
        return squadra_val, costo_val, anni_contratto, opzione

    # Team cash helpers (migrated from app.py) -------------------------------------------------
    def get_team_cash(self, conn: sqlite3.Connection, team: str):
        cur = conn.cursor()
        cur.execute("SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (team,))
        r = cur.fetchone()
        if r:
            iniziale = float(r[0]) if r[0] is not None else 300.0
            attuale = float(r[1]) if r[1] is not None else iniziale
        else:
            iniziale = 300.0
            attuale = 300.0
        return iniziale, attuale

    def update_team_cash(self, conn: sqlite3.Connection, team: str, new_attuale: float):
        cur = conn.cursor()
        cur.execute("SELECT carryover, cassa_iniziale FROM fantateam WHERE squadra=?", (team,))
        r = cur.fetchone()
        if r and r[0] is not None:
            carryover = float(r[0]) if r[0] is not None else 0.0
            cassa_iniziale = float(r[1]) if r[1] is not None else new_attuale
        else:
            carryover = 0.0
            cassa_iniziale = new_attuale
        cur.execute(
            "INSERT OR REPLACE INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            (team, carryover, cassa_iniziale, new_attuale),
        )

    def atomic_charge_team(self, conn: sqlite3.Connection, team: str, amount: float) -> bool:
        cur = conn.cursor()
        cur.execute("SELECT carryover, cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (team,))
        r = cur.fetchone()
        if not r:
            cur.execute(
                "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
                (team, 0, 300.0, 300.0),
            )
        else:
            if r[2] is None:
                iniz = float(r[1]) if r[1] is not None else 300.0
                cur.execute("UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (iniz, team))
        cur.execute(
            "UPDATE fantateam SET cassa_attuale = cassa_attuale - ? WHERE squadra=? AND cassa_attuale >= ?",
            (amount, team, amount),
        )
        return cur.rowcount > 0

    def refund_team(self, conn: sqlite3.Connection, team: str, amount: float):
        cur = conn.cursor()
        cur.execute("SELECT carryover, cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (team,))
        r = cur.fetchone()
        if r:
            try:
                cur_att = r[2]
            except Exception:
                cur_att = r[2]
            if cur_att is not None:
                new = float(cur_att) + amount
                cur.execute("UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (new, team))
            else:
                try:
                    iniz = float(r[1]) if r[1] is not None else 300.0
                except Exception:
                    iniz = 300.0
                new = iniz + amount
                cur.execute("UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (new, team))
        else:
            cur.execute(
                "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
                (team, 0, 300.0, 300.0 + amount),
            )

    # High-level operations -------------------------------------------------------------------
    def assign_player(
        self, conn: sqlite3.Connection, id: str, squadra: Optional[str], costo: Optional[str], anni_contratto: Optional[str], opzione: Optional[str]
    ) -> Dict[str, Any]:
        """Perform assign/move/unassign logic. Returns dict with keys: success(bool), error(optional), available(optional)."""
        cur = conn.cursor()
        squadra_val, costo_val, anni_contratto, opzione = self.normalize_assignment_values(
            squadra, costo, anni_contratto, opzione
        )

        # Find current assignment
        cur.execute("SELECT squadra, Costo FROM giocatori WHERE rowid=?", (id,))
        prev = cur.fetchone()
        prev_team = None
        prev_cost = 0.0
        if prev:
            prev_team = prev[0]
            try:
                prev_cost = float(prev[1]) if prev[1] not in (None, "") else 0.0
            except Exception:
                prev_cost = 0.0

        # Unassign
        if squadra_val is None:
            if prev_team and prev_cost > 0:
                self.refund_team(conn, prev_team, prev_cost)
            cur.execute('UPDATE giocatori SET "squadra"=?, "Costo"=?, "anni_contratto"=?, "opzione"=? WHERE rowid=?', (None, None, None, None, id))
            conn.commit()
            return {"success": True}

        # moving: refund prev first
        if prev_team and prev_team != squadra_val and prev_cost > 0:
            self.refund_team(conn, prev_team, prev_cost)

        # attempt atomic charge
        if costo_val > 0:
            ok = self.atomic_charge_team(conn, squadra_val, costo_val)
            if not ok:
                conn.rollback()
                cur.execute("SELECT cassa_attuale FROM fantateam WHERE squadra=?", (squadra_val,))
                rr = cur.fetchone()
                avail = float(rr[0]) if rr and rr[0] is not None else 300.0
                return {"success": False, "error": "Fondi insufficienti", "available": avail}

        cur.execute('UPDATE giocatori SET "squadra"=?, "Costo"=?, "anni_contratto"=?, "opzione"=? WHERE rowid=?', (squadra_val, costo_val, anni_contratto, opzione, id))
        conn.commit()
        return {"success": True}

    def update_player(self, conn: sqlite3.Connection, pid: str, squadra: Optional[str], costo: Optional[str], anni_contratto: Optional[str], opzione: Optional[str]) -> Dict[str, Any]:
        # Similar to assign_player but returns the updated row as dict
        cur = conn.cursor()
        if squadra == "" or squadra is None:
            squadra_val = None
            anni_contratto = None
            opzione = None
        else:
            squadra_val = squadra

        try:
            costo_val = (
                float(str(costo).replace(",", "").replace("€", "").strip())
                if costo not in (None, "")
                else 0.0
            )
        except Exception:
            costo_val = 0.0

        cur.execute("SELECT squadra, Costo FROM giocatori WHERE rowid=?", (pid,))
        prev = cur.fetchone()
        prev_team = None
        prev_cost = 0.0
        if prev:
            prev_team = prev[0]
            try:
                prev_cost = float(prev[1]) if prev[1] not in (None, "") else 0.0
            except Exception:
                prev_cost = 0.0

        if squadra_val is None and prev_team:
            if prev_cost > 0:
                self.refund_team(conn, prev_team, prev_cost)
            cur.execute('UPDATE giocatori SET "squadra"=?, "Costo"=?, "anni_contratto"=?, "opzione"=? WHERE rowid=?', (None, None, None, None, pid))
            conn.commit()
            cur.execute('SELECT rowid as id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione, squadra FROM giocatori WHERE rowid=?', (pid,))
            row = cur.fetchone()
            return dict(row) if row else {}

        if prev_team and prev_team != squadra_val and prev_cost > 0:
            self.refund_team(conn, prev_team, prev_cost)

        if squadra_val and costo_val > 0:
            ok = self.atomic_charge_team(conn, squadra_val, costo_val)
            if not ok:
                conn.rollback()
                cur.execute("SELECT cassa_attuale FROM fantateam WHERE squadra=?", (squadra_val,))
                r = cur.fetchone()
                avail = float(r[0]) if r and r[0] is not None else 300.0
                return {"error": "Fondi insufficienti", "needed": costo_val, "available": avail}

        cur.execute('UPDATE giocatori SET "squadra"=?, "Costo"=?, "anni_contratto"=?, "opzione"=? WHERE rowid=?', (squadra_val, costo_val, anni_contratto, opzione, pid))
        conn.commit()
        cur.execute('SELECT rowid as id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione, squadra FROM giocatori WHERE rowid=?', (pid,))
        row = cur.fetchone()
        return dict(row) if row else {}

    # Utility/read helpers -----------------------------------------------------
    def get_name_suggestions(self, conn: sqlite3.Connection, query: str, limit: int = 8):
        """Return a list of distinct player name suggestions for a short query.

        This mirrors the lightweight suggestion SQL used in the legacy code.
        """
        suggestions = []
        if not query or len(query) < 2:
            return suggestions
        cur = conn.cursor()
        try:
            suggestion_sql = (
                "SELECT DISTINCT Nome FROM giocatori "
                "WHERE Nome LIKE ? OR Nome LIKE ? OR Nome LIKE ? "
                "ORDER BY LENGTH(Nome) ASC LIMIT ?"
            )
            query_variants = [
                f"%{query[:min(4, len(query))]}%",
                f"%{query[:min(3, len(query))]}%",
                f"%{query}%",
            ]
            params = query_variants + [limit]
            cur.execute(suggestion_sql, params)
            rows = cur.fetchall()
            for r in rows:
                suggestions.append(r[0])
        except Exception:
            return []
        return suggestions

    def get_team_summaries(self, conn: sqlite3.Connection, squadre, rose_structure):
        """Compute team summaries (starting, spent, remaining, missing counts) using sqlite fallback.

        Returns list of dicts matching the shape expected by the templates.
        """
        cur = conn.cursor()
        team_casse = []
        for s in squadre:
            cur.execute("SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (s,))
            tr = cur.fetchone()
            if tr and tr[0] is not None:
                starting = float(tr[0])
            else:
                starting = 300.0
            cur.execute(
                """
                SELECT COALESCE(SUM(CAST(
                    REPLACE(REPLACE(REPLACE(REPLACE(COALESCE("Costo", '0'), ',', ''), '%', ''), '€', ''), ' ', '')
                AS REAL)), 0)
                FROM giocatori
                WHERE FantaSquadra = ?
                  AND NOT (opzione IS NOT NULL AND anni_contratto IS NULL)
            """,
                (s,),
            )
            spent_row = cur.fetchone()
            spent = float(spent_row[0]) if spent_row and spent_row[0] is not None else 0.0
            remaining = starting - spent
            cur.execute(
                """
                SELECT SUBSTR("R.",1,1) as code, COUNT(*) as cnt
                FROM giocatori
                WHERE FantaSquadra = ?
                  AND NOT (opzione IS NOT NULL AND anni_contratto IS NULL)
                GROUP BY SUBSTR("R.",1,1)
            """,
                (s,),
            )
            counts = {row[0]: row[1] for row in cur.fetchall()}
            portieri_count = int(counts.get("P", 0)) + int(counts.get("G", 0))
            dif_count = int(counts.get("D", 0))
            cen_count = int(counts.get("C", 0))
            att_count = int(counts.get("A", 0))
            missing_portieri = max(0, rose_structure.get("Portieri", 0) - portieri_count)
            missing_dif = max(0, rose_structure.get("Difensori", 0) - dif_count)
            missing_cen = max(0, rose_structure.get("Centrocampisti", 0) - cen_count)
            missing_att = max(0, rose_structure.get("Attaccanti", 0) - att_count)
            missing_total = missing_portieri + missing_dif + missing_cen + missing_att
            team_casse.append(
                {
                    "squadra": s,
                    "starting": starting,
                    "spent": spent,
                    "remaining": remaining,
                    "missing": missing_total,
                    "missing_portieri": missing_portieri,
                    "missing_dif": missing_dif,
                    "missing_cen": missing_cen,
                    "missing_att": missing_att,
                }
            )
        return team_casse

    def get_team_roster(self, conn: sqlite3.Connection, tname: str, rose_structure):
        """Return roster mapping and basic cassa computation for a team using sqlite fallback.

        Returns (team_roster, starting_pot, total_spent, cassa)
        """
        ruolo_map = {"P": "Portieri", "G": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"}
        team_roster = {r: [] for r in rose_structure.keys()}
        cur = conn.cursor()
        cur.execute(
            'SELECT rowid as id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione FROM giocatori WHERE FantaSquadra = ? AND NOT (opzione IS NOT NULL AND anni_contratto IS NULL)',
            (tname,),
        )
        rows = cur.fetchall()
        for row in rows:
            codice = (row["ruolo"] or "").strip()
            key = None
            if codice:
                ch = codice[0].upper()
                key = ruolo_map.get(ch)
            if not key:
                continue
            team_roster[key].append(
                {
                    "id": row["id"],
                    "nome": row["nome"],
                    "ruolo": codice,
                    "squadra_reale": row["squadra_reale"],
                    "costo": row["costo"],
                    "anni_contratto": row["anni_contratto"],
                    "opzione": row["opzione"],
                }
            )

        cur.execute('SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?', (tname,))
        team_row = cur.fetchone()
        if team_row:
            starting_pot = float(team_row[0])
        else:
            starting_pot = 300.0
        total_spent = sum([float(r["costo"]) for r in rows if r["costo"] not in (None, "")])
        cassa = starting_pot - total_spent
        return team_roster, starting_pot, total_spent, cassa

