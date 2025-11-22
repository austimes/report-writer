# Testing Guide

This document explains the testing strategy, test layers, and how to write and run tests.

## Test Layers

The project uses a **multi-layer testing approach**:

1. **Unit Tests**: Test individual functions and components in isolation
2. **Convex Tests**: Test Convex queries, mutations, and actions
3. **Integration Tests**: Test cross-service interactions (web + Convex + sandbox)
4. **End-to-End Tests**: Test full user workflows in a real browser

## Test Commands

### Run All Tests (CI)

```bash
npm run test:ci
```

This runs:
1. Linters (ESLint, Prettier)
2. Unit tests (Vitest)
3. Integration tests
4. End-to-end tests (Playwright)

**Required before every PR.**

### Individual Test Suites

```bash
# Unit tests only
npm test

# Integration tests
npm run test:integ

# End-to-end tests
npm run test:e2e

# Watch mode (for development)
npm test -- --watch
```

## Unit Tests

### Location

- **React components**: Co-located with source files
  - `apps/web/src/features/editor/BlockEditor.test.tsx`
- **Utilities**: Co-located with source files
  - `apps/web/src/lib/markdown.test.ts`
- **Python**: In `apps/sandbox/tests/`
  - `apps/sandbox/tests/test_agent.py`

### Framework

- **Frontend (TypeScript/React)**: Vitest + React Testing Library
- **Backend (Python)**: pytest

### Example: React Component Test

```tsx
// apps/web/src/features/editor/BlockEditor.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BlockEditor } from './BlockEditor';

describe('BlockEditor', () => {
  it('renders block content', () => {
    const block = {
      _id: 'b1',
      blockType: 'paragraph',
      markdownText: 'Hello world'
    };
    
    render(<BlockEditor block={block} onUpdate={vi.fn()} />);
    
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });
  
  it('calls onUpdate when text changes', async () => {
    const onUpdate = vi.fn();
    const block = { _id: 'b1', blockType: 'paragraph', markdownText: '' };
    
    render(<BlockEditor block={block} onUpdate={onUpdate} />);
    
    const input = screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'New text' } });
    
    // Wait for debounce
    await new Promise(r => setTimeout(r, 600));
    
    expect(onUpdate).toHaveBeenCalledWith('b1', 'New text');
  });
});
```

### Example: Utility Function Test

```typescript
// apps/web/src/lib/markdown.test.ts
import { describe, it, expect } from 'vitest';
import { parseMarkdownToBlocks } from './markdown';

describe('parseMarkdownToBlocks', () => {
  it('splits paragraphs into blocks', () => {
    const markdown = 'Para 1\n\nPara 2';
    const blocks = parseMarkdownToBlocks(markdown);
    
    expect(blocks).toHaveLength(2);
    expect(blocks[0].blockType).toBe('paragraph');
    expect(blocks[0].markdownText).toBe('Para 1');
    expect(blocks[1].markdownText).toBe('Para 2');
  });
  
  it('identifies headings', () => {
    const markdown = '# Title\n\nContent';
    const blocks = parseMarkdownToBlocks(markdown);
    
    expect(blocks[0].blockType).toBe('heading');
    expect(blocks[0].headingLevel).toBe(1);
  });
});
```

### Example: Python Test

```python
# apps/sandbox/tests/test_agent.py
import pytest
from app.services.agent import AgentOrchestrator

def test_build_prompt_with_context():
    orchestrator = AgentOrchestrator()
    
    context = {
        'messages': [
            {'senderType': 'user', 'content': 'Hello'}
        ],
        'anchoredContent': {
            'type': 'section',
            'heading': 'Intro',
            'content': 'Some text'
        }
    }
    
    prompt = orchestrator.build_prompt(context, 'Rewrite this')
    
    assert 'Hello' in prompt
    assert 'Intro' in prompt
    assert 'Rewrite this' in prompt

@pytest.mark.asyncio
async def test_call_llm_with_fake():
    orchestrator = AgentOrchestrator(llm=FakeLLM())
    
    response = await orchestrator.call_llm('Test prompt')
    
    assert response.message == 'Fake response'
    assert len(response.edits) == 0
```

## Convex Tests

### Location

- In `convex/` directory, co-located with source
- `convex/mutations.test.ts`
- `convex/locks.test.ts`

### Framework

Convex provides test utilities for running queries/mutations in a test database.

### Example: Mutation Test

