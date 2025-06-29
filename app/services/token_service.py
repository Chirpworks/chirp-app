import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

from app import db
from app.models.jwt_token_blocklist import TokenBlocklist
from .base_service import BaseService

logging = logging.getLogger(__name__)


class TokenBlocklistService(BaseService):
    """
    Service class for JWT token blacklist management.
    """
    model = TokenBlocklist
    
    @classmethod
    def add_token_to_blocklist(cls, jti: str) -> TokenBlocklist:
        """
        Add a JWT token to the blocklist (blacklist).
        
        Args:
            jti: JWT Token ID (unique identifier)
            
        Returns:
            Created TokenBlocklist instance
        """
        try:
            # Check if token is already blocklisted
            existing_token = cls.model.query.filter_by(jti=jti).first()
            if existing_token:
                logging.info(f"Token {jti} is already blocklisted")
                return existing_token
            
            token_blocklist = TokenBlocklist(jti=jti)
            db.session.add(token_blocklist)
            db.session.flush()
            
            logging.info(f"Added token {jti} to blocklist")
            return token_blocklist
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to add token {jti} to blocklist: {str(e)}")
            raise
    
    @classmethod
    def is_token_blocklisted(cls, jti: str) -> bool:
        """
        Check if a JWT token is in the blocklist.
        
        Args:
            jti: JWT Token ID
            
        Returns:
            True if token is blocklisted, False otherwise
        """
        try:
            token_exists = db.session.query(cls.model.id).filter_by(jti=jti).first() is not None
            
            if token_exists:
                logging.info(f"Token {jti} is blocklisted")
            else:
                logging.debug(f"Token {jti} is not blocklisted")
                
            return token_exists
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to check token blocklist status for {jti}: {str(e)}")
            raise
    
    @classmethod
    def remove_token_from_blocklist(cls, jti: str) -> bool:
        """
        Remove a JWT token from the blocklist (unblock).
        Use with caution - this effectively reactivates a previously blocked token.
        
        Args:
            jti: JWT Token ID
            
        Returns:
            True if token was removed, False if not found
        """
        try:
            token_record = cls.model.query.filter_by(jti=jti).first()
            if not token_record:
                logging.warning(f"Token {jti} not found in blocklist")
                return False
            
            db.session.delete(token_record)
            db.session.flush()
            
            logging.warning(f"REMOVED token {jti} from blocklist - token is now active!")
            return True
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to remove token {jti} from blocklist: {str(e)}")
            raise
    
    @classmethod
    def get_blocklisted_tokens(cls, limit: int = 100, offset: int = 0) -> List[TokenBlocklist]:
        """
        Get a list of blocklisted tokens.
        
        Args:
            limit: Maximum number of tokens to return
            offset: Number of tokens to skip
            
        Returns:
            List of TokenBlocklist instances
        """
        try:
            tokens = (
                cls.model.query
                .order_by(cls.model.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            
            logging.info(f"Retrieved {len(tokens)} blocklisted tokens")
            return tokens
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get blocklisted tokens: {str(e)}")
            raise
    
    @classmethod
    def get_blocklist_statistics(cls) -> Dict[str, Any]:
        """
        Get statistics about the token blocklist.
        
        Returns:
            Dictionary with blocklist statistics
        """
        try:
            total_tokens = cls.model.query.count()
            
            # Tokens added in last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            recent_tokens = (
                cls.model.query
                .filter(cls.model.created_at >= yesterday)
                .count()
            )
            
            # Tokens added in last 7 days
            last_week = datetime.utcnow() - timedelta(days=7)
            weekly_tokens = (
                cls.model.query
                .filter(cls.model.created_at >= last_week)
                .count()
            )
            
            # Oldest and newest tokens
            oldest_token = cls.model.query.order_by(cls.model.created_at.asc()).first()
            newest_token = cls.model.query.order_by(cls.model.created_at.desc()).first()
            
            statistics = {
                'total_blocklisted_tokens': total_tokens,
                'tokens_added_last_24h': recent_tokens,
                'tokens_added_last_7d': weekly_tokens,
                'oldest_token_date': oldest_token.created_at.isoformat() if oldest_token else None,
                'newest_token_date': newest_token.created_at.isoformat() if newest_token else None
            }
            
            logging.info(f"Generated blocklist statistics: {statistics}")
            return statistics
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get blocklist statistics: {str(e)}")
            raise
    
    @classmethod
    def cleanup_old_tokens(cls, days_old: int = 30) -> int:
        """
        Remove old tokens from the blocklist to keep it manageable.
        Tokens older than the specified days will be removed.
        
        Args:
            days_old: Number of days to keep tokens (default 30)
            
        Returns:
            Number of tokens removed
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            old_tokens = cls.model.query.filter(cls.model.created_at < cutoff_date).all()
            tokens_count = len(old_tokens)
            
            for token in old_tokens:
                db.session.delete(token)
            
            logging.info(f"Cleaned up {tokens_count} old tokens from blocklist (older than {days_old} days)")
            return tokens_count
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to cleanup old tokens: {str(e)}")
            raise
    
    @classmethod
    def bulk_add_tokens(cls, jtis: List[str]) -> int:
        """
        Add multiple tokens to the blocklist in bulk.
        
        Args:
            jtis: List of JWT Token IDs
            
        Returns:
            Number of tokens successfully added (excluding duplicates)
        """
        try:
            # Get existing tokens to avoid duplicates
            existing_jtis = set(
                token.jti for token in cls.model.query.filter(cls.model.jti.in_(jtis)).all()
            )
            
            # Filter out existing tokens
            new_jtis = [jti for jti in jtis if jti not in existing_jtis]
            
            # Bulk insert new tokens
            new_tokens = [TokenBlocklist(jti=jti) for jti in new_jtis]
            db.session.bulk_save_objects(new_tokens)
            db.session.flush()
            
            added_count = len(new_tokens)
            duplicate_count = len(jtis) - added_count
            
            logging.info(f"Bulk added {added_count} tokens to blocklist, skipped {duplicate_count} duplicates")
            return added_count
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to bulk add tokens to blocklist: {str(e)}")
            raise
    
    @classmethod
    def search_tokens_by_date(cls, start_date: datetime, end_date: datetime = None) -> List[TokenBlocklist]:
        """
        Search for tokens blocklisted within a date range.
        
        Args:
            start_date: Start date for search
            end_date: End date for search (defaults to now)
            
        Returns:
            List of TokenBlocklist instances
        """
        try:
            if end_date is None:
                end_date = datetime.utcnow()
            
            tokens = (
                cls.model.query
                .filter(and_(
                    cls.model.created_at >= start_date,
                    cls.model.created_at <= end_date
                ))
                .order_by(cls.model.created_at.desc())
                .all()
            )
            
            logging.info(f"Found {len(tokens)} tokens blocklisted between {start_date} and {end_date}")
            return tokens
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to search tokens by date: {str(e)}")
            raise
    
    @classmethod
    def get_token_info(cls, jti: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific blocklisted token.
        
        Args:
            jti: JWT Token ID
            
        Returns:
            Dictionary with token information or None if not found
        """
        try:
            token = cls.model.query.filter_by(jti=jti).first()
            if not token:
                logging.warning(f"Token {jti} not found in blocklist")
                return None
            
            token_info = {
                'id': str(token.id),
                'jti': token.jti,
                'created_at': token.created_at.isoformat(),
                'days_since_blocked': (datetime.utcnow() - token.created_at).days,
                'is_blocklisted': True
            }
            
            logging.info(f"Retrieved token info for {jti}")
            return token_info
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get token info for {jti}: {str(e)}")
            raise 