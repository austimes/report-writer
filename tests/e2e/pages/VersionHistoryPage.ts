import { Page, Locator } from '@playwright/test';

export class VersionHistoryPage {
  readonly page: Page;
  readonly versionsList: Locator;
  readonly compareButton: Locator;
  readonly restoreButton: Locator;
  readonly diffView: Locator;
  readonly closeButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.versionsList = page.locator('[class*="version"], li');
    this.compareButton = page.getByRole('button', { name: /compare/i });
    this.restoreButton = page.getByRole('button', { name: /restore/i });
    this.diffView = page.locator('[class*="diff"], pre');
    this.closeButton = page.getByRole('button', { name: /close/i });
  }

  async selectVersion(index: number) {
    await this.versionsList.nth(index).click();
  }

  async compareVersions(index1: number, index2: number) {
    await this.versionsList.nth(index1).click();
    await this.versionsList.nth(index2).click({ modifiers: ['Meta'] });
    await this.compareButton.click();
  }

  async getDiffContent() {
    return await this.diffView.textContent();
  }

  async restoreVersion(index: number) {
    await this.selectVersion(index);
    await this.restoreButton.click();
    const confirmButton = this.page.getByRole('button', { name: /confirm|yes/i });
    await confirmButton.click();
    await this.page.waitForTimeout(1000);
  }

  async close() {
    await this.closeButton.click();
  }

  async getVersionCount() {
    return await this.versionsList.count();
  }
}
