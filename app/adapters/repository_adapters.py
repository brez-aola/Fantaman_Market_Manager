"""Repository adapters bridging domain and infrastructure layers.

These adapters implement domain repository interfaces using existing ORM-based repositories.
They handle the translation between domain entities and ORM models.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.database import get_repositories
from app.usecases.player_use_cases import PlayerRepositoryInterface, TeamRepositoryInterface
from app.usecases.user_use_cases import UserRepositoryInterface
from app.usecases.league_use_cases import LeagueRepositoryInterface
from app.usecases.market_use_cases import MarketRepositoryInterface
from app.domain.entities import PlayerEntity, TeamEntity, UserEntity, LeagueEntity
from app.domain.value_objects import Money, PlayerRole, TeamName, Email, Username


class DomainModelMapper:
    """Mapper for converting between ORM models and domain entities."""

    @staticmethod
    def player_to_entity(player_model) -> PlayerEntity:
        """Convert ORM Player model to domain entity."""
        from app.domain.entities import PlayerId, TeamId

        return PlayerEntity(
            id=PlayerId(player_model.id) if player_model.id else None,
            name=player_model.name,
            role=PlayerRole.from_string(player_model.role),
            cost=Money(float(player_model.costo)),
            real_team=getattr(player_model, 'squadra', ''),
            team_id=TeamId(player_model.team_id) if getattr(player_model, 'team_id', None) else None
        )

    @staticmethod
    def entity_to_player(entity: PlayerEntity, player_model):
        """Update ORM Player model from domain entity."""
        if entity.id:
            player_model.id = entity.id.value
        player_model.name = entity.name
        player_model.role = entity.role.value.value  # Get the string value
        player_model.costo = entity.cost.amount
        if hasattr(player_model, 'squadra'):
            player_model.squadra = entity.real_team
        if entity.team_id and hasattr(player_model, 'team_id'):
            player_model.team_id = entity.team_id.value
        return player_model

    @staticmethod
    def team_to_entity(team_model) -> TeamEntity:
        """Convert ORM Team model to domain entity."""
        from app.domain.entities import TeamId, LeagueId
        from datetime import datetime

        return TeamEntity(
            id=TeamId(team_model.id) if team_model.id else None,
            name=TeamName(team_model.name),
            cash=Money(float(team_model.cash or 0)),
            league_id=LeagueId(team_model.league_id) if team_model.league_id else LeagueId(1),
            created_at=datetime.now()
        )

    @staticmethod
    def entity_to_team(entity: TeamEntity, team_model):
        """Update ORM Team model from domain entity."""
        team_model.name = entity.name.value
        team_model.cash = entity.cash.amount
        if entity.league_id:
            team_model.league_id = entity.league_id.value
        return team_model
class PlayerRepositoryAdapter(PlayerRepositoryInterface):
    """Adapter implementing PlayerRepositoryInterface using ORM repositories."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.repos = get_repositories(db_session)

    def get_by_id(self, player_id: int) -> Optional[PlayerEntity]:
        """Get player by ID."""
        player = self.repos.players.get_by_id(player_id)
        return DomainModelMapper.player_to_entity(player) if player else None

    def get_all(self, limit: int = 50, offset: int = 0) -> List[PlayerEntity]:
        """Get all players."""
        # The ORM repository doesn't support offset, so we get all and slice
        players = self.repos.players.get_all(limit=limit + offset)
        if offset > 0:
            players = players[offset:]
        return [DomainModelMapper.player_to_entity(player) for player in players[:limit]]

    def get_by_team_id(self, team_id: int) -> List[PlayerEntity]:
        """Get players by team ID."""
        # Use existing get_by_team method if available
        if hasattr(self.repos.players, 'get_by_team'):
            players = self.repos.players.get_by_team(team_id)
            return [DomainModelMapper.player_to_entity(player) for player in players]
        else:
            # Fallback: filter all players by team_id
            all_players = self.repos.players.get_all()
            team_players = [p for p in all_players if getattr(p, 'team_id', None) == team_id]
            return [DomainModelMapper.player_to_entity(player) for player in team_players]

    def get_free_agents(self, role: Optional[str] = None) -> List[PlayerEntity]:
        """Get free agent players."""
        players = self.repos.players.get_free_agents()
        entities = [DomainModelMapper.player_to_entity(player) for player in players]

        # Filter by role if specified
        if role:
            role_obj = PlayerRole.from_string(role)
            entities = [p for p in entities if p.role == role_obj]

        return entities

    def search_players(self, name: str, role: Optional[str] = None, limit: int = 50) -> List[PlayerEntity]:
        """Search players by name and optionally by role."""
        players = self.repos.players.search_by_name(name, limit=limit)
        entities = [DomainModelMapper.player_to_entity(player) for player in players]

        # Filter by role if specified
        if role:
            role_obj = PlayerRole.from_string(role)
            entities = [p for p in entities if p.role == role_obj]

        return entities

    def get_by_role(self, role: PlayerRole, limit: int = 50) -> List[PlayerEntity]:
        """Get players by role."""
        players = self.repos.players.get_by_role(role.value.value, limit=limit)
        return [DomainModelMapper.player_to_entity(player) for player in players]

    def search_by_name(self, name: str, limit: int = 50) -> List[PlayerEntity]:
        """Search players by name."""
        players = self.repos.players.search_by_name(name, limit=limit)
        return [DomainModelMapper.player_to_entity(player) for player in players]

    def assign_to_team(self, player_id: int, team_id: int) -> bool:
        """Assign player to team."""
        return self.repos.players.assign_to_team(player_id, team_id)

    def release_from_team(self, player_id: int) -> bool:
        """Release player from team."""
        return self.repos.players.release_from_team(player_id)

    def update_cost(self, player_id: int, new_cost: Money) -> bool:
        """Update player cost."""
        return self.repos.players.update_cost(player_id, new_cost.amount)

    def update(self, player: PlayerEntity) -> bool:
        """Update player entity."""
        if not player.id:
            return False

        # Get existing player
        orm_player = self.repos.players.get_by_id(player.id)
        if not orm_player:
            return False

        # Update ORM model from entity
        DomainModelMapper.entity_to_player(player, orm_player)

        # Save changes (assuming the repository handles commit)
        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