```typescript
// convex/locks.test.ts
import { describe, it, expect } from 'vitest';
import { convexTest } from 'convex-test';
import { api } from './_generated/api';

describe('Lock acquisition', () => {
  it('grants lock when none exists', async () => {
    const t = convexTest(schema);
    
    const projectId = await t.run(async (ctx) => {
      return await ctx.db.insert('projects', { name: 'Test', ownerId: 'u1' });
    });
    
    const sectionId = await t.run(async (ctx) => {
      return await ctx.db.insert('sections', {
        projectId,
        headingText: 'Intro',
        headingLevel: 1,
        order: 0
      });
    });
    
    // Acquire lock
    const result = await t.mutation(api.locks.acquireLock, {
      resourceType: 'section',
      resourceId: sectionId,
      userId: 'user1'
    });
    
    expect(result.success).toBe(true);
    
    // Verify lock created
    const lock = await t.query(api.locks.getLock, {
      resourceType: 'section',
      resourceId: sectionId
    });
    
    expect(lock.userId).toBe('user1');
  });
  
  it('rejects when locked by another user', async () => {
    const t = convexTest(schema);
    
    // Setup: create lock held by user1
    const sectionId = 'section123';
    await t.run(async (ctx) => {
      await ctx.db.insert('locks', {
        projectId: 'proj1',
        resourceType: 'section',
        resourceId: sectionId,
        userId: 'user1',
        lockedAt: Date.now()
      });
    });
    
    // Try to acquire as user2
    const result = await t.mutation(api.locks.acquireLock, {
      resourceType: 'section',
      resourceId: sectionId,
      userId: 'user2'
    });
    
    expect(result.success).toBe(false);
    expect(result.error).toContain('Locked by user1');
  });
});
```

## Integration Tests

### Location

- `tests/integration/`

### Scope

Test interactions between services:
- Web app → Convex mutations
- Convex actions → Sandbox API
- Full data flow (user action → agent response)

### Framework

- Vitest for test runner
- Real Convex dev deployment
- Mock or real sandbox (configurable)

### Example: Agent Flow Integration Test

```typescript
// tests/integration/agent-flow.test.ts
import { describe, it, expect, beforeAll } from 'vitest';
import { ConvexTestClient } from './utils/convex-client';
import { MockSandbox } from './utils/mock-sandbox';

describe('Agent thread flow', () => {
  let client: ConvexTestClient;
  let sandbox: MockSandbox;
  
  beforeAll(async () => {
    client = new ConvexTestClient();
    await client.connect();
    
    sandbox = new MockSandbox();
    await sandbox.start();
  });
  
  it('creates thread, sends message, receives agent response', async () => {
    // 1. Create project and section
    const projectId = await client.mutation('createProject', {
      name: 'Test Project'
    });
    
    const sectionId = await client.mutation('createSection', {
      projectId,
      headingText: 'Introduction'
    });
    
    // 2. Create agent thread
    const threadId = await client.mutation('createAgentThread', {
      projectId,
      title: 'Review intro',
      anchorSectionId: sectionId
    });
    
    // 3. Send message
    sandbox.mockResponse({
      message: 'The introduction looks good!',
      proposedEdits: []
    });
    
    const result = await client.mutation('runAgentOnThread', {
      threadId,
      userMessage: 'Can you review the introduction?'
    });
    
    // 4. Verify agent response stored
    expect(result.message).toBe('The introduction looks good!');
    
    const messages = await client.query('getThreadMessages', { threadId });
    expect(messages).toHaveLength(2); // User + agent
    expect(messages[1].senderType).toBe('agent');
  });
  
  it('enforces thread locks', async () => {
    const threadId = 'thread123';
    
    // User1 sends message (acquires lock)
    await client.mutation('runAgentOnThread', {
      threadId,
      userMessage: 'Hello',
      userId: 'user1'
    });
    
    // User2 tries to send message
    await expect(
      client.mutation('runAgentOnThread', {
        threadId,
        userMessage: 'Also hello',
        userId: 'user2'
      })
    ).rejects.toThrow('Thread locked by user1');
  });
});
```

## End-to-End Tests

### Location

- `tests/e2e/`

### Framework

- **Playwright**: Browser automation

### Scope

Full user workflows in a real browser:
- Login → Create project → Edit document → Save version
- Create thread → Send message → Review agent proposal → Accept

### Example: E2E Test

```typescript
// tests/e2e/editing.spec.ts
import { test, expect } from '@playwright/test';

test('user can edit and lock section', async ({ page }) => {
  // Login
  await page.goto('http://localhost:5173');
  await page.fill('[name=email]', 'test@example.com');
  await page.fill('[name=password]', 'password');
  await page.click('button:has-text("Login")');
  
  // Create project
  await page.click('button:has-text("New Project")');
  await page.fill('[name=projectName]', 'E2E Test Project');
  await page.click('button:has-text("Create")');
  
  // Navigate to editor
  await expect(page.locator('h1')).toContainText('E2E Test Project');
  
  // Lock section
  await page.click('button:has-text("Lock Section")');
  await expect(page.locator('.lock-indicator')).toContainText('Locked by You');
  
  // Edit block
  const editor = page.locator('[data-testid=block-editor]').first();
  await editor.fill('Updated content');
  
  // Wait for save (debounce)
  await page.waitForTimeout(600);
  
  // Verify saved (reload page)
  await page.reload();
  await expect(editor).toHaveValue('Updated content');
});

test('agent thread workflow', async ({ page }) => {
  await page.goto('http://localhost:5173/project/abc123');
  
  // Create thread
  await page.click('button:has-text("New Thread")');
  await page.fill('[name=threadTitle]', 'Review intro');
  await page.click('button:has-text("Create Thread")');
  
  // Send message
  await page.fill('[data-testid=message-input]', 'Can you review?');
  await page.click('button:has-text("Send")');
  
  // Wait for agent response
  await expect(page.locator('.agent-message')).toBeVisible({ timeout: 10000 });
  
  // Verify response displayed
  const agentMessage = page.locator('.agent-message').last();
  await expect(agentMessage).toContainText('looks good');
});
```

