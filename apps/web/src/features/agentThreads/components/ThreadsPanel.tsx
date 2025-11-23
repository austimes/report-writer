import { useQuery } from 'convex/react';
import { api } from '@/lib/convex';
import { Button } from '@/shared/components/ui/Button';
import { Card } from '@/shared/components/ui/Card';
import { cn } from '@/shared/utils/cn';
import type { Id } from 'convex/_generated/dataModel';
import { useState } from 'react';
import { CreateThreadButton } from './CreateThreadButton';
import { ThreadView } from './ThreadView';

interface ThreadsPanelProps {
  projectId: Id<'projects'>;
}

export function ThreadsPanel({ projectId }: ThreadsPanelProps) {
  const threads = useQuery(api.tables.agentThreads.listByProject, { projectId });
  const [selectedThreadId, setSelectedThreadId] = useState<Id<'agentThreads'> | null>(null);

  if (selectedThreadId) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-2 p-4 border-b">
          <Button variant="outline" size="sm" onClick={() => setSelectedThreadId(null)}>
            ← Back
          </Button>
        </div>
        <ThreadView threadId={selectedThreadId} projectId={projectId} />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="text-lg font-semibold">Agent Threads</h2>
        <CreateThreadButton projectId={projectId} />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {!threads ? (
          <div className="text-sm text-muted-foreground text-center py-8">Loading...</div>
        ) : threads.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-8">
            No threads yet. Create one to get started.
          </div>
        ) : (
          threads.map((thread: any) => (
            <Card
              key={thread._id}
              className={cn(
                'p-4 cursor-pointer hover:border-primary transition-colors',
                thread.status === 'archived' && 'opacity-60'
              )}
              onClick={() => setSelectedThreadId(thread._id)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <h3 className="font-medium truncate">{thread.title}</h3>
                  <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                    <span className={cn(
                      'px-2 py-0.5 rounded',
                      thread.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
                    )}>
                      {thread.status}
                    </span>
                    {thread.anchorSectionId && <span>📍 Section</span>}
                    {thread.anchorCommentId && <span>💬 Comment</span>}
                  </div>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
