"""Player repository implementation.

Handles all database operations for Player model including team relationships
and player market features.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func

from .base import BaseRepository
from app.models import Player, Team
import logging

logger = logging.getLogger(__name__)


class PlayerRepository(BaseRepository[Player]):
    """Repository for Player model with team and market relationships."""

    def __init__(self, db_session: Session):
        """Initialize player repository.

        Args:
            db_session: SQLAlchemy database session
        """
        super().__init__(db_session, Player)

    def get_by_name(self, name: str) -> Optional[Player]:
        """Get player by name.

        Args:
            name: Player name to search for

        Returns:
            Player instance if found, None otherwise
        """
        return self.db.query(Player).filter(Player.name == name).first()

    def get_by_team(self, team_id: int) -> List[Player]:
        """Get all players in a team.

        Args:
            team_id: Team ID

        Returns:
            List of players in the team
        """
        return self.db.query(Player).filter(Player.team_id == team_id).all()

    def get_by_real_team(self, squadra_reale: str) -> List[Player]:
        """Get all players from a real team.

        Args:
            squadra_reale: Real team name (Serie A team)

        Returns:
            List of players from the real team
        """
        return self.db.query(Player).filter(Player.squadra_reale == squadra_reale).all()

    def get_by_role(self, role: str, team_id: int = None) -> List[Player]:
        """Get players by role.

        Args:
            role: Player role (P, D, C, A)
            team_id: Team ID to filter by (optional)

        Returns:
            List of players with the specified role
        """
        query = self.db.query(Player).filter(Player.role == role)

        if team_id:
            query = query.filter(Player.team_id == team_id)

        return query.all()

    def get_free_agents(self) -> List[Player]:
        """Get all free agents (players without a team).

        Returns:
            List of free agent players
        """
        return self.db.query(Player).filter(Player.team_id.is_(None)).all()

    def get_with_team(self, player_id: int) -> Optional[Player]:
        """Get player with team information eagerly loaded.

        Args:
            player_id: Player ID

        Returns:
            Player instance with team loaded, None if not found
        """
        return self.db.query(Player).options(
            joinedload(Player.team)
        ).filter(Player.id == player_id).first()

    def get_players_by_cost_range(self, min_cost: float = None,
                                 max_cost: float = None,
                                 role: str = None) -> List[Player]:
        """Get players by cost range.

        Args:
            min_cost: Minimum cost
            max_cost: Maximum cost
            role: Player role to filter by (optional)

        Returns:
            List of players within cost range
        """
        query = self.db.query(Player)

        if role:
            query = query.filter(Player.role == role)

        if min_cost is not None:
            query = query.filter(Player.costo >= min_cost)

        if max_cost is not None:
            query = query.filter(Player.costo <= max_cost)

        return query.all()

    def get_most_expensive_players(self, role: str = None, limit: int = 10) -> List[Player]:
        """Get most expensive players.

        Args:
            role: Player role to filter by (optional)
            limit: Maximum number of players to return

        Returns:
            List of players ordered by cost descending
        """
        query = self.db.query(Player).filter(Player.costo.isnot(None))

        if role:
            query = query.filter(Player.role == role)

        return query.order_by(desc(Player.costo)).limit(limit).all()

    def get_injured_players(self, team_id: int = None) -> List[Player]:
        """Get injured players.

        Args:
            team_id: Team ID to filter by (optional)

        Returns:
            List of injured players
        """
        query = self.db.query(Player).filter(Player.is_injured == True)

        if team_id:
            query = query.filter(Player.team_id == team_id)

        return query.all()

    def create_player(self, name: str, role: str = None,
                     squadra_reale: str = None, costo: float = None,
                     team_id: int = None, is_injured: bool = False) -> Player:
        """Create a new player.

        Args:
            name: Player name
            role: Player role (P, D, C, A)
            squadra_reale: Real team name
            costo: Player cost
            team_id: Fantasy team ID (optional)
            is_injured: Whether player is injured

        Returns:
            Created player instance
        """
        return self.create(
            name=name,
            role=role,
            squadra_reale=squadra_reale,
            costo=costo,
            team_id=team_id,
            is_injured=is_injured
        )

    def assign_to_team(self, player_id: int, team_id: int) -> bool:
        """Assign player to a team.

        Args:
            player_id: Player ID
            team_id: Team ID

        Returns:
            True if assigned, False if player not found
        """
        player = self.get_by_id(player_id)
        if not player:
            return False

        old_team_id = player.team_id
        player.team_id = team_id
        self.db.commit()

        logger.info(f"Assigned player {player.name} from team {old_team_id} to team {team_id}")
        return True

    def release_from_team(self, player_id: int) -> bool:
        """Release player from team (make free agent).

        Args:
            player_id: Player ID

        Returns:
            True if released, False if player not found
        """
        player = self.get_by_id(player_id)
        if not player:
            return False

        old_team_id = player.team_id
        player.team_id = None
        self.db.commit()

        logger.info(f"Released player {player.name} from team {old_team_id}")
        return True

    def update_injury_status(self, player_id: int, is_injured: bool) -> bool:
        """Update player injury status.

        Args:
            player_id: Player ID
            is_injured: Whether player is injured

        Returns:
            True if updated, False if player not found
        """
        player = self.get_by_id(player_id)
        if not player:
            return False

        player.is_injured = is_injured
        self.db.commit()

        status = "injured" if is_injured else "recovered"
        logger.info(f"Updated player {player.name} injury status: {status}")
        return True

    def search_players(self, search_term: str, role: str = None,
                      team_id: int = None, available_only: bool = False) -> List[Player]:
        """Search players by name or real team.

        Args:
            search_term: Search term
            role: Player role to filter by (optional)
            team_id: Team ID to filter by (optional)
            available_only: Whether to include only free agents

        Returns:
            List of players matching search criteria
        """
        query = self.db.query(Player).filter(
            or_(
                Player.name.ilike(f"%{search_term}%"),
                Player.squadra_reale.ilike(f"%{search_term}%")
            )
        )

        if role:
            query = query.filter(Player.role == role)

        if team_id:
            query = query.filter(Player.team_id == team_id)

        if available_only:
            query = query.filter(Player.team_id.is_(None))

        return query.all()

    def get_market_statistics(self) -> Dict[str, Any]:
        """Get market statistics for all players.

        Returns:
            Dictionary with market statistics
        """
        # Total players by status
        total_players = self.count()
        assigned_players = self.count(team_id__isnot=None)
        free_agents = total_players - assigned_players

        # Players by role
        roles = ['P', 'D', 'C', 'A']
        role_stats = {}
        for role in roles:
            total = self.count(role=role)
            assigned = self.db.query(Player).filter(
                and_(Player.role == role, Player.team_id.isnot(None))
            ).count()
            role_stats[role] = {
                'total': total,
                'assigned': assigned,
                'available': total - assigned
            }

        # Cost statistics
        cost_stats = self.db.query(
            func.avg(Player.costo).label('avg_cost'),
            func.min(Player.costo).label('min_cost'),
            func.max(Player.costo).label('max_cost')
        ).filter(Player.costo.isnot(None)).first()

        return {
            'total_players': total_players,
            'assigned_players': assigned_players,
            'free_agents': free_agents,
            'role_distribution': role_stats,
            'cost_statistics': {
                'average': float(cost_stats.avg_cost or 0),
                'minimum': float(cost_stats.min_cost or 0),
                'maximum': float(cost_stats.max_cost or 0)
            },
            'injured_players': self.count(is_injured=True)
        }

    def get_team_composition(self, team_id: int) -> Dict[str, Any]:
        """Get team composition by role.

        Args:
            team_id: Team ID

        Returns:
            Dictionary with team composition statistics
        """
        players = self.get_by_team(team_id)

        composition = {
            'P': [],  # Portieri
            'D': [],  # Difensori
            'C': [],  # Centrocampisti
            'A': []   # Attaccanti
        }

        total_cost = 0
        injured_count = 0

        for player in players:
            role = player.role or 'Unknown'
            if role in composition:
                composition[role].append({
                    'id': player.id,
                    'name': player.name,
                    'real_team': player.squadra_reale,
                    'cost': player.costo or 0,
                    'is_injured': player.is_injured or False
                })

            total_cost += player.costo or 0
            if player.is_injured:
                injured_count += 1

        return {
            'team_id': team_id,
            'total_players': len(players),
            'total_cost': total_cost,
            'injured_players': injured_count,
            'composition': {
                'goalkeepers': len(composition['P']),
                'defenders': len(composition['D']),
                'midfielders': len(composition['C']),
                'forwards': len(composition['A'])
            },
            'players_by_role': composition
        }
