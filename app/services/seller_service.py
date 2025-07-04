import logging
from typing import List, Optional, Tuple
from datetime import timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_

from app import db
from app.models.seller import Seller, SellerRole
from app.utils.auth_utils import generate_user_claims
from app.utils.call_recording_utils import normalize_phone_number
from .base_service import BaseService

logging = logging.getLogger(__name__)


class SellerService(BaseService):
    """
    Service class for all seller/user related database operations.
    """
    model = Seller
    
    @classmethod
    def create_seller(cls, email: str, phone: str, password: str, agency_id: str, 
                     name: str, role: Optional[str] = None) -> Seller:
        """
        Create a new seller with normalized data.
        
        Args:
            email: Seller's email address
            phone: Seller's phone number (will be normalized)
            password: Plain password (will be hashed)
            agency_id: Agency UUID
            name: Seller's full name
            role: Seller's role (defaults to USER)
            
        Returns:
            Created Seller instance
            
        Raises:
            ValueError: If seller already exists
            SQLAlchemyError: If database operation fails
        """
        try:
            # Check if seller already exists
            existing_seller = cls.get_by_email_or_phone(email, phone)
            if existing_seller:
                raise ValueError(f"Seller already exists with email {email} or phone {phone}")
            
            # Normalize phone number
            normalized_phone = normalize_phone_number(phone)
            
            # Create seller using model constructor (handles password hashing)
            seller = Seller(
                email=email,
                phone=normalized_phone,
                password=password,
                agency_id=agency_id,
                name=name,
                role=role
            )
            
            db.session.add(seller)
            db.session.flush()
            
            logging.info(f"Created seller: {email} with ID: {seller.id}")
            return seller
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create seller {email}: {str(e)}")
            raise
    
    @classmethod
    def get_by_email(cls, email: str) -> Optional[Seller]:
        """
        Get seller by email address.
        
        Args:
            email: Email address to search for
            
        Returns:
            Seller instance or None if not found
        """
        return cls.get_by_field('email', email)
    
    @classmethod
    def get_by_phone(cls, phone: str) -> Optional[Seller]:
        """
        Get seller by phone number (normalized).
        
        Args:
            phone: Phone number to search for
            
        Returns:
            Seller instance or None if not found
        """
        normalized_phone = normalize_phone_number(phone)
        return cls.get_by_field('phone', normalized_phone)
    
    @classmethod
    def get_by_email_or_phone(cls, email: str, phone: str) -> Optional[Seller]:
        """
        Get seller by either email or phone number.
        
        Args:
            email: Email address to search for
            phone: Phone number to search for
            
        Returns:
            Seller instance or None if not found
        """
        try:
            normalized_phone = normalize_phone_number(phone)
            seller = Seller.query.filter(
                or_(Seller.email == email, Seller.phone == normalized_phone)
            ).first()
            
            if seller:
                logging.info(f"Found seller by email/phone: {email}/{normalized_phone}")
            else:
                logging.warning(f"Seller not found by email/phone: {email}/{normalized_phone}")
                
            return seller
        except SQLAlchemyError as e:
            logging.error(f"Failed to get seller by email/phone {email}/{phone}: {str(e)}")
            raise
    
    @classmethod
    def validate_credentials(cls, email: str, password: str) -> Tuple[bool, Optional[Seller]]:
        """
        Validate seller credentials for login.
        
        Args:
            email: Email address
            password: Plain password to check
            
        Returns:
            Tuple of (is_valid, seller_instance)
        """
        try:
            seller = cls.get_by_email(email)
            if not seller:
                logging.warning(f"Login attempt with non-existent email: {email}")
                return False, None
                
            if not seller.check_password(password):
                logging.warning(f"Invalid password for email: {email}")
                return False, None
                
            logging.info(f"Valid credentials for seller: {email}")
            return True, seller
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to validate credentials for {email}: {str(e)}")
            raise
    
    @classmethod
    def update_password(cls, seller_id: str, old_password: str, new_password: str) -> bool:
        """
        Update seller's password with validation.
        
        Args:
            seller_id: Seller's UUID
            old_password: Current password for validation
            new_password: New password to set
            
        Returns:
            True if password updated successfully, False if old password invalid
            
        Raises:
            ValueError: If seller not found
        """
        try:
            seller = cls.get_by_id(seller_id)
            if not seller:
                raise ValueError(f"Seller not found with ID: {seller_id}")
                
            if not seller.check_password(old_password):
                logging.warning(f"Invalid old password for seller: {seller.email}")
                return False
                
            seller.set_password(new_password)
            db.session.flush()
            
            logging.info(f"Password updated for seller: {seller.email}")
            return True
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to update password for seller {seller_id}: {str(e)}")
            raise
    
    @classmethod
    def reset_password(cls, seller_id: str, new_password: str) -> bool:
        """
        Reset seller's password without requiring old password validation.
        Use this for password reset functionality where old password is not available.
        
        Args:
            seller_id: Seller's UUID
            new_password: New password to set
            
        Returns:
            True if password reset successfully, False if seller not found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            seller = cls.get_by_id(seller_id)
            if not seller:
                logging.warning(f"Seller not found for password reset: {seller_id}")
                return False
                
            seller.set_password(new_password)
            db.session.commit()
            
            logging.info(f"Password reset successfully for seller: {seller.email}")
            return True
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to reset password for seller {seller_id}: {str(e)}")
            raise
    
    @classmethod
    def reset_password_by_email(cls, email: str, new_password: str) -> bool:
        """
        Reset seller's password by email without requiring old password validation.
        
        Args:
            email: Seller's email address
            new_password: New password to set
            
        Returns:
            True if password reset successfully, False if seller not found
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        try:
            seller = cls.get_by_email(email)
            if not seller:
                logging.warning(f"Seller not found for password reset: {email}")
                return False
                
            seller.set_password(new_password)
            db.session.commit()
            
            logging.info(f"Password reset successfully for seller: {seller.email}")
            return True
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to reset password for seller {email}: {str(e)}")
            raise
    
    @classmethod
    def get_team_members(cls, manager_id: str) -> List[Seller]:
        """
        Get all team members for a specific manager.
        
        Args:
            manager_id: Manager's UUID
            
        Returns:
            List of Seller instances that report to this manager
        """
        try:
            team_members = cls.model.query.filter_by(manager_id=manager_id).all()
            logging.info(f"Found {len(team_members)} team members for manager: {manager_id}")
            return team_members
        except SQLAlchemyError as e:
            logging.error(f"Failed to get team members for manager {manager_id}: {str(e)}")
            raise
    
    @classmethod
    def assign_manager(cls, seller_id: str, manager_id: str) -> Optional[Seller]:
        """
        Assign a manager to a seller.
        
        Args:
            seller_id: Seller's UUID
            manager_id: Manager's UUID
            
        Returns:
            Updated Seller instance or None if seller not found
        """
        try:
            # Validate that manager exists and has manager role
            manager = cls.get_by_id(manager_id)
            if not manager:
                raise ValueError(f"Manager not found with ID: {manager_id}")
                
            if manager.role != SellerRole.MANAGER:
                raise ValueError(f"User {manager_id} does not have manager role")
            
            # Update seller's manager
            seller = cls.update(seller_id, manager_id=manager_id)
            if seller:
                logging.info(f"Assigned manager {manager_id} to seller {seller_id}")
            
            return seller
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to assign manager {manager_id} to seller {seller_id}: {str(e)}")
            raise
    
    @classmethod
    def get_by_agency(cls, agency_id: str) -> List[Seller]:
        """
        Get all sellers in a specific agency.
        
        Args:
            agency_id: Agency UUID
            
        Returns:
            List of Seller instances in the agency
        """
        try:
            sellers = cls.model.query.filter_by(agency_id=agency_id).all()
            logging.info(f"Found {len(sellers)} sellers in agency: {agency_id}")
            return sellers
        except SQLAlchemyError as e:
            logging.error(f"Failed to get sellers for agency {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def search_sellers(cls, criteria: dict) -> List[Seller]:
        """
        Search sellers by multiple criteria.
        
        Args:
            criteria: Dictionary of field=value pairs for filtering
            
        Returns:
            List of matching Seller instances
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
                    logging.warning(f"Invalid search field for Seller: {field}")
            
            sellers = query.all()
            logging.info(f"Found {len(sellers)} sellers matching criteria: {criteria}")
            return sellers
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to search sellers with criteria {criteria}: {str(e)}")
            raise
    
    @classmethod
    def generate_tokens(cls, seller: Seller) -> dict:
        """
        Generate access and refresh tokens for a seller.
        
        Args:
            seller: Seller instance
            
        Returns:
            Dictionary with access_token, refresh_token, and user_id
        """
        try:
            user_claims = generate_user_claims(seller)
            access_token = seller.generate_access_token(
                expires_delta=timedelta(minutes=15), 
                additional_claims=user_claims
            )
            refresh_token = seller.generate_refresh_token()
            
            logging.info(f"Generated tokens for seller: {seller.email}")
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'user_id': str(seller.id)
            }
        except Exception as e:
            logging.error(f"Failed to generate tokens for seller {seller.email}: {str(e)}")
            raise
    
    @classmethod
    def get_all_count(cls) -> int:
        """
        Get total count of all sellers.
        
        Returns:
            Total number of sellers
        """
        try:
            count = cls.model.query.count()
            logging.info(f"Total sellers count: {count}")
            return count
        except SQLAlchemyError as e:
            logging.error(f"Failed to get sellers count: {str(e)}")
            raise
    
    @classmethod
    def get_active_users_count(cls) -> int:
        """
        Get count of active sellers (non-GUEST role).
        
        Returns:
            Number of active sellers
        """
        try:
            count = (
                Seller.query
                .filter(Seller.role != SellerRole.GUEST)
                .count()
            )
            logging.info(f"Active sellers count: {count}")
            return count
        except SQLAlchemyError as e:
            logging.error(f"Failed to get active users count: {str(e)}")
            raise 