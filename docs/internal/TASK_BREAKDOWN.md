# Agent-Enabled Markdown Report Editor - Task Breakdown

This document provides an overview of all project tasks tracked in bd (beads). Use `bd ready` to see which tasks are ready to work on.

## Quick Commands

```bash
# View all tasks
bd list

# View ready tasks (no blockers)
bd ready

# View a specific task
bd show <task-id>

# Claim a task
bd update <task-id> --status in_progress

# Complete a task
bd close <task-id> --reason "Completed"

# Run tests
npm run test:ci
```

## Architecture Overview

The project uses a **Python FastAPI sandbox** (modified from oracle's Node.js recommendation) with this structure:

```
apps/
  web/        - React + Vite + Convex client
  sandbox/    - Python FastAPI service (LLM orchestration)
convex/       - Convex backend (serverless functions + realtime DB)
packages/     - Shared TypeScript types
tests/        - Integration and E2E tests
docs/         - Documentation
```

## Task Categories

### 🏗️ Foundation (Priority: Critical)

**report-writer-jkb**: Create project directory structure
- Monorepo setup with pnpm workspaces
- All directory scaffolding
- Tooling configuration

**report-writer-sj9**: Setup testing infrastructure and harness (Priority 0 - CRITICAL)
- Vitest, Playwright, testing utilities
- FakeLLM for deterministic testing
- **Essential for AI-agent development**

**report-writer-v6n**: Create documentation files
- README, CONTRIBUTING, LICENSE
- Architecture, data model, testing guides
- AI-agent-friendly documentation

### ⚙️ Backend - Convex (Priority: High)

**report-writer-osw**: Setup Convex schema and base configuration
- All database tables defined
- Auth setup
- Indexes configured

**report-writer-14z**: Implement Convex table helpers
- CRUD operations for users, projects, sections, blocks
- Proper error handling

**report-writer-oj4**: Implement Convex locking system
- Generic lock acquisition/release
- Auto-expiry logic
- Resource-agnostic (sections, blocks, threads)

**report-writer-yds**: Implement Convex version snapshots system
- Create/restore snapshots
- Version comparison
- Block-level diffs

**report-writer-54n**: Implement Convex agent threads system
- Thread creation and forking
- Integration with locking
- Sandbox API calls via Convex actions

**report-writer-2jj**: Write Convex unit and integration tests
- Editing, locking, versions, agent tests
- Lock edge cases
- Snapshot integrity

### 🐍 Backend - Python Sandbox (Priority: High)

**report-writer-o3f**: Setup Python agent sandbox service
- FastAPI app structure
- Health endpoint
- POST /v1/agent/run stub
- Dockerfile

**report-writer-scf**: Implement sandbox LLM client and prompt builder
- OpenAI and Anthropic clients
- Prompt formatting
- **FakeLLM for testing** (critical!)

**report-writer-d7t**: Implement sandbox diff engine
- Word-level diff algorithm
- Markdown-aware
- Block-level edit proposals

**report-writer-on0**: Write sandbox unit and integration tests
- LLM client, prompt builder, diff engine tests
- API contract tests
- All using FakeLLM

### 🎨 Frontend - React (Priority: High)

**report-writer-sdf**: Setup React web app structure
- Vite + React + TypeScript
- Convex client setup
- Tailwind CSS
- Feature-based directory structure

**report-writer-b92**: Implement authentication and project management UI
- Login/signup
- Project CRUD
- Collaborator invitations

**report-writer-7cu**: Implement markdown editor with block-based editing
- Block parsing and serialization
- Live preview
- Debounced auto-save
- Block metadata tracking

**report-writer-l4o**: Implement lock UI and indicators
- Visual lock indicators
- Auto-refresh logic
- Graceful expiry handling

**report-writer-2eg**: Implement version history UI
- Version list and comparison
- Diff visualization
- Restore with confirmation

**report-writer-ya5**: Implement agent threads UI
- Chat interface
- Proposed edit review
- Fork and lock handling

**report-writer-b5z**: Implement comments system UI
- Comment anchoring
- Agent assignment (creates thread)
- Resolution workflow

### 🧪 Testing (Priority: High)

**report-writer-ka7**: Write Playwright E2E tests
- Auth, editing, locks, agent threads, versions
- Page object models
- Multi-user scenarios

### 🚀 DevOps (Priority: High)

**report-writer-xf7**: Setup GitHub Actions CI/CD pipeline
- Lint, unit, integration, E2E jobs
- PR and issue templates
- Automated testing on every PR

## Task Dependencies (Logical Order)

1. **Start Here**:
   - report-writer-jkb (directory structure)
   - report-writer-sj9 (testing infrastructure) ⚠️ CRITICAL
   - report-writer-v6n (documentation)

2. **Convex Backend**:
   - report-writer-osw (schema) → then all other Convex tasks can proceed in parallel
   - report-writer-14z, report-writer-oj4, report-writer-yds can be done concurrently
   - report-writer-54n depends on locking (report-writer-oj4)

3. **Python Sandbox**:
   - report-writer-o3f (setup) → then other sandbox tasks
   - report-writer-scf, report-writer-d7t can be concurrent

4. **Frontend**:
   - report-writer-sdf (setup) → then all UI tasks
   - Most UI tasks can proceed in parallel once setup is done

5. **Testing** (Continuous):
   - report-writer-2jj, report-writer-on0, report-writer-ka7 alongside implementation

6. **Final**:
   - report-writer-xf7 (CI/CD) once tests exist

## Key Testing Requirements (AI-Agent Development)

**Critical**: All tests must be:
- ✅ Non-interactive (no human input required)
- ✅ Deterministic (FakeLLM with predictable responses)
- ✅ Fast (using test doubles, no real LLM calls)
- ✅ Clear pass/fail (proper exit codes)
- ✅ Runnable via `npm run test:ci`

## Working on a Task

1. Check dependencies: `bd show <task-id>`
2. Claim task: `bd update <task-id> --status in_progress`
3. Implement following the detailed description
4. Run tests: `npm run test:ci`
5. Commit code AND `.beads/issues.jsonl` together
6. Complete: `bd close <task-id> --reason "Completed"`

## Questions?

- See oracle's detailed design in this thread
- Check PRD at docs/AgentMarkdownEditor_PRD_v0_4.md
- Documentation will be in docs/ as tasks complete
