# Cloud Run Deployment Plan

## Context
The Salesforce MCP server is working locally. We need to deploy it to Google Cloud Run so it's accessible as a remote MCP endpoint. The user has a GCP project with billing enabled.

## Changes Required

### 1. Update Dockerfile for Cloud Run
**File:** `Dockerfile`
- Remove `COPY .env ./` (secrets injected at runtime via Secret Manager)
- Remove `HEALTHCHECK` directive (Cloud Run uses its own probes)
- Remove `EXPOSE 8000` (Cloud Run ignores it; PORT is set automatically)

No Python code changes needed — `app_mcp.py` already reads `PORT` from env vars.

### 2. Create `.dockerignore`
**File:** `.dockerignore` (new)
- Exclude `.env`, `.venv/`, `logs/`, `__pycache__/`, `.git/`, `.claude/`, `.DS_Store`
- Keeps build context small (especially important for Cloud Build uploads)

### 3. Create deploy script
**File:** `scripts/deploy-cloudrun.sh` (new)

Handles the full deployment:
1. Enable required GCP APIs (Cloud Run, Artifact Registry, Secret Manager, Cloud Build)
2. Create Artifact Registry Docker repo (idempotent)
3. Create secrets in Secret Manager (idempotent):
   - `PG_SF_DEV_CONSUMER_KEY` → mapped to env var `SF_CONSUMER_KEY`
   - `PG_SF_DEV_CONSUMER_SECRET` → mapped to env var `SF_CONSUMER_SECRET`
4. Build image via Cloud Build (no local Docker needed)
5. Deploy to Cloud Run with:
   - `--allow-unauthenticated` (demo)
   - `--memory=512Mi` (pandas needs headroom)
   - `--min-instances=0` / `--max-instances=3`
   - `--set-env-vars` for `SF_DOMAIN`, `LOG_LEVEL`
   - `--set-secrets` for consumer key/secret from Secret Manager
   - `--startup-cpu-boost` for faster cold starts
6. Verify health endpoint

The script will prompt the user to set their `PROJECT_ID` before running.

### 4. Cloud Run configuration rationale

| Setting | Value | Why |
|---|---|---|
| Memory | 512Mi | pandas dataframes for pipeline tools |
| CPU | 1 | Sufficient for demo |
| Min instances | 0 | Scale to zero when idle (cost) |
| Max instances | 3 | Safety cap |
| Concurrency | 10 | Async server can handle concurrent requests |
| Timeout | 60s | Salesforce API calls can be slow |
| Port | 8080 | Cloud Run default; app reads `PORT` env var |

## Files Modified
- `Dockerfile` — remove .env copy, HEALTHCHECK, EXPOSE
- `.dockerignore` — new file
- `scripts/deploy-cloudrun.sh` — new deploy script

## Verification
1. `curl ${SERVICE_URL}/health` → "OK"
2. Check Cloud Run logs for "Salesforce connected"
3. Test with FastMCP client pointed at `${SERVICE_URL}/mcp`
