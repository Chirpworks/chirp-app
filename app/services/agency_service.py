import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, text

from app import db
from app.models.agency import Agency
from app.models.seller import Seller
from app.models.buyer import Buyer
from app.models.product import Product
from .base_service import BaseService

logging = logging.getLogger(__name__)


class AgencyService(BaseService):
    """
    Service class for all agency-related database operations and tenant management.
    """
    model = Agency
    
    @classmethod
    def create_agency(cls, name: str, description: Optional[str] = None) -> Agency:
        """
        Create a new agency.
        
        Args:
            name: Agency name
            description: Optional agency description
            
        Returns:
            Created Agency instance
            
        Raises:
            ValueError: If agency with same name already exists
            SQLAlchemyError: If database operation fails
        """
        try:
            # Check if agency with same name already exists
            existing_agency = cls.get_by_field('name', name)
            if existing_agency:
                logging.warning(f"Agency with name '{name}' already exists with ID: {existing_agency.id}")
                raise ValueError(f"Agency with name '{name}' already exists")
            
            agency_data = {
                'name': name
            }
            
            if description:
                agency_data['description'] = description
            
            agency = cls.create(**agency_data)
            logging.info(f"Created agency: {name} with ID: {agency.id}")
            return agency
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create agency {name}: {str(e)}")
            raise
    
    @classmethod
    def get_agency_with_details(cls, agency_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agency with detailed information including counts of sellers, buyers, and products.
        
        Args:
            agency_id: Agency UUID
            
        Returns:
            Dictionary with agency details and statistics or None if not found
        """
        try:
            agency = cls.get_by_id(agency_id)
            if not agency:
                logging.warning(f"Agency not found: {agency_id}")
                return None
            
            # Get counts
            seller_count = len(agency.sellers)
            buyer_count = len(agency.buyers)
            product_count = len(agency.products)
            
            # Get active sellers (assuming GUEST role means inactive)
            active_sellers = [s for s in agency.sellers if s.role.name != 'GUEST']
            active_seller_count = len(active_sellers)
            
            agency_details = {
                'id': str(agency.id),
                'name': agency.name,
                'description': agency.description,
                'seller_count': seller_count,
                'active_seller_count': active_seller_count,
                'buyer_count': buyer_count,
                'product_count': product_count,
                'sellers': [cls._format_seller_summary(seller) for seller in agency.sellers[:10]],  # First 10
                'recent_buyers': [cls._format_buyer_summary(buyer) for buyer in agency.buyers[:5]],  # First 5
                'products': [cls._format_product_summary(product) for product in agency.products[:5]]  # First 5
            }
            
            logging.info(f"Retrieved agency details for: {agency.name}")
            return agency_details
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get agency details for {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def get_agencies_summary(cls) -> List[Dict[str, Any]]:
        """
        Get a summary of all agencies with basic statistics.
        
        Returns:
            List of agency summary dictionaries
        """
        try:
            agencies = cls.get_all()
            
            summary_list = []
            for agency in agencies:
                summary = {
                    'id': str(agency.id),
                    'name': agency.name,
                    'description': agency.description,
                    'seller_count': len(agency.sellers),
                    'buyer_count': len(agency.buyers),
                    'product_count': len(agency.products)
                }
                summary_list.append(summary)
            
            logging.info(f"Retrieved summary for {len(summary_list)} agencies")
            return summary_list
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get agencies summary: {str(e)}")
            raise
    
    @classmethod
    def update_agency_info(cls, agency_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Optional[Agency]:
        """
        Update agency information.
        
        Args:
            agency_id: Agency UUID
            name: Optional new name
            description: Optional new description
            
        Returns:
            Updated Agency instance or None if not found
        """
        try:
            agency = cls.get_by_id(agency_id)
            if not agency:
                logging.warning(f"Agency not found: {agency_id}")
                return None
            
            update_data = {}
            if name:
                update_data['name'] = name
            if description is not None:  # Allow empty string
                update_data['description'] = description
            
            if update_data:
                updated_agency = cls.update(agency_id, **update_data)
                logging.info(f"Updated agency {agency_id}: {update_data}")
                return updated_agency
            
            return agency
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to update agency {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def get_agency_sellers(cls, agency_id: str, active_only: bool = True) -> List[Seller]:
        """
        Get all sellers for an agency.
        
        Args:
            agency_id: Agency UUID
            active_only: Whether to return only active sellers (non-GUEST role)
            
        Returns:
            List of Seller instances
        """
        try:
            agency = cls.get_by_id(agency_id)
            if not agency:
                logging.warning(f"Agency not found: {agency_id}")
                return []
            
            sellers = agency.sellers
            
            if active_only:
                sellers = [s for s in sellers if s.role.name != 'GUEST']
            
            logging.info(f"Found {len(sellers)} sellers for agency {agency_id}")
            return sellers
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get sellers for agency {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def get_agency_buyers(cls, agency_id: str, limit: Optional[int] = None) -> List[Buyer]:
        """
        Get buyers for an agency.
        
        Args:
            agency_id: Agency UUID
            limit: Optional limit on number of buyers returned
            
        Returns:
            List of Buyer instances
        """
        try:
            agency = cls.get_by_id(agency_id)
            if not agency:
                logging.warning(f"Agency not found: {agency_id}")
                return []
            
            buyers = agency.buyers
            
            if limit:
                buyers = buyers[:limit]
            
            logging.info(f"Found {len(buyers)} buyers for agency {agency_id}")
            return buyers
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get buyers for agency {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def get_agency_products(cls, agency_id: str) -> List[Product]:
        """
        Get all products for an agency.
        
        Args:
            agency_id: Agency UUID
            
        Returns:
            List of Product instances
        """
        try:
            agency = cls.get_by_id(agency_id)
            if not agency:
                logging.warning(f"Agency not found: {agency_id}")
                return []
            
            products = agency.products
            logging.info(f"Found {len(products)} products for agency {agency_id}")
            return products
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get products for agency {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def search_agencies(cls, query: str) -> List[Agency]:
        """
        Search agencies by name or description.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching Agency instances
        """
        try:
            search_term = f"%{query.lower()}%"
            
            agencies = (
                Agency.query
                .filter(or_(
                    Agency.name.ilike(search_term),
                    Agency.description.ilike(search_term)
                ))
                .order_by(Agency.name.asc())
                .all()
            )
            
            logging.info(f"Found {len(agencies)} agencies matching query: {query}")
            return agencies
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to search agencies with query {query}: {str(e)}")
            raise
    
    @classmethod
    def get_agency_statistics(cls, agency_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get agency statistics.
        
        Args:
            agency_id: Optional agency UUID to get stats for specific agency
            
        Returns:
            Dictionary with agency statistics
        """
        try:
            if agency_id:
                # Statistics for specific agency
                agency = cls.get_by_id(agency_id)
                if not agency:
                    logging.warning(f"Agency not found: {agency_id}")
                    return {}
                
                agencies = [agency]
            else:
                # Statistics for all agencies
                agencies = cls.get_all()
            
            # Calculate statistics
            total_agencies = len(agencies)
            total_sellers = sum(len(agency.sellers) for agency in agencies)
            total_buyers = sum(len(agency.buyers) for agency in agencies)
            total_products = sum(len(agency.products) for agency in agencies)
            
            # Active sellers (non-GUEST role)
            total_active_sellers = sum(
                len([s for s in agency.sellers if s.role.name != 'GUEST']) 
                for agency in agencies
            )
            
            statistics = {
                'total_agencies': total_agencies,
                'total_sellers': total_sellers,
                'total_active_sellers': total_active_sellers,
                'total_buyers': total_buyers,
                'total_products': total_products,
                'avg_sellers_per_agency': total_sellers / total_agencies if total_agencies > 0 else 0,
                'avg_buyers_per_agency': total_buyers / total_agencies if total_agencies > 0 else 0,
                'avg_products_per_agency': total_products / total_agencies if total_agencies > 0 else 0
            }
            
            if agency_id:
                statistics['agency_id'] = agency_id
                statistics['agency_name'] = agency.name
            
            logging.info(f"Generated agency statistics: {statistics}")
            return statistics
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get agency statistics: {str(e)}")
            raise
    
    @classmethod
    def delete_agency_cascade(cls, agency_id: str) -> bool:
        """
        Delete an agency and all its related data (sellers, buyers, products).
        Use with extreme caution - this is a destructive operation.
        
        Args:
            agency_id: Agency UUID
            
        Returns:
            True if deleted successfully
        """
        try:
            agency = cls.get_by_id(agency_id)
            if not agency:
                logging.warning(f"Agency not found: {agency_id}")
                return False
            
            agency_name = agency.name
            
            # The cascade='all, delete-orphan' in the model will handle the deletion
            # of related sellers, buyers, and products
            db.session.delete(agency)
            db.session.commit()  # Commit the transaction
            
            logging.warning(f"DELETED agency {agency_name} and all related data!")
            return True
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to delete agency {agency_id}: {str(e)}")
            db.session.rollback()
            raise
    
    @classmethod
    def _format_seller_summary(cls, seller: Seller) -> Dict[str, Any]:
        """
        Format seller for summary display.
        
        Args:
            seller: Seller instance
            
        Returns:
            Formatted seller dictionary
        """
        return {
            'id': str(seller.id),
            'name': seller.name,
            'email': seller.email,
            'phone': seller.phone,
            'role': seller.role.name if seller.role else None
        }
    
    @classmethod
    def _format_buyer_summary(cls, buyer: Buyer) -> Dict[str, Any]:
        """
        Format buyer for summary display.
        
        Args:
            buyer: Buyer instance
            
        Returns:
            Formatted buyer dictionary
        """
        return {
            'id': str(buyer.id),
            'name': buyer.name,
            'phone': buyer.phone,
            'email': buyer.email,
            'agency_name': buyer.agency.name
        }
    
    @classmethod
    def _format_product_summary(cls, product: Product) -> Dict[str, Any]:
        """
        Format product for summary display.
        
        Args:
            product: Product instance
            
        Returns:
            Formatted product dictionary
        """
        return {
            'id': str(product.id),
            'name': product.name,
            'description': product.description
        }
    
    @classmethod
    def agency_exists_by_id(cls, agency_id: str) -> bool:
        """
        Check if an agency with the given ID exists.
        
        Args:
            agency_id: Agency UUID to check
            
        Returns:
            True if agency exists, False otherwise
        """
        try:
            agency = cls.get_by_id(agency_id)
            return agency is not None
        except SQLAlchemyError as e:
            logging.error(f"Failed to check agency existence for ID {agency_id}: {str(e)}")
            raise

    @classmethod
    def agency_exists_by_name(cls, name: str) -> bool:
        """
        Check if an agency with the given name exists.
        
        Args:
            name: Agency name to check
            
        Returns:
            True if agency exists, False otherwise
        """
        try:
            agency = cls.get_by_field('name', name)
            return agency is not None
        except SQLAlchemyError as e:
            logging.error(f"Failed to check agency existence for name {name}: {str(e)}")
            raise 