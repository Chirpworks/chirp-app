from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


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