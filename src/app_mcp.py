import os
import sys
from pathlib import Path
from typing import Dict, Any, Annotated, Optional
from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
import json

sys.path.append(str(Path(__file__).parent))

from salesforce_connection import SalesforceConnection
from utils.logging_config import setup_logging
from utils.data_cleaner import clean_for_json

load_dotenv()
logger = setup_logging(os.getenv("LOG_LEVEL", "INFO"))


# Initialize MCP server (no auth for demo)
mcp = FastMCP("Salesforce MCP Server")


# Global Salesforce connection (Client Credentials flow)
# Connection is lazy - will connect on first use
sf_conn = SalesforceConnection(
    consumer_key=os.getenv("SF_CONSUMER_KEY"),
    consumer_secret=os.getenv("SF_CONSUMER_SECRET"),
    domain=os.getenv("SF_DOMAIN"),
)

# Don't connect during startup - let Cloud Run start the server first
# Connection will happen on first tool call
logger.info(f"Salesforce connection configured (domain: {os.getenv('SF_DOMAIN')})")
logger.info("Connection will be established on first tool call")

# Import tools
from tools.soql_query import execute_sf_query
from tools.renewal_pipeline import generate_renewal_pipeline
from tools.sales_pipeline import generate_sales_pipeline


# Register tools
@mcp.tool(
    name="execute_sf_query",
    title="Execute Salesforce SOQL Query",
    description="Execute arbitrary SOQL query and return structured results",
)
async def tool_execute_sf_query(
    query: Annotated[str, "SOQL query to execute"],
    description: Annotated[str, "Query description"] = None,
) -> Dict[str, Any]:
    return await execute_sf_query(sf_conn, query, description)


@mcp.tool(
    name="generate_renewal_pipeline",
    title="Generate Contract Renewal Pipeline",
    description="Report on upcoming contract renewals with urgency analysis",
)
async def tool_generate_renewal_pipeline(
    start_date: Annotated[str, "Start date (YYYY-MM-DD)"],
    end_date: Annotated[str, "End date (YYYY-MM-DD)"],
    account_name: Annotated[Optional[str], "Filter by account"] = None,
) -> Dict[str, Any]:
    return await generate_renewal_pipeline(
        sf_conn, start_date, end_date, account_name
    )


@mcp.tool(
    name="generate_sales_pipeline",
    title="Generate Sales Pipeline Report",
    description="Sales pipeline with stage analysis and weighted forecasting",
)
async def tool_generate_sales_pipeline(
    stage_filter: Annotated[Optional[list[str]], "Filter by stages"] = None,
    owner_name: Annotated[Optional[str], "Filter by owner"] = None,
    min_amount: Annotated[Optional[float], "Minimum amount"] = None,
    close_date_start: Annotated[Optional[str], "Close date start"] = None,
    close_date_end: Annotated[Optional[str], "Close date end"] = None,
) -> Dict[str, Any]:
    return await generate_sales_pipeline(
        sf_conn, stage_filter, owner_name, min_amount, close_date_start, close_date_end
    )


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check endpoint - returns OK if server is running."""
    logger.info("Health check called")
    return PlainTextResponse("OK")


@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> PlainTextResponse:
    """Readiness check - tests if Salesforce connection can be established."""
    logger.info("Readiness check called")
    try:
        sf_conn.reconnect_if_needed()
        return PlainTextResponse("READY")
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        from starlette.responses import Response
        return Response(content=f"NOT READY: {str(e)}", status_code=503)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    logger.info("=" * 60)
    logger.info("SALESFORCE MCP SERVER STARTUP")
    logger.info("=" * 60)
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"SF Domain: {os.getenv('SF_DOMAIN', 'NOT SET')}")
    logger.info(f"SF Consumer Key: {'SET' if os.getenv('SF_CONSUMER_KEY') else 'NOT SET'}")
    logger.info(f"SF Consumer Secret: {'SET' if os.getenv('SF_CONSUMER_SECRET') else 'NOT SET'}")
    logger.info(f"Log Level: {os.getenv('LOG_LEVEL', 'INFO')}")
    logger.info("=" * 60)
    logger.info(f"MCP endpoint: http://{host}:{port}/mcp")
    logger.info(f"Health endpoint: http://{host}:{port}/health")
    logger.info("=" * 60)
    logger.info("Starting server (Salesforce connection will be lazy)...")

    try:
        mcp.run(transport="http", host=host, port=port)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise
