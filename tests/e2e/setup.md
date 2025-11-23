# E2E Test Setup Guide

This guide explains how to set up and run the E2E tests.

## Prerequisites

1. **Node.js and npm** installed
2. **Playwright browsers** installed
3. **Development environment** ready

## Installation

Install Playwright browsers if not already installed:

```bash
npx playwright install
```

## Running Tests

### Quick Start

```bash
# Run all E2E tests
npm run test:e2e

# Run specific test file
npx playwright test specs/auth.spec.ts

# Run in headed mode (see browser)
npx playwright test --headed

# Run in debug mode
npx playwright test --debug
```

### Before Running Tests

**Important**: The tests expect the application to be running. You have two options:

#### Option 1: Manual Setup (Recommended for Development)

Start the required services in separate terminals:

```bash
# Terminal 1: Start Convex dev server
cd convex
npx convex dev

# Terminal 2: Start the web app
cd apps/web
npm run dev

# Terminal 3: Run the tests
npm run test:e2e
```

#### Option 2: Automatic Setup (Future)

The `playwright.config.ts` has a `webServer` configuration that can be uncommented to automatically start the dev server before tests run.

To enable it, edit `playwright.config.ts` and uncomment:

```typescript
webServer: {
  command: 'npm run dev',
  url: 'http://localhost:3000',
  reuseExistingServer: !process.env.CI,
  timeout: 120 * 1000,
}
```

### Test Environment Variables

Set `TEST_MODE=true` when running services to enable test-specific behavior:

```bash
TEST_MODE=true npx convex dev
TEST_MODE=true npm run dev
```

### Custom Base URL

If your app runs on a different port:

```bash
E2E_BASE_URL=http://localhost:4000 npm run test:e2e
```

## Test Coverage

The E2E test suite covers:

1. **Authentication** (auth.spec.ts)
   - User signup flow
   - User login flow
   - Logout
   - Creating first project after signup
   - Error handling

2. **Editing Locks** (editing_locks.spec.ts)
   - Concurrent editing with multiple users
   - Lock acquisition and release
   - Lock status visibility
   - Preventing edits without lock

3. **Agent Threads** (agent_threads.spec.ts)
   - Creating agent threads
   - Sending messages to agent
   - Receiving agent responses (FakeLLM)
   - Accepting proposed edits
   - Rejecting proposed edits
   - Version creation after edits

4. **Version History** (versions_history.spec.ts)
   - Creating versions
   - Viewing version history
   - Comparing versions (diff view)
   - Restoring previous versions
   - Version timestamps

5. **Comments** (comments.spec.ts)
   - Creating comments on sections
   - Assigning comments to agent
   - Resolving comments
   - Multiple comments support
   - Comment author display

## Viewing Results

After running tests:

```bash
# View HTML report
npx playwright show-report playwright-results/html

# Check JSON report
cat playwright-results/results.json
```

## Debugging Failed Tests

1. **Run in headed mode** to see what's happening:
   ```bash
   npx playwright test --headed
   ```

2. **Run in debug mode** to step through:
   ```bash
   npx playwright test --debug
   ```

3. **Check screenshots** on failure:
   ```bash
   ls playwright-results/
   ```

4. **Add console logging** in tests:
   ```typescript
   page.on('console', msg => console.log(msg.text()));
   ```

5. **Pause test execution**:
   ```typescript
   await page.pause();
   ```

## CI/CD Integration

Tests are configured for CI in `playwright.config.ts`:
- Automatic retries on failure
- Single worker for stability
- JSON and HTML reports
- Screenshots and videos captured on failure

Run tests as they would in CI:

```bash
CI=true npm run test:e2e
```

## Common Issues

### Tests timeout or fail to start

**Problem**: App not running or running on wrong port

**Solution**: 
- Ensure dev server is running on http://localhost:3000
- Or set `E2E_BASE_URL` to correct URL

### Tests fail with "navigation" errors

**Problem**: Routes not configured or auth not working

**Solution**:
- Check that all routes in App.tsx are working
- Verify auth hooks are properly implemented
- Check Convex is running and connected

### Lock tests fail

**Problem**: Lock system not fully implemented

**Solution**:
- These tests assume locking is implemented in Convex
- May need to adjust tests based on actual implementation

### Agent tests timeout

**Problem**: FakeLLM not configured or agent responses too slow

**Solution**:
- Ensure FakeLLM is set up in sandbox
- Check that TEST_MODE enables FakeLLM
- May need to increase timeout for agent tests

## Notes

- Tests use unique email addresses (with timestamps) to avoid conflicts
- Tests are designed to be independent and can run in parallel
- Page object models are in `tests/e2e/pages/` for maintainability
- Some tests create their own users and projects for isolation
