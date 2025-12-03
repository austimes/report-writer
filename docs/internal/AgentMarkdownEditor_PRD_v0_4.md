Agent-Enabled Collaborative Markdown Report Editor – PRD v0.4

1. Product Summary

A web application for collaboratively drafting Markdown-based reports, where:

- Multiple users can co-edit a report with near real-time updates.
- Users can attach comments to specific parts of the document and assign them either to:
  - Other humans, or
  - An AI agent.
- The AI agent:
  - Works in the context of the document (and optionally attached files).
  - Proposes diffs (text changes) that users can review, edit, and accept/reject.
- The system maintains:
  - Whole-document versions (snapshots).
  - Block-level attribution (“blame”: who edited what, and whether via agent).

Domain-specific behaviour (e.g. pathway reporting) is implemented later via custom tools in the agent sandbox, not in the core product.

2. Scope & Constraints

2.1 In Scope (v1)

- Projects & single-report per project.
- Markdown editor with live preview.
- Near real-time syncing via Convex.
- Locking for:
  - Sections (and potentially blocks).
  - Agent threads (who “drives” the agent).
- Unified comments system (human + agent).
- Shared agent threads (persistent conversations).
- @mentions for sections (and future artifacts).
- Generic AI assistance (rewrite, summarise, expand, resolve comments).
- Whole-document version snapshots and history.
- Block-level blame metadata.
- Basic artifact uploads (no special parsing in v1).
- Auth: email/password + invite.

2.2 Out of Scope (v1)

- Lock-free CRDT-style multi-cursor editing.
- Word/PDF layout features (headers, cross-references, etc.).
- Domain-specific tools (e.g. CSV/HTML parsers) – those live in sandbox later.
- Export to .docx/PDF (v1 relies on Markdown download and copy-paste).

3. Users & Roles

- Project Owner
  - Creates project.
  - Uploads initial report.
  - Manages collaborators.
  - Archives/deletes project.

- Editor
  - Edits content.
  - Uses locks (sections, threads).
  - Creates/assigns comments.
  - Starts/continues threads.
  - Accepts/rejects agent diffs.

(All collaborators are Editors in v1; Viewer roles later.)

4. Core Concepts & Text Granularity

4.1 Project

A Project encapsulates:

- One primary Markdown report.
- Zero or more attached artifacts (files; opaque in v1).
- Collaborators.
- Comments, locks, agent threads, versions.

4.2 Report → Sections → Blocks

Represent the report as:

