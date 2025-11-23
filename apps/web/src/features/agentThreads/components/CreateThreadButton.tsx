import { useState } from 'react';
import { useMutation, useQuery } from 'convex/react';
import { api } from '@/lib/convex';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import type { Id } from 'convex/_generated/dataModel';

interface CreateThreadButtonProps {
  projectId: Id<'projects'>;
  anchorSectionId?: Id<'sections'>;
  anchorCommentId?: Id<'comments'>;
  onCreated?: (threadId: Id<'agentThreads'>) => void;
}

export function CreateThreadButton({
  projectId,
  anchorSectionId,
  anchorCommentId,
  onCreated,
}: CreateThreadButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [title, setTitle] = useState('');
  const createThread = useMutation(api.features.agent.createThread);
  const sections = useQuery(api.tables.sections.listByProject, { projectId });
  const [selectedSectionId, setSelectedSectionId] = useState<Id<'sections'> | undefined>(
    anchorSectionId
  );

  const handleCreate = async () => {
    if (!title.trim()) return;

    try {
      const threadId = await createThread({
        projectId,
        title: title.trim(),
        anchorSectionId: selectedSectionId,
        anchorCommentId,
      });
      setTitle('');
      setIsOpen(false);
      onCreated?.(threadId);
    } catch (error) {
      console.error('Failed to create thread:', error);
    }
  };

  if (!isOpen) {
    return (
      <Button onClick={() => setIsOpen(true)} size="sm">
        + Create Thread
      </Button>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md shadow-xl">
        <h3 className="text-lg font-semibold mb-4">Create Agent Thread</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Title</label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Thread title"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleCreate();
                }
              }}
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Anchor to Section (Optional)
            </label>
            <select
              className="w-full px-3 py-2 border rounded-md"
              value={selectedSectionId || ''}
              onChange={(e) =>
                setSelectedSectionId(e.target.value as Id<'sections'> | undefined)
              }
            >
              <option value="">No anchor</option>
              {sections?.map((section: any) => (
                <option key={section._id} value={section._id}>
                  {section.headingText}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={() => {
                setIsOpen(false);
                setTitle('');
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={!title.trim()}>
              Create
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
