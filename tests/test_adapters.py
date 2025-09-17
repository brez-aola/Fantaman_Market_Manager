import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Team as ORMTeam, Player as ORMPlayer
from app.adapters.sqlalchemy_repository import SQLAlchemyPlayerRepository
from app.domain.models import Player as DomainPlayer


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

    p = DomainPlayer(id=None, name="Mario Rossi", role="FWD", team_id=None, costo=25.0)
    saved = repo.save(p)

    assert saved.id is not None
    assert saved.name == "Mario Rossi"
    assert saved.role == "FWD"
    assert saved.costo == 25.0

    fetched = repo.get_by_id(saved.id)
    assert fetched.id == saved.id
    assert fetched.name == "Mario Rossi"


def test_list_all_and_team_relation(in_memory_session):
    # create team and players via ORM to simulate existing DB rows
    team = ORMTeam(name="Dynamo")
    in_memory_session.add(team)
    in_memory_session.commit()

    p1 = ORMPlayer(name="A", role="MID", team_id=team.id, costo=10)
    p2 = ORMPlayer(name="B", role="DEF", team_id=team.id, costo=12)
    in_memory_session.add_all([p1, p2])
    in_memory_session.commit()

    repo = SQLAlchemyPlayerRepository(in_memory_session)
    all_players = repo.list_all()

    assert len(all_players) == 2
    names = {pl.name for pl in all_players}
    assert names == {"A", "B"}
