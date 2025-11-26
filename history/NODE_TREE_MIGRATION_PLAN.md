# Node Tree Architecture Migration Plan

**Date:** 2025-01-27  
**Status:** Planning  
**Goal:** Replace the current sections/blocks model with a unified node tree that provides stable identity for collaborative editing and commenting.

---

## Executive Summary

We're replacing the current `sections` + `blocks` tables with a unified `nodes` table where **everything is a node**, including the document root. This gives us:

- **Stable identity**: Convex `_id` is the node identity (no separate UUID needed)
- **Clean tree structure**: `parentId` adjacency list, simple `order` for siblings
- **Robust commenting**: Comments point to `targetNodeId` + optional character ranges
- **Structural edit resilience**: Rename, move, reorder operations preserve node identity

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         projects                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         documents                            │
│  - projectId                                                 │
│  - title                                                     │
│  - rootNodeId ──────────────────────────────────────────┐   │
└─────────────────────────────────────────────────────────────┘
                                                          │
                              ┌────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                          nodes                               │
│  - _id (Convex ID = stable node identity)                   │
│  - projectId, documentId                                     │
│  - parentId (null for root)                                  │
│  - order (sibling ordering)                                  │
│  - nodeType (document|heading|paragraph|list|...)           │
│  - text (content)                                            │
│  - attrs (level, language, src, etc.)                       │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│        comments          │    │          locks           │
│  - targetNodeId ─────────┼────│  - nodeId ───────────────│
│  - rangeStart/End        │    │  - userId                │
│  - body, status          │    │  - lockedAt              │
└──────────────────────────┘    └──────────────────────────┘
```

---

## Why Convex `_id` as Node Identity (No Separate UUID)

For this prototype, Convex's auto-generated `_id` is sufficient because:

1. **Stable lifetime**: `_id` never changes for a row
2. **Single table**: All nodes live in one `nodes` table
3. **No offline-first**: We don't need client-generated IDs before server roundtrip
4. **No cross-system sync**: Nodes don't move between databases

A separate `nodeId` UUID would only be needed for:
- Offline-first with client-generated IDs
- Cross-table or cross-database identity
- CRDT-style concurrent editing

---

## Phase 1: New Schema

### 1.1 Documents Table (NEW)

```typescript
documents: defineTable({
  projectId: v.id("projects"),
  title: v.string(),
  createdAt: v.number(),
  createdByUserId: v.id("users"),
  rootNodeId: v.id("nodes"),
})
  .index("by_project", ["projectId"])
  .index("by_project_created", ["projectId", "createdAt"]),
```

### 1.2 Nodes Table (REPLACES sections + blocks)

```typescript
nodes: defineTable({
  projectId: v.id("projects"),
  documentId: v.id("documents"),

  // Tree structure
  parentId: v.optional(v.id("nodes")), // null/undefined only for document root
  order: v.number(), // sibling ordering within parent

  // Node type
  nodeType: v.union(
    v.literal("document"),      // Root node
    v.literal("heading"),       // h1-h6
    v.literal("paragraph"),     // Text block
    v.literal("bulletList"),    // Unordered list container
    v.literal("numberedList"),  // Ordered list container
    v.literal("listItem"),      // List item
    v.literal("table"),         // Table container
    v.literal("tableRow"),      // Table row
    v.literal("tableCell"),     // Table cell
    v.literal("codeBlock"),     // Code block
    v.literal("image")          // Image
  ),

  // Content
  text: v.optional(v.string()), // Markdown text content

  // Type-specific attributes
  attrs: v.optional(v.any()),
  // Examples:
  //   heading: { level: 1 | 2 | 3 | 4 | 5 | 6 }
  //   codeBlock: { language: "typescript" }
  //   image: { src: "...", alt: "..." }

  // Edit tracking
  lastEditorUserId: v.optional(v.id("users")),
  lastEditType: v.optional(v.union(v.literal("human"), v.literal("agent"))),
  lastEditedAt: v.optional(v.number()),

  createdAt: v.number(),
})
  .index("by_project", ["projectId"])
  .index("by_document", ["documentId"])
  .index("by_parent_order", ["parentId", "order"])
  .index("by_document_type", ["documentId", "nodeType"]),
