import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

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
