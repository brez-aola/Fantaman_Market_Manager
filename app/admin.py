import os

import sqlalchemy as sa
from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from .utils.roster_import import apply_roster, parse_roster
from .utils.team_utils import populate_team_aliases

bp = Blueprint("admin", __name__, url_prefix="/admin")


def check_auth(username, password):
    cfg_user = current_app.config.get("ADMIN_USER", "admin")
    cfg_pass = current_app.config.get("ADMIN_PASS", "admin")
    return username == cfg_user and password == cfg_pass


def authenticate():
    return Response(
        "Authentication required", 401, {"WWW-Authenticate": 'Basic realm="Admin"'}
    )


def requires_auth(f):
    from functools import wraps

    @wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return wrapped


@bp.route("/")
@requires_auth
def index():
    engine = current_app.extensions["db_engine"]
    Session = current_app.extensions["db_session_factory"]
    # simple stats
    with engine.connect() as conn:
        teams_exists = conn.execute(
            sa.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='teams'\n"
            )
        ).fetchone()
        teams = (
            conn.execute(sa.text("SELECT COUNT(*) FROM teams")).scalar()
            if teams_exists
            else None
        )
        aliases_exists = conn.execute(
            sa.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='team_aliases'\n"
            )
        ).fetchone()
        aliases = (
            conn.execute(sa.text("SELECT COUNT(*) FROM team_aliases")).scalar()
            if aliases_exists
            else None
        )
    return render_template("admin/index.html", teams=teams, aliases=aliases)


@bp.route("/upload", methods=["GET", "POST"])
@requires_auth
def upload():
    if request.method == "POST":
        # support file upload or use pasted file via base64 (keep simple: file upload)
        f = request.files.get("xlsx_file")
        if not f:
            flash("No file provided", "danger")
            return redirect(url_for("admin.upload"))
        filename = secure_filename(f.filename or "upload.xlsx")
        upload_dir = os.path.join(
            os.path.dirname(current_app.config.get("DB_PATH")), "uploads"
        )
        os.makedirs(upload_dir, exist_ok=True)
        path = os.path.join(upload_dir, filename)
        f.save(path)

        # parse roster and show preview; apply immediately if requested
        parsed = None
        try:
            parsed = parse_roster(path)
            team_players = parsed["teams"]
            issues = parsed.get("issues", [])
        except Exception as e:
            flash(f"Failed to parse file: {e}", "danger")
            return redirect(url_for("admin.upload"))

        # if user asked for apply, run the DB updates
        if request.form.get("apply"):
            db_path = current_app.config.get("DB_PATH")
            # apply and audit
            summary = apply_roster(db_path, team_players)
            # run alias population
            engine = current_app.extensions["db_engine"]
            Session = current_app.extensions["db_session_factory"]
            s = Session()
            try:
                created = populate_team_aliases(s, source="fantateam")
            finally:
                s.close()
            # record audit via SQLAlchemy ImportAudit model
            try:
                from app.models import ImportAudit

                s2 = Session()
                ia = ImportAudit(
                    filename=filename,
                    user=(
                        request.authorization.username
                        if request.authorization
                        else None
                    ),
                    inserted=summary.get("inserted", 0),
                    updated=summary.get("updated", 0),
                    aliases_created=len(created),
                    success=True,
                    message=None,
                )
                s2.add(ia)
                s2.commit()
                s2.close()
            except Exception:
                # audit best-effort only
                pass
            flash(
                f"Applied roster: inserted={summary['inserted']} updated={summary['updated']} aliases_created={len(created)}",
                "success",
            )
            return redirect(url_for("admin.index"))

        # otherwise render preview
        return render_template("admin/upload.html", teams=team_players)

    return render_template("admin/upload.html", teams=None)


@bp.route("/aliases", methods=["GET", "POST"])
@requires_auth
def aliases():
    engine = current_app.extensions["db_engine"]
    Session = current_app.extensions["db_session_factory"]
    if request.method == "POST":
        # handle edits: alias_id, alias_text, action=update/delete
        alias_id = request.form.get("alias_id")
        action = request.form.get("action")
        if alias_id and action:
            with engine.begin() as conn:
                if action == "delete":
                    conn.execute(
                        sa.text("DELETE FROM team_aliases WHERE id=:id"),
                        {"id": alias_id},
                    )
                elif action == "update":
                    new_text = request.form.get("alias_text", "").strip()
                    conn.execute(
                        sa.text("UPDATE team_aliases SET alias=:alias WHERE id=:id"),
                        {"alias": new_text, "id": alias_id},
                    )
        return redirect(url_for("admin.aliases"))

    # GET: list aliases with simple search and pagination
    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page
    rows = []
    with engine.connect() as conn:
        exists = conn.execute(
            sa.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='team_aliases'\n"
            )
        ).fetchone()
        if exists:
            if q:
                rows = conn.execute(
                    sa.text(
                        "SELECT id, team_id, alias FROM team_aliases WHERE alias LIKE :q ORDER BY team_id LIMIT :limit OFFSET :offset"
                    ),
                    {"q": f"%{q}%", "limit": per_page, "offset": offset},
                ).fetchall()
                total = conn.execute(
                    sa.text("SELECT COUNT(*) FROM team_aliases WHERE alias LIKE :q"),
                    {"q": f"%{q}%"},
                ).scalar()
            else:
                rows = conn.execute(
                    sa.text(
                        "SELECT id, team_id, alias FROM team_aliases ORDER BY team_id LIMIT :limit OFFSET :offset"
                    ),
                    {"limit": per_page, "offset": offset},
                ).fetchall()
                total = conn.execute(
                    sa.text("SELECT COUNT(*) FROM team_aliases")
                ).scalar()
        else:
            total = 0
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "admin/aliases.html", aliases=rows, page=page, pages=pages, q=q
    )


