import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
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

  sections: defineTable({
    projectId: v.id("projects"),
    headingText: v.string(),
    headingLevel: v.number(),
    order: v.number(),
    createdAt: v.number(),
  })
    .index("by_project", ["projectId"])
    .index("by_project_order", ["projectId", "order"]),

  blocks: defineTable({
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
    lastEditorUserId: v.id("users"),
    lastEditType: v.union(v.literal("human"), v.literal("agent")),
    lastEditedAt: v.number(),
  })
    .index("by_project", ["projectId"])
    .index("by_section", ["sectionId"])
    .index("by_section_order", ["sectionId", "order"]),

  locks: defineTable({
    projectId: v.id("projects"),
    resourceType: v.union(
      v.literal("section"),
      v.literal("block"),
      v.literal("thread")
    ),
    resourceId: v.string(),
    userId: v.id("users"),
    lockedAt: v.number(),
  })
    .index("by_project", ["projectId"])
    .index("by_resource", ["resourceType", "resourceId"])
    .index("by_user", ["userId"]),

  comments: defineTable({
    projectId: v.id("projects"),
    sectionId: v.optional(v.id("sections")),
    blockId: v.optional(v.id("blocks")),
    authorUserId: v.id("users"),
    createdAt: v.number(),
    body: v.string(),
    status: v.union(
      v.literal("open"),
      v.literal("resolved"),
      v.literal("deferred")
    ),
    assigneeType: v.optional(
      v.union(v.literal("human"), v.literal("agent"))
    ),
    assigneeUserId: v.optional(v.id("users")),
    linkedSections: v.optional(v.array(v.id("sections"))),
    resolutionSummary: v.optional(v.string()),
    resolvedByUserId: v.optional(v.id("users")),
    resolvedAt: v.optional(v.number()),
  })
    .index("by_project", ["projectId"])
    .index("by_section", ["sectionId"])
    .index("by_block", ["blockId"])
    .index("by_author", ["authorUserId"])
    .index("by_status", ["status"])
    .index("by_project_status", ["projectId", "status"]),

  agentThreads: defineTable({
    projectId: v.id("projects"),
    title: v.string(),
    createdByUserId: v.id("users"),
    createdAt: v.number(),
    status: v.union(
      v.literal("active"),
      v.literal("paused"),
      v.literal("completed")
    ),
    anchorSectionId: v.optional(v.id("sections")),
    anchorCommentId: v.optional(v.id("comments")),
    metadata: v.optional(v.any()),
  })
    .index("by_project", ["projectId"])
    .index("by_project_status", ["projectId", "status"])
    .index("by_section", ["anchorSectionId"])
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
    createdAt: v.number(),
    createdByUserId: v.id("users"),
    summary: v.string(),
    snapshot: v.any(),
  })
    .index("by_project", ["projectId"])
    .index("by_project_created", ["projectId", "createdAt"]),

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
