"""Helper to initialize the database schema using SQLAlchemy models.

Usage (from repo root):
python3 scripts/init_db.py

This will import the Flask app factory and call app.init_db() which uses SQLAlchemy
models defined in app/models.py to create tables.
"""

import os
import sys

# ensure repo root is on path
HERE = os.path.dirname(os.path.dirname(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from app import create_app

app = create_app()

if __name__ == "__main__":
    print("Initializing DB (this will create tables defined in app.models)")
    app.init_db()
    print("Done.")
