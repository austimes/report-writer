# Contributing Guide for AI Agents

Quick reference for AI coding assistants (Amp, Cursor, GitHub Copilot, etc.).

> **Canonical Source**: [AGENTS.md](../AGENTS.md) at the repository root is the authoritative source for AI agent configuration. This document provides expanded, human-readable guidance.

---

## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- **Dependency-aware**: Track blockers and relationships between issues
- **Git-friendly**: Auto-syncs to `.beads/issues.jsonl` for version control
- **Agent-optimized**: JSON output, ready work detection, discovered-from links
- **Prevents duplicate tracking**: No confusion between different systems

### Essential Commands

```bash
# Check for ready work (unblocked issues)
bd ready --json

# Create new issues
bd create "Issue title" -t bug|feature|task -p 0-4 --json
bd create "Issue title" -p 1 --deps discovered-from:bd-123 --json

# Claim and update
bd update bd-42 --status in_progress --json
bd update bd-42 --priority 1 --json

# Complete work
bd close bd-42 --reason "Completed" --json
```

### Issue Types

| Type | Use For |
|------|---------|
| `bug` | Something broken |
| `feature` | New functionality |
| `task` | Work items (tests, docs, refactoring) |
| `epic` | Large features with subtasks |
| `chore` | Maintenance (dependencies, tooling) |

### Priorities

| Priority | Level | Examples |
|----------|-------|----------|
| `0` | Critical | Security, data loss, broken builds |
| `1` | High | Major features, important bugs |
| `2` | Medium | Default, nice-to-have |
| `3` | Low | Polish, optimization |
| `4` | Backlog | Future ideas |

### AI Agent Workflow

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   ```bash
   bd create "Found bug" -p 1 --deps discovered-from:<parent-id>
   ```
5. **Complete**: `bd close <id> --reason "Done"`
6. **Commit together**: Always commit `.beads/issues.jsonl` with your code changes

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ✅ Store AI planning docs in `history/` directory
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems
- ❌ Do NOT clutter repo root with planning documents

---

## LLM-Specific Documentation

This project includes specialized documentation for LLMs in [`docs/llm/`](llm/).

### Available References

| File | Description | Use When |
|------|-------------|----------|
| [`convex-llms.txt`](llm/convex-llms.txt) | Compact Convex reference with URLs | Quick lookups, conserve tokens |
| [`daytona-llms.txt`](llm/daytona-llms.txt) | Compact Daytona reference with URLs | Quick lookups, conserve tokens |
| [`daytona-cli-llms.txt`](llm/daytona-cli-llms.txt) | Daytona CLI reference | CLI command help |

### Usage Guidelines

**Prefer compact versions when:**
- You have web access and can follow documentation links
- You need to conserve context window tokens
- You're doing exploratory work

**Full documentation files** (if available in project or via web):
- Use when you need comprehensive offline reference
- For complex features requiring detailed examples
- When web access is unavailable

---

## Development Commands

### Essential Command

Before submitting any code:

```bash
npm run test:ci
```

This runs linters, unit tests, integration tests, and E2E tests. **All must pass.**

### Type Checking & Linting

**IMPORTANT**: Always run type checking after making code changes.

```bash
# Frontend (apps/web)
cd apps/web && npm run build:typecheck  # TypeScript + build
cd apps/web && npx tsc --noEmit         # TypeScript only
cd apps/web && npm run lint             # ESLint

# Backend (Convex)
npx convex dev --once                   # Compile and validate Convex functions
```

### Testing

```bash
npm test                                # Run all Vitest tests
npm run test:e2e                        # Run Playwright E2E tests
npm run test:ci                         # Full CI suite (use before PR)
```

### Pre-commit Checklist

1. ✅ Run `cd apps/web && npm run build:typecheck`
2. ✅ Run `npx convex dev --once`
3. ✅ Run relevant tests with `npm test`
4. ✅ Verify the app works in the browser

---

## Deployment Commands

### Quick Deploy

```bash
# Deploy Convex backend
npx convex deploy

# Deploy to Daytona sandbox
daytona sandbox create --name report-writer-sandbox --snapshot daytona-medium --auto-stop 0

# Build and deploy frontend (Vercel)
cd apps/web && pnpm build && vercel --prod
```

