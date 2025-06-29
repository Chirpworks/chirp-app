import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

from app.models.meeting import Meeting, ProcessingStatus
from app.models.seller import Seller
from app.models.buyer import Buyer
from app.models.mobile_app_calls import MobileAppCall
from app.models.job import JobStatus
from app.constants import CallDirection, MeetingSource
from app.utils.call_recording_utils import denormalize_phone_number
from .base_service import BaseService

logging = logging.getLogger(__name__)


def human_readable_duration(end_time: datetime, start_time: datetime) -> str:
    """Helper function to calculate human readable duration"""
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
                'status': kwargs.get('status', ProcessingStatus.INITIALIZED),
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
                _ = meeting.job
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
                
                # Apply status filter
                if 'status' in filters:
                    query = query.filter(cls.model.status == filters['status'])
                
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
    def get_call_history(cls, user_id: str, team_member_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get comprehensive call history for a user or team.
        
        Args:
            user_id: Current user's UUID
            team_member_ids: Optional list of team member UUIDs for managers
            
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
            
            # Get meetings for specified sellers
            meetings_query = (
                cls.model.query
                .join(Seller)
                .filter(Seller.id.in_(seller_ids))
                .order_by(cls.model.start_time.desc())
            )
            
            # Get mobile app calls for specified sellers
            mobile_app_calls_query = (
                MobileAppCall.query
                .filter(MobileAppCall.user_id.in_(seller_ids))
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
            
            logging.info(f"Retrieved {len(result)} call history records")
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
            # Get seller name
            if isinstance(call_record, Meeting):
                seller_name = call_record.seller.name
            else:
                seller = Seller.query.filter_by(phone=call_record.seller_number).first()
                seller_name = seller.name if seller else "Unknown"
            
            # Determine analysis status and direction
            analysis_status = 'Processing'
            direction = None
            # Get buyer number based on record type
            if isinstance(call_record, Meeting):
                buyer_number = call_record.buyer.phone
                seller_number = call_record.seller.phone
            else:  # MobileAppCall
                buyer_number = call_record.buyer_number
                seller_number = call_record.seller_number
            
            title = f"Meeting between {denormalize_phone_number(buyer_number)} and {seller_name}"
            
            if isinstance(call_record, Meeting):
                # Meeting record
                job_status = call_record.job.status if call_record.job else JobStatus.INIT
                if job_status in [JobStatus.INIT, JobStatus.IN_PROGRESS]:
                    analysis_status = 'Processing'
                elif job_status == JobStatus.COMPLETED:
                    analysis_status = 'Completed'
                else:
                    analysis_status = 'Not Recorded'
                
                title = call_record.title
                direction = call_record.direction
                
            elif isinstance(call_record, MobileAppCall):
                # Mobile app call record
                analysis_status = call_record.status
                
                if call_record.status == 'Missed':
                    title = f'Missed Call from {denormalize_phone_number(buyer_number)}'
                    direction = CallDirection.INCOMING.value
                elif call_record.status == 'Not Answered':
                    title = f'{denormalize_phone_number(buyer_number)} did not answer'
                    direction = CallDirection.OUTGOING.value
                elif call_record.status == 'Processing':
                    start_time_local = call_record.start_time
                    if start_time_local.tzinfo is None:
                        start_time_local = start_time_local.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                    if local_now - start_time_local > timedelta(seconds=30):
                        analysis_status = 'Not Recorded'
            else:
                return None
            
            # Handle timezone for start/end times
            call_record_start_time = call_record.start_time
            if call_record_start_time and call_record_start_time.tzinfo is None:
                call_record_start_time = call_record_start_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                
            call_record_end_time = call_record.end_time
            if call_record_end_time and call_record_end_time.tzinfo is None:
                call_record_end_time = call_record_end_time.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            
            # Calculate duration
            duration = human_readable_duration(call_record_end_time, call_record_start_time)
            
            return {
                "id": str(call_record.id),
                "title": title,
                "source": call_record.source.value if isinstance(call_record, Meeting) else MeetingSource.PHONE.value,
                "participants": getattr(call_record, 'participants', None),
                "start_time": call_record.start_time.isoformat() if call_record.start_time else None,
                "end_time": call_record.end_time.isoformat() if call_record.end_time else None,
                "buyer_number": denormalize_phone_number(buyer_number),
                "seller_number": denormalize_phone_number(seller_number),
                "analysis_status": analysis_status,
                "duration": duration,
                "call_notes": getattr(call_record, 'call_notes', None),
                "user_name": seller_name,
                "user_email": getattr(call_record.seller, 'email', None) if isinstance(call_record, Meeting) else None,
                "direction": direction
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