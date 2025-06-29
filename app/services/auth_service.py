import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from flask_jwt_extended import get_jwt_identity, get_jwt

from app.models.seller import Seller
from app.utils.auth_utils import generate_secure_otp, send_otp_email, generate_user_claims
from .seller_service import SellerService
from .token_service import TokenBlocklistService

logging = logging.getLogger(__name__)


class AuthService:
    """
    Service class for authentication operations and utilities.
    Consolidates authentication logic and provides high-level auth operations.
    """
    
    @classmethod
    def authenticate_user(cls, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with email and password.
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Dictionary with user info and tokens, or None if authentication fails
        """
        try:
            # Use SellerService for authentication
            user = SellerService.validate_credentials(email, password)
            if not user:
                logging.warning(f"Authentication failed for email: {email}")
                return None
            
            # Generate tokens
            tokens = cls.generate_tokens_for_user(user)
            if not tokens:
                logging.error(f"Failed to generate tokens for user: {email}")
                return None
            
            auth_result = {
                'user': {
                    'id': str(user.id),
                    'name': user.name,
                    'email': user.email,
                    'phone': user.phone,
                    'role': user.role.value if user.role else None,
                    'agency_id': str(user.agency_id) if user.agency_id else None
                },
                'tokens': tokens
            }
            
            logging.info(f"Successfully authenticated user: {email}")
            return auth_result
            
        except Exception as e:
            logging.error(f"Authentication error for {email}: {str(e)}")
            return None
    
    @classmethod
    def generate_tokens_for_user(cls, user: Seller) -> Optional[Dict[str, str]]:
        """
        Generate access and refresh tokens for a user.
        
        Args:
            user: Seller instance
            
        Returns:
            Dictionary with access_token and refresh_token, or None if generation fails
        """
        try:
            # Generate user claims
            user_claims = generate_user_claims(user)
            
            # Generate tokens using SellerService
            access_token = user.generate_access_token(
                expires_delta=timedelta(minutes=15), 
                additional_claims=user_claims
            )
            refresh_token = user.generate_refresh_token()
            
            tokens = {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'Bearer',
                'expires_in': 900  # 15 minutes in seconds
            }
            
            logging.info(f"Generated tokens for user: {user.email}")
            return tokens
            
        except Exception as e:
            logging.error(f"Failed to generate tokens for user {user.email}: {str(e)}")
            return None
    
    @classmethod
    def refresh_user_tokens(cls, user_id: str) -> Optional[Dict[str, str]]:
        """
        Refresh tokens for a user (typically called with refresh token).
        
        Args:
            user_id: User's UUID
            
        Returns:
            Dictionary with new tokens, or None if refresh fails
        """
        try:
            # Get user
            user = SellerService.get_by_id(user_id)
            if not user:
                logging.warning(f"User not found for token refresh: {user_id}")
                return None
            
            # Generate new tokens
            tokens = cls.generate_tokens_for_user(user)
            if not tokens:
                logging.error(f"Failed to refresh tokens for user: {user_id}")
                return None
            
            logging.info(f"Refreshed tokens for user: {user.email}")
            return tokens
            
        except Exception as e:
            logging.error(f"Token refresh error for user {user_id}: {str(e)}")
            return None
    
    @classmethod
    def logout_user(cls, jti: str = None) -> bool:
        """
        Logout a user by adding their current token to the blocklist.
        
        Args:
            jti: JWT Token ID (if not provided, will get from current request)
            
        Returns:
            True if logout successful, False otherwise
        """
        try:
            # Get token ID if not provided
            if not jti:
                try:
                    jti = get_jwt()["jti"]
                except Exception as e:
                    logging.error(f"Failed to get JWT from request: {str(e)}")
                    return False
            
            # Add token to blocklist
            TokenBlocklistService.add_token_to_blocklist(jti)
            
            logging.info(f"User logged out successfully, token {jti} blocklisted")
            return True
            
        except Exception as e:
            logging.error(f"Logout error: {str(e)}")
            return False
    
    @classmethod
    def is_token_valid(cls, jti: str) -> bool:
        """
        Check if a token is valid (not blocklisted).
        
        Args:
            jti: JWT Token ID
            
        Returns:
            True if token is valid, False if blocklisted
        """
        try:
            return not TokenBlocklistService.is_token_blocklisted(jti)
        except Exception as e:
            logging.error(f"Token validation error for {jti}: {str(e)}")
            return False
    
    @classmethod
    def get_current_user(cls) -> Optional[Seller]:
        """
        Get the current authenticated user from JWT context.
        
        Returns:
            Seller instance or None if not authenticated
        """
        try:
            user_id = get_jwt_identity()
            if not user_id:
                return None
            
            user = SellerService.get_by_id(user_id)
            return user
            
        except Exception as e:
            logging.error(f"Failed to get current user: {str(e)}")
            return None
    
    @classmethod
    def generate_and_send_otp(cls, email: str) -> Optional[str]:
        """
        Generate and send OTP to user's email.
        
        Args:
            email: User's email address
            
        Returns:
            Generated OTP string or None if failed
        """
        try:
            # Check if user exists
            user = SellerService.get_by_email(email)
            if not user:
                logging.warning(f"OTP requested for non-existent user: {email}")
                return None
            
            # Generate OTP
            otp = generate_secure_otp()
            
            # Send OTP email
            email_sent = send_otp_email(email, otp)
            if not email_sent:
                logging.error(f"Failed to send OTP email to: {email}")
                return None
            
            logging.info(f"OTP generated and sent to: {email}")
            return otp
            
        except Exception as e:
            logging.error(f"OTP generation error for {email}: {str(e)}")
            return None
    
    @classmethod
    def verify_otp_and_authenticate(cls, email: str, provided_otp: str, expected_otp: str) -> Optional[Dict[str, Any]]:
        """
        Verify OTP and authenticate user if OTP is correct.
        
        Args:
            email: User's email address
            provided_otp: OTP provided by user
            expected_otp: Expected OTP value
            
        Returns:
            Authentication result dictionary or None if verification fails
        """
        try:
            # Verify OTP
            if provided_otp != expected_otp:
                logging.warning(f"Invalid OTP provided for {email}")
                return None
            
            # Get user
            user = SellerService.get_by_email(email)
            if not user:
                logging.warning(f"User not found during OTP verification: {email}")
                return None
            
            # Generate tokens
            tokens = cls.generate_tokens_for_user(user)
            if not tokens:
                logging.error(f"Failed to generate tokens after OTP verification for: {email}")
                return None
            
            auth_result = {
                'user': {
                    'id': str(user.id),
                    'name': user.name,
                    'email': user.email,
                    'phone': user.phone,
                    'role': user.role.value if user.role else None,
                    'agency_id': str(user.agency_id) if user.agency_id else None
                },
                'tokens': tokens,
                'auth_method': 'otp'
            }
            
            logging.info(f"Successfully authenticated user via OTP: {email}")
            return auth_result
            
        except Exception as e:
            logging.error(f"OTP verification error for {email}: {str(e)}")
            return None
    
    @classmethod
    def change_user_password(cls, user_id: str, old_password: str, new_password: str) -> bool:
        """
        Change user password after verifying old password.
        
        Args:
            user_id: User's UUID
            old_password: Current password
            new_password: New password
            
        Returns:
            True if password changed successfully, False otherwise
        """
        try:
            # Get user
            user = SellerService.get_by_id(user_id)
            if not user:
                logging.warning(f"User not found for password change: {user_id}")
                return False
            
            # Verify old password
            if not user.check_password(old_password):
                logging.warning(f"Invalid old password provided for user: {user_id}")
                return False
            
            # Update password using SellerService
            success = SellerService.update_password(user_id, new_password)
            if success:
                logging.info(f"Password changed successfully for user: {user_id}")
                return True
            else:
                logging.error(f"Failed to update password for user: {user_id}")
                return False
                
        except Exception as e:
            logging.error(f"Password change error for user {user_id}: {str(e)}")
            return False
    
    @classmethod
    def get_auth_statistics(cls) -> Dict[str, Any]:
        """
        Get authentication-related statistics.
        
        Returns:
            Dictionary with authentication statistics
        """
        try:
            # Get token statistics
            token_stats = TokenBlocklistService.get_blocklist_statistics()
            
            # Get user statistics
            total_users = SellerService.get_all_count()
            active_users = SellerService.get_active_users_count()
            
            # Combine statistics
            auth_stats = {
                'total_users': total_users,
                'active_users': active_users,
                'inactive_users': total_users - active_users,
                'token_statistics': token_stats,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logging.info("Generated authentication statistics")
            return auth_stats
            
        except Exception as e:
            logging.error(f"Failed to get auth statistics: {str(e)}")
            return {}
    
    @classmethod
    def bulk_logout_users(cls, user_ids: list) -> Dict[str, Any]:
        """
        Logout multiple users by invalidating their tokens.
        Note: This is a security operation that should be used carefully.
        
        Args:
            user_ids: List of user UUIDs to logout
            
        Returns:
            Dictionary with operation results
        """
        try:
            # This is a simplified implementation
            # In a real scenario, you'd need to track active tokens per user
            # For now, we'll just return the count
            
            valid_users = 0
            for user_id in user_ids:
                user = SellerService.get_by_id(user_id)
                if user:
                    valid_users += 1
            
            result = {
                'requested_users': len(user_ids),
                'valid_users': valid_users,
                'invalid_users': len(user_ids) - valid_users,
                'note': 'Bulk logout requires additional token tracking implementation'
            }
            
            logging.warning(f"Bulk logout requested for {len(user_ids)} users")
            return result
            
        except Exception as e:
            logging.error(f"Bulk logout error: {str(e)}")
            return {'error': str(e)}
    
    @classmethod
    def cleanup_expired_tokens(cls, days_old: int = 30) -> int:
        """
        Clean up expired tokens from the blocklist.
        
        Args:
            days_old: Number of days to keep tokens
            
        Returns:
            Number of tokens cleaned up
        """
        try:
            cleaned_count = TokenBlocklistService.cleanup_old_tokens(days_old)
            logging.info(f"Cleaned up {cleaned_count} expired tokens")
            return cleaned_count
            
        except Exception as e:
            logging.error(f"Token cleanup error: {str(e)}")
            return 0 