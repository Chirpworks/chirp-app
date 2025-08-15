import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import text

from app import db
from app.analytics.sql_registry import get_sql_registry
from app.external.llm.open_ai.chat_gpt import OpenAIClient


logger = logging.getLogger(__name__)


class LLMSQLRunner:
    """Guarded LLM-to-SQL executor.

    - Builds a prompt with an allowlisted schema registry
    - Requests parameterized SELECT-only SQL with :agency_id, optional :start and :end
    - Validates SQL text for safety (no DDL/DML, only allowlisted tables/columns)
    - Executes read-only and returns rows
    """

    @staticmethod
    def _build_prompt(question: str) -> str:
        reg = get_sql_registry()
        payload = {
            "task": "Generate a single SELECT-only SQL for PostgreSQL to answer the question.",
            "rules": [
                "MUST use only allowlisted tables/columns from the registry.",
                "MUST include a WHERE sellers.agency_id = :agency_id OR join to sellers and filter by it.",
                "If time is implied, use BETWEEN :start AND :end on *_time columns (e.g., start_time, created_at).",
                "Return ONLY raw SQL text. No backticks, no markdown, no explanations.",
                "Ensure the query includes a LIMIT 200.",
                "Prefer selecting human-readable names (e.g., sellers.name, products.name) instead of internal IDs. Avoid exposing UUIDs in the SELECT list.",
            ],
            "registry": reg,
            "question": question,
            "params": {"agency_id": ":agency_id", "start": ":start", "end": ":end"}
        }
        return json.dumps(payload)

    @staticmethod
    def _extract_tables(sql: str) -> Tuple[Dict[str, str], str]:
        """Return mapping of table->alias (alias defaults to table) and lowercased SQL."""
        s = sql
        s_low = s.lower()
        tables: Dict[str, str] = {}
        # FROM clauses
        for m in re.finditer(r"\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:((?:as\s+)?(?!on\b|using\b|where\b|group\b|order\b|limit\b|left\b|right\b|full\b|inner\b|outer\b|cross\b|join\b)[a-zA-Z_][a-zA-Z0-9_]*))?", s_low):
            tbl = m.group(1)
            alias = (m.group(2) or '').replace('as ', '').strip() or tbl
            tables[tbl] = alias
        # JOIN clauses
        for m in re.finditer(r"\bjoin\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:((?:as\s+)?(?!on\b|using\b|where\b|group\b|order\b|limit\b|left\b|right\b|full\b|inner\b|outer\b|cross\b|join\b)[a-zA-Z_][a-zA-Z0-9_]*))?", s_low):
            tbl = m.group(1)
            alias = (m.group(2) or '').replace('as ', '').strip() or tbl
            tables[tbl] = alias
        return tables, s_low

    @staticmethod
    def _ensure_limit(sql: str, max_rows: int = 200) -> str:
        s_low = sql.lower()
        if re.search(r"\blimit\b", s_low):
            return sql
        return f"{sql.strip()} LIMIT {max_rows}"

    @staticmethod
    def _normalize_whitespace(sql: str) -> str:
        # Collapse whitespace while preserving spacing between tokens
        s = re.sub(r"\s+", " ", sql).strip()
        # Ensure spaces around keywords that often border tokens
        s = re.sub(r"\s*,\s*", ", ", s)
        return s

    @staticmethod
    def _has_valid_where_segment(sql: str) -> bool:
        s_low = sql.lower()
        m = re.search(r"\bwhere\b", s_low)
        if not m:
            return True
        after = s_low[m.end():]
        # WHERE must not immediately be followed by a clause keyword
        if re.match(r"\s*(group\s+by|order\s+by|limit)\b", after):
            return False
        return True

    @staticmethod
    def _sanitize_sql(sql: str, tables: Dict[str, str]) -> Optional[str]:
        s = LLMSQLRunner._normalize_whitespace(sql)
        s_low = s.lower()
        # Basic structural checks
        if not s_low.startswith("select "):
            return None
        if not LLMSQLRunner._has_valid_where_segment(s):
            return None
        # Avoid accidental alias keywords like 'left.on'
        if re.search(r"\b(on|left|right|full|inner|outer|cross)\.agency_id\b", s_low):
            return None
        # If sellers present, ensure condition references its alias, not a keyword
        if "sellers" in tables:
            sellers_alias = tables["sellers"].lower()
            if sellers_alias not in ("sellers", "s") and not re.search(rf"\b{sellers_alias}\.agency_id\b", s_low):
                # allow case where we will inject later; still pass here
                pass
        return s

    @staticmethod
    def _inject_agency_filter(sql: str, tables: Dict[str, str]) -> str:
        """If sellers is present but agency filter missing, inject it into WHERE safely."""
        s = sql
        s_low = s.lower()
        if "sellers" not in tables:
            return s
        sellers_alias = tables["sellers"]
        if f"{sellers_alias}.agency_id" in s_low:
            return s
        # Find WHERE and insert 'AND alias.agency_id = :agency_id' before GROUP/ORDER/LIMIT or end
        where_match = re.search(r"\bwhere\b", s, flags=re.IGNORECASE)
        if where_match:
            start_idx = where_match.end()
            # find next clause after WHERE
            tail_match = re.search(r"\b(group\s+by|order\s+by|limit)\b", s[start_idx:], flags=re.IGNORECASE)
            if tail_match:
                insert_pos = start_idx + tail_match.start()
                # insert condition followed by a space before the next clause
                return s[:insert_pos] + f" {sellers_alias}.agency_id = :agency_id " + s[insert_pos:]
            else:
                # append to end of WHERE conditions
                return s + f" AND {sellers_alias}.agency_id = :agency_id"
        # No WHERE: add it before next clause or at end
        head_match = re.search(r"\b(group\s+by|order\s+by|limit)\b", s, flags=re.IGNORECASE)
        if head_match:
            pos = head_match.start()
            return s[:pos] + f" WHERE {sellers_alias}.agency_id = :agency_id " + s[pos:]
        return s + f" WHERE {sellers_alias}.agency_id = :agency_id"

    @staticmethod
    def _requires_sellers_presence(tables: Dict[str, str]) -> bool:
        """When referencing meetings or app_calls, sellers join must be present."""
        uses_fact = any(t in tables for t in ("meetings", "app_calls"))
        if not uses_fact:
            return True
        return "sellers" in tables

    @staticmethod
    def _is_safe(sql: str, reg: Dict[str, Any]) -> bool:
        s = sql.strip()
        s_low = s.lower()
        if not s_low.startswith("select"):
            return False
        # Only single statement
        if ";" in s_low:
            return False
        forbidden = [" insert ", " update ", " delete ", " drop ", " alter ", " create ", " grant ", " revoke ", " truncate "]
        if any(tok in s_low for tok in forbidden):
            return False
        # table allowlist
        allowed_tables = set(reg["tables"].keys())
        tables, _ = LLMSQLRunner._extract_tables(s)
        for t in tables.keys():
            if t not in allowed_tables:
                return False
        # Ensure sellers presence when facts used
        if not LLMSQLRunner._requires_sellers_presence(tables):
            return False
        return True

    def run(self, *, question: str, agency_id: str, start: Optional[str] = None, end: Optional[str] = None, model: str = "gpt-4o") -> Dict[str, Any]:
        prompt = self._build_prompt(question)
        llm = OpenAIClient()
        sql_text = llm.send_prompt(prompt=prompt, model=model)
        if not isinstance(sql_text, dict):
            return {"error": "LLM did not return JSON"}
        candidate = sql_text.get("sql") or sql_text.get("query") or sql_text.get("SQL") or ""
        reg = get_sql_registry()
        if not candidate or not self._is_safe(candidate, reg):
            return {"error": "Unsafe or empty SQL from LLM", "sql": candidate}
        # enforce agency filter and limit, then sanitize
        tables, _ = self._extract_tables(candidate)
        candidate = self._inject_agency_filter(candidate, tables)
        candidate = self._ensure_limit(candidate)
        sanitized = self._sanitize_sql(candidate, tables)
        if not sanitized:
            return {"error": "Malformed SQL after sanitation", "sql": candidate}
        candidate = sanitized
        try:
            result = db.session.execute(text(candidate), {"agency_id": agency_id, "start": start, "end": end})
            rows = result.fetchall()
            cols = result.keys() if rows else []
            data = [dict(zip(cols, r)) for r in rows]
            # Guard: if question is an unanswered trend and no rows, signal fallback
            lowered_q = (question or "").lower()
            if ("unanswered" in lowered_q or "missed" in lowered_q) and len(data) == 0:
                return {"data": [], "sql": candidate, "suggest_fallback": True}
            return {"data": data, "sql": candidate}
        except Exception as e:
            logger.error(f"LLM SQL execution failed: {e}")
            try:
                db.session.rollback()
            except Exception:
                pass
            return {"error": str(e), "sql": candidate}


