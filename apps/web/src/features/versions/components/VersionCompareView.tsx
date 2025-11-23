import { BlockDiff } from './BlockDiff';

interface BlockChange {
  type: 'added' | 'removed' | 'modified';
  blockId: string;
  block?: any;
  oldBlock?: any;
  newBlock?: any;
}

interface VersionCompareViewProps {
  differences: BlockChange[];
  versionA: { summary: string; createdAt: number };
  versionB: { summary: string; createdAt: number };
  onClose: () => void;
}

export function VersionCompareView({
  differences,
  versionA,
  versionB,
  onClose,
}: VersionCompareViewProps) {
  return (
    <div className="fixed inset-0 bg-background z-50 overflow-y-auto">
      <div className="container mx-auto px-4 py-6">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Compare Versions</h1>
          <button
            onClick={onClose}
            className="px-4 py-2 border rounded-md hover:bg-gray-50"
          >
            Close
          </button>
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="p-4 border rounded-lg">
            <h3 className="font-semibold mb-2">Version A</h3>
            <p className="text-sm text-gray-600">{versionA.summary}</p>
            <p className="text-xs text-gray-500">
              {new Date(versionA.createdAt).toLocaleString()}
            </p>
          </div>
          <div className="p-4 border rounded-lg">
            <h3 className="font-semibold mb-2">Version B</h3>
            <p className="text-sm text-gray-600">{versionB.summary}</p>
            <p className="text-xs text-gray-500">
              {new Date(versionB.createdAt).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {differences.length === 0 && (
            <p className="text-center text-gray-500 py-8">No differences found</p>
          )}

          {differences.map((diff, index) => (
            <div key={index} className="border rounded-lg p-4">
              {diff.type === 'added' && (
                <div>
                  <div className="font-semibold text-green-700 mb-2">✓ Block Added</div>
                  <div className="bg-green-50 p-3 rounded">
                    <p className="text-sm">{diff.block?.markdownText}</p>
                  </div>
                </div>
              )}

              {diff.type === 'removed' && (
                <div>
                  <div className="font-semibold text-red-700 mb-2">✗ Block Removed</div>
                  <div className="bg-red-50 p-3 rounded">
                    <p className="text-sm">{diff.block?.markdownText}</p>
                  </div>
                </div>
              )}

              {diff.type === 'modified' && (
                <div>
                  <div className="font-semibold text-blue-700 mb-2">✎ Block Modified</div>
                  <BlockDiff
                    oldText={diff.oldBlock?.markdownText || ''}
                    newText={diff.newBlock?.markdownText || ''}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