class TeamRepositoryAdapter(TeamRepositoryInterface):
    """Adapter implementing TeamRepositoryInterface using ORM repositories."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.repos = get_repositories(db_session)

    def get_by_id(self, team_id: int) -> Optional[TeamEntity]:
        """Get team by ID."""
        team = self.repos.teams.get_by_id(team_id)
        return DomainModelMapper.team_to_entity(team) if team else None

    def get_by_name(self, name: TeamName) -> Optional[TeamEntity]:
        """Get team by name."""
        teams = self.repos.teams.get_all()
        for team in teams:
            if team.name == name.value:
                return DomainModelMapper.team_to_entity(team)
        return None

    def get_all(self, limit: int = 50, offset: int = 0) -> List[TeamEntity]:
        """Get all teams."""
        # The ORM repository doesn't support offset/limit, so we get all and slice
        teams = self.repos.teams.get_all()
        if offset > 0:
            teams = teams[offset:]
        return [DomainModelMapper.team_to_entity(team) for team in teams[:limit]]

    def create(self, team: TeamEntity) -> TeamEntity:
        """Create new team."""
        # Note: This would need implementation in the ORM repository
        raise NotImplementedError("Team creation not implemented in ORM repository yet")

    def update(self, team: TeamEntity) -> bool:
        """Update team entity."""
        if not team.id:
            return False

        # Get existing team
        orm_team = self.repos.teams.get_by_id(team.id)
        if not orm_team:
            return False

        # Update ORM model from entity
        DomainModelMapper.entity_to_team(team, orm_team)

        # Save changes (assuming the repository handles commit)
        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False

    def delete(self, team_id: int) -> bool:
        """Delete team."""
        # Note: This would need implementation in the ORM repository
        raise NotImplementedError("Team deletion not implemented in ORM repository yet")

    def get_by_owner(self, owner: str) -> List[TeamEntity]:
        """Get teams by owner."""
        teams = self.repos.teams.get_all()
        owner_teams = [team for team in teams if team.owner == owner]
        return [DomainModelMapper.team_to_entity(team) for team in owner_teams]

    def get_teams_with_budget_range(self, min_cash: Money, max_cash: Money) -> List[TeamEntity]:
        """Get teams within budget range."""
        teams = self.repos.teams.get_all()
        filtered_teams = [
            team for team in teams
            if min_cash.amount <= (team.cash or 0) <= max_cash.amount
        ]
        return [DomainModelMapper.team_to_entity(team) for team in filtered_teams]


class MarketRepositoryAdapter(MarketRepositoryInterface):
    """Adapter implementing MarketRepositoryInterface using existing repositories."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.repos = get_repositories(db_session)
        self.player_adapter = PlayerRepositoryAdapter(db_session)
        self.team_adapter = TeamRepositoryAdapter(db_session)

    def get_all_players(self) -> List[PlayerEntity]:
        """Get all players in the market."""
        return self.player_adapter.get_all()

    def get_free_agents(self) -> List[PlayerEntity]:
        """Get all free agent players."""
        return self.player_adapter.get_free_agents()

    def get_players_by_role(self, role: PlayerRole) -> List[PlayerEntity]:
        """Get players by role."""
        return self.player_adapter.get_by_role(role)

    def get_players_in_price_range(self, min_cost: Money, max_cost: Money) -> List[PlayerEntity]:
        """Get players within price range."""
        all_players = self.get_all_players()
        return [
            player for player in all_players
            if min_cost.amount <= player.cost.amount <= max_cost.amount
        ]

    def get_teams_with_budget(self, min_budget: Money) -> List[TeamEntity]:
        """Get teams with at least specified budget."""
        all_teams = self.team_adapter.get_all()
        return [team for team in all_teams if team.cash.amount >= min_budget.amount]

    def get_team_by_player(self, player_id: int) -> Optional[TeamEntity]:
        """Get team that owns a specific player."""
        player = self.player_adapter.get_by_id(player_id)
        if player and player.team_id:
            return self.team_adapter.get_by_id(player.team_id)
        return None


class IntegratedUseCase:
    """Integrated use case container providing all repository adapters."""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.player_repo = PlayerRepositoryAdapter(db_session)
        self.team_repo = TeamRepositoryAdapter(db_session)
        self.market_repo = MarketRepositoryAdapter(db_session)
