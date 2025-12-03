import { useState } from 'react';
import { useQuery } from 'convex/react';
import { api } from '@/lib/convex';
import { Button } from '@/shared/components/ui/Button';
import type { Id } from 'convex/_generated/dataModel';

interface CommentFormProps {
  projectId: Id<'projects'>;
  targetNodeId?: Id<'nodes'>;
  onSubmit: (data: {
    body: string;
    assigneeType?: 'human' | 'agent';
    assigneeUserId?: Id<'users'>;
    linkedNodeIds?: Id<'nodes'>[];
  }) => void;
  onCancel: () => void;
}

export function CommentForm({
  projectId,
  onSubmit,
  onCancel,
}: CommentFormProps) {
  const [body, setBody] = useState('');
  const [assigneeType, setAssigneeType] = useState<'human' | 'agent' | 'none'>('none');
  const [assigneeUserId, setAssigneeUserId] = useState<Id<'users'> | undefined>();
  
  const projectMembers = useQuery(api.tables.projectMembers.listByProject, { projectId });

  const handleSubmit = () => {
    if (!body.trim()) return;

    onSubmit({
      body: body.trim(),
      assigneeType: assigneeType === 'none' ? undefined : assigneeType,
      assigneeUserId: assigneeType === 'human' ? assigneeUserId : undefined,
    });

    setBody('');
    setAssigneeType('none');
    setAssigneeUserId(undefined);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium mb-1">Comment</label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Add a comment..."
          className="w-full px-3 py-2 border rounded-md min-h-[100px]"
          autoFocus
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Assign to</label>
        <select
          value={assigneeType}
          onChange={(e) => {
            const value = e.target.value as 'human' | 'agent' | 'none';
            setAssigneeType(value);
            if (value !== 'human') {
              setAssigneeUserId(undefined);
            }
          }}
          className="w-full px-3 py-2 border rounded-md mb-2"
        >
          <option value="none">Unassigned</option>
          <option value="agent">🤖 Agent</option>
          <option value="human">👤 User</option>
        </select>

        {assigneeType === 'human' && projectMembers && (
          <select
            value={assigneeUserId || ''}
            onChange={(e) => setAssigneeUserId(e.target.value as Id<'users'>)}
            className="w-full px-3 py-2 border rounded-md"
          >
            <option value="">Select user...</option>
            {projectMembers.map((member: any) => (
              <option key={member.userId} value={member.userId}>
                {member.userId}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="flex gap-2 justify-end">
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={handleSubmit} disabled={!body.trim()}>
          Create Comment
        </Button>
      </div>
    </div>
  );
}
