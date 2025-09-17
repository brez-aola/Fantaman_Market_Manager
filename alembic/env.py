"""Alembic environment script - minimal scaffold for baseline migrations

This is a lightweight env.py to serve as a starting point. It does not run migrations
automatically; it's intended as a project-scaffold artifact that developers can extend.
"""
from logging.config import fileConfig
import logging
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# this is the Alembic Config object, which provides access to the values within the .ini file
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name:
    fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# ensure project root is on path so we can import app
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import models' MetaData for 'autogenerate' support
try:
    from app.models import Base  # noqa: E402

    target_metadata = Base.metadata
except Exception as exc:  # pragma: no cover - runtime environment
    logger.exception('Failed importing app.models for alembic autogenerate: %s', exc)
    target_metadata = None


def run_migrations_offline():
    url = config.get_main_option('sqlalchemy.url')
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
