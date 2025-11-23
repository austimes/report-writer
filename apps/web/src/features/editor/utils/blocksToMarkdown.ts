interface Block {
  _id: string;
  markdownText: string;
  blockType: string;
  order: number;
}

interface Section {
  _id: string;
  headingText: string;
  headingLevel: number;
  order: number;
}

export function blocksToMarkdown(sections: Section[], blocksBySectionId: Map<string, Block[]>): string {
  const lines: string[] = [];

  const sortedSections = [...sections].sort((a, b) => a.order - b.order);

  for (const section of sortedSections) {
    const heading = '#'.repeat(section.headingLevel) + ' ' + section.headingText;
    lines.push(heading);
    lines.push('');

    const blocks = blocksBySectionId.get(section._id) || [];
    const sortedBlocks = [...blocks].sort((a, b) => a.order - b.order);

    for (let i = 0; i < sortedBlocks.length; i++) {
      const block = sortedBlocks[i];
      lines.push(block.markdownText);
      
      // Add blank line between blocks (but not after the last block)
      if (i < sortedBlocks.length - 1) {
        lines.push('');
      }
    }

    lines.push('');
  }

  return lines.join('\n').trim() + '\n';
}
