from app.domain.models import Player, Team


def test_player_dataclass():
    p = Player(id=1, name="Rossi", role="FW", team_id=2, costo=10.0)
    assert p.name == "Rossi"
    assert p.costo == 10.0
