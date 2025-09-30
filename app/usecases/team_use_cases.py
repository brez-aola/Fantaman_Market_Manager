"""Team-specific use cases for managing team operations."""

from typing import List, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.entities import TeamEntity, PlayerEntity
from app.domain.value_objects import Money, TeamName


# DTOs for Team operations
@dataclass
class TeamDTO:
    """Data Transfer Object for Team information."""
    id: Optional[int]
    name: str
    owner: str
    cash: float
    roster_size: int
    is_roster_valid: bool

    @classmethod
    def from_entity(cls, team: TeamEntity) -> 'TeamDTO':
        """Create DTO from domain entity."""
        return cls(
            id=team.id,
            name=team.name.value,
            owner=team.owner,
            cash=team.cash.amount,
            roster_size=len(team.roster),
            is_roster_valid=team.is_roster_valid()
        )


@dataclass
class TeamBudgetDTO:
    """Data Transfer Object for Team budget information."""
    team_id: int
    team_name: str
    current_cash: float
    can_afford: bool
    amount_requested: float
    remaining_after_purchase: float

    @classmethod
    def create(cls, team: TeamEntity, amount: Money) -> 'TeamBudgetDTO':
        """Create budget DTO from team and amount."""
        can_afford = team.can_afford(amount)
        remaining = team.cash.amount - amount.amount if can_afford else 0.0

        return cls(
            team_id=team.id or 0,
            team_name=team.name.value,
            current_cash=team.cash.amount,
            can_afford=can_afford,
            amount_requested=amount.amount,
            remaining_after_purchase=remaining
        )


@dataclass
class CreateTeamRequest:
    """Request to create a new team."""
    name: str
    owner: str
    initial_cash: float = 1000.0


@dataclass
class UpdateTeamBudgetRequest:
    """Request to update team budget."""
    team_id: int
    amount: float
    operation: str  # "add" or "subtract"


@dataclass
class GetTeamRequest:
    """Request to get team information."""
    team_id: Optional[int] = None
    team_name: Optional[str] = None


@dataclass
class ListTeamsRequest:
    """Request to list teams."""
    owner: Optional[str] = None
    min_cash: Optional[float] = None
    max_cash: Optional[float] = None
    limit: int = 50
    offset: int = 0


@dataclass
class ListTeamsResult:
    """Result of listing teams."""
    teams: List[TeamDTO]
    total_count: int
    has_more: bool


# Repository interfaces
class TeamRepositoryInterface(ABC):
    """Interface for Team repository operations."""

    @abstractmethod
    def get_by_id(self, team_id: int) -> Optional[TeamEntity]:
        """Get team by ID."""
        pass

    @abstractmethod
    def get_by_name(self, name: TeamName) -> Optional[TeamEntity]:
        """Get team by name."""
        pass

    @abstractmethod
    def create(self, team: TeamEntity) -> TeamEntity:
        """Create new team."""
        pass

    @abstractmethod
    def update(self, team: TeamEntity) -> TeamEntity:
        """Update existing team."""
        pass

    @abstractmethod
    def delete(self, team_id: int) -> bool:
        """Delete team by ID."""
        pass

    @abstractmethod
    def get_all(self, limit: int = 50, offset: int = 0) -> List[TeamEntity]:
        """Get all teams with pagination."""
        pass

    @abstractmethod
    def get_by_owner(self, owner: str) -> List[TeamEntity]:
        """Get teams by owner."""
        pass

    @abstractmethod
    def get_teams_with_budget_range(self, min_cash: Money, max_cash: Money) -> List[TeamEntity]:
        """Get teams within budget range."""
        pass


# Use Cases
class CreateTeamUseCase:
    """Use case for creating a new team."""

    def __init__(self, team_repository: TeamRepositoryInterface):
        self.team_repository = team_repository

    def execute(self, request: CreateTeamRequest) -> TeamDTO:
        """Create a new team."""
        # Create domain entity
        team = TeamEntity(
            name=TeamName(request.name),
            owner=request.owner,
            cash=Money(request.initial_cash)
        )

        # Validate team doesn't already exist
        existing = self.team_repository.get_by_name(team.name)
        if existing:
            raise ValueError(f"Team with name '{request.name}' already exists")

        # Save team
        created_team = self.team_repository.create(team)

        return TeamDTO.from_entity(created_team)


class GetTeamUseCase:
    """Use case for retrieving team information."""

    def __init__(self, team_repository: TeamRepositoryInterface):
        self.team_repository = team_repository

    def execute(self, request: GetTeamRequest) -> Optional[TeamDTO]:
        """Get team information."""
        team = None

        if request.team_id:
            team = self.team_repository.get_by_id(request.team_id)
        elif request.team_name:
            team = self.team_repository.get_by_name(TeamName(request.team_name))

        return TeamDTO.from_entity(team) if team else None


class ListTeamsUseCase:
    """Use case for listing teams."""

    def __init__(self, team_repository: TeamRepositoryInterface):
        self.team_repository = team_repository

    def execute(self, request: ListTeamsRequest) -> ListTeamsResult:
        """List teams based on criteria."""
        teams = []

        if request.owner:
            teams = self.team_repository.get_by_owner(request.owner)
        elif request.min_cash is not None and request.max_cash is not None:
            teams = self.team_repository.get_teams_with_budget_range(
                Money(request.min_cash),
                Money(request.max_cash)
            )
        else:
            teams = self.team_repository.get_all(request.limit, request.offset)

        # Apply additional filters
        filtered_teams = teams
        if request.min_cash is not None and not (request.max_cash is not None):
            filtered_teams = [t for t in teams if t.cash.amount >= request.min_cash]

        # Convert to DTOs
        team_dtos = [TeamDTO.from_entity(team) for team in filtered_teams]

        return ListTeamsResult(
            teams=team_dtos,
            total_count=len(team_dtos),
            has_more=len(team_dtos) == request.limit
        )


class UpdateTeamBudgetUseCase:
    """Use case for updating team budget."""

    def __init__(self, team_repository: TeamRepositoryInterface):
        self.team_repository = team_repository

    def execute(self, request: UpdateTeamBudgetRequest) -> TeamBudgetDTO:
        """Update team budget."""
        team = self.team_repository.get_by_id(request.team_id)
        if not team:
            raise ValueError(f"Team with ID {request.team_id} not found")

        amount = Money(abs(request.amount))  # Ensure positive amount

        if request.operation == "add":
            team.add_cash(amount)
        elif request.operation == "subtract":
            if not team.can_afford(amount):
                raise ValueError(f"Team cannot afford to subtract €{amount.amount}")
            team.spend_cash(amount)
        else:
            raise ValueError("Operation must be 'add' or 'subtract'")

        # Save updated team
        updated_team = self.team_repository.update(team)

        return TeamBudgetDTO.create(updated_team, amount)


class CheckTeamBudgetUseCase:
    """Use case for checking if team can afford a purchase."""

    def __init__(self, team_repository: TeamRepositoryInterface):
        self.team_repository = team_repository

    def execute(self, team_id: int, amount: float) -> TeamBudgetDTO:
        """Check if team can afford amount."""
        team = self.team_repository.get_by_id(team_id)
        if not team:
            raise ValueError(f"Team with ID {team_id} not found")

        money_amount = Money(amount)
        return TeamBudgetDTO.create(team, money_amount)
