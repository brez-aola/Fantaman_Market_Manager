# Testing the API locally

This file describes quick commands to run the API and the test suites we use for security and documentation checks.

Prerequisites:
- Python 3.10+
- Virtualenv (recommended)
- `requirements.txt` installed

Quick start:

1. Create virtualenv and install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start the app in background (development)

```bash
nohup python3 app.py > flask_server.log 2>&1 &
sleep 2
tail -n 50 flask_server.log
```

3. Run the security test suite

```bash
python3 test_api_security.py
```

4. Run docs + rate limit checks

```bash
python3 test_api_docs_and_rate_limiting.py
```

Notes:
- The CI workflow includes broader tests and linting under `.github/workflows/ci.yml`.
- If you change rate limits, update `app/security/config.py` and `app/security/decorators.py` accordingly.
