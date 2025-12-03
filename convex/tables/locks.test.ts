import { describe, it, expect } from 'vitest';
import { convexTest } from 'convex-test';
import { api } from '../_generated/api';
import schema from '../schema';
import { Id } from '../_generated/dataModel';

/**
 * Node Locking Test Suite
 * 
 * Tests the hierarchical locking rules:
 * 1. Cannot lock a node that is already locked
 * 2. Cannot lock a node if any ancestor is locked
 * 3. Cannot lock a node if any descendant is locked
 * 
 * Tree structure used in tests:
 *   document (root)
 *     ├── heading1
 *     │     ├── paragraph1
 *     │     └── paragraph2
 *     └── heading2
 *           └── paragraph3
 */

async function setupTestTree(t: ReturnType<typeof convexTest>) {
  // Create user
  const userId = await t.run(async (ctx) => {
    return await ctx.db.insert('users', {
      email: 'test@example.com',
      name: 'Test User',
      createdAt: Date.now(),
    });
  });

  // Create a second user for conflict tests
  const user2Id = await t.run(async (ctx) => {
    return await ctx.db.insert('users', {
      email: 'test2@example.com',
      name: 'Test User 2',
      createdAt: Date.now(),
    });
  });

  // Create project
  const projectId = await t.run(async (ctx) => {
    return await ctx.db.insert('projects', {
      ownerId: userId,
      name: 'Test Project',
      createdAt: Date.now(),
      archived: false,
    });
  });

  // Create document
  const documentId = await t.run(async (ctx) => {
    return await ctx.db.insert('documents', {
      projectId,
      title: 'Test Document',
      createdAt: Date.now(),
      createdByUserId: userId,
    });
  });

  // Create node tree:
  //   document (root)
  //     ├── heading1
  //     │     ├── paragraph1
  //     │     └── paragraph2
  //     └── heading2
  //           └── paragraph3

  const rootNodeId = await t.run(async (ctx) => {
    return await ctx.db.insert('nodes', {
      projectId,
      documentId,
      parentId: undefined,
      order: 0,
      nodeType: 'document',
      createdAt: Date.now(),
    });
  });

  // Update document with rootNodeId
  await t.run(async (ctx) => {
    await ctx.db.patch(documentId, { rootNodeId });
  });

  const heading1Id = await t.run(async (ctx) => {
    return await ctx.db.insert('nodes', {
      projectId,
      documentId,
      parentId: rootNodeId,
      order: 0,
      nodeType: 'heading',
      text: 'Heading 1',
      attrs: { level: 1 },
      createdAt: Date.now(),
    });
  });

  const paragraph1Id = await t.run(async (ctx) => {
    return await ctx.db.insert('nodes', {
      projectId,
      documentId,
      parentId: heading1Id,
      order: 0,
      nodeType: 'paragraph',
      text: 'Paragraph 1',
      createdAt: Date.now(),
    });
  });

  const paragraph2Id = await t.run(async (ctx) => {
    return await ctx.db.insert('nodes', {
      projectId,
      documentId,
      parentId: heading1Id,
      order: 1,
      nodeType: 'paragraph',
      text: 'Paragraph 2',
      createdAt: Date.now(),
    });
  });

  const heading2Id = await t.run(async (ctx) => {
    return await ctx.db.insert('nodes', {
      projectId,
      documentId,
      parentId: rootNodeId,
      order: 1,
      nodeType: 'heading',
      text: 'Heading 2',
      attrs: { level: 1 },
      createdAt: Date.now(),
    });
  });

  const paragraph3Id = await t.run(async (ctx) => {
    return await ctx.db.insert('nodes', {
      projectId,
      documentId,
      parentId: heading2Id,
      order: 0,
      nodeType: 'paragraph',
      text: 'Paragraph 3',
      createdAt: Date.now(),
    });
  });

  return {
    userId,
    user2Id,
    projectId,
    documentId,
    rootNodeId,
    heading1Id,
    paragraph1Id,
    paragraph2Id,
    heading2Id,
    paragraph3Id,
  };
}

