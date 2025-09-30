"""Validation schemas for API requests using Marshmallow.

Provides input validation for all API endpoints following Azure security best practices.
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from typing import Dict, Any


class PlayerCreateSchema(Schema):
    """Schema for validating player creation requests."""

    name = fields.Str(
        required=True,
        validate=[
            validate.Length(min=2, max=100),
            validate.Regexp(r'^[a-zA-Z0-9\s\-\'\.]+$', error='Invalid characters in name')
        ],
        error_messages={'required': 'Player name is required'}
    )

    role = fields.Str(
        required=True,
        validate=validate.OneOf(['P', 'D', 'C', 'A'], error='Role must be P, D, C, or A'),
        error_messages={'required': 'Player role is required'}
    )

    cost = fields.Float(
        load_default=0.0,
        validate=validate.Range(min=0.0, max=999.9, error='Cost must be between 0 and 999.9')
    )

    real_team = fields.Str(
        load_default='',
        validate=validate.Length(max=50)
    )

    team_id = fields.Int(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=1)
    )

    is_injured = fields.Bool(load_default=False)
class PlayerUpdateSchema(Schema):
    """Schema for validating player update requests."""

    name = fields.Str(
        validate=[
            validate.Length(min=2, max=100),
            validate.Regexp(r'^[a-zA-Z0-9\s\-\'\.]+$', error='Invalid characters in name')
        ]
    )

    role = fields.Str(
        validate=validate.OneOf(['P', 'D', 'C', 'A'], error='Role must be P, D, C, or A')
    )

    cost = fields.Float(
        validate=validate.Range(min=0.0, max=999.9, error='Cost must be between 0 and 999.9')
    )

    real_team = fields.Str(validate=validate.Length(max=50))
    team_id = fields.Int(allow_none=True, validate=validate.Range(min=1))
    is_injured = fields.Bool()


class TeamCreateSchema(Schema):
    """Schema for validating team creation requests."""

    name = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=50),
            validate.Regexp(r'^[a-zA-Z0-9\s\-\'\.]+$', error='Invalid characters in team name')
        ],
        error_messages={'required': 'Team name is required'}
    )

    cash = fields.Float(
        load_default=300.0,
        validate=validate.Range(min=0.0, max=10000.0, error='Cash must be between 0 and 10000')
    )

    league_id = fields.Int(
        load_default=1,
        validate=validate.Range(min=1)
    )
class TeamUpdateSchema(Schema):
    """Schema for validating team update requests."""

    name = fields.Str(
        validate=[
            validate.Length(min=3, max=50),
            validate.Regexp(r'^[a-zA-Z0-9\s\-\'\.]+$', error='Invalid characters in team name')
        ]
    )

    cash = fields.Float(
        validate=validate.Range(min=0.0, max=10000.0, error='Cash must be between 0 and 10000')
    )

    league_id = fields.Int(validate=validate.Range(min=1))


class MarketAssignSchema(Schema):
    """Schema for validating market assignment requests."""

    player_id = fields.Int(
        required=True,
        validate=validate.Range(min=1),
        error_messages={'required': 'Player ID is required'}
    )

    team_id = fields.Int(
        required=True,
        validate=validate.Range(min=1),
        error_messages={'required': 'Team ID is required'}
    )

    cost = fields.Float(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=0.0, max=999.9)
    )


class MarketTransferSchema(Schema):
    """Schema for validating market transfer requests."""

    player_id = fields.Int(
        required=True,
        validate=validate.Range(min=1),
        error_messages={'required': 'Player ID is required'}
    )

    from_team_id = fields.Int(
        required=True,
        validate=validate.Range(min=1),
        error_messages={'required': 'Source team ID is required'}
    )

    to_team_id = fields.Int(
        required=True,
        validate=validate.Range(min=1),
        error_messages={'required': 'Target team ID is required'}
    )

    transfer_cost = fields.Float(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=0.0, max=999.9)
    )

    @validates_schema
    def validate_different_teams(self, data: Dict[str, Any], **kwargs):
        """Ensure source and target teams are different."""
        if data.get('from_team_id') == data.get('to_team_id'):
            raise ValidationError('Source and target teams must be different')


class LoginSchema(Schema):
    """Schema for validating login requests."""

    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=50),
            validate.Regexp(r'^[a-zA-Z0-9_]+$', error='Username can only contain letters, numbers, and underscores')
        ],
        error_messages={'required': 'Username is required'}
    )

    password = fields.Str(
        required=True,
        validate=validate.Length(min=6, max=100),
        error_messages={'required': 'Password is required'}
    )


class RegisterSchema(LoginSchema):
    """Schema for validating registration requests."""

    email = fields.Email(
        required=True,
        error_messages={'required': 'Email is required', 'invalid': 'Invalid email format'}
    )

    confirm_password = fields.Str(
        required=True,
        validate=validate.Length(min=6, max=100),
        error_messages={'required': 'Password confirmation is required'}
    )

    @validates_schema
    def validate_passwords(self, data: Dict[str, Any], **kwargs):
        """Ensure password and confirm_password match."""
        if data.get('password') != data.get('confirm_password'):
            raise ValidationError('Passwords do not match', field_name='confirm_password')


# Schema instances for reuse
player_create_schema = PlayerCreateSchema()
player_update_schema = PlayerUpdateSchema()
team_create_schema = TeamCreateSchema()
team_update_schema = TeamUpdateSchema()
market_assign_schema = MarketAssignSchema()
market_transfer_schema = MarketTransferSchema()
login_schema = LoginSchema()
register_schema = RegisterSchema()
