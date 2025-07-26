import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

from app import db
from app.models.exotel_calls import ExotelCall
from app.models.mobile_app_calls import MobileAppCall
from app.utils.call_recording_utils import normalize_phone_number, calculate_call_status
from app.constants import MobileAppCallStatus
from .base_service import BaseService

logging = logging.getLogger(__name__)


class CallService(BaseService):
    """
    Service class for call record management (both ExotelCall and MobileAppCall).
    This service doesn't inherit from BaseService for a single model since it manages two models.
    """
    
    @classmethod
    def create_exotel_call(cls, call_from: str, start_time: datetime, end_time: datetime,
                          duration: int, call_recording_url: str) -> ExotelCall:
        """
        Create a new ExotelCall record.
        
        Args:
            call_from: Caller's phone number (will be normalized)
            start_time: Call start time
            end_time: Call end time
            duration: Call duration in seconds (integer)
            call_recording_url: URL to the call recording
            
        Returns:
            Created ExotelCall instance
        """
        try:
            normalized_phone = normalize_phone_number(call_from)
            
            exotel_call = ExotelCall()
            exotel_call.call_from = normalized_phone
            exotel_call.start_time = start_time
            exotel_call.end_time = end_time
            exotel_call.duration = int(duration)  # Ensure integer type
            exotel_call.call_recording_url = call_recording_url
            
            db.session.add(exotel_call)
            db.session.commit()  # Commit the transaction
            
            logging.info(f"Created ExotelCall with ID: {exotel_call.id}")
            return exotel_call
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create ExotelCall: {str(e)}")
            db.session.rollback()
            raise
    
    @classmethod
    def create_mobile_app_call(cls, mobile_app_call_id: int, buyer_number: str, seller_number: str,
                              call_type: str, start_time: datetime, end_time: datetime,
                              duration: int, user_id: str) -> MobileAppCall:
        """
        Create a new MobileAppCall record.
        
        Args:
            mobile_app_call_id: App-specific call ID
            buyer_number: Buyer's phone number (will be normalized)
            seller_number: Seller's phone number (will be normalized)
            call_type: Type of call (incoming/outgoing)
            start_time: Call start time
            end_time: Call end time
            duration: Call duration in seconds (integer)
            user_id: Seller's UUID
            
        Returns:
            Created MobileAppCall instance
        """
        try:
            normalized_buyer = normalize_phone_number(buyer_number)
            normalized_seller = normalize_phone_number(seller_number)
            
            # Calculate call status
            status = calculate_call_status(call_type, str(duration))  # Convert to string for status calculation
            
            mobile_call = MobileAppCall()
            mobile_call.mobile_app_call_id = mobile_app_call_id
            mobile_call.buyer_number = normalized_buyer
            mobile_call.seller_number = normalized_seller
            mobile_call.call_type = call_type
            mobile_call.start_time = start_time
            mobile_call.end_time = end_time
            mobile_call.duration = int(duration)  # Ensure integer type
            mobile_call.user_id = user_id
            mobile_call.status = status
            
            db.session.add(mobile_call)
            db.session.commit()  # Commit the transaction
            
            logging.info(f"Created MobileAppCall with ID: {mobile_call.id}")
            return mobile_call
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create MobileAppCall: {str(e)}")
            db.session.rollback()
            raise
    
    @classmethod
    def find_matching_exotel_call(cls, seller_number: str, start_time: datetime, end_time: datetime) -> Optional[ExotelCall]:
        """
        Find an ExotelCall that matches the given criteria for reconciliation.
        
        Args:
            seller_number: Seller's phone number
            start_time: Expected start time window
            end_time: Expected end time window
            
        Returns:
            Matching ExotelCall instance or None
        """
        try:
            normalized_seller = normalize_phone_number(seller_number)
            
            matching_call = (
                ExotelCall.query
                .filter(and_(
                    ExotelCall.call_from == normalized_seller,
                    ExotelCall.start_time >= start_time,
                    ExotelCall.end_time <= end_time,
                ))
                .order_by(ExotelCall.start_time.asc())
                .first()
            )
            
            if matching_call:
                logging.info(f"Found matching ExotelCall: {matching_call.id}")
            else:
                logging.info(f"No matching ExotelCall found for seller {normalized_seller}")
                
            return matching_call
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to find matching ExotelCall: {str(e)}")
            raise
    
    @classmethod
    def find_matching_mobile_app_call(cls, seller_number: str, start_time: datetime, end_time: datetime) -> Optional[MobileAppCall]:
        """
        Find a MobileAppCall that matches the given criteria for reconciliation.
        
        Args:
            seller_number: Seller's phone number
            start_time: Expected start time window
            end_time: Expected end time window
            
        Returns:
            Matching MobileAppCall instance or None
        """
        try:
            normalized_seller = normalize_phone_number(seller_number)
            
            matching_call = (
                MobileAppCall.query
                .filter(and_(
                    MobileAppCall.seller_number == normalized_seller,
                    MobileAppCall.start_time <= start_time,
                    MobileAppCall.end_time >= end_time,
                ))
                .order_by(MobileAppCall.start_time.asc())
                .first()
            )
            
            if matching_call:
                logging.info(f"Found matching MobileAppCall: {matching_call.id}")
            else:
                logging.info(f"No matching MobileAppCall found for seller {normalized_seller}")
                
            return matching_call
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to find matching MobileAppCall: {str(e)}")
            raise
    
    @classmethod
    def delete_exotel_call(cls, exotel_call: ExotelCall) -> bool:
        """
        Delete an ExotelCall record.
        
        Args:
            exotel_call: ExotelCall instance to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            db.session.delete(exotel_call)
            db.session.commit()  # Commit the transaction
            logging.info(f"Deleted ExotelCall: {exotel_call.id}")
            return True
        except SQLAlchemyError as e:
            logging.error(f"Failed to delete ExotelCall {exotel_call.id}: {str(e)}")
            db.session.rollback()
            raise
    
    @classmethod
    def delete_mobile_app_call(cls, mobile_call: MobileAppCall) -> bool:
        """
        Delete a MobileAppCall record.
        
        Args:
            mobile_call: MobileAppCall instance to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            db.session.delete(mobile_call)
            db.session.commit()  # Commit the transaction
            logging.info(f"Deleted MobileAppCall: {mobile_call.id}")
            return True
        except SQLAlchemyError as e:
            logging.error(f"Failed to delete MobileAppCall {mobile_call.id}: {str(e)}")
            db.session.rollback()
            raise
    
    @classmethod
    def get_exotel_calls_by_seller(cls, seller_number: str, date_range: Optional[Dict[str, datetime]] = None) -> List[ExotelCall]:
        """
        Get ExotelCall records for a specific seller.
        
        Args:
            seller_number: Seller's phone number
            date_range: Optional date range filter
            
        Returns:
            List of ExotelCall instances
        """
        try:
            normalized_seller = normalize_phone_number(seller_number)
            
            query = ExotelCall.query.filter_by(call_from=normalized_seller)
            
            if date_range:
                query = query.filter(
                    and_(
                        ExotelCall.start_time >= date_range['start'],
                        ExotelCall.start_time <= date_range['end']
                    )
                )
            
            calls = query.order_by(ExotelCall.start_time.desc()).all()
            logging.info(f"Found {len(calls)} ExotelCalls for seller {normalized_seller}")
            return calls
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get ExotelCalls for seller {seller_number}: {str(e)}")
            raise
    
    @classmethod
    def get_mobile_app_calls_by_user(cls, user_id: str, date_range: Optional[Dict[str, datetime]] = None) -> List[MobileAppCall]:
        """
        Get MobileAppCall records for a specific user.
        
        Args:
            user_id: User's UUID
            date_range: Optional date range filter
            
        Returns:
            List of MobileAppCall instances
        """
        try:
            query = MobileAppCall.query.filter_by(user_id=user_id)
            
            if date_range:
                query = query.filter(
                    and_(
                        MobileAppCall.start_time >= date_range['start'],
                        MobileAppCall.start_time <= date_range['end']
                    )
                )
            
            calls = query.order_by(MobileAppCall.start_time.desc()).all()
            logging.info(f"Found {len(calls)} MobileAppCalls for user {user_id}")
            return calls
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get MobileAppCalls for user {user_id}: {str(e)}")
            raise
    
    @classmethod
    def get_mobile_app_calls_by_seller_phone(cls, seller_number: str, date_range: Optional[Dict[str, datetime]] = None) -> List[MobileAppCall]:
        """
        Get MobileAppCall records for a specific seller by phone number.
        
        Args:
            seller_number: Seller's phone number
            date_range: Optional date range filter
            
        Returns:
            List of MobileAppCall instances
        """
        try:
            normalized_seller = normalize_phone_number(seller_number)
            
            query = MobileAppCall.query.filter_by(seller_number=normalized_seller)
            
            if date_range:
                query = query.filter(
                    and_(
                        MobileAppCall.start_time >= date_range['start'],
                        MobileAppCall.start_time <= date_range['end']
                    )
                )
            
            calls = query.order_by(MobileAppCall.start_time.desc()).all()
            logging.info(f"Found {len(calls)} MobileAppCalls for seller {normalized_seller}")
            return calls
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get MobileAppCalls for seller {seller_number}: {str(e)}")
            raise
    
    @classmethod
    def get_last_mobile_app_call_by_seller(cls, seller_number: str) -> Optional[MobileAppCall]:
        """
        Get the most recent MobileAppCall for a specific seller by phone number.
        
        Args:
            seller_number: Seller's phone number
            
        Returns:
            Most recent MobileAppCall instance or None if not found
        """
        try:
            normalized_seller = normalize_phone_number(seller_number)
            
            last_call = (
                MobileAppCall.query
                .filter_by(seller_number=normalized_seller)
                .order_by(MobileAppCall.start_time.desc())
                .first()
            )
            
            if last_call:
                logging.info(f"Found last MobileAppCall for seller {normalized_seller}: {last_call.id}")
            else:
                logging.info(f"No MobileAppCall found for seller {normalized_seller}")
                
            return last_call
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get last MobileAppCall for seller {seller_number}: {str(e)}")
            raise
    
    @classmethod
    def get_mobile_app_call_by_app_call_id(cls, mobile_app_call_id: str) -> Optional[MobileAppCall]:
        """
        Get a MobileAppCall by its mobile_app_call_id.
        
        Args:
            mobile_app_call_id: The app-specific call ID
            
        Returns:
            MobileAppCall instance or None if not found
        """
        try:
            mobile_call = (
                MobileAppCall.query
                .filter_by(mobile_app_call_id=mobile_app_call_id)
                .first()
            )
            
            if mobile_call:
                logging.info(f"Found MobileAppCall with app_call_id {mobile_app_call_id}: {mobile_call.id}")
            else:
                logging.debug(f"No MobileAppCall found with app_call_id {mobile_app_call_id}")
                
            return mobile_call
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get MobileAppCall by app_call_id {mobile_app_call_id}: {str(e)}")
            raise
    
    @classmethod
    def get_unmatched_calls(cls, age_threshold_minutes: int = 30) -> Tuple[List[ExotelCall], List[MobileAppCall]]:
        """
        Get calls that haven't been matched/reconciled and are older than threshold.
        
        Args:
            age_threshold_minutes: Minimum age in minutes for calls to be considered unmatched
            
        Returns:
            Tuple of (unmatched_exotel_calls, unmatched_mobile_calls)
        """
        try:
            threshold_time = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(minutes=age_threshold_minutes)
            
            # Get old ExotelCalls (these are temporary records that should be matched)
            unmatched_exotel = (
                ExotelCall.query
                .filter(ExotelCall.start_time < threshold_time)
                .order_by(ExotelCall.start_time.asc())
                .all()
            )
            
            # Get old MobileAppCalls with 'Processing' status that haven't been matched
            unmatched_mobile = (
                MobileAppCall.query
                .filter(
                    and_(
                        MobileAppCall.start_time < threshold_time,
                        MobileAppCall.status == MobileAppCallStatus.PROCESSING.value
                    )
                )
                .order_by(MobileAppCall.start_time.asc())
                .all()
            )
            
            logging.info(f"Found {len(unmatched_exotel)} unmatched ExotelCalls and {len(unmatched_mobile)} unmatched MobileAppCalls")
            return unmatched_exotel, unmatched_mobile
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get unmatched calls: {str(e)}")
            raise
    
    @classmethod
    def update_mobile_call_status(cls, mobile_call_id: str, status: str) -> Optional[MobileAppCall]:
        """
        Update the status of a MobileAppCall.
        
        Args:
            mobile_call_id: MobileAppCall UUID
            status: New status string
            
        Returns:
            Updated MobileAppCall instance or None if not found
        """
        try:
            mobile_call = MobileAppCall.query.get(mobile_call_id)
            if not mobile_call:
                logging.warning(f"MobileAppCall not found: {mobile_call_id}")
                return None
            
            mobile_call.status = status
            db.session.commit()  # Commit the transaction
            
            logging.info(f"Updated MobileAppCall {mobile_call_id} status to {status}")
            return mobile_call
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to update MobileAppCall {mobile_call_id} status: {str(e)}")
            db.session.rollback()
            raise
    
    @classmethod
    def get_call_statistics(cls, seller_number: Optional[str] = None, date_range: Optional[Dict[str, datetime]] = None) -> Dict[str, Any]:
        """
        Get call statistics for a seller or all sellers.
        
        Args:
            seller_number: Optional seller phone number to filter by
            date_range: Optional date range filter
            
        Returns:
            Dictionary with call statistics
        """
        try:
            # Build filter conditions
            exotel_filters = []
            mobile_filters = []
            
            if seller_number:
                normalized_seller = normalize_phone_number(seller_number)
                exotel_filters.append(ExotelCall.call_from == normalized_seller)
                mobile_filters.append(MobileAppCall.seller_number == normalized_seller)
            
            if date_range:
                exotel_filters.extend([
                    ExotelCall.start_time >= date_range['start'],
                    ExotelCall.start_time <= date_range['end']
                ])
                mobile_filters.extend([
                    MobileAppCall.start_time >= date_range['start'],
                    MobileAppCall.start_time <= date_range['end']
                ])
            
            # Get ExotelCall statistics
            exotel_query = ExotelCall.query
            if exotel_filters:
                exotel_query = exotel_query.filter(and_(*exotel_filters))
            exotel_calls = exotel_query.all()
            
            # Get MobileAppCall statistics
            mobile_query = MobileAppCall.query
            if mobile_filters:
                mobile_query = mobile_query.filter(and_(*mobile_filters))
            mobile_calls = mobile_query.all()
            
            # Calculate statistics
            total_exotel_calls = len(exotel_calls)
            total_mobile_calls = len(mobile_calls)
            
            # Mobile call status breakdown
            mobile_status_counts = {}
            for call in mobile_calls:
                status = call.status
                mobile_status_counts[status] = mobile_status_counts.get(status, 0) + 1
            
            statistics = {
                'total_exotel_calls': total_exotel_calls,
                'total_mobile_calls': total_mobile_calls,
                'mobile_call_status_breakdown': mobile_status_counts,
                'total_calls': total_exotel_calls + total_mobile_calls
            }
            
            logging.info(f"Generated call statistics: {statistics}")
            return statistics
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get call statistics: {str(e)}")
            raise
    
    @classmethod
    def cleanup_old_unmatched_calls(cls, days_old: int = 7) -> Tuple[int, int]:
        """
        Clean up old unmatched calls that are older than specified days.
        
        Args:
            days_old: Number of days to keep unmatched calls
            
        Returns:
            Tuple of (exotel_deleted_count, mobile_deleted_count)
        """
        try:
            cutoff_date = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(days=days_old)
            
            # Delete old ExotelCalls
            old_exotel_calls = ExotelCall.query.filter(ExotelCall.start_time < cutoff_date).all()
            exotel_count = len(old_exotel_calls)
            for call in old_exotel_calls:
                db.session.delete(call)
            
            # Delete old MobileAppCalls with non-final status
            old_mobile_calls = MobileAppCall.query.filter(
                and_(
                    MobileAppCall.start_time < cutoff_date,
                    MobileAppCall.status.in_([MobileAppCallStatus.PROCESSING.value, MobileAppCallStatus.NOT_ANSWERED.value, MobileAppCallStatus.MISSED.value])
                )
            ).all()
            mobile_count = len(old_mobile_calls)
            for call in old_mobile_calls:
                db.session.delete(call)
            
            logging.info(f"Cleaned up {exotel_count} old ExotelCalls and {mobile_count} old MobileAppCalls")
            return exotel_count, mobile_count
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to cleanup old calls: {str(e)}")
            raise
    
    @classmethod
    def commit_with_rollback(cls) -> bool:
        """
        Commit the current transaction with automatic rollback on failure.
        
        Returns:
            True if commit successful, False if rolled back
        """
        try:
            db.session.commit()
            logging.info("Call service transaction committed successfully")
            return True
        except SQLAlchemyError as e:
            logging.error(f"Call service transaction failed, rolling back: {str(e)}")
            db.session.rollback()
            return False
    
    @classmethod
    def rollback(cls):
        """
        Rollback the current transaction.
        """
        try:
            db.session.rollback()
            logging.info("Call service transaction rolled back")
        except SQLAlchemyError as e:
            logging.error(f"Failed to rollback call service transaction: {str(e)}")
