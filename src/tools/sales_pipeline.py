from typing import Dict, Any, Annotated, Optional
import pandas as pd
import logging
from utils.data_cleaner import clean_for_json

logger = logging.getLogger(__name__)


async def generate_sales_pipeline(
    sf_conn,
    stage_filter: Annotated[Optional[list[str]], "Filter by stages"] = None,
    owner_name: Annotated[Optional[str], "Filter by owner"] = None,
    min_amount: Annotated[Optional[float], "Minimum amount"] = None,
    close_date_start: Annotated[Optional[str], "Close date start"] = None,
    close_date_end: Annotated[Optional[str], "Close date end"] = None,
) -> Dict[str, Any]:
    """Generate sales pipeline report."""

    sf_conn.reconnect_if_needed()
    logger.info("Generating sales pipeline")

    try:
        query = """
        SELECT Id, Name, Account.Name, StageName, Amount, Probability,
               CloseDate, Type, LeadSource, Owner.Name
        FROM Opportunity
        WHERE IsClosed = false
        """

        if stage_filter:
            stages = "', '".join(stage_filter)
            query += f" AND StageName IN ('{stages}')"
        if owner_name:
            query += f" AND Owner.Name LIKE '%{owner_name}%'"
        if min_amount:
            query += f" AND Amount >= {min_amount}"
        if close_date_start:
            query += f" AND CloseDate >= {close_date_start}"
        if close_date_end:
            query += f" AND CloseDate <= {close_date_end}"

        query += " ORDER BY Amount DESC"

        result = sf_conn.sf.query(query)
        opportunities = result.get("records", [])

        if not opportunities:
            return {
                "status": "success",
                "total_opportunities": 0,
                "total_pipeline_value": 0,
                "note_to_LLM": "No opportunities found.",
            }

        df = pd.DataFrame(
            [
                {
                    "name": o.get("Name"),
                    "account": o.get("Account", {}).get("Name"),
                    "stage": o.get("StageName"),
                    "amount": o.get("Amount", 0),
                    "probability": o.get("Probability", 0),
                    "close_date": o.get("CloseDate"),
                }
                for o in opportunities
            ]
        )

        df["weighted_amount"] = df["amount"] * (df["probability"] / 100)

        pipeline_by_stage = df.groupby("stage").agg(
            {"name": "count", "amount": "sum", "weighted_amount": "sum"}
        ).to_dict("index")

        return {
            "status": "success",
            "total_opportunities": len(opportunities),
            "total_pipeline_value": round(df["amount"].sum(), 2),
            "weighted_pipeline_value": round(df["weighted_amount"].sum(), 2),
            "pipeline_by_stage": clean_for_json(pipeline_by_stage),
            "opportunities": clean_for_json(df.to_dict("records")),
            "note_to_LLM": f"Pipeline has {len(opportunities)} opportunities. Show stage breakdown.",
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "note_to_LLM": "Failed to generate sales pipeline.",
        }
