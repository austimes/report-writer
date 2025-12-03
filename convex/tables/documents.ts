import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

export const getById = query({
  args: { id: v.id("documents") },
  handler: async (ctx, { id }) => {
    return await ctx.db.get(id);
  },
});

export const listByProject = query({
  args: { projectId: v.id("projects") },
  handler: async (ctx, { projectId }) => {
    return await ctx.db
      .query("documents")
      .withIndex("by_project", (q) => q.eq("projectId", projectId))
      .collect();
  },
});

export const create = mutation({
  args: {
    projectId: v.id("projects"),
    title: v.string(),
    userId: v.id("users"),
  },
  handler: async (ctx, { projectId, title, userId }) => {
    const project = await ctx.db.get(projectId);
    if (!project) {
      throw new Error(`Project ${projectId} not found`);
    }

    const now = Date.now();

    const documentId = await ctx.db.insert("documents", {
      projectId,
      title,
      createdAt: now,
      createdByUserId: userId,
      rootNodeId: undefined,
    });

    const rootNodeId = await ctx.db.insert("nodes", {
      projectId,
      documentId,
      parentId: undefined,
      order: 0,
      nodeType: "document",
      text: undefined,
      attrs: { title },
      createdAt: now,
    });

    await ctx.db.patch(documentId, { rootNodeId });

    return documentId;
  },
});

export const update = mutation({
  args: {
    id: v.id("documents"),
    title: v.string(),
  },
  handler: async (ctx, { id, title }) => {
    const doc = await ctx.db.get(id);
    if (!doc) {
      throw new Error(`Document ${id} not found`);
    }

    await ctx.db.patch(id, { title });

    // Also update the root node's attrs.title if it exists
    const rootNode = await ctx.db.get(doc.rootNodeId);
    if (rootNode && rootNode.attrs) {
      await ctx.db.patch(doc.rootNodeId, {
        attrs: { ...rootNode.attrs, title },
      });
    }
  },
});

export const deleteDocument = mutation({
  args: { id: v.id("documents") },
  handler: async (ctx, { id }) => {
    const doc = await ctx.db.get(id);
    if (!doc) {
      throw new Error(`Document ${id} not found`);
    }

    // Delete all nodes belonging to this document
    const nodes = await ctx.db
      .query("nodes")
      .withIndex("by_document", (q) => q.eq("documentId", id))
      .collect();

    for (const node of nodes) {
      await ctx.db.delete(node._id);
    }

    // Delete the document itself
    await ctx.db.delete(id);
  },
});
