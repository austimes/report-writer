import { mutation, query } from "../_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    documentId: v.id("documents"),
    targetNodeId: v.id("nodes"),
    body: v.string(),
    rangeStart: v.optional(v.number()),
    rangeEnd: v.optional(v.number()),
    assigneeType: v.optional(v.union(v.literal("human"), v.literal("agent"))),
    assigneeUserId: v.optional(v.id("users")),
    linkedNodeIds: v.optional(v.array(v.id("nodes"))),
  },
  handler: async (ctx, args) => {
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

    const document = await ctx.db.get(args.documentId);
    if (!document) {
      throw new Error("Document not found");
    }

    const commentId = await ctx.db.insert("comments", {
      projectId: document.projectId,
      documentId: args.documentId,
      targetNodeId: args.targetNodeId,
      rangeStart: args.rangeStart,
      rangeEnd: args.rangeEnd,
      authorUserId: user._id,
      createdAt: Date.now(),
      body: args.body,
      status: "open",
      assigneeType: args.assigneeType,
      assigneeUserId: args.assigneeUserId,
      linkedNodeIds: args.linkedNodeIds,
    });

    return commentId;
  },
});

export const listByDocument = query({
  args: {
    documentId: v.id("documents"),
  },
  handler: async (ctx, { documentId }) => {
    const comments = await ctx.db
      .query("comments")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .collect();

    const commentsWithAuthors = await Promise.all(
      comments.map(async (comment) => {
        const author = await ctx.db.get(comment.authorUserId);
        const assignee = comment.assigneeUserId
          ? await ctx.db.get(comment.assigneeUserId)
          : null;
        const resolvedBy = comment.resolvedByUserId
          ? await ctx.db.get(comment.resolvedByUserId)
          : null;
        const targetNode = await ctx.db.get(comment.targetNodeId);

        return {
          ...comment,
          author,
          assignee,
          resolvedBy,
          targetNode,
        };
      })
    );

    return commentsWithAuthors.sort((a, b) => b.createdAt - a.createdAt);
  },
});

export const listByNode = query({
  args: {
    nodeId: v.id("nodes"),
  },
  handler: async (ctx, { nodeId }) => {
    const comments = await ctx.db
      .query("comments")
      .withIndex("by_node", (q) => q.eq("targetNodeId", nodeId))
      .collect();

    const commentsWithAuthors = await Promise.all(
      comments.map(async (comment) => {
        const author = await ctx.db.get(comment.authorUserId);
        const assignee = comment.assigneeUserId
          ? await ctx.db.get(comment.assigneeUserId)
          : null;

        return {
          ...comment,
          author,
          assignee,
        };
      })
    );

    return commentsWithAuthors.sort((a, b) => b.createdAt - a.createdAt);
  },
});

export const listOrphaned = query({
  args: {
    documentId: v.id("documents"),
  },
  handler: async (ctx, { documentId }) => {
    const comments = await ctx.db
      .query("comments")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .filter((q) => q.neq(q.field("orphanedAt"), undefined))
      .collect();

    const commentsWithAuthors = await Promise.all(
      comments.map(async (comment) => {
        const author = await ctx.db.get(comment.authorUserId);
        const assignee = comment.assigneeUserId
          ? await ctx.db.get(comment.assigneeUserId)
          : null;

        return {
          ...comment,
          author,
          assignee,
        };
      })
    );

    return commentsWithAuthors.sort((a, b) => b.createdAt - a.createdAt);
  },
});

export const getById = query({
  args: { id: v.id("comments") },
  handler: async (ctx, { id }) => {
    const comment = await ctx.db.get(id);
    if (!comment) return null;

    const author = await ctx.db.get(comment.authorUserId);
    const assignee = comment.assigneeUserId
      ? await ctx.db.get(comment.assigneeUserId)
      : null;
    const resolvedBy = comment.resolvedByUserId
      ? await ctx.db.get(comment.resolvedByUserId)
      : null;
    const targetNode = await ctx.db.get(comment.targetNodeId);

    return {
      ...comment,
      author,
      assignee,
      resolvedBy,
      targetNode,
    };
  },
});

export const update = mutation({
  args: {
    id: v.id("comments"),
    body: v.optional(v.string()),
    status: v.optional(
      v.union(v.literal("open"), v.literal("resolved"), v.literal("deferred"))
    ),
    assigneeType: v.optional(v.union(v.literal("human"), v.literal("agent"))),
    assigneeUserId: v.optional(v.id("users")),
  },
  handler: async (ctx, { id, ...updates }) => {
    const filteredUpdates = Object.fromEntries(
      Object.entries(updates).filter(([, value]) => value !== undefined)
    );
    await ctx.db.patch(id, filteredUpdates);
    return id;
  },
});

export const resolve = mutation({
  args: {
    id: v.id("comments"),
    resolutionSummary: v.optional(v.string()),
  },
  handler: async (ctx, { id, resolutionSummary }) => {
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

    await ctx.db.patch(id, {
      status: "resolved",
      resolutionSummary,
      resolvedByUserId: user._id,
      resolvedAt: Date.now(),
    });

    return id;
  },
});

export const reattach = mutation({
  args: {
    id: v.id("comments"),
    newTargetNodeId: v.id("nodes"),
    rangeStart: v.optional(v.number()),
    rangeEnd: v.optional(v.number()),
  },
  handler: async (ctx, { id, newTargetNodeId, rangeStart, rangeEnd }) => {
    await ctx.db.patch(id, {
      targetNodeId: newTargetNodeId,
      rangeStart,
      rangeEnd,
      orphanedAt: undefined,
    });

    return id;
  },
});

export const assignToAgent = mutation({
  args: {
    id: v.id("comments"),
  },
  handler: async (ctx, { id }) => {
    await ctx.db.patch(id, {
      assigneeType: "agent",
      assigneeUserId: undefined,
    });

    return id;
  },
});

export const assignToUser = mutation({
  args: {
    id: v.id("comments"),
    userId: v.id("users"),
  },
  handler: async (ctx, { id, userId }) => {
    await ctx.db.patch(id, {
      assigneeType: "human",
      assigneeUserId: userId,
    });

    return id;
  },
});
