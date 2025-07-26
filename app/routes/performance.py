import traceback
import logging

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.call_performance_service import CallPerformanceService
from app.services.seller_service import SellerService
from app.services.meeting_service import MeetingService

performance_bp = Blueprint("performance", __name__)
logging = logging.getLogger(__name__)


@performance_bp.route('/call/<meeting_id>/metrics', methods=['POST'])
def create_call_performance_metrics(meeting_id):
    """
    Create or update call performance metrics for a specific meeting.
    No authentication required - can be called by external analysis services.
    
    Expected JSON payload:
    {
        "intro": {"score": 8.5, "date": "2024-01-15", "reason": "Excellent value proposition"},
        "rapport_building": {"score": 7.2, "date": "2024-01-15", "reason": "Good connection established"},
        "need_realization": {"score": 6.8, "date": "2024-01-15", "reason": "Identified key pain points"},
        "script_adherance": {"score": 8.0, "date": "2024-01-15", "reason": "Followed script well"},
        "objection_handling": {"score": 7.5, "date": "2024-01-15", "reason": "Handled objections effectively"},
        "pricing_and_negotiation": {"score": 6.5, "date": "2024-01-15", "reason": "Room for improvement"},
        "closure_and_next_steps": {"score": 8.2, "date": "2024-01-15", "reason": "Clear next steps defined"},
        "conversation_structure_and_flow": {"score": 7.8, "date": "2024-01-15", "reason": "Good flow maintained"},
        "overall_score": 7.5,
        "analyzed_at": "2024-01-15T10:30:00Z"
    }
    """
    try:
        # Validate meeting_id format
        if not meeting_id:
            return jsonify({"error": "Meeting ID is required"}), 400
        
        # Get JSON data from request
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON payload is required"}), 400
        
        # Log the request
        logging.info(f"Received call performance data for meeting {meeting_id}")
        
        # Verify the meeting exists
        meeting = MeetingService.get_by_id(meeting_id)
        if not meeting:
            return jsonify({"error": "Meeting not found"}), 404
        
        # Create or update call performance
        call_performance = CallPerformanceService.create_or_update_call_performance(
            meeting_id=meeting_id,
            performance_data=data
        )
        
        # Return success response
        response_data = {
            "message": "Call performance metrics updated successfully",
            "call_performance": {
                "id": str(call_performance.id),
                "meeting_id": str(call_performance.meeting_id),
                "overall_score": call_performance.overall_score,
                "analyzed_at": call_performance.analyzed_at.isoformat() if call_performance.analyzed_at else None,
                "created_at": call_performance.created_at.isoformat(),
                "updated_at": call_performance.updated_at.isoformat()
            }
        }
        
        return jsonify(response_data), 201
        
    except ValueError as e:
        logging.error(f"Validation error in create_call_performance_metrics: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in create_call_performance_metrics: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error occurred"}), 500


@performance_bp.route('/call/<meeting_id>/metrics', methods=['GET'])
@jwt_required()
def get_call_performance_metrics(meeting_id):
    """
    Get call performance metrics for a specific meeting.
    """
    try:
        # Get the current user
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Validate meeting_id format
        if not meeting_id:
            return jsonify({"error": "Meeting ID is required"}), 400
        
        # Verify the meeting exists and user has access
        meeting = MeetingService.get_by_id(meeting_id)
        if not meeting:
            return jsonify({"error": "Meeting not found"}), 404
        
        # Check if user has permission to view this meeting's performance
        if meeting.seller_id != user.id and user.role.value not in ['admin', 'manager']:
            return jsonify({"error": "Unauthorized to view performance for this meeting"}), 403
        
        # Get performance summary
        performance_summary = CallPerformanceService.get_performance_summary(meeting_id)
        
        if not performance_summary:
            return jsonify({"message": "No performance data found for this meeting"}), 404
        
        return jsonify({
            "message": "Call performance metrics retrieved successfully",
            "performance": performance_summary
        }), 200
        
    except Exception as e:
        logging.error(f"Error in get_call_performance_metrics: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error occurred"}), 500


