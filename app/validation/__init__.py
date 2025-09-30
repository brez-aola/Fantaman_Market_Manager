"""Validation module for API input validation.

Provides Marshmallow schemas for all API endpoints.
"""

from .schemas import (
    PlayerCreateSchema, PlayerUpdateSchema,
    TeamCreateSchema, TeamUpdateSchema,
    MarketAssignSchema, MarketTransferSchema,
    LoginSchema, RegisterSchema,
    player_create_schema, player_update_schema,
    team_create_schema, team_update_schema,
    market_assign_schema, market_transfer_schema,
    login_schema, register_schema
)

__all__ = [
    'PlayerCreateSchema', 'PlayerUpdateSchema',
    'TeamCreateSchema', 'TeamUpdateSchema',
    'MarketAssignSchema', 'MarketTransferSchema',
    'LoginSchema', 'RegisterSchema',
    'player_create_schema', 'player_update_schema',
    'team_create_schema', 'team_update_schema',
    'market_assign_schema', 'market_transfer_schema',
    'login_schema', 'register_schema'
]
