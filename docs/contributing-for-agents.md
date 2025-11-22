# Contributing Guide for AI Agents

Quick reference for AI coding assistants (Amp, Cursor, GitHub Copilot, etc.).

## Essential Command

Before submitting any code:

```bash
npm run test:ci
```

This runs linters, unit tests, integration tests, and E2E tests. **All must pass.**

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
├── packages/
│   └── shared-types/     # Shared TypeScript types
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

## Common Tasks

### Add a new feature

1. **Create feature directory:**
   ```bash
   mkdir apps/web/src/features/my-feature
   ```

2. **Add components, hooks, types:**
   ```
   my-feature/
   ├── MyFeature.tsx
   ├── MyFeature.test.tsx
   ├── hooks.ts
   └── types.ts
   ```

3. **Add Convex backend if needed:**
   - Define schema in `convex/schema.ts`
   - Add mutations/queries in `convex/mutations.ts`, `convex/queries.ts`

4. **Write tests:**
   - Unit: Co-located `.test.tsx`
   - Integration: `tests/integration/my-feature.test.ts`
   - E2E: `tests/e2e/my-feature.spec.ts`

5. **Run tests:**
   ```bash
   npm run test:ci
   ```

### Modify Convex schema

1. **Edit `convex/schema.ts`:**
   ```typescript
   myTable: defineTable({
     field1: v.string(),
     field2: v.number(),
   }).index('by_field1', ['field1']),
   ```

2. **Update TypeScript types:**
   - Convex auto-generates types in `convex/_generated/`
   - Import: `import { Doc } from './_generated/dataModel';`

3. **Add migration if needed** (for production data)

4. **Test changes:**
   ```bash
   npm test
   ```

### Add agent capability

1. **Edit `apps/sandbox/app/services/agent.py`:**
   ```python
   class AgentOrchestrator:
       def build_prompt(self, context, user_message):
           # Add new context handling
           pass
   ```

2. **Update API endpoint if needed:**
   `apps/sandbox/app/routes/agent.py`

3. **Add Python tests:**
   ```bash
   cd apps/sandbox
   pytest tests/test_agent.py
   ```

4. **Update Convex action** to pass new context:
   `convex/actions.ts`

### Fix a bug

1. **Write a failing test** that reproduces the bug
2. **Fix the code**
3. **Verify test passes:**
   ```bash
   npm test -- <test-file>
   ```
4. **Run full suite:**
   ```bash
   npm run test:ci
   ```

## Testing Requirements

### Non-Interactive

❌ **Don't** use prompts, user input, or manual confirmation.

✅ **Do** use mocks and fixtures.

### Deterministic

❌ **Don't** rely on random data, real API calls, or system time (unless mocked).

✅ **Do** use seeds, mocks, and `vi.setSystemTime()`.

### Example: Testing Agent Code

**Bad:**
```python
async def test_agent():
    response = await openai.ChatCompletion.create(...)  # Real API call
    assert 'summary' in response
```

**Good:**
```python
async def test_agent():
    fake_llm = FakeLLM(response={'message': 'summary'})
    orchestrator = AgentOrchestrator(llm=fake_llm)
    response = await orchestrator.run('prompt')
    assert response['message'] == 'summary'
```

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

## Pull Request Checklist

- [ ] `npm run test:ci` passes
- [ ] All new code has tests
- [ ] Updated documentation if needed
- [ ] Commit messages follow convention
- [ ] No console.log or debug code left in

## Key Files to Reference

- **PRD**: `docs/AgentMarkdownEditor_PRD_v0_4.md` - Product requirements
- **Architecture**: `docs/architecture.md` - System design
- **Data Model**: `docs/data-model.md` - Convex schema explained
- **Locks & Versions**: `docs/locks-and-versions.md` - Locking mechanism
- **Agent Threads**: `docs/agent-threads.md` - AI integration
- **Testing**: `docs/testing.md` - Full testing guide

## Issue Tracking

Use **bd (beads)** for all tasks:

```bash
# Check for work
bd ready

# Claim task
bd update <issue-id> --status in_progress

# Complete
bd close <issue-id> --reason "Done"
```

See [AGENTS.md](../AGENTS.md) for full workflow.

## Getting Help

1. **Check existing docs**: Start with `docs/`
2. **Search codebase**: Use grep/finder to find examples
3. **Run tests**: See what's already tested for similar features
4. **Ask**: Create an issue or discussion if stuck

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

---

**Remember:** Always run `npm run test:ci` before committing!
