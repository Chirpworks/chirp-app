import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Intent:
    kind: str  # analytics_count_total_calls | analytics_seller_product_calls | rag_answer
    params: Dict[str, Any]


class IntentRouter:
    """Minimal rule-based intent detector for the answer endpoint.

    Extracts: seller mentions (by name keywords), product strings, month/date windows.
    Returns an Intent with normalized parameters.
    """

    MONTHS = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
    }

    @staticmethod
    def _parse_month_range(text: str) -> (Optional[datetime], Optional[datetime]):
        t = text.lower()
        for name, month in IntentRouter.MONTHS.items():
            if name in t:
                from datetime import timedelta
                now = datetime.now().astimezone()
                year = now.year
                start = datetime(year, month, 1, 0, 0, 0, tzinfo=now.tzinfo)
                if month == 12:
                    end = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=now.tzinfo) - timedelta(microseconds=1)
                else:
                    end = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=now.tzinfo) - timedelta(microseconds=1)
                return start, end
        return None, None

    @staticmethod
    def _parse_relative_range(text: str) -> (Optional[datetime], Optional[datetime]):
        """Basic parsing for: today, yesterday, this week/last week, this month/last month, last N days,
        and explicit YYYY-MM-DD to YYYY-MM-DD.
        """
        import re as _re
        from datetime import timedelta, date
        t = text.lower()
        now = datetime.now().astimezone()

        # Explicit range: from/to
        m = _re.search(r"(from|between)\s+(\d{4}-\d{2}-\d{2})\s+(to|and)\s+(\d{4}-\d{2}-\d{2})", t)
        if m:
            try:
                s = datetime.fromisoformat(m.group(2))
                e = datetime.fromisoformat(m.group(4))
                s = s.replace(tzinfo=now.tzinfo)
                e = e.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=now.tzinfo)
                return s, e
            except Exception:
                pass

        if "today" in t:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start, end
        if "yesterday" in t:
            y = now - timedelta(days=1)
            start = y.replace(hour=0, minute=0, second=0, microsecond=0)
            end = y.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start, end
        if "this week" in t:
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            return start, end
        if "last week" in t:
            start = now - timedelta(days=now.weekday() + 7)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59, microseconds=999999)
            return start, end
        if "this month" in t:
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            end = next_month - timedelta(microseconds=1)
            return start, end
        if "last month" in t:
            if now.month == 1:
                start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
            return start, end
        m = _re.search(r"last\s+(\d{1,3})\s+days?", t)
        if m:
            n = int(m.group(1))
            start = (now - timedelta(days=n)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
            return start, end
        return None, None

    @staticmethod
    def route(query: str):
        q = query.strip()
        lower = q.lower()

        # Date range inference with defaulting
        start, end = IntentRouter._parse_relative_range(lower)
        if not start and not end:
            start, end = IntentRouter._parse_month_range(lower)
        # Default: current month + full last month
        if not start and not end:
            from datetime import datetime, timedelta
            from dateutil.relativedelta import relativedelta
            now = datetime.now().astimezone()
            # current month
            current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # last month range
            last_month_end = current_month_start - timedelta(microseconds=1)
            last_month_start = (current_month_start - relativedelta(months=1)).replace(day=1)
            # combine: start=last_month_start, end=end_of_current_month (open-ended handled downstream)
            start, end = last_month_start, now

        # Pattern: total calls count (made/received)
        if re.search(r"\b(how many|count of|total)\s+(calls|meetings)\b", lower):
            params = {"start": start, "end": end, "direction": None, "answered": None}
            if re.search(r"\bmade\b|\boutgoing\b", lower):
                params["direction"] = "outgoing"
            elif re.search(r"\breceived\b|\bincoming\b", lower):
                params["direction"] = "incoming"
            if re.search(r"\bmissed\b|\brejected\b|not answered", lower):
                params["answered"] = "unanswered"
            elif re.search(r"\banswered\b|\bconnected\b", lower):
                params["answered"] = "answered"
            return Intent(kind="analytics_count_calls", params=params)

        # Pattern 2: seller + product calls
        if re.search(r"\b(calls|meetings)\b.*\bfor\b.*\b(product|plan|scheme)?\b", lower) and re.search(r"\bby\b|\bfrom\b", lower):
            # start,end already parsed above
            # crude product phrase after 'for'
            prod = None
            m = re.search(r"for\s+([A-Za-z0-9\s\-\.&]+)", q)
            if m:
                prod = m.group(1).strip().rstrip('?.,')
            # crude seller name after 'by'
            seller_name = None
            m2 = re.search(r"by\s+([A-Za-z\s\.]+)", q)
            if m2:
                seller_name = m2.group(1).strip().rstrip('?.,')
            return Intent(kind="analytics_seller_product_calls", params={
                "start": start, "end": end, "product_query": prod, "seller_name": seller_name,
            })

        # Pattern: number of buyers (engaged via calls) or total buyers
        if re.search(r"\b(how many|number of|count of)\s+(buyers|leads|customers)\b", lower):
            mode = "engaged" if re.search(r"\bcontacted|engaged|called|met\b", lower) else "total"
            return Intent(kind="analytics_count_buyers", params={"start": start, "end": end, "mode": mode})

        # Pattern: number of sellers (active vs total)
        if re.search(r"\b(how many|number of|count of)\s+(sellers|agents|reps|users|team members)\b", lower):
            mode = "active" if re.search(r"\bactive|made calls|received calls|called\b", lower) else "total"
            return Intent(kind="analytics_count_sellers", params={"start": start, "end": end, "mode": mode})

        # Pattern: number of products (catalog vs discussed)
        if re.search(r"\b(how many|number of|count of)\s+(products|skus|items)\b", lower):
            mode = "discussed" if re.search(r"\bdiscussed|talked about|mentioned\b", lower) else "catalog"
            return Intent(kind="analytics_count_products", params={"start": start, "end": end, "mode": mode})

        # Top sellers/products (check before rates to avoid capturing 'answered rate' within this phrase)
        if re.search(r"\b(top|best)\s+(sellers|agents|reps|users)\b.*\b(by|for)\s+(number of\s+)?calls\b", lower):
            metric = "total"
            lim = 5
            m = re.search(r"\btop\s+(\d{1,2})\b", lower)
            if m:
                try:
                    lim = int(m.group(1))
                except Exception:
                    lim = 5
            return Intent(kind="analytics_top_sellers", params={"start": start, "end": end, "metric": metric, "limit": lim})
        if re.search(r"\b(top|best)\s+(sellers|agents|reps|users)\b", lower):
            metric = "answered" if re.search(r"\b(answered|connected)\b", lower) else "total"
            lim = 5
            m = re.search(r"\btop\s+(\d{1,2})\b", lower)
            if m:
                try:
                    lim = int(m.group(1))
                except Exception:
                    lim = 5
            return Intent(kind="analytics_top_sellers", params={"start": start, "end": end, "metric": metric, "limit": lim})
        if re.search(r"\b(top|most discussed)\s+products\b", lower):
            lim = 5
            m = re.search(r"\btop\s+(\d{1,2})\b", lower)
            if m:
                try:
                    lim = int(m.group(1))
                except Exception:
                    lim = 5
            return Intent(kind="analytics_top_products", params={"start": start, "end": end, "limit": lim})

        # Rates and averages
        if re.search(r"\b(answered rate|connect rate|answer rate)\b", lower):
            return Intent(kind="analytics_answered_rate", params={"start": start, "end": end})
        if re.search(r"\b(missed rate|rejected rate)\b", lower):
            return Intent(kind="analytics_missed_rate", params={"start": start, "end": end})
        # Explicit average forms
        if re.search(r"\b(avg|average)\s+(outgoing|incoming)(\s+call[s]?)?\s*(duration|time)?\b", lower):
            dirn = "outgoing" if "outgoing" in lower else "incoming"
            return Intent(kind="analytics_avg_duration", params={"start": start, "end": end, "direction": dirn})
        if re.search(r"\baverage\s+(call\s+)?duration\b", lower) or re.search(r"\b(avg|average)\s+call\s*time\b", lower):
            dirn = "incoming" if "incoming" in lower or "received" in lower else ("outgoing" if "outgoing" in lower or "made" in lower else None)
            return Intent(kind="analytics_avg_duration", params={"start": start, "end": end, "direction": dirn})

        # Timeseries
        if re.search(r"\b(time[-\s]?series|trend|over time)\b", lower) or re.search(r"\b(daily|weekly)\b", lower):
            gran = "weekly" if "weekly" in lower else "daily"
            return Intent(kind="analytics_timeseries_calls", params={"start": start, "end": end, "granularity": gran})

        # Fallback to RAG; include defaulted start/end so RAG can use time scoping
        return Intent(kind="rag_answer", params={"start": start, "end": end})



