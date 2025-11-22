# Architecture

## System Overview

The Agent-Enabled Markdown Report Editor is a 3-tier web application:

1. **Web App** (React + Vite): User interface for editing, collaboration, and agent interaction
2. **Convex Backend**: Real-time database, business logic, and state synchronization
3. **Agent Sandbox** (Python FastAPI): AI agent orchestration and code execution

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           React SPA (apps/web)                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌─────────┐  │   │
│  │  │  Editor  │ │  Threads │ │ Locks  │ │ Versions│  │   │
│  │  │  Feature │ │  Feature │ │ Feature│ │ Feature │  │   │
│  │  └────┬─────┘ └────┬─────┘ └───┬────┘ └────┬────┘  │   │
│  │       └────────────┴────────────┴───────────┘       │   │
│  │                     │                                │   │
│  │              Convex Client SDK                       │   │
│  └─────────────────────┼─────────────────────────────────┘ │
└────────────────────────┼───────────────────────────────────┘
                         │ WebSocket (reactive queries)
                         │ HTTP (mutations, actions)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Convex Backend                            │
│  ┌──────────┐  ┌───────────┐  ┌─────────┐  ┌──────────┐   │
│  │ Queries  │  │ Mutations │  │ Actions │  │  Schema  │   │
│  └────┬─────┘  └─────┬─────┘  └────┬────┘  └──────────┘   │
│       │              │              │                       │
│       └──────────────┴──────────────┘                       │
│                      │                                      │
│            ┌─────────┴──────────┐                           │
│            │  Database Tables:  │                           │
│            │  - users           │                           │
│            │  - projects        │                           │
│            │  - sections        │                           │
│            │  - blocks          │                           │
│            │  - locks           │                           │
│            │  - agentThreads    │                           │
│            │  - versions        │                           │
│            └────────────────────┘                           │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP (Convex Actions)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Python Agent Sandbox (FastAPI)                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  POST /v1/agent/run                                  │  │
│  │    ├─ Context Builder (sections, comments, threads) │  │
│  │    ├─ LLM Orchestrator (OpenAI/Anthropic)          │  │
│  │    └─ Diff Generator (proposed block edits)        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  Future: Tool execution, artifact parsing, code sandbox    │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Editing Flow

```
User types in editor
    ↓
Debounced update (500ms)
    ↓
Convex mutation: updateBlock(blockId, newText)
    ↓
Convex updates block in database
    ↓
All subscribed clients receive update via WebSocket
    ↓
React components re-render with new block content
```

**Key points:**
- Block-level granularity for storage and sync
- Optimistic updates in UI for responsiveness
- Lock enforcement: only lock holder can mutate

### 2. Locking Flow

```
User clicks "Lock Section"
    ↓
Convex mutation: acquireLock(resourceType='section', resourceId=sectionId)
    ↓
Convex checks locks table:
    - No existing lock? → Create lock
    - Existing lock expired? → Transfer to new user
    - Existing lock active? → Reject with "Locked by [User]"
    ↓
Lock state propagates to all clients
    ↓
UI shows lock indicator, enables/disables editing
```

**Auto-expiry:**
- Locks expire after 1-2 hours of inactivity
- Client sends periodic refresh (every 5 minutes)
- Manual release available

### 3. Versioning Flow

```
User clicks "Save Version" or accepts agent diff
    ↓
Convex mutation: createVersion(projectId, summary)
    ↓
Snapshot current state:
    - Query all sections and blocks
    - Serialize to JSON structure
    - Store in reportVersions table
    ↓
Version appears in history UI
```

**Restore:**
```
User clicks "Restore Version"
    ↓
Convex mutation: restoreVersion(versionId)
    ↓
Replace current sections/blocks with snapshot data
    ↓
Create new version capturing pre-restore state
    ↓
All clients sync to restored content
```

### 4. Agent Thread Flow

```
User sends message in agent thread
    ↓
Convex mutation: runAgentOnThread(threadId, userMessage)
    ↓
Check/acquire thread lock:
    - No lock? → Acquire for user
    - Expired? → Transfer to user
    - Active by other? → Reject
    ↓
Store user message in agentMessages
    ↓
Convex action: HTTP POST to sandbox /v1/agent/run
    - Context: sections, linked comments, thread history
    ↓
Sandbox:
    - Builds prompt with context
    - Calls LLM API (OpenAI/Anthropic)
    - Parses response for message + proposed edits
    - Returns JSON: { message, proposedEdits: [{blockId, oldText, newText}] }
    ↓
Convex stores agent message and proposed edits
    ↓
UI shows diff view for user review
    ↓
User edits/accepts/rejects
    ↓
If accepted:
    - Apply edits to blocks
    - Create version snapshot
    - Mark comment as resolved (if applicable)
```

**Forking:**
- Any user can fork a locked thread
- Creates new thread with parent reference
- Independent lock and message history

## Technology Choices

### Frontend (apps/web)
- **React**: Component-based UI
- **Vite**: Fast dev server and build
- **TypeScript**: Type safety
- **TailwindCSS**: Utility-first styling
- **Convex React SDK**: Real-time queries and mutations

### Backend (convex/)
- **Convex**: Real-time database + backend functions
- **TypeScript**: Shared language with frontend
- **WebSocket**: Live query subscriptions
- **HTTP Functions**: Actions calling external services

### Sandbox (apps/sandbox)
- **Python**: Best ecosystem for AI/ML
- **FastAPI**: Modern async web framework
- **OpenAI/Anthropic SDKs**: LLM integration
- **Pydantic**: Data validation

## Deployment Topology

```
┌────────────┐
│   Vercel   │  ← React SPA (static)
└─────┬──────┘
      │
      ▼
┌──────────────┐
│    Convex    │  ← Backend (managed)
│   (Managed)  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Daytona    │  ← Python sandbox
│  or similar  │
└──────────────┘
```

**Scaling considerations:**
- Convex handles database and WebSocket connections
- Sandbox is stateless, can scale horizontally
- File storage (artifacts): S3 or Convex file storage

## Security

- **Authentication**: Convex built-in auth (email/password initially)
- **Authorization**: Project membership checked in all Convex functions
- **Lock enforcement**: Server-side validation in mutations
- **Sandbox isolation**: No direct database access, API-only communication
- **LLM API keys**: Stored server-side, never exposed to client

## Performance

- **Real-time sync**: Convex optimizes query subscriptions
- **Debouncing**: Editor updates debounced to reduce mutation frequency
- **Optimistic UI**: Updates shown immediately, rolled back on error
- **Lazy loading**: Version snapshots loaded on-demand
- **Caching**: Convex caches query results, invalidates on mutation
