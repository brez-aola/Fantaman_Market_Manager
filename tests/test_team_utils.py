import pytest
from app.models import Team, League, TeamAlias, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_resolve_team_by_alias():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        league = League(slug='test', name='Test League')
        s.add(league)
        s.commit()
        t = Team(name='My Team', cash=100, league_id=league.id)
        s.add(t)
        s.commit()
        ta = TeamAlias(team_id=t.id, alias='MyTeamAlias')
        s.add(ta)
        s.commit()

        from app.utils.team_utils import resolve_team_by_alias

        found = resolve_team_by_alias(s, 'MyTeamAlias', league_slug='test')
        assert found is not None and found.id == t.id

        found2 = resolve_team_by_alias(s, 'My Team')
        assert found2 is not None and found2.id == t.id
    finally:
        s.close()
