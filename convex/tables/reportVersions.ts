import { query, mutation } from "../_generated/server";
import { v } from "convex/values";
import { Id } from "../_generated/dataModel";

type SnapshotNode = {
  nodeId: string;
  parentId: string | null;
  order: number;
  nodeType: string;
  text?: string;
  attrs?: unknown;
};

type DocumentSnapshot = {
  rootNodeId: string;
  nodes: SnapshotNode[];
};

export const getById = query({
  args: { id: v.id("reportVersions") },
  handler: async (ctx, { id }) => {
    return await ctx.db.get(id);
  },
});

export const listByDocument = query({
  args: { documentId: v.id("documents") },
  handler: async (ctx, { documentId }) => {
    return await ctx.db
      .query("reportVersions")
      .withIndex("by_document_created", (q) => q.eq("documentId", documentId))
      .order("desc")
      .collect();
  },
});

export const createVersion = mutation({
  args: {
    documentId: v.id("documents"),
    userId: v.id("users"),
    summary: v.string(),
  },
  handler: async (ctx, { documentId, userId, summary }) => {
    const document = await ctx.db.get(documentId);
    if (!document) {
      throw new Error(`Document ${documentId} not found`);
    }

    const user = await ctx.db.get(userId);
    if (!user) {
      throw new Error(`User ${userId} not found`);
    }

    const nodes = await ctx.db
      .query("nodes")
      .withIndex("by_document", (q) => q.eq("documentId", documentId))
      .collect();

    const snapshotNodes: SnapshotNode[] = nodes.map((node) => ({
      nodeId: node._id as string,
      parentId: node.parentId ? (node.parentId as string) : null,
      order: node.order,
      nodeType: node.nodeType,
      text: node.text,
      attrs: node.attrs,
    }));

    const snapshot: DocumentSnapshot = {
      rootNodeId: document.rootNodeId as string,
      nodes: snapshotNodes,
    };

    return await ctx.db.insert("reportVersions", {
      projectId: document.projectId,
      documentId,
      createdByUserId: userId,
      summary,
      snapshot,
      createdAt: Date.now(),
    });
  },
});

export const restoreVersion = mutation({
  args: { versionId: v.id("reportVersions") },
  handler: async (ctx, { versionId }) => {
    const version = await ctx.db.get(versionId);
    if (!version) {
      throw new Error(`Version ${versionId} not found`);
    }

    const document = await ctx.db.get(version.documentId);
    if (!document) {
      throw new Error(`Document ${version.documentId} not found`);
    }

    const snapshot = version.snapshot as DocumentSnapshot;

    const currentNodes = await ctx.db
      .query("nodes")
      .withIndex("by_document", (q) => q.eq("documentId", version.documentId))
      .collect();

    for (const node of currentNodes) {
      await ctx.db.delete(node._id);
    }

    const idMap = new Map<string, Id<"nodes">>();

    for (const snapshotNode of snapshot.nodes) {
      const newId = await ctx.db.insert("nodes", {
        projectId: document.projectId,
        documentId: version.documentId,
        parentId: undefined,
        order: snapshotNode.order,
        nodeType: snapshotNode.nodeType as
          | "document"
          | "heading"
          | "paragraph"
          | "bulletList"
          | "numberedList"
          | "listItem"
          | "table"
          | "tableRow"
          | "tableCell"
          | "codeBlock"
          | "image",
        text: snapshotNode.text,
        attrs: snapshotNode.attrs,
        createdAt: Date.now(),
      });
      idMap.set(snapshotNode.nodeId, newId);
    }

    for (const snapshotNode of snapshot.nodes) {
      if (snapshotNode.parentId) {
        const newId = idMap.get(snapshotNode.nodeId);
        const newParentId = idMap.get(snapshotNode.parentId);
        if (newId && newParentId) {
          await ctx.db.patch(newId, { parentId: newParentId });
        }
      }
    }

    const newRootId = idMap.get(snapshot.rootNodeId);
    if (newRootId) {
      await ctx.db.patch(document._id, { rootNodeId: newRootId });
    }

    return { restoredNodeCount: snapshot.nodes.length };
  },
});
