import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

export const getById = query({
  args: { id: v.id("reportVersions") },
  handler: async (ctx, { id }) => {
    return await ctx.db.get(id);
  },
});

export const listByProject = query({
  args: { projectId: v.id("projects") },
  handler: async (ctx, { projectId }) => {
    return await ctx.db
      .query("reportVersions")
      .withIndex("by_project_created", (q) => q.eq("projectId", projectId))
      .order("desc")
      .collect();
  },
});

export const create = mutation({
  args: {
    projectId: v.id("projects"),
    createdByUserId: v.id("users"),
    summary: v.optional(v.string()),
    snapshot: v.any(),
  },
  handler: async (ctx, { projectId, createdByUserId, summary, snapshot }) => {
    const project = await ctx.db.get(projectId);
    if (!project) {
      throw new Error(`Project ${projectId} not found`);
    }

    const user = await ctx.db.get(createdByUserId);
    if (!user) {
      throw new Error(`User ${createdByUserId} not found`);
    }

    return await ctx.db.insert("reportVersions", {
      projectId,
      createdByUserId,
      summary: summary ?? "Auto-saved version",
      snapshot,
      createdAt: Date.now(),
    });
  },
});
