from dataclasses import dataclass
from typing import Optional

@dataclass
class Team:
    id: int
    name: str

@dataclass
class Player:
    id: int
    name: str
    role: str
    team_id: Optional[int] = None
    costo: Optional[float] = None
