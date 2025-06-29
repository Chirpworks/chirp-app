import logging
from typing import Any, List, Optional
from sqlalchemy.exc import SQLAlchemyError
from app import db

logging = logging.getLogger(__name__)


class BaseService:
    """
    Base service class providing common CRUD operations for all services.
    Each service should inherit from this class and set the model attribute.
    """
    model = None  # Type: Optional[Type[db.Model]]
    
    @classmethod
    def create(cls, **kwargs) -> Any:
        """
        Create a new record in the database.
        
        Args:
            **kwargs: Fields and values for the new record
            
        Returns:
            The created model instance
            
        Raises:
            ValueError: If required fields are missing
            SQLAlchemyError: If database operation fails
        """
        if not cls.model:
            raise NotImplementedError("Model not set in service class")
            
        try:
            instance = cls.model(**kwargs)
            db.session.add(instance)
            db.session.flush()  # Get ID without committing
            logging.info(f"Created {cls.model.__name__} with ID: {instance.id}")
            return instance
        except SQLAlchemyError as e:
            logging.error(f"Failed to create {cls.model.__name__}: {str(e)}")
            raise
    
    @classmethod
    def get_by_id(cls, record_id: Any) -> Optional[Any]:
        """
        Get a record by its ID.
        
        Args:
            record_id: The ID of the record to fetch
            
        Returns:
            The model instance or None if not found
        """
        if not cls.model:
            raise NotImplementedError("Model not set in service class")
            
        try:
            instance = cls.model.query.get(record_id)
            if instance:
                logging.info(f"Found {cls.model.__name__} with ID: {record_id}")
            else:
                logging.warning(f"{cls.model.__name__} not found with ID: {record_id}")
            return instance
        except SQLAlchemyError as e:
            logging.error(f"Failed to get {cls.model.__name__} by ID {record_id}: {str(e)}")
            raise
    
    @classmethod
    def get_by_field(cls, field: str, value: Any) -> Optional[Any]:
        """
        Get a record by a specific field value.
        
        Args:
            field: The field name to search by
            value: The value to search for
            
        Returns:
            The first model instance found or None
        """
        if not cls.model:
            raise NotImplementedError("Model not set in service class")
            
        try:
            instance = cls.model.query.filter(getattr(cls.model, field) == value).first()
            if instance:
                logging.info(f"Found {cls.model.__name__} by {field}: {value}")
            else:
                logging.warning(f"{cls.model.__name__} not found by {field}: {value}")
            return instance
        except AttributeError:
            logging.error(f"Field '{field}' does not exist in {cls.model.__name__}")
            raise
        except SQLAlchemyError as e:
            logging.error(f"Failed to get {cls.model.__name__} by {field}={value}: {str(e)}")
            raise
    
    @classmethod
    def get_all(cls, **filters) -> List[Any]:
        """
        Get all records, optionally filtered.
        
        Args:
            **filters: Field=value pairs for filtering
            
        Returns:
            List of model instances
        """
        if not cls.model:
            raise NotImplementedError("Model not set in service class")
            
        try:
            query = cls.model.query
            
            # Apply filters
            for field, value in filters.items():
                if hasattr(cls.model, field):
                    query = query.filter(getattr(cls.model, field) == value)
                else:
                    logging.warning(f"Field '{field}' does not exist in {cls.model.__name__}")
            
            instances = query.all()
            logging.info(f"Found {len(instances)} {cls.model.__name__} records")
            return instances
        except SQLAlchemyError as e:
            logging.error(f"Failed to get {cls.model.__name__} records: {str(e)}")
            raise
    
    @classmethod
    def update(cls, record_id: Any, **kwargs) -> Optional[Any]:
        """
        Update a record by its ID.
        
        Args:
            record_id: The ID of the record to update
            **kwargs: Fields and values to update
            
        Returns:
            The updated model instance or None if not found
        """
        if not cls.model:
            raise NotImplementedError("Model not set in service class")
            
        try:
            instance = cls.get_by_id(record_id)
            if not instance:
                return None
                
            # Update fields
            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)
                else:
                    logging.warning(f"Field '{field}' does not exist in {cls.model.__name__}")
            
            db.session.flush()
            logging.info(f"Updated {cls.model.__name__} with ID: {record_id}")
            return instance
        except SQLAlchemyError as e:
            logging.error(f"Failed to update {cls.model.__name__} with ID {record_id}: {str(e)}")
            raise
    
    @classmethod
    def delete(cls, record_id: Any) -> bool:
        """
        Delete a record by its ID.
        
        Args:
            record_id: The ID of the record to delete
            
        Returns:
            True if deleted, False if not found
        """
        if not cls.model:
            raise NotImplementedError("Model not set in service class")
            
        try:
            instance = cls.get_by_id(record_id)
            if not instance:
                return False
                
            db.session.delete(instance)
            db.session.flush()
            logging.info(f"Deleted {cls.model.__name__} with ID: {record_id}")
            return True
        except SQLAlchemyError as e:
            logging.error(f"Failed to delete {cls.model.__name__} with ID {record_id}: {str(e)}")
            raise
    
    @staticmethod
    def commit_with_rollback() -> bool:
        """
        Commit the current transaction with automatic rollback on failure.
        
        Returns:
            True if commit successful, False if rolled back
        """
        try:
            db.session.commit()
            logging.info("Database transaction committed successfully")
            return True
        except SQLAlchemyError as e:
            logging.error(f"Database transaction failed, rolling back: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def rollback():
        """
        Rollback the current transaction.
        """
        try:
            db.session.rollback()
            logging.info("Database transaction rolled back")
        except SQLAlchemyError as e:
            logging.error(f"Failed to rollback transaction: {str(e)}") 