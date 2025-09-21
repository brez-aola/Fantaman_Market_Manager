import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.sqlalchemy_repository import (
    SQLAlchemyPlayerRepository,
    SQLAlchemyTeamRepository,
)
from app.domain.models import Player as DomainPlayer
from app.models import Base
from app.models import Player as ORMPlayer
from app.models import Team as ORMTeam


@pytest.fixture
def in_memory_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_player_save_and_get(in_memory_session):
    repo = SQLAlchemyPlayerRepository(in_memory_session)

    p = DomainPlayer(
        id=None,
        name="Mario Rossi",
        role="FWD",
        team_id=None,
        costo=25.0,
        anni_contratto=2,
        opzione="OPT",
        squadra_reale="Real",
        is_injured=False,
    )
    saved = repo.save(p)

    assert saved.id is not None
    assert saved.name == "Mario Rossi"
    assert saved.role == "FWD"
    assert saved.costo == 25.0
    assert saved.anni_contratto == 2
    assert saved.opzione == "OPT"
    assert saved.squadra_reale == "Real"
    assert saved.is_injured is False

    fetched = repo.get_by_id(saved.id)
    assert fetched.id == saved.id
    assert fetched.name == "Mario Rossi"


def test_list_all_and_team_relation(in_memory_session):
    # create team and players via ORM to simulate existing DB rows
    team = ORMTeam(name="Dynamo")
    in_memory_session.add(team)
    in_memory_session.commit()
    p1 = ORMPlayer(
        name="A",
        role="MID",
        team_id=team.id,
        costo=10,
        anni_contratto=1,
        opzione="X",
        squadra_reale="R1",
        is_injured=False,
    )
    p2 = ORMPlayer(
        name="B",
        role="DEF",
        team_id=team.id,
        costo=12,
        anni_contratto=3,
        opzione="Y",
        squadra_reale="R2",
        is_injured=True,
    )
    in_memory_session.add_all([p1, p2])
    in_memory_session.commit()

    repo = SQLAlchemyPlayerRepository(in_memory_session)
    all_players = repo.list_all()

    assert len(all_players) == 2
    names = {pl.name for pl in all_players}
    assert names == {"A", "B"}


def test_team_mapping_with_players(in_memory_session):
    team = ORMTeam(name="United")
    in_memory_session.add(team)
    in_memory_session.commit()

    p1 = ORMPlayer(name="C", role="GK", team_id=team.id, costo=5)
    in_memory_session.add(p1)
    in_memory_session.commit()

    team_repo = SQLAlchemyTeamRepository(in_memory_session)
    domain_team = team_repo.get_by_id(team.id)

    assert domain_team.id == team.id
    assert domain_team.name == "United"
    # players relationship should be mapped
    assert len(domain_team.players) == 1
    assert domain_team.players[0].name == "C"
