import logging
import time
import hashlib
import redis
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, or_, and_, text

from app import db
from app.models.buyer import Buyer
from app.models.meeting import Meeting
from app.models.seller import Seller
from app.models.search_analytics import SearchAnalytics
from app.utils.call_recording_utils import normalize_phone_number, denormalize_phone_number
from .base_service import BaseService

logging = logging.getLogger(__name__)


class BuyerSearchService(BaseService):
    """
    Service class for buyer search functionality with fuzzy matching, caching, and rate limiting.
    """
    model = Buyer
    
    # Redis clients for caching and rate limiting (with graceful degradation)
    _cache_client = None
    _rate_limit_client = None
    
    @classmethod
    def _get_cache_client(cls):
        """Get Redis client for caching with lazy initialization."""
        if cls._cache_client is None:
            try:
                cls._cache_client = redis.Redis(
                    host='localhost', 
                    port=6379, 
                    db=2,  # Separate database for search cache
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2
                )
                cls._cache_client.ping()
                logging.info("Redis cache client initialized for buyer search")
            except Exception as e:
                logging.warning(f"Redis cache not available for buyer search: {e}")
                cls._cache_client = False  # Mark as unavailable
        return cls._cache_client if cls._cache_client is not False else None
    
    @classmethod
    def _get_rate_limit_client(cls):
        """Get Redis client for rate limiting with lazy initialization."""
        if cls._rate_limit_client is None:
            try:
                cls._rate_limit_client = redis.Redis(
                    host='localhost', 
                    port=6379, 
                    db=3,  # Separate database for search rate limiting
                    decode_responses=True,
                    socket_timeout=2,
                    socket_connect_timeout=2
                )
                cls._rate_limit_client.ping()
                logging.info("Redis rate limit client initialized for buyer search")
            except Exception as e:
                logging.warning(f"Redis rate limiting not available for buyer search: {e}")
                cls._rate_limit_client = False  # Mark as unavailable
        return cls._rate_limit_client if cls._rate_limit_client is not False else None
    
    @classmethod
    def validate_search_query(cls, query: str) -> Tuple[bool, str]:
        """
        Validate search query parameters.
        
        Args:
            query: Search query string
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query:
            return False, "Query is required"
        
        if len(query.strip()) < 2:
            return False, "Query must be at least 2 characters long"
        
        if len(query) > 100:
            return False, "Query must be less than 100 characters"
        
        return True, ""
    
    @classmethod
    def check_rate_limit(cls, user_id: str, limit: int = 10, window: int = 60) -> Tuple[bool, Dict[str, Any]]:
        """
        Check rate limit for search requests.
        
        Args:
            user_id: User making the request
            limit: Maximum requests per window (default: 10)
            window: Time window in seconds (default: 60)
            
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        rate_client = cls._get_rate_limit_client()
        if not rate_client:
            return True, {'rate_limiting': 'disabled'}
        
        try:
            rate_key = f"search_rate:{user_id}"
            current_count = rate_client.get(rate_key)
            
            if current_count is None:
                # First request in window
                rate_client.setex(rate_key, window, 1)
                return True, {
                    'requests_made': 1,
                    'requests_remaining': limit - 1,
                    'reset_time': datetime.utcnow() + timedelta(seconds=window)
                }
            
            current_count = int(current_count)
            
            if current_count >= limit:
                # Rate limit exceeded
                ttl = rate_client.ttl(rate_key)
                return False, {
                    'requests_made': current_count,
                    'requests_remaining': 0,
                    'reset_time': datetime.utcnow() + timedelta(seconds=ttl if ttl > 0 else window),
                    'rate_limit_exceeded': True
                }
            
            # Increment counter
            rate_client.incr(rate_key)
            
            return True, {
                'requests_made': current_count + 1,
                'requests_remaining': limit - (current_count + 1),
                'reset_time': datetime.utcnow() + timedelta(seconds=rate_client.ttl(rate_key))
            }
            
        except Exception as e:
            logging.error(f"Rate limiting error for user {user_id}: {e}")
            return True, {'rate_limiting': 'error', 'error': str(e)}
    
    @classmethod
    def _generate_cache_key(cls, agency_id: str, query: str, limit: int) -> str:
        """Generate cache key for search results."""
        query_hash = hashlib.md5(query.lower().encode()).hexdigest()[:8]
        return f"buyer_search:{agency_id}:{query_hash}:{limit}"
    
    @classmethod
    def _get_cached_results(cls, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached search results."""
        cache_client = cls._get_cache_client()
        if not cache_client:
            return None
        
        try:
            cached_data = cache_client.get(cache_key)
            if cached_data:
                import json
                return json.loads(cached_data)
        except Exception as e:
            logging.error(f"Cache retrieval error: {e}")
        
        return None
    
    @classmethod
    def _cache_results(cls, cache_key: str, results: Dict[str, Any], ttl: int = 300) -> None:
        """Cache search results."""
        cache_client = cls._get_cache_client()
        if not cache_client:
            return
        
        try:
            import json
            cache_client.setex(cache_key, ttl, json.dumps(results))
        except Exception as e:
            logging.error(f"Cache storage error: {e}")
    
    @classmethod
    def _track_search_analytics(cls, user_id: str, agency_id: str, query: str, 
                               results_count: int, search_time_ms: int, cached: bool = False) -> None:
        """
        Track search analytics for monitoring and optimization.
        
        Args:
            user_id: User who performed the search
            agency_id: Agency ID for the search
            query: Search query string
            results_count: Number of results returned
            search_time_ms: Search execution time in milliseconds
            cached: Whether results were served from cache
        """
        try:
            analytics_record = SearchAnalytics(
                user_id=user_id,
                agency_id=agency_id,
                query=query[:255],  # Truncate to fit column limit
                results_count=results_count,
                search_time_ms=search_time_ms,
                cached=cached
            )
            
            db.session.add(analytics_record)
            db.session.commit()
            
            logging.debug(f"Search analytics tracked: user={user_id}, query='{query}', "
                         f"results={results_count}, time={search_time_ms}ms, cached={cached}")
            
        except Exception as e:
            logging.error(f"Failed to track search analytics: {e}")
            # Don't let analytics failure affect the search response
            try:
                db.session.rollback()
            except:
                pass
    
    @classmethod
    def search_buyers(cls, query: str, agency_id: str, user_id: str, limit: int = 20, 
                     suggestion_limit: int = 5) -> Dict[str, Any]:
        """
        Search buyers with fuzzy matching and scoring.
        
        Args:
            query: Search query string
            agency_id: Agency UUID for tenant isolation
            user_id: User ID for analytics tracking
            limit: Maximum number of results (default: 20, max: 50)
            suggestion_limit: Maximum number of suggestions (default: 5)
            
        Returns:
            Dictionary with search results, suggestions, and metadata
        """
        start_time = time.time()
        
        try:
            # Validate inputs
            is_valid, error_msg = cls.validate_search_query(query)
            if not is_valid:
                return {
                    'results': [],
                    'suggestions': [],
                    'total_count': 0,
                    'query': query,
                    'search_time_ms': 0,
                    'error': error_msg
                }
            
            # Limit the maximum results
            limit = min(limit, 50)
            query = query.strip()
            
            # Check cache first
            cache_key = cls._generate_cache_key(agency_id, query, limit)
            cached_results = cls._get_cached_results(cache_key)
            if cached_results:
                search_time_ms = int((time.time() - start_time) * 1000)
                cached_results['search_time_ms'] = search_time_ms
                cached_results['cached'] = True
                
                # Track analytics for cached results
                cls._track_search_analytics(
                    user_id=user_id,
                    agency_id=agency_id,
                    query=query,
                    results_count=cached_results.get('total_count', 0),
                    search_time_ms=search_time_ms,
                    cached=True
                )
                
                return cached_results
            
            # Normalize phone number if query looks like a phone number
            normalized_query = query
            if query.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
                normalized_query = normalize_phone_number(query)
            
            # Build the search query with fuzzy matching
            search_results = cls._execute_search_query(normalized_query, agency_id, limit)
            
            # Get suggestions
            suggestions = cls.get_search_suggestions(query, agency_id, suggestion_limit)
            
            # Format results
            formatted_results = []
            for buyer_data in search_results:
                formatted_result = cls._format_search_result(buyer_data)
                formatted_results.append(formatted_result)
            
            # Prepare response
            search_time_ms = int((time.time() - start_time) * 1000)
            response = {
                'results': formatted_results,
                'suggestions': suggestions,
                'total_count': len(formatted_results),
                'query': query,
                'search_time_ms': search_time_ms,
                'cached': False
            }
            
            # Cache the results
            cls._cache_results(cache_key, response)
            
            # Track analytics for fresh results
            cls._track_search_analytics(
                user_id=user_id,
                agency_id=agency_id,
                query=query,
                results_count=len(formatted_results),
                search_time_ms=search_time_ms,
                cached=False
            )
            
            logging.info(f"Search completed: query='{query}', agency={agency_id}, "
                        f"results={len(formatted_results)}, time={search_time_ms}ms")
            
            return response
            
        except SQLAlchemyError as e:
            logging.error(f"Database error in buyer search: {str(e)}")
            return {
                'results': [],
                'suggestions': [],
                'total_count': 0,
                'query': query,
                'search_time_ms': int((time.time() - start_time) * 1000),
                'error': 'Search service temporarily unavailable'
            }
        except Exception as e:
            logging.error(f"Unexpected error in buyer search: {str(e)}")
            return {
                'results': [],
                'suggestions': [],
                'total_count': 0,
                'query': query,
                'search_time_ms': int((time.time() - start_time) * 1000),
                'error': 'Search failed'
            }
    
    @classmethod
    def _execute_search_query(cls, query: str, agency_id: str, limit: int) -> List[Dict[str, Any]]:
        """
        Execute the actual database search with fuzzy matching and scoring.
        """
        # Create the base query with agency isolation
        base_query = db.session.query(
            cls.model,
            # Calculate match scores for different fields
            func.greatest(
                func.coalesce(func.similarity(cls.model.name, query), 0) * 1.0,  # name weight
                func.coalesce(func.similarity(cls.model.company_name, query), 0) * 0.9,  # company weight
                func.coalesce(func.similarity(cls.model.phone, query), 0) * 0.8,  # phone weight
                func.coalesce(func.similarity(cls.model.email, query), 0) * 0.6   # email weight
            ).label('match_score'),
            # Simple match field indicator (we'll determine this in Python)
            text("'unknown'").label('match_field')
        ).filter(
            cls.model.agency_id == agency_id
        ).filter(
            # Multi-field search conditions
            or_(
                # Exact prefix matches (highest priority)
                cls.model.name.ilike(f'{query}%'),
                cls.model.company_name.ilike(f'{query}%'),
                cls.model.phone.like(f'{query}%'),
                cls.model.email.ilike(f'{query}%'),
                # Fuzzy matches using trigram similarity
                func.similarity(cls.model.name, query) > 0.3,
                func.similarity(cls.model.company_name, query) > 0.3,
                func.similarity(cls.model.phone, query) > 0.3,
                func.similarity(cls.model.email, query) > 0.3,
                # Contains matches
                cls.model.name.ilike(f'%{query}%'),
                cls.model.company_name.ilike(f'%{query}%'),
                cls.model.email.ilike(f'%{query}%')
            )
        ).order_by(
            # Order by match score descending, then by name
            text('match_score DESC'),
            cls.model.name.asc().nullslast()
        ).limit(limit)
        
        # Execute query and get results
        results = base_query.all()
        
        # Convert to list of dictionaries with buyer data and match info
        search_results = []
        for buyer, match_score, match_field in results:
            search_results.append({
                'buyer': buyer,
                'match_score': float(match_score) if match_score else 0.0,
                'query': query  # Include query for match field calculation
            })
        
        return search_results
    
    @classmethod
    def _determine_match_field(cls, buyer, query: str) -> str:
        """
        Determine which field had the best match based on simple string matching.
        This is a simplified version to avoid SQLAlchemy compatibility issues.
        """
        query_lower = query.lower()
        
        # Check for exact matches first
        if buyer.name and query_lower in buyer.name.lower():
            return 'name'
        if buyer.company_name and query_lower in buyer.company_name.lower():
            return 'company_name'
        if buyer.phone and query in buyer.phone:
            return 'phone'
        if buyer.email and query_lower in buyer.email.lower():
            return 'email'
        
        # Check for prefix matches
        if buyer.name and buyer.name.lower().startswith(query_lower):
            return 'name'
        if buyer.company_name and buyer.company_name.lower().startswith(query_lower):
            return 'company_name'
        if buyer.phone and buyer.phone.startswith(query):
            return 'phone'
        if buyer.email and buyer.email.lower().startswith(query_lower):
            return 'email'
        
        # Default to name if no clear match
        return 'name'
    
    @classmethod
    def _format_search_result(cls, buyer_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a single search result with all required fields.
        """
        buyer = buyer_data['buyer']
        match_score = buyer_data['match_score']
        
        # Determine match field based on which field has the highest similarity
        # We'll calculate this in Python to avoid SQLAlchemy compatibility issues
        query = buyer_data.get('query', '')
        match_field = cls._determine_match_field(buyer, query)
        
        # Get last contact information
        last_contacted_at = None
        last_contacted_by = None
        
        try:
            # Get the most recent meeting for this buyer
            latest_meeting = db.session.query(Meeting).filter(
                Meeting.buyer_id == buyer.id
            ).order_by(Meeting.start_time.desc()).first()
            
            if latest_meeting:
                last_contacted_at = latest_meeting.start_time
                if latest_meeting.seller_id:
                    seller = db.session.query(Seller).get(latest_meeting.seller_id)
                    last_contacted_by = seller.name if seller else None
        except Exception as e:
            logging.error(f"Error getting last contact info for buyer {buyer.id}: {e}")
        
        # Get products discussed with interest levels
        products_discussed = []
        try:
            from app.services.buyer_service import BuyerService
            products_discussed = BuyerService._calculate_averaged_products_discussed(str(buyer.id))
        except Exception as e:
            logging.error(f"Error getting products discussed for buyer {buyer.id}: {e}")
        
        return {
            'id': str(buyer.id),
            'name': buyer.name,
            'phone': denormalize_phone_number(buyer.phone) if buyer.phone else None,
            'email': buyer.email,
            'company_name': buyer.company_name,
            'products_discussed': products_discussed,
            'last_contacted_at': last_contacted_at.isoformat() if last_contacted_at else None,
            'last_contacted_by': last_contacted_by,
            'match_score': round(match_score, 3),
            'match_field': match_field
        }
    
    @classmethod
    def get_search_suggestions(cls, query: str, agency_id: str, limit: int = 5) -> List[str]:
        """
        Get search suggestions based on existing buyer data.
        
        Args:
            query: Partial search query
            agency_id: Agency UUID for tenant isolation
            limit: Maximum number of suggestions
            
        Returns:
            List of suggestion strings
        """
        try:
            suggestions = set()
            
            # Get name suggestions
            name_suggestions = db.session.query(cls.model.name).filter(
                and_(
                    cls.model.agency_id == agency_id,
                    cls.model.name.isnot(None),
                    cls.model.name.ilike(f'%{query}%')
                )
            ).distinct().limit(limit).all()
            
            for (name,) in name_suggestions:
                if name and len(suggestions) < limit:
                    suggestions.add(name.strip())
            
            # Get company name suggestions if we need more
            if len(suggestions) < limit:
                company_suggestions = db.session.query(cls.model.company_name).filter(
                    and_(
                        cls.model.agency_id == agency_id,
                        cls.model.company_name.isnot(None),
                        cls.model.company_name.ilike(f'%{query}%')
                    )
                ).distinct().limit(limit - len(suggestions)).all()
                
                for (company_name,) in company_suggestions:
                    if company_name and len(suggestions) < limit:
                        suggestions.add(company_name.strip())
            
            # Get phone suggestions if query looks like a phone number
            if len(suggestions) < limit and any(c.isdigit() for c in query):
                phone_suggestions = db.session.query(cls.model.phone).filter(
                    and_(
                        cls.model.agency_id == agency_id,
                        cls.model.phone.isnot(None),
                        cls.model.phone.like(f'%{query}%')
                    )
                ).distinct().limit(limit - len(suggestions)).all()
                
                for (phone,) in phone_suggestions:
                    if phone and len(suggestions) < limit:
                        suggestions.add(denormalize_phone_number(phone))
            
            return list(suggestions)[:limit]
            
        except SQLAlchemyError as e:
            logging.error(f"Database error getting search suggestions: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Error getting search suggestions: {str(e)}")
            return []
