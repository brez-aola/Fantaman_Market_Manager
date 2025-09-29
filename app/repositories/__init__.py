"""Repository pattern implementation.

This module provides data access layer abstractions following the Repository pattern
for clean separation of concerns and improved testability.
"""

from .base import BaseRepository
from .user_repository import UserRepository
from .team_repository import TeamRepository
from .player_repository import PlayerRepository
from .league_repository import LeagueRepository

__all__ = [
    'BaseRepository',
    'UserRepository',
    'TeamRepository',
    'PlayerRepository',
    'LeagueRepository'
]