- Sections:
  - Defined by headings (#, ##, ###, etc.).
  - Main units for navigation and locking.
  - Anchors for comments and threads.

- Blocks:
  - Smallest tracked text unit.
  - Types: paragraph, list_item, heading, table_row, code_block, etc.
  - Each block has:
    - id, section_id, order.
    - block_type.
    - markdown_text (string).
    - last_editor_user_id, last_edited_at, last_edit_type (manual | agent).

Design choice: block-level storage, but word-level diffs computed in memory.

5. Artifacts (Optional Attachments)

- Users can upload files (CSV, HTML, PDF, etc.) as artifacts.
- In v1:
  - The core editor treats them as opaque attachments.
  - Metadata + storage key recorded.
- Future:
  - Sandbox tools can parse/interpret artifacts and feed structured context to the agent.

6. Editing, Realtime Behaviour, Locks & History

6.1 Operational State: Convex

Convex holds the live state of:

- Projects, memberships, users.
- Sections, blocks.
- Comments, locks, threads, messages.
- Version metadata and snapshots.

Clients subscribe to Convex queries for near real-time updates.

6.2 Editing Mode: Block-wise (with locks)

- User edits are scoped to sections and their blocks.
- The editor manipulates markdown_text per block.
- Changes are sent via Convex mutations:
  - Debounced (e.g. on blur, small idle windows) to avoid spam.
- Other clients watching those blocks see updates quickly.

This is Option A: block-wise editing + locks, not full-blown CRDT.

6.3 Generic Locking (Sections, Blocks, Threads)

We use a single generic locking mechanism for all lockable resources:

- Sections (for editing content).
- Blocks (optional future refinement).
- Threads (for driving the agent).

Lock semantics:

- A Lock is a separate document that references a resource:
  - resource_type: 'section' | 'block' | 'thread' (v1).
  - resource_id: the ID of that section/block/thread.
  - user_id: who holds the lock.
  - locked_at: timestamp.

- At most one lock per (resource_type, resource_id) at a time.

Sections:

- User clicks “Lock section”:
  - Convex function attempts to create a Lock for resource_type = 'section'.
  - If none exists or existing is expired → success.
  - If held by someone else and not expired → user is told “Locked by [User]”.
- While locked:
  - Only the lock holder may edit blocks in that section.
- Users can release the lock manually.
- Locks auto-expire after a timeout (e.g. 1–2 hours idle) so others can acquire.

Threads (agent conversations):

- Agent threads are treated as lockable resources:
  - resource_type = 'thread', resource_id = threadId.
- To send a message that triggers an agent sandbox call:
  - Client ensures the current user holds the thread lock.
  - If thread is not locked or lock is expired:
    - Convex grants the lock to the user.
  - If locked by someone else:
    - User can:
      - View the thread (read-only).
      - Optionally fork a new thread (see §8).
      - Take over if the lock has clearly expired (with confirmation).

This reuses the same lock logic for both document sections and agent threads, keeping behaviour consistent.

6.4 Whole-Document Versions & Snapshots

We maintain whole-document snapshots for version history.

report_versions documents contain:

- id, project_id.
- created_at, created_by_user_id.
- summary (short description).
- snapshot JSON:
  - Full document structure at that time:
    - Sections (IDs, heading text, heading level, order).
    - Blocks within each section:
      - blockId, blockType, order, markdownText.

We create versions:

- When user hits “Save version”.
- When user accepts an agent-generated diff.
- (Optional) on periodic autosnapshots.

Restoring a version:

- Overwrites current sections/blocks in Convex with snapshot.
- Creates a new version capturing the restored document.

6.5 Diffs

Diffs are:

- Computed at block level, displayed at word level.

When comparing:

- Two versions, or
- Current vs agent proposal:

We:

- Get old vs new markdown_text for each block.
- Run a word-level diff algorithm (client or sandbox).
- Render additions/deletions inline.

6.6 Authorship / Blame

Each block carries:

- last_editor_user_id
- last_edited_at
- last_edit_type (manual | agent)

When changes are applied:

- Identify changed blocks.
- For each:
  - last_editor_user_id = user who clicked Accept (for agent diffs) or performed manual commit.
  - last_edit_type set appropriately.

UI:

- Hover over a block shows:
  - “Last edited by [User] – via [manual/agent] – [timestamp]”.

7. Comments, Mentions & Ownership

7.1 Unified Comments

Single comment system used for both:

- Human discussions.
- Agent resolution tasks.

Each comment:

- Anchored to section, optional block, optional text range.
- Fields:
  - status: open | in_progress | resolved.
  - assignee_type: user | agent.
  - assignee_user_id (for user).
  - body, resolution_summary, resolved_by_user_id, resolved_at.
  - linked_sections (from mentions).

UI:

- Select text or a block → “Add comment”.
- Assign to self, another user, or agent.

7.2 Mentions (@section, future @artifact)

@mentions help specify context:

- v1:
  - @section[...] – reference another section.
- Future:
  - @artifact[...], @user[...], etc.

UX:

- Typing @ opens autocomplete:
  - Shows sections (by heading text).
- On save:
  - Frontend parses mentions → sends structured linkedSections to Convex.

These references are passed to the sandbox as part of context when the agent is invoked.

7.3 Agent-Handled Comments

When assignee_type = 'agent':

- The app links the comment to an agent thread (new or existing).
- When user asks agent to resolve it:
  - Convex ensures user holds a thread lock for that thread (via generic Lock).
  - Sandbox receives:
    - Anchored text.
    - Comment body.
    - Linked sections’ text.
    - Recent thread messages.
  - Sandbox returns:
    - Agent reply message.
    - Proposed edits (old/new text for blocks).

User:

- Sees diff.
- Optionally edits proposal.
- Accepts:
  - Convex updates blocks.
  - Creates report version.
  - Resolves comment.
- Rejects:
  - No change; comment remains open; reply stored.

7.4 Human-Handled Comments

When assignee_type = 'user':

- Standard review flow.
- Mentions still help navigate context.
- On resolution, user sets status to resolved with optional summary.

8. Agent Threads (Shared Conversations, Using Locks)

8.1 Concept

Agent Threads:

- Are persistent conversations (chat) between users and the AI agent.
- Are project-scoped, visible to all collaborators.
- May be anchored to:
  - A section.
  - A comment.

8.2 Data Model (Convex)

agent_threads:

- id
- project_id
- title
- created_by_user_id
- created_at
- status: open | archived
- anchor_section_id?
- anchor_comment_id?
- metadata? (tags, etc.)

(No dedicated lock fields; thread lock lives in locks table with resource_type = 'thread'.)

agent_messages:

- id
- thread_id
- sender_type: user | agent | tool
- sender_user_id?
- created_at
- content (text/JSON)
- tool_calls?
- applied_edit_version_id?

8.3 Control & Locking

To avoid concurrent driver behaviour:

- At any time, 0 or 1 users hold a Lock with:
  - resource_type = 'thread'
  - resource_id = threadId

To send a message that triggers the agent:

1. Client calls a Convex mutation runAgentOnThread:
   - It:
     - Attempts to acquire or validate a Lock for the thread:
       - If no lock or expired → create/update lock for current user.
       - If locked by another user and not expired → reject with “Thread locked by [User]”.
   - If lock ok:
     - Records the outgoing agentMessage (sender=user).
     - Calls the sandbox endpoint /v1/agent/run.
     - Stores returned agentMessage + any proposed edits.

Other users:

- Can open and view the same thread in real time.
- Cannot send active agent-calling messages unless they:
  - Acquire the lock (which requires original lock to expire or be released), or
  - Fork the thread.

8.4 Forking Threads

Any user may choose to fork a thread:

- Creates new agent_thread with:
  - project_id same as parent.
  - title like “Fork of ‘[Original Title]’ by [User]”.
  - metadata.parent_thread_id and metadata.parent_message_id.
  - Optional same anchor section/comment.

- Context for new thread:
  - May start with a summarised view of parent up to the fork point, or just refer back.
- New thread is independent, has its own lock and messages.

8.5 Thread UI

- Threads list:
  - Title.
  - Anchors.
  - Status.
  - Lock state (“Locked by [User]” vs “Available”).
  - Fork badge (if forked).
- Thread view:
  - Chat transcript.
  - If current user owns thread lock → active input box.
  - If not:
    - Read-only view.
    - “Request control” (if lock expired) or “Fork thread” options.

9. Architecture & Deployment

9.1 Frontend + Convex

- React SPA using Convex client.
- Convex functions for:
  - CRUD on all tables.
  - Generic lock acquisition/release for resources.
  - Version creation/restoration.
  - Invoking sandbox for agent operations.

9.2 Agent Sandbox (External Service)

- Runs on e.g. Daytona or any hosted environment.
- Responsibilities:
  - Orchestrate LLM calls (OpenAI/Anthropic with training disabled).
  - Build prompts from context provided by Convex.
  - Return agent messages + proposed block edits.
- Uses S3-like storage and optional DB if needed for future artifact processing.

9.3 Convex Schema Stub (Updated with generic Lock)

Pseudo-TypeScript to guide devs; actual Convex schema will use its own APIs.

type User = {
  _id: string;
  email: string;
  name: string;
  createdAt: number;
};

type Project = {
  _id: string;
  ownerId: string;
  name: string;
  description?: string;
  createdAt: number;
  archived: boolean;
};

type ProjectMember = {
  _id: string;
  projectId: string;
  userId: string;
  role: 'owner' | 'editor';
  invitedAt: number;
};

type Section = {
  _id: string;
  projectId: string;
  headingText: string;
  headingLevel: number;
  order: number;
  createdAt: number;
};

type Block = {
  _id: string;
  projectId: string;
  sectionId: string;
  order: number;
  blockType:
    | 'paragraph'
    | 'list_item'
    | 'heading'
    | 'table_row'
    | 'code_block'
    | 'other';
  markdownText: string;
  lastEditorUserId?: string;
  lastEditType?: 'manual' | 'agent';
  lastEditedAt?: number;
};

// Generic lock for sections, blocks, threads, etc.
type Lock = {
  _id: string;
  projectId: string;
  resourceType: 'section' | 'block' | 'thread';
  resourceId: string;
  userId: string;
  lockedAt: number;
};

type Comment = {
  _id: string;
  projectId: string;
  sectionId: string;
  blockId?: string;
  authorUserId: string;
  createdAt: number;
  body: string;
  status: 'open' | 'in_progress' | 'resolved';
  assigneeType: 'user' | 'agent';
  assigneeUserId?: string;
  linkedSections: string[];
  resolutionSummary?: string;
  resolvedByUserId?: string;
  resolvedAt?: number;
};

type AgentThread = {
  _id: string;
  projectId: string;
  title: string;
  createdByUserId: string;
  createdAt: number;
  status: 'open' | 'archived';
  anchorSectionId?: string;
  anchorCommentId?: string;
  metadata?: Record<string, any>;
};

type AgentMessage = {
  _id: string;
  threadId: string;
  senderType: 'user' | 'agent' | 'tool';
  senderUserId?: string;
  createdAt: number;
  content: any;
  toolCalls?: any;
  appliedEditVersionId?: string;
};

type ReportVersion = {
  _id: string;
  projectId: string;
  createdAt: number;
  createdByUserId: string;
  summary?: string;
  snapshot: {
    sections: {
      sectionId: string;
      headingText: string;
      headingLevel: number;
      order: number;
      blocks: {
        blockId: string;
        blockType: string;
        order: number;
        markdownText: string;
      }[];
    }[];
  };
};

type Artifact = {
  _id: string;
  projectId: string;
  name: string;
  description?: string;
  fileType: string;
  storageKey: string;
  uploadedByUserId: string;
  uploadedAt: number;
};

// Pseudo Convex schema definition
export default defineSchema({
  users: defineTable<User>(),
  projects: defineTable<Project>(),
  projectMembers: defineTable<ProjectMember>(),
  sections: defineTable<Section>(),
  blocks: defineTable<Block>(),
  locks: defineTable<Lock>(),
  comments: defineTable<Comment>(),
  agentThreads: defineTable<AgentThread>(),
  agentMessages: defineTable<AgentMessage>(),
  reportVersions: defineTable<ReportVersion>(),
  artifacts: defineTable<Artifact>(),
});

9.4 Sandbox API (Core)

Key endpoint:

POST /v1/agent/run – runs the agent for a thread message with provided context, returns agent message + proposed edits.

Convex enforces locks before making this call; sandbox does not need to know about locks.
