# Agent-Enabled Markdown Report Editor

A collaborative web application for drafting Markdown-based reports with real-time collaboration and AI agent assistance.

## Key Features

- **Block-based editing**: Sections and blocks with fine-grained tracking and attribution
- **Real-time collaboration**: Near real-time syncing via Convex with section-level locking
- **AI agent integration**: Persistent agent threads, context-aware suggestions, diff-based review workflow
- **Version history**: Whole-document snapshots with restore capability
- **Comments & mentions**: Unified comment system supporting human and agent assignments with @section references
- **Artifact uploads**: Attach files (CSV, HTML, PDF) for agent context

## Architecture Overview

This is a 3-tier application:

1. **Web App** (apps/web): React SPA with Vite, TypeScript, TailwindCSS
2. **Backend** (convex/): Convex for real-time data sync, business logic, and schema
3. **Agent Sandbox** (apps/sandbox): Python FastAPI service for AI agent orchestration and code execution

```
┌─────────────┐
│  React SPA  │ ──(Convex client)──┐
└─────────────┘                    │
                                   ▼
                            ┌──────────────┐
                            │    Convex    │
                            │   Backend    │
                            └──────┬───────┘
                                   │
                            (HTTP Actions)
                                   │
                                   ▼
                          ┌─────────────────┐
                          │ Python Sandbox  │
                          │    (FastAPI)    │
                          └─────────────────┘
```

## Quick Start

### Prerequisites

- Node.js >= 18.0.0
- pnpm >= 8.0.0
- Python >= 3.11
- Convex CLI (`npm install -g convex`)

### Installation

```bash
# Install dependencies
pnpm install

# Set up Convex
cd convex
npx convex dev
# Follow prompts to create a project

# Set up Python sandbox
cd apps/sandbox
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Development

```bash
# Run all services (from root)
pnpm run dev

# Or run individually:
pnpm --filter web dev          # Web app on http://localhost:5173
pnpm --filter sandbox dev      # Sandbox on http://localhost:8000
npx convex dev                 # Convex in dev mode
```

### Testing

```bash
# Run all tests
pnpm run test:ci

# Individual test suites
pnpm test           # Unit tests
pnpm test:integ     # Integration tests
pnpm test:e2e       # End-to-end tests
```

## Documentation

- [Architecture](docs/architecture.md) - System design and data flow
- [Data Model](docs/data-model.md) - Convex schema and storage rationale
- [Locks & Versions](docs/locks-and-versions.md) - Lock semantics and version snapshots
- [Agent Threads](docs/agent-threads.md) - AI thread lifecycle and integration
- [Testing Guide](docs/testing.md) - How to write and run tests
- [Development Setup](docs/development-setup.md) - Detailed environment setup
- [Contributing](CONTRIBUTING.md) - How to contribute to this project
- [Contributing for Agents](docs/contributing-for-agents.md) - Quick guide for AI coding tools

## Project Structure

```
report-writer/
├── apps/
│   ├── web/              # React frontend
│   └── sandbox/          # Python agent sandbox
├── convex/               # Convex backend
│   ├── schema.ts         # Data schema
│   ├── mutations.ts      # State mutations
│   ├── queries.ts        # Data queries
│   └── actions.ts        # HTTP calls to sandbox
├── packages/
│   └── shared-types/     # Shared TypeScript types
├── tests/
│   ├── integration/      # Cross-service tests
│   └── e2e/              # Playwright tests
└── docs/                 # Documentation
```

## License

MIT - See [LICENSE](LICENSE) file for details.
