"""Team repository implementation.

Handles all database operations for Team model including league relationships
and team management features.
"""

from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc

from .base import BaseRepository
from app.models import Team, League, Player
import logging

logger = logging.getLogger(__name__)


class TeamRepository(BaseRepository[Team]):
    """Repository for Team model with league and player relationships."""

    def __init__(self, db_session: Session):
        """Initialize team repository.

        Args:
            db_session: SQLAlchemy database session
        """
        super().__init__(db_session, Team)

    def get_by_name(self, name: str) -> Optional[Team]:
        """Get team by name.

        Args:
            name: Team name to search for

        Returns:
            Team instance if found, None otherwise
        """
        return self.db.query(Team).filter(Team.name == name).first()

    def get_by_league(self, league_id: int) -> List[Team]:
        """Get all teams in a league.

        Args:
            league_id: League ID

        Returns:
            List of teams in the league
        """
        return self.db.query(Team).filter(Team.league_id == league_id).all()

    def get_with_players(self, team_id: int) -> Optional[Team]:
        """Get team with players eagerly loaded.

        Args:
            team_id: Team ID

        Returns:
            Team instance with players loaded, None if not found
        """
        return self.db.query(Team).options(
            joinedload(Team.players)
        ).filter(Team.id == team_id).first()

    def get_with_league(self, team_id: int) -> Optional[Team]:
        """Get team with league information eagerly loaded.

        Args:
            team_id: Team ID

        Returns:
            Team instance with league loaded, None if not found
        """
        return self.db.query(Team).options(
            joinedload(Team.league)
        ).filter(Team.id == team_id).first()

    def get_teams_by_cash_range(self, min_cash: float = None,
                               max_cash: float = None,
                               league_id: int = None) -> List[Team]:
        """Get teams by cash range.

        Args:
            min_cash: Minimum cash amount
            max_cash: Maximum cash amount
            league_id: League ID to filter by (optional)

        Returns:
            List of teams within cash range
        """
        query = self.db.query(Team)

        if league_id:
            query = query.filter(Team.league_id == league_id)

        if min_cash is not None:
            query = query.filter(Team.cash >= min_cash)

        if max_cash is not None:
            query = query.filter(Team.cash <= max_cash)

        return query.all()

    def get_richest_teams(self, league_id: int = None, limit: int = 10) -> List[Team]:
        """Get teams ordered by cash (richest first).

        Args:
            league_id: League ID to filter by (optional)
            limit: Maximum number of teams to return

        Returns:
            List of teams ordered by cash descending
        """
        query = self.db.query(Team)

        if league_id:
            query = query.filter(Team.league_id == league_id)

        return query.order_by(desc(Team.cash)).limit(limit).all()

    def create_team(self, name: str, league_id: int,
                   owner_name: str = None, cash: float = 500.0) -> Team:
        """Create a new team.

        Args:
            name: Team name
            league_id: League ID
            owner_name: Owner name (optional) - not currently used
            cash: Initial cash amount

        Returns:
            Created team instance
        """
        return self.create(
            name=name,
            league_id=league_id,
            cash=cash
            # owner_name not supported by Team model
        )

    def update_cash(self, team_id: int, amount: float) -> bool:
        """Update team's cash amount.

        Args:
            team_id: Team ID
            amount: New cash amount

        Returns:
            True if updated, False if team not found
        """
        team = self.get_by_id(team_id)
        if not team:
            return False

        old_cash = team.cash
        team.cash = amount
        self.db.commit()

        logger.info(f"Updated team {team.name} cash: {old_cash} -> {amount}")
        return True

    def add_cash(self, team_id: int, amount: float) -> bool:
        """Add cash to team.

        Args:
            team_id: Team ID
            amount: Amount to add (can be negative to subtract)

        Returns:
            True if updated, False if team not found
        """
        team = self.get_by_id(team_id)
        if not team:
            return False

        old_cash = team.cash
        team.cash = (team.cash or 0) + amount
        self.db.commit()

        logger.info(f"Updated team {team.name} cash: {old_cash} -> {team.cash} (change: {amount:+.2f})")
        return True

    def get_team_statistics(self, team_id: int) -> dict:
        """Get team statistics including player count and total value.

        Args:
            team_id: Team ID

        Returns:
            Dictionary with team statistics
        """
        team = self.get_with_players(team_id)
        if not team:
            return {}

        players = team.players
        total_players = len(players)
        total_value = sum(player.costo or 0 for player in players)

        # Count by position
        positions = {}
        for player in players:
            pos = player.role or 'Unknown'
            positions[pos] = positions.get(pos, 0) + 1

        return {
            'team_id': team_id,
            'team_name': team.name,
            'cash': team.cash,
            'total_players': total_players,
            'total_player_value': total_value,
            'total_investment': total_value,
            'remaining_budget': team.cash,
            'positions': positions,
            'players': [
                {
                    'id': p.id,
                    'name': p.name,
                    'role': p.role,
                    'cost': p.costo,
                    'real_team': p.squadra_reale
                }
                for p in players
            ]
        }

    def get_league_standings(self, league_id: int) -> List[dict]:
        """Get league standings based on team values and cash.

        Args:
            league_id: League ID

        Returns:
            List of team standings with statistics
        """
        teams = self.get_by_league(league_id)
        standings = []

        for team in teams:
            stats = self.get_team_statistics(team.id)
            standings.append(stats)

        # Sort by total investment (descending) then by cash (descending)
        standings.sort(key=lambda x: (x['total_investment'], x['cash']), reverse=True)

        # Add ranking
        for i, team_stats in enumerate(standings):
            team_stats['rank'] = i + 1

        return standings

    def search_teams(self, search_term: str, league_id: int = None) -> List[Team]:
        """Search teams by name or owner name.

        Args:
            search_term: Search term
            league_id: League ID to filter by (optional)

        Returns:
            List of teams matching search term
        """
        query = self.db.query(Team).filter(
            or_(
                Team.name.ilike(f"%{search_term}%"),
                Team.owner_name.ilike(f"%{search_term}%")
            )
        )

        if league_id:
            query = query.filter(Team.league_id == league_id)

        return query.all()

    def get_team_aliases(self, team_id: int) -> List[str]:
        """Get all aliases for a team.

        Args:
            team_id: Team ID

        Returns:
            List of team alias names
        """
        from app.models import TeamAlias

        aliases = self.db.query(TeamAlias).filter(TeamAlias.team_id == team_id).all()
        return [alias.alias for alias in aliases]

    def add_team_alias(self, team_id: int, alias: str) -> bool:
        """Add an alias for a team.

        Args:
            team_id: Team ID
            alias: Alias name

        Returns:
            True if added, False if team not found or alias exists
        """
        from app.models import TeamAlias

        team = self.get_by_id(team_id)
        if not team:
            return False

        # Check if alias already exists
        existing = self.db.query(TeamAlias).filter(
            TeamAlias.alias == alias
        ).first()

        if existing:
            return False  # Alias already exists

        team_alias = TeamAlias(team_id=team_id, alias=alias)
        self.db.add(team_alias)
        self.db.commit()

        logger.info(f"Added alias '{alias}' for team {team.name}")
        return True
