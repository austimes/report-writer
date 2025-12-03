interface Node {
  _id: string;
  nodeType: string;
  text?: string;
  attrs?: Record<string, unknown>;
  parentId?: string;
  order: number;
}

export function nodesToMarkdown(nodes: Node[]): string {
  const rootNode = nodes.find(n => n.nodeType === 'document');
  
  if (!rootNode) {
    return '';
  }

  const lines: string[] = [];

  function getChildren(parentId: string): Node[] {
    return nodes
      .filter(n => n.parentId === parentId)
      .sort((a, b) => a.order - b.order);
  }

  function serializeNode(node: Node, indent: number = 0): void {
    switch (node.nodeType) {
      case 'document':
        for (const child of getChildren(node._id)) {
          serializeNode(child, indent);
        }
        break;

      case 'heading': {
        const level = (node.attrs?.level as number) ?? 1;
        lines.push('#'.repeat(level) + ' ' + (node.text || ''));
        lines.push('');
        for (const child of getChildren(node._id)) {
          serializeNode(child, indent);
        }
        break;
      }

      case 'paragraph':
        lines.push(node.text || '');
        lines.push('');
        break;

      case 'bulletList':
        for (const child of getChildren(node._id)) {
          serializeNode(child, indent);
        }
        lines.push('');
        break;

      case 'numberedList': {
        const children = getChildren(node._id);
        children.forEach((child, idx) => {
          serializeListItem(child, indent, `${idx + 1}.`);
        });
        lines.push('');
        break;
      }

      case 'listItem':
        lines.push('  '.repeat(indent) + '- ' + (node.text || ''));
        for (const child of getChildren(node._id)) {
          serializeNode(child, indent + 1);
        }
        break;

      case 'codeBlock': {
        const lang = (node.attrs?.language as string) || '';
        lines.push('```' + lang);
        lines.push(node.text || '');
        lines.push('```');
        lines.push('');
        break;
      }

      case 'table':
        // TODO: Implement table serialization
        lines.push('[table]');
        lines.push('');
        break;

      case 'image': {
        const src = node.attrs?.src as string || '';
        const alt = node.attrs?.alt as string || '';
        lines.push(`![${alt}](${src})`);
        lines.push('');
        break;
      }

      default:
        if (node.text) {
          lines.push(node.text);
          lines.push('');
        }
    }
  }

  function serializeListItem(node: Node, indent: number, prefix: string): void {
    lines.push('  '.repeat(indent) + prefix + ' ' + (node.text || ''));
    for (const child of getChildren(node._id)) {
      serializeNode(child, indent + 1);
    }
  }

  serializeNode(rootNode);

  return lines.join('\n').trim() + '\n';
}

// Keep old export for compatibility during migration
export function blocksToMarkdown(_sections: unknown[], _blocksBySectionId: Map<string, unknown[]>): string {
  // Deprecated - just return empty for now
  return '';
}
