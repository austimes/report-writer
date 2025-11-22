# Data Model

This document explains the Convex database schema and storage design decisions.

## Schema Overview

The application uses **Convex** as its database, which stores data as documents in tables with indexes. All tables are defined in `convex/schema.ts`.

## Tables

### `users`

Stores user accounts.

```typescript
{
  _id: string;           // Auto-generated
  email: string;         // Unique
  name: string;          // Display name
  createdAt: number;     // Unix timestamp
}
```

**Indexes:**
- `by_email`: Fast lookup by email

**Access patterns:**
- Find user by email during authentication
- Populate user names in UI (editors, lock holders)

---

### `projects`

One project per collaborative report.

```typescript
{
  _id: string;
  ownerId: string;       // Reference to users._id
  name: string;
  description?: string;
  createdAt: number;
  archived: boolean;     // Soft delete
}
```

**Indexes:**
- `by_owner`: List projects owned by a user
- `by_archived`: Filter active vs archived

**Access patterns:**
- List all projects for a user (via projectMembers join)
- Load project details for editing

---

### `projectMembers`

Many-to-many relationship between users and projects.

```typescript
{
  _id: string;
  projectId: string;
  userId: string;
  role: 'owner' | 'editor';
  invitedAt: number;
}
```

**Indexes:**
- `by_project`: List all members of a project
- `by_user`: List all projects a user belongs to
- Compound: `(projectId, userId)` for membership check

**Access patterns:**
- Check if user has access to project
- List collaborators for UI

---

### `sections`

Top-level organizational units, corresponding to Markdown headings.

```typescript
{
  _id: string;
  projectId: string;
  headingText: string;   // "Introduction", "Methods", etc.
  headingLevel: number;  // 1-6 (# to ######)
  order: number;         // For sorting
  createdAt: number;
}
```

**Indexes:**
- `by_project`: Load all sections for a project
- `by_order`: Sort sections by position

**Access patterns:**
- Load entire document structure (sections + blocks)
- Navigate to specific section
- Reorder sections (drag-and-drop)

**Rationale:**
- Sections are natural units for navigation and locking
- Heading text and level stored separately for flexibility (rendering table of contents, changing heading levels)

---

### `blocks`

Smallest tracked text units. All content lives in blocks.

```typescript
{
  _id: string;
  projectId: string;
  sectionId: string;
  order: number;                    // Position within section
  blockType: 'paragraph' | 'list_item' | 'heading' | 'table_row' | 'code_block' | 'other';
  markdownText: string;             // Raw markdown content
  lastEditorUserId?: string;        // Who edited this block last
  lastEditType?: 'manual' | 'agent';
  lastEditedAt?: number;
}
```

**Indexes:**
- `by_section`: Load all blocks in a section
- `by_project`: Load all blocks for version snapshots

**Access patterns:**
- Load section content for editing
- Update individual block on edit
- Track attribution (who edited what, human vs agent)

**Rationale for block-based storage:**

1. **Granular tracking**: Attribution and history at block level, not word level
2. **Reasonable sync size**: Blocks are small enough for efficient updates, large enough to avoid excessive overhead
3. **Diff-friendly**: Block boundaries make diffs more readable
4. **Storage efficiency**: Plain text in each block, no CRDT metadata

**Why not CRDT?**
- CRDTs (Conflict-free Replicated Data Types) enable lock-free multi-cursor editing
- But they add complexity: more storage, harder reasoning, potential performance issues
- Our lock-based approach is simpler and fits the report-writing use case (typically one editor per section at a time)

**Word-level diffs:**
- Diffs are computed in memory (client or sandbox) by comparing `markdownText` strings
- Not stored at word level in database
- Displayed for agent proposals and version comparisons

---

### `locks`

Generic locking mechanism for sections, blocks, and threads.

```typescript
{
  _id: string;
  projectId: string;
  resourceType: 'section' | 'block' | 'thread';
  resourceId: string;    // ID of section/block/thread
  userId: string;        // Who holds the lock
  lockedAt: number;      // When acquired
}
```

