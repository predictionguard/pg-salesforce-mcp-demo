#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Cloud Run Deployment Script for Salesforce MCP Server
# ============================================================
# Prerequisites:
#   - gcloud CLI installed and authenticated (gcloud auth login)
#   - GCP project with billing enabled
#   - Salesforce Consumer Key and Secret ready
# ============================================================

# ============ CONFIGURE THESE ============
PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID env var}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="salesforce-mcp"
REPO_NAME="salesforce-mcp-repo"
IMAGE_TAG="latest"
SF_DOMAIN="orgfarm-c9cdfab41a-dev-ed.develop.my"
# =========================================

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"

echo "============================================================"
echo "Deploying Salesforce MCP Server to Cloud Run"
echo "  Project:  ${PROJECT_ID}"
echo "  Region:   ${REGION}"
echo "  Service:  ${SERVICE_NAME}"
echo "  Image:    ${IMAGE_URI}"
echo "============================================================"

# --- Step 1: Enable APIs ---
echo ""
echo "==> [1/5] Enabling GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  --project="${PROJECT_ID}"

# --- Step 2: Create Artifact Registry repo ---
echo ""
echo "==> [2/5] Creating Artifact Registry repo..."
gcloud artifacts repositories create "${REPO_NAME}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="Salesforce MCP Server images" \
  --project="${PROJECT_ID}" 2>/dev/null || echo "  (repo already exists)"

gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# --- Step 3: Load secrets from .env ---
echo ""
echo "==> [3/4] Loading Salesforce credentials..."
# Read from .env file if it exists, otherwise prompt
if [ -f .env ]; then
  SF_CONSUMER_KEY=$(grep '^SF_CONSUMER_KEY=' .env | cut -d'=' -f2-)
  SF_CONSUMER_SECRET=$(grep '^SF_CONSUMER_SECRET=' .env | cut -d'=' -f2-)
fi

if [ -z "${SF_CONSUMER_KEY:-}" ]; then
  read -rp "  Enter Salesforce Consumer Key: " SF_CONSUMER_KEY
fi
if [ -z "${SF_CONSUMER_SECRET:-}" ]; then
  read -rsp "  Enter Salesforce Consumer Secret: " SF_CONSUMER_SECRET
  echo ""
fi
echo "  Credentials loaded"

# --- Step 4: Build and push image ---
echo ""
echo "==> [4/5] Building image with Cloud Build..."
echo "  (skipping if image already exists from previous build)"
gcloud builds submit \
  --tag "${IMAGE_URI}" \
  --project="${PROJECT_ID}"

# --- Step 5: Deploy to Cloud Run ---
echo ""
echo "==> [5/5] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE_URI}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8080 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --timeout=60 \
  --concurrency=10 \
  --set-env-vars="SF_DOMAIN=${SF_DOMAIN},LOG_LEVEL=INFO,SF_CONSUMER_KEY=${SF_CONSUMER_KEY},SF_CONSUMER_SECRET=${SF_CONSUMER_SECRET}" \
  --cpu-boost

# --- Verify ---
echo ""
echo "============================================================"
echo "DEPLOYMENT COMPLETE"
echo "============================================================"
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --format='value(status.url)')
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "Verifying health..."
curl -sf "${SERVICE_URL}/health" && echo " (healthy)" || echo " (health check failed)"
echo ""
echo "MCP endpoint: ${SERVICE_URL}/mcp"
echo "============================================================"
