from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from flask import request, jsonify


def get_date_range_from_timeframe(time_frame: str):
    """
    Get start and end dates for a given time frame.
    
    Args:
        time_frame: One of 'today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month'
        
    Returns:
        tuple: (start_date, end_date) both as datetime objects in Asia/Kolkata timezone
        
    Raises:
        ValueError: If time_frame is not supported
    """
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    now = datetime.now(kolkata_tz)
    
    if time_frame == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_frame == "yesterday":
        yesterday = now - timedelta(days=1)
        start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif time_frame == "this_week":
        days_since_monday = now.weekday()
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
    elif time_frame == "last_week":
        days_since_monday = now.weekday()
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday + 7)
        end_date = start_date + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
    elif time_frame == "this_month":
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        end_date = next_month - timedelta(microseconds=1)
    elif time_frame == "last_month":
        if now.month == 1:
            start_date = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start_date = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
    else:
        raise ValueError(f"Invalid time_frame: {time_frame}")
    
    return start_date, end_date


def get_granularity_from_timeframe(time_frame: str) -> str:
    """
    Get granularity (hourly or daily) based on time frame.
    
    Args:
        time_frame: One of 'today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month'
        
    Returns:
        str: 'hourly' for 'today' and 'yesterday', 'daily' for all others
    """
    return "hourly" if time_frame in ["today", "yesterday"] else "daily"


def validate_time_frame(time_frame: str) -> bool:
    """
    Validate if the provided time frame is supported.
    
    Args:
        time_frame: Time frame string to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    valid_time_frames = ["today", "yesterday", "this_week", "last_week", "this_month", "last_month"]
    return time_frame in valid_time_frames


def parse_date_range_params(default_days_back=30, max_days_range=365):
    """
    Parse and validate start_date and end_date query parameters with fallback to time_frame.
    Similar to performance metrics endpoints implementation.
    
    Args:
        default_days_back: Default number of days to go back if no start_date provided
        max_days_range: Maximum allowed date range in days
        
    Returns:
        tuple: (start_date, end_date, error_response)
        - If successful: (datetime, datetime, None)
        - If error: (None, None, (error_dict, status_code))
    """
    try:
        kolkata_tz = ZoneInfo("Asia/Kolkata")
        
        # Check if we have start_date and end_date parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # If no date parameters, fall back to time_frame parameter
        if not start_date_str and not end_date_str:
            time_frame = request.args.get("time_frame", "today")
            if not validate_time_frame(time_frame):
                return None, None, ({"error": "Invalid time_frame. Must be one of: today, yesterday, this_week, last_week, this_month, last_month"}, 400)
            start_datetime, end_datetime = get_date_range_from_timeframe(time_frame)
            return start_datetime, end_datetime, None
        
        # Use date range parameters
        today = date.today()
        default_start = today - timedelta(days=default_days_back)
        
        # Parse start_date
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                return None, None, ({"error": "start_date must be in YYYY-MM-DD format"}, 400)
        else:
            start_date = default_start
        
        # Parse end_date
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return None, None, ({"error": "end_date must be in YYYY-MM-DD format"}, 400)
        else:
            end_date = today
        
        # Validate date range
        if start_date > end_date:
            return None, None, ({"error": "start_date cannot be after end_date"}, 400)
        
        # Check for reasonable date range
        if (end_date - start_date).days > max_days_range:
            return None, None, ({"error": f"Date range cannot exceed {max_days_range} days"}, 400)
        
        # Convert to datetime objects with timezone for database queries
        start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=kolkata_tz)
        end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=kolkata_tz)
        
        return start_datetime, end_datetime, None
        
    except Exception as e:
        return None, None, ({"error": f"Error parsing date parameters: {str(e)}"}, 400) 