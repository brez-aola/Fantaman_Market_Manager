"""Minimal top-level runner for the package-style Flask app.

This file intentionally keeps a tiny surface API for backwards compatibility
if someone runs `python app.py` directly. The real app is provided by
app.create_app() and the routes/live logic lives in the package modules.
"""

from app import create_app


def main():
    app = create_app()
    # If running as script, use debug auto-reload to match previous behavior
    app.run(debug=True, host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
