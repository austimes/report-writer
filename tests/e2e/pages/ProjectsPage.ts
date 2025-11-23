import { Page, Locator } from '@playwright/test';

export class ProjectsPage {
  readonly page: Page;
  readonly createProjectButton: Locator;
  readonly logoutButton: Locator;
  readonly userEmail: Locator;
  readonly projectCards: Locator;

  constructor(page: Page) {
    this.page = page;
    this.createProjectButton = page.getByRole('button', { name: /create project/i });
    this.logoutButton = page.getByRole('button', { name: /logout/i });
    this.userEmail = page.locator('text=/.*@.*\\..*/');
    this.projectCards = page.locator('[class*="project-card"], a[href^="/projects/"]');
  }

  async goto() {
    await this.page.goto('/');
  }

  async openCreateProjectModal() {
    await this.createProjectButton.click();
  }

  async createProject(name: string, description?: string) {
    await this.openCreateProjectModal();
    
    const nameInput = this.page.locator('input[placeholder*="name" i], input[name="name"]').first();
    await nameInput.fill(name);
    
    if (description) {
      const descInput = this.page.locator('input[placeholder*="description" i], textarea[placeholder*="description" i], input[name="description"], textarea[name="description"]').first();
      await descInput.fill(description);
    }
    
    const createButton = this.page.getByRole('button', { name: /^create$/i });
    await createButton.click();
    
    await this.page.waitForTimeout(500);
  }

  async getProjectByName(name: string) {
    return this.page.locator(`text=${name}`).first();
  }

  async openProject(name: string) {
    const project = await this.getProjectByName(name);
    await project.click();
    await this.page.waitForURL(/\/projects\/.+/);
  }

  async logout() {
    await this.logoutButton.click();
    await this.page.waitForURL('/login');
  }

  async getProjectCount() {
    return await this.projectCards.count();
  }
}
