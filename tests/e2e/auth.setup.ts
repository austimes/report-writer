import { test as setup, expect } from '@playwright/test';

const authFile = 'tests/e2e/.auth/user.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/sign-in');
  
  await page.getByRole('textbox', { name: 'Username' }).fill('test');
  await page.getByRole('textbox', { name: 'Password' }).fill('testmachine!@#$');
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  
  await page.waitForURL('/');
  await expect(page).toHaveURL('/');
  
  await page.context().storageState({ path: authFile });
});
