"""Value objects for the domain layer.

Value objects are immutable objects that have no identity and are defined
by their attributes. They encapsulate validation logic and business rules.
"""

import re
from typing import Union
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Email:
    """Email value object with validation."""

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("Email cannot be empty")

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, self.value):
            raise ValueError(f"Invalid email format: {self.value}")

    def domain(self) -> str:
        """Get email domain."""
        return self.value.split('@')[1]

    def local_part(self) -> str:
        """Get email local part (before @)."""
        return self.value.split('@')[0]

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Username:
    """Username value object with validation."""

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("Username cannot be empty")

        if len(self.value) < 3:
            raise ValueError("Username must be at least 3 characters long")

        if len(self.value) > 50:
            raise ValueError("Username must not exceed 50 characters")

        # Allow letters, numbers, underscores, and hyphens
        if not re.match(r'^[a-zA-Z0-9_-]+$', self.value):
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Money:
    """Money value object with currency operations."""

    amount: float
    currency: str = "EUR"

    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

        if not self.currency:
            raise ValueError("Currency must be specified")

        # Round to 2 decimal places for currency precision
        object.__setattr__(self, 'amount', round(self.amount, 2))

    def add(self, other: 'Money') -> 'Money':
        """Add money amounts."""
        if self.currency != other.currency:
            raise ValueError(f"Cannot add different currencies: {self.currency} and {other.currency}")
        return Money(self.amount + other.amount, self.currency)

    def subtract(self, other: 'Money') -> 'Money':
        """Subtract money amounts."""
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract different currencies: {self.currency} and {other.currency}")
        result = self.amount - other.amount
        if result < 0:
            raise ValueError("Result cannot be negative")
        return Money(result, self.currency)

    def multiply(self, factor: float) -> 'Money':
        """Multiply money by a factor."""
        if factor < 0:
            raise ValueError("Multiplication factor cannot be negative")
        return Money(self.amount * factor, self.currency)

    def is_greater_than(self, other: 'Money') -> bool:
        """Compare if this amount is greater than another."""
        if self.currency != other.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} and {other.currency}")
        return self.amount > other.amount

    def is_sufficient_for(self, required: 'Money') -> bool:
        """Check if this amount is sufficient for required amount."""
        if self.currency != required.currency:
            raise ValueError(f"Cannot compare different currencies: {self.currency} and {required.currency}")
        return self.amount >= required.amount

    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Money):
            return False
        return self.amount == other.amount and self.currency == other.currency


class PlayerRoleEnum(Enum):
    """Enumeration for player roles."""
    PORTIERE = "P"
    DIFENSORE = "D"
    CENTROCAMPISTA = "C"
    ATTACCANTE = "A"

    @classmethod
    def from_string(cls, role_str: str) -> 'PlayerRoleEnum':
        """Create PlayerRole from string."""
        role_str = role_str.upper().strip()

        # Handle legacy goalkeeper notation
        if role_str == "G":
            role_str = "P"

        for role in cls:
            if role.value == role_str:
                return role

        raise ValueError(f"Invalid player role: {role_str}")

    def display_name(self) -> str:
        """Get display name for role."""
        names = {
            self.PORTIERE: "Portiere",
            self.DIFENSORE: "Difensore",
            self.CENTROCAMPISTA: "Centrocampista",
            self.ATTACCANTE: "Attaccante"
        }
        return names[self]


@dataclass(frozen=True)
class PlayerRole:
    """Player role value object."""

    value: PlayerRoleEnum

    def __post_init__(self):
        if not isinstance(self.value, PlayerRoleEnum):
            raise ValueError("PlayerRole value must be a PlayerRoleEnum")

    @classmethod
    def from_string(cls, role_str: str) -> 'PlayerRole':
        """Create PlayerRole from string."""
        return cls(PlayerRoleEnum.from_string(role_str))

    def is_goalkeeper(self) -> bool:
        """Check if role is goalkeeper."""
        return self.value == PlayerRoleEnum.PORTIERE

    def is_defender(self) -> bool:
        """Check if role is defender."""
        return self.value == PlayerRoleEnum.DIFENSORE

    def is_midfielder(self) -> bool:
        """Check if role is midfielder."""
        return self.value == PlayerRoleEnum.CENTROCAMPISTA

    def is_forward(self) -> bool:
        """Check if role is forward."""
        return self.value == PlayerRoleEnum.ATTACCANTE

    def display_name(self) -> str:
        """Get display name for role."""
        return self.value.display_name()

    def __str__(self) -> str:
        return self.value.value


@dataclass(frozen=True)
class TeamName:
    """Team name value object with validation."""

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("Team name cannot be empty")

        if len(self.value.strip()) < 2:
            raise ValueError("Team name must be at least 2 characters long")

        if len(self.value) > 100:
            raise ValueError("Team name must not exceed 100 characters")

        # Clean up the name
        cleaned_name = self.value.strip()
        object.__setattr__(self, 'value', cleaned_name)

    def slug(self) -> str:
        """Get URL-friendly slug for team name."""
        import re
        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', self.value.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        return slug

    def initials(self) -> str:
        """Get team initials."""
        words = self.value.split()
        return ''.join(word[0].upper() for word in words if word)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class LeagueSlug:
    """League slug value object for URL-friendly identifiers."""

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("League slug cannot be empty")

        # Validate slug format: lowercase, alphanumeric, hyphens only
        if not re.match(r'^[a-z0-9-]+$', self.value):
            raise ValueError("League slug must contain only lowercase letters, numbers, and hyphens")

        if len(self.value) < 3:
            raise ValueError("League slug must be at least 3 characters long")

        if len(self.value) > 50:
            raise ValueError("League slug must not exceed 50 characters")

    @classmethod
    def from_name(cls, name: str) -> 'LeagueSlug':
        """Create slug from league name."""
        import re
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        slug = slug[:50]  # Truncate if too long
        return cls(slug)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Password:
    """Password value object with security validation."""

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("Password cannot be empty")

        if len(self.value) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if len(self.value) > 128:
            raise ValueError("Password must not exceed 128 characters")

    def has_uppercase(self) -> bool:
        """Check if password has uppercase letter."""
        return any(c.isupper() for c in self.value)

    def has_lowercase(self) -> bool:
        """Check if password has lowercase letter."""
        return any(c.islower() for c in self.value)

    def has_digit(self) -> bool:
        """Check if password has digit."""
        return any(c.isdigit() for c in self.value)

    def has_special_char(self) -> bool:
        """Check if password has special character."""
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        return any(c in special_chars for c in self.value)

    def is_strong(self) -> bool:
        """Check if password meets strength requirements."""
        return (
            len(self.value) >= 12 and
            self.has_uppercase() and
            self.has_lowercase() and
            self.has_digit() and
            self.has_special_char()
        )

    def strength_score(self) -> int:
        """Get password strength score (0-5)."""
        score = 0
        if len(self.value) >= 8:
            score += 1
        if self.has_uppercase():
            score += 1
        if self.has_lowercase():
            score += 1
        if self.has_digit():
            score += 1
        if self.has_special_char():
            score += 1
        return score

    def __str__(self) -> str:
        return "***" * len(self.value)  # Hide password in string representation
