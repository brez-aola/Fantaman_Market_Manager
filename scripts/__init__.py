"""Package marker for scripts to make mypy imports deterministic in pre-commit.

This file is intentionally empty. Adding it avoids mypy detecting modules under
multiple names (e.g. both `migrate_sqlite_to_postgres` and
`scripts.migrate_sqlite_to_postgres`).
"""
