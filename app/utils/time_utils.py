from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import request


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


def parse_date_range_params(default_days_back: int = 7):
    """
    Parse date range parameters from request, supporting both new start_date/end_date 
    and legacy time_frame parameters for backward compatibility.
    
    Args:
        default_days_back: Default number of days back if no parameters provided
        
    Returns:
        tuple: (start_date, end_date, error) where error is None on success or (message, status_code) on error
    """
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date") 
    time_frame = request.args.get("time_frame")
    
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    
    # If both new and old parameters are provided, prioritize new ones
    if start_date_str or end_date_str:
        if not start_date_str or not end_date_str:
            return None, None, ("Both start_date and end_date are required when using date range parameters", 400)
        
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").replace(tzinfo=kolkata_tz)
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=kolkata_tz)
            
            if start_date > end_date:
                return None, None, ("start_date cannot be after end_date", 400)
                
            return start_date, end_date, None
            
        except ValueError:
            return None, None, ("Invalid date format. Use YYYY-MM-DD format", 400)
    
    # Legacy time_frame parameter support
    elif time_frame:
        if not validate_time_frame(time_frame):
            return None, None, ("Invalid time_frame. Must be one of: today, yesterday, this_week, last_week, this_month, last_month", 400)
        
        try:
            start_date, end_date = get_date_range_from_timeframe(time_frame)
            return start_date, end_date, None
        except ValueError as e:
            return None, None, (str(e), 400)
    
    # Default behavior - last N days
    else:
        now = datetime.now(kolkata_tz)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = (now - timedelta(days=default_days_back)).replace(hour=0, minute=0, second=0, microsecond=0)
        return start_date, end_date, None 