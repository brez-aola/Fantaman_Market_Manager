import os

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )

    # default config
    app.config.from_mapping(
        DB_PATH=os.path.join(os.path.dirname(__file__), "..", "giocatori.db"),
        ROSE_STRUCTURE={
            "Portieri": 3,
            "Difensori": 8,
            "Centrocampisti": 8,
            "Attaccanti": 6,
        },
        SQUADRE=[
            "FC Bioparco",
            "Nova Spes",
            "Good Old Boys",
            "Atletico Milo",
            "FC Dude",
            "FC Pachuca",
            "AS Quiriti",
            "AS Plusvalenza",
        ],
        SECRET_KEY="dev",
        SQLALCHEMY_DATABASE_URI=None,
        ADMIN_USER="admin",
        ADMIN_PASS="admin",
    )

    if test_config:
        app.config.update(test_config)

    # configure SQLAlchemy engine/session
    db_path = app.config.get("DB_PATH")
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI") or f"sqlite:///{db_path}"
    engine = create_engine(
        db_uri,
        connect_args=(
            {"check_same_thread": False} if db_uri.startswith("sqlite") else {}
        ),
    )
    SessionLocal = sessionmaker(bind=engine)

    # attach to app for other modules to use
    app.extensions = getattr(app, "extensions", {})
    app.extensions["db_engine"] = engine
    app.extensions["db_session_factory"] = SessionLocal

    # register blueprints
    try:
        from .admin import bp as admin_bp
        from .api import bp as api_bp
        from .market import bp as market_bp
        from .teams import bp as teams_bp

        app.register_blueprint(api_bp, url_prefix="/api")
        app.register_blueprint(market_bp)
        app.register_blueprint(admin_bp)
        app.register_blueprint(teams_bp)
    except Exception:
        # keep failing registration quiet for now; files may be moved later
        pass

    # helper to create DB tables based on SQLAlchemy models
    def init_db():
        try:
            from .models import Base

            Base.metadata.create_all(bind=engine)
        except Exception:
            # fail silently; caller can inspect exceptions
            raise

    app.init_db = init_db

    return app
