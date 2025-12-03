import { test, expect } from '@playwright/test';

test.describe('Nested Section Lock Validation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
  });

  test('should prevent locking parent section when child is locked', async ({ page, context }) => {
    const page2 = await context.newPage();
    await page2.goto('http://localhost:5173');

    await page.getByRole('link', { name: 'Create New Project' }).click();
    await page.getByLabel('Project Name').fill('Lock Test Project');
    await page.getByRole('button', { name: 'Create Project' }).click();
    
    await page.waitForURL(/\/editor\/.*$/);
    
    const editorContent = page.locator('[contenteditable="true"]');
    await editorContent.fill(`# Chapter 1

This is chapter content.

## Section 1.1

This is section content.`);
    
    await page.waitForTimeout(1000);
    
    const section11 = page.getByRole('heading', { name: 'Section 1.1' });
    await section11.click();
    await page.getByRole('button', { name: 'Lock' }).first().click();
    
    await expect(page.getByText(/Locked by you/i)).toBeVisible();
    
    await page2.goto(page.url());
    const chapter1 = page2.getByRole('heading', { name: 'Chapter 1' });
    await chapter1.click();
    await page2.getByRole('button', { name: 'Lock' }).first().click();
    
    await expect(page2.getByText(/Cannot lock.*child section.*is already locked/i)).toBeVisible();
  });

  test('should prevent locking child section when parent is locked', async ({ page, context }) => {
    const page2 = await context.newPage();
    await page2.goto('http://localhost:5173');

    await page.getByRole('link', { name: 'Create New Project' }).click();
    await page.getByLabel('Project Name').fill('Lock Test Project 2');
    await page.getByRole('button', { name: 'Create Project' }).click();
    
    await page.waitForURL(/\/editor\/.*$/);
    
    const editorContent = page.locator('[contenteditable="true"]');
    await editorContent.fill(`# Chapter 1

This is chapter content.

## Section 1.1

This is section content.`);
    
    await page.waitForTimeout(1000);
    
    const chapter1 = page.getByRole('heading', { name: 'Chapter 1' });
    await chapter1.click();
    await page.getByRole('button', { name: 'Lock' }).first().click();
    
    await expect(page.getByText(/Locked by you/i)).toBeVisible();
    
    await page2.goto(page.url());
    const section11 = page2.getByRole('heading', { name: 'Section 1.1' });
    await section11.click();
    await page2.getByRole('button', { name: 'Lock' }).first().click();
    
    await expect(page2.getByText(/Cannot lock.*parent section.*is already locked/i)).toBeVisible();
  });

  test('should allow locking sibling sections independently', async ({ page, context }) => {
    const page2 = await context.newPage();
    await page2.goto('http://localhost:5173');

    await page.getByRole('link', { name: 'Create New Project' }).click();
    await page.getByLabel('Project Name').fill('Lock Test Project 3');
    await page.getByRole('button', { name: 'Create Project' }).click();
    
    await page.waitForURL(/\/editor\/.*$/);
    
    const editorContent = page.locator('[contenteditable="true"]');
    await editorContent.fill(`# Chapter 1

Content 1

# Chapter 2

Content 2`);
    
    await page.waitForTimeout(1000);
    
    const chapter1 = page.getByRole('heading', { name: 'Chapter 1' });
    await chapter1.click();
    await page.getByRole('button', { name: 'Lock' }).first().click();
    
    await expect(page.getByText(/Locked by you/i)).toBeVisible();
    
    await page2.goto(page.url());
    const chapter2 = page2.getByRole('heading', { name: 'Chapter 2' });
    await chapter2.click();
    await page2.getByRole('button', { name: 'Lock' }).first().click();
    
    await expect(page2.getByText(/Locked by you/i)).toBeVisible();
  });
});
