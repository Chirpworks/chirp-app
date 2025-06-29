import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

from app import db
from app.models.action import Action, ActionStatus
from app.models.meeting import Meeting
from app.models.seller import Seller, SellerRole
from app.utils.call_recording_utils import denormalize_phone_number
from .base_service import BaseService

logging = logging.getLogger(__name__)


# Define ActionType enum locally since it seems to be missing from the model file
# Based on migration and usage patterns
try:
    from app.models.action import ActionType
except ImportError:
    from enum import Enum
    class ActionType(Enum):
        SUGGESTED_ACTION = "suggested_action"
        CONTEXTUAL_ACTION = "contextual_action"


class ActionService(BaseService):
    """
    Service class for all action-related database operations and task management.
    """
    model = Action
    
    @classmethod
    def create_action(cls, title: str, meeting_id: str, buyer_id: str, seller_id: str, 
                     action_type: ActionType = None, **kwargs) -> Action:
        """
        Create a new action for a meeting.
        
        Args:
            title: Action title
            meeting_id: Meeting UUID this action relates to
            buyer_id: Buyer UUID
            seller_id: Seller UUID
            action_type: Type of action (SUGGESTED_ACTION or CONTEXTUAL_ACTION)
            **kwargs: Additional action fields (due_date, description, reasoning, signals)
            
        Returns:
            Created Action instance
        """
        try:
            action_data = {
                'title': title,
                'meeting_id': meeting_id,
                'buyer_id': buyer_id,
                'seller_id': seller_id,
                'status': kwargs.get('status', ActionStatus.PENDING),
                'created_at': kwargs.get('created_at', datetime.now(ZoneInfo("Asia/Kolkata"))),
                **kwargs
            }
            
            if action_type:
                action_data['type'] = action_type
            
            action = cls.create(**action_data)
            logging.info(f"Created action: {title} with ID: {action.id}")
            return action
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create action {title}: {str(e)}")
            raise
    
    @classmethod
    def get_actions_for_user(cls, user_id: str, team_member_ids: List[str] = None) -> List[Dict[str, Any]]:
        """
        Get all actions for a user or team, formatted for API response.
        
        Args:
            user_id: Current user's UUID
            team_member_ids: Optional list of team member UUIDs for managers
            
        Returns:
            List of formatted action dictionaries
        """
        try:
            # Determine which user IDs to query
            if team_member_ids:
                seller_ids = team_member_ids
                logging.info(f"Fetching actions for team members: {team_member_ids}")
            else:
                seller_ids = [user_id]
                logging.info(f"Fetching actions for user: {user_id}")
            
            # Build query based on user access
            if len(seller_ids) > 1:
                query = (
                    cls.model.query
                    .join(cls.model.meeting)
                    .join(Meeting.seller)
                    .filter(Seller.id.in_(seller_ids))
                    .order_by(cls.model.due_date.asc())
                )
            else:
                query = (
                    cls.model.query
                    .join(cls.model.meeting)
                    .join(Meeting.seller)
                    .filter(Seller.id == user_id)
                    .order_by(cls.model.due_date.asc())
                )
            
            actions = query.all()
            
            # Format actions for API response
            result = []
            for action in actions:
                formatted_action = cls._format_action(action)
                if formatted_action:
                    result.append(formatted_action)
            
            logging.info(f"Retrieved {len(result)} actions")
            return result
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get actions for user {user_id}: {str(e)}")
            raise
    
    @classmethod
    def get_action_by_id_for_user(cls, action_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific action by ID, ensuring user has access.
        
        Args:
            action_id: Action UUID
            user_id: User UUID for authorization
            
        Returns:
            Formatted action dictionary or None if not found/unauthorized
        """
        try:
            action = (
                cls.model.query
                .join(cls.model.meeting)
                .join(Meeting.seller)
                .filter(cls.model.id == action_id, Seller.id == user_id)
                .first()
            )
            
            if not action:
                logging.warning(f"Action {action_id} not found or unauthorized for user {user_id}")
                return None
            
            formatted_action = cls._format_action(action)
            logging.info(f"Retrieved action {action_id} for user {user_id}")
            return formatted_action
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get action {action_id} for user {user_id}: {str(e)}")
            raise
    
    @classmethod
    def _format_action(cls, action: Action) -> Dict[str, Any]:
        """
        Format an action for API response.
        
        Args:
            action: Action instance
            
        Returns:
            Formatted action dictionary
        """
        try:
            seller_name = action.meeting.seller.name
            
            formatted = {
                "id": str(action.id),
                "title": action.title,
                "due_date": action.due_date.isoformat() if action.due_date else None,
                "status": action.status.value,
                "description": action.description,
                "meeting_id": str(action.meeting.id),
                "meeting_title": action.meeting.title,
                "meeting_buyer_number": denormalize_phone_number(action.meeting.buyer_number),
                "meeting_seller_name": seller_name,
                "reasoning": action.reasoning,
                "signals": action.signals,
                "created_at": action.created_at.isoformat() if action.created_at else None,
            }
            
            # Add type if it exists (might be missing in some records)
            if hasattr(action, 'type') and action.type:
                formatted["type"] = action.type.value
            
            return formatted
            
        except Exception as e:
            logging.error(f"Failed to format action {action.id}: {str(e)}")
            return None
    
    @classmethod
    def update_action_status(cls, action_id: str, status: ActionStatus, user_id: str) -> Optional[Action]:
        """
        Update action status with user authorization check.
        
        Args:
            action_id: Action UUID
            status: New ActionStatus
            user_id: User UUID for authorization
            
        Returns:
            Updated Action instance or None if not found/unauthorized
        """
        try:
            # Verify user has access to this action
            action = (
                cls.model.query
                .join(cls.model.meeting)
                .join(Meeting.seller)
                .filter(cls.model.id == action_id, Seller.id == user_id)
                .first()
            )
            
            if not action:
                logging.warning(f"Action {action_id} not found or unauthorized for user {user_id}")
                return None
            
            action.status = status
            db.session.flush()
            
            logging.info(f"Updated action {action_id} status to {status.value}")
            return action
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to update action {action_id} status: {str(e)}")
            raise
    
    @classmethod
    def bulk_update_actions(cls, action_updates: List[Dict[str, Any]], user_id: str) -> int:
        """
        Update multiple actions in bulk with user authorization.
        
        Args:
            action_updates: List of dicts with 'id' and 'status' keys
            user_id: User UUID for authorization
            
        Returns:
            Number of actions successfully updated
            
        Raises:
            ValueError: If some actions are not found or unauthorized
        """
        try:
            action_ids = [update['id'] for update in action_updates]
            
            # Verify user has access to all actions
            accessible_actions = (
                cls.model.query
                .join(cls.model.meeting)
                .join(Meeting.seller)
                .filter(cls.model.id.in_(action_ids), Seller.id == user_id)
                .all()
            )
            
            if len(accessible_actions) != len(action_ids):
                accessible_ids = [str(a.id) for a in accessible_actions]
                missing_ids = [aid for aid in action_ids if aid not in accessible_ids]
                raise ValueError(f"Actions not found or unauthorized: {missing_ids}")
            
            # Update actions
            updated_count = 0
            for update in action_updates:
                action = next(a for a in accessible_actions if str(a.id) == update["id"])
                action.status = ActionStatus(update["status"])
                updated_count += 1
            
            db.session.flush()
            logging.info(f"Bulk updated {updated_count} actions for user {user_id}")
            return updated_count
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to bulk update actions: {str(e)}")
            raise
    
    @classmethod
    def get_actions_by_meeting(cls, meeting_id: str) -> List[Action]:
        """
        Get all actions for a specific meeting.
        
        Args:
            meeting_id: Meeting UUID
            
        Returns:
            List of Action instances
        """
        try:
            actions = cls.model.query.filter_by(meeting_id=meeting_id).order_by(
                cls.model.created_at.asc()
            ).all()
            logging.info(f"Found {len(actions)} actions for meeting: {meeting_id}")
            return actions
        except SQLAlchemyError as e:
            logging.error(f"Failed to get actions for meeting {meeting_id}: {str(e)}")
            raise
    
    @classmethod
    def get_actions_by_status(cls, status: ActionStatus, user_id: str = None) -> List[Action]:
        """
        Get all actions with a specific status, optionally filtered by user.
        
        Args:
            status: ActionStatus to filter by
            user_id: Optional user UUID to filter by
            
        Returns:
            List of Action instances
        """
        try:
            query = cls.model.query.filter_by(status=status)
            
            if user_id:
                query = (
                    query
                    .join(cls.model.meeting)
                    .join(Meeting.seller)
                    .filter(Seller.id == user_id)
                )
            
            actions = query.order_by(cls.model.due_date.asc()).all()
            logging.info(f"Found {len(actions)} actions with status {status.value}")
            return actions
        except SQLAlchemyError as e:
            logging.error(f"Failed to get actions by status {status.value}: {str(e)}")
            raise
    
    @classmethod
    def get_overdue_actions(cls, user_id: str = None) -> List[Action]:
        """
        Get all overdue actions (due_date < now and status = PENDING).
        
        Args:
            user_id: Optional user UUID to filter by
            
        Returns:
            List of overdue Action instances
        """
        try:
            current_time = datetime.now(ZoneInfo("Asia/Kolkata"))
            
            query = cls.model.query.filter(
                and_(
                    cls.model.status == ActionStatus.PENDING,
                    cls.model.due_date < current_time
                )
            )
            
            if user_id:
                query = (
                    query
                    .join(cls.model.meeting)
                    .join(Meeting.seller)
                    .filter(Seller.id == user_id)
                )
            
            actions = query.order_by(cls.model.due_date.asc()).all()
            logging.info(f"Found {len(actions)} overdue actions")
            return actions
        except SQLAlchemyError as e:
            logging.error(f"Failed to get overdue actions: {str(e)}")
            raise
    
    @classmethod
    def get_action_statistics(cls, user_id: str = None, date_range: Dict[str, datetime] = None) -> Dict[str, Any]:
        """
        Get action statistics for a user or all users.
        
        Args:
            user_id: Optional user UUID to filter by
            date_range: Optional date range filter
            
        Returns:
            Dictionary with action statistics
        """
        try:
            query = cls.model.query
            
            if user_id:
                query = (
                    query
                    .join(cls.model.meeting)
                    .join(Meeting.seller)
                    .filter(Seller.id == user_id)
                )
            
            if date_range:
                query = query.filter(
                    and_(
                        cls.model.created_at >= date_range['start'],
                        cls.model.created_at <= date_range['end']
                    )
                )
            
            actions = query.all()
            
            # Calculate statistics
            total_actions = len(actions)
            pending_actions = len([a for a in actions if a.status == ActionStatus.PENDING])
            completed_actions = len([a for a in actions if a.status == ActionStatus.COMPLETED])
            
            current_time = datetime.now(ZoneInfo("Asia/Kolkata"))
            overdue_actions = len([
                a for a in actions 
                if a.status == ActionStatus.PENDING and a.due_date and a.due_date < current_time
            ])
            
            statistics = {
                'total_actions': total_actions,
                'pending_actions': pending_actions,
                'completed_actions': completed_actions,
                'overdue_actions': overdue_actions,
                'completion_rate': (completed_actions / total_actions * 100) if total_actions > 0 else 0
            }
            
            logging.info(f"Generated action statistics: {statistics}")
            return statistics
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get action statistics: {str(e)}")
            raise 