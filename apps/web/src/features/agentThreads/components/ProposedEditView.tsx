import type { Id } from 'convex/_generated/dataModel';

interface BlockEdit {
  type: 'edit_block';
  blockId: Id<'blocks'>;
  oldText: string;
  newText: string;
}

interface ProposedEditViewProps {
  edits: BlockEdit[];
  onAccept?: (blockId: Id<'blocks'>) => void;
  onReject?: (blockId: Id<'blocks'>) => void;
  showActions?: boolean;
}

export function ProposedEditView({
  edits,
  onAccept,
  onReject,
  showActions = false,
}: ProposedEditViewProps) {
  if (!edits || edits.length === 0) {
    return null;
  }

  return (
    <div className="mt-4 space-y-4">
      <div className="text-sm font-medium">Proposed Edits:</div>
      {edits.map((edit, idx) => (
        <div key={idx} className="border rounded-lg overflow-hidden">
          <div className="bg-gray-50 px-3 py-2 text-xs text-muted-foreground border-b">
            Block {edit.blockId}
          </div>

          <div className="divide-y">
            <div className="p-3 bg-red-50">
              <div className="text-xs font-medium text-red-700 mb-1">- Original</div>
              <div className="text-sm font-mono text-red-900 whitespace-pre-wrap">
                {edit.oldText}
              </div>
            </div>

            <div className="p-3 bg-green-50">
              <div className="text-xs font-medium text-green-700 mb-1">+ Proposed</div>
              <div className="text-sm font-mono text-green-900 whitespace-pre-wrap">
                {edit.newText}
              </div>
            </div>
          </div>

          {showActions && (
            <div className="flex gap-2 p-3 bg-gray-50 border-t">
              <button
                onClick={() => onAccept?.(edit.blockId)}
                className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
              >
                Accept
              </button>
              <button
                onClick={() => onReject?.(edit.blockId)}
                className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
              >
                Reject
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
