from flask import Blueprint, render_template, current_app
from app.db import get_connection
from app.services.market_service import MarketService

bp = Blueprint("teams", __name__, url_prefix="/teams")


@bp.route("/<team_name>")
def team_page(team_name):
    # decode is handled by Flask; use DB to fetch roster for this team
    DB_PATH = current_app.config.get("DB_PATH")
    ruolo_map = {
        "P": "Portieri",
        "D": "Difensori",
        "C": "Centrocampisti",
        "A": "Attaccanti",
    }
    team_roster = {r: [] for r in current_app.config.get("ROSE_STRUCTURE", {}).keys()}
    # prefer ORM
    try:
        SessionLocal = current_app.extensions.get("db_session_factory")
        if SessionLocal:
            session = SessionLocal()
            try:
                from .models import Team, Player

                team_obj = session.query(Team).filter(Team.name == team_name).first()
                if team_obj:
                    players = team_obj.players
                else:
                    players = (
                        session.query(Player).filter(Player.team_id.isnot(None)).all()
                    )
                    players = [
                        p for p in players if p.team and p.team.name == team_name
                    ]
                for p in players:
                    codice = (p.role or "").strip()
                    key = None
                    if codice:
                        ch = codice[0].upper()
                        # normalize legacy 'G' (goalkeeper) to canonical 'P'
                        if ch == "G":
                            ch = "P"
                        key = ruolo_map.get(ch)
                    if not key:
                        continue
                    team_roster[key].append(
                        {
                            "id": p.id,
                            "nome": p.name,
                            # store canonical single-letter role
                            "ruolo": ch,
                            "squadra_reale": None,
                            "costo": getattr(p, "costo", None),
                            "anni_contratto": getattr(p, "anni_contratto", None),
                            "opzione": getattr(p, "opzione", None),
                        }
                    )
                starting_pot = (
                    float(team_obj.cash)
                    if team_obj and team_obj.cash is not None
                    else 300.0
                )
                total_spent = sum([float(getattr(p, "costo", 0) or 0) for p in players])
                cassa = starting_pot - total_spent
                # If ORM returned no players for this team, but the legacy DB has
                # assignments in the `giocatori` table for this team (FantaSquadra),
                # prefer the sqlite fallback so users see the up-to-date roster.
                try:
                    if not players:
                        conn_check = get_connection(DB_PATH)
                        cur_check = conn_check.cursor()
                        cur_check.execute(
                            'SELECT 1 FROM giocatori WHERE FantaSquadra = ? LIMIT 1',
                            (team_name,),
                        )
                        if cur_check.fetchone():
                            conn_check.close()
                            session.close()
                            # fallthrough to sqlite fallback below
                            raise Exception("use sqlite fallback")
                        conn_check.close()
                except Exception:
                    # close session and let fallback code below handle sqlite
                    try:
                        session.close()
                    except Exception:
                        pass
                    raise

                session.close()
                return render_template(
                    "team.html",
                    tname=team_name,
                    roster=team_roster,
                    rose_structure=current_app.config.get("ROSE_STRUCTURE", {}),
                    starting_pot=starting_pot,
                    total_spent=total_spent,
                    cassa=cassa,
                    squadre=[],
                )
            finally:
                session.close()
    except Exception:
        pass

    # fallback to sqlite
    # fallback to sqlite via MarketService helper
    try:
        conn = get_connection(DB_PATH)
        svc = MarketService()
        team_roster, starting_pot, total_spent, cassa = svc.get_team_roster(
            conn, team_name, current_app.config.get("ROSE_STRUCTURE", {})
        )
        conn.close()
        return render_template(
            "team.html",
            tname=team_name,
            roster=team_roster,
            rose_structure=current_app.config.get("ROSE_STRUCTURE", {}),
            starting_pot=starting_pot,
            total_spent=total_spent,
            cassa=cassa,
            squadre=[],
        )
    except Exception:
        # preserve existing fallback behavior: empty roster and default cash
        return render_template(
            "team.html",
            tname=team_name,
            roster=team_roster,
            rose_structure=current_app.config.get("ROSE_STRUCTURE", {}),
            starting_pot=300.0,
            total_spent=0.0,
            cassa=300.0,
            squadre=[],
        )
