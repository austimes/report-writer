import { Button } from '@/shared/components/ui/Button';
import { useMutation } from 'convex/react';
import { api } from '@/lib/convex';
import type { Id } from 'convex/_generated/dataModel';
import { useState } from 'react';

interface AcceptRejectButtonsProps {
  threadId: Id<'agentThreads'>;
  messageId: Id<'agentMessages'>;
  onAccepted?: () => void;
}

export function AcceptRejectButtons({
  threadId,
  messageId,
  onAccepted,
}: AcceptRejectButtonsProps) {
  const [isApplying, setIsApplying] = useState(false);
  const applyEdits = useMutation(api.features.agent.applyAgentEdits);

  const handleAcceptAll = async () => {
    setIsApplying(true);
    try {
      await applyEdits({ threadId, messageId });
      onAccepted?.();
    } catch (error) {
      console.error('Failed to apply edits:', error);
    } finally {
      setIsApplying(false);
    }
  };

  const handleRejectAll = () => {
    // For now, just close/ignore the edits
    // In the future, this could mark the message as rejected
  };

  return (
    <div className="flex gap-2 mt-4">
      <Button
        onClick={handleAcceptAll}
        disabled={isApplying}
        className="bg-green-600 hover:bg-green-700"
      >
        {isApplying ? 'Applying...' : '✓ Accept All'}
      </Button>
      <Button
        variant="outline"
        onClick={handleRejectAll}
        disabled={isApplying}
        className="border-red-600 text-red-600 hover:bg-red-50"
      >
        ✗ Reject All
      </Button>
    </div>
  );
}
