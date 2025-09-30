"""Market-specific use cases for managing market operations and statistics."""

from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections import defaultdict

from app.domain.entities import PlayerEntity, TeamEntity
from app.domain.value_objects import Money, PlayerRole
from app.domain.services import MarketService


# DTOs for Market operations
@dataclass
class MarketStatsDTO:
    """Data Transfer Object for Market statistics."""
    total_players: int
    free_agents: int
    assigned_players: int
    total_market_value: float
    average_player_cost: float
    role_distribution: Dict[str, Dict[str, int]]

    @classmethod
    def from_market_stats(cls, stats: Dict[str, Any]) -> 'MarketStatsDTO':
        """Create DTO from market statistics dictionary."""
        return cls(
            total_players=stats['total_players'],
            free_agents=stats['free_agents'],
            assigned_players=stats['assigned_players'],
            total_market_value=stats['total_market_value'],
            average_player_cost=stats['average_player_cost'],
            role_distribution=stats['role_distribution']
        )


@dataclass
class PlayerMarketValueDTO:
    """Data Transfer Object for Player market value information."""
    player_id: int
    player_name: str
    role: str
    current_cost: float
    suggested_value: float
    is_undervalued: bool
    is_overvalued: bool
    value_difference: float

    @classmethod
    def create(cls, player: PlayerEntity, suggested_value: float) -> 'PlayerMarketValueDTO':
        """Create market value DTO from player and suggested value."""
        current = player.cost.amount
        difference = suggested_value - current

        return cls(
            player_id=player.id or 0,
            player_name=player.name,
            role=player.role.display_name(),
            current_cost=current,
            suggested_value=suggested_value,
            is_undervalued=difference > 0,
            is_overvalued=difference < 0,
            value_difference=difference
        )


@dataclass
class TransferOpportunityDTO:
    """Data Transfer Object for Transfer opportunity."""
    player_id: int
    player_name: str
    role: str
    current_cost: float
    selling_team: Optional[str]
    interested_teams: List[str]
    market_demand: str  # "high", "medium", "low"
    recommended_price: float

    @classmethod
    def create(cls, player: PlayerEntity, selling_team: Optional[TeamEntity],
               interested_teams: List[TeamEntity], recommended_price: float) -> 'TransferOpportunityDTO':
        """Create transfer opportunity DTO."""
        demand_level = "high" if len(interested_teams) >= 3 else "medium" if len(interested_teams) >= 2 else "low"

        return cls(
            player_id=player.id or 0,
            player_name=player.name,
            role=player.role.display_name(),
            current_cost=player.cost.amount,
            selling_team=selling_team.name.value if selling_team else None,
            interested_teams=[team.name.value for team in interested_teams],
            market_demand=demand_level,
            recommended_price=recommended_price
        )


@dataclass
class GetMarketStatsRequest:
    """Request for market statistics."""
    include_role_breakdown: bool = True
    include_value_analysis: bool = False


@dataclass
class SearchMarketRequest:
    """Request to search market for opportunities."""
    role: Optional[str] = None
    max_cost: Optional[float] = None
    min_cost: Optional[float] = None
    free_agents_only: bool = False
    undervalued_only: bool = False
    limit: int = 50


@dataclass
class SearchMarketResult:
    """Result of market search."""
    opportunities: List[PlayerMarketValueDTO]
    total_count: int
    filters_applied: Dict[str, Any]


@dataclass
class TransferAnalysisRequest:
    """Request for transfer analysis."""
    player_id: int
    potential_buyer_teams: Optional[List[int]] = None


