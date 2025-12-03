# Deployment Guide

This guide covers deploying the Report Writer application to production.

## Prerequisites

- ✅ Convex CLI installed and authenticated (`npm install -g convex`)
- ✅ Daytona CLI installed and authenticated
- Node.js >= 18.0.0
- pnpm >= 8.0.0
- Python >= 3.11

## Architecture

The application consists of three deployable components:

1. **Convex Backend** - Real-time database and backend logic
2. **Web Frontend** - React SPA (static site)
3. **Agent Sandbox** - Python FastAPI service (deployed to Daytona)

## Step 1: Deploy Convex Backend

### Initial Setup (First Time Only)

If you haven't configured a Convex deployment yet:

```bash
# Interactive setup - creates project and links deployment
npx convex dev
```

This will:
- Prompt you to create a new Convex project or select an existing one
- Generate `.env.local` with `CONVEX_URL`
- Start the dev server

**Note**: The generated `.env.local` is git-ignored for security.

### Production Deployment

Once configured, deploy to production:

```bash
# Deploy backend functions to production
npx convex deploy

# Or deploy with environment variables
npx convex deploy --cmd 'echo "Deploying"'
```

### Environment Variables

Set production environment variables:

```bash
# List current variables
npx convex env list

# Set a variable
npx convex env set VARIABLE_NAME value

# Set from file
npx convex env set VARIABLE_NAME < value.txt
```

### Verify Deployment

```bash
# Open dashboard
npx convex dashboard

# Check deployment status
npx convex data

# Test a function
npx convex run <functionName>
```

## Step 2: Deploy Agent Sandbox to Daytona

The agent sandbox runs as a FastAPI service in a Daytona sandbox environment.

### Option A: Using Daytona CLI

```bash
# Create a snapshot with the sandbox code
cd apps/sandbox

# Create a sandbox with the snapshot
daytona sandbox create \
  --name report-writer-sandbox \
  --snapshot daytona-medium \
  --env CONVEX_URL="<your-convex-url>" \
  --auto-stop 0 \
  --class medium

# Get the sandbox URL
daytona sandbox info report-writer-sandbox
```

### Option B: Using Daytona SDK (Programmatic)

Create a deployment script `scripts/deploy-sandbox.ts`:

```typescript
import { Daytona } from '@daytona/sdk';

const daytona = new Daytona({
  apiKey: process.env.DAYTONA_API_KEY
});

const sandbox = await daytona.create({
  snapshot: 'daytona-medium',
  env: {
    CONVEX_URL: process.env.CONVEX_URL
  },
  resources: {
    class: 'medium'
  }
});

console.log(`Sandbox created: ${sandbox.id}`);
console.log(`URL: ${await sandbox.getUrl(8000)}`);
```

### Configure Sandbox Environment

The sandbox needs these environment variables:

```bash
CONVEX_URL=https://<your-project>.convex.cloud
PORT=8000
PYTHONUNBUFFERED=1
```

### Deploy Sandbox Code

```bash
# Install dependencies (requires uv)
uv sync

# Start the FastAPI server
uv run uvicorn sandbox.main:app --host 0.0.0.0 --port 8000
```

### Keep Sandbox Running

For production, disable auto-stop:

```bash
daytona sandbox create \
  --name report-writer-sandbox \
  --snapshot daytona-medium \
  --auto-stop 0 \
  --auto-archive 0
```

## Step 3: Deploy Web Frontend

The web frontend is a static React SPA that can be deployed to any static hosting service.

### Build the Frontend

```bash
cd apps/web
pnpm build
```

### Deployment Options

#### Option 1: Vercel (Recommended)

Vercel integrates with Convex to automatically deploy both backend and frontend.

**Step 1: Get Convex Production Deploy Key**

