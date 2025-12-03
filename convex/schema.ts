import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  documents: defineTable({
    projectId: v.id("projects"),
    title: v.string(),
    createdAt: v.number(),
    createdByUserId: v.id("users"),
    rootNodeId: v.optional(v.id("nodes")),
  })
    .index("by_project", ["projectId"])
    .index("by_project_created", ["projectId", "createdAt"]),

  nodes: defineTable({
    projectId: v.id("projects"),
    documentId: v.id("documents"),
    parentId: v.optional(v.id("nodes")),
    order: v.number(),
    nodeType: v.union(
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
    ),
    text: v.optional(v.string()),
    attrs: v.optional(v.any()),
    lastEditorUserId: v.optional(v.id("users")),
    lastEditType: v.optional(v.union(v.literal("human"), v.literal("agent"))),
    lastEditedAt: v.optional(v.number()),
    createdAt: v.number(),
  })
    .index("by_project", ["projectId"])
    .index("by_document", ["documentId"])
    .index("by_parent_order", ["parentId", "order"])
    .index("by_document_type", ["documentId", "nodeType"]),

  users: defineTable({
    email: v.string(),
    name: v.string(),
    createdAt: v.number(),
  }).index("by_email", ["email"]),

  projects: defineTable({
    ownerId: v.id("users"),
    name: v.string(),
    description: v.optional(v.string()),
    createdAt: v.number(),
    archived: v.boolean(),
  })
    .index("by_owner", ["ownerId"])
    .index("by_owner_archived", ["ownerId", "archived"]),

  projectMembers: defineTable({
    projectId: v.id("projects"),
    userId: v.id("users"),
    role: v.union(v.literal("owner"), v.literal("editor"), v.literal("viewer")),
    invitedAt: v.number(),
  })
    .index("by_project", ["projectId"])
    .index("by_user", ["userId"])
    .index("by_project_user", ["projectId", "userId"]),

  locks: defineTable({
    projectId: v.id("projects"),
    documentId: v.optional(v.id("documents")),
    nodeId: v.optional(v.id("nodes")),
    userId: v.id("users"),
    lockedAt: v.number(),
  })
    .index("by_project", ["projectId"])
    .index("by_document", ["documentId"])
    .index("by_node", ["nodeId"])
    .index("by_user", ["userId"]),

  comments: defineTable({
    projectId: v.id("projects"),
    documentId: v.id("documents"),
    targetNodeId: v.id("nodes"),
    rangeStart: v.optional(v.number()),
    rangeEnd: v.optional(v.number()),
    authorUserId: v.id("users"),
    createdAt: v.number(),
    body: v.string(),
    status: v.union(
      v.literal("open"),
      v.literal("resolved"),
      v.literal("deferred")
    ),
    assigneeType: v.optional(v.union(v.literal("human"), v.literal("agent"))),
    assigneeUserId: v.optional(v.id("users")),
    linkedNodeIds: v.optional(v.array(v.id("nodes"))),
    resolutionSummary: v.optional(v.string()),
    resolvedByUserId: v.optional(v.id("users")),
    resolvedAt: v.optional(v.number()),
    orphanedAt: v.optional(v.number()),
  })
    .index("by_project", ["projectId"])
    .index("by_document", ["documentId"])
    .index("by_node", ["targetNodeId"])
    .index("by_author", ["authorUserId"])
    .index("by_status", ["status"])
    .index("by_project_status", ["projectId", "status"])
    .index("by_document_orphaned", ["documentId", "orphanedAt"]),

  agentThreads: defineTable({
    projectId: v.id("projects"),
    documentId: v.optional(v.id("documents")),
    title: v.string(),
    createdByUserId: v.id("users"),
    createdAt: v.number(),
    status: v.union(
      v.literal("active"),
      v.literal("paused"),
      v.literal("completed")
    ),
    anchorNodeId: v.optional(v.id("nodes")),
    anchorCommentId: v.optional(v.id("comments")),
    metadata: v.optional(v.any()),
  })
    .index("by_project", ["projectId"])
    .index("by_project_status", ["projectId", "status"])
    .index("by_document", ["documentId"])
    .index("by_node", ["anchorNodeId"])
    .index("by_comment", ["anchorCommentId"]),

  agentMessages: defineTable({
    threadId: v.id("agentThreads"),
    senderType: v.union(v.literal("user"), v.literal("agent")),
    senderUserId: v.optional(v.id("users")),
    createdAt: v.number(),
    content: v.string(),
    toolCalls: v.optional(v.array(v.any())),
    appliedEditVersionId: v.optional(v.id("reportVersions")),
  })
    .index("by_thread", ["threadId"])
    .index("by_thread_created", ["threadId", "createdAt"]),

  reportVersions: defineTable({
    projectId: v.id("projects"),
    documentId: v.id("documents"),
    createdAt: v.number(),
    createdByUserId: v.id("users"),
    summary: v.string(),
    snapshot: v.any(),
  })
    .index("by_project", ["projectId"])
    .index("by_document", ["documentId"])
    .index("by_document_created", ["documentId", "createdAt"]),

  artifacts: defineTable({
    projectId: v.id("projects"),
    name: v.string(),
    description: v.optional(v.string()),
    fileType: v.string(),
    storageKey: v.string(),
    uploadedByUserId: v.id("users"),
    uploadedAt: v.number(),
  })
    .index("by_project", ["projectId"])
    .index("by_uploader", ["uploadedByUserId"]),
});
