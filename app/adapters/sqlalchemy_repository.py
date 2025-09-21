from typing import List, Optional

from sqlalchemy.orm import Session

from app.domain.models import Player as DomainPlayer
from app.domain.models import Team as DomainTeam
from app.models import Player as ORMPlayer
from app.models import Team as ORMTeam
from app.repositories.repository import PlayerRepository, TeamRepository


def _map_player(orm: ORMPlayer) -> DomainPlayer:
    return DomainPlayer(
        id=orm.id,
        name=orm.name,
        role=orm.role or "",
        team_id=orm.team_id,
        costo=float(orm.costo) if orm.costo is not None else None,
        anni_contratto=orm.anni_contratto,
        opzione=orm.opzione,
        squadra_reale=orm.squadra_reale,
        is_injured=bool(orm.is_injured),
    )


def _map_team(orm: ORMTeam) -> DomainTeam:
    domain_team = DomainTeam(id=orm.id, name=orm.name)
    # map players relationship if loaded
    try:
        domain_team.players = [_map_player(p) for p in orm.players]
    except Exception:
        # relationship not present or not loaded; leave empty
        domain_team.players = []
    return domain_team


class SQLAlchemyPlayerRepository(PlayerRepository):
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> List[DomainPlayer]:
        orm_players = self.session.query(ORMPlayer).all()
        return [_map_player(p) for p in orm_players]

    def get_by_id(self, player_id: int) -> DomainPlayer:
        orm = self.session.get(ORMPlayer, player_id)
        if orm is None:
            raise KeyError(f"Player {player_id} not found")
        return _map_player(orm)

    def save(self, player: DomainPlayer) -> DomainPlayer:
        # naive upsert by primary key
        orm: Optional[ORMPlayer] = None
        if player.id is not None:
            orm = self.session.get(ORMPlayer, player.id)

        if orm is None:
            orm = ORMPlayer()
            # if id provided and DB supports explicit ids, set it
            if player.id is not None:
                orm.id = player.id
            self.session.add(orm)

        orm.name = player.name
        orm.role = player.role
        orm.team_id = player.team_id
        orm.costo = int(player.costo) if player.costo is not None else None
        orm.anni_contratto = player.anni_contratto
        orm.opzione = player.opzione
        orm.squadra_reale = player.squadra_reale
        orm.is_injured = bool(player.is_injured)

        self.session.commit()
        # refresh to get id
        self.session.refresh(orm)
        return _map_player(orm)


class SQLAlchemyTeamRepository(TeamRepository):
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> List[DomainTeam]:
        orm = self.session.query(ORMTeam).all()
        return [_map_team(t) for t in orm]

    def get_by_id(self, team_id: int) -> DomainTeam:
        orm = self.session.get(ORMTeam, team_id)
        if orm is None:
            raise KeyError(f"Team {team_id} not found")
        return _map_team(orm)
