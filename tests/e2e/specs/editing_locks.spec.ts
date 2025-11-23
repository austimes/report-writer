import { test, expect } from '@playwright/test';
import { SignupPage } from '../pages/SignupPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { EditorPage } from '../pages/EditorPage';
import { generateTestId } from '../../utils/testHelpers';

test.describe('Editing Locks', () => {
  test('should handle concurrent editing with locks', async ({ browser }) => {
    const userAEmail = `userA-${generateTestId()}@example.com`;
    const userBEmail = `userB-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Lock Test Project ${Date.now()}`;

    const contextA = await browser.newContext();
    const contextB = await browser.newContext();
    
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();

    const signupPageA = new SignupPage(pageA);
    const projectsPageA = new ProjectsPage(pageA);
    
    await signupPageA.goto();
    await signupPageA.signup('User A', userAEmail, password);
    await signupPageA.waitForNavigation();
    
    await projectsPageA.createProject(projectName, 'Testing concurrent locks');
    await projectsPageA.openProject(projectName);
    
    const projectUrl = pageA.url();
    
    const signupPageB = new SignupPage(pageB);
    
    await signupPageB.goto();
    await signupPageB.signup('User B', userBEmail, password);
    await signupPageB.waitForNavigation();
    
    await pageB.goto(projectUrl);
    
    const editorA = new EditorPage(pageA);
    const editorB = new EditorPage(pageB);
    
    await editorA.acquireLock();
    
    await pageB.waitForTimeout(1000);
    
    const lockStatusB = await editorB.getLockStatus();
    expect(lockStatusB).toContain('Locked');
    
    const initialContent = 'Initial block content';
    await editorA.editBlock(initialContent);
    await editorA.waitForSave();
    
    await editorA.releaseLock();
    
    await pageB.waitForTimeout(1000);
    
    await editorB.acquireLock();
    
    const updatedContent = 'Updated by User B';
    await editorB.editBlock(updatedContent);
    await editorB.waitForSave();
    
    const finalContent = await editorB.getBlockContent();
    expect(finalContent).toContain('Updated by User B');

    await contextA.close();
    await contextB.close();
  });

  test('should prevent editing without lock', async ({ browser }) => {
    const userAEmail = `userA-${generateTestId()}@example.com`;
    const userBEmail = `userB-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Lock Prevent Test ${Date.now()}`;

    const contextA = await browser.newContext();
    const contextB = await browser.newContext();
    
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();

    const signupPageA = new SignupPage(pageA);
    const projectsPageA = new ProjectsPage(pageA);
    
    await signupPageA.goto();
    await signupPageA.signup('User A', userAEmail, password);
    await signupPageA.waitForNavigation();
    
    await projectsPageA.createProject(projectName, 'Testing lock prevention');
    await projectsPageA.openProject(projectName);
    
    const projectUrl = pageA.url();
    
    const signupPageB = new SignupPage(pageB);
    
    await signupPageB.goto();
    await signupPageB.signup('User B', userBEmail, password);
    await signupPageB.waitForNavigation();
    
    await pageB.goto(projectUrl);
    
    const editorA = new EditorPage(pageA);
    const editorB = new EditorPage(pageB);
    
    await editorA.acquireLock();
    
    await pageB.waitForTimeout(1000);
    
    const blockEditorB = editorB.blockEditor.first();
    const isDisabled = await blockEditorB.isDisabled();
    const isReadonly = await blockEditorB.getAttribute('readonly');
    
    expect(isDisabled || isReadonly !== null).toBeTruthy();

    await contextA.close();
    await contextB.close();
  });

  test('should show lock owner name', async ({ browser }) => {
    const userAEmail = `userA-${generateTestId()}@example.com`;
    const userBEmail = `userB-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Lock Owner Test ${Date.now()}`;

    const contextA = await browser.newContext();
    const contextB = await browser.newContext();
    
    const pageA = await contextA.newPage();
    const pageB = await contextB.newPage();

    const signupPageA = new SignupPage(pageA);
    const projectsPageA = new ProjectsPage(pageA);
    
    await signupPageA.goto();
    await signupPageA.signup('User A', userAEmail, password);
    await signupPageA.waitForNavigation();
    
    await projectsPageA.createProject(projectName, 'Testing lock owner display');
    await projectsPageA.openProject(projectName);
    
    const projectUrl = pageA.url();
    
    const signupPageB = new SignupPage(pageB);
    
    await signupPageB.goto();
    await signupPageB.signup('User B', userBEmail, password);
    await signupPageB.waitForNavigation();
    
    await pageB.goto(projectUrl);
    
    const editorA = new EditorPage(pageA);
    const editorB = new EditorPage(pageB);
    
    await editorA.acquireLock();
    
    await pageB.waitForTimeout(1000);
    
    const lockStatusB = await editorB.getLockStatus();
    expect(lockStatusB).toMatch(/Locked by|User A/i);

    await contextA.close();
    await contextB.close();
  });
});
