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
    def get_by_phone_and_agency(cls, phone: str, agency_id: str) -> Optional[Buyer]:
        """
        Get buyer by phone number and agency_id (with normalization).
        This allows the same phone number to exist for different agencies.
        
        Args:
            phone: Phone number to search for
            agency_id: Agency UUID
            
        Returns:
            Buyer instance or None if not found
        """
        try:
            normalized_phone = normalize_phone_number(phone)
            buyer = cls.model.query.filter_by(
                phone=normalized_phone,
                agency_id=agency_id
            ).first()
            
            if buyer:
                logging.info(f"Found buyer with phone {normalized_phone} in agency {agency_id}")
            else:
                logging.info(f"No buyer found with phone {normalized_phone} in agency {agency_id}")
                
            return buyer
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get buyer by phone {phone} and agency {agency_id}: {str(e)}")
            raise

    @classmethod
    def find_or_create_buyer(cls, buyer_phone: str, seller_agency_id: str) -> Buyer:
        """
        Find existing buyer by phone number and agency_id, or create new buyer if not found.
        This allows the same phone number to exist for different agencies.
        
        Args:
            buyer_phone: Buyer's phone number (will be normalized)
            seller_agency_id: Agency ID from the seller
            
        Returns:
            Buyer instance (existing or newly created)
        """
        try:
            # Normalize phone number for consistent search
            normalized_phone = normalize_phone_number(buyer_phone)
            
            # Try to find existing buyer by phone AND agency_id
            buyer = cls.get_by_phone_and_agency(normalized_phone, seller_agency_id)
            
            if buyer:
                logging.info(f"Found existing buyer with phone {normalized_phone} in agency {seller_agency_id}")
                return buyer
            
            # Create new buyer if not found
            logging.info(f"Creating new buyer with phone {normalized_phone} in agency {seller_agency_id}")
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
    def create_buyer(cls, phone: str, agency_id: str, name: Optional[str] = None, email: Optional[str] = None,
                    tags: Optional[dict] = None, requirements: Optional[dict] = None,
                    solutions_presented: Optional[dict] = None, relationship_progression: Optional[str] = None,
                    risks: Optional[dict] = None, products_discussed: Optional[dict] = None, 
                    company_name: Optional[str] = None, key_highlights: Optional[dict] = None) -> Buyer:
        """
        Create a new buyer with normalized phone number and optional additional fields.
        
        Args:
            phone: Buyer's phone number (will be normalized)
            agency_id: Agency UUID
            name: Optional buyer name
            email: Optional buyer email
            tags: Optional buyer tags as JSON
            requirements: Optional buyer requirements as JSON
            solutions_presented: Optional solutions presented as JSON
            relationship_progression: Optional relationship progression text
            risks: Optional risks as JSON
            products_discussed: Optional products discussed as JSON
            company_name: Optional buyer company name
            key_highlights: Optional key highlights as JSON
            
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
                'email': email,
                'tags': tags,
                'requirements': requirements,
                'solutions_presented': solutions_presented,
                'relationship_progression': relationship_progression,
                'risks': risks,
                'products_discussed': products_discussed,
                'company_name': company_name,
                'key_highlights': key_highlights
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
    def update_buyer_info(cls, buyer_id: str, name: Optional[str] = None, email: Optional[str] = None,
                         tags: Optional[dict] = None, requirements: Optional[dict] = None,
                         solutions_presented: Optional[dict] = None, relationship_progression: Optional[str] = None,
                         risks: Optional[dict] = None, products_discussed: Optional[dict] = None, 
                         key_highlights: Optional[dict] = None) -> Optional[Buyer]:
        """
        Update buyer's information including all available fields.
        
        Args:
            buyer_id: Buyer UUID
            name: Optional new name
            email: Optional new email
            tags: Optional buyer tags as JSON
            requirements: Optional buyer requirements as JSON
            solutions_presented: Optional solutions presented as JSON
            relationship_progression: Optional relationship progression text
            risks: Optional risks as JSON
            products_discussed: Optional products discussed as JSON
            key_highlights: Optional key highlights as JSON
            
        Returns:
            Updated Buyer instance or None if not found
        """
        try:
            update_data = {}
            if name is not None:
                update_data['name'] = name
            if email is not None:
                update_data['email'] = email
            if tags is not None:
                update_data['tags'] = tags
            if requirements is not None:
                update_data['requirements'] = requirements
            if solutions_presented is not None:
                update_data['solutions_presented'] = solutions_presented
            if relationship_progression is not None:
                update_data['relationship_progression'] = relationship_progression
            if risks is not None:
                update_data['risks'] = risks
            if products_discussed is not None:
                update_data['products_discussed'] = products_discussed
            if key_highlights is not None:
                update_data['key_highlights'] = key_highlights
            
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
                    'meeting_count': meeting_count,
                    'company_name': buyer.company_name
                })
            
            logging.info(f"Found {len(buyers_with_meetings)} buyers with meeting counts")
            return buyers_with_meetings
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get buyers with meetings: {str(e)}")
            raise
    
    @classmethod
    def get_buyers_with_last_contact(cls, agency_id: str) -> List[dict]:
        """
        Get buyers with their last contact information, sorted by last contacted date.
        
        Args:
            agency_id: Agency UUID to filter buyers
            
        Returns:
            List of dictionaries with buyer info and last contact details
        """
        try:
            from app.models.meeting import Meeting  # Local import to avoid circular imports
            from sqlalchemy import func, desc
            
            # Subquery to get the latest meeting for each buyer
            latest_meeting_subquery = db.session.query(
                Meeting.buyer_id,
                func.max(Meeting.start_time).label('last_contacted_at')
            ).group_by(Meeting.buyer_id).subquery()
            
            # Main query to get buyers with their last contact info
            query = db.session.query(
                cls.model,
                latest_meeting_subquery.c.last_contacted_at,
                Meeting.seller_id,
                Meeting.id.label('last_meeting_id')
            ).outerjoin(
                latest_meeting_subquery,
                cls.model.id == latest_meeting_subquery.c.buyer_id
            ).outerjoin(
                Meeting,
                (Meeting.buyer_id == cls.model.id) & 
                (Meeting.start_time == latest_meeting_subquery.c.last_contacted_at)
            ).filter(
                cls.model.agency_id == agency_id
            ).order_by(
                latest_meeting_subquery.c.last_contacted_at.desc().nullslast()
            )
            
            results = query.all()
            
            buyers_with_contact = []
            for buyer, last_contacted_at, seller_id, meeting_id in results:
                # Get seller name for last contact
                last_contacted_by = None
                if seller_id:
                    from app.models.seller import Seller
                    seller = Seller.query.get(seller_id)
                    last_contacted_by = seller.name if seller else None
                
                buyers_with_contact.append({
                    'id': str(buyer.id),
                    'name': buyer.name,
                    'email': buyer.email,
                    'phone': buyer.phone,
                    'products_discussed': buyer.products_discussed,
                    'last_contacted_by': last_contacted_by,
                    'last_contacted_at': last_contacted_at.isoformat() if last_contacted_at else None,
                    'company_name': buyer.company_name
                })
            
            logging.info(f"Found {len(buyers_with_contact)} buyers with last contact info for agency {agency_id}")
            return buyers_with_contact
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get buyers with last contact for agency {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def get_buyer_with_last_contact(cls, buyer_id: str) -> Optional[dict]:
        """
        Get a single buyer with their last contact information.
        
        Args:
            buyer_id: Buyer UUID
            
        Returns:
            Dictionary with buyer info and last contact details, or None if not found
        """
        try:
            from app.models.meeting import Meeting  # Local import to avoid circular imports
            from sqlalchemy import func, desc
            
            # Get the buyer first
            buyer = cls.get_by_id(buyer_id)
            if not buyer:
                return None
            
            # Get the latest meeting for this buyer
            latest_meeting = db.session.query(
                Meeting
            ).filter(
                Meeting.buyer_id == buyer_id
            ).order_by(
                desc(Meeting.start_time)
            ).first()
            
            # Get seller name for last contact
            last_contacted_by = None
            last_contacted_at = None
            
            if latest_meeting and latest_meeting.seller_id:
                from app.models.seller import Seller
                seller = Seller.query.get(latest_meeting.seller_id)
                last_contacted_by = seller.name if seller else None
                last_contacted_at = latest_meeting.start_time
            
            buyer_with_contact = {
                'id': str(buyer.id),
                'name': buyer.name,
                'email': buyer.email,
                'phone': buyer.phone,
                'tags': buyer.tags,
                'requirements': buyer.requirements,
                'solutions_presented': buyer.solutions_presented,
                'relationship_progression': buyer.relationship_progression,
                'risks': buyer.risks,
                'products_discussed': buyer.products_discussed,
                'key_highlights': buyer.key_highlights,
                'last_contacted_by': last_contacted_by,
                'last_contacted_at': last_contacted_at.isoformat() if last_contacted_at else None,
                'company_name': buyer.company_name
            }
            
            logging.info(f"Found buyer {buyer_id} with last contact info")
            return buyer_with_contact
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get buyer with last contact for {buyer_id}: {str(e)}")
            raise
