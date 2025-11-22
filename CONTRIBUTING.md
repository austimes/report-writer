# Contributing to Agent-Enabled Markdown Report Editor

Thank you for your interest in contributing! This guide will help you set up your development environment and understand the contribution workflow.

## Development Environment Setup

### Required Tools

- **Node.js**: >= 18.0.0 (LTS recommended)
- **pnpm**: >= 8.0.0 (`npm install -g pnpm`)
- **Python**: >= 3.11
- **Convex CLI**: `npm install -g convex`
- **Git**: Latest version

### Initial Setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/report-writer.git
   cd report-writer
   ```

2. **Install Node dependencies**:
   ```bash
   pnpm install
   ```

3. **Set up Convex**:
   ```bash
   cd convex
   npx convex dev
   # Follow the prompts to create a new project or link to existing
   ```

4. **Set up Python sandbox**:
   ```bash
   cd apps/sandbox
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

5. **Configure environment variables**:
   - See [docs/development-setup.md](docs/development-setup.md) for detailed configuration

## Code Organization

The project uses a monorepo structure:

### `apps/web/`
React frontend application.
- **src/features/**: Feature-based organization
  - `editor/`: Markdown editor components
  - `locks/`: Lock acquisition and display
  - `versions/`: Version history and restoration
  - `threads/`: Agent thread UI
  - `comments/`: Comment system
- **src/lib/**: Shared utilities and hooks
- **src/components/**: Reusable UI components

### `convex/`
Convex backend.
- **schema.ts**: Database schema definitions
- **mutations.ts**: State-changing operations
- **queries.ts**: Read-only data access
- **actions.ts**: External HTTP calls (to sandbox)
- **lib/**: Shared backend utilities

### `apps/sandbox/`
Python FastAPI agent sandbox.
- **app/routes/**: API endpoints
- **app/services/**: Business logic (LLM orchestration)
- **app/models/**: Data models and types

### `packages/shared-types/`
TypeScript types shared across services.

### `tests/`
- **integration/**: Tests spanning multiple services
- **e2e/**: End-to-end Playwright tests

## Testing Requirements

**All pull requests MUST pass the full test suite before merging.**

### Running Tests

```bash
# Full CI suite (required before PR)
pnpm run test:ci

# Individual suites
pnpm test           # Unit tests (Vitest)
pnpm test:integ     # Integration tests
pnpm test:e2e       # End-to-end tests (Playwright)
```

### Writing Tests

- **Unit tests**: Co-located with source files (`*.test.ts`, `*.test.tsx`)
- **Integration tests**: In `tests/integration/`
- **E2E tests**: In `tests/e2e/`

See [docs/testing.md](docs/testing.md) for detailed testing guidelines.

### AI-Agent Testing

For AI-assisted development, ensure:
- Tests are non-interactive and deterministic
- Use `FakeLLM` or mock responses for agent tests
- No actual API calls in CI (use fixtures)

## Commit Conventions

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions or fixes
- `refactor`: Code refactoring
- `chore`: Build, tooling, dependencies

**Examples:**
```
feat(editor): add block-level locking
fix(threads): prevent concurrent agent calls
docs(architecture): update data flow diagram
test(locks): add expiry edge cases
```

## Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make changes and test**:
   ```bash
   # Make your changes
   pnpm run test:ci  # Ensure all tests pass
   ```

3. **Commit with conventional commits**:
   ```bash
   git add .
   git commit -m "feat(feature): description"
   ```

4. **Push and create PR**:
   ```bash
   git push origin feat/my-feature
   # Create PR on GitHub
   ```

5. **PR Requirements**:
   - All tests passing
   - Code follows existing style and conventions
   - New features include tests
   - Documentation updated if needed
   - PR description explains changes and rationale

6. **Review process**:
   - At least one approval required
   - CI must pass
   - No merge conflicts

## Where to Add Features

- **New editor feature**: `apps/web/src/features/editor/`
- **New Convex table/schema**: `convex/schema.ts`
- **New Convex mutation**: `convex/mutations.ts`
- **New agent capability**: `apps/sandbox/app/services/`
- **Shared types**: `packages/shared-types/src/`

## Code Style

- **TypeScript**: Strict mode enabled, no `any` without justification
- **React**: Functional components with hooks
- **CSS**: TailwindCSS utility classes
- **Python**: PEP 8, type hints required
- **Formatting**: Prettier (run `pnpm format`)
- **Linting**: ESLint (run `pnpm lint`)

## Issue Tracking

We use **bd (beads)** for issue tracking:

```bash
# Check for work
bd ready

# Claim a task
bd update <issue-id> --status in_progress

# Complete
bd close <issue-id> --reason "Done"
```

See [AGENTS.md](AGENTS.md) for full bd workflow.

## Getting Help

- Check existing [documentation](docs/)
- Search [existing issues](https://github.com/dlg0/report-writer/issues)
- Ask in discussions or create a new issue

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
