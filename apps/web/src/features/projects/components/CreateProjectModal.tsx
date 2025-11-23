import { useState, FormEvent } from 'react';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Id } from 'convex/_generated/dataModel';

interface CreateProjectModalProps {
  userId: Id<'users'>;
  onClose: () => void;
  onCreate: (ownerId: Id<'users'>, name: string, description?: string) => Promise<void>;
}

export function CreateProjectModal({ userId, onClose, onCreate }: CreateProjectModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await onCreate(userId, name, description || undefined);
      onClose();
    } catch (err) {
      console.error('Failed to create project:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-8 max-w-md w-full">
        <h2 className="text-2xl font-bold mb-6">Create New Project</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Project Name</label>
            <Input
              type="text"
              placeholder="My Project"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Description (optional)</label>
            <textarea
              className="w-full px-3 py-2 border rounded-md"
              rows={4}
              placeholder="Project description..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="flex gap-2 justify-end">
            <Button type="button" onClick={onClose} variant="outline">
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating...' : 'Create Project'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
