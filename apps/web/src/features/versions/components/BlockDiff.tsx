interface BlockDiffProps {
  oldText: string;
  newText: string;
}

export function BlockDiff({ oldText, newText }: BlockDiffProps) {
  const words = (text: string) => text.split(/(\s+)/);
  
  const oldWords = words(oldText);
  const newWords = words(newText);
  
  const maxLen = Math.max(oldWords.length, newWords.length);
  const additions: string[] = [];
  const deletions: string[] = [];
  
  for (let i = 0; i < maxLen; i++) {
    if (i < oldWords.length && i < newWords.length) {
      if (oldWords[i] !== newWords[i]) {
        deletions.push(oldWords[i]);
        additions.push(newWords[i]);
      }
    } else if (i < oldWords.length) {
      deletions.push(oldWords[i]);
    } else if (i < newWords.length) {
      additions.push(newWords[i]);
    }
  }

  return (
    <div className="font-mono text-sm">
      {deletions.length > 0 && (
        <div className="bg-red-50 p-2 rounded mb-2">
          <span className="text-red-700">
            {deletions.map((word, i) => (
              <span key={i} className="bg-red-200 px-1">
                [-{word}-]
              </span>
            ))}
          </span>
        </div>
      )}
      {additions.length > 0 && (
        <div className="bg-green-50 p-2 rounded">
          <span className="text-green-700">
            {additions.map((word, i) => (
              <span key={i} className="bg-green-200 px-1">
                [+{word}+]
              </span>
            ))}
          </span>
        </div>
      )}
      {deletions.length === 0 && additions.length === 0 && (
        <div className="text-gray-500 italic">No changes</div>
      )}
    </div>
  );
}
