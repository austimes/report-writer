# Manual Sandbox Deployment Guide

The Daytona sandbox is running but needs the Python FastAPI application deployed to it.

## Current Sandbox

- **ID**: `522d53be-36b3-4273-835d-188a443cee23`
- **Name**: `report-writer-sandbox`
- **URL**: `https://8000-522d53be-36b3-4273-835d-188a443cee23.proxy.daytona.works`
- **Status**: STARTED (auto-stop disabled)

## Deployment Options

### Option 1: Using Daytona Python SDK (Recommended)

1. Install the SDK with uv:
```bash
uv add daytona-sdk
```

2. Get your Daytona API key:
   - Visit https://daytona.io/dashboard
   - Go to Settings → API Keys
   - Create a new API key

3. Set the environment variable:
```bash
export DAYTONA_API_KEY='your-api-key-here'
```

4. Create a deployment script (or use the one in `scripts/`):
```python
from daytona_sdk import Daytona
from pathlib import Path

# Connect to sandbox
daytona = Daytona()
sandbox = daytona.sandbox.get('522d53be-36b3-4273-835d-188a443cee23')

# Upload files
sandbox.fs.upload_directory('apps/sandbox/src', '/app/src')
sandbox.fs.upload_file('apps/sandbox/pyproject.toml', '/app/pyproject.toml')
sandbox.fs.upload_file('apps/sandbox/requirements.lock', '/app/requirements.lock')

# Install and run
sandbox.process.execute('cd /app && uv sync --frozen')
sandbox.process.start_background('cd /app && uv run uvicorn sandbox.main:app --host 0.0.0.0 --port 8000')
```

### Option 2: Using Dockerfile (Build and Push)

The sandbox includes a Dockerfile. You can build an image and create a new snapshot:

```bash
cd apps/sandbox

# Build image locally
docker build -t report-writer-sandbox:latest .

# Create a Daytona snapshot from the image
daytona snapshot create \
  --name report-writer-app \
  --dockerfile Dockerfile \
  --context .

# Create new sandbox from snapshot
daytona sandbox delete report-writer-sandbox
daytona sandbox create \
  --name report-writer-sandbox \
  --snapshot report-writer-app \
  --env CONVEX_URL=https://agreeable-giraffe-398.convex.cloud \
  --auto-stop 0
```

### Option 3: Manual File Transfer

If SDK is not available, you can package and transfer files manually:

```bash
# 1. Package the app
cd apps/sandbox
tar -czf /tmp/sandbox-app.tar.gz \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  src/ pyproject.toml requirements.lock

# 2. The sandbox should have file upload capabilities
# Check Daytona docs for file upload methods specific to your plan

# 3. Once files are uploaded, SSH/exec into the sandbox:
cd /app
tar -xzf sandbox-app.tar.gz
uv sync --frozen
uv run uvicorn sandbox.main:app --host 0.0.0.0 --port 8000
```

## Verifying Deployment

Once deployed, test the API:

```bash
# Health check
curl https://8000-522d53be-36b3-4273-835d-188a443cee23.proxy.daytona.works/health

# Or with the CLI
daytona sandbox info report-writer-sandbox
```

## Environment Variables Needed

The sandbox app needs these environment variables:

```bash
CONVEX_URL=https://agreeable-giraffe-398.convex.cloud
PORT=8000
PYTHONUNBUFFERED=1
```

Set them when creating the sandbox or in the application startup script.

## Next Steps

After sandbox deployment:

1. Verify the API is responding
2. Update Convex with the correct sandbox URL (already done)
3. Deploy the web frontend
4. Test end-to-end workflow
