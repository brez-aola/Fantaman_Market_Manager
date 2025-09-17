import os
import sys

# Ensure repo root is on sys.path so tests can import the app package
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
