import { useLock } from '@/features/locks/hooks/useLock';
import type { Id } from 'convex/_generated/dataModel';

export function useThreadLock(threadId: Id<'agentThreads'>, projectId: Id<'projects'>) {
  return useLock('thread', threadId, projectId);
}
