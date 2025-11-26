import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

export const getById = query({
  args: { id: v.id("agentThreads") },
  handler: async (ctx, { id }) => {
    return await ctx.db.get(id);
  },
});

export const listByProject = query({
  args: { projectId: v.id("projects") },
  handler: async (ctx, { projectId }) => {
    return await ctx.db
      .query("agentThreads")
      .withIndex("by_project", (q) => q.eq("projectId", projectId))
      .collect();
  },
});

export const listByDocument = query({
  args: { documentId: v.id("documents") },
  handler: async (ctx, { documentId }) => {
    return await ctx.db
      .query("agentThreads")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .collect();
  },
});

export const listByNode = query({
  args: { nodeId: v.id("nodes") },
  handler: async (ctx, { nodeId }) => {
    return await ctx.db
      .query("agentThreads")
      .withIndex("by_node", (q) => q.eq("anchorNodeId", nodeId))
      .collect();
  },
});

export const create = mutation({
  args: {
    projectId: v.id("projects"),
    documentId: v.optional(v.id("documents")),
    title: v.string(),
    anchorNodeId: v.optional(v.id("nodes")),
    anchorCommentId: v.optional(v.id("comments")),
    metadata: v.optional(v.any()),
  },
  handler: async (
    ctx,
    { projectId, documentId, title, anchorNodeId, anchorCommentId, metadata }
  ) => {
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

    const project = await ctx.db.get(projectId);
    if (!project) {
      throw new Error(`Project ${projectId} not found`);
    }

    if (documentId) {
      const document = await ctx.db.get(documentId);
      if (!document || document.projectId !== projectId) {
        throw new Error("Invalid document");
      }
    }

    if (anchorNodeId) {
      const node = await ctx.db.get(anchorNodeId);
      if (!node) {
        throw new Error("Invalid anchor node");
      }
      if (documentId && node.documentId !== documentId) {
        throw new Error("Anchor node does not belong to the specified document");
      }
    }

    if (anchorCommentId) {
      const comment = await ctx.db.get(anchorCommentId);
      if (!comment || comment.projectId !== projectId) {
        throw new Error("Invalid anchor comment");
      }
    }

    return await ctx.db.insert("agentThreads", {
      projectId,
      documentId,
      title,
      createdByUserId: user._id,
      createdAt: Date.now(),
      status: "active",
      anchorNodeId,
      anchorCommentId,
      metadata,
    });
  },
});
