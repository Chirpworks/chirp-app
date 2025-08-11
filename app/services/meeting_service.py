import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

from app.models.meeting import Meeting
from app.models.seller import Seller
from app.models.buyer import Buyer
from app.models.mobile_app_calls import MobileAppCall
from app.models.job import JobStatus
from app.constants import CallDirection, MeetingSource, MobileAppCallStatus
from app.utils.call_recording_utils import denormalize_phone_number, normalize_phone_number
from .base_service import BaseService

logging = logging.getLogger(__name__)


def human_readable_duration(end_time: datetime, start_time: datetime) -> str:
    """Helper function to calculate human readable duration from start and end times"""
    if not end_time or not start_time:
        return "N/A"
    
    duration = end_time - start_time
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"


class MeetingService(BaseService):
    """
    Service class for all meeting-related database operations and business logic.
    """
    model = Meeting
    
    @classmethod
    def create_meeting(cls, buyer_id: str, seller_id: str, title: str, 
                      start_time: datetime, **kwargs) -> Meeting:
        """
        Create a new meeting with required relationships.
        
        Args:
            buyer_id: Buyer UUID
            seller_id: Seller UUID
            title: Meeting title
            start_time: Meeting start time
            **kwargs: Additional meeting fields
            
        Returns:
            Created Meeting instance
        """
        try:
            meeting_data = {
                'buyer_id': buyer_id,
                'seller_id': seller_id,
                'title': title,
                'start_time': start_time,
                'source': kwargs.get('source', MeetingSource.PHONE),
                **kwargs
            }
            
            meeting = cls.create(**meeting_data)
            logging.info(f"Created meeting: {title} with ID: {meeting.id}")
            return meeting
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create meeting {title}: {str(e)}")
            raise
    
    @classmethod
    def get_meeting_with_job(cls, meeting_id: str) -> Optional[Meeting]:
        """
        Get meeting with its associated job.
        
        Args:
            meeting_id: Meeting UUID
            
        Returns:
            Meeting instance with job relationship loaded
        """
        try:
            meeting = cls.model.query.filter_by(id=meeting_id).first()
            if meeting:
                # Accessing job attribute loads the relationship
                job = meeting.job
                logging.info(f"Found meeting with job: {meeting_id}")
            else:
                logging.warning(f"Meeting not found: {meeting_id}")
            return meeting
        except SQLAlchemyError as e:
            logging.error(f"Failed to get meeting with job {meeting_id}: {str(e)}")
            raise
    
    @classmethod
    def get_meetings_by_seller(cls, seller_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Meeting]:
        """
        Get all meetings for a specific seller with optional filters.
        
        Args:
            seller_id: Seller UUID
            filters: Optional filters (date_range, status, etc.)
            
        Returns:
            List of Meeting instances
        """
        try:
            query = cls.model.query.filter_by(seller_id=seller_id)
            
            if filters:
                # Apply date filters
                if 'start_date' in filters and 'end_date' in filters:
                    query = query.filter(
                        and_(
                            cls.model.start_time >= filters['start_date'],
                            cls.model.start_time <= filters['end_date']
                        )
                    )
                
                # Note: Meeting model doesn't have a status field
                # Status is tracked through the associated Job model
                # Apply status filter (if needed, filter through job relationship)
                if 'status' in filters:
                    logging.warning("Status filter requested but Meeting model doesn't have status field")
                    # Could implement job.status filtering here if needed
                
                # Apply direction filter
                if 'direction' in filters:
                    query = query.filter(cls.model.direction == filters['direction'])
            
            meetings = query.order_by(cls.model.start_time.desc()).all()
            logging.info(f"Found {len(meetings)} meetings for seller: {seller_id}")
            return meetings
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get meetings for seller {seller_id}: {str(e)}")
            raise
    
    @classmethod
    def get_meetings_by_buyer(cls, buyer_id: str) -> List[Meeting]:
        """
        Get all meetings for a specific buyer.
        
        Args:
            buyer_id: Buyer UUID
            
        Returns:
            List of Meeting instances
        """
        try:
            meetings = cls.model.query.filter_by(buyer_id=buyer_id).order_by(
                cls.model.start_time.desc()
            ).all()
            logging.info(f"Found {len(meetings)} meetings for buyer: {buyer_id}")
            return meetings
        except SQLAlchemyError as e:
            logging.error(f"Failed to get meetings for buyer {buyer_id}: {str(e)}")
            raise
    
    @classmethod
    def get_call_history(cls, user_id: str, team_member_ids: Optional[List[str]] = None, 
                        start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Get comprehensive call history for a user or team.
        
        Args:
            user_id: Current user's UUID
            team_member_ids: Optional list of team member UUIDs for managers
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            
        Returns:
            List of call history dictionaries with formatted data
        """
        try:
            # Determine which user IDs to query
            if team_member_ids:
                # Manager querying team members
                seller_ids = team_member_ids
                logging.info(f"Fetching call history for team members: {team_member_ids}")
            else:
                seller_ids = [user_id]
                logging.info(f"Fetching call history for user: {user_id}")
            
            # Get meetings for specified sellers with buyer information
            meetings_query = (
                cls.model.query
                .join(Seller)
                .join(Buyer)  # Join Buyer table to get buyer information
                .filter(Seller.id.in_(seller_ids))
            )
            
            # Add date filtering for meetings if provided
            if start_date:
                meetings_query = meetings_query.filter(cls.model.start_time >= start_date)
            if end_date:
                meetings_query = meetings_query.filter(cls.model.start_time <= end_date)
            
            meetings_query = meetings_query.order_by(cls.model.start_time.desc())
            
            # Get mobile app calls for specified sellers
            mobile_app_calls_query = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id.in_(seller_ids))
            )
            
            # Add date filtering for mobile app calls if provided
            if start_date:
                mobile_app_calls_query = mobile_app_calls_query.filter(MobileAppCall.start_time >= start_date)
            if end_date:
                mobile_app_calls_query = mobile_app_calls_query.filter(MobileAppCall.start_time <= end_date)
            
            mobile_app_calls_query = mobile_app_calls_query.order_by(MobileAppCall.start_time.desc())
            
            meetings = meetings_query.all()
            mobile_app_calls = mobile_app_calls_query.all()
            
            # Combine all call records
            all_calls = []
            all_calls.extend(meetings)
            all_calls.extend(mobile_app_calls)
            
            # Deduplicate records (prioritize meetings over mobile app calls)
            deduplicated_calls = cls._deduplicate_call_records(all_calls)
            
            # Sort by start time
            deduplicated_calls.sort(
                key=lambda x: x.start_time.replace(
                    tzinfo=ZoneInfo("Asia/Kolkata")
                ) if x.start_time and x.start_time.tzinfo is None else x.start_time,
                reverse=True
            )
            
            # Format call history
            local_now = datetime.now(ZoneInfo("Asia/Kolkata"))
            result = []
            
            for call_record in deduplicated_calls:
                formatted_call = cls._format_call_record(call_record, local_now)
                if formatted_call:
                    result.append(formatted_call)
            
            logging.info(f"Retrieved {len(result)} call history records (after deduplication)")
            return result
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get call history for user {user_id}: {str(e)}")
            raise
    
    @classmethod
    def _format_call_record(cls, call_record, local_now: datetime) -> Optional[Dict[str, Any]]:
        """
        Format a call record (Meeting or MobileAppCall) for API response.
        
        Args:
            call_record: Meeting or MobileAppCall instance
            local_now: Current local time for calculations
            
        Returns:
            Formatted call record dictionary or None if invalid
        """
        try:
            # Get seller name and email
            if isinstance(call_record, Meeting):
                seller_name = call_record.seller.name
                seller_email = call_record.seller.email
            else:
                seller = Seller.query.filter_by(phone=call_record.seller_number).first()
                seller_name = seller.name if seller else "Unknown"
                seller_email = seller.email if seller else None
            
            # Get buyer information
            buyer_name = None
            buyer_email = None
            if isinstance(call_record, Meeting):
                # For meetings, buyer information is already loaded via join
                buyer_name = call_record.buyer.name
                buyer_email = call_record.buyer.email
                buyer_number = call_record.buyer.phone
                seller_number = call_record.seller.phone
            else:  # MobileAppCall
                # For mobile app calls, need to look up buyer by phone number
                buyer_number = call_record.buyer_number
                seller_number = call_record.seller_number
                
                # Look up buyer by normalized phone number
                from app.utils.call_recording_utils import normalize_phone_number
                normalized_buyer_phone = normalize_phone_number(buyer_number)
                buyer = Buyer.query.filter_by(phone=normalized_buyer_phone).first()
                if buyer:
                    buyer_name = buyer.name
                    buyer_email = buyer.email
            
            # Determine analysis status and direction
            analysis_status = 'Processing'
            direction = None
            
            title = f"Meeting between {denormalize_phone_number(buyer_number)} and {seller_name}"

            # Handle timezone for start/end times
            call_record_start_time = call_record.start_time
            if call_record_start_time and call_record_start_time.tzinfo is None:
                call_record_start_time = call_record_start_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                
            call_record_end_time = call_record.end_time
            if call_record_end_time and call_record_end_time.tzinfo is None:
                call_record_end_time = call_record_end_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            
            if isinstance(call_record, Meeting):
                # Meeting record
                job_status = call_record.job.status
                if job_status in [JobStatus.INIT, JobStatus.IN_PROGRESS]:
                    analysis_status = 'Processing'
                elif job_status == JobStatus.COMPLETED:
                    analysis_status = 'Completed'
                else:
                    analysis_status = 'Not Recorded'
                
                title = call_record.title
                direction = call_record.direction
                duration = human_readable_duration(call_record_end_time, call_record_start_time)
                if duration == "0s":
                    call_type = "Not Answered"
                else:
                    call_type = "Answered"
            elif isinstance(call_record, MobileAppCall):
                # Mobile app call record
                analysis_status = call_record.status
                
                if call_record.status == MobileAppCallStatus.MISSED.value:
                    title = f'Missed Call from {denormalize_phone_number(buyer_number)}'
                    direction = CallDirection.INCOMING.value
                    call_type = "Missed"
                elif call_record.status == MobileAppCallStatus.REJECTED.value:
                    call_type = "Rejected"
                    title = f'Rejected Call from {denormalize_phone_number(buyer_number)}'
                    direction = CallDirection.INCOMING.value
                elif call_record.status == MobileAppCallStatus.NOT_ANSWERED.value:
                    call_type = "Not Answered"
                    title = f'{denormalize_phone_number(buyer_number)} did not answer'
                    direction = CallDirection.OUTGOING.value
                elif call_record.status == MobileAppCallStatus.PROCESSING.value:
                    call_type = "Answered"
                    # Set direction based on call_type field
                    if call_record.call_type == "incoming":
                        direction = CallDirection.INCOMING.value
                    elif call_record.call_type == "outgoing":
                        direction = CallDirection.OUTGOING.value
                    else:
                        direction = None  # Fallback for unknown call types
                    
                    start_time_local = call_record.start_time
                    if start_time_local.tzinfo is None:
                        start_time_local = start_time_local.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                    if local_now - start_time_local > timedelta(seconds=30):
                        analysis_status = 'Not Recorded'
                
                if call_record.status in [MobileAppCallStatus.MISSED.value, MobileAppCallStatus.REJECTED.value, MobileAppCallStatus.NOT_ANSWERED.value]:
                    # Unsuccessful calls always show 0s duration
                    duration = "0s"
                else:
                    # Successful calls (PROCESSING status) use the original duration field to avoid 3-second inflation
                    # Use the duration field from the record instead of calculating from start/end times
                    duration_seconds = call_record.duration if hasattr(call_record, 'duration') else 0
                    if duration_seconds < 60:
                        duration = f"{duration_seconds}s"
                    elif duration_seconds < 3600:
                        minutes = duration_seconds // 60
                        seconds = duration_seconds % 60
                        duration = f"{minutes}m {seconds}s"
                    else:
                        hours = duration_seconds // 3600
                        minutes = (duration_seconds % 3600) // 60
                        duration = f"{hours}h {minutes}m"
                
            else:
                return None                
            
            return {
                "id": str(call_record.id),
                "title": title,
                "source": call_record.source.value if isinstance(call_record, Meeting) else MeetingSource.PHONE.value,
                "start_time": call_record.start_time.isoformat() if call_record.start_time else None,
                "end_time": call_record.end_time.isoformat() if call_record.end_time else None,
                "buyer_number": denormalize_phone_number(buyer_number),
                "buyer_name": buyer_name,
                "buyer_email": buyer_email,
                "seller_number": denormalize_phone_number(seller_number),
                "analysis_status": analysis_status,
                "duration": duration,
                "call_notes": getattr(call_record, 'call_notes', None),
                "user_name": seller_name,
                "user_email": seller_email,
                "call_direction": direction,
                "call_type": call_type,
                "app_call_type": getattr(call_record, "call_type", None),
                "call_summary": getattr(call_record, 'summary', None)
            }
            
        except Exception as e:
            logging.error(f"Failed to format call record {call_record.id}: {str(e)}")
            return None
    
    @classmethod
    def update_llm_analysis(cls, meeting_id: str, analysis_data: Dict[str, Any]) -> Optional[Meeting]:
        """
        Update meeting with LLM analysis results.
        
        Args:
            meeting_id: Meeting UUID
            analysis_data: Dictionary containing LLM analysis fields
            
        Returns:
            Updated Meeting instance or None if not found
        """
        try:
            meeting = cls.update(meeting_id, **analysis_data)
            if meeting:
                logging.info(f"Updated LLM analysis for meeting: {meeting_id}")
            return meeting
        except SQLAlchemyError as e:
            logging.error(f"Failed to update LLM analysis for meeting {meeting_id}: {str(e)}")
            raise
    
    @classmethod
    def update_transcription(cls, meeting_id: str, transcription: str) -> Optional[Meeting]:
        """
        Update meeting with transcription data.
        
        Args:
            meeting_id: Meeting UUID
            transcription: Transcription data (JSON string)
            
        Returns:
            Updated Meeting instance or None if not found
        """
        try:
            meeting = cls.update(meeting_id, transcription=transcription)
            if meeting:
                logging.info(f"Updated transcription for meeting: {meeting_id}")
            return meeting
        except SQLAlchemyError as e:
            logging.error(f"Failed to update transcription for meeting {meeting_id}: {str(e)}")
            raise
    
    @classmethod
    def get_with_seller_buyer(cls, meeting_id: str) -> Optional[Meeting]:
        """
        Get meeting with seller and buyer relationships loaded.
        
        Args:
            meeting_id: Meeting UUID
            
        Returns:
            Meeting instance with relationships loaded
        """
        try:
            meeting = (
                cls.model.query
                .join(Seller)
                .join(Buyer)
                .filter(cls.model.id == meeting_id)
                .first()
            )
            
            if meeting:
                logging.info(f"Found meeting with relationships: {meeting_id}")
            else:
                logging.warning(f"Meeting not found with relationships: {meeting_id}")
                
            return meeting
        except SQLAlchemyError as e:
            logging.error(f"Failed to get meeting with relationships {meeting_id}: {str(e)}")
            raise
    
    @classmethod
    def get_last_meeting_by_seller(cls, seller_id: str) -> Optional[Meeting]:
        """
        Get the most recent meeting for a specific seller.
        
        Args:
            seller_id: Seller UUID
            
        Returns:
            Most recent Meeting instance or None if not found
        """
        try:
            last_meeting = (
                cls.model.query
                .filter_by(seller_id=seller_id)
                .order_by(cls.model.start_time.desc())
                .first()
            )
            
            if last_meeting:
                logging.info(f"Found last meeting for seller {seller_id}: {last_meeting.id}")
            else:
                logging.info(f"No meeting found for seller {seller_id}")
                
            return last_meeting
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get last meeting for seller {seller_id}: {str(e)}")
            raise
    
    @classmethod
    def get_call_history_by_buyer(cls, buyer_id: str) -> List[Dict[str, Any]]:
        """
        Get comprehensive call history for a specific buyer.
        
        Args:
            buyer_id: Buyer UUID
            user_id: Current user's UUID for authorization
            
        Returns:
            List of call history dictionaries with formatted data
        """
        try:
            # Get buyer to verify access
            buyer = Buyer.query.get(buyer_id)
            if not buyer:
                logging.error(f"Buyer not found: {buyer_id}")
                return []
            
            # Get meetings for the buyer
            meetings_query = (
                cls.model.query
                .filter_by(buyer_id=buyer_id)
                .order_by(cls.model.start_time.desc())
            )
            
            # Get mobile app calls for the buyer (by phone number)
            # Normalize buyer phone for consistent comparison
            normalized_buyer_phone = normalize_phone_number(buyer.phone)
            mobile_app_calls_query = (
                MobileAppCall.query
                .filter(MobileAppCall.buyer_number == normalized_buyer_phone)
                .order_by(MobileAppCall.start_time.desc())
            )
            
            meetings = meetings_query.all()
            mobile_app_calls = mobile_app_calls_query.all()
            
            # Combine and sort all call records
            all_calls = []
            all_calls.extend(meetings)
            all_calls.extend(mobile_app_calls)
            
            # Sort by start time
            all_calls.sort(
                key=lambda x: x.start_time.replace(
                    tzinfo=ZoneInfo("Asia/Kolkata")
                ) if x.start_time and x.start_time.tzinfo is None else x.start_time,
                reverse=True
            )
            
            # Format call history
            local_now = datetime.now(ZoneInfo("Asia/Kolkata"))
            result = []
            
            for call_record in all_calls:
                formatted_call = cls._format_call_record(call_record, local_now)
                if formatted_call:
                    result.append(formatted_call)
            
            logging.info(f"Retrieved {len(result)} call history records for buyer {buyer_id}")
            return result
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get call history for buyer {buyer_id}: {str(e)}")
            raise
    
    @classmethod
    def get_meeting_analytics(cls, user_id: str, date_range: Optional[Dict[str, datetime]] = None) -> Dict[str, Any]:
        """
        Get meeting analytics for a user.
        
        Args:
            user_id: Seller UUID
            date_range: Optional date range filter
            
        Returns:
            Dictionary with analytics data
        """
        try:
            query = cls.model.query.filter_by(seller_id=user_id)
            
            if date_range:
                query = query.filter(
                    and_(
                        cls.model.start_time >= date_range['start'],
                        cls.model.start_time <= date_range['end']
                    )
                )
            
            meetings = query.all()
            
            # Calculate analytics
            total_meetings = len(meetings)
            completed_meetings = len([m for m in meetings if m.job and m.job.status == JobStatus.COMPLETED])
            incoming_calls = len([m for m in meetings if m.direction == CallDirection.INCOMING.value])
            outgoing_calls = len([m for m in meetings if m.direction == CallDirection.OUTGOING.value])
            
            analytics = {
                'total_meetings': total_meetings,
                'completed_meetings': completed_meetings,
                'processing_meetings': total_meetings - completed_meetings,
                'incoming_calls': incoming_calls,
                'outgoing_calls': outgoing_calls,
                'completion_rate': (completed_meetings / total_meetings * 100) if total_meetings > 0 else 0
            }
            
            logging.info(f"Generated analytics for user {user_id}: {analytics}")
            return analytics
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get meeting analytics for user {user_id}: {str(e)}")
            raise
    
    @classmethod
    def _deduplicate_call_records(cls, all_calls: List) -> List:
        """
        Remove duplicate call records, prioritizing meetings over mobile app calls.
        
        Args:
            all_calls: List containing both Meeting and MobileAppCall instances
            
        Returns:
            Deduplicated list with mobile app calls removed if corresponding meetings exist
        """
        try:
            # Separate record types
            meetings = [call for call in all_calls if isinstance(call, Meeting)]
            mobile_calls = [call for call in all_calls if isinstance(call, MobileAppCall)]
            
            # Find duplicates to remove
            duplicates_to_remove = set()
            duplicate_count = 0
            
            for mobile_call in mobile_calls:
                for meeting in meetings:
                    if cls._is_duplicate_call(meeting, mobile_call):
                        duplicates_to_remove.add(mobile_call.id)
                        duplicate_count += 1
                        logging.info(f"Duplicate detected: Mobile call {mobile_call.id} matches meeting {meeting.id}")
                        break  # One mobile call can only match one meeting
            
            # Filter out duplicates
            deduplicated_calls = []
            for call in all_calls:
                if isinstance(call, MobileAppCall) and call.id in duplicates_to_remove:
                    continue  # Skip this mobile app call
                deduplicated_calls.append(call)
            
            if duplicate_count > 0:
                logging.info(f"Removed {duplicate_count} duplicate mobile app calls from call history")
            
            return deduplicated_calls
            
        except Exception as e:
            logging.error(f"Error during call record deduplication: {str(e)}")
            # Return original list if deduplication fails
            return all_calls
    
    @classmethod
    def _is_duplicate_call(cls, meeting: Meeting, mobile_call: MobileAppCall) -> bool:
        """
        Check if a meeting and mobile app call represent the same call.
        
        Args:
            meeting: Meeting instance
            mobile_call: MobileAppCall instance
            
        Returns:
            True if they represent the same call, False otherwise
        """
        try:
            # Check 1: Same seller
            if str(meeting.seller_id) != str(mobile_call.user_id):
                return False
            
            # Check 2: Same buyer (normalize phone numbers for comparison)
            meeting_buyer_phone = normalize_phone_number(meeting.buyer.phone)
            mobile_buyer_phone = normalize_phone_number(mobile_call.buyer_number)
            if meeting_buyer_phone != mobile_buyer_phone:
                return False
            
            # Check 3: Similar timing (±2 minutes tolerance)
            # Ensure both times are timezone-aware for comparison
            meeting_time = meeting.start_time
            if meeting_time.tzinfo is None:
                meeting_time = meeting_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            
            mobile_time = mobile_call.start_time
            if mobile_time.tzinfo is None:
                mobile_time = mobile_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            
            time_diff = abs((meeting_time - mobile_time).total_seconds())
            if time_diff > 120:  # 2 minutes in seconds
                return False
            
            # All checks passed - this is a duplicate
            return True
            
        except Exception as e:
            logging.error(f"Error checking duplicate call: {str(e)}")
            return False  # Conservative approach - don't remove if unsure 