import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

export const getForResource = query({
  args: {
    resourceType: v.union(
      v.literal("section"),
      v.literal("block"),
      v.literal("thread")
    ),
    resourceId: v.string(),
  },
  handler: async (ctx, { resourceType, resourceId }) => {
    return await ctx.db
      .query("locks")
      .withIndex("by_resource", (q) =>
        q.eq("resourceType", resourceType).eq("resourceId", resourceId)
      )
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

export const createLock = mutation({
  args: {
    projectId: v.id("projects"),
    resourceType: v.union(
      v.literal("section"),
      v.literal("block"),
      v.literal("thread")
    ),
    resourceId: v.string(),
    userId: v.id("users"),
  },
  handler: async (ctx, { projectId, resourceType, resourceId, userId }) => {
    return await ctx.db.insert("locks", {
      projectId,
      resourceType,
      resourceId,
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
