"""Adapters Layer - Infrastructure adapters for domain interfaces.

This layer contains adapters that implement domain interfaces using
external infrastructure components like ORM repositories.
"""

# Export all adapters
from .repository_adapters import *

__all__ = [
    # Domain Model Mapping
    "DomainModelMapper",

    # Repository Adapters
    "PlayerRepositoryAdapter",
    "TeamRepositoryAdapter",
    "MarketRepositoryAdapter",
    "IntegratedUseCase",
]
