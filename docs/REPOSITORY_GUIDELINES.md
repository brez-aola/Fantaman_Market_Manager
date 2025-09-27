Repository guidelines for Fantaman_Market_Manager
===============================================

This document describes recommended practices, branching and PR workflow, linting and testing rules, CI configuration, and maintenance tasks for the repository. Keep this document up to date — small improvements here pay back exponentially.

1. Branching and PRs
---------------------
- Branches
  - Use short-lived feature branches: `feature/<short-desc>`, `fix/<ticket>-<short-desc>`, `chore/<desc>`.
  - Rebase frequently on `main` to avoid long-lived diverging branches.
- Pull Requests
  - Target `main` (or a release branch if applicable). Create one feature per PR.
  - Include in PR description: what changed, why, test coverage, migration steps (if any).
  - Use squash-and-merge by default (keeps `main` linear). Use merge commits only for larger merges that need explicit history.
  - Require at least one approving review before merge.

2. CI and quality gates
-----------------------
- CI (GitHub Actions)
  - Must run `flake8`, `pytest` and `bandit` on PRs and `push` to main.
  - Use a matrix for Python versions supported by the project (3.9–3.11).
  - Cache pip to speed up builds.
- Required checks
  - Protect `main`: require CI checks to pass and one review before merging.

3. Pre-commit hooks (local developer experience)
-----------------------------------------------
- Use `pre-commit` to run formatting and basic checks before commits.
- Recommended hooks:
  - `black` (formatting), `isort` (imports), `flake8` (linting), `ruff` (optional fast lint), `bandit` (security checks), `check-yaml`, `end-of-file-fixer`.
- Installation
  - pip install pre-commit
  - pre-commit install
  - pre-commit run --all-files

4. Tests
--------
- Use pytest. Keep tests fast and deterministic where possible.
- Use markers to separate slow/integration tests from unit tests.
- Keep coverage threshold reasonable (e.g., 70–80%) and report it in CI.

5. Security and dependencies
----------------------------
- Use Dependabot or equivalent to keep dependencies up to date.
- Run `bandit` and `safety` in CI to detect insecure dependencies or patterns.

6. Repository hygiene
---------------------
- .gitignore: keep generated files, local venvs and DB dumps excluded.
- Avoid committing large files; use Git LFS when necessary.
- Regularly prune merged remote/local branches.

7. Release notes and changelog
-----------------------------
- Keep a `CHANGELOG.md` or use GitHub Releases derived from merge commits.

8. Onboarding and contribution
------------------------------
- `CONTRIBUTING.md` should document how to run tests, format code, and open PRs.
- Add a `PULL_REQUEST_TEMPLATE.md` with checklist: tests, lint, changes documented, migration steps.

9. Emergency procedures
-----------------------
- If a secret is committed: rotate credentials immediately, and consider `git filter-repo`/BFG to remove history.
- If a release breaks: create a rollback tag from pre-release backup tag and deploy the rollback.

Appendix: Links and commands
- Create pre-commit config: see `.pre-commit-config.yaml` in this repo.
- Common cleanup commands:
  - `git fetch --prune`
  - `git branch --merged origin/main | egrep -v "(^\*| main| master)" | xargs -r git branch -d`
  - `git remote prune origin`
