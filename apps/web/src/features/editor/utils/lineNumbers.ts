export interface LineRange {
  startLine: number;
  endLine: number;
  totalLines: number;
}

export function getLineRange(text: string, startOffset: number, endOffset: number): LineRange {
  const lines = text.split('\n');
  let currentOffset = 0;
  let startLine = -1;
  let endLine = -1;
  
  for (let i = 0; i < lines.length; i++) {
    const lineLength = lines[i].length + 1; // +1 for the newline character
    
    // Find the line containing startOffset
    if (startLine === -1 && currentOffset <= startOffset && startOffset < currentOffset + lineLength) {
      startLine = i + 1;
    }
    
    // Find the line containing endOffset
    if (currentOffset < endOffset && endOffset <= currentOffset + lineLength) {
      endLine = i + 1;
      break;
    }
    
    currentOffset += lineLength;
  }
  
  // Handle edge case: if we didn't find endLine, it's the last line
  if (endLine === -1) {
    endLine = lines.length;
  }
  
  // Handle edge case: if we didn't find startLine, it's line 1
  if (startLine === -1) {
    startLine = 1;
  }
  
  return {
    startLine,
    endLine,
    totalLines: lines.length,
  };
}

export function getLineCount(text: string): number {
  return text.split('\n').length;
}
