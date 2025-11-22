import { mutation, query } from "../_generated/server";
import { v } from "convex/values";

export const createVersionSnapshot = mutation({
  args: {
    projectId: v.id("projects"),
    summary: v.optional(v.string()),
  },
  handler: async (ctx, { projectId, summary }) => {
    const userId = await ctx.auth.getUserIdentity();
    if (!userId) {
      throw new Error("Unauthorized");
    }

    const user = await ctx.db
      .query("users")
      .withIndex("by_email", (q) => q.eq("email", userId.email!))
      .first();
    if (!user) {
      throw new Error("User not found");
    }

    const sections = await ctx.db
      .query("sections")
      .withIndex("by_project_order", (q) => q.eq("projectId", projectId))
      .collect();

    const snapshotSections = [];
    for (const section of sections) {
      const blocks = await ctx.db
        .query("blocks")
        .withIndex("by_section_order", (q) => q.eq("sectionId", section._id))
        .collect();

      snapshotSections.push({
        sectionId: section._id,
        headingText: section.headingText,
        headingLevel: section.headingLevel,
        order: section.order,
        blocks: blocks.map((block) => ({
          blockId: block._id,
          blockType: block.blockType,
          order: block.order,
          markdownText: block.markdownText,
        })),
      });
    }

    const snapshot = { sections: snapshotSections };

    const versionId = await ctx.db.insert("reportVersions", {
      projectId,
      createdByUserId: user._id,
      summary: summary ?? "Auto-saved version",
      snapshot,
      createdAt: Date.now(),
    });

    return versionId;
  },
});

export const restoreVersion = mutation({
  args: { versionId: v.id("reportVersions") },
  handler: async (ctx, { versionId }) => {
    const userId = await ctx.auth.getUserIdentity();
    if (!userId) {
      throw new Error("Unauthorized");
    }

    const user = await ctx.db
      .query("users")
      .withIndex("by_email", (q) => q.eq("email", userId.email!))
      .first();
    if (!user) {
      throw new Error("User not found");
    }

    const version = await ctx.db.get(versionId);
    if (!version) {
      throw new Error(`Version ${versionId} not found`);
    }

    const projectId = version.projectId;

    const currentSections = await ctx.db
      .query("sections")
      .withIndex("by_project_order", (q) => q.eq("projectId", projectId))
      .collect();

    const currentSnapshot = [];
    for (const section of currentSections) {
      const blocks = await ctx.db
        .query("blocks")
        .withIndex("by_section_order", (q) => q.eq("sectionId", section._id))
        .collect();

      currentSnapshot.push({
        sectionId: section._id,
        headingText: section.headingText,
        headingLevel: section.headingLevel,
        order: section.order,
        blocks: blocks.map((block) => ({
          blockId: block._id,
          blockType: block.blockType,
          order: block.order,
          markdownText: block.markdownText,
        })),
      });
    }

    for (const section of currentSections) {
      const blocks = await ctx.db
        .query("blocks")
        .withIndex("by_section", (q) => q.eq("sectionId", section._id))
        .collect();
      for (const block of blocks) {
        await ctx.db.delete(block._id);
      }
      await ctx.db.delete(section._id);
    }

    const snapshot = version.snapshot as {
      sections: Array<{
        sectionId: string;
        headingText: string;
        headingLevel: number;
        order: number;
        blocks: Array<{
          blockId: string;
          blockType: string;
          order: number;
          markdownText: string;
        }>;
      }>;
    };

    for (const snapshotSection of snapshot.sections) {
      const newSectionId = await ctx.db.insert("sections", {
        projectId,
        headingText: snapshotSection.headingText,
        headingLevel: snapshotSection.headingLevel,
        order: snapshotSection.order,
        createdAt: Date.now(),
      });

      for (const snapshotBlock of snapshotSection.blocks) {
        await ctx.db.insert("blocks", {
          projectId,
          sectionId: newSectionId,
          order: snapshotBlock.order,
          blockType: snapshotBlock.blockType as any,
          markdownText: snapshotBlock.markdownText,
          lastEditorUserId: user._id,
          lastEditType: "human",
          lastEditedAt: Date.now(),
        });
      }
    }

    const restoreDate = new Date(version.createdAt).toISOString();
    const newVersionId = await ctx.db.insert("reportVersions", {
      projectId,
      createdByUserId: user._id,
      summary: `Restored from version ${restoreDate}`,
      snapshot: { sections: currentSnapshot },
      createdAt: Date.now(),
    });

    return newVersionId;
  },
});

export const compareVersions = query({
  args: {
    versionIdA: v.id("reportVersions"),
    versionIdB: v.id("reportVersions"),
  },
  handler: async (ctx, { versionIdA, versionIdB }) => {
    const versionA = await ctx.db.get(versionIdA);
    const versionB = await ctx.db.get(versionIdB);

    if (!versionA || !versionB) {
      throw new Error("One or both versions not found");
    }

    const snapshotA = versionA.snapshot as {
      sections: Array<{
        sectionId: string;
        headingText: string;
        headingLevel: number;
        order: number;
        blocks: Array<{
          blockId: string;
          blockType: string;
          order: number;
          markdownText: string;
        }>;
      }>;
    };

    const snapshotB = versionB.snapshot as {
      sections: Array<{
        sectionId: string;
        headingText: string;
        headingLevel: number;
        order: number;
        blocks: Array<{
          blockId: string;
          blockType: string;
          order: number;
          markdownText: string;
        }>;
      }>;
    };

    const blocksA = new Map<string, any>();
    const blocksB = new Map<string, any>();

    for (const section of snapshotA.sections) {
      for (const block of section.blocks) {
        blocksA.set(block.blockId, { ...block, sectionId: section.sectionId });
      }
    }

    for (const section of snapshotB.sections) {
      for (const block of section.blocks) {
        blocksB.set(block.blockId, { ...block, sectionId: section.sectionId });
      }
    }

    const differences = [];

    for (const [blockId, blockA] of blocksA) {
      const blockB = blocksB.get(blockId);
      if (!blockB) {
        differences.push({
          type: "removed",
          blockId,
          block: blockA,
        });
      } else if (blockA.markdownText !== blockB.markdownText) {
        differences.push({
          type: "modified",
          blockId,
          oldBlock: blockA,
          newBlock: blockB,
        });
      }
    }

    for (const [blockId, blockB] of blocksB) {
      if (!blocksA.has(blockId)) {
        differences.push({
          type: "added",
          blockId,
          block: blockB,
        });
      }
    }

    return differences;
  },
});
