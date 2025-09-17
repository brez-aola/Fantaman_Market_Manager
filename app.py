from flask import Flask, render_template_string, request, jsonify
import urllib.parse
import sqlite3
import os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "giocatori.db")


def ensure_db_columns():
    """Assicura che le colonne usate dall'app esistano nella tabella giocatori."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA table_info(giocatori)")
        existing = [row[1] for row in cur.fetchall()]
    except Exception:
        existing = []
    needed = {
        "squadra": "TEXT",
        "costo": "REAL",
        "opzione": "TEXT",
        "anni_contratto": "INTEGER",
    }
    for col, coltype in needed.items():
        if col not in existing:
            try:
                cur.execute(
                    f"ALTER TABLE giocatori ADD COLUMN {col} {coltype} DEFAULT NULL"
                )
            except Exception:
                # If table doesn't exist or other error, ignore here
                pass
    conn.commit()
    conn.close()


def ensure_teams_table():
    """Create a small table to store per-team carryovers and initial cash, and populate defaults."""
    carryovers = {
        "FC Bioparco": 74,
        "Nova Spes": 20,
        "Good Old Boys": 55,
        "Atletico Milo": 12,
        "FC Dude": 19,
        "FC Pachuca": 13,
        "AS Quiriti": 3,
        "AS Plusvalenza": 25,
    }
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
      CREATE TABLE IF NOT EXISTS fantateam (
          squadra TEXT PRIMARY KEY,
          carryover REAL DEFAULT 0,
          cassa_iniziale REAL DEFAULT 0,
          cassa_attuale REAL
      )
    """
    )
    # Insert or update defaults for canonical teams
    for s in SQUADRE:
        co = carryovers.get(s, 0)
        iniziale = 300 + float(co)
        # Upsert: if row exists keep cassa_attuale as-is, otherwise set cassa_attuale = iniziale
        cur.execute("SELECT cassa_attuale FROM fantateam WHERE squadra=?", (s,))
        r = cur.fetchone()
        if r and r[0] is not None:
            # keep existing cassa_attuale, but ensure carryover and iniziale are stored
            cur.execute(
                "UPDATE fantateam SET carryover=?, cassa_iniziale=? WHERE squadra=?",
                (co, iniziale, s),
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
                (s, co, iniziale, iniziale),
            )
    conn.commit()
    conn.close()


def get_team_cash(conn, team):
    """Return a tuple (starting, current) for the given team. Uses fantateam, falls back to 300."""
    cur = conn.cursor()
    cur.execute(
        "SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (team,)
    )
    r = cur.fetchone()
    if r:
        iniziale = float(r[0]) if r[0] is not None else 300.0
        attuale = float(r[1]) if r[1] is not None else iniziale
    else:
        iniziale = 300.0
        attuale = 300.0
    return iniziale, attuale


def update_team_cash(conn, team, new_attuale):
    cur = conn.cursor()
    # Preserve existing carryover and cassa_iniziale if the row exists, otherwise create sensible defaults
    cur.execute(
        "SELECT carryover, cassa_iniziale FROM fantateam WHERE squadra=?", (team,)
    )
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
    # Note: caller should commit


def atomic_charge_team(conn, team, amount):
    """Attempt to atomically deduct `amount` from team's cassa_attuale.
    Returns True if deduction succeeded, False if insufficient funds.
    Ensures a fantateam row exists (with default 300) before attempting the atomic update.
    """
    cur = conn.cursor()
    # Ensure team row exists while preserving carryover/cassa_iniziale semantics
    cur.execute(
        "SELECT carryover, cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?",
        (team,),
    )
    r = cur.fetchone()
    if not r:
        # create default row with sensible defaults
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            (team, 0, 300.0, 300.0),
        )
    else:
        # if cassa_attuale is NULL, initialize it from cassa_iniziale or 300
        if r[2] is None:
            iniz = float(r[1]) if r[1] is not None else 300.0
            cur.execute(
                "UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (iniz, team)
            )
    # atomic update: only subtract if enough funds
    cur.execute(
        "UPDATE fantateam SET cassa_attuale = cassa_attuale - ? WHERE squadra=? AND cassa_attuale >= ?",
        (amount, team, amount),
    )
    return cur.rowcount > 0


