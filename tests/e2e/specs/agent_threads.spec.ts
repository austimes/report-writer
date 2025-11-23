import { test, expect } from '@playwright/test';
import { SignupPage } from '../pages/SignupPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { EditorPage } from '../pages/EditorPage';
import { generateTestId } from '../../utils/testHelpers';

test.describe('Agent Threads', () => {
  test('should create thread and get agent response', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Agent Thread Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing agent threads');
    await projectsPage.openProject(projectName);
    
    await editorPage.acquireLock();
    
    await editorPage.openAgentThread();
    
    await editorPage.sendAgentMessage('Please help me write a summary for this section');
    
    await editorPage.waitForAgentResponse();
    
    const responseVisible = await page.locator('text=/fake|response|summary/i').isVisible();
    expect(responseVisible).toBeTruthy();
  });

  test('should accept proposed edits from agent', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Agent Edit Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing agent edits');
    await projectsPage.openProject(projectName);
    
    await editorPage.acquireLock();
    
    const initialContent = 'Original content';
    await editorPage.editBlock(initialContent);
    await editorPage.waitForSave();
    
    await editorPage.openAgentThread();
    await editorPage.sendAgentMessage('Improve this text');
    await editorPage.waitForAgentResponse();
    
    await editorPage.acceptProposedEdit();
    
    await page.waitForTimeout(1000);
    
    const updatedContent = await editorPage.getBlockContent();
    expect(updatedContent).not.toBe(initialContent);
  });

  test('should reject proposed edits from agent', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Agent Reject Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing agent rejection');
    await projectsPage.openProject(projectName);
    
    await editorPage.acquireLock();
    
    const initialContent = 'Original content to keep';
    await editorPage.editBlock(initialContent);
    await editorPage.waitForSave();
    
    await editorPage.openAgentThread();
    await editorPage.sendAgentMessage('Improve this text');
    await editorPage.waitForAgentResponse();
    
    await editorPage.rejectProposedEdit();
    
    await page.waitForTimeout(500);
    
    const content = await editorPage.getBlockContent();
    expect(content).toBe(initialContent);
  });

  test('should create version after accepting agent edit', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Agent Version Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing version creation');
    await projectsPage.openProject(projectName);
    
    await editorPage.acquireLock();
    await editorPage.editBlock('Version test content');
    await editorPage.waitForSave();
    
    await editorPage.openAgentThread();
    await editorPage.sendAgentMessage('Improve this');
    await editorPage.waitForAgentResponse();
    await editorPage.acceptProposedEdit();
    
    await page.waitForTimeout(1000);
    
    await editorPage.openVersionHistory();
    
    const versionExists = await page.locator('text=/version|history/i').isVisible();
    expect(versionExists).toBeTruthy();
  });
});
