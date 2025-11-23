import { useQuery } from 'convex/react';
import { api } from '@/lib/convex';
import { cn } from '@/shared/utils/cn';
import type { Id } from 'convex/_generated/dataModel';
import { useAgentThread } from '../hooks/useAgentThread';
import { useThreadLock } from '../hooks/useThreadLock';
import { ThreadInput } from './ThreadInput';
import { ForkThreadButton } from './ForkThreadButton';
import { ProposedEditView } from './ProposedEditView';
import { AcceptRejectButtons } from './AcceptRejectButtons';
import { useEffect, useRef } from 'react';

interface MessageItemProps {
  message: any;
  threadId: Id<'agentThreads'>;
}

function MessageItem({ message, threadId }: MessageItemProps) {
  const isUser = message.senderType === 'user';
  const isAgent = message.senderType === 'agent';
  const senderUser = useQuery(
    api.tables.users.getById,
    message.senderUserId ? { id: message.senderUserId } : 'skip'
  );

  return (
    <div
      className={cn(
        'flex',
        isUser && 'justify-start',
        isAgent && 'justify-end'
      )}
    >
      <div
        className={cn(
          'max-w-[80%] rounded-lg px-4 py-3 shadow-sm',
          isUser && 'bg-blue-100 text-blue-900',
          isAgent && 'bg-green-100 text-green-900'
        )}
      >
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-medium">
            {isUser ? senderUser?.name || 'User' : '🤖 Agent'}
          </span>
          <span className="text-xs text-muted-foreground">
            {new Date(message.createdAt).toLocaleTimeString()}
          </span>
        </div>
        <div className="text-sm whitespace-pre-wrap">{message.content}</div>

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-3">
            <ProposedEditView edits={message.toolCalls as any} />
            {!message.appliedEditVersionId && (
              <AcceptRejectButtons
                threadId={threadId}
                messageId={message._id}
              />
            )}
            {message.appliedEditVersionId && (
              <div className="mt-2 text-xs text-green-700 bg-green-50 px-2 py-1 rounded">
                ✓ Edits applied
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface ThreadViewProps {
  threadId: Id<'agentThreads'>;
  projectId: Id<'projects'>;
}

export function ThreadView({ threadId, projectId }: ThreadViewProps) {
  const { thread, messages, sendMessage } = useAgentThread(threadId);
  const { lockStatus, lockOwner, acquire } = useThreadLock(threadId, projectId);
  const lockOwnerUser = useQuery(
    api.tables.users.getById,
    lockOwner ? { id: lockOwner as Id<'users'> } : 'skip'
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const isLocked = lockStatus === 'blocked';
  const canSend = lockStatus === 'acquired';

  const handleSend = async (message: string) => {
    if (!canSend) {
      await acquire();
    }
    await sendMessage(message);
  };

  if (!thread) {
    return <div className="p-4">Loading thread...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b bg-white">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <h2 className="text-lg font-semibold">{thread.title}</h2>
            <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
              <span
                className={cn(
                  'px-2 py-0.5 rounded',
                  thread.status === 'active'
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-700'
                )}
              >
                {thread.status}
              </span>
              {lockStatus === 'blocked' && (
                <span className="text-amber-600">
                  🔒 Locked by {lockOwnerUser?.name || 'another user'}
                </span>
              )}
              {lockStatus === 'acquired' && <span className="text-green-600">✓ You have lock</span>}
            </div>
          </div>
          {isLocked && <ForkThreadButton threadId={threadId} />}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {!messages ? (
          <div className="text-center text-muted-foreground py-8">Loading messages...</div>
        ) : messages.length === 0 ? (
          <div className="text-center text-muted-foreground py-8">
            No messages yet. Start the conversation!
          </div>
        ) : (
          messages.map((message: any) => (
            <MessageItem
              key={message._id}
              message={message}
              threadId={threadId}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <ThreadInput
        onSend={handleSend}
        lockStatus={lockStatus}
        lockOwnerName={lockOwnerUser?.name}
      />
    </div>
  );
}