def refund_team(conn, team, amount):
    """Refund amount to team's cassa_attuale (create row if needed)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT carryover, cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?",
        (team,),
    )
    r = cur.fetchone()
    if r:
        # r can be a tuple-like; handle both index and key access
        try:
            cur_att = r["cassa_attuale"]
        except Exception:
            cur_att = r[2]
        if cur_att is not None:
            new = float(cur_att) + amount
            cur.execute(
                "UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (new, team)
            )
        else:
            # initialize from cassa_iniziale if present, else default 300
            try:
                iniz = (
                    float(r["cassa_iniziale"])
                    if r["cassa_iniziale"] is not None
                    else 300.0
                )
            except Exception:
                iniz = 300.0
            new = iniz + amount
            cur.execute(
                "UPDATE fantateam SET cassa_attuale=? WHERE squadra=?", (new, team)
            )
    else:
        # create with sensible defaults: carryover 0, cassa_iniziale 300, and cassa_attuale = 300 + amount
        cur.execute(
            "INSERT INTO fantateam(squadra, carryover, cassa_iniziale, cassa_attuale) VALUES (?,?,?,?)",
            (team, 0, 300.0, 300.0 + amount),
        )
    # caller should commit


# Ensure DB columns at startup
ensure_db_columns()

SQUADRE = [
    "FC Bioparco",
    "Nova Spes",
    "Good Old Boys",
    "Atletico Milo",
    "FC Dude",
    "FC Pachuca",
    "AS Quiriti",
    "AS Plusvalenza",
]
ROSE_STRUCTURE = {"Portieri": 3, "Difensori": 8, "Centrocampisti": 8, "Attaccanti": 6}

# Populate teams table now that SQUADRE is defined
ensure_teams_table()


HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
  <title>Catch a Buzz - Market Manager</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 40px; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
      th { background: #eee; }
      th.sort-active { background: #dfefff; }
      th a.header-link { color: inherit; text-decoration: none; display: inline-block; width:100%; }
      input[type=text] { width: 300px; padding: 6px; }
      .search { margin-bottom: 20px; }
      .nav { margin-bottom: 30px; }
      .nav a { margin-right: 20px; }
      /* Team cash boxes: horizontal layout at the top */
      .team-cash-container { display:flex; gap:12px; flex-wrap:nowrap; overflow-x:auto; margin-bottom:18px; align-items:stretch; }
      .team-box { border:1px solid #ccc; padding:10px 12px; background:#fafafa; border-radius:6px; min-width:160px; flex:0 0 auto; }
      .team-name { font-weight:bold; margin-bottom:6px; }
      .team-values { color:#1155cc; }
    .team-sub { font-size:0.9em; color:#666; margin-top:6px; }
    .team-missing { display:inline-block; background:#ffe9d6; color:#7a3b00; padding:4px 8px; border-radius:12px; margin-top:8px; font-weight:bold; }
      .role-badge { display:inline-block; padding:4px 8px; border-radius:10px; color:#fff; font-weight:bold; font-size:0.9em; }
      .role-p { background:#2b6cb0; }
      .role-d { background:#38a169; }
      .role-c { background:#dd6b20; }
      .role-a { background:#d53f8c; }
    </style>
</head>
<body>
  <header style="position:fixed; top:0; left:0; width:100%; max-width:100vw; box-sizing:border-box; display:flex; align-items:center; justify-content:space-between; background:#222; color:#fff; padding:16px 32px; z-index:1000; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow-x:auto;">
    <div style="display:flex; align-items:center; gap:12px; min-width:220px;">
      <img src="https://raw.githubusercontent.com/marketplaceimages/fantaman-logo.png" alt="Logo" style="height:40px; width:40px; border-radius:8px; background:#fff; object-fit:cover;">
      <span style="font-size:1.6em; font-weight:bold; letter-spacing:2px; margin-left:8px;">Fantaman</span>
    </div>
    <nav style="flex:2; text-align:center;">
      <nav style="position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); display:inline-block; text-align:center;">
        <a href="/" style="color:#fff; text-decoration:none; margin:0 18px; font-weight:500;">Market Manager</a>
        <a href="/rose" style="color:#fff; text-decoration:none; margin:0 18px; font-weight:500;">Rose Squadre</a>
      </nav>
    </nav>
    <div style="display:flex; align-items:center; gap:12px; min-width:60px; justify-content:flex-end;">
      <img src="https://cdn-icons-png.flaticon.com/512/1077/1077012.png" alt="Account" style="height:32px; width:32px; border-radius:50%; background:#fff; object-fit:cover;">
    </div>
  </header>
  <div id="team-bar" style="position:fixed; left:50%; top:64px; transform:translateX(-50%); display:flex; gap:10px; z-index:1100;">
    {% for squadra in squadre %}
    <a href="/squadra/{{ squadra|urlencode }}" style="background:#fff; color:#222; border:1px solid #1155cc; border-radius:14px; font-weight:500; padding:6px 12px; font-size:0.85em; box-shadow:0 1px 4px rgba(0,0,0,0.07); position:relative; top:-10px; display:flex; align-items:center; justify-content:center; text-align:center; margin-bottom:-4px; text-decoration:none;">
      <span style="width:100%;">{{ squadra }}</span>
    </a>
    {% endfor %}
  </div>
  <div style="height:84px;"></div>
  <div style="height:44px;"></div>
  <h1 style="margin-top:0px;">Catch a Buzz - Market Manager</h1>
  <!-- Visible server-side debug marker: shows the query the server received and how many results it returned -->
    <!-- Team cash summary: boxes ordered by remaining cash -->
    <div class="team-cash-container" style="display:flex; gap:8px; flex-wrap:nowrap; margin-bottom:18px; align-items:stretch; justify-content:center;">
      {% for t in team_casse %}
      <div class="team-box" style="flex:0 1 12.5%; min-width:120px; max-width:12.5%; box-sizing:border-box;">
        <div class="team-name">{{ t.squadra }}</div>
        <div class="team-values">Cassa attuale: <strong>{{ t.remaining }}</strong></div>
        <div class="team-sub">Cassa iniziale: {{ t.starting }}</div>
      </div>
      {% endfor %}
    </div>
    <div class="team-missing-container" style="display:flex; gap:8px; flex-wrap:nowrap; margin-bottom:18px; align-items:stretch; justify-content:center;">
      {% for t in team_casse_missing %}
      <div class="team-box" style="flex:0 1 12.5%; min-width:120px; max-width:12.5%; box-sizing:border-box; background:#f8f8f8;">
        <div class="team-name">{{ t.squadra }}</div>
        <div style="margin-top:8px;">
          <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
            <span class="team-missing">Giocatori mancanti: <strong>{{ t.missing }}</strong></span>
            <span class="role-badge role-p">P {{ t.missing_portieri }}</span>
            <span class="role-badge role-d">D {{ t.missing_dif }}</span>
            <span class="role-badge role-c">C {{ t.missing_cen }}</span>
            <span class="role-badge role-a">A {{ t.missing_att }}</span>
          </div>
        </div>
      </div>
      {% endfor %}
    </div>
    <form method="get" class="search">
      <input type="text" name="q" placeholder="Cerca giocatore, squadra..." value="{{ query }}">
      <button type="submit">Cerca</button>
    </form>
    {% if suggestions and query %}
      <div class="suggestions" style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-left: 3px solid #007bff; border-radius: 4px;">
        <strong>💡 Forse intendevi:</strong>
        {% for suggestion in suggestions %}
          <a href="?{{ request.query_string|safe|replace('q=' ~ query|urlencode, 'q=' ~ suggestion|urlencode) }}" style="display: inline-block; margin: 2px 8px 2px 0; padding: 4px 8px; background: #e7f1ff; color: #0056b3; text-decoration: none; border-radius: 12px; font-size: 0.9em;">{{ suggestion }}</a>
        {% endfor %}
      </div>
    {% endif %}
    {% if query and results|length > 0 %}
    <div id="players-table">
    <table>
        <tr>
            {% for col in columns %}
                {% set sk = display_to_sortkey.get(col) %}
                <th class="{% if sk and sk==request.args.get('sort_by') %}sort-active{% endif %}">
                  {% if sk %}
                    <a class="header-link" href="{{ header_toggle_links[sk] }}">{{ col }}
                      {% if request.args.get('sort_by') == sk %}
                        {% if request.args.get('sort_dir','asc') == 'asc' %} 🔼 {% else %} 🔽 {% endif %}
                      {% endif %}
                    </a>
                  {% else %}
                    {{ col }}
                  {% endif %}
                </th>
            {% endfor %}
            <th>Azioni</th>
        </tr>
        {% for row in results %}
    <tr data-player-id="{{ row['id'] }}" data-player-name="{{ row['Nome'] if 'Nome' in row.keys() else (row['nome'] if 'nome' in row.keys() else row['id']) }}">
      {% for col in columns %}
      <td>{{ row[col] }}</td>
      {% endfor %}
      <td>
        <button onclick="openAssignPopup('{{ row['id'] }}', '{{ row['nome'] }}')">Assegna giocatore</button>
      </td>
    </tr>
        {% endfor %}
    </table>
    </div>
    {% endif %}

      <script>
      // Intercept header clicks and update the table via fetch
      document.addEventListener('click', function(e){
          var a = e.target.closest && e.target.closest('a.header-link');
          if(!a) return;
          e.preventDefault();
          var url = a.getAttribute('href');
          // Fetch the page and replace the players-table div
          fetch(url).then(r=>r.text()).then(html=>{
              // extract the players-table div
              var m = html.match(/<div id="players-table">([\s\S]*?)<\/div>/i);
              if(m){
                  document.getElementById('players-table').innerHTML = m[1];
              } else {
                  // fallback: replace entire body
                  document.body.innerHTML = html;
              }
          }).catch(err=>{ console.error('Failed to load sorted table', err); window.location = url; });
      });
      </script>

      <!-- Popup Assegna Giocatore -->
      <div id="assignPopup" style="display:none; position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.4); z-index:1000;">
          <div style="background:#fff; padding:30px; max-width:400px; margin:80px auto; border-radius:8px; position:relative;">
              <h2>Assegna giocatore</h2>
              <form id="assignForm" method="post" action="/assegna_giocatore" onsubmit="return submitAssignForm();">
                  <input type="hidden" name="id" id="assign_id">
                  <div><b>Nome:</b> <span id="assign_nome"></span></div>
                  <div style="margin-top:10px;">
                      <label>Squadra:</label>
                      <select name="squadra" required>
                          <option value="">Seleziona...</option>
                          {% for s in squadre %}
                          <option value="{{ s }}">{{ s }}</option>
                          {% endfor %}
                      </select>
                  </div>
                  <div style="margin-top:10px;">
                      <label>Costo:</label>
                      <input type="number" name="costo" min="1" required>
                  </div>
                  <div style="margin-top:10px;">
                      <label>Anni contratto:</label>
                      <select name="anni_contratto" id="anni_contratto" onchange="updateOpzione()" required>
                          <option value="1">1</option>
                          <option value="2">2</option>
                          <option value="3">3</option>
                      </select>
                  </div>
                  <div style="margin-top:10px;">
                      <label>Opzione:</label>
                      <input type="checkbox" name="opzione" id="opzione" checked>
                  </div>
                  <div style="margin-top:20px;">
                      <button type="submit">Salva</button>
                      <button type="button" onclick="closeAssignPopup()">Annulla</button>
                  </div>
                  <!-- inline error container for assign dialog -->
                  <div id="assignError" role="alert" style="color:#8a1f11; background:#fee; padding:8px; margin-top:12px; display:none; border:1px solid #f5c2c2; border-radius:4px;"></div>
              </form>
              <button style="position:absolute; top:10px; right:10px;" onclick="closeAssignPopup()">&times;</button>
          </div>
      </div>

      <script>
      function openAssignPopup(id, nome) {
          document.getElementById('assign_id').value = id;
          document.getElementById('assign_nome').innerText = nome;
          document.getElementById('assignPopup').style.display = 'block';
          document.getElementById('anni_contratto').value = '1';
          updateOpzione();
      }
      function closeAssignPopup() {
          document.getElementById('assignPopup').style.display = 'none';
      }
      function updateOpzione() {
          var anni = document.getElementById('anni_contratto').value;
          var opzione = document.getElementById('opzione');
          if (anni == '3') {
              opzione.checked = false;
              opzione.disabled = true;
          } else {
              opzione.checked = true;
              opzione.disabled = false;
          }
      }
      async function submitAssignForm() {
          const form = document.getElementById('assignForm');
          const formData = new FormData(form);
          // send as form-encoded POST
          const params = new URLSearchParams();
          for (const pair of formData.entries()) params.append(pair[0], pair[1]);
          try {
              const res = await fetch(form.action, {method:'POST', body: params});
              if (!res.ok) {
                  const text = await res.text();
                  // put error into inline container if present
                  const errBox = document.getElementById('assignError');
                  if (errBox) {
                      errBox.style.display = 'block';
                      errBox.innerText = text || res.statusText;
                  } else {
                      showToast('Errore: ' + (text || res.statusText));
                  }
                  return false;
              }
              // success -> close popup and refresh only the team-cash-container and players table
              closeAssignPopup();
              try{
                  // fetch the main page and replace the two fragments we care about
                  const rhtml = await fetch('/');
                  const text = await rhtml.text();
                  // extract team-cash-container
                  const m1 = text.match(/<div class="team-cash-container">([\s\S]*?)<\/div>/i);
                  if(m1){
                      const container = document.querySelector('.team-cash-container');
                      if(container) container.outerHTML = '<div class="team-cash-container">' + m1[1] + '</div>';
                  }
                  // extract players-table div
                  const m2 = text.match(/<div id="players-table">([\s\S]*?)<\/div>/i);
                  if(m2){
                      const pt = document.getElementById('players-table');
                      if(pt) pt.innerHTML = m2[1];
                  }
              }catch(e){
                  // fallback: full reload if partial update fails
                  window.location.reload();
              }
              return false;
          } catch (e) {
              const errBox = document.getElementById('assignError');
              if (errBox) { errBox.style.display = 'block'; errBox.innerText = 'Errore invio: ' + e.message; }
              else { showToast('Errore invio: ' + e.message); }
              return false;
          }
      }
      </script>
    <p>{{ results|length }} giocatori trovati.</p>
</body>
</html>
"""

