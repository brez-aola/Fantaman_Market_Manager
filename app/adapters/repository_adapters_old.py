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
        return PlayerEntity(
            id=player_model.id,
            name=player_model.name,
            role=PlayerRole.from_string(player_model.role),
            cost=Money(float(player_model.costo)),
            team_id=player_model.squadra_id
        )

    @staticmethod
    def entity_to_player(entity: PlayerEntity, player_model):
        """Update ORM Player model from domain entity."""
        player_model.name = entity.name
        player_model.role = entity.role.value.value  # Get the string value
        player_model.costo = entity.cost.amount
        player_model.squadra_id = entity.team_id
        return player_model

    @staticmethod
    def team_to_entity(team_model) -> TeamEntity:
        """Convert ORM Team model to domain entity."""
        # Get team's players
        roster = []
        if hasattr(team_model, 'giocatori') and team_model.giocatori:
            roster = [DomainModelMapper.player_to_entity(player) for player in team_model.giocatori]

        return TeamEntity(
            id=team_model.id,
            name=TeamName(team_model.name),
            owner=team_model.owner or "",
            cash=Money(float(team_model.cash or 0)),
            roster=roster
        )

    @staticmethod
    def entity_to_team(entity: TeamEntity, team_model):
        """Update ORM Team model from domain entity."""
        team_model.name = entity.name.value
        team_model.owner = entity.owner
        team_model.cash = entity.cash.amount
        return team_model

    @staticmethod
    def user_to_entity(user_model) -> UserEntity:
        """Convert ORM User model to domain entity."""
        return UserEntity(
            id=user_model.id,
            username=Username(user_model.username),
            email=Email(user_model.email),
            password_hash=user_model.password_hash or "",
            is_active=getattr(user_model, 'is_active', True)
        )

    @staticmethod
    def entity_to_user(entity: UserEntity, user_model):
        """Update ORM User model from domain entity."""
        user_model.username = entity.username.value
        user_model.email = entity.email.value
        user_model.password_hash = entity.password_hash
        if hasattr(user_model, 'is_active'):
            user_model.is_active = entity.is_active
        return user_model

    @staticmethod
    def league_to_entity(league_model) -> LeagueEntity:
        """Convert ORM League model to domain entity."""
        # Get league's teams
        teams = []
        if hasattr(league_model, 'teams') and league_model.teams:
            teams = [DomainModelMapper.team_to_entity(team) for team in league_model.teams]

        return LeagueEntity(
            id=league_model.id,
            name=league_model.name,
            max_teams=getattr(league_model, 'max_teams', 8),
            budget_per_team=Money(float(getattr(league_model, 'budget_per_team', 1000))),
            teams=teams,
            is_active=getattr(league_model, 'is_active', True)
        )

    @staticmethod
    def entity_to_league(entity: LeagueEntity, league_model):
        """Update ORM League model from domain entity."""
        league_model.name = entity.name
        if hasattr(league_model, 'max_teams'):
            league_model.max_teams = entity.max_teams
        if hasattr(league_model, 'budget_per_team'):
            league_model.budget_per_team = entity.budget_per_team.amount
        if hasattr(league_model, 'is_active'):
            league_model.is_active = entity.is_active
        return league_model

    @staticmethod
    def team_to_entity(team: Team) -> TeamEntity:
        """Convert ORM Team to TeamEntity."""
        return TeamEntity(
            id=TeamId(team.id) if team.id else None,
            name=TeamName(team.name),
            cash=Money(float(team.cash) if team.cash else 0.0),
            league_id=LeagueId(team.league_id) if team.league_id else LeagueId(1),
            created_at=datetime.utcnow()  # Default since ORM model might not have this
        )

    @staticmethod
    def entity_to_team(entity: TeamEntity, existing_team: Optional[Team] = None) -> Team:
        """Convert TeamEntity to ORM Team."""
        team = existing_team or Team()

        if entity.id:
            team.id = entity.id.value
        team.name = entity.name.value
        team.cash = entity.cash.amount
        team.league_id = entity.league_id.value

        return team


