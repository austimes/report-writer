import { useState } from 'react';
import { CommentThread } from './CommentThread';
import { CreateCommentButton } from './CreateCommentButton';
import { useComments } from '../hooks/useComments';
import type { Id } from 'convex/_generated/dataModel';

interface CommentsPanelProps {
  projectId: Id<'projects'>;
  documentId: Id<'documents'>;
  onCommentClick?: (commentId: Id<'comments'>) => void;
  onCreateThread?: (commentId: Id<'comments'>) => void;
}

export function CommentsPanel({
  projectId,
  documentId,
  onCommentClick,
  onCreateThread,
}: CommentsPanelProps) {
  const [statusFilter, setStatusFilter] = useState<'open' | 'resolved' | 'deferred' | 'all'>('all');
  const [assigneeFilter, setAssigneeFilter] = useState<'all' | 'agent' | 'unassigned'>('all');

  const filters: any = {};
  if (statusFilter !== 'all') {
    filters.status = statusFilter;
  }
  if (assigneeFilter === 'agent') {
    filters.assigneeType = 'agent';
  }

  const {
    comments,
    createComment,
    assignToAgent,
    assignToUser,
    resolveComment,
  } = useComments(documentId, filters);

  const handleCreate = async (data: any) => {
    await createComment({
      documentId,
      ...data,
    });
  };

  const handleAssign = async (commentId: Id<'comments'>, assigneeType: 'human' | 'agent', userId?: Id<'users'>) => {
    if (assigneeType === 'agent') {
      await assignToAgent({ id: commentId });
    } else if (userId) {
      await assignToUser({ id: commentId, userId });
    }
  };

  const handleResolve = async (commentId: Id<'comments'>, summary?: string) => {
    await resolveComment({ id: commentId, resolutionSummary: summary });
  };

  const openComments = comments?.filter((c: any) => c.status === 'open') || [];

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b">
        <div>
          <h2 className="text-lg font-semibold">Comments</h2>
          <p className="text-xs text-muted-foreground">
            {openComments.length} open
          </p>
        </div>
        <CreateCommentButton projectId={projectId} onCreate={handleCreate} />
      </div>

      <div className="p-4 border-b space-y-2">
        <div>
          <label className="block text-xs font-medium mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="w-full px-2 py-1 text-sm border rounded-md"
          >
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="resolved">Resolved</option>
            <option value="deferred">Deferred</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium mb-1">Assignee</label>
          <select
            value={assigneeFilter}
            onChange={(e) => setAssigneeFilter(e.target.value as any)}
            className="w-full px-2 py-1 text-sm border rounded-md"
          >
            <option value="all">All</option>
            <option value="agent">Agent</option>
            <option value="unassigned">Unassigned</option>
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {!comments ? (
          <div className="text-sm text-muted-foreground text-center py-8">Loading...</div>
        ) : comments.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-8">
            No comments yet. Create one to get started.
          </div>
        ) : (
          comments.map((comment: any) => (
            <CommentThread
              key={comment._id}
              comment={comment}
              onAssign={(assigneeType, userId) => handleAssign(comment._id, assigneeType, userId)}
              onResolve={(summary) => handleResolve(comment._id, summary)}
              onCreateThread={onCreateThread ? () => onCreateThread(comment._id) : undefined}
              onClick={onCommentClick ? () => onCommentClick(comment._id) : undefined}
            />
          ))
        )}
      </div>
    </div>
  );
}
