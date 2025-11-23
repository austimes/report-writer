import { test, expect } from '@playwright/test';
import { SignupPage } from '../pages/SignupPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { EditorPage } from '../pages/EditorPage';
import { generateTestId } from '../../utils/testHelpers';

test.describe('Comments', () => {
  test('should create comment on section', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Comment Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing comments');
    await projectsPage.openProject(projectName);
    
    const commentText = 'This is a test comment';
    await editorPage.createComment(commentText);
    
    const commentVisible = await page.locator(`text=${commentText}`).isVisible();
    expect(commentVisible).toBeTruthy();
  });

  test('should assign comment to agent', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Comment Agent Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing comment assignment');
    await projectsPage.openProject(projectName);
    
    await editorPage.createComment('Assign this to agent');
    
    const assignButton = page.getByRole('button', { name: /assign|agent/i });
    if (await assignButton.isVisible()) {
      await assignButton.click();
      
      await page.waitForTimeout(500);
      
      const threadCreated = await page.locator('text=/thread|agent/i').isVisible();
      expect(threadCreated).toBeTruthy();
    }
  });

  test('should resolve comment', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Comment Resolve Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing comment resolution');
    await projectsPage.openProject(projectName);
    
    await editorPage.createComment('Comment to resolve');
    
    const resolveButton = page.getByRole('button', { name: /resolve/i });
    if (await resolveButton.isVisible()) {
      await resolveButton.click();
      
      await page.waitForTimeout(500);
      
      const resolvedIndicator = await page.locator('text=/resolved|complete/i').isVisible();
      expect(resolvedIndicator).toBeTruthy();
    }
  });

  test('should show comment author', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const userName = 'Comment Author';
    const projectName = `Comment Author Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup(userName, testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing comment author');
    await projectsPage.openProject(projectName);
    
    await editorPage.createComment('Test comment with author');
    
    const authorVisible = await page.locator(`text=${userName}`).isVisible();
    expect(authorVisible).toBeTruthy();
  });

  test('should support multiple comments', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Multiple Comments Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing multiple comments');
    await projectsPage.openProject(projectName);
    
    await editorPage.createComment('First comment');
    await page.waitForTimeout(500);
    
    await editorPage.createComment('Second comment');
    await page.waitForTimeout(500);
    
    const firstCommentVisible = await page.locator('text=First comment').isVisible();
    const secondCommentVisible = await page.locator('text=Second comment').isVisible();
    
    expect(firstCommentVisible).toBeTruthy();
    expect(secondCommentVisible).toBeTruthy();
  });
});