describe('locks - basic operations', () => {
  it('should allow locking an unlocked node', async () => {
    const t = convexTest(schema);
    const { userId, heading1Id } = await setupTestTree(t);

    const lockId = await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    expect(lockId).toBeDefined();

    const lock = await t.query(api['tables/locks'].getForNode, {
      nodeId: heading1Id,
    });
    expect(lock).toBeDefined();
    expect(lock?.userId).toBe(userId);
  });

  it('should allow deleting a lock', async () => {
    const t = convexTest(schema);
    const { userId, heading1Id } = await setupTestTree(t);

    const lockId = await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    await t.mutation(api['tables/locks'].deleteLock, { lockId });

    const lock = await t.query(api['tables/locks'].getForNode, {
      nodeId: heading1Id,
    });
    expect(lock).toBeNull();
  });
});

describe('locks - cannot lock already locked node', () => {
  it('should reject locking a node that is already locked by another user', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, heading1Id } = await setupTestTree(t);

    // User 1 locks heading1
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    // User 2 tries to lock same node - should fail
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: heading1Id,
        userId: user2Id,
      })
    ).rejects.toThrow();
  });

  it('should reject locking a node that is already locked by same user', async () => {
    const t = convexTest(schema);
    const { userId, heading1Id } = await setupTestTree(t);

    // User locks heading1
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    // Same user tries to lock again - should fail
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: heading1Id,
        userId,
      })
    ).rejects.toThrow();
  });
});

describe('locks - cannot lock child if ancestor is locked', () => {
  it('should reject locking a child when parent is locked', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, heading1Id, paragraph1Id } = await setupTestTree(t);

    // User 1 locks heading1
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    // User 2 tries to lock paragraph1 (child of heading1) - should fail
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: paragraph1Id,
        userId: user2Id,
      })
    ).rejects.toThrow();
  });

  it('should reject locking a grandchild when grandparent is locked', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, rootNodeId, paragraph1Id } = await setupTestTree(t);

    // User 1 locks root
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: rootNodeId,
      userId,
    });

    // User 2 tries to lock paragraph1 (grandchild of root) - should fail
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: paragraph1Id,
        userId: user2Id,
      })
    ).rejects.toThrow();
  });

  it('should reject locking child even by same user who locked parent', async () => {
    const t = convexTest(schema);
    const { userId, heading1Id, paragraph1Id } = await setupTestTree(t);

    // User locks heading1
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    // Same user tries to lock paragraph1 (child) - should fail (already covered by parent lock)
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: paragraph1Id,
        userId,
      })
    ).rejects.toThrow();
  });
});

describe('locks - cannot lock parent if descendant is locked', () => {
  it('should reject locking a parent when child is locked', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, heading1Id, paragraph1Id } = await setupTestTree(t);

    // User 1 locks paragraph1
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: paragraph1Id,
      userId,
    });

    // User 2 tries to lock heading1 (parent of paragraph1) - should fail
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: heading1Id,
        userId: user2Id,
      })
    ).rejects.toThrow();
  });

  it('should reject locking grandparent when grandchild is locked', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, rootNodeId, paragraph1Id } = await setupTestTree(t);

    // User 1 locks paragraph1
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: paragraph1Id,
      userId,
    });

    // User 2 tries to lock root (grandparent of paragraph1) - should fail
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: rootNodeId,
        userId: user2Id,
      })
    ).rejects.toThrow();
  });

  it('should reject locking parent even by same user who locked child', async () => {
    const t = convexTest(schema);
    const { userId, heading1Id, paragraph1Id } = await setupTestTree(t);

    // User locks paragraph1
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: paragraph1Id,
      userId,
    });

    // Same user tries to lock heading1 (parent) - should fail (would create overlapping locks)
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: heading1Id,
        userId,
      })
    ).rejects.toThrow();
  });
});

