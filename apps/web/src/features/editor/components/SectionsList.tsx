import { cn } from '@/shared/utils/cn';
import type { Id } from 'convex/_generated/dataModel';
import { useMemo } from 'react';
import { parseMarkdownSections, type Section as ParsedSection } from '../utils/sectionParser';

interface Node {
  _id: Id<"nodes">;
  nodeType: string;
  text?: string;
  order: number;
  attrs?: { level?: number };
}

interface NodesListProps {
  nodes: Node[];
  activeNodeId: Id<"nodes"> | null;
  onNodeClick: (nodeId: Id<"nodes"> | null, section?: ParsedSection) => void;
  liveMarkdown?: string;
  selectedSectionId?: string | null;
}

export function SectionsList({ nodes, activeNodeId, onNodeClick, liveMarkdown, selectedSectionId }: NodesListProps) {
  const parsedSections = useMemo(() => {
    if (!liveMarkdown) return null;
    return parseMarkdownSections(liveMarkdown);
  }, [liveMarkdown]);

  const headingNodes = useMemo(() => {
    return nodes
      .filter(n => n.nodeType === 'heading')
      .sort((a, b) => a.order - b.order);
  }, [nodes]);

  const renderParsedSection = (section: ParsedSection, level: number = 0) => {
    const isSelected = selectedSectionId === section.id;
    
    return (
      <div key={section.id}>
        <button
          onClick={() => onNodeClick(null, section)}
          className={cn(
            "w-full text-left px-3 py-2 rounded-md text-sm transition-colors mb-1",
            "hover:bg-accent hover:text-accent-foreground",
            isSelected && "bg-accent text-accent-foreground font-medium",
            section.depth === 1 && "pl-3",
            section.depth === 2 && "pl-6",
            section.depth === 3 && "pl-9",
            section.depth === 4 && "pl-12",
            section.depth === 5 && "pl-15",
            section.depth === 6 && "pl-18"
          )}
        >
          <span className="text-muted-foreground mr-2">H{section.depth}</span>
          {section.title}
        </button>
        {section.children.map(child => renderParsedSection(child, level + 1))}
      </div>
    );
  };

  if (parsedSections) {
    return (
      <div className="h-full overflow-y-auto border-r bg-card">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-sm text-muted-foreground uppercase">Sections</h2>
        </div>
        <nav className="p-2">
          <button
            onClick={() => onNodeClick(null)}
            className={cn(
              "w-full text-left px-3 py-2 rounded-md text-sm transition-colors mb-1",
              "hover:bg-accent hover:text-accent-foreground",
              !selectedSectionId && activeNodeId === null && "bg-accent text-accent-foreground font-medium"
            )}
          >
            <span className="text-muted-foreground mr-2">📄</span>
            Full Document
          </button>
          {parsedSections.map(section => renderParsedSection(section))}
        </nav>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto border-r bg-card">
      <div className="p-4 border-b">
        <h2 className="font-semibold text-sm text-muted-foreground uppercase">Sections</h2>
      </div>
      <nav className="p-2">
        <button
          onClick={() => onNodeClick(null)}
          className={cn(
            "w-full text-left px-3 py-2 rounded-md text-sm transition-colors mb-1",
            "hover:bg-accent hover:text-accent-foreground",
            activeNodeId === null && "bg-accent text-accent-foreground font-medium"
          )}
        >
          <span className="text-muted-foreground mr-2">📄</span>
          Full Document
        </button>
        {headingNodes.map((node) => {
          const level = node.attrs?.level ?? 1;
          return (
            <button
              key={node._id}
              onClick={() => onNodeClick(node._id)}
              className={cn(
                "w-full text-left px-3 py-2 rounded-md text-sm transition-colors mb-1",
                "hover:bg-accent hover:text-accent-foreground",
                activeNodeId === node._id && "bg-accent text-accent-foreground font-medium",
                level === 1 && "pl-3",
                level === 2 && "pl-6",
                level === 3 && "pl-9",
                level === 4 && "pl-12",
                level === 5 && "pl-15",
                level === 6 && "pl-18"
              )}
            >
              <span className="text-muted-foreground mr-2">H{level}</span>
              {node.text || '(untitled)'}
            </button>
          );
        })}
      </nav>
    </div>
  );
}
