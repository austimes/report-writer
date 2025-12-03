import { query, mutation } from "../_generated/server";
import { v } from "convex/values";
import { Id } from "../_generated/dataModel";

const LOCK_EXPIRY_MS = 7200000; // 2 hours

type Lock = {
  _id: any;
  _creationTime: number;
  projectId: any;
  documentId?: any;
  nodeId?: any;
  userId: any;
  lockedAt: number;
};

function isLockExpired(lock: Lock): boolean {
  return lock.lockedAt + LOCK_EXPIRY_MS < Date.now();
}

export const acquireDocumentLock = mutation({
  args: {
    documentId: v.id("documents"),
  },
  handler: async (ctx, { documentId }) => {
    const userId = await ctx.auth.getUserIdentity();
    if (!userId) {
      throw new Error("Not authenticated");
    }

    const user = await ctx.db
      .query("users")
      .withIndex("by_email", (q) => q.eq("email", userId.email!))
      .unique();

    if (!user) {
      throw new Error("User not found");
    }

    const document = await ctx.db.get(documentId);
    if (!document) {
      throw new Error("Document not found");
    }

    // Check for existing document lock
    const existingLock = await ctx.db
      .query("locks")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .filter((q) => q.eq(q.field("nodeId"), undefined))
      .unique();

    if (existingLock) {
      if (!isLockExpired(existingLock)) {
        if (existingLock.userId !== user._id) {
          const lockOwner = await ctx.db.get(existingLock.userId);
          throw new Error(
            `Document is locked by ${lockOwner?.name || "another user"}`
          );
        }
        // Refresh existing lock
        await ctx.db.patch(existingLock._id, { lockedAt: Date.now() });
        return await ctx.db.get(existingLock._id);
      } else {
        await ctx.db.delete(existingLock._id);
      }
    }

    const lockId = await ctx.db.insert("locks", {
      projectId: document.projectId,
      documentId,
      nodeId: undefined,
      userId: user._id,
      lockedAt: Date.now(),
    });

    return await ctx.db.get(lockId);
  },
});

export const acquireNodeLock = mutation({
  args: {
    nodeId: v.id("nodes"),
  },
  handler: async (ctx, { nodeId }) => {
    const userId = await ctx.auth.getUserIdentity();
    if (!userId) {
      throw new Error("Not authenticated");
    }

    const user = await ctx.db
      .query("users")
      .withIndex("by_email", (q) => q.eq("email", userId.email!))
      .unique();

    if (!user) {
      throw new Error("User not found");
    }

    const node = await ctx.db.get(nodeId);
    if (!node) {
      throw new Error("Node not found");
    }

    // Check for existing node lock
    const existingLock = await ctx.db
      .query("locks")
      .withIndex("by_node", (q) => q.eq("nodeId", nodeId))
      .unique();

    if (existingLock) {
      if (!isLockExpired(existingLock)) {
        if (existingLock.userId !== user._id) {
          const lockOwner = await ctx.db.get(existingLock.userId);
          throw new Error(
            `Node is locked by ${lockOwner?.name || "another user"}`
          );
        }
        // Refresh existing lock
        await ctx.db.patch(existingLock._id, { lockedAt: Date.now() });
        return await ctx.db.get(existingLock._id);
      } else {
        await ctx.db.delete(existingLock._id);
      }
    }

    // Check for document-level lock that would block node editing
    const documentLock = await ctx.db
      .query("locks")
      .withIndex("by_document", (q) => q.eq("documentId", node.documentId))
      .filter((q) => q.eq(q.field("nodeId"), undefined))
      .unique();

    if (documentLock && !isLockExpired(documentLock) && documentLock.userId !== user._id) {
      const lockOwner = await ctx.db.get(documentLock.userId);
      throw new Error(
        `Document is locked by ${lockOwner?.name || "another user"}`
      );
    }

    const lockId = await ctx.db.insert("locks", {
      projectId: node.projectId,
      documentId: node.documentId,
      nodeId,
      userId: user._id,
      lockedAt: Date.now(),
    });

    return await ctx.db.get(lockId);
  },
});

export const releaseLock = mutation({
  args: { lockId: v.id("locks") },
  handler: async (ctx, { lockId }) => {
    await ctx.db.delete(lockId);
  },
});

export const refreshLock = mutation({
  args: { lockId: v.id("locks") },
  handler: async (ctx, { lockId }) => {
    await ctx.db.patch(lockId, { lockedAt: Date.now() });
    return await ctx.db.get(lockId);
  },
});

export const getLocksForProject = query({
  args: { projectId: v.id("projects") },
  handler: async (ctx, { projectId }) => {
    const locks = await ctx.db
      .query("locks")
      .withIndex("by_project", (q) => q.eq("projectId", projectId))
      .collect();

    return locks.filter((lock) => !isLockExpired(lock));
  },
});

export const getLocksForDocument = query({
  args: { documentId: v.id("documents") },
  handler: async (ctx, { documentId }) => {
    const locks = await ctx.db
      .query("locks")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .collect();

    return locks.filter((lock) => !isLockExpired(lock));
  },
});

