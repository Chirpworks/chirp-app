from typing import Dict, List


def get_sql_registry() -> Dict[str, Dict[str, List[str]]]:
    """Allowlist of tables and columns that the LLM may reference.

    Use snake_case table names as in the DB. Only SELECT is permitted.
    """
    return {
        "tables": {
            "agencies": {
                "columns": ["id", "name", "description"],
                "semantics": "Organizations. agency.id is referenced by sellers.agency_id, buyers.agency_id, products.agency_id."
            },
            "sellers": {
                "columns": ["id", "agency_id", "name", "email", "phone", "role", "manager_id"],
                "semantics": "Sales reps/agents. agency_id is mandatory; manager_id denotes reporting line."
            },
            "buyers": {
                "columns": ["id", "agency_id", "phone", "name", "email", "company_name"],
                "semantics": "Customers/leads. phone is normalized and unique per agency via constraint."
            },
            "products": {
                "columns": ["id", "agency_id", "name", "description", "features"],
                "semantics": "Per-agency product catalog. features JSON may include key-value attributes."
            },
            "meetings": {
                "columns": [
                    "id", "buyer_id", "seller_id", "source", "start_time", "end_time",
                    "transcription", "direction", "title", "summary", "overall_summary",
                    "type", "detected_call_type", "detected_products"
                ],
                "semantics": "Answered calls/conversations. direction in ('incoming','outgoing'). detected_products is JSON/text of mentioned products."
            },
            "app_calls": {
                "columns": ["id", "mobile_app_call_id", "buyer_number", "seller_number", "call_type", "start_time", "end_time", "duration", "user_id", "status"],
                "semantics": "Raw mobile calls. Unanswered: incoming status in ('missed','rejected'); outgoing status = 'not_answered'. user_id -> sellers.id."
            },
            "call_performances": {
                "columns": [
                    "id", "meeting_id", "intro", "rapport_building", "need_realization", "script_adherance",
                    "objection_handling", "pricing_and_negotiation", "closure_and_next_steps", "conversation_structure_and_flow",
                    "product_details_analysis", "objection_handling_analysis", "overall_performance_summary", "overall_score",
                    "analyzed_at", "created_at", "updated_at"
                ],
                "semantics": "Per-meeting analysis and metric scores stored as JSON; meeting_id -> meetings.id."
            }
        },
        "notes": [
            "Use sellers.agency_id = :agency_id to scope queries.",
            "Join meetings via meetings.seller_id = sellers.id; join app_calls via app_calls.user_id = sellers.id.",
            "Time-window filters should compare *_time BETWEEN :start AND :end when provided.",
            "Count unanswered using app_calls: incoming missed/rejected; outgoing not_answered. Answered = meetings rows.",
            "Use DISTINCT for unique buyers/sellers/products where appropriate.",
        ],
    }