describe('locks - sibling isolation', () => {
  it('should allow locking a sibling when another sibling is locked', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, paragraph1Id, paragraph2Id } = await setupTestTree(t);

    // User 1 locks paragraph1
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: paragraph1Id,
      userId,
    });

    // User 2 should be able to lock paragraph2 (sibling)
    const lockId = await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: paragraph2Id,
      userId: user2Id,
    });

    expect(lockId).toBeDefined();
  });

  it('should allow locking a cousin when another cousin is locked', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, paragraph1Id, paragraph3Id } = await setupTestTree(t);

    // User 1 locks paragraph1 (under heading1)
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: paragraph1Id,
      userId,
    });

    // User 2 should be able to lock paragraph3 (under heading2 - cousin)
    const lockId = await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: paragraph3Id,
      userId: user2Id,
    });

    expect(lockId).toBeDefined();
  });
});

describe('locks - getLockBlocker helper', () => {
  it('should return the blocking lock when node is directly locked', async () => {
    const t = convexTest(schema);
    const { userId, heading1Id } = await setupTestTree(t);

    // Lock heading1
    const lockId = await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    // Check what blocks locking heading1
    const blocker = await t.query(api['tables/locks'].getLockBlocker, {
      nodeId: heading1Id,
    });

    expect(blocker).toBeDefined();
    expect(blocker?.lockId).toBe(lockId);
    expect(blocker?.nodeId).toBe(heading1Id);
    expect(blocker?.reason).toBe('self');
  });

  it('should return the ancestor lock when checking a child node', async () => {
    const t = convexTest(schema);
    const { userId, heading1Id, paragraph1Id } = await setupTestTree(t);

    // Lock heading1
    const lockId = await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    // Check what blocks locking paragraph1
    const blocker = await t.query(api['tables/locks'].getLockBlocker, {
      nodeId: paragraph1Id,
    });

    expect(blocker).toBeDefined();
    expect(blocker?.lockId).toBe(lockId);
    expect(blocker?.nodeId).toBe(heading1Id);
    expect(blocker?.reason).toBe('ancestor');
  });

  it('should return the descendant lock when checking a parent node', async () => {
    const t = convexTest(schema);
    const { userId, heading1Id, paragraph1Id } = await setupTestTree(t);

    // Lock paragraph1
    const lockId = await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: paragraph1Id,
      userId,
    });

    // Check what blocks locking heading1
    const blocker = await t.query(api['tables/locks'].getLockBlocker, {
      nodeId: heading1Id,
    });

    expect(blocker).toBeDefined();
    expect(blocker?.lockId).toBe(lockId);
    expect(blocker?.nodeId).toBe(paragraph1Id);
    expect(blocker?.reason).toBe('descendant');
  });

  it('should return null when node can be locked', async () => {
    const t = convexTest(schema);
    const { heading1Id, paragraph3Id } = await setupTestTree(t);

    // No locks exist
    const blocker1 = await t.query(api['tables/locks'].getLockBlocker, {
      nodeId: heading1Id,
    });
    expect(blocker1).toBeNull();

    // Lock heading1
    const { userId } = await setupTestTree(t);
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    // paragraph3 (under heading2) should still be lockable
    const blocker2 = await t.query(api['tables/locks'].getLockBlocker, {
      nodeId: paragraph3Id,
    });
    expect(blocker2).toBeNull();
  });
});

describe('locks - document-level locks', () => {
  it('should reject node lock when document is locked', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, documentId, heading1Id } = await setupTestTree(t);

    // Lock the document
    await t.mutation(api['tables/locks'].createDocumentLock, {
      documentId,
      userId,
    });

    // Try to lock a node - should fail (document lock covers all nodes)
    await expect(
      t.mutation(api['tables/locks'].createNodeLock, {
        nodeId: heading1Id,
        userId: user2Id,
      })
    ).rejects.toThrow();
  });

  it('should reject document lock when any node is locked', async () => {
    const t = convexTest(schema);
    const { userId, user2Id, documentId, heading1Id } = await setupTestTree(t);

    // Lock a node
    await t.mutation(api['tables/locks'].createNodeLock, {
      nodeId: heading1Id,
      userId,
    });

    // Try to lock the document - should fail
    await expect(
      t.mutation(api['tables/locks'].createDocumentLock, {
        documentId,
        userId: user2Id,
      })
    ).rejects.toThrow();
  });
});
