CI / Tests — quick guide

This repository includes a GitHub Actions workflow at `.github/workflows/ci.yml` that:

- runs on pushes and pull requests to `main`/`master`.
- executes on a Python matrix (3.10, 3.11).
- installs dependencies from `requirements.txt`.
- runs linters (`black` check + `flake8`) and `pytest` with coverage.
- uploads coverage artifacts.

Local sanity checks

1) Create and activate your Python environment (WSL):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install black flake8 pytest pytest-cov
```

2) Run linters:

```bash
# check formatting
black --check .

# run flake8
flake8 --max-line-length=120
```

3) Run tests (fast integration smoke):

```bash
pytest -q
```

Notes and recommendations

- The CI workflow caches pip downloads (actions/cache) to speed up runs. If you need deterministic installs in CI, pin versions in `requirements.txt`.
- To see what CI runs, check the file `.github/workflows/ci.yml`.
- If you change dependencies, update `requirements.txt` and consider updating CI matrix versions accordingly.

Database & alembic

- Alembic is scaffolded under `alembic/`; an initial no-op baseline revision was created to avoid accidental DDL in existing DBs.
- To mark an existing DB as being at the baseline revision locally, run:

```bash
# from repo root
alembic stamp head
```

If you want me to tighten CI further (e.g., reintroduce a validated cache step, enable coverage uploads per matrix into separate folders, or fix YAML style issues flagged by `yamllint`) I can do that next.
