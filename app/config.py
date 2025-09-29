"""Configuration management using environment variables.

This module provides centralized configuration management using python-decouple
to read from .env files and environment variables.
"""

from decouple import config
from typing import List


class Config:
    """Base configuration class."""

    # Database
    DATABASE_URL: str = config('DATABASE_URL', default='sqlite:///giocatori.db')

    # Application
    SECRET_KEY: str = config('SECRET_KEY', default='dev-secret-key-change-in-production')
    JWT_SECRET_KEY: str = config('JWT_SECRET_KEY', default='dev-jwt-secret-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = config('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', default=30, cast=int)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = config('JWT_REFRESH_TOKEN_EXPIRE_DAYS', default=7, cast=int)

    # Environment
    DEBUG: bool = config('DEBUG', default=False, cast=bool)
    ENVIRONMENT: str = config('ENVIRONMENT', default='development')

    # Security
    ALLOWED_HOSTS: List[str] = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda x: [host.strip() for host in x.split(',')])
    CORS_ORIGINS: List[str] = config('CORS_ORIGINS', default='http://localhost:3000,http://127.0.0.1:3000', cast=lambda x: [origin.strip() for origin in x.split(',')])

    # Logging
    LOG_LEVEL: str = config('LOG_LEVEL', default='INFO')
    LOG_FILE: str = config('LOG_FILE', default='app.log')

    # Cache (optional)
    REDIS_URL: str = config('REDIS_URL', default='')

    # Email (optional)
    EMAIL_HOST: str = config('EMAIL_HOST', default='')
    EMAIL_PORT: int = config('EMAIL_PORT', default=587, cast=int)
    EMAIL_USE_TLS: bool = config('EMAIL_USE_TLS', default=True, cast=bool)
    EMAIL_HOST_USER: str = config('EMAIL_HOST_USER', default='')
    EMAIL_HOST_PASSWORD: str = config('EMAIL_HOST_PASSWORD', default='')

    @property
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database."""
        return self.DATABASE_URL.startswith('postgresql')

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.DATABASE_URL.startswith('sqlite')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    LOG_LEVEL = 'WARNING'


class TestingConfig(Config):
    """Testing configuration."""
    DATABASE_URL = 'sqlite:///test.db'
    DEBUG = True


def get_config() -> Config:
    """Get configuration based on environment."""
    env = config('ENVIRONMENT', default='development')

    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return DevelopmentConfig()


# Global config instance
settings = get_config()
