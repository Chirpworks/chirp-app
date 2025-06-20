from datetime import date, datetime, timedelta


def human_readable_duration(dt1, dt2):
    diff = abs(dt1 - dt2)  # use abs() to ensure positive timedelta
    days = diff.days
    seconds = diff.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} min{'s' if minutes != 1 else ''}")
    if seconds:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return ', '.join(parts) if parts else '0 seconds'


def compute_date_range(tf: str):
    """Return (start, end) datetimes for the given time_frame string."""
    today = date.today()
    tf = tf.strip().lower()
    # start of today
    if tf == "today":
        start = datetime.combine(today, datetime.min.time())
        end = start + timedelta(days=1)
    # yesterday
    elif tf == "yesterday":
        start = datetime.combine(today - timedelta(days=1), datetime.min.time())
        end = start + timedelta(days=1)
    # this week (Mon – next Mon)
    elif tf == "this_week":
        mon = today - timedelta(days=today.weekday())
        start = datetime.combine(mon, datetime.min.time())
        end = start + timedelta(days=7)
    # last week (Mon – Mon of previous week)
    elif tf == "last_week":
        mon_this = today - timedelta(days=today.weekday())
        start = datetime.combine(mon_this - timedelta(days=7), datetime.min.time())
        end = start + timedelta(days=7)
    # this month (1st – 1st next month)
    elif tf == "this_month":
        first = today.replace(day=1)
        start = datetime.combine(first, datetime.min.time())
        # compute first of next month
        year, month = first.year, first.month
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        end = datetime.combine(date(year, month, 1), datetime.min.time())
    # last month (1st last month – 1st this month)
    elif tf == "last_month":
        first_this = today.replace(day=1)
        last_day_prev = first_this - timedelta(days=1)
        start = datetime.combine(last_day_prev.replace(day=1), datetime.min.time())
        end = datetime.combine(first_this, datetime.min.time())
    else:
        raise ValueError(f"Unknown time_frame: {tf}")
    return start, end
