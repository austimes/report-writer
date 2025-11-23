import { useState } from 'react';
import { Button } from '@/shared/components/ui/Button';
import type { Id } from 'convex/_generated/dataModel';

interface Version {
  _id: Id<'reportVersions'>;
  summary: string;
  createdAt: number;
  createdByUserId: Id<'users'>;
}

interface VersionRestoreModalProps {
  version: Version;
  onRestore: (versionId: Id<'reportVersions'>) => Promise<void>;
  onCancel: () => void;
}

export function VersionRestoreModal({ version, onRestore, onCancel }: VersionRestoreModalProps) {
  const [loading, setLoading] = useState(false);

  const handleRestore = async () => {
    setLoading(true);
    try {
      await onRestore(version._id);
    } catch (error) {
      console.error('Failed to restore version:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h2 className="text-xl font-bold mb-4">Restore Version</h2>
        <div className="mb-6">
          <div className="mb-2">
            <span className="font-medium">Version:</span> {version.summary}
          </div>
          <div className="mb-2">
            <span className="font-medium">Created:</span>{' '}
            {new Date(version.createdAt).toLocaleString()}
          </div>
          <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
            <p className="text-sm text-yellow-800">
              ⚠️ Warning: This will overwrite the current project state. The current state will
              be saved as a new version before restoring.
            </p>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <Button onClick={onCancel} variant="outline" disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleRestore} disabled={loading}>
            {loading ? 'Restoring...' : 'Restore'}
          </Button>
        </div>
      </div>
    </div>
  );
}
