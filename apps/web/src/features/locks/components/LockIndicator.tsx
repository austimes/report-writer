import { useQuery } from 'convex/react';
import { api } from '@/lib/convex';
import { useLock } from '../hooks/useLock';
import type { Id } from 'convex/_generated/dataModel';

interface LockIndicatorProps {
  resourceType: 'section' | 'block' | 'thread' | 'project' | 'markdown-section' | 'document' | 'node';
  resourceId: string;
  projectId: Id<'projects'>;
  className?: string;
}

export function LockIndicator({
  resourceType,
  resourceId,
  projectId,
  className = '',
}: LockIndicatorProps) {
  const { lockStatus, lockOwner, hierarchyConflict } = useLock(resourceType, resourceId, projectId);
  const owner = useQuery(
    api.tables.users.getById,
    lockOwner ? { id: lockOwner } : 'skip'
  );

  if (lockStatus === 'available') {
    return (
      <div
        className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-gray-100 text-gray-600 ${className}`}
        title="Available"
      >
        <span className="w-2 h-2 rounded-full bg-gray-400" />
        <span>Available</span>
      </div>
    );
  }

  if (lockStatus === 'acquired') {
    return (
      <div
        className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-green-100 text-green-700 ${className}`}
        title="You hold this lock"
      >
        <span className="w-2 h-2 rounded-full bg-green-500" />
        <span>Locked by you</span>
      </div>
    );
  }

  if (lockStatus === 'blocked') {
    return (
      <div
        className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-red-100 text-red-700 ${className}`}
        title={`Locked by ${owner?.name || 'another user'}`}
      >
        <span className="w-2 h-2 rounded-full bg-red-500" />
        <span>Locked by {owner?.name || 'another user'}</span>
      </div>
    );
  }

  if (lockStatus === 'hierarchy-conflict' && hierarchyConflict) {
    const relationText = hierarchyConflict.relation === 'child' ? 'Subsection' : 'Parent';
    return (
      <div
        className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-amber-100 text-amber-700 ${className}`}
        title={`${relationText} "${hierarchyConflict.sectionTitle}" is locked by ${hierarchyConflict.lockedBy}`}
      >
        <span className="w-2 h-2 rounded-full bg-amber-500" />
        <span>{relationText} locked</span>
      </div>
    );
  }

  return null;
}
