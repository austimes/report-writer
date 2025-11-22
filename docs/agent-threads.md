# Agent Threads

This document explains how AI agent threads work, including lifecycle, locking, and sandbox integration.

## Overview

**Agent Threads** are persistent conversations between users and the AI agent, visible to all project collaborators. They enable:

- Multi-turn dialogue with context
- Reviewing agent proposals before accepting
- Collaboration (viewing threads, forking for parallel exploration)
- Anchoring to sections or comments

## Data Model

### `agentThreads`

```typescript
type AgentThread = {
  _id: string;
  projectId: string;
  title: string;
  createdByUserId: string;
  createdAt: number;
  status: 'open' | 'archived';
  anchorSectionId?: string;      // Optional: thread about a specific section
  anchorCommentId?: string;      // Optional: thread to resolve a comment
  metadata?: {
    parentThreadId?: string;     // If forked from another thread
    parentMessageId?: string;    // Fork point
    [key: string]: any;
  };
};
```

### `agentMessages`

```typescript
type AgentMessage = {
  _id: string;
  threadId: string;
  senderType: 'user' | 'agent' | 'tool';
  senderUserId?: string;         // If senderType = 'user'
  createdAt: number;
  content: any;                  // Text or structured data
  toolCalls?: any;               // Future: tool execution logs
  appliedEditVersionId?: string; // Links to reportVersion if edits accepted
};
```

## Thread Lifecycle

### 1. Creation

**Triggers:**
- User clicks "New Thread" in sidebar
- User assigns a comment to agent (auto-creates thread)
- User selects text and chooses "Ask Agent"

**Process:**
```typescript
export const createAgentThread = mutation(
  async ({ db, auth }, { projectId, title, anchorSectionId?, anchorCommentId? }) => {
    const userId = await auth.getUserIdentity();
    
    const threadId = await db.insert('agentThreads', {
      projectId,
      title,
      createdByUserId: userId,
      createdAt: Date.now(),
      status: 'open',
      anchorSectionId,
      anchorCommentId,
      metadata: {}
    });
    
    return threadId;
  }
);
```

### 2. Sending Messages

**User sends message:**
```typescript
export const sendUserMessage = mutation(
  async ({ db, auth }, { threadId, content }) => {
    const userId = await auth.getUserIdentity();
    
    await db.insert('agentMessages', {
      threadId,
      senderType: 'user',
      senderUserId: userId,
      createdAt: Date.now(),
      content
    });
  }
);
```

**Triggering agent (requires lock):**
```typescript
export const runAgentOnThread = mutation(
  async ({ db, auth }, { threadId, userMessage }) => {
    const userId = await auth.getUserIdentity();
    const thread = await db.get(threadId);
    
    // 1. Check/acquire thread lock
    const lock = await db.query('locks')
      .withIndex('by_resource', q => 
        q.eq('resourceType', 'thread').eq('resourceId', threadId)
      )
      .first();
    
    if (lock && lock.userId !== userId && !isExpired(lock)) {
      throw new Error(`Thread locked by ${lock.userId}`);
    }
    
    // Acquire or refresh lock
    if (!lock || isExpired(lock)) {
      await db.insert('locks', {
        projectId: thread.projectId,
        resourceType: 'thread',
        resourceId: threadId,
        userId,
        lockedAt: Date.now()
      });
    } else {
      await db.patch(lock._id, { lockedAt: Date.now() });
    }
    
    // 2. Store user message
    await db.insert('agentMessages', {
      threadId,
      senderType: 'user',
      senderUserId: userId,
      createdAt: Date.now(),
      content: userMessage
    });
    
    // 3. Call sandbox (via Convex action)
    const agentResponse = await ctx.runAction('runAgentSandbox', {
      threadId,
      userMessage
    });
    
    // 4. Store agent response
    await db.insert('agentMessages', {
      threadId,
      senderType: 'agent',
      createdAt: Date.now(),
      content: agentResponse.message,
      toolCalls: agentResponse.toolCalls
    });
    
    return agentResponse;
  }
);
```

### 3. Archiving

**User can archive inactive threads:**
```typescript
export const archiveThread = mutation(async ({ db, auth }, { threadId }) => {
  await db.patch(threadId, { status: 'archived' });
});
```

Archived threads are hidden from main list but remain searchable.

## Lock Enforcement for Threads

### Why Lock Threads?

Without locking, multiple users could simultaneously send messages to the agent, causing:
- Race conditions in context building
- Conflicting proposed edits
- Confusion about "who's driving"

**Solution:** Treat threads as lockable resources.

### Lock Semantics

- **Lock type**: `resourceType = 'thread'`, `resourceId = threadId`
- **Holder**: User currently interacting with agent
- **Duration**: Same TTL as section locks (1-2 hours)
- **Acquisition**: First user to send agent message acquires lock
- **Refresh**: Refreshed on each agent message
- **Release**: Manual or auto-expiry

