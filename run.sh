#!/usr/bin/env bash
# Simple development runner that uses the new package factory but keeps the old app.py as fallback
set -e

if [ -f "app.py" ]; then
  echo "Starting legacy app.py (for now)"
  python app.py
else
  echo "Starting app package via factory"
  export FLASK_APP=app:create_app
  flask run --reload
fi