```

### 1.3 Comments Table (UPDATED)

```typescript
comments: defineTable({
  projectId: v.id("projects"),
  documentId: v.id("documents"),

  // Node anchor - the stable identity
  targetNodeId: v.id("nodes"),

  // Optional text range within node (character offsets)
  rangeStart: v.optional(v.number()),
  rangeEnd: v.optional(v.number()),

  // Comment data
  authorUserId: v.id("users"),
  createdAt: v.number(),
  body: v.string(),
  status: v.union(
    v.literal("open"),
    v.literal("resolved"),
    v.literal("deferred")
  ),

  // Assignment
  assigneeType: v.optional(v.union(v.literal("human"), v.literal("agent"))),
  assigneeUserId: v.optional(v.id("users")),

  // Multi-node links (for comments spanning multiple nodes)
  linkedNodeIds: v.optional(v.array(v.id("nodes"))),

  // Resolution
  resolutionSummary: v.optional(v.string()),
  resolvedByUserId: v.optional(v.id("users")),
  resolvedAt: v.optional(v.number()),

  // Orphan tracking (set when target node is deleted)
  orphanedAt: v.optional(v.number()),
})
  .index("by_project", ["projectId"])
  .index("by_document", ["documentId"])
  .index("by_node", ["targetNodeId"])
  .index("by_author", ["authorUserId"])
  .index("by_status", ["status"])
  .index("by_project_status", ["projectId", "status"])
  .index("by_document_orphaned", ["documentId", "orphanedAt"]),
```

### 1.4 Locks Table (SIMPLIFIED)

```typescript
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
```

### 1.5 Agent Threads (UPDATED)

```typescript
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

  // Anchors
  anchorNodeId: v.optional(v.id("nodes")),
  anchorCommentId: v.optional(v.id("comments")),

  metadata: v.optional(v.any()),
})
  .index("by_project", ["projectId"])
  .index("by_project_status", ["projectId", "status"])
  .index("by_document", ["documentId"])
  .index("by_node", ["anchorNodeId"])
  .index("by_comment", ["anchorCommentId"]),
```

### 1.6 Report Versions (UPDATED)

```typescript
reportVersions: defineTable({
  projectId: v.id("projects"),
  documentId: v.id("documents"),

  createdAt: v.number(),
  createdByUserId: v.id("users"),
  summary: v.string(),

  // Snapshot of the full node tree
  snapshot: v.any(),
})
  .index("by_project", ["projectId"])
  .index("by_document", ["documentId"])
  .index("by_document_created", ["documentId", "createdAt"]),
```

---

## Phase 2: Backend Implementation

### 2.1 New Convex Functions Structure

```
convex/
├── tables/
│   ├── documents.ts      # NEW: Document CRUD
│   ├── nodes.ts          # NEW: Node tree operations
│   ├── comments.ts       # REWRITE: Node-based anchoring
│   ├── locks.ts          # REWRITE: Node-based locking
│   └── ...
├── features/
│   ├── documentTree.ts   # NEW: Tree traversal, subtree operations
│   ├── nodeOperations.ts # NEW: Insert, move, delete with comment handling
│   └── ...
└── schema.ts             # REPLACE: New schema
```

### 2.2 Core Node Operations

```typescript
// convex/tables/nodes.ts

// Create a node
export const create = mutation({
  args: {
    documentId: v.id("documents"),
    parentId: v.optional(v.id("nodes")),
    order: v.number(),
    nodeType: v.union(...),
    text: v.optional(v.string()),
    attrs: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const doc = await ctx.db.get(args.documentId);
    if (!doc) throw new Error("Document not found");

    return await ctx.db.insert("nodes", {
      projectId: doc.projectId,
      documentId: args.documentId,
      parentId: args.parentId,
      order: args.order,
      nodeType: args.nodeType,
      text: args.text,
      attrs: args.attrs,
      createdAt: Date.now(),
    });
  },
});

// Move a node (change parent and/or order)
export const move = mutation({
  args: {
    nodeId: v.id("nodes"),
    newParentId: v.optional(v.id("nodes")),
    newOrder: v.number(),
  },
  handler: async (ctx, { nodeId, newParentId, newOrder }) => {
    // Node identity (nodeId) stays the same
    // Comments automatically follow because they reference nodeId
    await ctx.db.patch(nodeId, {
      parentId: newParentId,
      order: newOrder,
    });
  },
});