### UI States

| Lock State | Current User | Other Users |
|------------|--------------|-------------|
| No lock | Can send messages | Can send messages |
| Locked by you | Active input, can send | Read-only, "Locked by You" |
| Locked by Alice (active) | Read-only, "Fork Thread" option | Read-only, "Fork Thread" option |
| Locked by Alice (expired) | Can "Take Over" | Can "Take Over" |

### Forking Locked Threads

If a thread is locked by someone else, users can **fork** it:

```typescript
export const forkThread = mutation(
  async ({ db, auth }, { parentThreadId, forkFromMessageId? }) => {
    const userId = await auth.getUserIdentity();
    const parentThread = await db.get(parentThreadId);
    
    // Create new thread
    const newThreadId = await db.insert('agentThreads', {
      projectId: parentThread.projectId,
      title: `Fork of "${parentThread.title}" by ${userId}`,
      createdByUserId: userId,
      createdAt: Date.now(),
      status: 'open',
      anchorSectionId: parentThread.anchorSectionId,
      anchorCommentId: parentThread.anchorCommentId,
      metadata: {
        parentThreadId,
        parentMessageId: forkFromMessageId
      }
    });
    
    // Optionally copy messages up to fork point
    if (forkFromMessageId) {
      const parentMessages = await db.query('agentMessages')
        .withIndex('by_thread', q => q.eq('threadId', parentThreadId))
        .filter(q => q.lte('createdAt', forkFromMessageId.createdAt))
        .collect();
      
      for (const msg of parentMessages) {
        await db.insert('agentMessages', {
          threadId: newThreadId,
          senderType: msg.senderType,
          senderUserId: msg.senderUserId,
          createdAt: msg.createdAt,
          content: msg.content
        });
      }
    }
    
    return newThreadId;
  }
);
```

**Use cases for forking:**
- Alice is exploring one direction, Bob wants to try another
- Long thread needs cleanup; fork with summary
- Experiment with different prompts without affecting main thread

## Sandbox Integration

### Context Building

When the agent is invoked, Convex builds context from:

1. **Thread history**: Recent messages (e.g., last 20)
2. **Anchored section**: If `anchorSectionId` exists, include section + blocks
3. **Anchored comment**: If `anchorCommentId` exists, include comment body and linked sections
4. **Project artifacts**: List of uploaded files (future: parsed content)

**Convex action:**
```typescript
export const runAgentSandbox = action(
  async (ctx, { threadId, userMessage }) => {
    const thread = await ctx.runQuery('getThread', { threadId });
    const messages = await ctx.runQuery('getThreadMessages', { threadId });
    
    // Build context
    let context = {
      threadId,
      projectId: thread.projectId,
      messages: messages.slice(-20), // Last 20 messages
      anchoredContent: null
    };
    
    // Add anchored section
    if (thread.anchorSectionId) {
      const section = await ctx.runQuery('getSection', { sectionId: thread.anchorSectionId });
      const blocks = await ctx.runQuery('getSectionBlocks', { sectionId: thread.anchorSectionId });
      context.anchoredContent = {
        type: 'section',
        heading: section.headingText,
        content: blocks.map(b => b.markdownText).join('\n\n')
      };
    }
    
    // Add anchored comment
    if (thread.anchorCommentId) {
      const comment = await ctx.runQuery('getComment', { commentId: thread.anchorCommentId });
      const linkedSections = await ctx.runQuery('getSections', { ids: comment.linkedSections });
      context.anchoredContent = {
        type: 'comment',
        body: comment.body,
        linkedSections: linkedSections.map(s => ({
          heading: s.headingText,
          content: '...' // blocks content
        }))
      };
    }
    
    // Call sandbox
    const response = await fetch('http://sandbox:8000/v1/agent/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        context,
        userMessage
      })
    });
    
    return await response.json();
  }
);
```

### Sandbox Endpoint

**`POST /v1/agent/run`**

**Request:**
```json
{
  "context": {
    "threadId": "abc123",
    "projectId": "proj456",
    "messages": [
      { "senderType": "user", "content": "Can you help?" },
      { "senderType": "agent", "content": "Sure!" }
    ],
    "anchoredContent": {
      "type": "section",
      "heading": "Introduction",
      "content": "This is the introduction..."
    }
  },
  "userMessage": "Please rewrite this to be more concise."
}
```

**Response:**
```json
{
  "message": "I've rewritten the introduction to be more concise.",
  "proposedEdits": [
    {
      "blockId": "block789",
      "oldText": "This is the introduction...",
      "newText": "Introduction:\n\nWe propose..."
    }
  ],
  "toolCalls": []
}
```