ROSE_HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>Fantacalcio - Rose Squadre</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 40px; }
      .nav { margin-bottom: 30px; }
      .nav a { margin-right: 20px; }
      .squadra { margin-bottom: 40px; }
      h2 { margin-bottom: 10px; }
      table { border-collapse: collapse; width: 100%; margin-bottom: 10px; }
      th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
      th { background: #eee; }
      .option-checkbox { text-align: center; }
    </style>
</head>
<body>
  <header style="position:fixed; top:0; left:0; width:100%; max-width:100vw; box-sizing:border-box; display:flex; align-items:center; justify-content:space-between; background:#222; color:#fff; padding:16px 32px; z-index:1000; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow-x:auto;">
      <div style="display:flex; align-items:center; gap:12px; min-width:220px;">
        <img src="https://raw.githubusercontent.com/marketplaceimages/fantaman-logo.png" alt="Logo" style="height:40px; width:40px; border-radius:8px; background:#fff; object-fit:cover;">
        <span style="font-size:1.6em; font-weight:bold; letter-spacing:2px; margin-left:8px;">Fantaman</span>
      </div>
      <nav style="flex:2; display:flex; justify-content:center; align-items:center;">
        <a href="/" style="color:#fff; text-decoration:none; margin:0 18px; font-weight:500;">Market Manager</a>
        <a href="/rose" style="color:#fff; text-decoration:none; margin:0 18px; font-weight:500;">Rose Squadre</a>
      </nav>
      <div style="display:flex; align-items:center; gap:12px; min-width:60px; justify-content:flex-end;">
        <img src="https://cdn-icons-png.flaticon.com/512/1077/1077012.png" alt="Account" style="height:32px; width:32px; border-radius:50%; background:#fff; object-fit:cover;">
      </div>
    </header>
    <div id="team-bar" style="position:fixed; left:50%; top:64px; transform:translateX(-50%); display:flex; gap:10px; z-index:1100;">
      {% for squadra in squadre %}
      <a href="/squadra/{{ squadra|urlencode }}" style="background:#fff; color:#222; border:1px solid #1155cc; border-radius:14px; font-weight:500; padding:6px 12px; font-size:0.85em; box-shadow:0 1px 4px rgba(0,0,0,0.07); position:relative; top:-10px; display:flex; align-items:center; justify-content:center; text-align:center; margin-bottom:-4px; text-decoration:none;">
        <span style="width:100%;">{{ squadra }}</span>
      </a>
      {% endfor %}
    </div>
    <div style="height:84px;"></div>
    <h1>Rose Attuali delle Squadre</h1>
    {% for squadra in squadre %}
    <div class="squadra">
      <h2><a href="/squadra/{{ squadra|urlencode }}">{{ squadra }}</a></h2>
      {% for ruolo, n in rose_structure.items() %}
      <table>
          <tr>
              <th colspan="6">{{ ruolo }} ({{ n }})</th>
          </tr>
          <tr>
              <th>#</th>
              <th>Nome</th>
              <th>Squadra reale</th>
              <th>Costo</th>
              <th>Anni contratto</th>
              <th>Opzione</th>
          </tr>
          {% set players = rose.get(squadra, {}).get(ruolo, []) %}
                      {% for p in players %}
          <tr data-player-id="{{ p.id }}" data-role="{{ p.ruolo }}">
              <td>{{ loop.index }}</td>
              <td class="p-nome">{{ p.nome }}</td>
              <td class="p-squadra-reale">{{ p.squadra_reale }}</td>
              <td class="p-costo">{{ p.costo if p.costo is not none else '' }}</td>
              <td class="p-anni">{{ p.anni_contratto if p.anni_contratto is not none else '' }}</td>
              <td class="option-checkbox p-opzione">{{ p.opzione if p.opzione is not none else '' }}</td>
              <td>
                  <button onclick="openEdit({{ p.id }}, this)">Edit</button>
              </td>
          </tr>
          {% endfor %}
          {% for i in range(n - (players|length)) %}
          <tr>
              <td>{{ (players|length) + i + 1 }}</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
              <td class="option-checkbox"><input type="checkbox" disabled></td>
          </tr>
          {% endfor %}
      </table>
      {% endfor %}
    </div>
    {% endfor %}
</body>
</html>
<div id="editDialog" style="display:none; position:fixed; left:0; top:0; width:100vw; height:100vh; background:rgba(0,0,0,0.4); z-index:2000;">
    <div style="background:#fff; padding:20px; max-width:420px; margin:80px auto; border-radius:8px; position:relative;">
      <h3>Modifica giocatore</h3>
      <form id="editForm" onsubmit="return submitEdit();">
          <input type="hidden" id="edit_id">
          <div><label>Squadra:</label>
              <select id="edit_squadra">
                  <option value="">- non assegnato -</option>
                  {% for s in squadre %}
                  <option value="{{ s }}">{{ s }}</option>
                  {% endfor %}
              </select>
          </div>
          <div><label>Costo:</label> <input id="edit_costo" type="number" min="0" step="0.5"></div>
          <div><label>Anni contratto:</label>
              <select id="edit_anni" onchange="editUpdateOpzione()">
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
              </select>
          </div>
          <div><label>Opzione:</label> <input id="edit_opzione" type="checkbox"></div>
          <div style="margin-top:10px;"><button type="submit">Salva</button> <button type="button" onclick="closeEdit()">Annulla</button></div>
      </form>
      <!-- inline error container for edit dialog -->
      <div id="editError" role="alert" style="color:#8a1f11; background:#fee; padding:8px; margin-top:12px; display:none; border:1px solid #f5c2c2; border-radius:4px;"></div>
      <button style="position:absolute; right:8px; top:8px;" onclick="closeEdit()">&times;</button>
    </div>
</div>

<script>
function openEdit(id, btn) {
    // carica i dati del giocatore via fetch
    fetch('/update_player', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id:id})})
      .then(r=>r.json()).then(data=>{
          document.getElementById('edit_id').value = data.id || id;
          document.getElementById('edit_squadra').value = data.squadra || '';
          document.getElementById('edit_costo').value = data.costo || '';
          document.getElementById('edit_anni').value = data.anni_contratto || '1';
          document.getElementById('edit_opzione').checked = (data.opzione=='SI');
          editUpdateOpzione();
          document.getElementById('editDialog').style.display = 'block';
      }).catch(e=>{alert('Errore caricamento giocatore');});
}
function closeEdit(){ document.getElementById('editDialog').style.display='none'; }
function editUpdateOpzione(){ var a=document.getElementById('edit_anni').value; var o=document.getElementById('edit_opzione'); if(a=='3'){ o.checked=false; o.disabled=true; } else { o.disabled=false; o.checked=true; } }
function submitEdit(){
    var id=document.getElementById('edit_id').value;
    var payload={
      id:id,
      squadra: document.getElementById('edit_squadra').value,
      costo: document.getElementById('edit_costo').value || null,
      anni_contratto: document.getElementById('edit_anni').value,
      opzione: document.getElementById('edit_opzione').checked ? 'SI' : 'NO'
    };
    (async ()=>{
      try{
          const res = await fetch('/update_player', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
          if(!res.ok){
              // try parse json error and show inline
              const editErr = document.getElementById('editError');
              try{
                  const j = await res.json();
                  if(j && j.error){
                      if(editErr){ editErr.style.display='block'; editErr.innerText = j.error + (j.available ? (' (disponibile: ' + j.available + ')') : ''); }
                      else { showToast(j.error + (j.available ? (' (disponibile: ' + j.available + ')') : '')); }
                  } else {
                      if(editErr){ editErr.style.display='block'; editErr.innerText = 'Errore server: ' + res.status; }
                      else { showToast('Errore server: ' + res.status); }
                  }
              } catch(e){
                  const t = await res.text();
                  if(editErr){ editErr.style.display='block'; editErr.innerText = t || res.statusText; }
                  else { showToast('Errore: ' + (t || res.statusText)); }
              }
              return false;
          }
          const data = await res.json();
          if(data && data.id){
              // update the specific row inline if present
              const row = document.querySelector('tr[data-player-id="'+data.id+'"]');
              if(row){
                  if(row.querySelector('.p-costo')) row.querySelector('.p-costo').innerText = data.Costo || '';
                  if(row.querySelector('.p-anni')) row.querySelector('.p-anni').innerText = data.anni_contratto || '';
                  if(row.querySelector('.p-opzione')) row.querySelector('.p-opzione').innerText = data.opzione || '';
              }
              showToast('Salvataggio riuscito');
              // also refresh team boxes and players table fragment to reflect budget and sorting
              try{
                  const rhtml = await fetch('/');
                  const text = await rhtml.text();
                  const m1 = text.match(/<div class="team-cash-container">([\s\S]*?)<\/div>/i);
                  if(m1){
                      const container = document.querySelector('.team-cash-container');
                      if(container) container.outerHTML = '<div class="team-cash-container">' + m1[1] + '</div>';
                  }
                  const m2 = text.match(/<div id="players-table">([\s\S]*?)<\/div>/i);
                  if(m2){
                      const pt = document.getElementById('players-table');
                      if(pt) pt.innerHTML = m2[1];
                  }
              }catch(e){
                  // ignore; UI already updated partially
              }
          }
          closeEdit();
          return false;
      }catch(e){ showToast('Errore salvataggio: ' + e.message); return false; }
    })();
    return false;
}

function showToast(msg){
    let t = document.getElementById('toast');
    if(!t){
      t = document.createElement('div'); t.id='toast'; t.style.position='fixed'; t.style.right='20px'; t.style.bottom='20px'; t.style.background='#222'; t.style.color='#fff'; t.style.padding='10px 16px'; t.style.borderRadius='6px'; t.style.zIndex=3000; document.body.appendChild(t);
    }
    t.innerText = msg; t.style.opacity = '1'; setTimeout(()=>{ t.style.transition='opacity 0.6s'; t.style.opacity='0'; }, 1500);
}
</script>
"""


@app.route("/", methods=["GET"])
def index():
    query = request.args.get("q", "").strip()
    ruolo = request.args.get("ruolo", "").strip()
    squadra = request.args.get("squadra", "").strip()
    # ruoli selezionati (checkbox multipli). Se non presenti, tutti abilitati di default
    roles_selected = request.args.getlist("roles")
    costo_min = request.args.get("costo_min", "").strip()
    costo_max = request.args.get("costo_max", "").strip()
    opzione = request.args.get("opzione", "").strip()
    anni_contratto = request.args.get("anni_contratto", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 50

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(giocatori)")
    # Ottieni colonne dalla tabella in modo sicuro
    columns_info = cur.fetchall()
    columns = [row["name"] for row in columns_info]
    # Remove the '#' column from display (it contains internal ids) but keep it available as rowid
    if "#" in columns:
        columns = [c for c in columns if c != "#"]
    # Remove 'Fuori lista' column from display per user request
    if "Fuori lista" in columns:
        columns = [c for c in columns if c != "Fuori lista"]
    # Remove 'Under' and 'R.MANTRA' columns from display per user request
    for hide_col in ["Under", "R.MANTRA"]:
        if hide_col in columns:
            columns = [c for c in columns if c != hide_col]
    # Remove 'FVM/1000' from display per user request
    if "FVM/1000" in columns:
        columns = [c for c in columns if c != "FVM/1000"]
    # Build display_columns ordering so key columns appear first and avoid header/data mismatch
    preferred = ["Nome", "Sq.", "FantaSquadra"]
    # Crea una mappa dei nomi di colonna sicuri (solo lettere, numeri e underscore)
    safe_columns = []
    for col in columns:
        if col.replace("_", "").isalnum():
            safe_columns.append(col)
    if not safe_columns:
        safe_columns = columns

    # Costruisci query avanzata (seleziona anche rowid come id se non presente)
    sql = "SELECT rowid AS id, * FROM giocatori WHERE 1=1"
    params = []
    if query:
        like = f"%{query}%"
        # Usa solo colonne sicure per costruire la clausola LIKE
        where = " OR ".join([f'"{col}" LIKE ?' for col in safe_columns])
        sql += f" AND ({where})"
        params += [like] * len(safe_columns)
    if ruolo:
        sql += " AND ruolo LIKE ?"
        params.append(f"%{ruolo}%")
    # Filtra per ruoli (checkbox): Portieri, Difensori, Centrocampisti, Attaccanti
    role_map = {
        "Portieri": ["P", "G"],
        "Difensori": ["D"],
        "Centrocampisti": ["C"],
        "Attaccanti": ["A"],
    }
    # if roles_selected empty -> default all
    if not roles_selected:
        roles_selected = list(role_map.keys())
    # costruiamo lista di codici (es. 'A','C',...)
    codes = []
    for rcat in roles_selected:
        codes += role_map.get(rcat, [])
    if codes:
        role_where = " OR ".join([f'"R." LIKE ?' for _ in codes])
        sql += f" AND ({role_where})"
        params += [f"{c}%" for c in codes]
    else:
        # nessun ruolo selezionato => nessun risultato
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

    # Conta totale risultati
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
    # Applica filtro ruoli anche al count
    if not roles_selected:
        roles_selected = list(role_map.keys())
    codes = []
    for rcat in roles_selected:
        codes += role_map.get(rcat, [])
    if codes:
        role_where = " OR ".join([f'"R." LIKE ?' for _ in codes])
        count_sql += f" AND ({role_where})"
        count_params += [f"{c}%" for c in codes]
    else:
        count_sql += " AND 0"
    cur.execute(count_sql, count_params)
    total = cur.fetchone()[0]

    # --- Sorting support ---
    # Accept sort params: sort_by (column key) and sort_dir (asc/desc)
    sort_by = request.args.get("sort_by", "").strip()
    sort_dir = request.args.get("sort_dir", "asc").lower()

    # Map of allowed sort keys to actual SQL expressions (quoted where needed)
    # We detect the actual column names present in the table (to handle punctuation/case)
    def q(colname):
        return f'"{colname}"'

    allowed_sorts = {}
    # static mappings if present
    if "Nome" in columns:
        allowed_sorts["nome"] = q("Nome")
    if "Sq." in columns:
        allowed_sorts["sq"] = q("Sq.")
    if "FantaSquadra" in columns:
        allowed_sorts["fantasquadra"] = q("FantaSquadra")
    # allow sorting by squadra (team owner)
    if "squadra" in columns:
        allowed_sorts["squadra"] = q("squadra")
    # detect PGv, Costo columns explicitly
    for c in columns:
        cl = c.lower()
        if cl == "pgv" or cl == "pgv":
            allowed_sorts["pgv"] = q(c)
        if cl == "costo" or "costo" in cl:
            allowed_sorts["costo"] = q(c)
    # detect MV, FM, QUOT-like columns by substring match (case-insensitive)
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
        # also detect pgv if not caught earlier (e.g., 'PGv')
        if (
            "pg" in cl
            and "pgv" not in allowed_sorts
            and cl.replace(".", "").startswith("pg")
        ):
            allowed_sorts.setdefault("pgv", q(c))

    # Build clean sort links (preserve existing query params except sort_by/sort_dir)
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
    # header toggle links: clicking header toggles sort direction (and we expose active sort)
    header_toggle_links = {}
    active_sort_key = sort_by
    active_sort_dir = sort_dir
    for k in allowed_sorts.keys():
        # if currently sorted by k asc -> toggle to desc, otherwise toggle to asc
        if active_sort_key == k and active_sort_dir == "asc":
            header_toggle_links[k] = sort_links[k]["desc"]
        else:
            header_toggle_links[k] = sort_links[k]["asc"]

    # Map displayed column names to our sort keys so template can render arrows
    display_to_sortkey = {}
    # common mappings
    if "Nome" in columns and "nome" in allowed_sorts:
        display_to_sortkey["Nome"] = "nome"
    if "Sq." in columns and "sq" in allowed_sorts:
        display_to_sortkey["Sq."] = "sq"
    if "FantaSquadra" in columns and "fantasquadra" in allowed_sorts:
        display_to_sortkey["FantaSquadra"] = "fantasquadra"
    # numeric/display columns: try to match actual column names
    for k, expr in allowed_sorts.items():
        # expr is quoted column name like "MV" or "Costo"
        colname = expr.strip('"')
        # prefer to map simple uppercase variants
        display_to_sortkey[colname] = k
    if sort_by in allowed_sorts:
        direction = "ASC" if sort_dir != "desc" else "DESC"
        # Numeric sorts: MV, FM, QUOT -> cast to REAL
        if sort_by in ("mv", "fm", "quot", "pgv", "costo"):
            # clean common non-numeric characters before casting (commas, percent, euro symbol, spaces)
            clean = f"REPLACE(REPLACE(REPLACE(REPLACE({allowed_sorts[sort_by]}, ',', ''), '%', ''), '€', ''), ' ', '')"
            order_expr = f"CAST({clean} AS REAL) {direction}"
        else:
            # Text sorts: case-insensitive
            order_expr = f"{allowed_sorts[sort_by]} COLLATE NOCASE {direction}"
        # Add a deterministic secondary sort by Nome (case-insensitive asc)
        if "Nome" in columns:
            order_expr = f"{order_expr}, {q('Nome')} COLLATE NOCASE ASC"
        # Inject ORDER BY just before LIMIT/OFFSET
        sql = sql.rstrip()
        sql += f" ORDER BY {order_expr}"
    # Paginazione
    offset = (page - 1) * per_page
    sql += f" LIMIT {per_page} OFFSET {offset}"
    cur.execute(sql, params)
    results = cur.fetchall()

    conn.close()

    # Genera suggerimenti se la ricerca ha restituito pochi risultati e c'è una query
    suggestions = []
    if (
        query and len(query) >= 2 and len(results) < 5
    ):  # Se pochi risultati e query abbastanza lunga
        try:
            # Nuova connessione per i suggerimenti
            sugg_conn = sqlite3.connect(DB_PATH)
            sugg_conn.row_factory = sqlite3.Row
            sugg_cur = sugg_conn.cursor()

            # Cerca nomi simili usando una ricerca più permissiva
            suggestion_sql = """
            SELECT DISTINCT Nome FROM giocatori
            WHERE Nome LIKE ? OR Nome LIKE ? OR Nome LIKE ?
            ORDER BY LENGTH(Nome) ASC
            LIMIT 8
            """
            # Diverse varianti della query per matching più flessibile (safe slicing)
            query_variants = [
                f"%{query[:min(4, len(query))]}%",  # Primi 4 caratteri (o meno se la query è corta)
                f"%{query[:min(3, len(query))]}%",  # Primi 3 caratteri (o meno se la query è corta)
                f"%{query}%",  # Query originale
            ]
            sugg_cur.execute(suggestion_sql, query_variants)
            suggestion_results = sugg_cur.fetchall()

            for row in suggestion_results:
                name = row["Nome"]
                # Evita di suggerire nomi già nei risultati
                if (
                    not any(r["Nome"] == name for r in results if "Nome" in r.keys())
                    and name.lower() != query.lower()
                ):
                    suggestions.append(name)

            sugg_conn.close()
        except Exception as e:
            # In caso di errore, continua senza suggerimenti
            suggestions = (
                []
            )  # Compute per-team cash summary (starting, spent, remaining) to render the top boxes
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    team_casse = []
    for s in SQUADRE:
        # starting pot from fantateam or default
        cur.execute(
            "SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (s,)
        )
        tr = cur.fetchone()
        if tr and tr["cassa_iniziale"] is not None:
            starting = float(tr["cassa_iniziale"])
        else:
            starting = 300.0

        # sum costs of visible roster (exclude optioned without contract)
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

        # count assigned players per role code (first char of "R.") and compute missing total
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
        counts = {row["code"]: row["cnt"] for row in cur.fetchall()}
        # counts per role code: P/G for portieri, D, C, A
        portieri_count = int(counts.get("P", 0)) + int(counts.get("G", 0))
        dif_count = int(counts.get("D", 0))
        cen_count = int(counts.get("C", 0))
        att_count = int(counts.get("A", 0))

        # missing per role according to ROSE_STRUCTURE
        missing_portieri = max(0, ROSE_STRUCTURE.get("Portieri", 0) - portieri_count)
        missing_dif = max(0, ROSE_STRUCTURE.get("Difensori", 0) - dif_count)
        missing_cen = max(0, ROSE_STRUCTURE.get("Centrocampisti", 0) - cen_count)
        missing_att = max(0, ROSE_STRUCTURE.get("Attaccanti", 0) - att_count)

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
    conn.close()
    # sort by remaining desc
    team_casse.sort(key=lambda x: x["remaining"], reverse=True)
    team_casse_missing = sorted(team_casse, key=lambda x: x["missing"])

    # Filtri HTML
    # Include hidden sort inputs so that auto-submitting role checkboxes preserves the active sort
    filters_html = """
<form method="get" class="search">
    <input type="text" name="q" placeholder="Cerca giocatore..." value="{{ query }}">
    <input type="text" name="ruolo" placeholder="Ruolo" value="{{ ruolo }}">
    <input type="text" name="squadra" placeholder="Squadra reale" value="{{ squadra }}">
    <input type="number" name="costo_min" placeholder="Costo min" value="{{ costo_min }}" style="width:90px;">
    <input type="number" name="costo_max" placeholder="Costo max" value="{{ costo_max }}" style="width:90px;">
    <input type="text" name="opzione" placeholder="Opzione" value="{{ opzione }}" style="width:90px;">
    <input type="number" name="anni_contratto" placeholder="Anni contratto" value="{{ anni_contratto }}" style="width:90px;">
  <!-- Visible submit button so users can click to search (previously missing) -->
  <button type="submit">Cerca</button>
    <!-- Preserve active sort when form auto-submits -->
    <input type="hidden" name="sort_by" value="{{ request.args.get('sort_by','') }}">
    <input type="hidden" name="sort_dir" value="{{ request.args.get('sort_dir','asc') }}">
    <div style="margin-top:8px;">
      <label><input type="checkbox" name="roles" value="Portieri" {% if 'Portieri' in roles_selected %}checked{% endif %} onchange="this.form.submit()"> Portieri</label>
      <label style="margin-left:8px;"><input type="checkbox" name="roles" value="Difensori" {% if 'Difensori' in roles_selected %}checked{% endif %} onchange="this.form.submit()"> Difensori</label>
      <label style="margin-left:8px;"><input type="checkbox" name="roles" value="Centrocampisti" {% if 'Centrocampisti' in roles_selected %}checked{% endif %} onchange="this.form.submit()"> Centrocampisti</label>
      <label style="margin-left:8px;"><input type="checkbox" name="roles" value="Attaccanti" {% if 'Attaccanti' in roles_selected %}checked{% endif %} onchange="this.form.submit()"> Attaccanti</label>
    </div>
</form>
"""

    # Paginazione HTML
    pagination_html = """
    <div style="margin:20px 0;">
      {% if page > 1 %}
          <a href="?{{ request.query_string|safe|replace('page=' ~ page, 'page=' ~ (page-1)) }}">&lt; Prec</a>
      {% endif %}
      Pagina {{ page }} di {{ (total // per_page) + (1 if total % per_page else 0) }}
      {% if page * per_page < total %}
          <a href="?{{ request.query_string|safe|replace('page=' ~ page, 'page=' ~ (page+1)) }}">Succ &gt;</a>
      {% endif %}
    </div>
    """

    # HTML principale: keep the original simple search form in HTML (don't inject advanced filters)
    html = HTML
    if query and len(results) > 0:
        html = html.replace(
            "<p>{{ results|length }} giocatori trovati.</p>",
            pagination_html
            + "<p>{{ results|length }} giocatori trovati su "
            + str(total)
            + ".</p>",
        )
    else:
        html = html.replace("<p>{{ results|length }} giocatori trovati.</p>", "")

    return render_template_string(
        html,
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


@app.route("/assegna_giocatore", methods=["POST"])
def validate_player_assignment(id, squadra, costo, anni_contratto):
    if not id or not str(id).isdigit():
        return "ID giocatore non valido."
    if squadra and squadra not in SQUADRE:
        return "Squadra selezionata non valida."
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


def normalize_assignment_values(squadra, costo, anni_contratto, opzione):
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


def assegna_giocatore():
    # Tutte le query SQL usano parametri per prevenire SQL injection.
    """
    Assegna un giocatore a una squadra, gestendo costi, opzioni e anni di contratto.
    - Valida l'input utente
    - Aggiorna la cassa della squadra
    - Gestisce il rimborso in caso di cambio squadra
    - Aggiorna la tabella giocatori
    """
    """
  Valida i dati di assegnazione giocatore ricevuti dal form.
  Restituisce una stringa di errore se non valido, altrimenti None.
  """
    """
  Normalizza i valori di input per l'assegnazione del giocatore.
  Restituisce tuple di valori coerenti per l'update SQL.
  """
    id = request.form.get("id")
    squadra = request.form.get("squadra")
    costo = request.form.get("costo")
    anni_contratto = request.form.get("anni_contratto")
    opzione = "SI" if request.form.get("opzione") == "on" else "NO"
    error_msg = validate_player_assignment(id, squadra, costo, anni_contratto)
    if error_msg:
        return (
            f'<html><body style="font-family:Arial; color:#8a1f11; background:#fff8e1; padding:24px; border-radius:8px;">'
            f"<h2>Errore di assegnazione</h2>"
            f'<div style="margin-bottom:12px;">{error_msg}</div>'
            f'<a href="/" style="color:#0056b3; text-decoration:underline;">Torna indietro</a>'
            f"</body></html>",
            400,
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    squadra_val, costo_val, anni_contratto, opzione = normalize_assignment_values(
        squadra, costo, anni_contratto, opzione
    )
    try:
        # Find current assignment (if any)
        cur.execute("SELECT squadra, Costo FROM giocatori WHERE rowid=?", (id,))
        prev = cur.fetchone()
        prev_team = None
        prev_cost = 0.0
        if prev:
            prev_team = prev["squadra"]
            try:
                prev_cost = (
                    float(prev["Costo"]) if prev["Costo"] not in (None, "") else 0.0
                )
            except Exception:
                prev_cost = 0.0
        # If removing assignment (squadra_val is None): refund previous team's cassa_attuale by prev_cost
        if squadra_val is None:
            if prev_team and prev_cost > 0:
                refund_team(conn, prev_team, prev_cost)
            # update player row
            cur.execute(
                'UPDATE giocatori SET "squadra"=?, "Costo"=?, "anni_contratto"=?, "opzione"=? WHERE rowid=?',
                (None, None, None, None, id),
            )
            conn.commit()
            return __import__("flask").redirect("/")
        # Assigning or moving: attempt atomic charge on target team
        # If moving from prev_team, refund prev first (so their cash is restored)
        if prev_team and prev_team != squadra_val and prev_cost > 0:
            refund_team(conn, prev_team, prev_cost)
        # Try to atomically deduct the cost from target team
        if costo_val > 0:
            ok = atomic_charge_team(conn, squadra_val, costo_val)
            if not ok:
                conn.rollback()
                # insufficient funds -> return 400 HTML for form
                cur.execute(
                    "SELECT cassa_attuale FROM fantateam WHERE squadra=?",
                    (squadra_val,),
                )
                rr = cur.fetchone()
                avail = (
                    float(rr["cassa_attuale"])
                    if rr and rr["cassa_attuale"] is not None
                    else 300.0
                )
                return (
                    '<html><body>Fondi insufficienti per assegnare (costo: {} &gt; disponibile: {}). <a href="/">Indietro</a></body></html>'.format(
                        costo_val, avail
                    ),
                    400,
                )
        # Update player row
        cur.execute(
            'UPDATE giocatori SET "squadra"=?, "Costo"=?, "anni_contratto"=?, "opzione"=? WHERE rowid=?',
            (squadra_val, costo_val, anni_contratto, opzione, id),
        )
        conn.commit()
    finally:
        conn.close()
    # Reindirizza alla pagina principale
    from flask import redirect

    return redirect("/")


@app.route("/update_player", methods=["POST"])
def update_player():
    # Tutte le query SQL usano parametri per prevenire SQL injection.
    data = request.get_json() or {}
    pid = data.get("id")
    squadra = data.get("squadra")
    costo = data.get("costo")
    anni_contratto = data.get("anni_contratto")
    opzione = data.get("opzione")
    # Validazione input
    error_msg = None
    if not pid or not str(pid).isdigit():
        error_msg = "ID giocatore non valido."
    if squadra and squadra not in SQUADRE:
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
            __import__("flask").jsonify(
                {"error": error_msg, "help": "Controlla i dati inseriti e riprova."}
            ),
            400,
        )
    # normalize empty squadra to NULL
    if squadra == "" or squadra is None:
        squadra_val = None
        anni_contratto = None
        opzione = None
    else:
        squadra_val = squadra
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            # parse costo
            try:
                costo_val = (
                    float(str(costo).replace(",", "").replace("€", "").strip())
                    if costo not in (None, "")
                    else 0.0
                )
            except Exception:
                costo_val = 0.0

            # fetch previous assignment
            cur.execute("SELECT squadra, Costo FROM giocatori WHERE rowid=?", (pid,))
            prev = cur.fetchone()
            prev_team = None
            prev_cost = 0.0
            if prev:
                prev_team = prev["squadra"]
                try:
                    prev_cost = (
                        float(prev["Costo"]) if prev["Costo"] not in (None, "") else 0.0
                    )
                except Exception:
                    prev_cost = 0.0

            # If unassigning (squadra_val is None), refund previous team
            if squadra_val is None and prev_team:
                if prev_cost > 0:
                    refund_team(conn, prev_team, prev_cost)
                cur.execute(
                    'UPDATE giocatori SET "squadra"=?, "Costo"=?, "anni_contratto"=?, "opzione"=? WHERE rowid=?',
                    (None, None, None, None, pid),
                )
                conn.commit()
                cur.execute(
                    'SELECT rowid as id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione, squadra FROM giocatori WHERE rowid=?',
                    (pid,),
                )
                row = cur.fetchone()
                return jsonify(dict(row) if row else {})

            # Assigning or moving: if moving from prev_team refund prev first
            if prev_team and prev_team != squadra_val and prev_cost > 0:
                refund_team(conn, prev_team, prev_cost)

            # Try to deduct atomically from target team
            if squadra_val and costo_val > 0:
                ok = atomic_charge_team(conn, squadra_val, costo_val)
                if not ok:
                    conn.rollback()
                    # return JSON error with available funds
                    cur.execute(
                        "SELECT cassa_attuale FROM fantateam WHERE squadra=?",
                        (squadra_val,),
                    )
                    r = cur.fetchone()
                    avail = (
                        float(r["cassa_attuale"])
                        if r and r["cassa_attuale"] is not None
                        else 300.0
                    )
                    return (
                        __import__("flask").jsonify(
                            {
                                "error": "Fondi insufficienti",
                                "needed": costo_val,
                                "available": avail,
                            }
                        ),
                        400,
                    )

            # Finally, update player
            cur.execute(
                'UPDATE giocatori SET "squadra"=?, "Costo"=?, "anni_contratto"=?, "opzione"=? WHERE rowid=?',
                (squadra_val, costo_val, anni_contratto, opzione, pid),
            )
            conn.commit()
            cur.execute(
                'SELECT rowid as id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione, squadra FROM giocatori WHERE rowid=?',
                (pid,),
            )
            row = cur.fetchone()
            result = dict(row) if row else {}
        finally:
            conn.close()
        return jsonify(result)


@app.route("/rose", methods=["GET"])
def rose():
    # Costruisci rose leggendo dal DB
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    # Recupera i giocatori con squadra assegnata
    # IMPORTANT: players who are optioned (opzione='SI') but have no contract (anni_contratto IS NULL)
    # should NOT appear in the visible rosters — they are only included once confirmed during the auction.
    cur.execute(
        """SELECT rowid AS id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione, FantaSquadra
        FROM giocatori
        WHERE FantaSquadra IS NOT NULL
        AND NOT (opzione IS NOT NULL AND anni_contratto IS NULL)
    """
    )
    rows = cur.fetchall()
    conn.close()

    # Mappa ruolo codice a ruolo esteso
    ruolo_map = {
        "P": "Portieri",
        "G": "Portieri",
        "D": "Difensori",
        "C": "Centrocampisti",
        "A": "Attaccanti",
    }

    # Inizializza le rose. Include sia le squadre canoniche in SQUADRE sia qualsiasi nome di squadra trovato nel DB
    # (così i giocatori assegnati con nomi leggermente diversi non spariscono dalla pagina Rose).
    teams_in_rows = {row["FantaSquadra"] for row in rows if row["FantaSquadra"]}
    all_teams = list(dict.fromkeys(list(SQUADRE) + sorted(teams_in_rows)))
    # Inizializza la mappa delle rose per tutte le team names trovate
    rose = {s: {r: [] for r in ROSE_STRUCTURE.keys()} for s in all_teams}
    for row in rows:
        sname = row["FantaSquadra"]
        codice_ruolo = (row["ruolo"] or "").strip()
        # prendi il primo carattere rilevante
        key = None
        if codice_ruolo:
            ch = codice_ruolo[0].upper()
            key = ruolo_map.get(ch)
        if not key:
            # se non riusciamo a determinare il ruolo dalla colonna 'R.' salta il giocatore
            continue
        # append only if we resolved a role and the squadra is present in our rose mapping
        if sname in rose:
            rose[sname][key].append(
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

    # render using the combined team list so links and displays include non-canonical names
    return render_template_string(
        ROSE_HTML, squadre=all_teams, rose_structure=ROSE_STRUCTURE, rose=rose
    )


TEAM_HTML = """
    <!DOCTYPE html>
    <html lang="it">
    <head>
      <meta charset="utf-8">
      <title>Roster - {{ tname }}</title>
      <style>
          body { font-family: Arial, sans-serif; margin: 24px; }
          .nav a{ margin-right:12px; }
          .cassa { border:1px solid #ccc; padding:12px; display:inline-block; margin-bottom:16px; background:#f9f9f9; }
          .badge { display:inline-block; min-width:40px; padding:6px 8px; margin-left:8px; background:#eee; border-radius:6px; text-align:center; }
          table{ border-collapse:collapse; width:100%; margin-top:8px; }
          th,td{ border:1px solid #ccc; padding:6px; text-align:left; }
          th{background:#eee;}
      </style>
    </head>
    <body>
  <header style="position:fixed; top:0; left:0; width:100%; max-width:100vw; box-sizing:border-box; display:flex; align-items:center; justify-content:space-between; background:#222; color:#fff; padding:16px 32px; z-index:1000; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow-x:auto;">
        <div style="display:flex; align-items:center; gap:12px; min-width:220px;">
          <img src="https://raw.githubusercontent.com/marketplaceimages/fantaman-logo.png" alt="Logo" style="height:40px; width:40px; border-radius:8px; background:#fff; object-fit:cover;">
          <span style="font-size:1.6em; font-weight:bold; letter-spacing:2px; margin-left:8px;">Fantaman</span>
        </div>
        <nav style="flex:2; display:flex; justify-content:center; align-items:center;">
          <a href="/" style="color:#fff; text-decoration:none; margin:0 18px; font-weight:500;">Market Manager</a>
          <a href="/rose" style="color:#fff; text-decoration:none; margin:0 18px; font-weight:500;">Rose Squadre</a>
        </nav>
        <div style="display:flex; align-items:center; gap:12px; min-width:60px; justify-content:flex-end;">
          <img src="https://cdn-icons-png.flaticon.com/512/1077/1077012.png" alt="Account" style="height:32px; width:32px; border-radius:50%; background:#fff; object-fit:cover;">
        </div>
      </header>
      <div id="team-bar" style="position:fixed; left:50%; top:64px; transform:translateX(-50%); display:flex; gap:10px; z-index:1100;">
        {% for squadra in squadre %}
        <a href="/squadra/{{ squadra|urlencode }}" style="background:#fff; color:#222; border:1px solid #1155cc; border-radius:14px; font-weight:500; padding:6px 12px; font-size:0.85em; box-shadow:0 1px 4px rgba(0,0,0,0.07); position:relative; top:-10px; display:flex; align-items:center; justify-content:center; text-align:center; margin-bottom:-4px; text-decoration:none;">
          <span style="width:100%;">{{ squadra }}</span>
        </a>
        {% endfor %}
      </div>
      <div style="height:84px;"></div>
      <h1>Roster: {{ tname }}</h1>

      <div class="cassa">
          <strong>Cassa</strong>
          <div>Iniziale: {{ starting_pot }}</div>
          <div>Speso: {{ total_spent }}</div>
          <div>Rimanente: {{ cassa }}</div>
      </div>

      {% for ruolo, n in rose_structure.items() %}
          {% set players = roster.get(ruolo, []) %}
          <h2>{{ ruolo }} <span class="badge">Mancano: {{ (n - (players|length)) if n - (players|length) > 0 else 0 }}</span></h2>
          <table>
              <tr><th>#</th><th>Nome</th><th>Squadra reale</th><th>Costo</th><th>Anni contratto</th><th>Opzione</th></tr>
              {% for p in players %}
              <tr>
                  <td>{{ loop.index }}</td>
                  <td>{{ p.nome }}</td>
                  <td>{{ p.squadra_reale }}</td>
                  <td>{{ p.costo if p.costo is not none else '' }}</td>
                  <td>{{ p.anni_contratto if p.anni_contratto is not none else '' }}</td>
                  <td>{{ p.opzione if p.opzione is not none else '' }}</td>
              </tr>
              {% endfor %}
              {% for i in range(n - (players|length)) %}
              <tr>
                  <td>{{ (players|length) + i + 1 }}</td>
                  <td></td><td></td><td></td><td></td><td></td>
              </tr>
              {% endfor %}
          </table>
      {% endfor %}

    </body>
    </html>
    """


@app.route("/squadra/<team_name>", methods=["GET"])
def squadra(team_name):
    # decode team name from URL
    from urllib.parse import unquote

    tname = unquote(team_name)
    # load players assigned to this team (exclude optioned without contract)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        'SELECT rowid as id, "Nome" as nome, "Sq." as squadra_reale, "R." as ruolo, "Costo" as costo, anni_contratto, opzione FROM giocatori WHERE FantaSquadra = ? AND NOT (opzione IS NOT NULL AND anni_contratto IS NULL)',
        (tname,),
    )
    rows = cur.fetchall()
    conn.close()

    # build per-role lists using same shape as rose() so templates match exactly
    ruolo_map = {
        "P": "Portieri",
        "G": "Portieri",
        "D": "Difensori",
        "C": "Centrocampisti",
        "A": "Attaccanti",
    }
    team_roster = {r: [] for r in ROSE_STRUCTURE.keys()}
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

    # compute cassa using fantateam table: starting from per-team cassa_iniziale and subtract Costo
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT cassa_iniziale, cassa_attuale FROM fantateam WHERE squadra=?", (tname,)
    )
    team_row = cur.fetchone()
    if team_row:
        starting_pot = float(team_row["cassa_iniziale"])
        # if cassa_attuale is managed separately we could prefer that; for now compute spent from players
    else:
        starting_pot = 300.0
    total_spent = sum([float(r["costo"]) for r in rows if r["costo"] not in (None, "")])
    cassa = starting_pot - total_spent
    conn.close()

    # compute missing per role
    missing = {
        r: max(0, ROSE_STRUCTURE[r] - len(team_roster[r]))
        for r in ROSE_STRUCTURE.keys()
    }

    # prepare a rose-like mapping for the template
    rose = {tname: team_roster}
    return render_template_string(
        TEAM_HTML,
        tname=tname,
        roster=team_roster,
        rose_structure=ROSE_STRUCTURE,
        starting_pot=starting_pot,
        total_spent=total_spent,
        cassa=cassa,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
