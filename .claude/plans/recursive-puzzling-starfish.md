# Salesforce MCP Server Demo - Implementation Plan

## Overview

Build a FastMCP-based server providing three Salesforce query tools:
1. `execute_sf_query` - Execute arbitrary SOQL queries
2. `generate_renewal_pipeline` - Contract renewal reports
3. `generate_sales_pipeline` - Lead/opportunity pipeline reports

**Tech Stack:** FastMCP, simple-salesforce, JWT auth, uv package management

---

## Project Structure

```
salesforce-auth-pg/
├── src/
│   ├── app_mcp.py                    # Main MCP server entry point
│   ├── salesforce_connection.py      # Salesforce connection handler
│   ├── tools/
│   │   ├── soql_query.py            # execute_sf_query tool
│   │   ├── renewal_pipeline.py      # generate_renewal_pipeline tool
│   │   └── sales_pipeline.py        # generate_sales_pipeline tool
│   └── utils/
│       ├── logging_config.py        # Logging setup
│       └── data_cleaner.py          # JSON serialization helpers
├── scripts/
│   ├── generate_token.py            # JWT token generator
│   └── upload_demo_data.py          # Data upload script
├── tests/
│   ├── test_connection.py
│   ├── test_tools.py
│   └── test_mcp_client.py
├── Salesforce_GovCon_Demo_Pack/     # Demo CSV data (existing)
├── logs/
├── .env.example
├── .env
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Phase 1: Foundation Setup

### 1.1 Initialize Project

```bash
# Initialize uv project
cd /Users/bengsoon/Projects/salesforce-auth-pg
uv init

# Create project structure
mkdir -p src/tools src/utils scripts tests logs
touch src/__init__.py src/tools/__init__.py src/utils/__init__.py
```

### 1.2 Configure Dependencies

**pyproject.toml:**
```toml
[project]
name = "salesforce-mcp-server"
version = "0.1.0"
description = "FastMCP server for Salesforce with JWT auth"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.12.4",
    "simple-salesforce>=1.12.9",
    "pandas>=2.3.0",
    "python-dotenv>=1.2.0",
    "pyjwt>=2.8.0",
    "loguru>=0.7.2",
    "uvicorn>=0.37.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]
```

```bash
uv sync
```

### 1.3 Environment Configuration

**Create `.env`:**
```bash
# Salesforce Authentication
SF_USERNAME=your-username@example.com
SF_PASSWORD=your-password
SF_SECURITY_TOKEN=your-security-token
SF_DOMAIN=login  # or 'test' for sandbox

# Application
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Optional: JWT Authentication (for production/secure deployments)
# Uncomment these if you want to add JWT auth later:
# JWT_SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_urlsafe(64))">
# JWT_ALGORITHM=HS256
# JWT_ISSUER=salesforce-mcp
# JWT_AUDIENCE=salesforce-client
```

---

## Phase 2: Core Components

### 2.1 Salesforce Connection Class

**File:** [src/salesforce_connection.py](src/salesforce_connection.py)

**Pattern from:** `/Users/bengsoon/Projects/srg-report-generator/backend/salesforce_utils.py`

```python
from simple_salesforce import Salesforce
import logging

logger = logging.getLogger(__name__)

class SalesforceConnection:
    def __init__(self, username: str, password: str, security_token: str, domain: str = 'login'):
        self.username = username
        self.password = password
        self.security_token = security_token
        self.domain = domain
        self.sf = None

    def connect(self) -> Salesforce:
        """Establish connection to Salesforce."""
        logger.info(f"Connecting to Salesforce: {self.username}")
        try:
            self.sf = Salesforce(
                username=self.username,
                password=self.password,
                security_token=self.security_token,
                domain=self.domain
            )
            logger.info("✓ Connected to Salesforce")
            return self.sf
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """Test if connection is active."""
        if not self.sf:
            return False
        try:
            self.sf.query("SELECT Id FROM User LIMIT 1")
            return True
        except:
            return False

    def reconnect_if_needed(self):
        """Reconnect if connection lost."""
        if not self.test_connection():
            logger.warning("Connection lost, reconnecting...")
            self.connect()
```

### 2.2 Utility Modules

**File:** [src/utils/logging_config.py](src/utils/logging_config.py)

```python
from loguru import logger
import sys
from pathlib import Path

def setup_logging(log_level: str = "INFO"):
    logger.remove()

    # Console handler
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>",
        colorize=True
    )

    # File handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "salesforce_mcp.log",
        level=log_level,
        rotation="1 day",
        retention="7 days"
    )

    return logger
