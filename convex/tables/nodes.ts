import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

const nodeTypeValidator = v.union(
  v.literal("document"),
  v.literal("heading"),
  v.literal("paragraph"),
  v.literal("bulletList"),
  v.literal("numberedList"),
  v.literal("listItem"),
  v.literal("table"),
  v.literal("tableRow"),
  v.literal("tableCell"),
  v.literal("codeBlock"),
  v.literal("image")
);

export const getById = query({
  args: { id: v.id("nodes") },
  handler: async (ctx, { id }) => {
    return await ctx.db.get(id);
  },
});

export const listByDocument = query({
  args: { documentId: v.id("documents") },
  handler: async (ctx, { documentId }) => {
    return await ctx.db
      .query("nodes")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .collect();
  },
});

export const listChildren = query({
  args: { parentId: v.id("nodes") },
  handler: async (ctx, { parentId }) => {
    return await ctx.db
      .query("nodes")
      .withIndex("by_parent_order", (q) => q.eq("parentId", parentId))
      .collect();
  },
});

export const create = mutation({
  args: {
    documentId: v.id("documents"),
    parentId: v.optional(v.id("nodes")),
    order: v.number(),
    nodeType: nodeTypeValidator,
    text: v.optional(v.string()),
    attrs: v.optional(v.any()),
  },
  handler: async (ctx, { documentId, parentId, order, nodeType, text, attrs }) => {
    const doc = await ctx.db.get(documentId);
    if (!doc) {
      throw new Error(`Document ${documentId} not found`);
    }

    return await ctx.db.insert("nodes", {
      projectId: doc.projectId,
      documentId,
      parentId,
      order,
      nodeType,
      text,
      attrs,
      createdAt: Date.now(),
    });
  },
});

export const update = mutation({
  args: {
    id: v.id("nodes"),
    text: v.optional(v.string()),
    attrs: v.optional(v.any()),
    lastEditorUserId: v.optional(v.id("users")),
    lastEditType: v.optional(v.union(v.literal("human"), v.literal("agent"))),
  },
  handler: async (ctx, { id, text, attrs, lastEditorUserId, lastEditType }) => {
    const node = await ctx.db.get(id);
    if (!node) {
      throw new Error(`Node ${id} not found`);
    }

    const updates: Record<string, unknown> = {};
    if (text !== undefined) updates.text = text;
    if (attrs !== undefined) updates.attrs = attrs;
    if (lastEditorUserId !== undefined) updates.lastEditorUserId = lastEditorUserId;
    if (lastEditType !== undefined) updates.lastEditType = lastEditType;

    if (Object.keys(updates).length > 0) {
      updates.lastEditedAt = Date.now();
      await ctx.db.patch(id, updates);
    }
  },
});

export const move = mutation({
  args: {
    nodeId: v.id("nodes"),
    newParentId: v.optional(v.id("nodes")),
    newOrder: v.number(),
  },
  handler: async (ctx, { nodeId, newParentId, newOrder }) => {
    const node = await ctx.db.get(nodeId);
    if (!node) {
      throw new Error(`Node ${nodeId} not found`);
    }

    await ctx.db.patch(nodeId, {
      parentId: newParentId,
      order: newOrder,
    });
  },
});

export const deleteNode = mutation({
  args: { nodeId: v.id("nodes") },
  handler: async (ctx, { nodeId }) => {
    const node = await ctx.db.get(nodeId);
    if (!node) {
      throw new Error(`Node ${nodeId} not found`);
    }

    await ctx.db.delete(nodeId);
  },
});

export const updateText = mutation({
  args: {
    id: v.id("nodes"),
    text: v.string(),
    editorUserId: v.id("users"),
    editType: v.union(v.literal("human"), v.literal("agent")),
  },
  handler: async (ctx, { id, text, editorUserId, editType }) => {
    const node = await ctx.db.get(id);
    if (!node) {
      throw new Error(`Node ${id} not found`);
    }

    const editor = await ctx.db.get(editorUserId);
    if (!editor) {
      throw new Error(`User ${editorUserId} not found`);
    }

    await ctx.db.patch(id, {
      text,
      lastEditorUserId: editorUserId,
      lastEditType: editType,
      lastEditedAt: Date.now(),
    });
  },
});
