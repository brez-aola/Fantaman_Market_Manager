from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True, nullable=False)
    cash = Column(Integer, default=0)
    # relation to players
    players = relationship("Player", back_populates="team")

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
