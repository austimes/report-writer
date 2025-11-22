# Locks and Versions

This document explains the locking mechanism and version snapshot system in detail.

## Generic Lock System

The application uses a **unified locking mechanism** for all lockable resources:
- Sections (for editing)
- Blocks (optional future refinement)
- Agent threads (for driving the agent)

### Lock Data Model

Locks are stored in the `locks` table:

```typescript
type Lock = {
  _id: string;
  projectId: string;
  resourceType: 'section' | 'block' | 'thread';
  resourceId: string;    // ID of the locked resource
  userId: string;        // Who holds the lock
  lockedAt: number;      // Unix timestamp (ms)
};
```

**Invariant:** At most one lock per `(resourceType, resourceId)` pair.

### Lock Acquisition

When a user attempts to acquire a lock (e.g., clicks "Lock Section"):

1. **Check existing lock:**
   ```typescript
   const existingLock = await db.query('locks')
     .withIndex('by_resource', q => 
       q.eq('resourceType', 'section').eq('resourceId', sectionId)
     )
     .first();
   ```

2. **Decide outcome:**
   - **No lock exists** → Create new lock
   - **Lock exists and expired** (older than TTL) → Transfer to requesting user
   - **Lock exists and active, held by requester** → Refresh timestamp
   - **Lock exists and active, held by someone else** → Reject with "Locked by [User]"

3. **Create or update lock:**
   ```typescript
   if (!existingLock || isExpired(existingLock)) {
     await db.insert('locks', {
       projectId,
       resourceType: 'section',
       resourceId: sectionId,
       userId: currentUserId,
       lockedAt: Date.now()
     });
   }
   ```

### Lock Expiry

**Default TTL:** 1-2 hours (configurable)

A lock is considered expired if:
```typescript
function isExpired(lock: Lock, ttlMs: number = 2 * 60 * 60 * 1000): boolean {
  return Date.now() - lock.lockedAt > ttlMs;
}
```

**Why expiry?**
- Prevents indefinite locks if user closes browser without releasing
- Allows teammates to take over abandoned work
- Balances protection vs accessibility

### Lock Refresh

Active users periodically refresh their locks to prevent expiry:

**Client-side:**
```typescript
// Every 5 minutes, refresh all held locks
setInterval(async () => {
  await refreshMyLocks();
}, 5 * 60 * 1000);
```

**Convex mutation:**
```typescript
export const refreshLock = mutation(async ({ db, auth }, { resourceType, resourceId }) => {
  const userId = await auth.getUserIdentity();
  
  const lock = await db.query('locks')
    .withIndex('by_resource', q => 
      q.eq('resourceType', resourceType).eq('resourceId', resourceId)
    )
    .first();
  
  if (lock && lock.userId === userId) {
    await db.patch(lock._id, { lockedAt: Date.now() });
  }
});
```

### Lock Release

**Manual release:**
```typescript
export const releaseLock = mutation(async ({ db, auth }, { resourceType, resourceId }) => {
  const userId = await auth.getUserIdentity();
  
  const lock = await db.query('locks')
    .withIndex('by_resource', q => 
      q.eq('resourceType', resourceType).eq('resourceId', resourceId)
    )
    .first();
  
  if (lock && lock.userId === userId) {
    await db.delete(lock._id);
  }
});
```

**Automatic release scenarios:**
- User clicks "Release" button
- User navigates away (via `beforeunload` event)
- Lock expires (no action needed; next acquire will overwrite)

### Lock Enforcement

Locks are enforced **server-side** in Convex mutations:

```typescript
export const updateBlock = mutation(async ({ db, auth }, { blockId, newText }) => {
  const userId = await auth.getUserIdentity();
  
  const block = await db.get(blockId);
  const section = await db.get(block.sectionId);
  
  // Check lock
  const lock = await db.query('locks')
    .withIndex('by_resource', q => 
      q.eq('resourceType', 'section').eq('resourceId', section._id)
    )
    .first();
  
  if (lock && lock.userId !== userId && !isExpired(lock)) {
    throw new Error(`Section locked by ${lock.userId}`);
  }
  
  // Proceed with update
  await db.patch(blockId, {
    markdownText: newText,
    lastEditorUserId: userId,
    lastEditType: 'manual',
    lastEditedAt: Date.now()
  });
});
```

### Lock Use Cases

#### 1. Section Editing

**UI:**
- Show lock status badge: "Locked by Alice" or "Available"
- Enable "Lock Section" button if unlocked or expired
- Disable editing if locked by someone else

**Workflow:**
```
User clicks "Lock Section"
  ↓
Convex: acquireLock(resourceType='section', resourceId=sectionId)
  ↓
Lock granted → UI enables editor
  ↓
User edits blocks (mutations check lock)
  ↓
User clicks "Release" or navigates away
  ↓
Convex: releaseLock(...)
```

#### 2. Agent Threads

**UI:**
- Show lock status: "Active (You)" / "Locked by Bob" / "Available"
- Enable message input only if user holds lock
- Offer "Fork Thread" if locked by someone else

**Workflow:**
```
User sends agent message
  ↓
Convex: runAgentOnThread(threadId, message)
  ↓
Check/acquire thread lock:
  - No lock? → Acquire
  - Expired? → Transfer
  - Active by other? → Reject
  ↓
If lock ok:
  - Store user message
  - Call sandbox via action
  - Store agent response
```

### Edge Cases

#### Concurrent Acquisition
- Two users click "Lock" at nearly the same time
- Convex serializes mutations; first wins
- Second receives rejection