**Indexes:**
- Unique compound: `(resourceType, resourceId)` – at most one lock per resource
- `by_project`: List all active locks in a project
- `by_user`: Find locks held by a user

**Access patterns:**
- Check if resource is locked before edit
- Acquire/release/refresh locks
- Display lock status in UI ("Locked by Alice")
- Auto-expire stale locks (check `lockedAt + TTL`)

**Lock semantics:**
- **Acquisition**: Create if none exists or expired
- **Refresh**: Update `lockedAt` periodically (every 5 min)
- **Expiry**: Locks older than 1-2 hours are considered expired
- **Release**: Delete lock document

---

### `comments`

Unified comment system for human and agent assignments.

```typescript
{
  _id: string;
  projectId: string;
  sectionId: string;
  blockId?: string;              // Optional: anchor to specific block
  authorUserId: string;
  createdAt: number;
  body: string;                  // Comment text
  status: 'open' | 'in_progress' | 'resolved';
  assigneeType: 'user' | 'agent';
  assigneeUserId?: string;       // If assigneeType = 'user'
  linkedSections: string[];      // From @section mentions
  resolutionSummary?: string;
  resolvedByUserId?: string;
  resolvedAt?: number;
}
```

**Indexes:**
- `by_section`: Show comments for a section
- `by_project`: All comments in project
- `by_status`: Filter open/resolved
- `by_assignee`: Find all comments assigned to a user/agent

**Access patterns:**
- Display comments in sidebar for a section
- List all open comments for project overview
- Resolve comment after agent proposes changes
- Navigate to linked sections

**@mentions:**
- Parsed client-side: `@section[Section Name]` → `linkedSections: [sectionId]`
- Sandbox receives linked section text as context

---

### `agentThreads`

Persistent conversations with the AI agent.

```typescript
{
  _id: string;
  projectId: string;
  title: string;
  createdByUserId: string;
  createdAt: number;
  status: 'open' | 'archived';
  anchorSectionId?: string;      // Optional: thread about a section
  anchorCommentId?: string;      // Optional: thread to resolve a comment
  metadata?: {
    parentThreadId?: string;     // If forked
    parentMessageId?: string;
    [key: string]: any;
  };
}
```

**Indexes:**
- `by_project`: List all threads in a project
- `by_status`: Filter active vs archived
- `by_anchor_section`: Find threads about a section

**Access patterns:**
- List threads in sidebar
- Open thread to view messages
- Fork thread (create new with parentThreadId)

**Lock integration:**
- Threads are lockable via `locks` table with `resourceType='thread'`
- Only lock holder can send messages that trigger agent

---

### `agentMessages`

Messages within agent threads.

```typescript
{
  _id: string;
  threadId: string;
  senderType: 'user' | 'agent' | 'tool';
  senderUserId?: string;         // If senderType = 'user'
  createdAt: number;
  content: any;                  // Text or structured data
  toolCalls?: any;               // Future: tool execution metadata
  appliedEditVersionId?: string; // If this message led to accepted edits
}
```

**Indexes:**
- `by_thread`: Load all messages for a thread (ordered by createdAt)

**Access patterns:**
- Display thread conversation history
- Build context for sandbox: recent N messages
- Link message to version if edits were accepted

**Storage:**
- Full conversation history stored
- Sandbox receives recent messages (e.g., last 20) to manage context window

---

### `reportVersions`

Whole-document snapshots for version history.

```typescript
{
  _id: string;
  projectId: string;
  createdAt: number;
  createdByUserId: string;
  summary?: string;              // "Initial draft", "After agent review", etc.
  snapshot: {
    sections: [
      {
        sectionId: string;
        headingText: string;
        headingLevel: number;
        order: number;
        blocks: [
          {
            blockId: string;
            blockType: string;
            order: number;
            markdownText: string;
          }
        ]
      }
    ]
  };
}
```

**Indexes:**
- `by_project`: List all versions for a project (sorted by createdAt desc)

**Access patterns:**
- Display version history UI
- Load snapshot for diff comparison
- Restore version: replace current sections/blocks with snapshot data