1. Run `npx convex dashboard` (or visit https://dashboard.convex.dev)
2. Select your project
3. Go to **Settings** → **Deploy Keys**
4. Click **Generate Production Deploy Key**
5. Copy the generated key

**Step 2: Set Environment Variables in Vercel**

```bash
cd apps/web

# Set the Convex deploy key (required)
vercel env add CONVEX_DEPLOY_KEY production

# Set sandbox URL if needed
vercel env add VITE_SANDBOX_URL production
```

Or set via Vercel Dashboard: Project → Settings → Environment Variables

**Step 3: Deploy**

```bash
cd apps/web
vercel --prod
```

**How It Works**

The `vercel.json` configuration handles the integration:

```json
{
  "buildCommand": "npx convex deploy --cmd 'npm run build'",
  "framework": "vite",
  "outputDirectory": "dist"
}
```

During deployment:
1. `npx convex deploy` reads `CONVEX_DEPLOY_KEY`
2. Deploys Convex functions to production
3. Sets `VITE_CONVEX_URL` automatically
4. Runs `npm run build` with the correct Convex URL
5. Vercel serves the built static files

#### Option 2: Netlify

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
cd apps/web
netlify deploy --prod --dir=dist
```

#### Option 3: Convex Hosting (Static Sites)

Convex can host static sites directly:

```bash
# Add to convex.json
{
  "functions": "convex/",
  "hosting": {
    "dir": "apps/web/dist"
  }
}

# Deploy
npx convex deploy
```

### Configure Environment Variables

Set these in your hosting platform:

```bash
VITE_CONVEX_URL=https://<your-project>.convex.cloud
VITE_SANDBOX_URL=https://8000-<your-sandbox-id>.proxy.daytona.works
```

## Step 4: Connect the Services

Update Convex actions to use the production Daytona sandbox URL:

```typescript
// convex/actions.ts
const SANDBOX_URL = process.env.SANDBOX_URL || 'http://localhost:8000';
```

Set the environment variable in Convex:

```bash
npx convex env set SANDBOX_URL https://8000-<your-sandbox-id>.proxy.daytona.works
```

## Deployment Checklist

- [ ] Convex backend deployed (`npx convex deploy`)
- [ ] Convex environment variables set
- [ ] Daytona sandbox created and running
- [ ] Sandbox environment variables configured
- [ ] Sandbox URL added to Convex env
- [ ] Web frontend built
- [ ] Web frontend deployed to hosting
- [ ] Web environment variables set (VITE_CONVEX_URL, VITE_SANDBOX_URL)
- [ ] All services can communicate
- [ ] Test end-to-end workflow

## Monitoring & Management

### Convex Dashboard

Monitor backend activity:

```bash
npx convex dashboard
```

View real-time logs:

```bash
npx convex logs
```

### Daytona Sandbox Management

List running sandboxes:

```bash
daytona sandbox list
```

View sandbox info:

```bash
daytona sandbox info report-writer-sandbox
```

Stop/start sandbox:

```bash
daytona sandbox stop report-writer-sandbox
daytona sandbox start report-writer-sandbox
```

### Cost Optimization

For development/staging environments:

```bash
# Auto-stop after 15 minutes of inactivity
daytona sandbox create --auto-stop 15

# Auto-delete after 7 days
daytona sandbox create --auto-delete 10080
```

## Rollback Procedure

### Rollback Convex

Convex maintains deployment history. To rollback:

1. Open Convex dashboard
2. Go to Deployments tab
3. Select previous deployment
4. Click "Restore"

### Rollback Sandbox

```bash
# Create new sandbox from previous snapshot
daytona sandbox create --snapshot <previous-snapshot-id>

# Update Convex with new sandbox URL
npx convex env set SANDBOX_URL <new-sandbox-url>
```

### Rollback Frontend

Depends on hosting provider (Vercel/Netlify have built-in rollback).

## Troubleshooting

### Convex Connection Issues

```bash
# Verify deployment
npx convex data

# Check logs
npx convex logs --tail

# Test connection
npx convex run queries:ping
```

### Sandbox Connection Issues

```bash
# Check sandbox status
daytona sandbox info <sandbox-id>

# View sandbox logs (if available via SDK)
# Or SSH into sandbox:
daytona sandbox info <sandbox-id>  # Get SSH command
```

### CORS Issues

Ensure Convex HTTP actions allow requests from your frontend domain.

## Security Considerations

1. **API Keys**: Never commit API keys. Use environment variables.
2. **Convex Auth**: Configure Convex authentication for production.
3. **Sandbox Network**: Use Daytona network allow-lists for security.
4. **HTTPS**: Always use HTTPS in production.

## Automated Deployment

### GitHub Actions Example

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: 18
      
      - name: Deploy Convex
        run: |
          npm install -g convex
          npx convex deploy
        env:
          CONVEX_DEPLOY_KEY: ${{ secrets.CONVEX_DEPLOY_KEY }}
      
      - name: Deploy Frontend
        run: |
          cd apps/web
          pnpm install
          pnpm build
          npx vercel --prod
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
```

## Support

For deployment issues:
- Convex: https://docs.convex.dev
- Daytona: https://daytona.io/docs
- GitHub Issues: [Report an issue](https://github.com/<your-org>/<your-repo>/issues)
