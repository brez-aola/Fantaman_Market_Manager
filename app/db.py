"""Lightweight DB connection helper.

Provides a single place to create sqlite3 connections with the correct row_factory
and a default path. Scripts and modules should call `get_connection(db_path=None)` so
we can change creation logic in one place later (for example to switch to SQLAlchemy).
"""

import os
import sqlite3
from typing import Optional


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a sqlite3.Connection configured with Row factory.

    If db_path is not provided, uses the environment variable GIOCATORI_DB or the
    repository default at ../giocatori.db.
    """
    if db_path is None:
        db_path = os.environ.get("GIOCATORI_DB")
    if not db_path:
        db_path = os.path.join(os.path.dirname(__file__), "..", "giocatori.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
