import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_

from app.models.product import Product
from .base_service import BaseService

logging = logging.getLogger(__name__)


class ProductService(BaseService):
    """
    Service class for all product-related database operations.
    """
    model = Product
    
    @classmethod
    def create_product(cls, name: str, agency_id: str, description: Optional[str] = None, 
                      features: Optional[Dict[str, Any]] = None) -> Product:
        """
        Create a new product for an agency.
        
        Args:
            name: Product name
            agency_id: Agency UUID this product belongs to
            description: Optional product description
            features: Optional product features as JSON
            
        Returns:
            Created Product instance
        """
        try:
            product_data = {
                'name': name,
                'agency_id': agency_id,
                'description': description,
                'features': features or {}
            }
            
            product = cls.create(**product_data)
            logging.info(f"Created product: {name} for agency {agency_id} with ID: {product.id}")
            return product
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create product {name}: {str(e)}")
            raise
    
    @classmethod
    def get_products_by_agency(cls, agency_id: str) -> List[Product]:
        """
        Get all products for a specific agency.
        
        Args:
            agency_id: Agency UUID
            
        Returns:
            List of Product instances
        """
        try:
            products = cls.model.query.filter_by(agency_id=agency_id).order_by(
                cls.model.name.asc()
            ).all()
            
            logging.info(f"Found {len(products)} products for agency {agency_id}")
            return products
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get products for agency {agency_id}: {str(e)}")
            raise
    
    @classmethod
    def get_product_with_agency(cls, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product with agency information.
        
        Args:
            product_id: Product UUID
            
        Returns:
            Dictionary with product and agency details or None if not found
        """
        try:
            product = (
                cls.model.query
                .join(cls.model.agency)
                .filter(cls.model.id == product_id)
                .first()
            )
            
            if not product:
                logging.warning(f"Product not found: {product_id}")
                return None
            
            product_details = {
                'id': str(product.id),
                'name': product.name,
                'description': product.description,
                'features': product.features,
                'agency': {
                    'id': str(product.agency.id),
                    'name': product.agency.name,
                    'description': product.agency.description
                }
            }
            
            logging.info(f"Retrieved product details for: {product.name}")
            return product_details
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get product details for {product_id}: {str(e)}")
            raise
    
    @classmethod
    def update_product_info(cls, product_id: str, name: Optional[str] = None, description: Optional[str] = None,
                           features: Optional[Dict[str, Any]] = None) -> Optional[Product]:
        """
        Update product information.
        
        Args:
            product_id: Product UUID
            name: Optional new name
            description: Optional new description
            features: Optional new features
            
        Returns:
            Updated Product instance or None if not found
        """
        try:
            product = cls.get_by_id(product_id)
            if not product:
                logging.warning(f"Product not found: {product_id}")
                return None
            
            update_data = {}
            if name:
                update_data['name'] = name
            if description is not None:  # Allow empty string
                update_data['description'] = description
            if features is not None:
                update_data['features'] = features
            
            if update_data:
                updated_product = cls.update(product_id, **update_data)
                logging.info(f"Updated product {product_id}: {update_data}")
                return updated_product
            
            return product
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to update product {product_id}: {str(e)}")
            raise
    
    @classmethod
    def add_product_feature(cls, product_id: str, feature_key: str, feature_value: Any) -> Optional[Product]:
        """
        Add or update a specific feature for a product.
        
        Args:
            product_id: Product UUID
            feature_key: Feature key to add/update
            feature_value: Feature value
            
        Returns:
            Updated Product instance or None if not found
        """
        try:
            product = cls.get_by_id(product_id)
            if not product:
                logging.warning(f"Product not found: {product_id}")
                return None
            
            # Initialize features if None
            if product.features is None:
                product.features = {}
            
            # Add/update the feature
            features = product.features.copy()
            features[feature_key] = feature_value
            
            updated_product = cls.update(product_id, features=features)
            logging.info(f"Added feature {feature_key} to product {product_id}")
            return updated_product
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to add feature to product {product_id}: {str(e)}")
            raise
    
    @classmethod
    def remove_product_feature(cls, product_id: str, feature_key: str) -> Optional[Product]:
        """
        Remove a specific feature from a product.
        
        Args:
            product_id: Product UUID
            feature_key: Feature key to remove
            
        Returns:
            Updated Product instance or None if not found
        """
        try:
            product = cls.get_by_id(product_id)
            if not product:
                logging.warning(f"Product not found: {product_id}")
                return None
            
            if not product.features or feature_key not in product.features:
                logging.warning(f"Feature {feature_key} not found in product {product_id}")
                return product
            
            # Remove the feature
            features = product.features.copy()
            del features[feature_key]
            
            updated_product = cls.update(product_id, features=features)
            logging.info(f"Removed feature {feature_key} from product {product_id}")
            return updated_product
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to remove feature from product {product_id}: {str(e)}")
            raise
    
    @classmethod
    def search_products(cls, query: str, agency_id: Optional[str] = None) -> List[Product]:
        """
        Search products by name or description, optionally filtered by agency.
        
        Args:
            query: Search query string
            agency_id: Optional agency UUID to filter by
            
        Returns:
            List of matching Product instances
        """
        try:
            search_term = f"%{query.lower()}%"
            
            query_builder = (
                cls.model.query
                .filter(or_(
                    cls.model.name.ilike(search_term),
                    cls.model.description.ilike(search_term)
                ))
            )
            
            if agency_id:
                query_builder = query_builder.filter(cls.model.agency_id == agency_id)
            
            products = query_builder.order_by(cls.model.name.asc()).all()
            
            logging.info(f"Found {len(products)} products matching query: {query}")
            return products
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to search products with query {query}: {str(e)}")
            raise
    
    @classmethod
    def get_products_by_feature(cls, feature_key: str, feature_value: Optional[Any] = None, 
                               agency_id: Optional[str] = None) -> List[Product]:
        """
        Get products that have a specific feature, optionally with a specific value.
        
        Args:
            feature_key: Feature key to search for
            feature_value: Optional specific feature value to match
            agency_id: Optional agency UUID to filter by
            
        Returns:
            List of matching Product instances
        """
        try:
            query_builder = cls.model.query.filter(
                cls.model.features.has_key(feature_key)
            )
            
            if feature_value is not None:
                query_builder = query_builder.filter(
                    cls.model.features[feature_key].astext == str(feature_value)
                )
            
            if agency_id:
                query_builder = query_builder.filter(cls.model.agency_id == agency_id)
            
            products = query_builder.order_by(cls.model.name.asc()).all()
            
            filter_desc = f"feature {feature_key}"
            if feature_value is not None:
                filter_desc += f" = {feature_value}"
            if agency_id:
                filter_desc += f" in agency {agency_id}"
            
            logging.info(f"Found {len(products)} products with {filter_desc}")
            return products
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get products by feature {feature_key}: {str(e)}")
            raise
    
    @classmethod
    def get_product_statistics(cls, agency_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get product statistics for an agency or all agencies.
        
        Args:
            agency_id: Optional agency UUID to get stats for specific agency
            
        Returns:
            Dictionary with product statistics
        """
        try:
            query_builder = cls.model.query
            
            if agency_id:
                query_builder = query_builder.filter(cls.model.agency_id == agency_id)
            
            products = query_builder.all()
            
            # Calculate statistics
            total_products = len(products)
            products_with_description = len([p for p in products if p.description])
            products_with_features = len([p for p in products if p.features])
            
            # Feature statistics
            all_features = {}
            for product in products:
                if product.features:
                    for feature_key in product.features.keys():
                        all_features[feature_key] = all_features.get(feature_key, 0) + 1
            
            # Most common features
            top_features = sorted(all_features.items(), key=lambda x: x[1], reverse=True)[:5]
            
            statistics = {
                'total_products': total_products,
                'products_with_description': products_with_description,
                'products_with_features': products_with_features,
                'description_completion_rate': (products_with_description / total_products * 100) if total_products > 0 else 0,
                'feature_completion_rate': (products_with_features / total_products * 100) if total_products > 0 else 0,
                'unique_features_count': len(all_features),
                'top_features': [{'feature': k, 'usage_count': v} for k, v in top_features]
            }
            
            if agency_id:
                statistics['agency_id'] = agency_id
            
            logging.info(f"Generated product statistics: {statistics}")
            return statistics
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get product statistics: {str(e)}")
            raise
    
    @classmethod
    def clone_product(cls, product_id: str, new_name: Optional[str] = None, target_agency_id: Optional[str] = None) -> Optional[Product]:
        """
        Clone a product, optionally to a different agency.
        
        Args:
            product_id: Source product UUID
            new_name: Optional new name for cloned product
            target_agency_id: Optional target agency UUID (defaults to same agency)
            
        Returns:
            Cloned Product instance or None if source not found
        """
        try:
            source_product = cls.get_by_id(product_id)
            if not source_product:
                logging.warning(f"Source product not found: {product_id}")
                return None
            
            # Prepare clone data
            clone_name = new_name or f"{source_product.name} (Copy)"
            clone_agency_id = target_agency_id or source_product.agency_id
            
            cloned_product = cls.create_product(
                name=clone_name,
                agency_id=clone_agency_id,
                description=source_product.description,
                features=source_product.features.copy() if source_product.features else None
            )
            
            logging.info(f"Cloned product {product_id} to {cloned_product.id}")
            return cloned_product
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to clone product {product_id}: {str(e)}")
            raise
