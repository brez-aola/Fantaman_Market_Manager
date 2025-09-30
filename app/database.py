"""Database dependency injection.

Provides database session and repository instances for dependency injection
in Flask routes and services.
"""

from functools import wraps
from typing import Generator
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.repositories import (
    UserRepository,
    TeamRepository,
    PlayerRepository,
    LeagueRepository
)
import logging

logger = logging.getLogger(__name__)

# Database engine and session factory
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """Get database session with automatic cleanup.

    Yields:
        SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_repository(db: Session) -> UserRepository:
    """Get user repository instance.

    Args:
        db: Database session

    Returns:
        UserRepository instance
    """
    return UserRepository(db)


def get_team_repository(db: Session) -> TeamRepository:
    """Get team repository instance.

    Args:
        db: Database session

    Returns:
        TeamRepository instance
    """
    return TeamRepository(db)


def get_player_repository(db: Session) -> PlayerRepository:
    """Get player repository instance.

    Args:
        db: Database session

    Returns:
        PlayerRepository instance
    """
    return PlayerRepository(db)


def get_league_repository(db: Session) -> LeagueRepository:
    """Get league repository instance.

    Args:
        db: Database session

    Returns:
        LeagueRepository instance
    """
    return LeagueRepository(db)


class RepositoryContainer:
    """Container for all repository instances."""

    def __init__(self, db: Session):
        """Initialize repository container.

        Args:
            db: Database session
        """
        self.db = db
        self._user_repo = None
        self._team_repo = None
        self._player_repo = None
        self._league_repo = None

    @property
    def users(self) -> UserRepository:
        """Get user repository."""
        if self._user_repo is None:
            self._user_repo = UserRepository(self.db)
        return self._user_repo

    @property
    def teams(self) -> TeamRepository:
        """Get team repository."""
        if self._team_repo is None:
            self._team_repo = TeamRepository(self.db)
        return self._team_repo

    @property
    def players(self) -> PlayerRepository:
        """Get player repository."""
        if self._player_repo is None:
            self._player_repo = PlayerRepository(self.db)
        return self._player_repo

    @property
    def leagues(self) -> LeagueRepository:
        """Get league repository."""
        if self._league_repo is None:
            self._league_repo = LeagueRepository(self.db)
        return self._league_repo


def get_repositories(db: Session) -> RepositoryContainer:
    """Get repository container with all repositories.

    Args:
        db: Database session

    Returns:
        RepositoryContainer instance
    """
    return RepositoryContainer(db)


def with_repositories(func):
    """Decorator to inject repositories into route handlers.

    Usage:
        @app.route('/users')
        @with_repositories
        def get_users(repos: RepositoryContainer):
            users = repos.users.get_all()
            return jsonify([{'id': u.id, 'username': u.username} for u in users])
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with SessionLocal() as db:
            repos = RepositoryContainer(db)
            return func(repos, *args, **kwargs)
    return wrapper


def with_db_session(func):
    """Decorator to inject database session into route handlers.

    Usage:
        @app.route('/users')
        @with_db_session
        def get_users(db: Session):
            users = db.query(User).all()
            return jsonify([{'id': u.id, 'username': u.username} for u in users])
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with SessionLocal() as db:
            return func(db, *args, **kwargs)
    return wrapper
