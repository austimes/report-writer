import { query, mutation } from "../_generated/server";
import { v } from "convex/values";

export const getById = query({
  args: { id: v.id("blocks") },
  handler: async (ctx, { id }) => {
    return await ctx.db.get(id);
  },
});

export const listBySection = query({
  args: { sectionId: v.id("sections") },
  handler: async (ctx, { sectionId }) => {
    return await ctx.db
      .query("blocks")
      .withIndex("by_section_order", (q) => q.eq("sectionId", sectionId))
      .collect();
  },
});

export const listByProject = query({
  args: { projectId: v.id("projects") },
  handler: async (ctx, { projectId }) => {
    return await ctx.db
      .query("blocks")
      .withIndex("by_project", (q) => q.eq("projectId", projectId))
      .collect();
  },
});

export const create = mutation({
  args: {
    projectId: v.id("projects"),
    sectionId: v.id("sections"),
    order: v.number(),
    blockType: v.union(
      v.literal("paragraph"),
      v.literal("bulletList"),
      v.literal("numberedList"),
      v.literal("table"),
      v.literal("image"),
      v.literal("codeBlock")
    ),
    markdownText: v.string(),
  },
  handler: async (
    ctx,
    { projectId, sectionId, order, blockType, markdownText }
  ) => {
    const project = await ctx.db.get(projectId);
    if (!project) {
      throw new Error(`Project ${projectId} not found`);
    }

    const section = await ctx.db.get(sectionId);
    if (!section) {
      throw new Error(`Section ${sectionId} not found`);
    }
    if (section.projectId !== projectId) {
      throw new Error(`Section ${sectionId} does not belong to project ${projectId}`);
    }

    return await ctx.db.insert("blocks", {
      projectId,
      sectionId,
      order,
      blockType,
      markdownText,
      lastEditorUserId: project.ownerId,
      lastEditType: "human",
      lastEditedAt: Date.now(),
    });
  },
});

export const updateText = mutation({
  args: {
    id: v.id("blocks"),
    markdownText: v.string(),
    editorUserId: v.id("users"),
    editType: v.union(v.literal("human"), v.literal("agent")),
  },
  handler: async (ctx, { id, markdownText, editorUserId, editType }) => {
    const block = await ctx.db.get(id);
    if (!block) {
      throw new Error(`Block ${id} not found`);
    }

    const editor = await ctx.db.get(editorUserId);
    if (!editor) {
      throw new Error(`User ${editorUserId} not found`);
    }

    await ctx.db.patch(id, {
      markdownText,
      lastEditorUserId: editorUserId,
      lastEditType: editType,
      lastEditedAt: Date.now(),
    });
  },
});

export const deleteBlock = mutation({
  args: { id: v.id("blocks") },
  handler: async (ctx, { id }) => {
    const block = await ctx.db.get(id);
    if (!block) {
      throw new Error(`Block ${id} not found`);
    }

    await ctx.db.delete(id);
  },
});

export const reorder = mutation({
  args: {
    sectionId: v.id("sections"),
    newOrder: v.array(v.object({ id: v.id("blocks"), order: v.number() })),
  },
  handler: async (ctx, { sectionId, newOrder }) => {
    const section = await ctx.db.get(sectionId);
    if (!section) {
      throw new Error(`Section ${sectionId} not found`);
    }

    for (const { id, order } of newOrder) {
      const block = await ctx.db.get(id);
      if (!block) {
        throw new Error(`Block ${id} not found`);
      }
      if (block.sectionId !== sectionId) {
        throw new Error(`Block ${id} does not belong to section ${sectionId}`);
      }
      await ctx.db.patch(id, { order });
    }
  },
});

export const bulkUpdate = mutation({
  args: {
    updates: v.array(
      v.object({
        id: v.id("blocks"),
        markdownText: v.string(),
      })
    ),
  },
  handler: async (ctx, { updates }) => {
    for (const { id, markdownText } of updates) {
      const block = await ctx.db.get(id);
      if (!block) {
        throw new Error(`Block ${id} not found`);
      }
      await ctx.db.patch(id, {
        markdownText,
        lastEditedAt: Date.now(),
      });
    }
  },
});
