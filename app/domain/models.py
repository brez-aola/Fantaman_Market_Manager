from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Team:
    id: int
    name: str
    players: List["Player"] = field(default_factory=list)


@dataclass
class Player:
    id: int
    name: str
    role: str
    team_id: Optional[int] = None
    costo: Optional[float] = None
    anni_contratto: Optional[int] = None
    opzione: Optional[str] = None
    squadra_reale: Optional[str] = None
    is_injured: bool = False