### Convex Commands

```bash
npx convex dev              # Start dev mode (auto-deploys on changes)
npx convex deploy           # Deploy to production
npx convex env set KEY val  # Set environment variable
npx convex env list         # List environment variables
npx convex dashboard        # Open web dashboard
npx convex logs             # Stream logs
npx convex data             # View database tables
npx convex run <function>   # Execute a function
```

### Daytona Commands

```bash
daytona sandbox create --name <name> --snapshot daytona-medium  # Create sandbox
daytona sandbox list                                             # List sandboxes
daytona sandbox info <name>                                      # Get sandbox details
daytona sandbox stop <name>                                      # Stop sandbox
daytona sandbox start <name>                                     # Start sandbox
daytona sandbox delete <name>                                    # Delete sandbox
```

---

## Project Structure

```
report-writer/
├── apps/
│   ├── web/              # React frontend
│   │   └── src/
│   │       ├── features/  # Feature-based organization
│   │       ├── lib/       # Utilities
│   │       └── components/ # UI components
│   └── sandbox/          # Python agent service
│       └── app/
│           ├── routes/    # API endpoints
│           └── services/  # LLM orchestration
├── convex/               # Backend (queries, mutations, schema)
├── docs/
│   └── llm/              # LLM-specific documentation
├── packages/
│   └── shared-types/     # Shared TypeScript types
├── history/              # AI planning documents (ephemeral)
└── tests/
    ├── integration/      # Cross-service tests
    └── e2e/              # Playwright tests
```

## Where to Add Code

| Feature | Location |
|---------|----------|
| New React component | `apps/web/src/features/<feature>/` |
| Convex table/schema | `convex/schema.ts` |
| Convex query | `convex/queries.ts` |
| Convex mutation | `convex/mutations.ts` |
| Convex action (HTTP) | `convex/actions.ts` |
| Agent logic | `apps/sandbox/app/services/` |
| Shared types | `packages/shared-types/src/` |
| Unit test | Co-located: `<file>.test.ts` |
| Integration test | `tests/integration/` |
| E2E test | `tests/e2e/` |

---

## Managing AI-Generated Documents

AI assistants often create planning and design documents during development:
- PLAN.md, IMPLEMENTATION.md, ARCHITECTURE.md
- DESIGN.md, CODEBASE_SUMMARY.md, INTEGRATION_PLAN.md

**Best Practice**: Store ALL AI-generated planning/design docs in `history/`

**Benefits:**
- ✅ Clean repository root
- ✅ Clear separation between ephemeral and permanent documentation
- ✅ Preserves planning history for later reference
- ✅ Reduces noise when browsing the project

---

## Code Style

- **TypeScript**: Strict mode, no `any` without justification
- **React**: Functional components with hooks
- **Formatting**: Run `pnpm format` (Prettier)
- **Linting**: Run `pnpm lint` (ESLint)
- **Python**: PEP 8, type hints required

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(editor): add block-level locking
fix(threads): prevent concurrent agent calls
docs(readme): update installation steps
test(locks): add expiry edge cases
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `pnpm install` | Install dependencies |
| `pnpm --filter web dev` | Run web app |
| `pnpm --filter sandbox dev` | Run Python sandbox |
| `npx convex dev` | Run Convex backend |
| `npm test` | Run unit tests |
| `npm run test:ci` | **Run before PR** |
| `pnpm format` | Format code |
| `pnpm lint` | Lint code |
| `bd ready` | Check for tasks |
| `bd update <id> --status in_progress` | Claim task |
| `bd close <id> --reason "Done"` | Complete task |

---

## Key Documentation

- **PRD**: `docs/AgentMarkdownEditor_PRD_v0_4.md` - Product requirements
- **Architecture**: `docs/architecture.md` - System design
- **Data Model**: `docs/data-model.md` - Convex schema explained
- **Testing**: `docs/testing.md` - Full testing guide
- **AGENTS.md**: [`../AGENTS.md`](../AGENTS.md) - Canonical AI agent configuration

---

**Remember:** 
- Always run `npm run test:ci` before committing!
- Always commit `.beads/issues.jsonl` with your code changes!