export const getLockForNode = query({
  args: { nodeId: v.id("nodes") },
  handler: async (ctx, { nodeId }) => {
    const lock = await ctx.db
      .query("locks")
      .withIndex("by_node", (q) => q.eq("nodeId", nodeId))
      .unique();

    if (!lock || isLockExpired(lock)) {
      return null;
    }

    return lock;
  },
});

export const getLockForDocument = query({
  args: { documentId: v.id("documents") },
  handler: async (ctx, { documentId }) => {
    const lock = await ctx.db
      .query("locks")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .filter((q) => q.eq(q.field("nodeId"), undefined))
      .unique();

    if (!lock || isLockExpired(lock)) {
      return null;
    }

    return lock;
  },
});

export const getLockForResource = query({
  args: {
    resourceType: v.string(),
    resourceId: v.string(),
  },
  handler: async (ctx, { resourceType, resourceId }) => {
    if (resourceType === "document") {
      const lock = await ctx.db
        .query("locks")
        .withIndex("by_document", (q) => q.eq("documentId", resourceId as any))
        .filter((q) => q.eq(q.field("nodeId"), undefined))
        .unique();

      if (!lock || isLockExpired(lock)) {
        return null;
      }
      return lock;
    }

    if (resourceType === "node") {
      const lock = await ctx.db
        .query("locks")
        .withIndex("by_node", (q) => q.eq("nodeId", resourceId as any))
        .unique();

      if (!lock || isLockExpired(lock)) {
        return null;
      }
      return lock;
    }

    return null;
  },
});

export const acquireLock = mutation({
  args: {
    projectId: v.id("projects"),
    resourceType: v.string(),
    resourceId: v.string(),
  },
  handler: async (ctx, { resourceType, resourceId }) => {
    const userId = await ctx.auth.getUserIdentity();
    if (!userId) {
      throw new Error("Not authenticated");
    }

    const user = await ctx.db
      .query("users")
      .withIndex("by_email", (q) => q.eq("email", userId.email!))
      .unique();

    if (!user) {
      throw new Error("User not found");
    }

    if (resourceType === "document") {
      const documentId = resourceId as Id<"documents">;
      const document = await ctx.db.get(documentId);
      if (!document) {
        throw new Error("Document not found");
      }

      const existingLock = await ctx.db
        .query("locks")
        .withIndex("by_document", (q) => q.eq("documentId", documentId))
        .filter((q) => q.eq(q.field("nodeId"), undefined))
        .unique();

      if (existingLock) {
        if (!isLockExpired(existingLock)) {
          if (existingLock.userId !== user._id) {
            const lockOwner = await ctx.db.get(existingLock.userId);
            throw new Error(
              `Document is locked by ${(lockOwner as { name?: string })?.name || "another user"}`
            );
          }
          await ctx.db.patch(existingLock._id, { lockedAt: Date.now() });
          return await ctx.db.get(existingLock._id);
        } else {
          await ctx.db.delete(existingLock._id);
        }
      }

      const lockId = await ctx.db.insert("locks", {
        projectId: document.projectId,
        documentId,
        nodeId: undefined,
        userId: user._id,
        lockedAt: Date.now(),
      });

      return await ctx.db.get(lockId);
    }

    if (resourceType === "node") {
      const nodeId = resourceId as Id<"nodes">;
      const node = await ctx.db.get(nodeId);
      if (!node) {
        throw new Error("Node not found");
      }

      const existingLock = await ctx.db
        .query("locks")
        .withIndex("by_node", (q) => q.eq("nodeId", nodeId))
        .unique();

      if (existingLock) {
        if (!isLockExpired(existingLock)) {
          if (existingLock.userId !== user._id) {
            const lockOwner = await ctx.db.get(existingLock.userId);
            throw new Error(
              `Node is locked by ${(lockOwner as { name?: string })?.name || "another user"}`
            );
          }
          await ctx.db.patch(existingLock._id, { lockedAt: Date.now() });
          return await ctx.db.get(existingLock._id);
        } else {
          await ctx.db.delete(existingLock._id);
        }
      }

      const documentLock = await ctx.db
        .query("locks")
        .withIndex("by_document", (q) => q.eq("documentId", node.documentId))
        .filter((q) => q.eq(q.field("nodeId"), undefined))
        .unique();

      if (documentLock && !isLockExpired(documentLock) && documentLock.userId !== user._id) {
        const lockOwner = await ctx.db.get(documentLock.userId);
        throw new Error(
          `Document is locked by ${(lockOwner as { name?: string })?.name || "another user"}`
        );
      }

      const lockId = await ctx.db.insert("locks", {
        projectId: node.projectId,
        documentId: node.documentId,
        nodeId,
        userId: user._id,
        lockedAt: Date.now(),
      });

      return await ctx.db.get(lockId);
    }

    throw new Error(`Unsupported resource type: ${resourceType}`);
  },
});

export const getHierarchyLockConflict = query({
  args: {
    resourceType: v.string(),
    resourceId: v.string(),
  },
  handler: async () => {
    return null;
  },
});
