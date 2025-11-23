type BlockType = "paragraph" | "bulletList" | "numberedList" | "table" | "image" | "codeBlock";

export interface ParsedBlock {
  sectionId?: string;
  blockType: BlockType;
  order: number;
  markdownText: string;
}

export interface ParsedSection {
  headingText: string;
  headingLevel: number;
  order: number;
  blocks: ParsedBlock[];
}

export interface ParsedDocument {
  sections: ParsedSection[];
}

export function parseMarkdownToBlocks(markdown: string): ParsedDocument {
  const lines = markdown.split('\n');
  const sections: ParsedSection[] = [];
  let currentSection: ParsedSection | null = null;
  let currentBlockLines: string[] = [];
  let currentBlockType: BlockType | null = null;
  let inCodeBlock = false;
  let blockOrder = 0;

  const flushBlock = () => {
    if (currentBlockLines.length > 0 && currentBlockType && currentSection) {
      currentSection.blocks.push({
        blockType: currentBlockType,
        order: blockOrder++,
        markdownText: currentBlockLines.join('\n'),
      });
      currentBlockLines = [];
      currentBlockType = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Handle code blocks
    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        flushBlock();
        inCodeBlock = true;
        currentBlockType = 'codeBlock';
        currentBlockLines = [line];
      } else {
        currentBlockLines.push(line);
        flushBlock();
        inCodeBlock = false;
      }
      continue;
    }

    if (inCodeBlock) {
      currentBlockLines.push(line);
      continue;
    }

    // Handle headings
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushBlock();
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      
      currentSection = {
        headingText: text,
        headingLevel: level,
        order: sections.length,
        blocks: [],
      };
      sections.push(currentSection);
      blockOrder = 0;
      continue;
    }

    // Skip empty lines between blocks
    if (line.trim() === '') {
      if (currentBlockLines.length > 0) {
        flushBlock();
      }
      continue;
    }

    // Create default section if none exists
    if (!currentSection) {
      currentSection = {
        headingText: 'Introduction',
        headingLevel: 1,
        order: 0,
        blocks: [],
      };
      sections.push(currentSection);
    }

    // Detect block type
    if (!currentBlockType) {
      if (line.match(/^[-*+]\s/)) {
        currentBlockType = 'bulletList';
      } else if (line.match(/^\d+\.\s/)) {
        currentBlockType = 'numberedList';
      } else if (line.match(/^\|.*\|$/)) {
        currentBlockType = 'table';
      } else if (line.match(/^!\[.*\]\(.*\)$/)) {
        currentBlockType = 'image';
      } else {
        currentBlockType = 'paragraph';
      }
    }

    currentBlockLines.push(line);

    // For lists and tables, continue accumulating lines of the same type
    if (currentBlockType === 'bulletList' || currentBlockType === 'numberedList' || currentBlockType === 'table') {
      const nextLine = i + 1 < lines.length ? lines[i + 1] : '';
      const isSameType = 
        (currentBlockType === 'bulletList' && nextLine.match(/^[-*+]\s/)) ||
        (currentBlockType === 'numberedList' && nextLine.match(/^\d+\.\s/)) ||
        (currentBlockType === 'table' && nextLine.match(/^\|.*\|$/));
      
      if (!isSameType && nextLine.trim() !== '') {
        flushBlock();
      }
    } else if (currentBlockType === 'image' || currentBlockType === 'paragraph') {
      // Single-line blocks
      flushBlock();
    }
  }

  // Flush any remaining block
  flushBlock();

  return { sections };
}
