import { query, mutation } from "../_generated/server";
import { v } from "convex/values";
import { Id } from "../_generated/dataModel";
import { MutationCtx, QueryCtx } from "../_generated/server";

// --- Internal helpers (not exported) ---

async function getDocumentLock(ctx: QueryCtx | MutationCtx, documentId: Id<"documents">) {
  return await ctx.db
    .query("locks")
    .withIndex("by_document", (q) => q.eq("documentId", documentId))
    .filter((q) => q.eq(q.field("nodeId"), undefined))
    .unique();
}

async function getAncestorLock(
  ctx: QueryCtx | MutationCtx,
  nodeId: Id<"nodes">
): Promise<{
  lock: {
    _id: Id<"locks">;
    userId: Id<"users">;
    lockedAt: number;
  };
  lockedNodeId: Id<"nodes">;
  reason: "self" | "ancestor";
} | null> {
  let currentNodeId: Id<"nodes"> | undefined = nodeId;
  let isFirst = true;
  const MAX_DEPTH = 256;

  for (let depth = 0; depth < MAX_DEPTH && currentNodeId; depth++) {
    const lock = await ctx.db
      .query("locks")
      .withIndex("by_node", (q) => q.eq("nodeId", currentNodeId))
      .unique();

    if (lock) {
      return {
        lock: {
          _id: lock._id,
          userId: lock.userId,
          lockedAt: lock.lockedAt,
        },
        lockedNodeId: currentNodeId,
        reason: isFirst ? "self" : "ancestor",
      };
    }

    const currentNode = await ctx.db.get(currentNodeId);
    if (!currentNode || !currentNode.parentId) break;

    currentNodeId = currentNode.parentId;
    isFirst = false;
  }

  return null;
}

async function getDescendantLock(
  ctx: QueryCtx | MutationCtx,
  nodeId: Id<"nodes">
): Promise<{
  lock: {
    _id: Id<"locks">;
    userId: Id<"users">;
    lockedAt: number;
  };
  lockedNodeId: Id<"nodes">;
} | null> {
  const node = await ctx.db.get(nodeId);
  if (!node) {
    throw new Error("Node not found");
  }

  const nodeLocks = await ctx.db
    .query("locks")
    .withIndex("by_document", (q) => q.eq("documentId", node.documentId))
    .filter((q) => q.neq(q.field("nodeId"), undefined))
    .collect();

  const MAX_DEPTH = 256;

  for (const lock of nodeLocks) {
    const lockedNodeId = lock.nodeId as Id<"nodes">;

    if (lockedNodeId === nodeId) continue;

    let currentNodeId: Id<"nodes"> | undefined = lockedNodeId;

    for (let depth = 0; depth < MAX_DEPTH && currentNodeId; depth++) {
      const currentNode = await ctx.db.get(currentNodeId);
      if (!currentNode || !currentNode.parentId) break;

      if (currentNode.parentId === nodeId) {
        return {
          lock: {
            _id: lock._id,
            userId: lock.userId,
            lockedAt: lock.lockedAt,
          },
          lockedNodeId,
        };
      }

      currentNodeId = currentNode.parentId;
    }
  }

  return null;
}

async function findLockBlockerForNode(
  ctx: QueryCtx | MutationCtx,
  nodeId: Id<"nodes">
): Promise<{
  lockId: Id<"locks">;
  nodeId?: Id<"nodes">;
  userId: Id<"users">;
  lockedAt: number;
  reason: "self" | "ancestor" | "descendant" | "document";
} | null> {
  const node = await ctx.db.get(nodeId);
  if (!node) {
    throw new Error("Node not found");
  }

  const documentLock = await getDocumentLock(ctx, node.documentId);
  if (documentLock) {
    return {
      lockId: documentLock._id,
      nodeId: undefined,
      userId: documentLock.userId,
      lockedAt: documentLock.lockedAt,
      reason: "document",
    };
  }

  const ancestor = await getAncestorLock(ctx, nodeId);
  if (ancestor) {
    return {
      lockId: ancestor.lock._id,
      nodeId: ancestor.lockedNodeId,
      userId: ancestor.lock.userId,
      lockedAt: ancestor.lock.lockedAt,
      reason: ancestor.reason,
    };
  }

  const descendant = await getDescendantLock(ctx, nodeId);
  if (descendant) {
    return {
      lockId: descendant.lock._id,
      nodeId: descendant.lockedNodeId,
      userId: descendant.lock.userId,
      lockedAt: descendant.lock.lockedAt,
      reason: "descendant",
    };
  }

  return null;
}

