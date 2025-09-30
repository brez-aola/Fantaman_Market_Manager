"""Modern Flask routes using Repository Pattern.

This module contains the refactored routes that use the new repository pattern
and dependency injection system for clean separation of concerns.
"""

from .api_routes import bp as api_bp, web_bp
from .team_routes import bp as team_bp
from .market_routes import bp as market_bp

__all__ = ['api_bp', 'web_bp', 'team_bp', 'market_bp']
