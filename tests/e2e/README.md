# End-to-End (E2E) Tests

E2E tests verify the complete application flow from the user's perspective using Playwright. These tests run in real browsers and test the entire stack.

## Structure

```
tests/e2e/
├── README.md              # This file
├── fixtures/
│   ├── auth.ts           # Authentication fixtures
│   └── projects.ts       # Project fixtures
├── pages/                # Page object models
│   ├── LoginPage.ts      # Login page interactions
│   ├── SignupPage.ts     # Signup page interactions
│   ├── ProjectsPage.ts   # Projects listing page
│   ├── EditorPage.ts     # Project editor page
│   └── VersionHistoryPage.ts # Version history page
├── specs/                # Test specifications
│   ├── auth.spec.ts      # Authentication tests
│   ├── editing_locks.spec.ts # Concurrent editing tests
│   ├── agent_threads.spec.ts # Agent interaction tests
│   ├── versions_history.spec.ts # Version management tests
│   └── comments.spec.ts  # Comments and collaboration tests
```

## Running E2E Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run E2E tests in headed mode (see browser)
npx playwright test --headed

# Run E2E tests in debug mode
npx playwright test --debug

# Run specific test file
npx playwright test tests/e2e/auth/login.spec.ts

# Run tests in specific browser
npx playwright test --project=chromium

# Show test report
npx playwright show-report playwright-results/html
```

## Writing E2E Tests

E2E tests should:

1. **Use page object models** for reusable UI interactions
2. **Use fixtures** for authentication and test data
3. **Test complete user workflows**, not individual functions
4. **Be independent** - each test should work in isolation
5. **Use data-testid attributes** for stable selectors

### Example E2E Test

```typescript
import { test, expect } from '../fixtures/projects';

test.describe('Project Management', () => {
  test('user can create a new project', async ({ authenticatedPage }) => {
    await authenticatedPage.goto('/projects');
    
    await authenticatedPage.click('[data-testid="create-project-button"]');
    await authenticatedPage.fill('[data-testid="project-name"]', 'My New Project');
    await authenticatedPage.fill('[data-testid="project-description"]', 'Test project description');
    await authenticatedPage.click('[data-testid="submit-project"]');
    
    await expect(authenticatedPage.locator('[data-testid="project-list"]'))
      .toContainText('My New Project');
  });

  test('user can view project details', async ({ authenticatedPage, testProject }) => {
    await authenticatedPage.goto(`/projects/${testProject.id}`);
    
    await expect(authenticatedPage.locator('[data-testid="project-name"]'))
      .toContainText(testProject.name);
  });
});
```

## Fixtures

Fixtures provide pre-configured test environments:

### Authentication Fixture (`tests/e2e/fixtures/auth.ts`)

```typescript
import { test, expect } from '../fixtures/auth';

test('authenticated feature', async ({ authenticatedPage, testUser }) => {
  // authenticatedPage is already logged in as testUser
  await authenticatedPage.goto('/dashboard');
});
```

### Project Fixture (`tests/e2e/fixtures/projects.ts`)

```typescript
import { test, expect } from '../fixtures/projects';

test('project feature', async ({ authenticatedPage, testProject }) => {
  // testProject is already created in the database
  await authenticatedPage.goto(`/projects/${testProject.id}`);
});
```

## Selectors

**Prefer data-testid attributes** for stable selectors:

```html
<!-- Good -->
<button data-testid="submit-button">Submit</button>

<!-- Avoid (brittle) -->
<button class="btn btn-primary">Submit</button>
```

```typescript
// Good
await page.click('[data-testid="submit-button"]');

// Avoid
await page.click('.btn.btn-primary');
```

## Configuration

Playwright configuration is in `playwright.config.ts`:

- Tests run in **chromium, firefox, webkit** by default
- **Retries**: 2 retries on CI, 0 locally
- **Timeout**: 30 seconds per test
- **Screenshots/Videos**: On failure only
- **Base URL**: http://localhost:3000 (configurable via `E2E_BASE_URL`)

## CI/CD

E2E tests run in CI via `npm run test:ci`. They:

- Run headlessly in all configured browsers
- Retry failed tests up to 2 times
- Generate JSON and HTML reports
- Capture screenshots/videos on failure

## Debugging

### View test in browser
```bash
npx playwright test --headed --project=chromium
```

### Step through test
```bash
npx playwright test --debug
```

### View trace after failure
```bash
npx playwright show-trace playwright-results/trace.zip
```

### Screenshots
Failed tests automatically capture screenshots in `playwright-results/`

## Best Practices

1. **Keep tests independent** - don't rely on test execution order
2. **Use meaningful test data** - helps with debugging
3. **Test happy paths first** - then edge cases
4. **One assertion concept per test** - easier to diagnose failures
5. **Use fixtures for setup/teardown** - cleaner test code
6. **Avoid hardcoded waits** - use Playwright's auto-waiting
7. **Tag tests appropriately** - for selective execution

## Troubleshooting

**Tests timing out?**
- Check if app is running on expected port
- Increase timeout in playwright.config.ts
- Use `await page.waitForLoadState('networkidle')`

**Flaky tests?**
- Avoid `page.waitForTimeout()` - use specific waits
- Check for race conditions
- Ensure proper element visibility

**Can't see what's happening?**
- Run with `--headed` flag
- Use `--debug` for step-by-step execution
- Add `await page.pause()` to pause at specific point