// --- Exported queries ---

export const getForDocument = query({
  args: { documentId: v.id("documents") },
  handler: async (ctx, { documentId }) => {
    return await ctx.db
      .query("locks")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .filter((q) => q.eq(q.field("nodeId"), undefined))
      .unique();
  },
});

export const getForNode = query({
  args: { nodeId: v.id("nodes") },
  handler: async (ctx, { nodeId }) => {
    return await ctx.db
      .query("locks")
      .withIndex("by_node", (q) => q.eq("nodeId", nodeId))
      .unique();
  },
});

export const listByProject = query({
  args: { projectId: v.id("projects") },
  handler: async (ctx, { projectId }) => {
    return await ctx.db
      .query("locks")
      .withIndex("by_project", (q) => q.eq("projectId", projectId))
      .collect();
  },
});

export const listByDocument = query({
  args: { documentId: v.id("documents") },
  handler: async (ctx, { documentId }) => {
    const documentLock = await ctx.db
      .query("locks")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .filter((q) => q.eq(q.field("nodeId"), undefined))
      .unique();

    const nodeLocks = await ctx.db
      .query("locks")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .filter((q) => q.neq(q.field("nodeId"), undefined))
      .collect();

    const locks = documentLock ? [documentLock, ...nodeLocks] : nodeLocks;
    return locks;
  },
});

export const getLockBlocker = query({
  args: { nodeId: v.id("nodes") },
  handler: async (ctx, { nodeId }) => {
    return await findLockBlockerForNode(ctx, nodeId);
  },
});

// --- Exported mutations ---

export const createDocumentLock = mutation({
  args: {
    documentId: v.id("documents"),
    userId: v.id("users"),
  },
  handler: async (ctx, { documentId, userId }) => {
    const document = await ctx.db.get(documentId);
    if (!document) {
      throw new Error("Document not found");
    }

    const existingDocLock = await getDocumentLock(ctx, documentId);
    if (existingDocLock) {
      throw new Error("Document is already locked");
    }

    const nodeLocks = await ctx.db
      .query("locks")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .filter((q) => q.neq(q.field("nodeId"), undefined))
      .collect();

    if (nodeLocks.length > 0) {
      throw new Error("Document has locked nodes");
    }

    return await ctx.db.insert("locks", {
      projectId: document.projectId,
      documentId,
      userId,
      lockedAt: Date.now(),
    });
  },
});

export const createNodeLock = mutation({
  args: {
    nodeId: v.id("nodes"),
    userId: v.id("users"),
  },
  handler: async (ctx, { nodeId, userId }) => {
    const node = await ctx.db.get(nodeId);
    if (!node) {
      throw new Error("Node not found");
    }

    const blocker = await findLockBlockerForNode(ctx, nodeId);
    if (blocker) {
      throw new Error(
        `Cannot lock node; blocked by ${blocker.reason} lock (${blocker.lockId})`
      );
    }

    return await ctx.db.insert("locks", {
      projectId: node.projectId,
      documentId: node.documentId,
      nodeId,
      userId,
      lockedAt: Date.now(),
    });
  },
});

export const deleteLock = mutation({
  args: { lockId: v.id("locks") },
  handler: async (ctx, { lockId }) => {
    await ctx.db.delete(lockId);
  },
});

export const updateLockedAt = mutation({
  args: { lockId: v.id("locks") },
  handler: async (ctx, { lockId }) => {
    await ctx.db.patch(lockId, {
      lockedAt: Date.now(),
    });
  },
});
