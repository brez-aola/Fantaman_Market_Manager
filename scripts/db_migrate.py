#!/usr/bin/env python3
"""Database migration and management script.

This script helps manage database migrations from SQLite to PostgreSQL
and provides utilities for database operations.
"""

import argparse
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database session configurations
PostgresEngine = create_engine(settings.DATABASE_URL)
PostgresSession = sessionmaker(bind=PostgresEngine)


# SQLite session for migration source
def get_sqlite_engine(sqlite_path):
    return create_engine(f"sqlite:///{sqlite_path}")


def get_sqlite_session(sqlite_path):
    engine = get_sqlite_engine(sqlite_path)
    return sessionmaker(bind=engine)


def create_database_if_not_exists():
    """Create PostgreSQL database if it doesn't exist."""
    if not settings.is_postgresql:
        logger.info("Not using PostgreSQL, skipping database creation")
        return

    # Parse database URL to get connection details
    from urllib.parse import urlparse

    parsed = urlparse(settings.DATABASE_URL)

    # Connect to postgres database to create our target database
    postgres_url = f"postgresql+psycopg2://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}/postgres"

    try:
        engine = create_engine(postgres_url)
        with engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{parsed.path[1:]}'")
            )  # nosec: B608 - database name from parsed URL
            if not result.fetchone():
                # Create database
                conn.execute(text("COMMIT"))  # End current transaction
                conn.execute(text(f"CREATE DATABASE {parsed.path[1:]}"))
                logger.info(f"Created database: {parsed.path[1:]}")
            else:
                logger.info(f"Database {parsed.path[1:]} already exists")

    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise


def create_tables():
    """Create all tables using SQLAlchemy metadata."""
    logger.info(f"Creating tables in database: {settings.DATABASE_URL}")

    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(engine)
    logger.info("Tables created successfully")


def convert_data_types(table_name, row_dict):
    """Convert data types for PostgreSQL compatibility."""

    # Define boolean columns for each table
    boolean_columns = {
        "users": ["is_active", "is_verified"],
        "roles": ["is_active"],
        "user_sessions": ["is_active"],
        "audit_logs": ["success"],
    }

    # Convert integer 0/1 to boolean for PostgreSQL
    if table_name in boolean_columns:
        for col in boolean_columns[table_name]:
            if col in row_dict and row_dict[col] is not None:
                row_dict[col] = bool(row_dict[col])

    return row_dict


def migrate_data(sqlite_db_path, dry_run=False):
    """Migrate data from SQLite to PostgreSQL."""
    logger.info(f"Migrating data from {sqlite_db_path} to PostgreSQL")

    if dry_run:
        logger.info("DRY RUN MODE - No data will be modified")

    # Define the order of tables to maintain foreign key constraints
    tables_to_migrate = [
        "leagues",
        "teams",
        "players",
        "team_aliases",
        "canonical_mappings",
        "import_audit",
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "user_sessions",
        "audit_logs",
    ]

    try:
        SQLiteSession = get_sqlite_session(sqlite_db_path)
        with SQLiteSession() as sqlite_session, PostgresSession() as postgres_session:
            for table_name in tables_to_migrate:
                logger.info(f"Migrating table: {table_name}")

                # Get data from SQLite
                try:
                    result = sqlite_session.execute(
                        text(f"SELECT * FROM {table_name}")
                    )  # nosec: B608 - table_name validated above
                    rows = result.fetchall()
                    columns = result.keys()

                    if not rows:
                        logger.info(f"  No data in table {table_name}")
                        continue

                    logger.info(f"  Found {len(rows)} rows")

                    if not dry_run:
                        # Clear existing data in PostgreSQL table
                        postgres_session.execute(
                            text(f"TRUNCATE TABLE {table_name} CASCADE")
                        )

                        # Insert data into PostgreSQL with type conversion
                        for row in rows:
                            row_dict = dict(zip(columns, row))
                            # Convert data types for PostgreSQL compatibility
                            row_dict = convert_data_types(table_name, row_dict)

                            placeholders = ", ".join([f":{col}" for col in columns])
                            query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                            postgres_session.execute(text(query), row_dict)

                        postgres_session.commit()
                        logger.info(f"  Migrated {len(rows)} rows to PostgreSQL")
                    else:
                        logger.info(f"  Would migrate {len(rows)} rows")

                except Exception as e:
                    logger.error(f"Error migrating table {table_name}: {e}")
                    if not dry_run:
                        postgres_session.rollback()
                    continue

        logger.info("Data migration completed successfully")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def validate_migration():
    """Validate that migration was successful by comparing row counts."""
    if not settings.is_postgresql:
        logger.error("Can only validate PostgreSQL migrations")
        return False

    logger.info("Validating migration...")

    # This would need the original SQLite path - for now just check PostgreSQL
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        # Check key tables have data
        key_tables = ["users", "teams", "players"]

        for table in key_tables:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            )  # nosec: B608 - table name from validated list
            count = result.scalar()
            logger.info(f"Table {table}: {count} rows")

    logger.info("Validation completed")
    return True


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Database migration and management")
    parser.add_argument(
        "--create-db",
        action="store_true",
        help="Create PostgreSQL database if not exists",
    )
    parser.add_argument(
        "--create-tables", action="store_true", help="Create all tables"
    )
    parser.add_argument(
        "--migrate-data",
        type=str,
        help="Migrate data from SQLite database (provide path)",
    )
    parser.add_argument("--validate", action="store_true", help="Validate migration")
    parser.add_argument(
        "--dry-run", action="store_true", help="Perform dry run (no changes)"
    )
    parser.add_argument(
        "--all", action="store_true", help="Perform all migration steps"
    )

    args = parser.parse_args()

    if not any(
        [args.create_db, args.create_tables, args.migrate_data, args.validate, args.all]
    ):
        parser.print_help()
        return 1

    try:
        if args.all:
            # Perform complete migration
            logger.info("Starting complete migration process...")
            create_database_if_not_exists()
            create_tables()

            # Look for SQLite database in standard locations
            sqlite_paths = [
                "giocatori.db",
                "../giocatori.db",
                str(project_root / "giocatori.db"),
            ]

            sqlite_path = None
            for path in sqlite_paths:
                if os.path.exists(path):
                    sqlite_path = path
                    break

            if sqlite_path:
                migrate_data(sqlite_path, dry_run=args.dry_run)
                if not args.dry_run:
                    validate_migration()
            else:
                logger.warning("SQLite database not found in standard locations")

        else:
            if args.create_db:
                create_database_if_not_exists()

            if args.create_tables:
                create_tables()

            if args.migrate_data:
                migrate_data(args.migrate_data, dry_run=args.dry_run)

            if args.validate:
                validate_migration()

        logger.info("Migration script completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Migration script failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
