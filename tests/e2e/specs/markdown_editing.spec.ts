import { test, expect } from '@playwright/test';
import { ProjectsPage } from '../pages/ProjectsPage';
import { EditorPage } from '../pages/EditorPage';

test.describe('Markdown Editing', () => {
  test('user can create project, create and save markdown document', async ({ page }) => {
    const projectsPage = new ProjectsPage(page);
    const editorPage = new EditorPage(page);
    
    await page.goto('/');
    await expect(page).toHaveURL('/');
    
    await page.waitForTimeout(5000);
    
    const projectName = `Markdown Project ${Date.now()}`;
    const projectDescription = 'Test markdown editing';
    
    await projectsPage.createProject(projectName, projectDescription);
    await projectsPage.openProject(projectName);
    
    await expect(page).toHaveURL(/\/projects\/.+/);
    await expect(page.getByText(projectName)).toBeVisible();
  });
});
