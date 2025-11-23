import { useState } from 'react';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import type { Id } from 'convex/_generated/dataModel';

interface CreateVersionButtonProps {
  projectId: Id<'projects'>;
  onCreateVersion: (projectId: Id<'projects'>, summary?: string) => Promise<Id<'reportVersions'>>;
}

export function CreateVersionButton({ projectId, onCreateVersion }: CreateVersionButtonProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [summary, setSummary] = useState('');
  const [loading, setLoading] = useState(false);

  const handleCreate = async () => {
    setLoading(true);
    try {
      await onCreateVersion(projectId, summary || undefined);
      setSummary('');
      setIsModalOpen(false);
    } catch (error) {
      console.error('Failed to create version:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button onClick={() => setIsModalOpen(true)} variant="outline">
        Save Version
      </Button>

      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold mb-4">Create Version Snapshot</h2>
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">
                Summary (optional)
              </label>
              <Input
                type="text"
                placeholder="Describe this version..."
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button
                onClick={() => {
                  setIsModalOpen(false);
                  setSummary('');
                }}
                variant="outline"
                disabled={loading}
              >
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={loading}>
                {loading ? 'Creating...' : 'Create Version'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
