Title: Refactor: centralize market business logic into MarketService and centralize sqlite access

Summary

This PR consolidates legacy market/business logic into a single service, `app.services.market_service.MarketService`, makes the `app.market` blueprint the canonical routing surface for the web UI, and centralizes sqlite connection creation behind `app.db.get_connection()`.

Why

- Reduce duplicated sqlite fallback SQL scattered across routes and scripts.
- Improve testability by allowing MarketService methods to accept sqlite3.Connection objects (in-memory DB tests).
- Make the blueprint (`app.market`) the single source of HTTP routing/handlers.
- Prepare the codebase for an eventual migration to an ORM-first approach while preserving backward compatibility.

What changed (high level)

- New/Updated core:
  - `app/services/market_service.py`: central service with business logic, team cash helpers, and sqlite fallback read helpers (get_name_suggestions, get_team_summaries, get_team_roster).
  - `app/db.py`: `get_connection(db_path=None)` helper to create sqlite3 connections with Row factory.
  - `app/market.py`: blueprint updated to delegate to MarketService where appropriate and to use `get_connection` for sqlite fallbacks.
  - `app/teams.py`, `app.py`: now delegate to MarketService and use `get_connection`.

- Tests:
  - Added `tests/test_market_service_helpers.py` (in-memory sqlite) to cover name suggestions, team summaries, and team roster helpers.
  - Existing tests updated to use the service and in-memory DB where appropriate.
  - Test result: 16 passed locally.

- Scripts:
  - Several utility scripts migrated to use `app.db.get_connection()` instead of direct `sqlite3.connect(...)`.

- Minor tidyups:
  - Removed unused `import sqlite3` from application modules where `get_connection` is used.

Compatibility / migration notes

- The flask app keeps thin deprecated wrappers in `app.py` that delegate to MarketService (they emit DeprecationWarning). These remain for backwards compatibility.
- Scripts that rely on direct sqlite usage (e.g. some `apply_options_*` scripts) still import `sqlite3` where needed; no behavioral changes expected.

Testing

- Run tests: `pytest -q` — all tests pass locally (16 passed).
- Manual smoke tests: navigated main pages and team views using sqlite fallback and ORM fallback paths.

Follow-ups / TODOs

- (Optional) Remove deprecated wrappers from `app.py` after a deprecation period.
- (Optional) Migrate remaining utility scripts to always use `app.db.get_connection()` for consistency.
- Add CI job that runs tests + linter (recommended: `ruff` + `black` check).
- Consider adding type hints and running `mypy` for stricter checks.

Checklist for PR

- [ ] Confirm PR title and description
- [ ] Verify tests run in CI (I can add a GH Actions workflow to run pytest + ruff)
- [ ] Confirm whether to remove deprecated wrappers in `app.py` in this PR or a follow-up

Notes

- This change is intentionally conservative in behavior — it centralizes and encapsulates business logic without changing existing public behaviors or data formats.
- If reviewers want, I can break the PR into smaller logical commits (service + db helper + blueprint changes + tests + scripts) for easier review.

---

If you want I can open the PR on GitHub now, or add a minimal GitHub Actions workflow to run tests on push/PR before opening.
