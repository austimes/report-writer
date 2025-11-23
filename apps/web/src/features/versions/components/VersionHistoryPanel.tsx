import { useState } from 'react';
import { Button } from '@/shared/components/ui/Button';
import { VersionRestoreModal } from './VersionRestoreModal';
import type { Id } from 'convex/_generated/dataModel';

interface Version {
  _id: Id<'reportVersions'>;
  summary: string;
  createdAt: number;
  createdByUserId: Id<'users'>;
}

interface VersionHistoryPanelProps {
  versions: Version[];
  onRestore: (versionId: Id<'reportVersions'>) => Promise<void>;
  onCompare: (versionA: Id<'reportVersions'>, versionB: Id<'reportVersions'>) => void;
  onClose?: () => void;
}

export function VersionHistoryPanel({
  versions,
  onRestore,
  onCompare,
  onClose,
}: VersionHistoryPanelProps) {
  const [selectedVersion, setSelectedVersion] = useState<Version | null>(null);
  const [compareVersionA, setCompareVersionA] = useState<Id<'reportVersions'> | null>(null);

  const handleVersionClick = (version: Version) => {
    if (compareVersionA === null) {
      setCompareVersionA(version._id);
    } else if (compareVersionA === version._id) {
      setCompareVersionA(null);
    } else {
      onCompare(compareVersionA, version._id);
      setCompareVersionA(null);
    }
  };

  return (
    <div className="h-full flex flex-col bg-card border-l">
      <div className="p-4 border-b flex items-center justify-between">
        <h2 className="text-lg font-bold">Version History</h2>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {versions.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">
            No versions saved yet
          </p>
        )}

        {compareVersionA && (
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-sm">
            Select another version to compare
          </div>
        )}

        {versions.map((version) => {
          const isSelected = compareVersionA === version._id;
          
          return (
            <div
              key={version._id}
              className={`p-3 border rounded-lg cursor-pointer transition-colors ${
                isSelected
                  ? 'bg-blue-50 border-blue-300'
                  : 'hover:bg-gray-50'
              }`}
              onClick={() => handleVersionClick(version)}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <p className="font-medium text-sm">{version.summary}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(version.createdAt).toLocaleString()}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedVersion(version);
                  }}
                >
                  Restore
                </Button>
              </div>
            </div>
          );
        })}
      </div>

      {selectedVersion && (
        <VersionRestoreModal
          version={selectedVersion}
          onRestore={onRestore}
          onCancel={() => setSelectedVersion(null)}
        />
      )}
    </div>
  );
}