// Delete a node (orphans comments)
export const deleteNode = mutation({
  args: { nodeId: v.id("nodes") },
  handler: async (ctx, { nodeId }) => {
    const node = await ctx.db.get(nodeId);
    if (!node) throw new Error("Node not found");

    const now = Date.now();

    // Orphan all comments pointing to this node
    const comments = await ctx.db
      .query("comments")
      .withIndex("by_node", (q) => q.eq("targetNodeId", nodeId))
      .collect();

    for (const comment of comments) {
      await ctx.db.patch(comment._id, { orphanedAt: now });
    }

    // Recursively delete children (and orphan their comments too)
    const children = await ctx.db
      .query("nodes")
      .withIndex("by_parent_order", (q) => q.eq("parentId", nodeId))
      .collect();

    for (const child of children) {
      await deleteNode(ctx, { nodeId: child._id });
    }

    await ctx.db.delete(nodeId);
  },
});
```

### 2.3 Document Creation with Root Node

```typescript
// convex/tables/documents.ts

export const create = mutation({
  args: {
    projectId: v.id("projects"),
    title: v.string(),
    userId: v.id("users"),
  },
  handler: async (ctx, { projectId, title, userId }) => {
    // Create root node first (with temporary documentId)
    const rootNodeId = await ctx.db.insert("nodes", {
      projectId,
      documentId: "" as any, // Will be patched
      parentId: undefined,
      order: 0,
      nodeType: "document",
      text: undefined,
      attrs: { title },
      createdAt: Date.now(),
    });

    // Create document pointing to root
    const documentId = await ctx.db.insert("documents", {
      projectId,
      title,
      createdAt: Date.now(),
      createdByUserId: userId,
      rootNodeId,
    });

    // Patch root node with correct documentId
    await ctx.db.patch(rootNodeId, { documentId });

    return documentId;
  },
});
```

---

## Phase 3: Frontend Implementation

### 3.1 Updated Section Parser

The frontend parser should now:
1. Parse markdown into AST (unchanged)
2. Map AST nodes to Convex node IDs (new)
3. Track ranges for comment highlighting (new)

```typescript
// apps/web/src/features/editor/utils/nodeTreeParser.ts

export interface NodeTreeEntry {
  convexId: Id<"nodes">;     // Stable identity from Convex
  nodeType: NodeType;
  text?: string;
  attrs?: Record<string, any>;
  children: NodeTreeEntry[];
  
  // For rendering and comment positioning
  startOffset: number;
  endOffset: number;
}

// Build tree from Convex nodes
export function buildNodeTree(nodes: Doc<"nodes">[]): NodeTreeEntry {
  const nodeMap = new Map(nodes.map(n => [n._id, n]));
  const root = nodes.find(n => n.nodeType === "document");
  if (!root) throw new Error("No root node");
  
  function buildChildren(parentId: Id<"nodes">): NodeTreeEntry[] {
    return nodes
      .filter(n => n.parentId === parentId)
      .sort((a, b) => a.order - b.order)
      .map(n => ({
        convexId: n._id,
        nodeType: n.nodeType,
        text: n.text,
        attrs: n.attrs,
        children: buildChildren(n._id),
        startOffset: 0, // Computed during render
        endOffset: 0,
      }));
  }
  
  return {
    convexId: root._id,
    nodeType: "document",
    attrs: root.attrs,
    children: buildChildren(root._id),
    startOffset: 0,
    endOffset: 0,
  };
}
```

### 3.2 Comment Anchoring

```typescript
// apps/web/src/features/comments/hooks/useComments.ts

export function useCommentsForNode(nodeId: Id<"nodes">) {
  return useQuery(api.comments.listByNode, { nodeId });
}

