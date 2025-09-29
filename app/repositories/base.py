"""Base repository implementation.

Provides common database operations and patterns for all repository classes.
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from sqlalchemy.exc import IntegrityError, NoResultFound
import logging

logger = logging.getLogger(__name__)

# Generic type for model classes
ModelType = TypeVar('ModelType')


class BaseRepository(Generic[ModelType], ABC):
    """Base repository class with common CRUD operations."""

    def __init__(self, db_session: Session, model_class: type):
        """Initialize repository with database session and model class.

        Args:
            db_session: SQLAlchemy database session
            model_class: SQLAlchemy model class
        """
        self.db = db_session
        self.model_class = model_class

    def create(self, **kwargs) -> ModelType:
        """Create a new record.

        Args:
            **kwargs: Field values for the new record

        Returns:
            Created model instance

        Raises:
            IntegrityError: If database constraints are violated
        """
        try:
            instance = self.model_class(**kwargs)
            self.db.add(instance)
            self.db.commit()
            self.db.refresh(instance)
            logger.info(f"Created {self.model_class.__name__} with id {instance.id}")
            return instance
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to create {self.model_class.__name__}: {e}")
            raise

    def get_by_id(self, id: int) -> Optional[ModelType]:
        """Get a record by its ID.

        Args:
            id: Record ID

        Returns:
            Model instance if found, None otherwise
        """
        return self.db.query(self.model_class).filter(self.model_class.id == id).first()

    def get_by_id_or_404(self, id: int) -> ModelType:
        """Get a record by its ID or raise exception.

        Args:
            id: Record ID

        Returns:
            Model instance

        Raises:
            NoResultFound: If record not found
        """
        instance = self.get_by_id(id)
        if not instance:
            raise NoResultFound(f"{self.model_class.__name__} with id {id} not found")
        return instance

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Get all records with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        return self.db.query(self.model_class).offset(skip).limit(limit).all()

    def get_by_filter(self, **filters) -> List[ModelType]:
        """Get records by filter criteria.

        Args:
            **filters: Filter criteria

        Returns:
            List of model instances matching filters
        """
        query = self.db.query(self.model_class)
        for field, value in filters.items():
            if hasattr(self.model_class, field):
                query = query.filter(getattr(self.model_class, field) == value)
        return query.all()

    def get_one_by_filter(self, **filters) -> Optional[ModelType]:
        """Get single record by filter criteria.

        Args:
            **filters: Filter criteria

        Returns:
            Model instance if found, None otherwise
        """
        query = self.db.query(self.model_class)
        for field, value in filters.items():
            if hasattr(self.model_class, field):
                query = query.filter(getattr(self.model_class, field) == value)
        return query.first()

    def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """Update a record.

        Args:
            id: Record ID
            **kwargs: Fields to update

        Returns:
            Updated model instance if found, None otherwise

        Raises:
            IntegrityError: If database constraints are violated
        """
        try:
            instance = self.get_by_id(id)
            if not instance:
                return None

            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)

            self.db.commit()
            self.db.refresh(instance)
            logger.info(f"Updated {self.model_class.__name__} with id {id}")
            return instance
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to update {self.model_class.__name__} {id}: {e}")
            raise

    def delete(self, id: int) -> bool:
        """Delete a record.

        Args:
            id: Record ID

        Returns:
            True if deleted, False if not found
        """
        instance = self.get_by_id(id)
        if not instance:
            return False

        self.db.delete(instance)
        self.db.commit()
        logger.info(f"Deleted {self.model_class.__name__} with id {id}")
        return True

    def count(self, **filters) -> int:
        """Count records matching filters.

        Args:
            **filters: Filter criteria

        Returns:
            Number of matching records
        """
        query = self.db.query(self.model_class)
        for field, value in filters.items():
            if hasattr(self.model_class, field):
                query = query.filter(getattr(self.model_class, field) == value)
        return query.count()

    def exists(self, **filters) -> bool:
        """Check if record exists matching filters.

        Args:
            **filters: Filter criteria

        Returns:
            True if record exists, False otherwise
        """
        return self.count(**filters) > 0

    def bulk_create(self, instances: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple records in batch.

        Args:
            instances: List of dictionaries with field values

        Returns:
            List of created model instances

        Raises:
            IntegrityError: If database constraints are violated
        """
        try:
            db_instances = [self.model_class(**data) for data in instances]
            self.db.add_all(db_instances)
            self.db.commit()

            for instance in db_instances:
                self.db.refresh(instance)

            logger.info(f"Created {len(db_instances)} {self.model_class.__name__} records")
            return db_instances
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Failed to bulk create {self.model_class.__name__}: {e}")
            raise
