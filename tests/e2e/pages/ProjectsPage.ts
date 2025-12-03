import { Page, Locator } from '@playwright/test';

export class ProjectsPage {
  readonly page: Page;
  readonly createProjectButton: Locator;
  readonly logoutButton: Locator;
  readonly userEmail: Locator;
  readonly projectList: Locator;
  readonly projectCards: Locator;

  constructor(page: Page) {
    this.page = page;
    this.createProjectButton = page.getByRole('button', { name: 'Create Project' });
    this.logoutButton = page.getByRole('button', { name: /logout/i });
    this.userEmail = page.locator('text=/.*@.*\\..*/');
    this.projectList = page.getByTestId('project-list');
    this.projectCards = page.getByTestId('project-card');
  }

  async goto() {
    await this.page.goto('/');
  }

  async waitForReady() {
    await this.createProjectButton.waitFor({ state: 'visible', timeout: 10000 });
    await this.page.waitForTimeout(2000);
  }

  async openCreateProjectModal() {
    await this.waitForReady();
    await this.createProjectButton.click();
    await this.page.getByTestId('create-project-modal').waitFor();
  }

  async createProject(name: string, description?: string) {
    await this.openCreateProjectModal();

    await this.page.getByTestId('project-name-input').fill(name);
    if (description) {
      await this.page.getByTestId('project-description-input').fill(description);
    }

    await this.page.getByTestId('submit-create-project').click();
    // Wait for modal to close and list to update
    await this.page.getByTestId('create-project-modal').waitFor({ state: 'detached' });
  }

  async getProjectByName(name: string) {
    return this.page.getByTestId('project-card').filter({ hasText: name }).first();
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