@performance_bp.route('/call/<meeting_id>/metrics', methods=['DELETE'])
@jwt_required()
def delete_call_performance_metrics(meeting_id):
    """
    Delete call performance metrics for a specific meeting.
    """
    try:
        # Get the current user
        user_id = get_jwt_identity()
        user = SellerService.get_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Validate meeting_id format
        if not meeting_id:
            return jsonify({"error": "Meeting ID is required"}), 400
        
        # Verify the meeting exists and user has access
        meeting = MeetingService.get_by_id(meeting_id)
        if not meeting:
            return jsonify({"error": "Meeting not found"}), 404
        
        # Check if user has permission to delete this meeting's performance (admin/manager only)
        if user.role.value not in ['admin', 'manager']:
            return jsonify({"error": "Unauthorized to delete performance data"}), 403
        
        # Delete performance data
        deleted = CallPerformanceService.delete_by_meeting_id(meeting_id)
        
        if deleted:
            return jsonify({"message": "Call performance metrics deleted successfully"}), 200
        else:
            return jsonify({"message": "No performance data found for this meeting"}), 404
        
    except Exception as e:
        logging.error(f"Error in delete_call_performance_metrics: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error occurred"}), 500


@performance_bp.route('/user/<user_id>/metrics', methods=['GET'])
@jwt_required()
def get_user_performance_metrics(user_id):
    """
    Get call performance metrics for a specific user within a date range.
    
    Query parameters:
    - start_date: Start date in YYYY-MM-DD format (optional, defaults to 30 days ago)
    - end_date: End date in YYYY-MM-DD format (optional, defaults to today)
    
    Returns daily averages for each metric within the specified date range.
    """
    try:
        from datetime import datetime, date, timedelta
        from zoneinfo import ZoneInfo
        
        # Get the current user
        current_user_id = get_jwt_identity()
        current_user = SellerService.get_by_id(current_user_id)
        if not current_user:
            return jsonify({"error": "User not found"}), 404
        
        # Validate user_id format
        if not user_id:
            return jsonify({"error": "User ID is required"}), 400
        
        # Check if current user has permission to view this user's performance
        # (Either viewing own data or admin/manager viewing any user's data)
        if user_id != current_user_id and current_user.role.value not in ['admin', 'manager']:
            return jsonify({"error": "Unauthorized to view this user's performance data"}), 403
        
        # Validate that target user exists
        target_user = SellerService.get_by_id(user_id)
        if not target_user:
            return jsonify({"error": "Target user not found"}), 404
        
        # Parse and validate date parameters
        today = date.today()
        thirty_days_ago = today - timedelta(days=30)
        
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Parse start_date
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({"error": "start_date must be in YYYY-MM-DD format"}), 400
        else:
            start_date = thirty_days_ago
        
        # Parse end_date
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return jsonify({"error": "end_date must be in YYYY-MM-DD format"}), 400
        else:
            end_date = today
        
        # Validate date range
        if start_date > end_date:
            return jsonify({"error": "start_date cannot be after end_date"}), 400
        
        # Check for reasonable date range (max 365 days)
        if (end_date - start_date).days > 365:
            return jsonify({"error": "Date range cannot exceed 365 days"}), 400
        
        logging.info(f"Getting performance metrics for user {target_user.email} from {start_date} to {end_date}")
        
        # Get user performance metrics
        performance_data = CallPerformanceService.get_user_performance_metrics(
            seller_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return jsonify({
            "message": "User performance metrics retrieved successfully",
            "user_info": {
                "user_id": user_id,
                "name": performance_data['seller_info']['name'],
                "email": performance_data['seller_info']['email']
            },
            "date_range": performance_data['date_range'],
            "daily_metrics": performance_data['daily_metrics'],
            "period_summary": performance_data['period_summary']
        }), 200
        
    except ValueError as e:
        logging.error(f"Validation error in get_user_performance_metrics: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error in get_user_performance_metrics: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error occurred"}), 500
