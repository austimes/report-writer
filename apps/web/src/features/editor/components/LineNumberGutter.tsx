import { useRef, useEffect } from 'react';

interface LineNumberGutterProps {
  lineCount: number;
  selectedLineRange?: { startLine: number; endLine: number } | null;
  scrollTop: number;
}

export function LineNumberGutter({ lineCount, selectedLineRange, scrollTop }: LineNumberGutterProps) {
  const gutterRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (gutterRef.current) {
      gutterRef.current.scrollTop = scrollTop;
    }
  }, [scrollTop]);

  return (
    <div
      ref={gutterRef}
      className="overflow-hidden border-r bg-gray-100 text-gray-500 font-mono text-sm"
      style={{
        width: '4rem',
        paddingTop: '1rem',
        paddingBottom: '1rem',
        lineHeight: '1.25rem',
        height: 'calc(100vh - 300px)',
      }}
    >
      {Array.from({ length: lineCount }, (_, i) => {
        const lineNumber = i + 1;
        const isSelected =
          selectedLineRange &&
          lineNumber >= selectedLineRange.startLine &&
          lineNumber <= selectedLineRange.endLine;

        return (
          <div
            key={lineNumber}
            className={`px-2 text-right ${isSelected ? 'bg-blue-200 text-blue-900 font-semibold' : ''}`}
            style={{ lineHeight: '1.25rem' }}
          >
            {lineNumber}
          </div>
        );
      })}
    </div>
  );
}
