import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Player as ORMPlayer
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


def test_update_existing_player(in_memory_session):
    # create via ORM
    orm = ORMPlayer(name="Old", role="MID", costo=5)
    in_memory_session.add(orm)
    in_memory_session.commit()

    repo = SQLAlchemyPlayerRepository(in_memory_session)
    domain = repo.get_by_id(orm.id)
    domain.name = "New"
    domain.costo = 15.0
    updated = repo.save(domain)

    assert updated.id == orm.id
    assert updated.name == "New"
    assert updated.costo == 15.0


def test_save_with_explicit_id(in_memory_session):
    repo = SQLAlchemyPlayerRepository(in_memory_session)
    p = DomainPlayer(id=42, name="Ghost", role="DEF", costo=7.0)
    saved = repo.save(p)

    assert saved.id == 42
    assert saved.name == "Ghost"


def test_get_missing_player_raises(in_memory_session):
    repo = SQLAlchemyPlayerRepository(in_memory_session)
    with pytest.raises(KeyError):
        repo.get_by_id(9999)
