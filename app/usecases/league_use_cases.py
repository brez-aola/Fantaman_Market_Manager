"""League-specific use cases for managing league operations."""

from typing import List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.entities import LeagueEntity, TeamEntity
from app.domain.value_objects import Money


# DTOs for League operations
@dataclass
class LeagueDTO:
    """Data Transfer Object for League information."""
    id: Optional[int]
    name: str
    max_teams: int
    budget_per_team: float
    current_teams: int
    is_active: bool
    is_full: bool

    @classmethod
    def from_entity(cls, league: LeagueEntity) -> 'LeagueDTO':
        """Create DTO from domain entity."""
        return cls(
            id=league.id,
            name=league.name,
            max_teams=league.max_teams,
            budget_per_team=league.budget_per_team.amount,
            current_teams=len(league.teams),
            is_active=league.is_active,
            is_full=league.is_full()
        )


@dataclass
class LeagueStatsDTO:
    """Data Transfer Object for League statistics."""
    league_id: int
    league_name: str
    total_teams: int
    max_teams: int
    total_budget: float
    average_team_cash: float
    teams_with_full_roster: int
    teams_with_partial_roster: int

    @classmethod
    def create(cls, league: LeagueEntity) -> 'LeagueStatsDTO':
        """Create statistics DTO from league entity."""
        total_cash = sum(team.cash.amount for team in league.teams)
        avg_cash = total_cash / len(league.teams) if league.teams else 0.0

        full_rosters = sum(1 for team in league.teams if team.is_roster_valid())
        partial_rosters = len(league.teams) - full_rosters

        return cls(
            league_id=league.id or 0,
            league_name=league.name,
            total_teams=len(league.teams),
            max_teams=league.max_teams,
            total_budget=league.budget_per_team.amount * league.max_teams,
            average_team_cash=avg_cash,
            teams_with_full_roster=full_rosters,
            teams_with_partial_roster=partial_rosters
        )


@dataclass
class CreateLeagueRequest:
    """Request to create a new league."""
    name: str
    max_teams: int = 8
    budget_per_team: float = 1000.0


@dataclass
class UpdateLeagueRequest:
    """Request to update league information."""
    league_id: int
    name: Optional[str] = None
    max_teams: Optional[int] = None
    budget_per_team: Optional[float] = None
    is_active: Optional[bool] = None


@dataclass
class AddTeamToLeagueRequest:
    """Request to add team to league."""
    league_id: int
    team_id: int


@dataclass
class ListLeaguesRequest:
    """Request to list leagues."""
    active_only: bool = True
    available_only: bool = False  # Only leagues with space for more teams
    limit: int = 50
    offset: int = 0


@dataclass
class ListLeaguesResult:
    """Result of listing leagues."""
    leagues: List[LeagueDTO]
    total_count: int
    has_more: bool


# Repository interface
class LeagueRepositoryInterface(ABC):
    """Interface for League repository operations."""

    @abstractmethod
    def get_by_id(self, league_id: int) -> Optional[LeagueEntity]:
        """Get league by ID."""
        pass

    @abstractmethod
    def get_by_name(self, name: str) -> Optional[LeagueEntity]:
        """Get league by name."""
        pass

    @abstractmethod
    def create(self, league: LeagueEntity) -> LeagueEntity:
        """Create new league."""
        pass

    @abstractmethod
    def update(self, league: LeagueEntity) -> LeagueEntity:
        """Update existing league."""
        pass

    @abstractmethod
    def delete(self, league_id: int) -> bool:
        """Delete league by ID."""
        pass

    @abstractmethod
    def get_all(self, active_only: bool = True, limit: int = 50, offset: int = 0) -> List[LeagueEntity]:
        """Get all leagues with pagination."""
        pass

    @abstractmethod
    def get_available_leagues(self) -> List[LeagueEntity]:
        """Get leagues that still have space for teams."""
        pass

    @abstractmethod
    def add_team_to_league(self, league_id: int, team: TeamEntity) -> bool:
        """Add team to league."""
        pass

    @abstractmethod
    def remove_team_from_league(self, league_id: int, team_id: int) -> bool:
        """Remove team from league."""
        pass


# Use Cases
class CreateLeagueUseCase:
    """Use case for creating a new league."""

    def __init__(self, league_repository: LeagueRepositoryInterface):
        self.league_repository = league_repository

    def execute(self, request: CreateLeagueRequest) -> LeagueDTO:
        """Create a new league."""
        # Validate league doesn't already exist
        existing = self.league_repository.get_by_name(request.name)
        if existing:
            raise ValueError(f"League with name '{request.name}' already exists")

        # Create domain entity
        league = LeagueEntity(
            name=request.name,
            max_teams=request.max_teams,
            budget_per_team=Money(request.budget_per_team)
        )

        # Save league
        created_league = self.league_repository.create(league)

        return LeagueDTO.from_entity(created_league)


