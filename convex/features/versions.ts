import { mutation } from "../_generated/server";
import { v } from "convex/values";
import { api } from "../_generated/api";

export const createVersionSnapshot = mutation({
  args: {
    projectId: v.id("projects"),
    documentId: v.id("documents"),
    summary: v.optional(v.string()),
  },
  handler: async (ctx, { documentId, summary }): Promise<any> => {
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

    return await ctx.runMutation(api.tables.reportVersions.createVersion, {
      documentId,
      userId: user._id,
      summary: summary || `Snapshot at ${new Date().toLocaleString()}`,
    });
  },
});

export const restoreVersion = mutation({
  args: {
    versionId: v.id("reportVersions"),
  },
  handler: async (ctx, { versionId }): Promise<any> => {
    const userId = await ctx.auth.getUserIdentity();
    if (!userId) {
      throw new Error("Not authenticated");
    }

    return await ctx.runMutation(api.tables.reportVersions.restoreVersion, {
      versionId,
    });
  },
});
