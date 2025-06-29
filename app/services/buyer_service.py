import logging
from typing import List, Optional
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.buyer import Buyer
from app.utils.call_recording_utils import normalize_phone_number
from .base_service import BaseService

logging = logging.getLogger(__name__)


class BuyerService(BaseService):
    """
    Service class for all buyer-related database operations.
    """
    model = Buyer
    
    @classmethod
    def find_or_create_buyer(cls, buyer_phone: str, seller_agency_id: str) -> Buyer:
        """
        Find existing buyer by phone number, or create new buyer if not found.
        This is the main method used by call processing workflows.
        
        Args:
            buyer_phone: Buyer's phone number (will be normalized)
            seller_agency_id: Agency ID from the seller
            
        Returns:
            Buyer instance (existing or newly created)
        """
        try:
            # Normalize phone number for consistent search
            normalized_phone = normalize_phone_number(buyer_phone)
            
            # Try to find existing buyer
            buyer = cls.get_by_phone(normalized_phone)
            
            if buyer:
                logging.info(f"Found existing buyer with phone {normalized_phone}")
                return buyer
            
            # Create new buyer if not found
            logging.info(f"Creating new buyer with phone {normalized_phone}")
            buyer = cls.create_buyer(
                phone=normalized_phone,
                agency_id=seller_agency_id,
                name=None,  # Will be populated later via LLM or manual entry
                email=None  # Will be populated later via LLM or manual entry
            )
            
            return buyer
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to find or create buyer {buyer_phone}: {str(e)}")
            raise
    
    @classmethod
    def create_buyer(cls, phone: str, agency_id: str, name: Optional[str] = None, email: Optional[str] = None) -> Buyer:
        """
        Create a new buyer with normalized phone number.
        
        Args:
            phone: Buyer's phone number (will be normalized)
            agency_id: Agency UUID
            name: Optional buyer name
            email: Optional buyer email
            
        Returns:
            Created Buyer instance
        """
        try:
            # Normalize phone number
            normalized_phone = normalize_phone_number(phone)
            
            buyer_data = {
                'phone': normalized_phone,
                'agency_id': agency_id,
                'name': name,
                'email': email
            }
            
            buyer = cls.create(**buyer_data)
            logging.info(f"Created buyer with phone {normalized_phone} and ID: {buyer.id}")
            return buyer
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create buyer {phone}: {str(e)}")
            raise
    
    @classmethod
    def get_by_phone(cls, phone: str) -> Optional[Buyer]:
        """
        Get buyer by phone number (with normalization).
        
        Args:
            phone: Phone number to search for
            
        Returns:
            Buyer instance or None if not found
        """
        normalized_phone = normalize_phone_number(phone)
        return cls.get_by_field('phone', normalized_phone)
    
    @classmethod
    def get_by_agency(cls, agency_id: str) -> List[Buyer]:
        """
        Get all buyers in a specific agency.
        
        Args:
            agency_id: Agency UUID
            
        Returns:
            List of Buyer instances in the agency
        """
        try:
            buyers = cls.model.query.filter_by(agency_id=agency_id).all()
            logging.info(f"Found {len(buyers)} buyers in agency: {agency_id}")
            return buyers
        except SQLAlchemyError as e:
            logging.error(f"Failed to get buyers for agency {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def update_buyer_info(cls, buyer_id: str, name: Optional[str] = None, email: Optional[str] = None) -> Optional[Buyer]:
        """
        Update buyer's name and/or email information.
        
        Args:
            buyer_id: Buyer UUID
            name: Optional new name
            email: Optional new email
            
        Returns:
            Updated Buyer instance or None if not found
        """
        try:
            update_data = {}
            if name is not None:
                update_data['name'] = name
            if email is not None:
                update_data['email'] = email
            
            if not update_data:
                logging.warning(f"No update data provided for buyer {buyer_id}")
                return cls.get_by_id(buyer_id)
            
            buyer = cls.update(buyer_id, **update_data)
            if buyer:
                logging.info(f"Updated buyer {buyer_id} info: {update_data}")
            return buyer
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to update buyer {buyer_id}: {str(e)}")
            raise
    
    @classmethod
    def get_buyer_interactions(cls, buyer_id: str) -> dict:
        """
        Get buyer's interaction summary (meetings count, etc.).
        
        Args:
            buyer_id: Buyer UUID
            
        Returns:
            Dictionary with interaction statistics
        """
        try:
            from app.models.meeting import Meeting  # Local import to avoid circular imports
            
            buyer = cls.get_by_id(buyer_id)
            if not buyer:
                return {}
            
            # Count meetings
            meeting_count = Meeting.query.filter_by(buyer_id=buyer_id).count()
            
            interactions = {
                'buyer_id': buyer_id,
                'phone': buyer.phone,
                'name': buyer.name,
                'email': buyer.email,
                'total_meetings': meeting_count,
                'agency_id': buyer.agency_id
            }
            
            logging.info(f"Generated interaction summary for buyer {buyer_id}")
            return interactions
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get buyer interactions for {buyer_id}: {str(e)}")
            raise
    
    @classmethod
    def search_buyers(cls, criteria: dict) -> List[Buyer]:
        """
        Search buyers by multiple criteria.
        
        Args:
            criteria: Dictionary of field=value pairs for filtering
            
        Returns:
            List of matching Buyer instances
        """
        try:
            query = cls.model.query
            
            # Apply filters
            for field, value in criteria.items():
                if hasattr(cls.model, field):
                    if field == 'phone':
                        # Normalize phone for search
                        value = normalize_phone_number(value)
                    query = query.filter(getattr(cls.model, field) == value)
                else:
                    logging.warning(f"Invalid search field for Buyer: {field}")
            
            buyers = query.all()
            logging.info(f"Found {len(buyers)} buyers matching criteria: {criteria}")
            return buyers
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to search buyers with criteria {criteria}: {str(e)}")
            raise
    
    @classmethod
    def get_buyers_with_meetings(cls, agency_id: Optional[str] = None) -> List[dict]:
        """
        Get buyers along with their meeting counts.
        
        Args:
            agency_id: Optional agency filter
            
        Returns:
            List of dictionaries with buyer info and meeting counts
        """
        try:
            from app.models.meeting import Meeting  # Local import to avoid circular imports
            from sqlalchemy import func
            
            query = db.session.query(
                cls.model,
                func.count(Meeting.id).label('meeting_count')
            ).outerjoin(Meeting).group_by(cls.model.id)
            
            if agency_id:
                query = query.filter(cls.model.agency_id == agency_id)
            
            results = query.all()
            
            buyers_with_meetings = []
            for buyer, meeting_count in results:
                buyers_with_meetings.append({
                    'id': str(buyer.id),
                    'phone': buyer.phone,
                    'name': buyer.name,
                    'email': buyer.email,
                    'agency_id': str(buyer.agency_id),
                    'meeting_count': meeting_count
                })
            
            logging.info(f"Found {len(buyers_with_meetings)} buyers with meeting counts")
            return buyers_with_meetings
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get buyers with meetings: {str(e)}")
            raise 