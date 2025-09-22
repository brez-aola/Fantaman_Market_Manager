# Fantacalcio - Market Manager

Questo repository contiene una applicazione Flask (Proof-of-Concept) per la gestione del mercato fantacalcistico.

Scopo di questa cartella `work_doc` è fornire analisi e roadmap per trasformare il progetto in un prodotto di livello industriale.

## Come iniziare (sviluppo locale)

Prerequisiti:
- Python 3.10+
- pip

Installazione:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Nota: l'app attuale è un POC e richiede lavoro per produzione. Vedi `work_doc/` per analisi e roadmap completa.

## Running tests

Use a virtual environment and the pinned `requirements.txt` before running tests. This keeps test runs hermetic and avoids loading unrelated site-package pytest plugins from the system Python.

Local:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
# disable third-party pytest plugin autoload when you run locally if you see import-time plugin errors
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q
```

CI recommendation:

- Ensure CI installs dependencies from `requirements.txt` in a clean environment.
- Set the environment variable `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` in the CI job that runs pytest. This prevents global site-packages plugins from being auto-loaded and breaking the test run.

