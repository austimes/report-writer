import { describe, it, expect } from 'vitest';
import { convexTest } from 'convex-test';
import { api } from '../_generated/api';
import schema from '../schema';

describe('projects.create', () => {
  it('should create project with default document and root node', async () => {
    const t = convexTest(schema);

    const userId = await t.run(async (ctx) => {
      return await ctx.db.insert('users', {
        email: 'test@example.com',
        name: 'Test User',
        createdAt: Date.now(),
      });
    });

    const projectId = await t.mutation(api["tables/projects"].create, {
      ownerId: userId,
      name: 'Test Project',
      description: 'Test description',
    });

    const project = await t.run(async (ctx) => {
      return await ctx.db.get(projectId);
    });
    expect(project).toBeDefined();
    expect(project?.name).toBe('Test Project');

    const documents = await t.run(async (ctx) => {
      return await ctx.db
        .query('documents')
        .withIndex('by_project', (q) => q.eq('projectId', projectId))
        .collect();
    });
    expect(documents).toHaveLength(1);
    expect(documents[0].title).toBe('Untitled Document');
    expect(documents[0].rootNodeId).toBeDefined();

    const rootNode = await t.run(async (ctx) => {
      return await ctx.db.get(documents[0].rootNodeId!);
    });
    expect(rootNode).toBeDefined();
    expect(rootNode?.nodeType).toBe('document');
    expect(rootNode?.documentId).toBe(documents[0]._id);
    expect(rootNode?.parentId).toBeUndefined();
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