## AI-Agent Testing Requirements

When using AI coding assistants (like Amp, Cursor, Copilot), ensure:

### 1. Non-Interactive Tests

**❌ Bad:**
```typescript
it('prompts user for confirmation', async () => {
  const answer = await prompt('Are you sure?'); // Waits for user input
  expect(answer).toBe('yes');
});
```

**✅ Good:**
```typescript
it('calls confirmation callback', async () => {
  const onConfirm = vi.fn();
  render(<DeleteButton onConfirm={onConfirm} />);
  
  fireEvent.click(screen.getByText('Delete'));
  expect(onConfirm).toHaveBeenCalled();
});
```

### 2. Deterministic Tests

**❌ Bad:**
```typescript
it('generates random ID', () => {
  const id = generateId(); // Non-deterministic
  expect(id).toHaveLength(10); // Might pass or fail
});
```

**✅ Good:**
```typescript
it('generates UUID format', () => {
  const id = generateId();
  expect(id).toMatch(/^[a-f0-9-]{36}$/); // Deterministic pattern
});

// Or use mocking:
it('generates ID with seed', () => {
  vi.spyOn(Math, 'random').mockReturnValue(0.5);
  const id = generateId();
  expect(id).toBe('expected-id-from-0.5-seed');
});
```

### 3. No Real API Calls in CI

**❌ Bad:**
```python
async def test_agent_call():
    response = await openai.ChatCompletion.create(...)  # Real API call
    assert response.message == 'Expected'
```

**✅ Good:**
```python
async def test_agent_call():
    fake_llm = FakeLLM(response='Expected message')
    orchestrator = AgentOrchestrator(llm=fake_llm)
    
    response = await orchestrator.call_llm('prompt')
    assert response.message == 'Expected message'
```

### 4. Use Fixtures and Factories

```typescript
// tests/fixtures/project.ts
export const createTestProject = (overrides = {}) => ({
  _id: 'proj_test_123',
  name: 'Test Project',
  ownerId: 'user_test_1',
  createdAt: 1234567890,
  archived: false,
  ...overrides
});

// Usage:
it('archives project', async () => {
  const project = createTestProject();
  const result = await archiveProject(project._id);
  expect(result.archived).toBe(true);
});
```

## Writing New Tests

### Checklist

- [ ] Test file co-located with source (unit) or in tests/ (integration/e2e)
- [ ] Test name describes behavior: "it('grants lock when none exists')"
- [ ] Tests are isolated (no shared state between tests)
- [ ] Tests are fast (< 1s for unit, < 10s for integration, < 30s for e2e)
- [ ] Tests are deterministic (same input → same output)
- [ ] Mock external dependencies (LLM APIs, file system, time)
- [ ] Clean up resources (test databases, temp files)

### Best Practices

1. **Arrange-Act-Assert pattern:**
   ```typescript
   it('updates block text', async () => {
     // Arrange
     const block = createTestBlock();
     
     // Act
     const result = await updateBlock(block._id, 'New text');
     
     // Assert
     expect(result.markdownText).toBe('New text');
   });
   ```

2. **Test one thing per test:**
   - ✅ Good: `it('grants lock')`
   - ❌ Bad: `it('grants lock and updates block and creates version')`

3. **Use descriptive variable names:**
   - ✅ `const lockedByAnotherUser = createLock({ userId: 'user2' })`
   - ❌ `const l = { ...}`

4. **Mock time for date-dependent tests:**
   ```typescript
   vi.setSystemTime(new Date('2024-01-01'));
   const lock = createLock();
   expect(isExpired(lock)).toBe(false);
   ```

## Continuous Integration

GitHub Actions runs `npm run test:ci` on every push and PR.

**Required checks:**
- ✅ All linters pass
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ All E2E tests pass

**If CI fails:**
1. Check logs for error messages
2. Run failing test locally: `npm test -- <test-name>`
3. Fix issue
4. Re-run `npm run test:ci` before pushing

## Test Coverage

We aim for:
- **Unit tests**: 80%+ coverage of business logic
- **Integration tests**: All major user flows
- **E2E tests**: Critical paths (login, edit, agent interaction)

**Check coverage:**
```bash
npm test -- --coverage
```

View HTML report: `coverage/index.html`