class PlayerRepositoryAdapter(PlayerRepositoryInterface):
    """Adapter for PlayerRepository implementing domain interface."""

    def __init__(self, player_repo: PlayerRepository):
        self._repo = player_repo

    def get_by_id(self, player_id: int) -> Optional[PlayerEntity]:
        """Get player by ID as domain entity."""
        player = self._repo.get_by_id(player_id)
        if player:
            return DomainModelMapper.player_to_entity(player)
        return None

    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[PlayerEntity]:
        """Get all players as domain entities."""
        players = self._repo.get_all(limit=limit, offset=offset)
        return [DomainModelMapper.player_to_entity(p) for p in players]

    def search_players(self, **filters) -> List[PlayerEntity]:
        """Search players with filters."""
        # Convert domain filters to repository filters
        repo_filters = {}

        if 'name' in filters:
            repo_filters['name'] = filters['name']
        if 'role' in filters:
            repo_filters['role'] = filters['role']
        if 'real_team' in filters:
            repo_filters['real_team'] = filters['real_team']
        if 'min_cost' in filters:
            repo_filters['min_cost'] = filters['min_cost']
        if 'max_cost' in filters:
            repo_filters['max_cost'] = filters['max_cost']
        if 'free_agents_only' in filters and filters['free_agents_only']:
            # Get free agents
            players = self._repo.get_free_agents()
        else:
            # Use search functionality
            players = self._repo.search_players(
                name_query=repo_filters.get('name'),
                role=repo_filters.get('role'),
                real_team=repo_filters.get('real_team'),
                min_cost=repo_filters.get('min_cost'),
                max_cost=repo_filters.get('max_cost'),
                limit=filters.get('limit'),
                offset=filters.get('offset')
            )

        return [DomainModelMapper.player_to_entity(p) for p in players]

    def get_by_team_id(self, team_id: int) -> List[PlayerEntity]:
        """Get players by team ID."""
        players = self._repo.get_by_team_id(team_id)
        return [DomainModelMapper.player_to_entity(p) for p in players]

    def get_free_agents(self, role: Optional[str] = None) -> List[PlayerEntity]:
        """Get free agent players."""
        players = self._repo.get_free_agents(role=role)
        return [DomainModelMapper.player_to_entity(p) for p in players]

    def update(self, player: PlayerEntity) -> bool:
        """Update player entity."""
        try:
            # Get existing ORM model
            if player.id:
                existing = self._repo.get_by_id(player.id.value)
                if existing:
                    # Update existing model
                    updated_player = DomainModelMapper.entity_to_player(player, existing)
                    return self._repo.update_player(updated_player) is not None
            return False
        except Exception as e:
            return False


class TeamRepositoryAdapter(TeamRepositoryInterface):
    """Adapter for TeamRepository implementing domain interface."""

    def __init__(self, team_repo: TeamRepository):
        self._repo = team_repo

    def get_by_id(self, team_id: int) -> Optional[TeamEntity]:
        """Get team by ID as domain entity."""
        team = self._repo.get_by_id(team_id)
        if team:
            return DomainModelMapper.team_to_entity(team)
        return None

    def update(self, team: TeamEntity) -> bool:
        """Update team entity."""
        try:
            if team.id:
                existing = self._repo.get_by_id(team.id.value)
                if existing:
                    # Update cash specifically
                    return self._repo.update_cash(team.id.value, team.cash.amount)
            return False
        except Exception as e:
            return False


class IntegratedUseCase:
    """Base class for use cases with repository integration."""

    def __init__(self, db_session):
        """Initialize with database session and create adapted repositories."""
        from app.database import get_repositories

        # Get ORM repositories
        orm_repos = get_repositories(db_session)

        # Create adapted repositories implementing domain interfaces
        self.player_repo = PlayerRepositoryAdapter(orm_repos.players)
        self.team_repo = TeamRepositoryAdapter(orm_repos.teams)

        # Keep reference to session for transactions
        self.db_session = db_session