**Snapshot format:**
- Denormalized: full section and block data embedded
- No references: snapshot is self-contained (even if original sections/blocks are deleted)
- Size: Typically a few KB to a few MB per version (acceptable for Convex storage)

**When versions are created:**
- User clicks "Save Version"
- User accepts agent-proposed edits
- (Optional) Auto-snapshot every N minutes or edits

---

### `artifacts`

Uploaded files (CSV, HTML, PDF, etc.) for context.

```typescript
{
  _id: string;
  projectId: string;
  name: string;               // Original filename
  description?: string;
  fileType: string;           // MIME type or extension
  storageKey: string;         // S3 key or Convex file storage ID
  uploadedByUserId: string;
  uploadedAt: number;
}
```

**Indexes:**
- `by_project`: List all artifacts for a project

**Access patterns:**
- Upload artifact: store file, create record
- List artifacts in project settings
- (Future) Sandbox downloads artifact for parsing

**v1 limitation:**
- Artifacts are opaque attachments
- Future versions will parse and provide structured context to agent

---

## Common Queries

### Load entire document for editing

```typescript
// Convex query
const sections = await db.query('sections')
  .withIndex('by_project', q => q.eq('projectId', projectId))
  .order('order')
  .collect();

const blocks = await db.query('blocks')
  .withIndex('by_project', q => q.eq('projectId', projectId))
  .collect();

// Group blocks by section in client
```

### Check if user can edit section

```typescript
// 1. Verify user is project member
const membership = await db.query('projectMembers')
  .withIndex('by_project_user', q => q.eq('projectId', projectId).eq('userId', userId))
  .first();

// 2. Check lock
const lock = await db.query('locks')
  .withIndex('by_resource', q => q.eq('resourceType', 'section').eq('resourceId', sectionId))
  .first();

// 3. Allow if no lock, expired lock, or user holds lock
```

### Create version snapshot

```typescript
const sections = await db.query('sections')
  .withIndex('by_project', q => q.eq('projectId', projectId))
  .order('order')
  .collect();

const allBlocks = await db.query('blocks')
  .withIndex('by_project', q => q.eq('projectId', projectId))
  .collect();

// Group blocks by section, serialize to snapshot
const snapshot = {
  sections: sections.map(s => ({
    sectionId: s._id,
    headingText: s.headingText,
    headingLevel: s.headingLevel,
    order: s.order,
    blocks: allBlocks.filter(b => b.sectionId === s._id)
      .sort((a, b) => a.order - b.order)
      .map(b => ({
        blockId: b._id,
        blockType: b.blockType,
        order: b.order,
        markdownText: b.markdownText
      }))
  }))
};

await db.insert('reportVersions', {
  projectId,
  createdAt: Date.now(),
  createdByUserId: userId,
  summary: 'Manual save',
  snapshot
});
```

## Design Trade-offs

### Block-based vs CRDT
- **Chosen**: Block-based with locks
- **Pros**: Simpler, easier to reason about, good enough for report writing
- **Cons**: No simultaneous multi-cursor editing within same section
- **Rationale**: Reports are typically edited by one person per section; collaboration is more async review than real-time pair programming

### Whole snapshots vs delta-based versioning
- **Chosen**: Whole snapshots
- **Pros**: Simple restore, self-contained, no dependency on prior versions
- **Cons**: More storage (mitigated: text is small, Convex handles compression)
- **Rationale**: Reports are not huge; simplicity and reliability outweigh storage cost

### Denormalized snapshots vs references
- **Chosen**: Denormalized (embed all data in snapshot)
- **Pros**: Snapshot survives deletion of original sections/blocks, faster restore
- **Cons**: Duplication of data
- **Rationale**: Versions are immutable history; should not break if current data changes

### Generic lock table vs per-resource lock fields
- **Chosen**: Generic `locks` table
- **Pros**: Single implementation for sections, blocks, threads; easier to query all locks
- **Cons**: Slightly more complex queries (join on resourceType + resourceId)
- **Rationale**: Reusable pattern, easier to extend (e.g., lock entire projects, artifacts)
