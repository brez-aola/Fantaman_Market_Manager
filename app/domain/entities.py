"""Domain entities representing core business objects.

Entities have identity and lifecycle. They encapsulate business rules
and maintain invariants within their boundaries.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .value_objects import Email, Username, Money, PlayerRole, TeamName


class EntityId:
    """Base class for entity identifiers."""

    def __init__(self, value: int):
        if value <= 0:
            raise ValueError("Entity ID must be positive")
        self._value = value

    @property
    def value(self) -> int:
        return self._value

    def __eq__(self, other) -> bool:
        if not isinstance(other, EntityId):
            return False
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return str(self._value)


class UserId(EntityId):
    """User entity identifier."""
    pass


class TeamId(EntityId):
    """Team entity identifier."""
    pass


class PlayerId(EntityId):
    """Player entity identifier."""
    pass


class LeagueId(EntityId):
    """League entity identifier."""
    pass


@dataclass
class UserEntity:
    """User domain entity with authentication and authorization."""

    id: Optional[UserId]
    username: Username
    email: Email
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    failed_login_attempts: int = 0
    account_locked_until: Optional[datetime] = None

    def authenticate(self, password: str, hashed_password: str) -> bool:
        """Authenticate user with password."""
        from app.services.auth_service import AuthService
        return AuthService.verify_password(password, hashed_password)

    def lock_account(self, duration_minutes: int = 30) -> None:
        """Lock user account for specified duration."""
        from datetime import timedelta
        self.account_locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.is_active = False

    def unlock_account(self) -> None:
        """Unlock user account."""
        self.account_locked_until = None
        self.is_active = True
        self.failed_login_attempts = 0

    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.account_locked_until is None:
            return False
        return datetime.utcnow() < self.account_locked_until

    def record_login_attempt(self, success: bool) -> None:
        """Record login attempt result."""
        if success:
            self.failed_login_attempts = 0
            self.last_login = datetime.utcnow()
        else:
            self.failed_login_attempts += 1

            # Auto-lock after 5 failed attempts
            if self.failed_login_attempts >= 5:
                self.lock_account()


@dataclass
class TeamEntity:
    """Team domain entity with budget and player management."""

    id: Optional[TeamId]
    name: TeamName
    cash: Money
    league_id: LeagueId
    created_at: datetime

    def can_afford(self, amount: Money) -> bool:
        """Check if team can afford a given amount."""
        return self.cash.amount >= amount.amount

    def spend_money(self, amount: Money) -> None:
        """Spend money from team budget."""
        if not self.can_afford(amount):
            raise ValueError(f"Insufficient funds. Available: {self.cash}, Required: {amount}")
        self.cash = Money(self.cash.amount - amount.amount)

    def receive_money(self, amount: Money) -> None:
        """Add money to team budget."""
        self.cash = Money(self.cash.amount + amount.amount)

    def validate_roster_limits(self, players: List['PlayerEntity']) -> bool:
        """Validate team roster against league rules."""
        role_counts = {}
        for player in players:
            role = player.role.value.value  # Get the string value from PlayerRoleEnum
            role_counts[role] = role_counts.get(role, 0) + 1

        # Standard fantasy football roster limits
        limits = {
            'P': 3,  # Portieri
            'D': 8,  # Difensori
            'C': 8,  # Centrocampisti
            'A': 6   # Attaccanti
        }

        for role, count in role_counts.items():
            if count > limits.get(role, 0):
                return False

        return True
@dataclass
class PlayerEntity:
    """Player domain entity with market and assignment logic."""

    id: Optional[PlayerId]
    name: str
    role: PlayerRole
    cost: Money
    real_team: Optional[str]
    team_id: Optional[TeamId] = None
    contract_years: Optional[int] = None
    option: Optional[str] = None

    def is_free_agent(self) -> bool:
        """Check if player is a free agent."""
        return self.team_id is None

    def assign_to_team(self, team_id: TeamId) -> None:
        """Assign player to a team."""
        if not self.is_free_agent():
            raise ValueError(f"Player {self.name} is already assigned to team {self.team_id}")
        self.team_id = team_id

    def release_from_team(self) -> None:
        """Release player from current team."""
        if self.is_free_agent():
            raise ValueError(f"Player {self.name} is already a free agent")
        self.team_id = None

    def update_cost(self, new_cost: Money) -> None:
        """Update player cost with validation."""
        if new_cost.amount < 0:
            raise ValueError("Player cost cannot be negative")
        self.cost = new_cost

    def extend_contract(self, years: int) -> None:
        """Extend player contract."""
        if years <= 0:
            raise ValueError("Contract extension must be positive")
        self.contract_years = (self.contract_years or 0) + years


@dataclass
class LeagueEntity:
    """League domain entity with team and competition management."""

    id: Optional[LeagueId]
    name: str
    slug: str
    max_teams: int = 8
    created_at: Optional[datetime] = None

    def can_add_team(self, current_team_count: int) -> bool:
        """Check if league can accept more teams."""
        return current_team_count < self.max_teams

    def validate_team_addition(self, team: TeamEntity, current_teams: List[TeamEntity]) -> bool:
        """Validate if team can be added to league."""
        if not self.can_add_team(len(current_teams)):
            return False

        # Check for duplicate team names
        for existing_team in current_teams:
            if existing_team.name.value == team.name.value:
                return False

        return True


class PlayerAssignmentRules:
    """Domain service for player assignment business rules."""

    @staticmethod
    def can_assign_player(player: PlayerEntity, team: TeamEntity, team_players: List[PlayerEntity]) -> bool:
        """Check if player can be assigned to team based on business rules."""

        # Player must be free agent
        if not player.is_free_agent():
            return False

        # Team must have sufficient funds
        if not team.can_afford(player.cost):
            return False

        # Check roster limits
        role_counts = {}
        for p in team_players:
            role = p.role.value
            role_counts[role] = role_counts.get(role, 0) + 1

        player_role = player.role.value
        current_count = role_counts.get(player_role, 0)

        limits = {'P': 3, 'D': 8, 'C': 8, 'A': 6}
        max_allowed = limits.get(player_role, 0)

        return current_count < max_allowed


class TeamBudgetRules:
    """Domain service for team budget management rules."""

    @staticmethod
    def calculate_remaining_budget(team: TeamEntity, team_players: List[PlayerEntity]) -> Money:
        """Calculate team's remaining budget after player costs."""
        total_spent = sum(player.cost.amount for player in team_players)
        return Money(team.cash.amount - total_spent)

    @staticmethod
    def validate_transaction(team: TeamEntity, amount: Money) -> bool:
        """Validate if team can perform a financial transaction."""
        return team.can_afford(amount)


class MarketRules:
    """Domain service for market operation rules."""

    @staticmethod
    def calculate_market_value(players: List[PlayerEntity]) -> Money:
        """Calculate total market value of players."""
        total = sum(player.cost.amount for player in players)
        return Money(total)

    @staticmethod
    def get_free_agents(players: List[PlayerEntity]) -> List[PlayerEntity]:
        """Get all free agent players."""
        return [player for player in players if player.is_free_agent()]

    @staticmethod
    def filter_by_role(players: List[PlayerEntity], role: PlayerRole) -> List[PlayerEntity]:
        """Filter players by role."""
        return [player for player in players if player.role == role]
