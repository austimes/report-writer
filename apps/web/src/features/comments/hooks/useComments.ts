import { useQuery, useMutation } from 'convex/react';
import { api } from '@/lib/convex';
import type { Id } from 'convex/_generated/dataModel';

export function useComments(documentId: Id<'documents'>, filters?: {
  status?: 'open' | 'resolved' | 'deferred';
  assigneeUserId?: Id<'users'>;
  assigneeType?: 'human' | 'agent';
}) {
  const comments = useQuery(api.tables.comments.listByDocument, {
    documentId,
  });

  const createComment = useMutation(api.tables.comments.create);
  const updateComment = useMutation(api.tables.comments.update);
  const resolveComment = useMutation(api.tables.comments.resolve);
  const assignToAgent = useMutation(api.tables.comments.assignToAgent);
  const assignToUser = useMutation(api.tables.comments.assignToUser);

  // Apply client-side filtering for now
  const filteredComments = comments?.filter((c: any) => {
    if (filters?.status && c.status !== filters.status) return false;
    if (filters?.assigneeType && c.assigneeType !== filters.assigneeType) return false;
    if (filters?.assigneeUserId && c.assigneeUserId !== filters.assigneeUserId) return false;
    return true;
  });

  return {
    comments: filteredComments,
    createComment,
    updateComment,
    resolveComment,
    assignToAgent,
    assignToUser,
  };
}
