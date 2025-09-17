"""Simple development runner that imports the app factory and runs the Flask dev server.
Use this for manual UI smoke testing only.
"""
from app import create_app

if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5001, debug=True)
