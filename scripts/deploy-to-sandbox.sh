#!/bin/bash
set -e

echo "📦 Deploying Python app to Daytona sandbox..."

SANDBOX_NAME="${SANDBOX_NAME:-report-writer-sandbox}"

# Get sandbox ID
SANDBOX_ID=$(daytona sandbox list | grep "$SANDBOX_NAME" | awk '{print $1}')

if [ -z "$SANDBOX_ID" ]; then
  echo "❌ Sandbox '$SANDBOX_NAME' not found"
  echo "Available sandboxes:"
  daytona sandbox list
  exit 1
fi

echo "Found sandbox: $SANDBOX_ID"

# Create temporary deployment package
echo "Creating deployment package..."
cd apps/sandbox
tar -czf /tmp/sandbox-deploy.tar.gz \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='*.pyc' \
  src/ pyproject.toml requirements.lock

echo "Package created: /tmp/sandbox-deploy.tar.gz"

# Upload to sandbox (using Daytona SDK would be ideal here)
# For now, we'll use the CLI if available, or provide instructions

echo ""
echo "⚠️  Manual deployment required:"
echo ""
echo "1. Upload the package to the sandbox:"
echo "   daytona sandbox upload $SANDBOX_NAME /tmp/sandbox-deploy.tar.gz /app/"
echo ""
echo "2. SSH into the sandbox and run:"
echo "   cd /app"
echo "   tar -xzf sandbox-deploy.tar.gz"
echo "   uv sync --frozen"
echo "   uv run uvicorn sandbox.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Or use the Python SDK to deploy programmatically."
echo ""
echo "Sandbox URL: https://22222-$SANDBOX_ID.proxy.daytona.works"

# Cleanup
rm /tmp/sandbox-deploy.tar.gz
echo "✅ Deployment package prepared"
