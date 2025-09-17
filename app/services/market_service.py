from app.usecases.player_usecases import PlayerUseCases
from app.repositories.repository import PlayerRepository

class MarketService:
    def __init__(self, player_repo: PlayerRepository):
        self.player_uc = PlayerUseCases(player_repo)

    def list_market_players(self):
        return self.player_uc.list_players()

    # add business methods here (assign player, refund, pricing rules)
