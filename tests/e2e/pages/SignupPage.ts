import { Page, Locator } from '@playwright/test';

export class SignupPage {
  readonly page: Page;
  readonly firstNameInput: Locator;
  readonly lastNameInput: Locator;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;
  readonly loginLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.firstNameInput = page.getByRole('textbox', { name: 'First name' });
    this.lastNameInput = page.getByRole('textbox', { name: 'Last name' });
    this.emailInput = page.getByRole('textbox', { name: 'Email address' });
    this.passwordInput = page.getByRole('textbox', { name: 'Password' });
    this.submitButton = page.getByRole('button', { name: 'Continue', exact: true });
    this.errorMessage = page.locator('.bg-red-100');
    this.loginLink = page.getByRole('link', { name: 'Sign in' });
  }

  async goto() {
    await this.page.goto('/sign-up');
  }

  async signup(name: string, email: string, password: string) {
    const [firstName, ...rest] = name.split(' ');
    const lastName = rest.join(' ') || firstName;
    
    await this.firstNameInput.fill(firstName);
    await this.lastNameInput.fill(lastName);
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async waitForNavigation() {
    await this.page.waitForURL('/');
  }

  async getError() {
    return await this.errorMessage.textContent();
  }
}
