# Contributing

Grazie per contribuire a Fantacalcio Market Manager! Qui ci sono istruzioni rapide per mettere a punto l'ambiente di sviluppo e rispettare le regole di formato e linting.

## Setup rapido (WSL / Bash)

1. Crea un virtualenv e attivalo:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Installa le dipendenze (se esiste `requirements.txt`):

```bash
pip install -r requirements.txt
```

3. Installa pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

4. Per eseguire i controlli manualmente:

```bash
pre-commit run --all-files
```

## Stile e strumenti

- Black: formattazione automatica (line-length = 88)
- isort: organizzazione import
- flake8: linting
- mypy: controllo tipizzazione (base)
- bandit: controlli di sicurezza statici

## Pull Request
- Assicurati che tutti i test passino e che `pre-commit` non segnali errori prima di aprire una PR.
# Contributing

Thanks for helping improve Fantacalcio Market Manager.

- Please follow the code style: Black for formatting and flake8 for linting.
- Run tests locally with `python -m pytest`.
- Open PRs against `main` and include a short description of changes and testing steps.
- For larger refactors (DB migration, auth), file an issue linking to the roadmap in `work_doc/roadmap.md`.
\nBranch protection
------------
See work_doc/branch_protection.md for the branch protection policy and developer workflow.
