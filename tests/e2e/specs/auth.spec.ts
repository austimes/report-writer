import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';
import { SignupPage } from '../pages/SignupPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { generateTestId } from '../../utils/testHelpers';

test.describe('Authentication', () => {
  test('should sign up a new user', async ({ page }) => {
    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);

    const testEmail = `test-${generateTestId()}@example.com`;
    const testPassword = 'test-password-123';
    const testName = 'Test User';

    await signupPage.goto();
    await signupPage.signup(testName, testEmail, testPassword);
    
    await signupPage.waitForNavigation();
    
    await expect(page).toHaveURL('/');
    await expect(projectsPage.userEmail).toBeVisible();
  });

  test('should login with existing user', async ({ page }) => {
    const signupPage = new SignupPage(page);
    const loginPage = new LoginPage(page);
    const projectsPage = new ProjectsPage(page);

    const testEmail = `test-${generateTestId()}@example.com`;
    const testPassword = 'test-password-123';
    const testName = 'Test User';

    await signupPage.goto();
    await signupPage.signup(testName, testEmail, testPassword);
    await signupPage.waitForNavigation();
    
    await projectsPage.logout();
    
    await loginPage.goto();
    await loginPage.login(testEmail, testPassword);
    await loginPage.waitForNavigation();
    
    await expect(page).toHaveURL('/');
    await expect(projectsPage.userEmail).toContainText(testEmail);
  });

  test('should logout successfully', async ({ page }) => {
    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);

    const testEmail = `test-${generateTestId()}@example.com`;
    const testPassword = 'test-password-123';
    const testName = 'Test User';

    await signupPage.goto();
    await signupPage.signup(testName, testEmail, testPassword);
    await signupPage.waitForNavigation();
    
    await projectsPage.logout();
    
    await expect(page).toHaveURL('/login');
  });

  test('should create first project after signup', async ({ page }) => {
    const signupPage = new SignupPage(page);
    const projectsPage = new ProjectsPage(page);

    const testEmail = `test-${generateTestId()}@example.com`;
    const testPassword = 'test-password-123';
    const testName = 'Test User';

    await signupPage.goto();
    await signupPage.signup(testName, testEmail, testPassword);
    await signupPage.waitForNavigation();
    
    const projectName = `My First Project ${Date.now()}`;
    const projectDescription = 'A project created during E2E testing';
    
    await projectsPage.createProject(projectName, projectDescription);
    
    const project = await projectsPage.getProjectByName(projectName);
    await expect(project).toBeVisible();
  });

  test('should show error on invalid login', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.login('invalid@example.com', 'wrongpassword');
    
    await page.waitForTimeout(1000);
    
    await expect(loginPage.errorMessage).toBeVisible();
  });

  test('should navigate between login and signup', async ({ page }) => {
    const loginPage = new LoginPage(page);
    const signupPage = new SignupPage(page);

    await loginPage.goto();
    await loginPage.signupLink.click();
    await expect(page).toHaveURL('/signup');
    
    await signupPage.loginLink.click();
    await expect(page).toHaveURL('/login');
  });
});
