#!/usr/bin/env bash
set -euo pipefail

# Simple development setup script for WSL / Unix-like environments
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
VENV_DIR="$PROJECT_ROOT/.venv"

echo "Project root: $PROJECT_ROOT"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv in $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

echo "Activating virtualenv"
source "$VENV_DIR/bin/activate"

echo "Upgrading pip"
pip install --upgrade pip

if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
  echo "Installing requirements.txt"
  pip install -r "$PROJECT_ROOT/requirements.txt"
else
  echo "No requirements.txt found, skipping pip install -r requirements.txt"
fi

echo "Installing pre-commit and hooks"
pip install pre-commit || true
pre-commit install || true

echo "Done. Activate the venv with: source .venv/bin/activate"