**Python implementation (apps/sandbox):**
```python
from fastapi import FastAPI
from app.services.agent import AgentOrchestrator

app = FastAPI()
orchestrator = AgentOrchestrator()

@app.post('/v1/agent/run')
async def run_agent(request: AgentRunRequest):
    # Build prompt
    prompt = orchestrator.build_prompt(
        context=request.context,
        user_message=request.userMessage
    )
    
    # Call LLM (OpenAI/Anthropic)
    llm_response = await orchestrator.call_llm(prompt)
    
    # Parse response for message + edits
    parsed = orchestrator.parse_response(llm_response)
    
    return {
        'message': parsed.message,
        'proposedEdits': parsed.edits,
        'toolCalls': parsed.tool_calls
    }
```

### Proposed Edits

The sandbox returns proposed edits in a structured format:

```typescript
type ProposedEdit = {
  blockId: string;
  oldText: string;  // For verification
  newText: string;  // Proposed replacement
};
```

**Convex stores these temporarily:**
```typescript
// In agentMessages, add a field:
proposedEdits?: ProposedEdit[];
```

**UI workflow:**
1. Display diff (old vs new) for each block
2. User can:
   - **Accept**: Apply edits, create version
   - **Edit**: Modify proposed text, then apply
   - **Reject**: Discard, keep original

**Accepting edits:**
```typescript
export const acceptAgentEdits = mutation(
  async ({ db, auth }, { messageId }) => {
    const userId = await auth.getUserIdentity();
    const message = await db.get(messageId);
    
    // Apply each edit
    for (const edit of message.proposedEdits) {
      const block = await db.get(edit.blockId);
      
      // Verify old text matches (safety check)
      if (block.markdownText !== edit.oldText) {
        throw new Error('Block content changed since proposal');
      }
      
      // Apply new text
      await db.patch(edit.blockId, {
        markdownText: edit.newText,
        lastEditorUserId: userId,
        lastEditType: 'agent',
        lastEditedAt: Date.now()
      });
    }
    
    // Create version
    const versionId = await ctx.runMutation('createVersion', {
      projectId: message.threadId.projectId,
      summary: `Agent edits from thread: ${message.threadId.title}`
    });
    
    // Link version to message
    await db.patch(messageId, {
      appliedEditVersionId: versionId
    });
    
    // If anchored to comment, resolve it
    const thread = await db.get(message.threadId);
    if (thread.anchorCommentId) {
      await db.patch(thread.anchorCommentId, {
        status: 'resolved',
        resolvedByUserId: userId,
        resolvedAt: Date.now()
      });
    }
  }
);
```

## UI Components

### Thread List Sidebar

```tsx
function ThreadList({ projectId }) {
  const threads = useQuery('listThreads', { projectId });
  
  return (
    <div>
      <button onClick={createNewThread}>+ New Thread</button>
      {threads.map(t => (
        <ThreadItem 
          key={t._id} 
          thread={t}
          lockStatus={getLockStatus(t._id)}
        />
      ))}
    </div>
  );
}
```

### Thread View

```tsx
function ThreadView({ threadId }) {
  const messages = useQuery('getThreadMessages', { threadId });
  const lock = useQuery('getThreadLock', { threadId });
  
  const canSendMessage = !lock || lock.userId === currentUserId || isExpired(lock);
  
  return (
    <div>
      <MessageList messages={messages} />
      {canSendMessage ? (
        <MessageInput onSend={sendMessage} />
      ) : (
        <LockedBanner 
          lockedBy={lock.userId}
          onFork={() => forkThread(threadId)}
        />
      )}
    </div>
  );
}
```

### Agent Diff Review

```tsx
function AgentDiffView({ proposedEdits }) {
  return (
    <div>
      {proposedEdits.map(edit => (
        <BlockDiff
          key={edit.blockId}
          oldText={edit.oldText}
          newText={edit.newText}
        />
      ))}
      <button onClick={acceptEdits}>Accept All</button>
      <button onClick={rejectEdits}>Reject</button>
    </div>
  );
}
```

## Security Considerations

- **Lock bypass prevention**: All mutations verify locks server-side
- **Message validation**: Sanitize user input before sending to sandbox
- **LLM API keys**: Stored in sandbox environment, never exposed to client
- **Rate limiting**: Prevent spam by limiting agent calls per user/project
- **Content filtering**: Future: scan agent responses for sensitive data

## Performance

- **Message pagination**: Load last 50 messages, infinite scroll for history
- **Context window**: Limit to ~20 messages to avoid token limits
- **Caching**: Convex caches thread queries, invalidates on new message
- **Debouncing**: Typing indicators, but message send is immediate (no debounce)

## Future Enhancements

- **Tool calls**: Agent can invoke functions (search web, query artifacts, run code)
- **Streaming responses**: Show agent typing in real-time
- **Rich edits**: Not just text replacement, but insert/delete/move blocks
- **Multi-agent**: Assign different agent personas to threads
- **Voice input**: Transcribe audio to text for messages