export function useOrphanedComments(documentId: Id<"documents">) {
  return useQuery(api.comments.listOrphaned, { documentId });
}
```

---

## Phase 4: Delete Old Code

### Tables to DELETE:
- `convex/tables/sections.ts`
- `convex/tables/blocks.ts`

### Schema entries to REMOVE:
- `sections` table definition
- `blocks` table definition

### Frontend files to REWRITE:
- `apps/web/src/features/editor/utils/sectionParser.ts` → `nodeTreeParser.ts`
- `apps/web/src/features/editor/utils/markdownParser.ts` → integrate with node tree
- `apps/web/src/features/editor/components/SectionsList.tsx` → `NodeTree.tsx`

---

## Comment System Behavior

### Structural Edits

| Operation | Comment Behavior |
|-----------|------------------|
| Rename node (edit text) | Comments stay (same nodeId) |
| Move node | Comments follow (same nodeId) |
| Reorder siblings | Comments stay (same nodeId) |
| Delete node | Comments orphaned (`orphanedAt` set) |
| Move subtree | All comments in subtree follow |

### Orphaned Comments View

```typescript
// Query orphaned comments for a document
export const listOrphaned = query({
  args: { documentId: v.id("documents") },
  handler: async (ctx, { documentId }) => {
    return await ctx.db
      .query("comments")
      .withIndex("by_document_orphaned", (q) => 
        q.eq("documentId", documentId)
      )
      .filter((q) => q.neq(q.field("orphanedAt"), undefined))
      .collect();
  },
});
```

### Re-attachment

```typescript
export const reattach = mutation({
  args: {
    commentId: v.id("comments"),
    newTargetNodeId: v.id("nodes"),
    rangeStart: v.optional(v.number()),
    rangeEnd: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    await ctx.db.patch(args.commentId, {
      targetNodeId: args.newTargetNodeId,
      rangeStart: args.rangeStart,
      rangeEnd: args.rangeEnd,
      orphanedAt: undefined, // Clear orphan status
    });
  },
});
```

---

## Implementation Order

### Week 1: Foundation
1. [ ] Create new schema in `convex/schema.ts`
2. [ ] Implement `documents` table functions
3. [ ] Implement `nodes` table with core CRUD
4. [ ] Implement tree traversal utilities

### Week 2: Comments & Locks
5. [ ] Rewrite `comments` table for node anchoring
6. [ ] Implement orphan handling on node deletion
7. [ ] Rewrite `locks` table for node-based locking
8. [ ] Update `agentThreads` for node anchoring

### Week 3: Frontend
9. [ ] Create `nodeTreeParser.ts`
10. [ ] Rewrite editor to use node tree
11. [ ] Implement comment display with range highlighting
12. [ ] Build orphaned comments view

### Week 4: Cleanup
13. [ ] Delete old sections/blocks code
14. [ ] Update all tests
15. [ ] Update documentation

---

## Resolved Questions

### Q1: Markdown Serialization → Option B (Derive from Structure)

**Decision:** Node tree is canonical. Derive markdown from `nodeType + attrs + text`.

**Convention:**
- `text` field = **inline markdown only** (bold, links, emphasis)
- Block-level syntax (`##`, `-`, ``` ``` ```) derived from `nodeType + attrs`

**Examples:**
| Node | attrs | text | → Markdown |
|------|-------|------|------------|
| heading | `{ level: 2 }` | `"Foo *bar*"` | `## Foo *bar*\n\n` |
| paragraph | — | `"Some [link](url)"` | `Some [link](url)\n\n` |
| codeBlock | `{ language: "ts" }` | `"const x = 1"` | ``` ```ts\nconst x = 1\n``` ``` |
| bulletList | — | — | (children are listItems) |
| listItem | — | `"Item text"` | `- Item text\n` |

**Serializer:** Single `serializeNode(node)` function that walks tree and emits markdown.

**Trade-off:** Won't preserve original formatting quirks (exact whitespace, `-` vs `*`). Acceptable for prototype.

---

### Q2: Collaborative Cursors → Defer (Not Needed Now)

**Decision:** Don't implement cursor tracking now. We have exclusive locks.

**Future design (when we drop locks):**

```typescript
cursorPresence: defineTable({
  documentId: v.id("documents"),
  userId: v.id("users"),
  nodeId: v.optional(v.id("nodes")),
  rangeStart: v.optional(v.number()),  // Same coords as comments
  rangeEnd: v.optional(v.number()),
  updatedAt: v.number(),
})
  .index("by_document", ["documentId"])
  .index("by_document_user", ["documentId", "userId"]),
```

**Key insight:** Cursor offsets use same coordinate system as comment ranges (node.text character positions), so design is already aligned.

---

### Q3: Version Snapshots → Option A (Full Tree Snapshot)

**Decision:** Store complete node tree per version. Simple and self-contained.

**Snapshot shape:**

```typescript
type SnapshotNode = {
  nodeId: string;           // Original Convex _id as string
  parentId: string | null;  // Original parentId
  order: number;
  nodeType: NodeType;
  text?: string;
  attrs?: Record<string, any>;
};

type DocumentSnapshot = {
  rootNodeId: string;
  nodes: SnapshotNode[];    // Adjacency list
};
```

**Create:** Query all nodes for document, serialize to `DocumentSnapshot`.

**Restore:** Delete current nodes, re-insert from snapshot with new `_id`s.

**Diff/Compare:** Load two snapshots, compare by original `nodeId` to find changes.

**Trade-off:** 
- Storage is O(nodes × versions) - fine for prototype
- Restore creates fresh `_id`s, so comments may orphan. Acceptable for now.

**Future optimization (if needed):** Keep full snapshots every N versions, store diffs in between.

---

## References

- [comment_system_design.txt](../docs/comment_system_design.txt) - Original design principles
- [Convex Schema Docs](https://docs.convex.dev/database/schemas)