# Repository interfaces (extending existing ones)
class MarketRepositoryInterface(ABC):
    """Interface for Market-specific repository operations."""

    @abstractmethod
    def get_all_players(self) -> List[PlayerEntity]:
        """Get all players in the market."""
        pass

    @abstractmethod
    def get_free_agents(self) -> List[PlayerEntity]:
        """Get all free agent players."""
        pass

    @abstractmethod
    def get_players_by_role(self, role: PlayerRole) -> List[PlayerEntity]:
        """Get players by role."""
        pass

    @abstractmethod
    def get_players_in_price_range(self, min_cost: Money, max_cost: Money) -> List[PlayerEntity]:
        """Get players within price range."""
        pass

    @abstractmethod
    def get_teams_with_budget(self, min_budget: Money) -> List[TeamEntity]:
        """Get teams with at least specified budget."""
        pass

    @abstractmethod
    def get_team_by_player(self, player_id: int) -> Optional[TeamEntity]:
        """Get team that owns a specific player."""
        pass


# Use Cases
class GetMarketStatsUseCase:
    """Use case for retrieving market statistics."""

    def __init__(self, market_repository: MarketRepositoryInterface):
        self.market_repository = market_repository

    def execute(self, request: GetMarketStatsRequest) -> MarketStatsDTO:
        """Get comprehensive market statistics."""
        all_players = self.market_repository.get_all_players()

        # Calculate statistics using domain service
        stats = MarketService.calculate_market_statistics(all_players)

        return MarketStatsDTO.from_market_stats(stats)


class SearchMarketUseCase:
    """Use case for searching market opportunities."""

    def __init__(self, market_repository: MarketRepositoryInterface):
        self.market_repository = market_repository

    def execute(self, request: SearchMarketRequest) -> SearchMarketResult:
        """Search for market opportunities based on criteria."""
        players = []

        # Apply filters
        if request.free_agents_only:
            players = self.market_repository.get_free_agents()
        elif request.role:
            role = PlayerRole.from_string(request.role)
            players = self.market_repository.get_players_by_role(role)
        elif request.min_cost is not None or request.max_cost is not None:
            min_money = Money(request.min_cost or 0)
            max_money = Money(request.max_cost or float('inf'))
            players = self.market_repository.get_players_in_price_range(min_money, max_money)
        else:
            players = self.market_repository.get_all_players()

        # Apply additional filters
        if request.max_cost is not None and not request.min_cost:
            players = [p for p in players if p.cost.amount <= request.max_cost]

        if request.min_cost is not None and not request.max_cost:
            players = [p for p in players if p.cost.amount >= request.min_cost]

        if request.free_agents_only and request.role is None:
            players = [p for p in players if p.is_free_agent()]

        # Calculate market values for filtering undervalued players
        opportunities = []
        for player in players[:request.limit]:
            # Simple market value calculation (could be enhanced)
            suggested_value = self._calculate_suggested_value(player)
            market_dto = PlayerMarketValueDTO.create(player, suggested_value)

            if request.undervalued_only and not market_dto.is_undervalued:
                continue

            opportunities.append(market_dto)

        return SearchMarketResult(
            opportunities=opportunities,
            total_count=len(opportunities),
            filters_applied={
                'role': request.role,
                'max_cost': request.max_cost,
                'min_cost': request.min_cost,
                'free_agents_only': request.free_agents_only,
                'undervalued_only': request.undervalued_only
            }
        )

    def _calculate_suggested_value(self, player: PlayerEntity) -> float:
        """Calculate suggested market value for a player."""
        # Simple calculation based on role and current market
        base_values = {
            PlayerRole.GOALKEEPER: 50.0,
            PlayerRole.DEFENDER: 75.0,
            PlayerRole.MIDFIELDER: 100.0,
            PlayerRole.FORWARD: 125.0
        }

        base = base_values.get(player.role, 75.0)

        # Add some variation (in real implementation, this would use more sophisticated logic)
        if player.is_free_agent():
            return base * 0.8  # Free agents slightly cheaper
        else:
            return base * 1.1  # Assigned players slightly more expensive


