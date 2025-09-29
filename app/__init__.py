import logging
import os

from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings
from .security.config import init_security


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )

    # Load configuration from settings
    app.config.from_mapping(
        SECRET_KEY=settings.SECRET_KEY,
        JWT_SECRET_KEY=settings.JWT_SECRET_KEY,
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        JWT_REFRESH_TOKEN_EXPIRE_DAYS=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS,
        DEBUG=settings.DEBUG,

        # Legacy compatibility - keep these for now
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
        SQLALCHEMY_DATABASE_URI=None,
        # Legacy admin config (will be deprecated)
        ADMIN_USER="admin",
        ADMIN_PASS="admin",
        # Security settings
        AUTH_ENABLED=True,
        MAX_LOGIN_ATTEMPTS=5,
        ACCOUNT_LOCKOUT_DURATION=30,  # minutes
    )

    if test_config:
        app.config.update(test_config)

    # Configure SQLAlchemy engine/session using DATABASE_URL from settings
    db_uri = settings.DATABASE_URL

    # Configure engine based on database type
    if settings.is_postgresql:
        # PostgreSQL specific configuration
        engine = create_engine(
            db_uri,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.DEBUG  # Log SQL queries in debug mode
        )
    else:
        # SQLite configuration (fallback)
        engine = create_engine(
            db_uri,
            connect_args={"check_same_thread": False},
            echo=settings.DEBUG
        )

    SessionLocal = sessionmaker(bind=engine)

    # attach to app for other modules to use
    app.extensions = getattr(app, "extensions", {})
    app.extensions["db_engine"] = engine
    app.extensions["db_session_factory"] = SessionLocal

    # Initialize security (JWT, rate limiting)
    jwt_manager, limiter = init_security(app)
    app.extensions["jwt_manager"] = jwt_manager
    app.extensions["limiter"] = limiter

    # initialize authentication middleware
    if app.config.get("AUTH_ENABLED", True):
        from .auth.middleware import AuthMiddleware
        auth_middleware = AuthMiddleware(app)

    # register blueprints
    try:
        from .admin import bp as admin_bp
        from .api import bp as api_bp
        from .auth.routes import bp as auth_bp
        from .market import bp as market_bp
        from .teams import bp as teams_bp

        # Register modern routes with Repository Pattern
        from .routes import api_bp as modern_api_bp
        from .routes import web_bp as modern_web_bp
        from .routes import team_bp as modern_team_bp
        from .routes import market_bp as modern_market_bp

        # Register security routes
        from .routes.auth_routes import auth_bp as security_auth_bp

        # Register API documentation
        from .docs import init_api_docs
        api_docs = init_api_docs(app)

        app.register_blueprint(auth_bp)  # Legacy Authentication API
        app.register_blueprint(security_auth_bp, url_prefix="/api/v1/auth")  # Modern Auth API
        app.register_blueprint(api_bp, url_prefix="/api")  # Legacy API
        app.register_blueprint(modern_api_bp)  # Modern API with Repository Pattern
        app.register_blueprint(modern_web_bp)  # Modern web pages (/, /rose)
        app.register_blueprint(market_bp, url_prefix="/legacy/market")  # Legacy market (fallback)
        app.register_blueprint(modern_market_bp, url_prefix="/market")  # Modern market with Repository Pattern
        app.register_blueprint(admin_bp)
        app.register_blueprint(teams_bp, url_prefix="/legacy/teams")  # Legacy teams (fallback)
        app.register_blueprint(modern_team_bp)  # Modern teams with Repository Pattern
    except Exception as e:
        # Log blueprint registration errors so missing modules don't fail silently
        logging.exception("Failed to register blueprints: %s", e)

    # helper to create DB tables based on SQLAlchemy models
    def init_db():
        try:
            from .models import Base

            Base.metadata.create_all(bind=engine)
        except Exception as e:
            logging.exception("init_db failed: %s", e)
            # re-raise so callers (tests) can handle or log as needed
            raise

    app.init_db = init_db

    # helper to initialize authentication system
    def init_auth(admin_username="admin", admin_email="admin@fantacalcio.local",
                  admin_password="admin123"):
        try:
            from .auth.init_auth import AuthInitializer

            auth_init = AuthInitializer(SessionLocal)
            return auth_init.initialize_all(admin_username, admin_email, admin_password)
        except Exception as e:
            logging.exception("init_auth failed: %s", e)
            return False

    app.init_auth = init_auth

    return app