@bp.route("/canonical", methods=["GET", "POST"])
@requires_auth
def canonical():
    engine = current_app.extensions["db_engine"]
    Session = current_app.extensions["db_session_factory"]
    if request.method == "POST":
        if request.form.get("action") == "delete":
            vid = request.form.get("id")
            if vid:
                with engine.begin() as conn:
                    conn.execute(
                        sa.text("DELETE FROM canonical_mappings WHERE id=:id"),
                        {"id": vid},
                    )
            return redirect(url_for("admin.canonical"))
        # export
        if request.form.get("action") == "export":
            # stream CSV
            with engine.connect() as conn:
                rows = conn.execute(
                    sa.text(
                        "SELECT variant, canonical FROM canonical_mappings ORDER BY variant"
                    )
                ).fetchall()
                csv_lines = ["variant,canonical"]
                for r in rows:
                    csv_lines.append(f'"{r[0]}","{r[1]}"')
            return ("\n".join(csv_lines), 200, {"Content-Type": "text/csv"})
        variant = request.form.get("variant", "").strip()
        canonical = request.form.get("canonical", "").strip()
        if variant and canonical:
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT OR REPLACE INTO canonical_mappings(variant, canonical) VALUES (:v,:c)"
                    ),
                    {"v": variant, "c": canonical},
                )
        return redirect(url_for("admin.canonical"))

    # list mappings
    with engine.connect() as conn:
        exists = conn.execute(
            sa.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='canonical_mappings'\n"
            )
        ).fetchone()
        rows = []
        if exists:
            rows = conn.execute(
                sa.text(
                    "SELECT id, variant, canonical FROM canonical_mappings ORDER BY variant"
                )
            ).fetchall()
    return render_template("admin/canonical.html", mappings=rows)


@bp.route("/suggestions", methods=["GET", "POST"])
@requires_auth
def suggestions():
    """Show suggested canonical mappings (from CSV) and allow approving them into DB."""
    engine = current_app.extensions["db_engine"]
    Session = current_app.extensions["db_session_factory"]
    csv_path = os.path.join(
        os.path.dirname(current_app.config.get("DB_PATH")),
        "..",
        "suggested_canonical_mappings_highconf.csv",
    )
    # normalize path: allow file in repo root
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(current_app.config.get("DB_PATH")), "..")
    )
    csv_path = os.path.join(repo_root, "suggested_canonical_mappings_highconf.csv")

    if request.method == "POST":
        # actions: approve (single or bulk), refresh
        action = request.form.get("action")
        selected = request.form.getlist("selected")
        if action == "approve" and selected:
            # load CSV into map
            csv_map = {}
            try:
                import csv as _csv

                with open(csv_path, newline="", encoding="utf-8") as fh:
                    reader = _csv.DictReader(fh)
                    for r in reader:
                        csv_map[r.get("source_alias", "").strip()] = r
            except Exception:
                csv_map = {}

            # insert into canonical_mappings avoiding duplicates
            with engine.begin() as conn:
                for s in selected:
                    entry = csv_map.get(s)
                    if not entry:
                        continue
                    variant = entry.get("source_alias", "").strip()
                    canonical = entry.get("best_match", "").strip()
                    # check exists
                    exists = conn.execute(
                        sa.text("SELECT id FROM canonical_mappings WHERE variant=:v"),
                        {"v": variant},
                    ).fetchone()
                    if exists:
                        continue
                    conn.execute(
                        sa.text(
                            "INSERT INTO canonical_mappings(variant, canonical) VALUES (:v,:c)"
                        ),
                        {"v": variant, "c": canonical},
                    )
            return redirect(url_for("admin.suggestions"))
        # single approve
        if action == "approve_one":
            one = request.form.get("one")
            if one:
                try:
                    import csv as _csv

                    with open(csv_path, newline="", encoding="utf-8") as fh:
                        reader = _csv.DictReader(fh)
                        for r in reader:
                            if r.get("source_alias", "").strip() == one:
                                variant = r.get("source_alias", "").strip()
                                canonical = r.get("best_match", "").strip()
                                with engine.begin() as conn:
                                    exists = conn.execute(
                                        sa.text(
                                            "SELECT id FROM canonical_mappings WHERE variant=:v"
                                        ),
                                        {"v": variant},
                                    ).fetchone()
                                    if not exists:
                                        conn.execute(
                                            sa.text(
                                                "INSERT INTO canonical_mappings(variant, canonical) VALUES (:v,:c)"
                                            ),
                                            {"v": variant, "c": canonical},
                                        )
                                break
                except Exception:
                    pass
            return redirect(url_for("admin.suggestions"))

    suggestions = []
    # load CSV
    try:
        import csv

        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for r in reader:
                suggestions.append(r)
    except Exception:
        suggestions = []

    return render_template("admin/suggestions.html", suggestions=suggestions)


@bp.route("/audit", methods=["GET"])
@requires_auth
def audit():
    engine = current_app.extensions["db_engine"]
    page = int(request.args.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page
    with engine.connect() as conn:
        exists = conn.execute(
            sa.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='import_audit'\n"
            )
        ).fetchone()
        rows = []
        total = 0
        if exists:
            rows = conn.execute(
                sa.text(
                    "SELECT id, filename, user, inserted, updated, aliases_created, success, message FROM import_audit ORDER BY id DESC LIMIT :l OFFSET :o"
                ),
                {"l": per_page, "o": offset},
            ).fetchall()
            total = conn.execute(sa.text("SELECT COUNT(*) FROM import_audit")).scalar()
    pages = max(1, (total + per_page - 1) // per_page)
    return render_template("admin/audit.html", audits=rows, page=page, pages=pages)
