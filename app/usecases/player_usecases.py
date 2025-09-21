from typing import List

from app.domain.models import Player
from app.repositories.repository import PlayerRepository


class PlayerUseCases:
    def __init__(self, repo: PlayerRepository):
        self.repo = repo

    def list_players(self) -> List[Player]:
        return self.repo.list_all()

    def get_player(self, player_id: int) -> Player:
        return self.repo.get_by_id(player_id)