class GetLeagueUseCase:
    """Use case for retrieving league information."""

    def __init__(self, league_repository: LeagueRepositoryInterface):
        self.league_repository = league_repository

    def execute(self, league_id: int) -> Optional[LeagueDTO]:
        """Get league by ID."""
        league = self.league_repository.get_by_id(league_id)
        return LeagueDTO.from_entity(league) if league else None


class ListLeaguesUseCase:
    """Use case for listing leagues."""

    def __init__(self, league_repository: LeagueRepositoryInterface):
        self.league_repository = league_repository

    def execute(self, request: ListLeaguesRequest) -> ListLeaguesResult:
        """List leagues based on criteria."""
        if request.available_only:
            leagues = self.league_repository.get_available_leagues()
        else:
            leagues = self.league_repository.get_all(
                active_only=request.active_only,
                limit=request.limit,
                offset=request.offset
            )

        # Convert to DTOs
        league_dtos = [LeagueDTO.from_entity(league) for league in leagues]

        return ListLeaguesResult(
            leagues=league_dtos,
            total_count=len(league_dtos),
            has_more=len(league_dtos) == request.limit
        )


class UpdateLeagueUseCase:
    """Use case for updating league information."""

    def __init__(self, league_repository: LeagueRepositoryInterface):
        self.league_repository = league_repository

    def execute(self, request: UpdateLeagueRequest) -> LeagueDTO:
        """Update league information."""
        league = self.league_repository.get_by_id(request.league_id)
        if not league:
            raise ValueError(f"League with ID {request.league_id} not found")

        # Update fields if provided
        if request.name:
            # Check if name is already taken by another league
            existing = self.league_repository.get_by_name(request.name)
            if existing and existing.id != league.id:
                raise ValueError(f"League name '{request.name}' already exists")
            league.name = request.name

        if request.max_teams:
            if request.max_teams < len(league.teams):
                raise ValueError(f"Cannot reduce max_teams below current team count ({len(league.teams)})")
            league.max_teams = request.max_teams

        if request.budget_per_team:
            league.budget_per_team = Money(request.budget_per_team)

        if request.is_active is not None:
            league.is_active = request.is_active

        # Save updated league
        updated_league = self.league_repository.update(league)

        return LeagueDTO.from_entity(updated_league)


class AddTeamToLeagueUseCase:
    """Use case for adding team to league."""

    def __init__(self, league_repository: LeagueRepositoryInterface, team_repository):
        self.league_repository = league_repository
        self.team_repository = team_repository

    def execute(self, request: AddTeamToLeagueRequest) -> LeagueDTO:
        """Add team to league."""
        league = self.league_repository.get_by_id(request.league_id)
        if not league:
            raise ValueError(f"League with ID {request.league_id} not found")

        team = self.team_repository.get_by_id(request.team_id)
        if not team:
            raise ValueError(f"Team with ID {request.team_id} not found")

        # Check if league has space
        if league.is_full():
            raise ValueError(f"League '{league.name}' is full")

        # Check if team is already in league
        if team in league.teams:
            raise ValueError(f"Team '{team.name.value}' is already in league '{league.name}'")

        # Add team to league
        success = self.league_repository.add_team_to_league(request.league_id, team)
        if not success:
            raise ValueError("Failed to add team to league")

        # Get updated league
        updated_league = self.league_repository.get_by_id(request.league_id)
        return LeagueDTO.from_entity(updated_league)


class RemoveTeamFromLeagueUseCase:
    """Use case for removing team from league."""

    def __init__(self, league_repository: LeagueRepositoryInterface):
        self.league_repository = league_repository

    def execute(self, league_id: int, team_id: int) -> LeagueDTO:
        """Remove team from league."""
        league = self.league_repository.get_by_id(league_id)
        if not league:
            raise ValueError(f"League with ID {league_id} not found")

        # Remove team from league
        success = self.league_repository.remove_team_from_league(league_id, team_id)
        if not success:
            raise ValueError("Failed to remove team from league")

        # Get updated league
        updated_league = self.league_repository.get_by_id(league_id)
        return LeagueDTO.from_entity(updated_league)


class GetLeagueStatsUseCase:
    """Use case for getting league statistics."""

    def __init__(self, league_repository: LeagueRepositoryInterface):
        self.league_repository = league_repository

    def execute(self, league_id: int) -> LeagueStatsDTO:
        """Get detailed league statistics."""
        league = self.league_repository.get_by_id(league_id)
        if not league:
            raise ValueError(f"League with ID {league_id} not found")

        return LeagueStatsDTO.create(league)


class GetAvailableLeaguesUseCase:
    """Use case for getting leagues with available spots."""

    def __init__(self, league_repository: LeagueRepositoryInterface):
        self.league_repository = league_repository

    def execute(self) -> List[LeagueDTO]:
        """Get all leagues that still have space for teams."""
        leagues = self.league_repository.get_available_leagues()
        return [LeagueDTO.from_entity(league) for league in leagues]
