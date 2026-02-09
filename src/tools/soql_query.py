from typing import Dict, Any, Annotated
import logging
import time
from utils.data_cleaner import clean_for_json

logger = logging.getLogger(__name__)


async def execute_sf_query(
    sf_conn,
    query: Annotated[str, "SOQL query to execute"],
    description: Annotated[str, "Query description"] = None,
) -> Dict[str, Any]:
    """Execute arbitrary SOQL query."""

    sf_conn.reconnect_if_needed()

    query_preview = " ".join(query.split())[:200]
    logger.info(f"Executing SOQL: {query_preview}")

    start_time = time.time()

    try:
        result = sf_conn.sf.query(query)
        duration_ms = (time.time() - start_time) * 1000

        records = result.get("records", [])
        cleaned_records = clean_for_json(records)

        return {
            "status": "success",
            "total_count": result.get("totalSize", len(records)),
            "returned_count": len(records),
            "records": cleaned_records,
            "execution_time_ms": round(duration_ms, 2),
            "note_to_LLM": f"Retrieved {len(records)} records. Present in clear format.",
        }
    except Exception as e:
        error_msg = str(e)

        if "INVALID_FIELD" in error_msg:
            suggestion = "Invalid field name. Check available fields."
        elif "MALFORMED_QUERY" in error_msg:
            suggestion = "Malformed SOQL syntax."
        else:
            suggestion = "Check query syntax and field names."

        return {
            "status": "error",
            "error_message": error_msg,
            "suggestion": suggestion,
            "note_to_LLM": f"Query failed. {suggestion}",
        }