```

**File:** [src/utils/data_cleaner.py](src/utils/data_cleaner.py)

```python
import math
import pandas as pd

def clean_for_json(obj):
    """Recursively clean object for JSON serialization."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, (float, int)):
        try:
            if math.isnan(obj) or math.isinf(obj):
                return None
        except (TypeError, ValueError):
            pass
        return float(obj) if isinstance(obj, float) else int(obj)
    elif obj is None:
        return None
    else:
        try:
            if pd.isna(obj):
                return None
        except (TypeError, ValueError):
            pass
    return obj
```

---

## Phase 3: MCP Tools Implementation

### 3.1 Tool 1: execute_sf_query

**File:** [src/tools/soql_query.py](src/tools/soql_query.py)

```python
from typing import Dict, Any, Annotated
import logging
import time
from ..utils.data_cleaner import clean_for_json

logger = logging.getLogger(__name__)

async def execute_sf_query(
    sf_conn,
    query: Annotated[str, "SOQL query to execute"],
    description: Annotated[str, "Query description"] = None
) -> Dict[str, Any]:
    """Execute arbitrary SOQL query."""

    sf_conn.reconnect_if_needed()

    query_preview = ' '.join(query.split())[:200]
    logger.info(f"Executing SOQL: {query_preview}")

    start_time = time.time()

    try:
        result = sf_conn.sf.query(query)
        duration_ms = (time.time() - start_time) * 1000

        records = result.get('records', [])
        cleaned_records = clean_for_json(records)

        return {
            "status": "success",
            "total_count": result.get('totalSize', len(records)),
            "returned_count": len(records),
            "records": cleaned_records,
            "execution_time_ms": round(duration_ms, 2),
            "note_to_LLM": f"Retrieved {len(records)} records. Present in clear format."
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
            "note_to_LLM": f"Query failed. {suggestion}"
        }
```

### 3.2 Tool 2: generate_renewal_pipeline

**File:** [src/tools/renewal_pipeline.py](src/tools/renewal_pipeline.py)

```python
from typing import Dict, Any, Annotated, Optional
import pandas as pd
from datetime import datetime
import logging
from ..utils.data_cleaner import clean_for_json

logger = logging.getLogger(__name__)

async def generate_renewal_pipeline(
    sf_conn,
    start_date: Annotated[str, "Start date (YYYY-MM-DD)"],
    end_date: Annotated[str, "End date (YYYY-MM-DD)"],
    account_name: Annotated[Optional[str], "Filter by account"] = None,
    min_value: Annotated[Optional[float], "Minimum value"] = None
) -> Dict[str, Any]:
    """Generate contract renewal pipeline report."""

    sf_conn.reconnect_if_needed()
    logger.info(f"Generating renewal pipeline: {start_date} to {end_date}")

    try:
        query = f"""
        SELECT Id, ContractNumber, Account.Name, StartDate, EndDate,
               ContractTerm, Status, TotalPrice__c
        FROM Contract
        WHERE EndDate >= {start_date} AND EndDate <= {end_date}
          AND Status = 'Activated'
        """

        if account_name:
            query += f" AND Account.Name LIKE '%{account_name}%'"
        if min_value:
            query += f" AND TotalPrice__c >= {min_value}"
        query += " ORDER BY EndDate ASC"

        result = sf_conn.sf.query(query)
        contracts = result.get('records', [])

        if not contracts:
            return {
                "status": "success",
                "total_contracts": 0,
                "total_value": 0,
                "note_to_LLM": "No contracts found in date range."
            }

        # Analysis with pandas
        df = pd.DataFrame([{
            'contract_number': c.get('ContractNumber'),
            'account_name': c.get('Account', {}).get('Name'),
            'end_date': c.get('EndDate'),
            'total_value': c.get('TotalPrice__c', 0)
        } for c in contracts])

        df['days_until_expiration'] = (
            pd.to_datetime(df['end_date']) - datetime.now()
        ).dt.days

        def categorize_urgency(days):
            if days <= 30:
                return "High Risk (< 30 days)"
            elif days <= 90:
                return "Medium Risk (30-90 days)"
            return "Low Risk (> 90 days)"

        df['urgency'] = df['days_until_expiration'].apply(categorize_urgency)

        return {
            "status": "success",
            "total_contracts": len(contracts),
            "total_pipeline_value": round(df['total_value'].sum(), 2),
            "contracts": clean_for_json(df.to_dict('records')),
            "note_to_LLM": f"Found {len(contracts)} renewals. Present with urgency."
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "note_to_LLM": "Failed to generate renewal pipeline."
        }
```

### 3.3 Tool 3: generate_sales_pipeline

**File:** [src/tools/sales_pipeline.py](src/tools/sales_pipeline.py)

```python
from typing import Dict, Any, Annotated, Optional
import pandas as pd
import logging
from ..utils.data_cleaner import clean_for_json

logger = logging.getLogger(__name__)

async def generate_sales_pipeline(
    sf_conn,
    stage_filter: Annotated[Optional[list[str]], "Filter by stages"] = None,
    owner_name: Annotated[Optional[str], "Filter by owner"] = None,
    min_amount: Annotated[Optional[float], "Minimum amount"] = None,
    close_date_start: Annotated[Optional[str], "Close date start"] = None,
    close_date_end: Annotated[Optional[str], "Close date end"] = None
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
        opportunities = result.get('records', [])

        if not opportunities:
            return {
                "status": "success",
                "total_opportunities": 0,
                "total_pipeline_value": 0,
                "note_to_LLM": "No opportunities found."
            }

        df = pd.DataFrame([{
            'name': o.get('Name'),
            'account': o.get('Account', {}).get('Name'),
            'stage': o.get('StageName'),
            'amount': o.get('Amount', 0),
            'probability': o.get('Probability', 0),
            'close_date': o.get('CloseDate')
        } for o in opportunities])

        df['weighted_amount'] = df['amount'] * (df['probability'] / 100)

        pipeline_by_stage = df.groupby('stage').agg({
            'name': 'count',
            'amount': 'sum',
            'weighted_amount': 'sum'
        }).to_dict('index')

        return {
            "status": "success",
            "total_opportunities": len(opportunities),
            "total_pipeline_value": round(df['amount'].sum(), 2),
            "weighted_pipeline_value": round(df['weighted_amount'].sum(), 2),
            "pipeline_by_stage": clean_for_json(pipeline_by_stage),
            "opportunities": clean_for_json(df.to_dict('records')),
            "note_to_LLM": f"Pipeline has {len(opportunities)} opportunities. Show stage breakdown."
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "note_to_LLM": "Failed to generate sales pipeline."
        }
```

---

## Phase 4: MCP Server Setup

### 4.1 Main Application (No Auth - Simple Version)

**File:** [src/app_mcp.py](src/app_mcp.py)

**Pattern from:** `/Users/bengsoon/Projects/greek-room-api/src/app_mcp.py`

```python
import os
import sys
from pathlib import Path
from typing import Dict, Any, Annotated, Optional
from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

sys.path.append(str(Path(__file__).parent))

from salesforce_connection import SalesforceConnection
from utils.logging_config import setup_logging
from utils.data_cleaner import clean_for_json

load_dotenv()
logger = setup_logging(os.getenv("LOG_LEVEL", "INFO"))

# Initialize MCP server (no auth for demo)
mcp = FastMCP("Salesforce MCP Server")

# Global Salesforce connection
sf_conn = SalesforceConnection(
    username=os.getenv("SF_USERNAME"),
    password=os.getenv("SF_PASSWORD"),
    security_token=os.getenv("SF_SECURITY_TOKEN"),
    domain=os.getenv("SF_DOMAIN", "login")
)

try:
    sf_conn.connect()
    logger.info("✓ Salesforce connected")
except Exception as e:
    logger.warning(f"Initial connection failed: {e}")

# Import tools
from tools.soql_query import execute_sf_query
from tools.renewal_pipeline import generate_renewal_pipeline
from tools.sales_pipeline import generate_sales_pipeline

# Register tools
@mcp.tool(
    name="execute_sf_query",
    title="Execute Salesforce SOQL Query",
    description="Execute arbitrary SOQL query and return structured results"
)
async def tool_execute_sf_query(
    query: Annotated[str, "SOQL query to execute"],
    description: Annotated[str, "Query description"] = None
) -> Dict[str, Any]:
    return await execute_sf_query(sf_conn, query, description)

@mcp.tool(
    name="generate_renewal_pipeline",
    title="Generate Contract Renewal Pipeline",
    description="Report on upcoming contract renewals with urgency analysis"
)
async def tool_generate_renewal_pipeline(
    start_date: Annotated[str, "Start date (YYYY-MM-DD)"],
    end_date: Annotated[str, "End date (YYYY-MM-DD)"],
    account_name: Annotated[Optional[str], "Filter by account"] = None,
    min_value: Annotated[Optional[float], "Minimum value"] = None
) -> Dict[str, Any]:
    return await generate_renewal_pipeline(sf_conn, start_date, end_date, account_name, min_value)

@mcp.tool(
    name="generate_sales_pipeline",
    title="Generate Sales Pipeline Report",
    description="Sales pipeline with stage analysis and weighted forecasting"
)
async def tool_generate_sales_pipeline(
    stage_filter: Annotated[Optional[list[str]], "Filter by stages"] = None,
    owner_name: Annotated[Optional[str], "Filter by owner"] = None,
    min_amount: Annotated[Optional[float], "Minimum amount"] = None,
    close_date_start: Annotated[Optional[str], "Close date start"] = None,
    close_date_end: Annotated[Optional[str], "Close date end"] = None
) -> Dict[str, Any]:
    return await generate_sales_pipeline(sf_conn, stage_filter, owner_name, min_amount, close_date_start, close_date_end)

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting MCP Server on {host}:{port}")
    mcp.run(transport="http", host=host, port=port)
```

### 4.2 Optional: JWT Authentication (Skip for Now)

If you want to add JWT authentication later, you can modify the server initialization:

```python
# Add to app_mcp.py if you want JWT auth
from fastmcp.server.auth.providers.jwt import JWTVerifier

jwt_verifier = JWTVerifier(
    public_key=os.getenv("JWT_SECRET_KEY"),
    issuer=os.getenv("JWT_ISSUER", "salesforce-mcp"),
    audience=os.getenv("JWT_AUDIENCE", "salesforce-client"),
    algorithm=os.getenv("JWT_ALGORITHM", "HS256")
)

mcp = FastMCP("Salesforce MCP Server", auth=jwt_verifier)
```

**Token Generator** [scripts/generate_token.py](scripts/generate_token.py) (optional):

```python
import jwt
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def generate_jwt_token(expiry_days=30):
    payload = {
        "iss": os.getenv("JWT_ISSUER", "salesforce-mcp"),
        "aud": os.getenv("JWT_AUDIENCE", "salesforce-client"),
        "exp": datetime.utcnow() + timedelta(days=expiry_days),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

if __name__ == "__main__":
    print(f"JWT Token:\n{generate_jwt_token()}")
```

---

## Phase 5: Data Upload (Programmatic Approach)

### 5.1 Upload Products

**File:** [scripts/upload_demo_data.py](scripts/upload_demo_data.py)

```python
import pandas as pd
from simple_salesforce import Salesforce
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import random

load_dotenv()

sf = Salesforce(
    username=os.getenv("SF_USERNAME"),
    password=os.getenv("SF_PASSWORD"),
    security_token=os.getenv("SF_SECURITY_TOKEN"),
    domain=os.getenv("SF_DOMAIN", "login")
)

print("=" * 60)
print("SALESFORCE DEMO DATA UPLOADER")
print("=" * 60)

# Step 1: Upload Products
print("\n[1/4] Uploading Products...")
products_df = pd.read_csv("Salesforce_GovCon_Demo_Pack/products.csv")
product_ids = {}

for idx, row in products_df.iterrows():
    try:
        result = sf.Product2.create({
            'Name': row['Name'],
            'ProductCode': row['ProductCode'],
            'Family': row['Family'],
            'IsActive': bool(row['IsActive']),
            'Description': row['Description']
        })
        product_ids[row['ProductCode']] = result['id']
        print(f"  ✓ {row['Name']}")
    except Exception as e:
        print(f"  ✗ {row['Name']}: {e}")

print(f"\n✓ Uploaded {len(product_ids)} products")

# Step 2: Create Sample Accounts
print("\n[2/4] Creating Sample Accounts...")
accounts = [
    {"Name": "Department of Defense", "Industry": "Government"},
    {"Name": "Department of Homeland Security", "Industry": "Government"},
    {"Name": "Federal Aviation Administration", "Industry": "Government"},
    {"Name": "National Security Agency", "Industry": "Government"},
    {"Name": "US Customs & Border Protection", "Industry": "Government"}
]
account_ids = []

for acc in accounts:
    try:
        result = sf.Account.create(acc)
        account_ids.append(result['id'])
        print(f"  ✓ {acc['Name']}")
    except Exception as e:
        print(f"  ✗ {acc['Name']}: {e}")

print(f"\n✓ Created {len(account_ids)} accounts")

# Step 3: Create Sample Contracts (for renewal pipeline)
print("\n[3/4] Creating Sample Contracts...")
contract_count = 0

for i, account_id in enumerate(account_ids):
    # Create 2-3 contracts per account
    for j in range(random.randint(2, 3)):
        start_date = datetime.now() - timedelta(days=random.randint(180, 540))
        contract_term = random.choice([12, 24, 36])
        end_date = start_date + timedelta(days=contract_term * 30)

        try:
            result = sf.Contract.create({
                'AccountId': account_id,
                'Status': 'Draft',
                'StartDate': start_date.strftime('%Y-%m-%d'),
                'ContractTerm': contract_term
            })
            contract_id = result['id']

            # Activate contract
            sf.Contract.update(contract_id, {'Status': 'Activated'})
            contract_count += 1
            print(f"  ✓ Contract {contract_count} (expires: {end_date.strftime('%Y-%m-%d')})")
        except Exception as e:
            print(f"  ✗ Contract creation failed: {e}")

print(f"\n✓ Created {contract_count} contracts")

# Step 4: Create Sample Opportunities (for sales pipeline)
print("\n[4/4] Creating Sample Opportunities...")
stages = ['Prospecting', 'Qualification', 'Needs Analysis', 'Value Proposition',
          'Proposal/Price Quote', 'Negotiation/Review']
opp_count = 0

for i, account_id in enumerate(account_ids):
    # Create 3-5 opportunities per account
    for j in range(random.randint(3, 5)):
        product_code = random.choice(list(product_ids.keys()))
        product_name = products_df[products_df['ProductCode'] == product_code]['Name'].iloc[0]
        amount = random.randint(50000, 1500000)
        stage = random.choice(stages)
        probability = {
            'Prospecting': 10,
            'Qualification': 20,
            'Needs Analysis': 40,
            'Value Proposition': 60,
            'Proposal/Price Quote': 75,
            'Negotiation/Review': 90
        }[stage]

        close_date = datetime.now() + timedelta(days=random.randint(30, 180))

        try:
            result = sf.Opportunity.create({
                'Name': f"{product_name} - {accounts[i]['Name'][:20]}",
                'AccountId': account_id,
                'StageName': stage,
                'Amount': amount,
                'Probability': probability,
                'CloseDate': close_date.strftime('%Y-%m-%d')
            })
            opp_count += 1
            print(f"  ✓ Opp {opp_count}: ${amount:,} ({stage})")
        except Exception as e:
            print(f"  ✗ Opportunity creation failed: {e}")

print(f"\n✓ Created {opp_count} opportunities")

print("\n" + "=" * 60)
print("DATA UPLOAD COMPLETE!")
print("=" * 60)
print(f"Products:      {len(product_ids)}")
print(f"Accounts:      {len(account_ids)}")
print(f"Contracts:     {contract_count}")
print(f"Opportunities: {opp_count}")
print("=" * 60)
```

**Run:**
```bash
uv run python scripts/upload_demo_data.py
```

This script will:
1. Upload all 30 products from your CSV
2. Create 5 government agency accounts
3. Create 10-15 contracts (for renewal pipeline testing)
4. Create 15-25 opportunities (for sales pipeline testing)

---

## Phase 6: Testing

### 6.1 Test Connection

**File:** [tests/test_connection.py](tests/test_connection.py)

```python
import pytest
from src.salesforce_connection import SalesforceConnection
import os
from dotenv import load_dotenv

load_dotenv()

@pytest.fixture
def sf_conn():
    return SalesforceConnection(
        username=os.getenv("SF_USERNAME"),
        password=os.getenv("SF_PASSWORD"),
        security_token=os.getenv("SF_SECURITY_TOKEN")
    )

def test_connection(sf_conn):
    sf = sf_conn.connect()
    assert sf is not None
    assert sf_conn.test_connection() is True

def test_query_products(sf_conn):
    sf_conn.connect()
    result = sf_conn.sf.query("SELECT Id, Name FROM Product2 LIMIT 5")
    assert result['totalSize'] >= 0
```

### 6.2 Run Tests

```bash
uv run pytest tests/ -v
```

### 6.3 Manual Testing

```bash
# Start server
uv run python src/app_mcp.py

# Generate token
TOKEN=$(uv run python scripts/generate_token.py)

# Test execute_sf_query
curl -X POST http://localhost:8000/mcp/tool/execute_sf_query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT Id, Name FROM Product2 LIMIT 5"}'
```

---

## Phase 7: Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.local/bin/uv sync --no-dev

COPY src/ ./src/
COPY .env ./
RUN mkdir -p logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "src/app_mcp.py"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  salesforce-mcp:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
```

### Build & Run

```bash
docker-compose up --build
```

---

## Verification Checklist

### After Implementation

- [ ] Salesforce connection works (`test_connection.py` passes)
- [ ] Demo data uploaded to Salesforce
- [ ] JWT token generation works
- [ ] Health endpoint responds: `curl http://localhost:8000/health`
- [ ] `execute_sf_query` tool returns product data
- [ ] `generate_renewal_pipeline` handles missing Contract data gracefully
- [ ] `generate_sales_pipeline` handles missing Opportunity data gracefully
- [ ] Docker build succeeds
- [ ] All tests pass: `uv run pytest tests/ -v`

### End-to-End Test

```python
# Test all three tools with valid JWT
TOKEN = generate_jwt_token()

# 1. Query products
response = requests.post(
    "http://localhost:8000/mcp/tool/execute_sf_query",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"query": "SELECT Id, Name, ProductCode FROM Product2 LIMIT 10"}
)
assert response.status_code == 200

# 2. Generate renewal pipeline (may return no data if no contracts)
response = requests.post(
    "http://localhost:8000/mcp/tool/generate_renewal_pipeline",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "start_date": "2026-01-01",
        "end_date": "2026-12-31"
    }
)
assert response.status_code == 200

# 3. Generate sales pipeline (may return no data if no opportunities)
response = requests.post(
    "http://localhost:8000/mcp/tool/generate_sales_pipeline",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={}
)
assert response.status_code == 200
```

---

## Critical Files Referenced

- **Salesforce Connection Pattern:** `/Users/bengsoon/Projects/srg-report-generator/backend/salesforce_utils.py`
- **MCP Server Pattern:** `/Users/bengsoon/Projects/greek-room-api/src/app_mcp.py`
- **Docker Pattern:** `/Users/bengsoon/Projects/greek-room-api/Dockerfile.mcp`
- **Demo Data:** `/Users/bengsoon/Projects/salesforce-auth-pg/Salesforce_GovCon_Demo_Pack/products.csv`

---

## Using the MCP Server

### Direct API Testing (No Auth - Simple)

```bash
# Start the server
uv run python src/app_mcp.py

# Test health endpoint
curl http://localhost:8000/health

# Test execute_sf_query tool
curl -X POST http://localhost:8000/mcp/tool/execute_sf_query \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT Id, Name FROM Product2 LIMIT 10"}'

# Test renewal pipeline
curl -X POST http://localhost:8000/mcp/tool/generate_renewal_pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2026-01-01",
    "end_date": "2026-12-31"
  }'

# Test sales pipeline
curl -X POST http://localhost:8000/mcp/tool/generate_sales_pipeline \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Claude Desktop Integration (Future)

To use with Claude Desktop, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "salesforce": {
      "command": "uv",
      "args": ["run", "python", "/Users/bengsoon/Projects/salesforce-auth-pg/src/app_mcp.py"],
      "env": {
        "SF_USERNAME": "your-username",
        "SF_PASSWORD": "your-password",
        "SF_SECURITY_TOKEN": "your-token"
      }
    }
  }
}
```

## Known Limitations & Notes

1. **Sample Data**: Script will create realistic Contract and Opportunity records for testing both pipeline tools.

2. **No Authentication (Initial)**: Starting without JWT auth for simplicity. Add it later if deploying publicly or need security.

3. **Field Assumptions**: Tools assume standard Salesforce schema. May need minor adjustments based on actual Developer account configuration.

4. **Rate Limits**: Developer accounts have API call limits (typically 15,000 API calls per 24 hours). Connection pooling helps, but monitor usage.

5. **Demo Focus**: This is optimized for demonstration, not production. No caching, rate limiting, or advanced error recovery.

6. **FastMCP**: This implementation uses FastMCP framework which provides HTTP transport for easy testing with curl or integration with Claude Desktop.

---

## Implementation Timeline

- **Day 1**: Foundation (structure, dependencies, connection, utilities)
- **Day 2**: Tools (implement all 3 MCP tools)
- **Day 3**: MCP server setup, token generation
- **Day 4**: Data upload, schema validation
- **Day 5**: Testing, documentation
- **Day 6**: Docker deployment
- **Day 7**: Polish and demo preparation
