import json
import logging
from typing import Any, Dict, List, Optional

from app.external.llm.open_ai.chat_gpt import OpenAIClient
from app.search.intent_router import IntentRouter
from app.analytics import AnalyticsTool
from app.search.search_service import SemanticSearchService
from app.analytics.llm_sql import LLMSQLRunner


logger = logging.getLogger(__name__)


class SemanticAnswerService:
    """Compose an answer using retrieved context and GPT with citations.

    MVP strategy: top-k vector results → simple diversification by truncation →
    build a compact context → single-shot prompt to gpt-4.1-mini → JSON output.
    """

    def __init__(self):
        self.search = SemanticSearchService()
        self.llm = OpenAIClient()

    def answer(
        self,
        *,
        query: str,
        agency_id: str,
        k: int = 8,
        types: Optional[List[str]] = None,
        seller_id: Optional[str] = None,
        model: str = "gpt-4.1-mini",
        max_context_chars: int = 6000,
        per_doc_chars: int = 1000,
    ) -> Dict[str, Any]:
        intent = IntentRouter.route(query)

        # Prefer LLM-SQL path for analytics intents when enabled, to enable A/B testing
        import os
        use_llm_sql = os.getenv("ANALYTICS_LLM_SQL", "off").lower() in ("1", "true", "yes", "on")
        if use_llm_sql and intent.kind.startswith("analytics_"):
            start = intent.params.get("start")
            end = intent.params.get("end")
            llm_sql = LLMSQLRunner()
            sql_result = llm_sql.run(
                question=query,
                agency_id=agency_id,
                start=start.isoformat() if start else None,
                end=end.isoformat() if end else None,
            )
            if isinstance(sql_result, dict) and sql_result.get("data") is not None:
                # Fallback to deterministic timeseries when LLM-SQL suggests empty unanswered
                if sql_result.get("suggest_fallback"):
                    det = self._dispatch_analytics(intent=intent, agency_id=agency_id)
                    if det is not None:
                        return det
                # summarization pass using raw prompt; include SQL and limited rows
                try:
                    rows_preview = sql_result["data"][:50]
                    sql_text = sql_result.get("sql")
                    summary_prompt = (
                        "You are an expert data analyst.\n"
                        "Task: Given the user's question, the executed SQL, and the first rows of the result,\n"
                        "produce a concise natural-language answer (one or two sentences).\n"
                        "- Be precise and avoid fluff.\n"
                        "- If data is empty or insufficient, say so.\n"
                        "- Do NOT output code or SQL.\n"
                        "- Prefer human names and readable labels; do not expose internal IDs/UUIDs in the answer.\n\n"
                        f"Question: {query}\n\nSQL:\n{sql_text}\n\nRows (preview):\n{json.dumps(rows_preview, indent=2)}\n"
                    )
                    raw = self.llm.send_prompt_raw(prompt=summary_prompt, model=model)
                    if raw:
                        answer_txt = self._sanitize_summary_text(raw.strip())
                        return {
                            "answer": answer_txt,
                            "sources": [{"type": "sql", "sql": sql_text, "rows": len(sql_result.get("data", []))}],
                        }
                except Exception:
                    pass
                # Fallback to raw data if summarization fails
                return {
                    "answer": json.dumps(sql_result.get("data", [])[:10]),
                    "sources": [{"type": "sql", "sql": sql_result.get("sql")}],
                }

        if intent.kind == "analytics_count_total_calls":
            return AnalyticsTool.count_total_calls(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
            )

        if intent.kind == "analytics_count_calls":
            return AnalyticsTool.count_calls(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
                direction=intent.params.get("direction"),
                answered=intent.params.get("answered"),
            )

        if intent.kind == "analytics_seller_product_calls":
            resolved_seller_id = seller_id
            if not resolved_seller_id and intent.params.get("seller_name"):
                from app.models.seller import Seller
                name = intent.params.get("seller_name")
                s = (
                    Seller.query
                    .filter(Seller.agency_id == agency_id)
                    .filter(Seller.name.ilike(f"%{name}%"))
                    .first()
                )
                resolved_seller_id = str(s.id) if s else None

            if not resolved_seller_id:
                return {"answer": "0", "sources": [{"type": "analytics", "reason": "seller_not_found"}]}

            return AnalyticsTool.count_calls_by_seller_for_product(
                agency_id=agency_id,
                seller_id=resolved_seller_id,
                product_query=intent.params.get("product_query") or "",
                start=intent.params.get("start"),
                end=intent.params.get("end"),
            )

        if intent.kind == "analytics_count_buyers":
            return AnalyticsTool.count_buyers(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
                mode=intent.params.get("mode") or "total",
            )

        if intent.kind == "analytics_count_sellers":
            return AnalyticsTool.count_sellers(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
                mode=intent.params.get("mode") or "total",
            )

        if intent.kind == "analytics_count_products":
            return AnalyticsTool.count_products(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
                mode=intent.params.get("mode") or "catalog",
            )

        if intent.kind == "analytics_answered_rate":
            return AnalyticsTool.answered_rate(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
            )

        if intent.kind == "analytics_missed_rate":
            return AnalyticsTool.missed_rate(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
            )

        if intent.kind == "analytics_avg_duration":
            return AnalyticsTool.avg_call_duration(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
                direction=intent.params.get("direction"),
            )

        if intent.kind == "analytics_top_sellers":
            return AnalyticsTool.top_sellers_by_calls(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
                metric=intent.params.get("metric") or "total",
                limit=int(intent.params.get("limit") or 5),
            )

        if intent.kind == "analytics_top_products":
            return AnalyticsTool.top_products_discussed(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
                limit=int(intent.params.get("limit") or 5),
            )

        if intent.kind == "analytics_timeseries_calls":
            return AnalyticsTool.timeseries_calls(
                agency_id=agency_id,
                start=intent.params.get("start"),
                end=intent.params.get("end"),
                granularity=intent.params.get("granularity") or "daily",
            )

        # If deterministic router fell through to RAG, ask LLM to classify intent when enabled;
        # If LLM says analytics, immediately execute analytics flow (LLM-SQL → deterministic fallback). Otherwise proceed to RAG.
        if intent.kind == "rag_answer" and os.getenv("ANALYTICS_LLM_INTENT", "off").lower() in ("1", "true", "yes", "on"):
            payload = {
                "task": "Classify the user's question as 'analytics' or 'rag', and if analytics, map to one of the allowed analytics intents with params.",
                "allowed_analytics_intents": [
                    "analytics_count_calls", "analytics_seller_product_calls", "analytics_count_buyers",
                    "analytics_count_sellers", "analytics_count_products", "analytics_answered_rate",
                    "analytics_missed_rate", "analytics_avg_duration", "analytics_top_sellers",
                    "analytics_top_products", "analytics_timeseries_calls"
                ],
                "param_hints": {
                    "start": "ISO datetime or null",
                    "end": "ISO datetime or null",
                    "direction": "incoming|outgoing|null",
                    "answered": "answered|unanswered|null",
                    "seller_name": "string|null",
                    "product_query": "string|null",
                    "metric": "answered|total|null",
                    "granularity": "daily|weekly|null",
                    "limit": "integer|null"
                },
                "question": query,
                "instructions": [
                    "Return strict JSON with keys: mode ('analytics'|'rag'), kind (when analytics), params (when analytics).",
                    "Do not include markdown or backticks."
                ],
            }
            res = self.llm.send_prompt(prompt=json.dumps(payload), model="gpt-4.1-mini")
            if isinstance(res, dict) and res.get("mode") == "analytics" and isinstance(res.get("params"), dict):
                try:
                    ai_kind = res.get("kind") or "analytics_count_calls"
                    # Correctly create the new intent
                    new_intent = Intent(kind=ai_kind, params=res.get("params", {}))
                    # Immediately dispatch to the correct analytics path
                    analytics_result = self._dispatch_analytics(intent=new_intent, agency_id=agency_id)
                    if analytics_result:
                        return analytics_result
                except Exception as e:
                    logger.error(f"Error dispatching LLM-classified analytics intent: {e}")
                    # Fall through to RAG if dispatch fails
                    pass

        # Default: RAG
        results = self.search.search(
            query=query,
            agency_id=agency_id,
            k=k,
            types=types,
            seller_id=seller_id,
            start=intent.params.get("start"),
            end=intent.params.get("end"),
        )

        if not results:
            return {
                "answer": "I don't have enough information to answer that based on your data.",
                "sources": [],
            }

        context_blocks: List[str] = []
        sources_for_prompt: List[Dict[str, Any]] = []

        for idx, r in enumerate(results, start=1):
            snippet = (r.get("text") or "")[:per_doc_chars]
            block = (
                f"Source {idx}:\n"
                f"id={r.get('id')} type={r.get('type')} meeting_id={r.get('meeting_id')} "
                f"buyer_id={r.get('buyer_id')} product_id={r.get('product_id')} seller_id={r.get('seller_id')}\n"
                f"distance={r.get('distance')}\n"
                f"---\n{snippet}\n"
            )
            context_blocks.append(block)
            sources_for_prompt.append({
                "id": r.get("id"),
                "type": r.get("type"),
                "meeting_id": r.get("meeting_id"),
                "buyer_id": r.get("buyer_id"),
                "product_id": r.get("product_id"),
                "seller_id": r.get("seller_id"),
                "distance": r.get("distance"),
            })
            if sum(len(b) for b in context_blocks) >= max_context_chars:
                break

        context_text = "\n\n".join(context_blocks)

        prompt = self._build_prompt(query=query, context=context_text)
        try:
            llm_result = self.llm.send_prompt(prompt=prompt, model=model)
        except Exception as e:
            logger.error(f"Answer LLM call failed: {e}")
            llm_result = None

        if not isinstance(llm_result, dict):
            return {
                "answer": "I couldn't synthesize an answer right now.",
                "sources": sources_for_prompt,
            }

        llm_result.setdefault("sources", sources_for_prompt)
        return llm_result

    @staticmethod
    def _build_prompt(*, query: str, context: str) -> str:
        instruction = {
            "task": "Answer the user question strictly based on the provided sources.",
            "rules": [
                "Use only the supplied context. If insufficient, say you don't have enough information.",
                "Be concise and specific.",
                "Return strictly valid JSON with keys: answer (string) and sources (array).",
                "Do not wrap the JSON in backticks or any markdown fences.",
            ],
            "output_schema": {
                "answer": "string",
                "sources": [
                    {
                        "id": "string",
                        "type": "string",
                        "meeting_id": "string|null",
                        "buyer_id": "string|null",
                        "product_id": "string|null",
                        "seller_id": "string|null",
                        "distance": "number|null"
                    }
                ]
            }
        }
        payload = {
            "instruction": instruction,
            "question": query,
            "context": context,
            "respond_with": {
                "format": "json",
                "keys": ["answer", "sources"]
            }
        }
        return json.dumps(payload)

    @staticmethod
    def _sanitize_summary_text(text: str) -> str:
        # Remove parenthetical seller_id/UUID mentions
        import re
        text = re.sub(r"\(seller_id:[^)]+\)", "", text)
        text = re.sub(r"\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b", "", text, flags=re.IGNORECASE)
        # Remove lingering phrases referencing IDs
        text = re.sub(r"\b[Ss]eller with ID:?\s*", "", text)
        # Remove empty parentheses left after removals
        text = re.sub(r"\(\s*\)", "", text)
        # Collapse double spaces created by removals
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text

    @staticmethod
    def _parse_dt(value):
        if value is None:
            return None
        from datetime import datetime
        try:
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            return value
        except Exception:
            return None

    def _dispatch_analytics(self, *, intent, agency_id: str) -> Optional[Dict[str, Any]]:
        start = self._parse_dt(intent.params.get("start"))
        end = self._parse_dt(intent.params.get("end"))
        kind = intent.kind
        if kind == "analytics_count_total_calls":
            return AnalyticsTool.count_total_calls(agency_id=agency_id, start=start, end=end)
        if kind == "analytics_count_calls":
            return AnalyticsTool.count_calls(
                agency_id=agency_id,
                start=start,
                end=end,
                direction=intent.params.get("direction"),
                answered=intent.params.get("answered"),
            )
        if kind == "analytics_seller_product_calls":
            from app.models.seller import Seller
            seller_id = intent.params.get("seller_id")
            if not seller_id and intent.params.get("seller_name"):
                s = (
                    Seller.query
                    .filter(Seller.agency_id == agency_id)
                    .filter(Seller.name.ilike(f"%{intent.params.get('seller_name')}%"))
                    .first()
                )
                seller_id = str(s.id) if s else None
            if not seller_id:
                return {"answer": "0", "sources": [{"type": "analytics", "reason": "seller_not_found"}]}
            return AnalyticsTool.count_calls_by_seller_for_product(
                agency_id=agency_id,
                seller_id=seller_id,
                product_query=intent.params.get("product_query") or "",
                start=start,
                end=end,
            )
        if kind == "analytics_count_buyers":
            return AnalyticsTool.count_buyers(agency_id=agency_id, start=start, end=end, mode=intent.params.get("mode") or "total")
        if kind == "analytics_count_sellers":
            return AnalyticsTool.count_sellers(agency_id=agency_id, start=start, end=end, mode=intent.params.get("mode") or "total")
        if kind == "analytics_count_products":
            return AnalyticsTool.count_products(agency_id=agency_id, start=start, end=end, mode=intent.params.get("mode") or "catalog")
        if kind == "analytics_answered_rate":
            return AnalyticsTool.answered_rate(agency_id=agency_id, start=start, end=end)
        if kind == "analytics_missed_rate":
            return AnalyticsTool.missed_rate(agency_id=agency_id, start=start, end=end)
        if kind == "analytics_avg_duration":
            return AnalyticsTool.avg_call_duration(agency_id=agency_id, start=start, end=end, direction=intent.params.get("direction"))
        if kind == "analytics_top_sellers":
            return AnalyticsTool.top_sellers_by_calls(
                agency_id=agency_id,
                start=start,
                end=end,
                metric=intent.params.get("metric") or "total",
                limit=int(intent.params.get("limit") or 5),
            )
        if kind == "analytics_top_products":
            return AnalyticsTool.top_products_discussed(
                agency_id=agency_id,
                start=start,
                end=end,
                limit=int(intent.params.get("limit") or 5),
            )
        if kind == "analytics_timeseries_calls":
            return AnalyticsTool.timeseries_calls(agency_id=agency_id, start=start, end=end, granularity=intent.params.get("granularity") or "daily")
        return None



