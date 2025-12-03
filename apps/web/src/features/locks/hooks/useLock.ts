import { useEffect, useRef, useCallback } from 'react';
import { useQuery, useMutation } from 'convex/react';
import { api } from '@/lib/convex';
import type { Id } from 'convex/_generated/dataModel';

const LOCK_REFRESH_INTERVAL = 30 * 60 * 1000; // 30 minutes

export type LockStatus = 'acquired' | 'available' | 'blocked' | 'pending' | 'hierarchy-conflict';

export interface HierarchyConflict {
  relation: 'parent' | 'child';
  sectionTitle: string;
  lockedBy: string;
}

export interface UseLockResult {
  lockStatus: LockStatus;
  lockOwner: any | null;
  lockId: Id<'locks'> | null;
  hierarchyConflict: HierarchyConflict | null;
  acquire: () => Promise<void>;
  release: () => Promise<void>;
  refresh: () => Promise<void>;
}

export function useLock(
  resourceType: 'section' | 'block' | 'thread' | 'project' | 'markdown-section' | 'document' | 'node',
  resourceId: string,
  projectId: Id<'projects'>
): UseLockResult {
  const refreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const acquireLockMutation = useMutation(api.features.locking.acquireLock);
  const releaseLockMutation = useMutation(api.features.locking.releaseLock);
  const refreshLockMutation = useMutation(api.features.locking.refreshLock);
  
  const currentUser = useQuery(api.tables.users.getCurrentUser);
  const lock = useQuery(api.features.locking.getLockForResource, {
    resourceType,
    resourceId,
  });
  const hierarchyConflictData = useQuery(
    api.features.locking.getHierarchyLockConflict,
    resourceType === 'markdown-section' && resourceId
      ? { resourceType, resourceId }
      : 'skip'
  );

  const isOwnLock = lock && currentUser && lock.userId === currentUser._id;

  const hierarchyConflict: HierarchyConflict | null = hierarchyConflictData && 
    typeof hierarchyConflictData === 'object' &&
    'relation' in hierarchyConflictData
    ? {
        relation: (hierarchyConflictData as { relation: string }).relation as 'parent' | 'child',
        sectionTitle: (hierarchyConflictData as { sectionTitle: string }).sectionTitle,
        lockedBy: (hierarchyConflictData as { lockedBy: string }).lockedBy,
      }
    : null;

  const lockStatus: LockStatus = hierarchyConflict
    ? 'hierarchy-conflict'
    : lock
      ? isOwnLock
        ? 'acquired'
        : 'blocked'
      : 'available';

  const lockOwner = lock && !isOwnLock ? lock.userId : null;

  const acquire = useCallback(async () => {
    try {
      await acquireLockMutation({
        projectId,
        resourceType,
        resourceId,
      });
    } catch (error) {
      console.error('Failed to acquire lock:', error);
      throw error;
    }
  }, [acquireLockMutation, projectId, resourceType, resourceId]);

  const release = useCallback(async () => {
    if (lock && isOwnLock) {
      try {
        await releaseLockMutation({ lockId: lock._id });
      } catch (error) {
        console.error('Failed to release lock:', error);
        throw error;
      }
    }
  }, [releaseLockMutation, lock, isOwnLock]);

  const refresh = useCallback(async () => {
    if (lock && isOwnLock) {
      try {
        await refreshLockMutation({ lockId: lock._id });
      } catch (error) {
        console.error('Failed to refresh lock:', error);
        throw error;
      }
    }
  }, [refreshLockMutation, lock, isOwnLock]);

  // Auto-refresh lock every 30 minutes
  useEffect(() => {
    if (lockStatus === 'acquired' && lock) {
      refreshIntervalRef.current = setInterval(() => {
        refresh();
      }, LOCK_REFRESH_INTERVAL);

      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
        }
      };
    }
  }, [lockStatus, lock, refresh]);

  // Refresh on window focus
  useEffect(() => {
    const handleFocus = () => {
      if (lockStatus === 'acquired') {
        refresh();
      }
    };

    window.addEventListener('focus', handleFocus);
    return () => window.removeEventListener('focus', handleFocus);
  }, [lockStatus, refresh]);

  return {
    lockStatus,
    lockOwner,
    lockId: lock?._id ?? null,
    hierarchyConflict,
    acquire,
    release,
    refresh,
  };
}
