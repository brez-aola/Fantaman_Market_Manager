"""Player-related use cases."""

from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod

from app.domain.entities import PlayerEntity, TeamEntity, PlayerId, TeamId
from app.domain.value_objects import Money, PlayerRole
from app.domain.services import PlayerAssignmentService, MarketService


# Input/Output DTOs for Use Cases

@dataclass
class AssignPlayerRequest:
    """Request to assign a player to a team."""
    player_id: int
    team_id: int
    assigned_by_user_id: int


@dataclass
class AssignPlayerResponse:
    """Response from player assignment operation."""
    success: bool
    message: str
    player_id: Optional[int] = None
    team_id: Optional[int] = None


@dataclass
class SearchPlayersRequest:
    """Request to search for players."""
    name_query: Optional[str] = None
    role: Optional[str] = None
    real_team: Optional[str] = None
    min_cost: Optional[float] = None
    max_cost: Optional[float] = None
    free_agents_only: bool = False
    limit: int = 50
    offset: int = 0


@dataclass
class PlayerSummaryDTO:
    """Summary information about a player."""
    id: int
    name: str
    role: str
    cost: float
    real_team: Optional[str]
    team_id: Optional[int]
    team_name: Optional[str]
    is_free_agent: bool


@dataclass
class SearchPlayersResponse:
    """Response from player search operation."""
    players: List[PlayerSummaryDTO]
    total_count: int
    has_more: bool


# Repository Interfaces (to be implemented in infrastructure layer)

class PlayerRepositoryInterface(ABC):
    """Interface for player data access."""

    @abstractmethod
    def get_by_id(self, player_id: int) -> Optional[PlayerEntity]:
        pass

    @abstractmethod
    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[PlayerEntity]:
        pass

    @abstractmethod
    def search_players(self, **filters) -> List[PlayerEntity]:
        pass

    @abstractmethod
    def get_by_team_id(self, team_id: int) -> List[PlayerEntity]:
        pass

    @abstractmethod
    def get_free_agents(self, role: Optional[str] = None) -> List[PlayerEntity]:
        pass

    @abstractmethod
    def update(self, player: PlayerEntity) -> bool:
        pass


class TeamRepositoryInterface(ABC):
    """Interface for team data access."""

    @abstractmethod
    def get_by_id(self, team_id: int) -> Optional[TeamEntity]:
        pass

    @abstractmethod
    def update(self, team: TeamEntity) -> bool:
        pass


# Use Cases Implementation

class AssignPlayerUseCase:
    """Use case for assigning a player to a team."""

    def __init__(self, player_repo: PlayerRepositoryInterface, team_repo: TeamRepositoryInterface):
        self._player_repo = player_repo
        self._team_repo = team_repo

    def execute(self, request: AssignPlayerRequest) -> AssignPlayerResponse:
        """Execute player assignment."""

        try:
            # Get player
            player = self._player_repo.get_by_id(request.player_id)
            if not player:
                return AssignPlayerResponse(
                    success=False,
                    message=f"Player with ID {request.player_id} not found"
                )

            # Get team
            team = self._team_repo.get_by_id(request.team_id)
            if not team:
                return AssignPlayerResponse(
                    success=False,
                    message=f"Team with ID {request.team_id} not found"
                )

            # Get current team players for validation
            current_team_players = self._player_repo.get_by_team_id(request.team_id)

            # Use domain service to assign player
            success, message = PlayerAssignmentService.assign_player_to_team(
                player, team, current_team_players
            )

            if success:
                # Persist changes
                self._player_repo.update(player)
                self._team_repo.update(team)

                return AssignPlayerResponse(
                    success=True,
                    message=message,
                    player_id=request.player_id,
                    team_id=request.team_id
                )
            else:
                return AssignPlayerResponse(success=False, message=message)

        except Exception as e:
            return AssignPlayerResponse(
                success=False,
                message=f"Error assigning player: {str(e)}"
            )


class ReleasePlayerUseCase:
    """Use case for releasing a player from their team."""

    def __init__(self, player_repo: PlayerRepositoryInterface, team_repo: TeamRepositoryInterface):
        self._player_repo = player_repo
        self._team_repo = team_repo

    def execute(self, player_id: int, released_by_user_id: int) -> AssignPlayerResponse:
        """Execute player release."""

        try:
            # Get player
            player = self._player_repo.get_by_id(player_id)
            if not player:
                return AssignPlayerResponse(
                    success=False,
                    message=f"Player with ID {player_id} not found"
                )

            if player.is_free_agent():
                return AssignPlayerResponse(
                    success=False,
                    message=f"Player {player.name} is already a free agent"
                )

            # Get team
            team = self._team_repo.get_by_id(player.team_id.value)
            if not team:
                return AssignPlayerResponse(
                    success=False,
                    message=f"Team with ID {player.team_id} not found"
                )

            # Use domain service to release player
            success, message = PlayerAssignmentService.release_player_from_team(player, team)

            if success:
                # Persist changes
                self._player_repo.update(player)
                self._team_repo.update(team)

                return AssignPlayerResponse(
                    success=True,
                    message=message,
                    player_id=player_id
                )
            else:
                return AssignPlayerResponse(success=False, message=message)

        except Exception as e:
            return AssignPlayerResponse(
                success=False,
                message=f"Error releasing player: {str(e)}"
            )


