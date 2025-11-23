import { Page, Locator } from '@playwright/test';

export class EditorPage {
  readonly page: Page;
  readonly sectionsList: Locator;
  readonly blockEditor: Locator;
  readonly lockButton: Locator;
  readonly lockIndicator: Locator;
  readonly saveIndicator: Locator;
  readonly versionHistoryButton: Locator;
  readonly commentsButton: Locator;
  readonly agentThreadButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.sectionsList = page.locator('[class*="sections-list"], nav');
    this.blockEditor = page.locator('textarea, [contenteditable="true"]');
    this.lockButton = page.getByRole('button', { name: /lock|unlock/i });
    this.lockIndicator = page.locator('[class*="lock-indicator"], [class*="lock-badge"]');
    this.saveIndicator = page.locator('text=/saving|saved/i');
    this.versionHistoryButton = page.getByRole('button', { name: /version|history/i });
    this.commentsButton = page.getByRole('button', { name: /comment/i });
    this.agentThreadButton = page.getByRole('button', { name: /agent|thread/i });
  }

  async goto(projectId: string) {
    await this.page.goto(`/projects/${projectId}`);
  }

  async selectSection(sectionName: string) {
    const section = this.page.locator(`text=${sectionName}`).first();
    await section.click();
  }

  async acquireLock() {
    await this.lockButton.click();
    await this.page.waitForTimeout(500);
  }

  async releaseLock() {
    const unlockButton = this.page.getByRole('button', { name: /unlock|release/i });
    await unlockButton.click();
    await this.page.waitForTimeout(500);
  }

  async getLockStatus() {
    return await this.lockIndicator.textContent();
  }

  async isLocked() {
    const status = await this.getLockStatus();
    return status?.toLowerCase().includes('locked') || false;
  }

  async editBlock(content: string) {
    await this.blockEditor.first().clear();
    await this.blockEditor.first().fill(content);
    await this.page.waitForTimeout(1000);
  }

  async getBlockContent() {
    return await this.blockEditor.first().inputValue();
  }

  async waitForSave() {
    await this.page.waitForSelector('text=/saved/i', { timeout: 5000 });
  }

  async openVersionHistory() {
    await this.versionHistoryButton.click();
  }

  async createComment(text: string) {
    await this.commentsButton.click();
    const commentInput = this.page.locator('textarea[placeholder*="comment" i], input[placeholder*="comment" i]');
    await commentInput.fill(text);
    const submitButton = this.page.getByRole('button', { name: /add|submit|create/i });
    await submitButton.click();
  }

  async openAgentThread() {
    await this.agentThreadButton.click();
  }

  async sendAgentMessage(message: string) {
    const messageInput = this.page.locator('textarea[placeholder*="message" i], input[placeholder*="message" i]');
    await messageInput.fill(message);
    const sendButton = this.page.getByRole('button', { name: /send/i });
    await sendButton.click();
  }

  async waitForAgentResponse() {
    await this.page.waitForSelector('text=/proposed edit|suggestion/i', { timeout: 10000 });
  }

  async acceptProposedEdit() {
    const acceptButton = this.page.getByRole('button', { name: /accept|apply/i });
    await acceptButton.click();
    await this.page.waitForTimeout(1000);
  }

  async rejectProposedEdit() {
    const rejectButton = this.page.getByRole('button', { name: /reject|dismiss/i });
    await rejectButton.click();
  }
}
