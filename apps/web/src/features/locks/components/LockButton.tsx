import { useState } from 'react';
import { Button } from '@/shared/components/ui/Button';
import { useLock } from '../hooks/useLock';
import type { Id } from 'convex/_generated/dataModel';

interface LockButtonProps {
  resourceType: 'section' | 'block' | 'thread' | 'project' | 'markdown-section' | 'document' | 'node';
  resourceId: string;
  projectId: Id<'projects'>;
  className?: string;
}

export function LockButton({
  resourceType,
  resourceId,
  projectId,
  className,
}: LockButtonProps) {
  const [isPending, setIsPending] = useState(false);
  const { lockStatus, hierarchyConflict, acquire, release } = useLock(
    resourceType,
    resourceId,
    projectId
  );

  const handleClick = async () => {
    setIsPending(true);
    try {
      if (lockStatus === 'acquired') {
        await release();
      } else if (lockStatus === 'available') {
        await acquire();
      }
    } catch (error) {
      console.error('Lock operation failed:', error);
    } finally {
      setIsPending(false);
    }
  };

  const isDisabled = isPending || lockStatus === 'blocked' || lockStatus === 'hierarchy-conflict';

  const getButtonText = () => {
    if (isPending) return 'Processing...';
    if (lockStatus === 'acquired') return 'Unlock';
    if (lockStatus === 'blocked') return 'Locked by another user';
    if (lockStatus === 'hierarchy-conflict' && hierarchyConflict) {
      const relationText = hierarchyConflict.relation === 'child' ? 'Subsection' : 'Parent section';
      return `${relationText} "${hierarchyConflict.sectionTitle}" locked by ${hierarchyConflict.lockedBy}`;
    }
    return 'Lock';
  };

  const getButtonVariant = () => {
    if (lockStatus === 'acquired') return 'secondary';
    if (lockStatus === 'blocked' || lockStatus === 'hierarchy-conflict') return 'outline';
    return 'default';
  };

  return (
    <Button
      onClick={handleClick}
      disabled={isDisabled}
      variant={getButtonVariant()}
      size="sm"
      className={className}
      title={lockStatus === 'hierarchy-conflict' && hierarchyConflict 
        ? `Cannot lock: ${hierarchyConflict.relation} section "${hierarchyConflict.sectionTitle}" is already locked by ${hierarchyConflict.lockedBy}`
        : undefined
      }
    >
      {getButtonText()}
    </Button>
  );
}
