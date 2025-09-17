from flask import Blueprint, render_template, current_app
import sqlite3

bp = Blueprint("teams", __name__, url_prefix="/teams")


@bp.route("/<team_name>")
def team_page(team_name):
    # decode is handled by Flask; use DB to fetch roster for this team
    DB_PATH = current_app.config.get("DB_PATH")
    ruolo_map = {"P": "Portieri", "G": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"}
    team_roster = {r: [] for r in current_app.config.get("ROSE_STRUCTURE", {}).keys()}
    # prefer ORM
    try:
        SessionLocal = current_app.extensions.get('db_session_factory')
        if SessionLocal:
            session = SessionLocal()
            try:
                from .models import Team, Player

                team_obj = session.query(Team).filter(Team.name == team_name).first()
                if team_obj:
                    players = team_obj.players
                else:
                    players = session.query(Player).filter(Player.team_id.isnot(None)).all()
                    players = [p for p in players if p.team and p.team.name == team_name]
                for p in players:
                    codice = (p.role or '').strip()
                    key = None
                    if codice:
                        ch = codice[0].upper()
                        key = ruolo_map.get(ch)
                    if not key:
                        continue
                    team_roster[key].append({
                        'id': p.id,
                        'nome': p.name,
                        'ruolo': p.role,
                        'squadra_reale': None,
                        'costo': getattr(p, 'costo', None),
                        'anni_contratto': getattr(p, 'anni_contratto', None),
                        'opzione': getattr(p, 'opzione', None),
                    })
                starting_pot = float(team_obj.cash) if team_obj and team_obj.cash is not None else 300.0
                total_spent = sum([float(getattr(p, 'costo', 0) or 0) for p in players])
                cassa = starting_pot - total_spent
                session.close()
                return render_template('team.html', tname=team_name, roster=team_roster, rose_structure=current_app.config.get('ROSE_STRUCTURE', {}), starting_pot=starting_pot, total_spent=total_spent, cassa=cassa, squadre=[])
            finally:
                session.close()
    except Exception:
        pass

    # fallback to sqlite
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        'SELECT rowid as id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione FROM giocatori WHERE FantaSquadra = ? AND NOT (opzione IS NOT NULL AND anni_contratto IS NULL)',
        (team_name,),
    )
    rows = cur.fetchall()
    conn.close()
    for row in rows:
        codice = (row['ruolo'] or '').strip()
        key = None
        if codice:
            ch = codice[0].upper()
            key = ruolo_map.get(ch)
        if not key:
            continue
        team_roster[key].append({
            'id': row['id'],
            'nome': row['nome'],
            'ruolo': codice,
            'squadra_reale': row['squadra_reale'],
            'costo': row['costo'],
            'anni_contratto': row['anni_contratto'],
            'opzione': row['opzione'],
        })
    # compute basic cassa
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT cassa_iniziale FROM fantateam WHERE squadra=?', (team_name,))
    tr = cur.fetchone()
    starting_pot = float(tr[0]) if tr and tr[0] is not None else 300.0
    total_spent = sum([float(r['costo']) for r in rows if r['costo'] not in (None, '')])
    cassa = starting_pot - total_spent
    conn.close()
    return render_template('team.html', tname=team_name, roster=team_roster, rose_structure=current_app.config.get('ROSE_STRUCTURE', {}), starting_pot=starting_pot, total_spent=total_spent, cassa=cassa, squadre=[])