class TransferPlayerUseCase:
    """Use case for transferring a player between teams."""

    def __init__(self, player_repo: PlayerRepositoryInterface, team_repo: TeamRepositoryInterface):
        self._player_repo = player_repo
        self._team_repo = team_repo

    def execute(self, player_id: int, from_team_id: int, to_team_id: int,
               transferred_by_user_id: int) -> AssignPlayerResponse:
        """Execute player transfer."""

        try:
            # Get entities
            player = self._player_repo.get_by_id(player_id)
            if not player:
                return AssignPlayerResponse(
                    success=False,
                    message=f"Player with ID {player_id} not found"
                )

            from_team = self._team_repo.get_by_id(from_team_id)
            to_team = self._team_repo.get_by_id(to_team_id)

            if not from_team or not to_team:
                return AssignPlayerResponse(
                    success=False,
                    message="One or both teams not found"
                )

            # Get team rosters
            from_team_players = self._player_repo.get_by_team_id(from_team_id)
            to_team_players = self._player_repo.get_by_team_id(to_team_id)

            # Use domain service for transfer
            success, message = PlayerAssignmentService.transfer_player(
                player, from_team, to_team, from_team_players, to_team_players
            )

            if success:
                # Persist changes
                self._player_repo.update(player)
                self._team_repo.update(from_team)
                self._team_repo.update(to_team)

                return AssignPlayerResponse(
                    success=True,
                    message=message,
                    player_id=player_id,
                    team_id=to_team_id
                )
            else:
                return AssignPlayerResponse(success=False, message=message)

        except Exception as e:
            return AssignPlayerResponse(
                success=False,
                message=f"Error transferring player: {str(e)}"
            )


class SearchPlayersUseCase:
    """Use case for searching players with filters."""

    def __init__(self, player_repo: PlayerRepositoryInterface):
        self._player_repo = player_repo

    def execute(self, request: SearchPlayersRequest) -> SearchPlayersResponse:
        """Execute player search."""

        try:
            # Build search filters
            filters = {}
            if request.name_query:
                filters['name'] = request.name_query
            if request.role:
                filters['role'] = request.role
            if request.real_team:
                filters['real_team'] = request.real_team
            if request.min_cost is not None:
                filters['min_cost'] = request.min_cost
            if request.max_cost is not None:
                filters['max_cost'] = request.max_cost
            if request.free_agents_only:
                filters['free_agents_only'] = True

            # Search players
            players = self._player_repo.search_players(
                limit=request.limit + 1,  # Get one extra to check if there are more
                offset=request.offset,
                **filters
            )

            # Check if there are more results
            has_more = len(players) > request.limit
            if has_more:
                players = players[:request.limit]

            # Convert to DTOs
            player_dtos = []
            for player in players:
                dto = PlayerSummaryDTO(
                    id=player.id.value if player.id else 0,
                    name=player.name,
                    role=player.role.display_name(),
                    cost=player.cost.amount,
                    real_team=player.real_team,
                    team_id=player.team_id.value if player.team_id else None,
                    team_name=None,  # Would need team repository to populate
                    is_free_agent=player.is_free_agent()
                )
                player_dtos.append(dto)

            return SearchPlayersResponse(
                players=player_dtos,
                total_count=len(player_dtos),
                has_more=has_more
            )

        except Exception as e:
            return SearchPlayersResponse(
                players=[],
                total_count=0,
                has_more=False
            )


class GetPlayerDetailsUseCase:
    """Use case for getting detailed player information."""

    def __init__(self, player_repo: PlayerRepositoryInterface, team_repo: TeamRepositoryInterface):
        self._player_repo = player_repo
        self._team_repo = team_repo

    def execute(self, player_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed player information."""

        try:
            player = self._player_repo.get_by_id(player_id)
            if not player:
                return None

            # Get team information if player is assigned
            team_info = None
            if player.team_id:
                team = self._team_repo.get_by_id(player.team_id.value)
                if team:
                    team_info = {
                        'id': team.id.value,
                        'name': team.name.value,
                        'cash': team.cash.amount
                    }

            return {
                'id': player.id.value if player.id else None,
                'name': player.name,
                'role': {
                    'code': player.role.value.value,
                    'display_name': player.role.display_name()
                },
                'cost': {
                    'amount': player.cost.amount,
                    'currency': player.cost.currency
                },
                'real_team': player.real_team,
                'contract_years': player.contract_years,
                'option': player.option,
                'is_free_agent': player.is_free_agent(),
                'team': team_info
            }

        except Exception as e:
            return None


class GetFreeAgentsUseCase:
    """Use case for getting all free agent players."""

    def __init__(self, player_repo: PlayerRepositoryInterface):
        self._player_repo = player_repo

    def execute(self, role: Optional[str] = None) -> List[PlayerSummaryDTO]:
        """Get all free agent players, optionally filtered by role."""

        try:
            free_agents = self._player_repo.get_free_agents(role=role)

            # Convert to DTOs
            return [
                PlayerSummaryDTO(
                    id=player.id.value if player.id else 0,
                    name=player.name,
                    role=player.role.display_name(),
                    cost=player.cost.amount,
                    real_team=player.real_team,
                    team_id=None,
                    team_name=None,
                    is_free_agent=True
                )
                for player in free_agents
            ]

        except Exception as e:
            return []
