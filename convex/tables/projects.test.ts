import { describe, it, expect, beforeEach } from 'vitest';
import { convexTest } from 'convex-test';
import { api } from '../_generated/api';
import schema from '../schema';

describe('projects.create', () => {
  it('should create project with default section and block', async () => {
    const t = convexTest(schema);

    // Create a test user
    const userId = await t.run(async (ctx) => {
      return await ctx.db.insert('users', {
        email: 'test@example.com',
        name: 'Test User',
        createdAt: Date.now(),
      });
    });

    // Create project using dot notation
    const projectId = await t.mutation(api["tables/projects"].create, {
      ownerId: userId,
      name: 'Test Project',
      description: 'Test description',
    });

    // Verify project exists
    const project = await t.run(async (ctx) => {
      return await ctx.db.get(projectId);
    });
    expect(project).toBeDefined();
    expect(project?.name).toBe('Test Project');

    // Verify section was created
    const sections = await t.run(async (ctx) => {
      return await ctx.db
        .query('sections')
        .withIndex('by_project', (q) => q.eq('projectId', projectId))
        .collect();
    });
    expect(sections).toHaveLength(1);
    expect(sections[0].headingText).toBe('Introduction');
    expect(sections[0].headingLevel).toBe(1);

    // Verify block was created with template markdown
    const blocks = await t.run(async (ctx) => {
      return await ctx.db
        .query('blocks')
        .withIndex('by_section', (q) => q.eq('sectionId', sections[0]._id))
        .collect();
    });
    expect(blocks).toHaveLength(1);
    expect(blocks[0].markdownText).toContain('Test Project');
    expect(blocks[0].markdownText).toContain('Start writing your report here');
    expect(blocks[0].blockType).toBe('paragraph');
    expect(blocks[0].lastEditorUserId).toBe(userId);
    expect(blocks[0].lastEditType).toBe('human');
  });

  it('should fail if user does not exist', async () => {
    const t = convexTest(schema);

    await expect(
      t.mutation(api["tables/projects"].create, {
        ownerId: 'invalid-id' as any,
        name: 'Test Project',
      })
    ).rejects.toThrow();
  });
});
