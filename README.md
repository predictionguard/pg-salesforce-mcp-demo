# Example of Setting up MCP server with FastMCP

## Salesforce Demo MCP

A demonstration of how to build a production-ready MCP (Model Context Protocol) server for Salesforce integration using [FastMCP](https://github.com/jlowin/fastmcp).

## What this demonstrates

- Defining MCP tools with `@mcp.tool()` and typed, annotated parameters
- Adding custom HTTP routes (health, readiness checks) alongside MCP endpoints
- Serving the MCP protocol over stateless HTTP using `mcp.http_app()`
- Deploying the server as a containerized service (Docker + Google Cloud Run)
- Testing MCP tools programmatically with the `fastmcp.Client`

## Project structure

```
src/
  app_mcp.py               # FastMCP server, tool registration, ASGI app
  salesforce_connection.py # External service connection with caching
  tools/
    soql_query.py          # Tool: execute arbitrary SOQL queries
    renewal_pipeline.py    # Tool: contract renewal report
    sales_pipeline.py      # Tool: sales pipeline with forecasting
  utils/
    data_cleaner.py        # JSON serialization helpers
    logging_config.py      # Loguru setup
tests/
  test_with_fastmcp_client.py  # FastMCP client test script
scripts/
  deploy-cloudrun.sh       # GCP Cloud Run deployment script
Dockerfile
pyproject.toml
```

## How the server is built

### 1. Create the server

```python
from fastmcp import FastMCP

mcp = FastMCP("Salesforce MCP Server")
```

### 2. Register tools

Each tool is a decorated async function. Parameters use `Annotated` for schema descriptions that the MCP client (and the LLM) sees.

```python
from typing import Annotated, Dict, Any

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
```

### 3. Add custom HTTP routes

FastMCP lets you attach arbitrary Starlette routes to the same server — useful for health checks and readiness probes.

```python
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    """Health check — returns OK if server is running."""
    return PlainTextResponse("OK")

@mcp.custom_route("/ready", methods=["GET"])
async def readiness_check(request: Request) -> PlainTextResponse:
    """Readiness check — tests if Salesforce connection can be established."""
    try:
        sf_conn.reconnect_if_needed()
        return PlainTextResponse("READY")
    except Exception as e:
        return Response(content=f"NOT READY: {str(e)}", status_code=503)
```

### 4. Run the server

`mcp.run()` starts the server using FastMCP's built-in HTTP transport. The Salesforce connection is lazy — it is established on the first tool call rather than at startup, which allows the server to pass health checks before the external service is confirmed reachable.

```python
mcp.run(transport="http", host=host, port=port)
```

The MCP endpoint is available at `http://localhost:8000/mcp`.

## Running locally

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- A `.env` file with Salesforce credentials

### Install and run

```bash
uv sync
uv run python src/app_mcp.py
```

### Test with the FastMCP client

```bash
uv run python tests/test_with_fastmcp_client.py
```

The test script connects to the running server, lists available tools, and calls them — the same way any MCP host (Claude, Cursor, etc.) would.


## Deploying to Cloud

Because the server is a standard ASGI app, it can be deployed to any platform that runs containers or Python runtimes — Google Cloud Run, AWS App Runner, Azure Container Apps, etc.

## Connecting to Agent Forge

Add the server to Agent Forge as Custom MCP Server:

```json
[
  {
    "type": "mcp",
    "server_url": "https://salesforce-mcp-<your-hash>.run.app/mcp",
    "server_label": "salesforce",
    "server_description": "Salesforce data access — query records, contract renewals, and sales pipeline reports",
    "authorization": "Your Bearer Token",
    "allowed_tools": ["execute_sf_query", "generate_renewal_pipeline", "generate_sales_pipeline"]
  }
]
```

