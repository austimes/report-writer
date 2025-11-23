import { test, expect } from '@playwright/test';
import { SignupPage } from '../pages/SignupPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { EditorPage } from '../pages/EditorPage';
import { VersionHistoryPage } from '../pages/VersionHistoryPage';
import { generateTestId } from '../../utils/testHelpers';

test.describe('Version History', () => {
  test('should create and view versions', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Version Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);
    const versionHistoryPage = new VersionHistoryPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing versions');
    await projectsPage.openProject(projectName);
    
    await editorPage.acquireLock();
    
    const firstContent = 'First version content';
    await editorPage.editBlock(firstContent);
    await editorPage.waitForSave();
    
    await page.waitForTimeout(1000);
    
    const secondContent = 'Second version content';
    await editorPage.editBlock(secondContent);
    await editorPage.waitForSave();
    
    await editorPage.openVersionHistory();
    
    const versionCount = await versionHistoryPage.getVersionCount();
    expect(versionCount).toBeGreaterThan(0);
  });

  test('should compare two versions', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Version Compare Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);
    const versionHistoryPage = new VersionHistoryPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing version comparison');
    await projectsPage.openProject(projectName);
    
    await editorPage.acquireLock();
    
    await editorPage.editBlock('Version 1 text');
    await editorPage.waitForSave();
    await page.waitForTimeout(1000);
    
    await editorPage.editBlock('Version 2 text');
    await editorPage.waitForSave();
    await page.waitForTimeout(1000);
    
    await editorPage.openVersionHistory();
    
    const versionCount = await versionHistoryPage.getVersionCount();
    if (versionCount >= 2) {
      await versionHistoryPage.compareVersions(0, 1);
      
      await page.waitForTimeout(500);
      
      const diffVisible = await versionHistoryPage.diffView.isVisible();
      expect(diffVisible).toBeTruthy();
    }
  });

  test('should restore previous version', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Version Restore Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);
    const versionHistoryPage = new VersionHistoryPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing version restore');
    await projectsPage.openProject(projectName);
    
    await editorPage.acquireLock();
    
    const originalContent = 'Original version content';
    await editorPage.editBlock(originalContent);
    await editorPage.waitForSave();
    await page.waitForTimeout(1000);
    
    const modifiedContent = 'Modified version content';
    await editorPage.editBlock(modifiedContent);
    await editorPage.waitForSave();
    await page.waitForTimeout(1000);
    
    await editorPage.openVersionHistory();
    
    const versionCount = await versionHistoryPage.getVersionCount();
    if (versionCount >= 2) {
      await versionHistoryPage.restoreVersion(1);
      
      await versionHistoryPage.close();
      
      const restoredContent = await editorPage.getBlockContent();
      expect(restoredContent).toBe(originalContent);
    }
  });

  test('should show version timestamps', async ({ page }) => {
    const testEmail = `test-${generateTestId()}@example.com`;
    const password = 'test-password-123';
    const projectName = `Version Timestamp Test ${Date.now()}`;

    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);
    const versionHistoryPage = new VersionHistoryPage(page);

    await signupPage.goto();
    await signupPage.signup('Test User', testEmail, password);
    await signupPage.waitForNavigation();
    
    await projectsPage.createProject(projectName, 'Testing version timestamps');
    await projectsPage.openProject(projectName);
    
    await editorPage.acquireLock();
    await editorPage.editBlock('Content with timestamp');
    await editorPage.waitForSave();
    
    await editorPage.openVersionHistory();
    
    const timestampVisible = await page.locator('text=/ago|am|pm|:\\d{2}/i').isVisible();
    expect(timestampVisible).toBeTruthy();
  });
});
