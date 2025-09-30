"""League repository implementation.

Handles all database operations for League model including team relationships
and league management features.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import League, Player, Team

from .base import BaseRepository

logger = logging.getLogger(__name__)


class LeagueRepository(BaseRepository[League]):
    """Repository for League model with team and player relationships."""

    def __init__(self, db_session: Session):
        """Initialize league repository.

        Args:
            db_session: SQLAlchemy database session
        """
        super().__init__(db_session, League)

    def get_by_name(self, name: str) -> Optional[League]:
        """Get league by name.

        Args:
            name: League name to search for

        Returns:
            League instance if found, None otherwise
        """
        return self.db.query(League).filter(League.name == name).first()

    def get_by_slug(self, slug: str) -> Optional[League]:
        """Get league by slug.

        Args:
            slug: League slug to search for

        Returns:
            League instance if found, None otherwise
        """
        return self.db.query(League).filter(League.slug == slug).first()

    def get_with_teams(self, league_id: int) -> Optional[League]:
        """Get league with teams eagerly loaded.

        Args:
            league_id: League ID

        Returns:
            League instance with teams loaded, None if not found
        """
        return (
            self.db.query(League)
            .options(joinedload(League.teams))
            .filter(League.id == league_id)
            .first()
        )

    def get_active_leagues(self) -> List[League]:
        """Get all active leagues.

        Returns:
            List of active leagues
        """
        return self.db.query(League).filter(League.is_active.is_(True)).all()

    def create_league(
        self,
        name: str,
        slug: str = None,
        description: str = None,
        max_teams: int = 8,
        is_active: bool = True,
    ) -> League:
        """Create a new league.

        Args:
            name: League name
            slug: League slug (optional, will be generated from name)
            description: League description
            max_teams: Maximum number of teams allowed
            is_active: Whether league is active

        Returns:
            Created league instance
        """
        if not slug:
            # Generate slug from name
            slug = name.lower().replace(" ", "-").replace("_", "-")
            # Remove special characters
            slug = "".join(c for c in slug if c.isalnum() or c == "-")

        return self.create(
            name=name,
            slug=slug,
            description=description,
            max_teams=max_teams,
            is_active=is_active,
        )

    def get_league_statistics(self, league_id: int) -> Dict[str, Any]:
        """Get comprehensive league statistics.

        Args:
            league_id: League ID

        Returns:
            Dictionary with league statistics
        """
        league = self.get_by_id(league_id)
        if not league:
            raise ValueError(f"League with id {league_id} not found")

        # Get teams in league
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        current_teams = len(teams)

        # Calculate total players and cash
        total_players = (
            self.db.query(Player).join(Team).filter(Team.league_id == league_id).count()
        )

        total_cash = (
            self.db.query(func.sum(Team.cash))
            .filter(Team.league_id == league_id)
            .scalar()
            or 0
        )

        return {
            "id": league.id,
            "name": league.name,
            "slug": league.slug,
            "current_teams": current_teams,
            "max_teams": 8,  # Default max teams
            "total_players": total_players,
            "total_cash": float(total_cash),
        }

    def get_league_standings(self, league_id: int) -> List[Dict[str, Any]]:
        """Get league standings based on team performance.

        Args:
            league_id: League ID

        Returns:
            List of teams with standings information
        """
        teams = self.db.query(Team).filter(Team.league_id == league_id).all()
        standings = []

        for team in teams:
            # Calculate team value
            team_value = (
                self.db.query(func.sum(Player.costo))
                .filter(Player.team_id == team.id)
                .scalar()
                or 0
            )

            # Count players
            player_count = (
                self.db.query(Player).filter(Player.team_id == team.id).count()
            )

            # Count by role
            role_counts = (
                self.db.query(Player.role, func.count(Player.id).label("count"))
                .filter(Player.team_id == team.id)
                .group_by(Player.role)
                .all()
            )

            role_distribution = {role: count for role, count in role_counts}

            standings.append(
                {
                    "team_id": team.id,
                    "team_name": team.name,
                    "owner_name": team.owner_name,
                    "cash": float(team.cash or 0),
                    "team_value": float(team_value),
                    "total_investment": float(team_value),
                    "player_count": player_count,
                    "role_distribution": role_distribution,
                }
            )

        # Sort by total investment (descending) then by cash (descending)
        standings.sort(key=lambda x: (x["total_investment"], x["cash"]), reverse=True)

        # Add ranking
        for i, team_stats in enumerate(standings):
            team_stats["rank"] = i + 1

        return standings

    def add_team_to_league(
        self, league_id: int, team_name: str, owner_name: str = None
    ) -> Optional[Team]:
        """Add a team to the league.

        Args:
            league_id: League ID
            team_name: Team name
            owner_name: Owner name

        Returns:
            Created team instance if successful, None if league is full
        """
        league = self.get_by_id(league_id)
        if not league:
            return None

        # Check if league has space
        current_teams = self.db.query(Team).filter(Team.league_id == league_id).count()
        if current_teams >= league.max_teams:
            logger.warning(
                f"League {league.name} is full ({current_teams}/{league.max_teams})"
            )
            return None

        # Create team
        from .team_repository import TeamRepository

        team_repo = TeamRepository(self.db)
        team = team_repo.create_team(
            name=team_name,
            league_id=league_id,
            owner_name=owner_name,
            cash=500.0,  # Default starting cash
        )

        logger.info(f"Added team {team_name} to league {league.name}")
        return team

    def remove_team_from_league(self, league_id: int, team_id: int) -> bool:
        """Remove a team from the league.

        Args:
            league_id: League ID
            team_id: Team ID

        Returns:
            True if removed, False if team not found or not in league
        """
        team = (
            self.db.query(Team)
            .filter(Team.id == team_id, Team.league_id == league_id)
            .first()
        )

        if not team:
            return False

        # Release all players from the team
        self.db.query(Player).filter(Player.team_id == team_id).update(
            {"team_id": None}
        )

        # Delete team
        self.db.delete(team)
        self.db.commit()

        logger.info(f"Removed team {team.name} from league")
        return True

    def get_free_agents_in_league(
        self, league_id: int, role: str = None
    ) -> List[Player]:
        """Get free agents available for teams in the league.

        Note: This returns all free agents regardless of league,
        as free agents don't belong to any specific league.

        Args:
            league_id: League ID (for context)
            role: Player role to filter by (optional)

        Returns:
            List of free agent players
        """
        query = self.db.query(Player).filter(Player.team_id.is_(None))

        if role:
            query = query.filter(Player.role == role)

        return query.all()

    def search_leagues(
        self, search_term: str, active_only: bool = True
    ) -> List[League]:
        """Search leagues by name or description.

        Args:
            search_term: Search term
            active_only: Whether to include only active leagues

        Returns:
            List of leagues matching search term
        """
        from sqlalchemy import or_

        query = self.db.query(League).filter(
            or_(
                League.name.ilike(f"%{search_term}%"),
                League.description.ilike(f"%{search_term}%"),
            )
        )

        if active_only:
            query = query.filter(League.is_active.is_(True))

        return query.all()

    def activate_league(self, league_id: int) -> bool:
        """Activate a league.

        Args:
            league_id: League ID

        Returns:
            True if activated, False if league not found
        """
        league = self.get_by_id(league_id)
        if not league:
            return False

        league.is_active = True
        self.db.commit()

        logger.info(f"Activated league {league.name}")
        return True

    def deactivate_league(self, league_id: int) -> bool:
        """Deactivate a league.

        Args:
            league_id: League ID

        Returns:
            True if deactivated, False if league not found
        """
        league = self.get_by_id(league_id)
        if not league:
            return False

        league.is_active = False
        self.db.commit()

        logger.info(f"Deactivated league {league.name}")
        return True