class AnalyzeTransferUseCase:
    """Use case for analyzing transfer opportunities."""

    def __init__(self, market_repository: MarketRepositoryInterface):
        self.market_repository = market_repository

    def execute(self, request: TransferAnalysisRequest) -> TransferOpportunityDTO:
        """Analyze transfer opportunity for a specific player."""
        # Get all players to find the target
        all_players = self.market_repository.get_all_players()
        target_player = next((p for p in all_players if p.id == request.player_id), None)

        if not target_player:
            raise ValueError(f"Player with ID {request.player_id} not found")

        # Get current team (if any)
        current_team = self.market_repository.get_team_by_player(request.player_id)

        # Find teams that can afford the player
        min_budget = Money(target_player.cost.amount * 1.1)  # 10% markup
        potential_buyers = self.market_repository.get_teams_with_budget(min_budget)

        # Filter out current team
        if current_team:
            potential_buyers = [team for team in potential_buyers if team.id != current_team.id]

        # Filter by specific teams if requested
        if request.potential_buyer_teams:
            potential_buyers = [
                team for team in potential_buyers
                if team.id in request.potential_buyer_teams
            ]

        # Calculate recommended price using domain service
        recommended_price = MarketService.calculate_transfer_price(target_player, potential_buyers)

        return TransferOpportunityDTO.create(
            target_player,
            current_team,
            potential_buyers,
            recommended_price
        )


class GetTopTransferTargetsUseCase:
    """Use case for getting top transfer targets."""

    def __init__(self, market_repository: MarketRepositoryInterface):
        self.market_repository = market_repository

    def execute(self, role: Optional[str] = None, limit: int = 10) -> List[TransferOpportunityDTO]:
        """Get top transfer targets."""
        # Get players based on role
        if role:
            player_role = PlayerRole.from_string(role)
            players = self.market_repository.get_players_by_role(player_role)
        else:
            players = self.market_repository.get_all_players()

        # Calculate transfer opportunities for each player
        opportunities = []
        for player in players:
            current_team = self.market_repository.get_team_by_player(player.id or 0)

            # Skip if player is free agent (not a transfer target)
            if player.is_free_agent():
                continue

            # Find potential buyers
            min_budget = Money(player.cost.amount * 1.1)
            potential_buyers = self.market_repository.get_teams_with_budget(min_budget)

            # Filter out current team
            if current_team:
                potential_buyers = [team for team in potential_buyers if team.id != current_team.id]

            # Only include if there are potential buyers
            if potential_buyers:
                recommended_price = MarketService.calculate_transfer_price(player, potential_buyers)
                opportunity = TransferOpportunityDTO.create(
                    player, current_team, potential_buyers, recommended_price
                )
                opportunities.append(opportunity)

        # Sort by market demand and recommended price
        opportunities.sort(key=lambda x: (len(x.interested_teams), x.recommended_price), reverse=True)

        return opportunities[:limit]


class GetMarketTrendsUseCase:
    """Use case for analyzing market trends."""

    def __init__(self, market_repository: MarketRepositoryInterface):
        self.market_repository = market_repository

    def execute(self) -> Dict[str, Any]:
        """Get market trends analysis."""
        all_players = self.market_repository.get_all_players()

        # Calculate trends by role
        role_trends = defaultdict(lambda: {'count': 0, 'total_value': 0.0, 'free_agents': 0})

        for player in all_players:
            role_key = player.role.display_name()
            role_trends[role_key]['count'] += 1
            role_trends[role_key]['total_value'] += player.cost.amount

            if player.is_free_agent():
                role_trends[role_key]['free_agents'] += 1

        # Calculate averages and availability
        trends = {}
        for role, data in role_trends.items():
            avg_cost = data['total_value'] / data['count'] if data['count'] > 0 else 0
            availability = (data['free_agents'] / data['count']) * 100 if data['count'] > 0 else 0

            trends[role] = {
                'total_players': data['count'],
                'average_cost': round(avg_cost, 2),
                'free_agents': data['free_agents'],
                'availability_percentage': round(availability, 1),
                'market_activity': 'high' if availability > 30 else 'medium' if availability > 15 else 'low'
            }

        return {
            'role_trends': trends,
            'total_market_size': len(all_players),
            'overall_availability': round((sum(p.is_free_agent() for p in all_players) / len(all_players)) * 100, 1),
            'total_market_value': sum(p.cost.amount for p in all_players)
        }
