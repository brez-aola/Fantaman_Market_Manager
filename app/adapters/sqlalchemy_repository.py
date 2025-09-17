from typing import List
from app.repositories.repository import PlayerRepository, TeamRepository
from app.domain.models import Player, Team

# skeleton adapter — inject SQLAlchemy session in constructor
class SQLAlchemyPlayerRepository(PlayerRepository):
    def __init__(self, session):
        self.session = session

    def list_all(self) -> List[Player]:
        # TODO: map ORM models -> domain Player
        raise NotImplementedError

    def get_by_id(self, player_id: int) -> Player:
        # TODO: query ORM and return domain Player
        raise NotImplementedError

    def save(self, player: Player) -> Player:
        # TODO: persist domain -> ORM
        raise NotImplementedError

class SQLAlchemyTeamRepository(TeamRepository):
    def __init__(self, session):
        self.session = session

    def list_all(self) -> List[Team]:
        raise NotImplementedError

    def get_by_id(self, team_id: int) -> Team:
        raise NotImplementedError
