import os
import shutil
import tempfile

import pytest

from app import create_app


@pytest.fixture()
def tmp_db_path(tmp_path):
    # create a temporary copy of the existing DB if present, otherwise create an empty DB
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src = os.path.join(repo_root, 'giocatori.db')
    dest = tmp_path / 'giocatori.db'
    if os.path.exists(src):
        shutil.copy(src, dest)
    else:
        # ensure file exists
        dest.write_text('')
    return str(dest)


@pytest.fixture()
def app(tmp_db_path):
    # create app configured to use the temp DB
    test_config = {
        'DB_PATH': tmp_db_path,
        'TESTING': True,
    }
    app = create_app(test_config)
    # ensure tables created via SQLAlchemy models if code expects them
    try:
        app.init_db()
    except Exception:
        # models may not be applied; ignore for now
        pass
    yield app


def test_index_and_rose_endpoints(app):
    client = app.test_client()

    r = client.get('/')
    assert r.status_code == 200
    assert b'/static/css/main.css' in r.data

    r2 = client.get('/rose')
    assert r2.status_code == 200
    assert b'/static/css/main.css' in r2.data
