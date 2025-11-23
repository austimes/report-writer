import { Button } from '@/shared/components/ui/Button';
import { useAgentThread } from '../hooks/useAgentThread';
import type { Id } from 'convex/_generated/dataModel';

interface ForkThreadButtonProps {
  threadId: Id<'agentThreads'>;
  onForked?: (newThreadId: Id<'agentThreads'>) => void;
}

export function ForkThreadButton({ threadId, onForked }: ForkThreadButtonProps) {
  const { forkThread } = useAgentThread(threadId);

  const handleFork = async () => {
    try {
      const newThreadId = await forkThread();
      onForked?.(newThreadId);
    } catch (error) {
      console.error('Failed to fork thread:', error);
    }
  };

  return (
    <Button variant="outline" size="sm" onClick={handleFork}>
      🔀 Fork Thread
    </Button>
  );
}
