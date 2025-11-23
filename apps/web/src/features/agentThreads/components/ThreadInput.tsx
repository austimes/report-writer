import { useState } from 'react';
import { Button } from '@/shared/components/ui/Button';
import { cn } from '@/shared/utils/cn';
import type { LockStatus } from '@/features/locks/hooks/useLock';

interface ThreadInputProps {
  onSend: (message: string) => Promise<void>;
  lockStatus: LockStatus;
  lockOwnerName?: string;
  disabled?: boolean;
}

export function ThreadInput({
  onSend,
  lockStatus,
  lockOwnerName,
  disabled = false,
}: ThreadInputProps) {
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);

  const isLocked = lockStatus === 'blocked';
  const isDisabled = disabled || isLocked || isSending;

  const handleSend = async () => {
    if (!message.trim() || isDisabled) return;

    setIsSending(true);
    try {
      await onSend(message.trim());
      setMessage('');
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t p-4 bg-white">
      {isLocked && lockOwnerName && (
        <div className="mb-2 text-sm text-amber-600 bg-amber-50 px-3 py-2 rounded">
          🔒 Locked by {lockOwnerName}
        </div>
      )}

      <div className="flex gap-2">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isLocked ? 'Thread is locked' : 'Type your message...'}
          disabled={isDisabled}
          className={cn(
            'flex-1 resize-none border rounded-md px-3 py-2 text-sm',
            'min-h-[80px] max-h-[200px]',
            isDisabled && 'opacity-50 cursor-not-allowed bg-gray-50'
          )}
        />
        <Button
          onClick={handleSend}
          disabled={isDisabled || !message.trim()}
          className="self-end"
        >
          {isSending ? 'Sending...' : 'Send'}
        </Button>
      </div>

      <div className="mt-1 text-xs text-muted-foreground">
        Press Enter to send, Shift+Enter for new line
      </div>
    </div>
  );
}
