import { test, expect } from '@playwright/test';
import { SignupPage } from '../pages/SignupPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { generateTestId } from '../../utils/testHelpers';

test.describe('Projects', () => {
  test('user can create a project and see it in the list', async ({ page }) => {
    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);

    const email = `projects-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const name = 'Projects User';

    await signupPage.goto();
    await signupPage.signup(name, email, password);
    await signupPage.waitForNavigation();

    // Verify we landed on projects page
    await expect(page).toHaveURL('/');
    await expect(projectsPage.userEmail).toContainText(email);

    const initialCount = await projectsPage.getProjectCount();

    const projectName = `My Project ${Date.now()}`;
    const projectDescription = 'E2E project creation test';

    await projectsPage.createProject(projectName, projectDescription);

    // Assert new project appears in the list
    const newCount = await projectsPage.getProjectCount();
    expect(newCount).toBe(initialCount + 1);

    const projectCard = await projectsPage.getProjectByName(projectName);
    await expect(projectCard).toBeVisible();
    await expect(projectCard).toContainText(projectDescription);

    // And we can open it
    await projectsPage.openProject(projectName);
    await expect(page).toHaveURL(/\/projects\/.+/);
  });

  test('projects are scoped per user', async ({ browser }) => {
    // User A
    const contextA = await browser.newContext();
    const pageA = await contextA.newPage();
    const signupA = new SignupPage(pageA);
    const projectsA = new ProjectsPage(pageA);

    const emailA = `userA-${generateTestId()}@example.com`;
    const password = 'test-password-123';

    await signupA.goto();
    await signupA.signup('User A', emailA, password);
    await signupA.waitForNavigation();

    const projectNameA = `User A Project ${Date.now()}`;
    await projectsA.createProject(projectNameA, 'Owned by A');

    // User B
    const contextB = await browser.newContext();
    const pageB = await contextB.newPage();
    const signupB = new SignupPage(pageB);
    const projectsB = new ProjectsPage(pageB);

    const emailB = `userB-${generateTestId()}@example.com`;

    await signupB.goto();
    await signupB.signup('User B', emailB, password);
    await signupB.waitForNavigation();

    // User B should NOT see User A's project
    const cardForAProject = await projectsB.getProjectByName(projectNameA);
    await expect(cardForAProject).not.toBeVisible();

    await contextA.close();
    await contextB.close();
  });
});
