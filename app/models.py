from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeMeta, declarative_base, relationship

Base: DeclarativeMeta = declarative_base()


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    league_id = Column(Integer, ForeignKey("leagues.id"), nullable=True)
    cash = Column(Integer, default=0)
    # relation to players
    players = relationship("Player", back_populates="team")
    aliases = relationship("TeamAlias", back_populates="team")
    league = relationship("League", back_populates="teams")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Team id={self.id} name={self.name} cash={self.cash}>"


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    role = Column(String(64), nullable=True)
    # new fields mirroring legacy DB
    costo = Column(Integer, nullable=True)
    anni_contratto = Column(Integer, nullable=True)
    opzione = Column(String(8), nullable=True)
    squadra_reale = Column(String(128), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    is_injured = Column(Boolean, default=False)

    team = relationship("Team", back_populates="players")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<Player id={self.id} name={self.name} team_id={self.team_id}>"


class League(Base):
    __tablename__ = "leagues"

    id = Column(Integer, primary_key=True)
    slug = Column(String(64), unique=True, nullable=False)
    name = Column(String(128), nullable=False)

    teams = relationship("Team", back_populates="league")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<League id={self.id} slug={self.slug} name={self.name}>"


class TeamAlias(Base):
    __tablename__ = "team_aliases"

    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    alias = Column(String(256), nullable=False, index=True)

    team = relationship("Team", back_populates="aliases")

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<TeamAlias id={self.id} alias={self.alias} team_id={self.team_id}>"


class ImportAudit(Base):
    __tablename__ = "import_audit"

    id = Column(Integer, primary_key=True)
    filename = Column(String(256), nullable=True)
    user = Column(String(128), nullable=True)
    inserted = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    aliases_created = Column(Integer, default=0)
    success = Column(Boolean, default=True)
    message = Column(String(1024), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<ImportAudit id={self.id} file={self.filename} user={self.user} success={self.success}>"


class CanonicalMapping(Base):
    __tablename__ = "canonical_mappings"

    id = Column(Integer, primary_key=True)
    variant = Column(String(256), nullable=False, unique=True, index=True)
    canonical = Column(String(256), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"<CanonicalMapping id={self.id} variant={self.variant} canonical={self.canonical}>"
