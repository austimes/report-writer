import { useState, FormEvent } from 'react';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { Id } from 'convex/_generated/dataModel';

interface InviteCollaboratorModalProps {
  projectId: Id<'projects'>;
  onClose: () => void;
  onInvite: (args: { projectId: Id<'projects'>; userId: Id<'users'>; role: 'owner' | 'editor' | 'viewer' }) => Promise<Id<'projectMembers'> | void>;
}

export function InviteCollaboratorModal({ projectId, onClose, onInvite }: InviteCollaboratorModalProps) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'owner' | 'editor' | 'viewer'>('editor');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const mockUserId = '1' as Id<'users'>;
      await onInvite({ projectId, userId: mockUserId, role });
      onClose();
    } catch (err) {
      console.error('Failed to invite collaborator:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-8 max-w-md w-full">
        <h2 className="text-2xl font-bold mb-6">Invite Collaborator</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Email</label>
            <Input
              type="email"
              placeholder="collaborator@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-2">Role</label>
            <select
              className="w-full px-3 py-2 border rounded-md"
              value={role}
              onChange={(e) => setRole(e.target.value as 'owner' | 'editor' | 'viewer')}
            >
              <option value="viewer">Viewer</option>
              <option value="editor">Editor</option>
              <option value="owner">Owner</option>
            </select>
          </div>
          <div className="flex gap-2 justify-end">
            <Button type="button" onClick={onClose} variant="outline">
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Inviting...' : 'Invite'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