#### Browser Crash
- User's browser crashes without releasing lock
- Lock expires after TTL
- Other users can acquire after expiry

#### Network Partition
- User loses network, thinks they have lock
- Mutations will fail (optimistic UI rolls back)
- Lock may expire if network down > TTL

#### Takeover
- User A locks section, goes idle
- Lock expires after 2 hours
- User B acquires lock automatically
- User A's pending edits will fail (lock check)

---

## Version Snapshots

The application maintains **whole-document snapshots** for version history and restore.

### Version Data Model

```typescript
type ReportVersion = {
  _id: string;
  projectId: string;
  createdAt: number;
  createdByUserId: string;
  summary?: string;  // "Initial draft", "After agent review", etc.
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
};
```

### Creating Snapshots

**Triggers:**
1. User clicks "Save Version"
2. User accepts agent-proposed edits
3. (Optional) Auto-snapshot every N minutes or edits

**Process:**
```typescript
export const createVersion = mutation(async ({ db, auth }, { projectId, summary }) => {
  const userId = await auth.getUserIdentity();
  
  // Load all sections and blocks
  const sections = await db.query('sections')
    .withIndex('by_project', q => q.eq('projectId', projectId))
    .order('order')
    .collect();
  
  const allBlocks = await db.query('blocks')
    .withIndex('by_project', q => q.eq('projectId', projectId))
    .collect();
  
  // Build snapshot
  const snapshot = {
    sections: sections.map(s => ({
      sectionId: s._id,
      headingText: s.headingText,
      headingLevel: s.headingLevel,
      order: s.order,
      blocks: allBlocks
        .filter(b => b.sectionId === s._id)
        .sort((a, b) => a.order - b.order)
        .map(b => ({
          blockId: b._id,
          blockType: b.blockType,
          order: b.order,
          markdownText: b.markdownText
        }))
    }))
  };
  
  // Store version
  await db.insert('reportVersions', {
    projectId,
    createdAt: Date.now(),
    createdByUserId: userId,
    summary: summary || `Version ${Date.now()}`,
    snapshot
  });
});
```

### Restoring Versions

**UI:**
- Version history list (sorted by date, most recent first)
- Click version → Show diff vs current
- Click "Restore" → Confirmation dialog → Restore

**Process:**
```typescript
export const restoreVersion = mutation(async ({ db, auth }, { versionId }) => {
  const userId = await auth.getUserIdentity();
  
  const version = await db.get(versionId);
  const projectId = version.projectId;
  
  // 1. Create snapshot of current state (for undo)
  await createVersion({ db, auth }, { projectId, summary: 'Before restore' });
  
  // 2. Delete current sections and blocks
  const currentSections = await db.query('sections')
    .withIndex('by_project', q => q.eq('projectId', projectId))
    .collect();
  for (const s of currentSections) {
    await db.delete(s._id);
  }
  
  const currentBlocks = await db.query('blocks')
    .withIndex('by_project', q => q.eq('projectId', projectId))
    .collect();
  for (const b of currentBlocks) {
    await db.delete(b._id);
  }
  
  // 3. Recreate from snapshot
  for (const sectionSnapshot of version.snapshot.sections) {
    const sectionId = await db.insert('sections', {
      projectId,
      headingText: sectionSnapshot.headingText,
      headingLevel: sectionSnapshot.headingLevel,
      order: sectionSnapshot.order,
      createdAt: Date.now()
    });
    
    for (const blockSnapshot of sectionSnapshot.blocks) {
      await db.insert('blocks', {
        projectId,
        sectionId,
        order: blockSnapshot.order,
        blockType: blockSnapshot.blockType,
        markdownText: blockSnapshot.markdownText,
        lastEditorUserId: userId,
        lastEditType: 'manual',
        lastEditedAt: Date.now()
      });
    }
  }
  
  // 4. Create new version capturing restored state
  await createVersion({ db, auth }, { 
    projectId, 
    summary: `Restored from ${version.summary}` 
  });
});
```

### Version Diffs

**Compare two versions:**
```typescript
export const compareVersions = query(async ({ db }, { versionIdA, versionIdB }) => {
  const vA = await db.get(versionIdA);
  const vB = await db.get(versionIdB);
  
  // Client-side: compute word-level diffs per block
  // Or call sandbox for diff generation
  return { versionA: vA.snapshot, versionB: vB.snapshot };
});
```

**Client-side diff rendering:**
- Use `diff` library (e.g., `diff-match-patch`, `fast-diff`)
- Highlight additions (green) and deletions (red)
- Show side-by-side or inline view

### Snapshot Storage Considerations

**Size:**
- Typical report: 10-100 sections, 100-1000 blocks
- Average block: 50-200 characters
- Snapshot size: ~10KB to 1MB
- With 100 versions: ~1-100MB (acceptable for Convex)

**Retention:**
- Keep all versions by default
- Optional: Prune old versions (e.g., keep last 50, or older than 6 months)

**Optimization:**
- Convex compresses JSON automatically
- Could implement delta-based storage in future (complexity vs benefit trade-off)

### Use Cases

#### Undo Bulk Agent Changes
```
User accepts agent proposal → Version created
User realizes changes are wrong
User restores previous version
```

#### Compare Draft Stages
```
User saves "Draft 1" version
User makes edits
User saves "Draft 2" version
User compares Draft 1 vs Draft 2 → Reviews changes
```

#### Recover from Mistake
```
User accidentally deletes entire section
User restores last version → Section recovered
```

#### Audit Trail
```
Manager wants to see who changed what
View version history → See timestamps, authors, summaries
Compare versions to see specific changes
```
