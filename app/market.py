from flask import Blueprint, render_template, current_app, request
from app.db import get_connection
from flask import redirect, jsonify
import urllib.parse
from app.services.market_service import MarketService

bp = Blueprint("market", __name__)


@bp.route("/", methods=["GET"])
def index():
    DB_PATH = current_app.config.get("DB_PATH")
    SQUADRE = current_app.config.get("SQUADRE")
    ROSE_STRUCTURE = current_app.config.get("ROSE_STRUCTURE")

    query = request.args.get("q", "").strip()
    ruolo = request.args.get("ruolo", "").strip()
    squadra = request.args.get("squadra", "").strip()
    roles_selected = request.args.getlist("roles")
    costo_min = request.args.get("costo_min", "").strip()
    costo_max = request.args.get("costo_max", "").strip()
    opzione = request.args.get("opzione", "").strip()
    anni_contratto = request.args.get("anni_contratto", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 50

    conn = get_connection(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(giocatori)")
    columns_info = cur.fetchall()
    columns = [row["name"] for row in columns_info]
    if "#" in columns:
        columns = [c for c in columns if c != "#"]
    for hide_col in ["Fuori lista", "Under", "R.MANTRA", "FVM/1000"]:
        if hide_col in columns:
            columns = [c for c in columns if c != hide_col]
    safe_columns = []
    for col in columns:
        if col.replace("_", "").isalnum():
            safe_columns.append(col)
    if not safe_columns:
        safe_columns = columns

    sql = "SELECT rowid AS id, * FROM giocatori WHERE 1=1"
    params = []
    if query:
        like = f"%{query}%"
        where = " OR ".join([f'"{col}" LIKE ?' for col in safe_columns])
        sql += f" AND ({where})"
        params += [like] * len(safe_columns)
    if ruolo:
        sql += " AND ruolo LIKE ?"
        params.append(f"%{ruolo}%")
    role_map = {
        "Portieri": ["P", "G"],
        "Difensori": ["D"],
        "Centrocampisti": ["C"],
        "Attaccanti": ["A"],
    }
    if not roles_selected:
        roles_selected = list(role_map.keys())
    codes = []
    for rcat in roles_selected:
        codes += role_map.get(rcat, [])
    if codes:
        role_where = " OR ".join(['"R." LIKE ?' for _ in codes])
        sql += f" AND ({role_where})"
        params += [f"{c}%" for c in codes]
    else:
        sql += " AND 0"
    if squadra:
        sql += " AND squadra LIKE ?"
        params.append(f"%{squadra}%")
    if costo_min:
        sql += " AND costo >= ?"
        params.append(costo_min)
    if costo_max:
        sql += " AND costo <= ?"
        params.append(costo_max)
    if opzione:
        sql += " AND opzione LIKE ?"
        params.append(f"%{opzione}%")
    if anni_contratto:
        sql += " AND anni_contratto = ?"
        params.append(anni_contratto)

    count_sql = "SELECT COUNT(*) FROM giocatori WHERE 1=1"
    count_params = []
    if query:
        like = f"%{query}%"
        where = " OR ".join([f'"{col}" LIKE ?' for col in safe_columns])
        count_sql += f" AND ({where})"
        count_params += [like] * len(safe_columns)
    if ruolo:
        count_sql += " AND ruolo LIKE ?"
        count_params.append(f"%{ruolo}%")
    if squadra:
        count_sql += " AND squadra LIKE ?"
        count_params.append(f"%{squadra}%")
    if costo_min:
        count_sql += " AND costo >= ?"
        count_params.append(costo_min)
    if costo_max:
        count_sql += " AND costo <= ?"
        count_params.append(costo_max)
    if opzione:
        count_sql += " AND opzione LIKE ?"
        count_params.append(f"%{opzione}%")
    if anni_contratto:
        count_sql += " AND anni_contratto = ?"
        count_params.append(anni_contratto)
    if not roles_selected:
        roles_selected = list(role_map.keys())
    codes = []
    for rcat in roles_selected:
        codes += role_map.get(rcat, [])
    if codes:
        role_where = " OR ".join(['"R." LIKE ?' for _ in codes])
        count_sql += f" AND ({role_where})"
        count_params += [f"{c}%" for c in codes]
    else:
        count_sql += " AND 0"
    cur.execute(count_sql, count_params)
    total = cur.fetchone()[0]

    # Sorting
    sort_by = request.args.get("sort_by", "").strip()
    sort_dir = request.args.get("sort_dir", "asc").lower()

    def q(colname):
        return f'"{colname}"'

    allowed_sorts = {}
    if "Nome" in columns:
        allowed_sorts["nome"] = q("Nome")
    if "Sq." in columns:
        allowed_sorts["sq"] = q("Sq.")
    if "FantaSquadra" in columns:
        allowed_sorts["fantasquadra"] = q("FantaSquadra")
    if "squadra" in columns:
        allowed_sorts["squadra"] = q("squadra")
    for c in columns:
        cl = c.lower()
        if cl == "pgv":
            allowed_sorts.setdefault("pgv", q(c))
        if "costo" in cl:
            allowed_sorts.setdefault("costo", q(c))
    quot_col = None
    for c in columns:
        cl = c.lower()
        if "mv" in cl and "mv" not in allowed_sorts:
            allowed_sorts["mv"] = q(c)
        if "fm" in cl and "fm" not in allowed_sorts:
            allowed_sorts["fm"] = q(c)
        if "quot" in cl and "quot" not in allowed_sorts:
            allowed_sorts["quot"] = q(c)
            quot_col = c
        if (
            "pg" in cl
            and "pgv" not in allowed_sorts
            and cl.replace(".", "").startswith("pg")
        ):
            allowed_sorts.setdefault("pgv", q(c))

    base_args = request.args.to_dict(flat=False)
    base_args.pop("sort_by", None)
    base_args.pop("sort_dir", None)
    sort_links = {}
    for key in allowed_sorts.keys():
        a = dict(base_args)
        a["sort_by"] = key
        a["sort_dir"] = "asc"
        asc_q = urllib.parse.urlencode(a, doseq=True)
        a["sort_dir"] = "desc"
        desc_q = urllib.parse.urlencode(a, doseq=True)
        sort_links[key] = {"asc": "?" + asc_q, "desc": "?" + desc_q}
    header_toggle_links = {}
    active_sort_key = sort_by
    active_sort_dir = sort_dir
    for k in allowed_sorts.keys():
        if active_sort_key == k and active_sort_dir == "asc":
            header_toggle_links[k] = sort_links[k]["desc"]
        else:
            header_toggle_links[k] = sort_links[k]["asc"]

    display_to_sortkey = {}
    if "Nome" in columns and "nome" in allowed_sorts:
        display_to_sortkey["Nome"] = "nome"
    if "Sq." in columns and "sq" in allowed_sorts:
        display_to_sortkey["Sq."] = "sq"
    if "FantaSquadra" in columns and "fantasquadra" in allowed_sorts:
        display_to_sortkey["FantaSquadra"] = "fantasquadra"
    for k, expr in allowed_sorts.items():
        colname = expr.strip('"')
        display_to_sortkey[colname] = k
    if sort_by in allowed_sorts:
        direction = "ASC" if sort_dir != "desc" else "DESC"
        if sort_by in ("mv", "fm", "quot", "pgv", "costo"):
            clean = f"REPLACE(REPLACE(REPLACE(REPLACE({allowed_sorts[sort_by]}, ',', ''), '%', ''), '€', ''), ' ', '')"
            order_expr = f"CAST({clean} AS REAL) {direction}"
        else:
            order_expr = f"{allowed_sorts[sort_by]} COLLATE NOCASE {direction}"
        if "Nome" in columns:
            order_expr = f"{order_expr}, {q('Nome')} COLLATE NOCASE ASC"
        sql = sql.rstrip()
        sql += f" ORDER BY {order_expr}"

    offset = (page - 1) * per_page
    sql += f" LIMIT {per_page} OFFSET {offset}"
    cur.execute(sql, params)
    results = cur.fetchall()
    conn.close()

    suggestions = []
    if query and len(query) >= 2 and len(results) < 5:
        try:
            conn = get_connection(DB_PATH)
            svc = MarketService()
            suggestion_results = svc.get_name_suggestions(conn, query, limit=8)
            for name in suggestion_results:
                if (
                    not any(
                        r.get("Nome") == name for r in results if "Nome" in r.keys()
                    )
                    and name.lower() != query.lower()
                ):
                    suggestions.append(name)
            conn.close()
        except Exception:
            suggestions = []

    # compute team summaries: prefer ORM if available, otherwise fall back to sqlite3
    team_casse = []
    try:
        SessionLocal = current_app.extensions.get("db_session_factory")
        if SessionLocal:
            session = SessionLocal()
            try:
                from .models import Team, Player

                for s in SQUADRE:
                    team_obj = session.query(Team).filter(Team.name == s).first()
                    starting = (
                        float(team_obj.cash)
                        if team_obj and team_obj.cash is not None
                        else 300.0
                    )
                    # sum costs of players assigned to this team
                    spent = 0.0
                    counts = {}
                    players = []
                    if team_obj:
                        players = team_obj.players
                    else:
                        # no Team row, try to find Player.team by name match
                        players = (
                            session.query(Player)
                            .filter(Player.team_id.isnot(None))
                            .all()
                        )
                        players = [p for p in players if p.team and p.team.name == s]
                    for p in players:
                        # p may not have a numeric cost field in ORM model; ignore cost unless custom attribute exists
                        try:
                            costo_val = float(getattr(p, "costo", 0) or 0)
                        except Exception:
                            costo_val = 0.0
                        spent += costo_val
                        rcode = (p.role or "")[:1].upper() if p.role else ""
                        counts[rcode] = counts.get(rcode, 0) + 1
                    portieri_count = int(counts.get("P", 0)) + int(counts.get("G", 0))
                    dif_count = int(counts.get("D", 0))
                    cen_count = int(counts.get("C", 0))
                    att_count = int(counts.get("A", 0))
                    missing_portieri = max(
                        0, ROSE_STRUCTURE.get("Portieri", 0) - portieri_count
                    )
                    missing_dif = max(0, ROSE_STRUCTURE.get("Difensori", 0) - dif_count)
                    missing_cen = max(
                        0, ROSE_STRUCTURE.get("Centrocampisti", 0) - cen_count
                    )
                    missing_att = max(
                        0, ROSE_STRUCTURE.get("Attaccanti", 0) - att_count
                    )
                    missing_total = (
                        missing_portieri + missing_dif + missing_cen + missing_att
                    )
                    team_casse.append(
                        {
                            "squadra": s,
                            "starting": starting,
                            "spent": spent,
                            "remaining": starting - spent,
                            "missing": missing_total,
                            "missing_portieri": missing_portieri,
                            "missing_dif": missing_dif,
                            "missing_cen": missing_cen,
                            "missing_att": missing_att,
                        }
                    )
            finally:
                session.close()
    except Exception:
        team_casse = []

    if not team_casse:
        try:
            conn = get_connection(DB_PATH)
            svc = MarketService()
            team_casse = svc.get_team_summaries(conn, SQUADRE, ROSE_STRUCTURE)
            conn.close()
        except Exception:
            team_casse = []
    team_casse.sort(key=lambda x: x["remaining"], reverse=True)
    team_casse_missing = sorted(team_casse, key=lambda x: x["missing"])

    # pagination HTML handled in template; provide necessary context
    return render_template(
        "index.html",
        columns=columns,
        results=results,
        suggestions=suggestions,
        query=query,
        ruolo=ruolo,
        squadra=squadra,
        costo_min=costo_min,
        costo_max=costo_max,
        opzione=opzione,
        anni_contratto=anni_contratto,
        page=page,
        per_page=per_page,
        total=total,
        request=request,
        squadre=SQUADRE,
        roles_selected=roles_selected,
        allowed_sorts=allowed_sorts,
        quot_col=quot_col,
        sort_links=sort_links,
        display_to_sortkey=display_to_sortkey,
        header_toggle_links=header_toggle_links,
        team_casse=team_casse,
        team_casse_missing=team_casse_missing,
    )


@bp.route("/assegna_giocatore", methods=["POST"])
def assegna_giocatore():
    DB_PATH = current_app.config.get("DB_PATH")
    id = request.form.get("id")
    squadra = request.form.get("squadra")
    costo = request.form.get("costo")
    anni_contratto = request.form.get("anni_contratto")
    opzione = "SI" if request.form.get("opzione") == "on" else "NO"
    service = MarketService()
    # re-use service validation; keep canonical team check from app config
    error_msg = service.validate_player_assignment(id, squadra, costo, anni_contratto)
    if squadra and squadra not in current_app.config.get("SQUADRE"):
        error_msg = "Squadra selezionata non valida."
    if error_msg:
        return (error_msg, 400)

    conn = get_connection(DB_PATH)
    try:
        res = service.assign_player(conn, id, squadra, costo, anni_contratto, opzione)
        if not res.get("success"):
            avail = res.get("available")
            if avail is None:
                avail = 300.0
            needed = 0.0
            try:
                needed = (
                    float(str(costo).replace(",", "").replace("€", "").strip())
                    if costo not in (None, "")
                    else 0.0
                )
            except Exception:
                needed = 0.0
            return (
                f"Fondi insufficienti per assegnare (costo: {needed} > disponibile: {avail}).",
                400,
            )
    finally:
        conn.close()

    return redirect("/")


@bp.route("/update_player", methods=["POST"])
def update_player():
    DB_PATH = current_app.config.get("DB_PATH")
    data = request.get_json() or {}
    pid = data.get("id")
    squadra = data.get("squadra")
    costo = data.get("costo")
    anni_contratto = data.get("anni_contratto")
    opzione = data.get("opzione")
    error_msg = None
    if not pid or not str(pid).isdigit():
        error_msg = "ID giocatore non valido."
    if squadra and squadra not in current_app.config.get("SQUADRE"):
        error_msg = "Squadra selezionata non valida."
    try:
        costo_val = (
            float(str(costo).replace(",", "").replace("€", "").strip())
            if costo not in (None, "")
            else 0.0
        )
        if costo_val < 0 or costo_val > 1000:
            error_msg = "Il costo deve essere tra 0 e 1000."
    except Exception:
        error_msg = "Costo non valido."
    if anni_contratto and str(anni_contratto) not in ["1", "2", "3"]:
        error_msg = "Anni contratto non valido."
    if error_msg:
        return (
            jsonify(
                {"error": error_msg, "help": "Controlla i dati inseriti e riprova."}
            ),
            400,
        )
    # delegate to MarketService for the heavy lifting
    service = MarketService()
    # normalize empty team -> None behavior inside service
    conn = get_connection(DB_PATH)
    try:
        res = service.update_player(conn, pid, squadra, costo, anni_contratto, opzione)
        # service returns either an updated row dict or an error mapping
        if isinstance(res, dict) and res.get("error"):
            # keep previous JSON error shape
            return (jsonify(res), 400)
        return jsonify(res)
    finally:
        conn.close()


@bp.route("/rose", methods=["GET"])
def rose():
    DB_PATH = current_app.config.get("DB_PATH")
    # Prefer ORM data if present; fall back to legacy sqlite3 queries when needed
    ROSE_STRUCTURE = current_app.config.get("ROSE_STRUCTURE")
    ruolo_map = {
        "P": "Portieri",
        "G": "Portieri",
        "D": "Difensori",
        "C": "Centrocampisti",
        "A": "Attaccanti",
    }

    # attempt ORM query
    orm_rows = []
    try:
        SessionLocal = current_app.extensions.get("db_session_factory")
        if SessionLocal:
            session = SessionLocal()
            try:
                from .models import Player

                # get players assigned to a fantasy team (team_id not null)
                qs = session.query(Player).filter(Player.team_id.isnot(None)).all()
                for p in qs:
                    team = p.team.name if p.team is not None else None
                    orm_rows.append(
                        {
                            "id": p.id,
                            "nome": p.name,
                            "ruolo": p.role,
                            "squadra_reale": None,
                            "costo": None,
                            "anni_contratto": None,
                            "opzione": None,
                            "FantaSquadra": team,
                        }
                    )
            finally:
                session.close()
    except Exception:
        orm_rows = []

    if orm_rows:
        teams_in_rows = {r["FantaSquadra"] for r in orm_rows if r["FantaSquadra"]}
        all_teams = list(
            dict.fromkeys(
                list(current_app.config.get("SQUADRE")) + sorted(teams_in_rows)
            )
        )
        rose_map = {s: {r: [] for r in ROSE_STRUCTURE.keys()} for s in all_teams}
        for row in orm_rows:
            sname = row["FantaSquadra"]
            codice_ruolo = (row.get("ruolo") or "").strip()
            key = None
            if codice_ruolo:
                ch = codice_ruolo[0].upper()
                key = ruolo_map.get(ch)
            if not key:
                continue
            if sname in rose_map:
                rose_map[sname][key].append(
                    {
                        "id": row["id"],
                        "nome": row["nome"],
                        "ruolo": codice_ruolo,
                        "squadra_reale": row.get("squadra_reale"),
                        "costo": row.get("costo"),
                        "anni_contratto": row.get("anni_contratto"),
                        "opzione": row.get("opzione"),
                    }
                )
        return render_template(
            "rose.html", squadre=all_teams, rose_structure=ROSE_STRUCTURE, rose=rose_map
        )

    # fallback: legacy sqlite3 logic
    conn = get_connection(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """SELECT rowid AS id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione, FantaSquadra
        FROM giocatori
        WHERE FantaSquadra IS NOT NULL
        AND NOT (opzione IS NOT NULL AND anni_contratto IS NULL)
    """
    )
    rows = cur.fetchall()
    conn.close()
    teams_in_rows = {row["FantaSquadra"] for row in rows if row["FantaSquadra"]}
    all_teams = list(
        dict.fromkeys(list(current_app.config.get("SQUADRE")) + sorted(teams_in_rows))
    )
    rose_map = {s: {r: [] for r in ROSE_STRUCTURE.keys()} for s in all_teams}
    for row in rows:
        sname = row["FantaSquadra"]
        codice_ruolo = (row["ruolo"] or "").strip()
        key = None
        if codice_ruolo:
            ch = codice_ruolo[0].upper()
            key = ruolo_map.get(ch)
        if not key:
            continue
        if sname in rose_map:
            rose_map[sname][key].append(
                {
                    "id": row["id"],
                    "nome": row["nome"],
                    "ruolo": codice_ruolo,
                    "squadra_reale": row["squadra_reale"],
                    "costo": row["costo"],
                    "anni_contratto": row["anni_contratto"],
                    "opzione": row["opzione"],
                }
            )
    return render_template(
        "rose.html", squadre=all_teams, rose_structure=ROSE_STRUCTURE, rose=rose_map
    )


@bp.route("/squadra/<team_name>", methods=["GET"])
def squadra(team_name):
    from urllib.parse import unquote

    tname = unquote(team_name)
    DB_PATH = current_app.config.get("DB_PATH")
    # prefer ORM if available
    ruolo_map = {
        "P": "Portieri",
        "G": "Portieri",
        "D": "Difensori",
        "C": "Centrocampisti",
        "A": "Attaccanti",
    }
    ROSE_STRUCTURE = current_app.config.get("ROSE_STRUCTURE")
    team_roster = {r: [] for r in ROSE_STRUCTURE.keys()}
    try:
        SessionLocal = current_app.extensions.get("db_session_factory")
        if SessionLocal:
            session = SessionLocal()
            try:
                from .models import Team, Player

                team_obj = session.query(Team).filter(Team.name == tname).first()
                if team_obj:
                    players = team_obj.players
                else:
                    players = (
                        session.query(Player).filter(Player.team_id.isnot(None)).all()
                    )
                    players = [p for p in players if p.team and p.team.name == tname]
                for p in players:
                    codice = (p.role or "").strip()
                    key = None
                    if codice:
                        ch = codice[0].upper()
                        key = ruolo_map.get(ch)
                    if not key:
                        continue
                    team_roster[key].append(
                        {
                            "id": p.id,
                            "nome": p.name,
                            "ruolo": p.role,
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
                return render_template(
                    "team.html",
                    tname=tname,
                    roster=team_roster,
                    rose_structure=ROSE_STRUCTURE,
                    starting_pot=starting_pot,
                    total_spent=total_spent,
                    cassa=cassa,
                    squadre=current_app.config.get("SQUADRE"),
                )
            finally:
                session.close()
    except Exception:
        # fall back to sqlite
        pass

    conn = get_connection(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        'SELECT rowid as id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione FROM giocatori WHERE FantaSquadra = ? AND NOT (opzione IS NOT NULL AND anni_contratto IS NULL)',
        (tname,),
    )
    rows = cur.fetchall()
    conn.close()
    if rows:
        # If we got rows above from sqlite fallback, use the MarketService helper to compute roster and cassa
        try:
            conn = get_connection(DB_PATH)
            svc = MarketService()
            team_roster, starting_pot, total_spent, cassa = svc.get_team_roster(
                conn, tname, ROSE_STRUCTURE
            )
            conn.close()
            return render_template(
                "team.html",
                tname=tname,
                roster=team_roster,
                rose_structure=ROSE_STRUCTURE,
                starting_pot=starting_pot,
                total_spent=total_spent,
                cassa=cassa,
                squadre=current_app.config.get("SQUADRE"),
            )
        except Exception:
            # fallback to current in-place computation if service fails
            pass
    # final fallback: render with computed variables (should rarely reach here)
    return render_template(
        "team.html",
        tname=tname,
        roster=team_roster,
        rose_structure=ROSE_STRUCTURE,
        starting_pot=300.0,
        total_spent=0.0,
        cassa=300.0,
        squadre=current_app.config.get("SQUADRE"),
    )
