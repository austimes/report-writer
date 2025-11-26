import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

export const getById = query({
  args: { id: v.id("projects") },
  handler: async (ctx, { id }) => {
    return await ctx.db.get(id);
  },
});

export const listByUser = query({
  args: { userId: v.id("users") },
  handler: async (ctx, { userId }) => {
    return await ctx.db
      .query("projects")
      .withIndex("by_owner", (q) => q.eq("ownerId", userId))
      .collect();
  },
});

export const create = mutation({
  args: {
    ownerId: v.id("users"),
    name: v.string(),
    description: v.optional(v.string()),
  },
  handler: async (ctx, { ownerId, name, description }) => {
    const owner = await ctx.db.get(ownerId);
    if (!owner) {
      throw new Error(`User ${ownerId} not found`);
    }

    const projectId = await ctx.db.insert("projects", {
      ownerId,
      name,
      description,
      createdAt: Date.now(),
      archived: false,
    });

    return projectId;
  },
});

export const update = mutation({
  args: {
    id: v.id("projects"),
    name: v.optional(v.string()),
    description: v.optional(v.string()),
  },
  handler: async (ctx, { id, name, description }) => {
    const project = await ctx.db.get(id);
    if (!project) {
      throw new Error(`Project ${id} not found`);
    }

    const updates: Record<string, any> = {};
    if (name !== undefined) updates.name = name;
    if (description !== undefined) updates.description = description;

    await ctx.db.patch(id, updates);
  },
});

export const archive = mutation({
  args: { id: v.id("projects") },
  handler: async (ctx, { id }) => {
    const project = await ctx.db.get(id);
    if (!project) {
      throw new Error(`Project ${id} not found`);
    }

    await ctx.db.patch(id, { archived: true });
  },
});

export const deleteProject = mutation({
  args: { id: v.id("projects") },
  handler: async (ctx, { id }) => {
    const project = await ctx.db.get(id);
    if (!project) {
      throw new Error(`Project ${id} not found`);
    }

    const documents = await ctx.db
      .query("documents")
      .withIndex("by_project", (q) => q.eq("projectId", id))
      .collect();

    for (const doc of documents) {
      const nodes = await ctx.db
        .query("nodes")
        .withIndex("by_document", (q) => q.eq("documentId", doc._id))
        .collect();
      
      for (const node of nodes) {
        await ctx.db.delete(node._id);
      }
      
      await ctx.db.delete(doc._id);
    }

    const members = await ctx.db
      .query("projectMembers")
      .withIndex("by_project", (q) => q.eq("projectId", id))
      .collect();
    
    for (const member of members) {
      await ctx.db.delete(member._id);
    }

    const locks = await ctx.db
      .query("locks")
      .withIndex("by_project", (q) => q.eq("projectId", id))
      .collect();
    
    for (const lock of locks) {
      await ctx.db.delete(lock._id);
    }

    const threads = await ctx.db
      .query("agentThreads")
      .withIndex("by_project", (q) => q.eq("projectId", id))
      .collect();
    
    for (const thread of threads) {
      await ctx.db.delete(thread._id);
    }

    const versions = await ctx.db
      .query("reportVersions")
      .withIndex("by_project", (q) => q.eq("projectId", id))
      .collect();
    
    for (const version of versions) {
      await ctx.db.delete(version._id);
    }

    const comments = await ctx.db
      .query("comments")
      .withIndex("by_project", (q) => q.eq("projectId", id))
      .collect();
    
    for (const comment of comments) {
      await ctx.db.delete(comment._id);
    }

    await ctx.db.delete(id);
  },
});
