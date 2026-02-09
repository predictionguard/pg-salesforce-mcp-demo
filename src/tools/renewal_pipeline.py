from typing import Dict, Any, Annotated, Optional
import pandas as pd
from datetime import datetime
import logging
from utils.data_cleaner import clean_for_json

logger = logging.getLogger(__name__)


async def generate_renewal_pipeline(
    sf_conn,
    start_date: Annotated[str, "Start date (YYYY-MM-DD)"],
    end_date: Annotated[str, "End date (YYYY-MM-DD)"],
    account_name: Annotated[Optional[str], "Filter by account"] = None,
) -> Dict[str, Any]:
    """Generate contract renewal pipeline report."""

    sf_conn.reconnect_if_needed()
    logger.info(f"Generating renewal pipeline: {start_date} to {end_date}")

    try:
        query = f"""
        SELECT Id, ContractNumber, Account.Name, StartDate, EndDate,
               ContractTerm, Status
        FROM Contract
        WHERE EndDate >= {start_date} AND EndDate <= {end_date}
          AND Status = 'Activated'
        """

        if account_name:
            query += f" AND Account.Name LIKE '%{account_name}%'"
        query += " ORDER BY EndDate ASC"

        result = sf_conn.sf.query(query)
        contracts = result.get("records", [])

        if not contracts:
            return {
                "status": "success",
                "total_contracts": 0,
                "note_to_LLM": "No contracts found in date range.",
            }

        # Analysis with pandas
        df = pd.DataFrame(
            [
                {
                    "contract_number": c.get("ContractNumber"),
                    "account_name": c.get("Account", {}).get("Name"),
                    "start_date": c.get("StartDate"),
                    "end_date": c.get("EndDate"),
                    "contract_term_months": c.get("ContractTerm"),
                }
                for c in contracts
            ]
        )

        df["days_until_expiration"] = (
            pd.to_datetime(df["end_date"]) - datetime.now()
        ).dt.days

        def categorize_urgency(days):
            if days <= 30:
                return "High Risk (< 30 days)"
            elif days <= 90:
                return "Medium Risk (30-90 days)"
            return "Low Risk (> 90 days)"

        df["urgency"] = df["days_until_expiration"].apply(categorize_urgency)

        urgency_summary = df["urgency"].value_counts().to_dict()

        return {
            "status": "success",
            "total_contracts": len(contracts),
            "urgency_summary": urgency_summary,
            "contracts": clean_for_json(df.to_dict("records")),
            "note_to_LLM": f"Found {len(contracts)} renewals. Present with urgency breakdown.",
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "note_to_LLM": "Failed to generate renewal pipeline.",
        }
