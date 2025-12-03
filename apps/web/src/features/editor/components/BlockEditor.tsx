import { useState, useRef, useEffect } from 'react';
import { cn } from '@/shared/utils/cn';
import type { Id } from 'convex/_generated/dataModel';

interface Node {
  _id: Id<"nodes">;
  text?: string;
  nodeType: string;
  order: number;
  lastEditedAt?: number;
  lastEditorUserId?: Id<"users">;
  lastEditType?: "human" | "agent";
}

interface BlockEditorProps {
  node: Node;
  onSave: (nodeId: Id<"nodes">, text: string) => void;
  onBlur: (nodeId: Id<"nodes">, text: string) => void;
  saving?: boolean;
  disabled?: boolean;
}

const nodeTypeLabels: Record<string, string> = {
  paragraph: "P",
  bulletList: "UL",
  numberedList: "OL",
  table: "Table",
  image: "Image",
  codeBlock: "Code",
};

const nodeTypeColors: Record<string, string> = {
  paragraph: "bg-blue-100 text-blue-700",
  bulletList: "bg-green-100 text-green-700",
  numberedList: "bg-green-100 text-green-700",
  table: "bg-purple-100 text-purple-700",
  image: "bg-pink-100 text-pink-700",
  codeBlock: "bg-gray-100 text-gray-700",
};

export function BlockEditor({ node, onSave, onBlur, saving, disabled = false }: BlockEditorProps) {
  const [text, setText] = useState(node.text ?? '');
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setText(node.text ?? '');
  }, [node.text]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [text]);

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
  };

  const handleBlur = () => {
    setIsFocused(false);
    if (text !== node.text) {
      onBlur(node._id, text);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      onSave(node._id, text);
    }
  };

  const lastEditTime = node.lastEditedAt ? new Date(node.lastEditedAt).toLocaleString() : 'never';
  const nodeTypeLabel = nodeTypeLabels[node.nodeType] || node.nodeType;
  const nodeTypeColor = nodeTypeColors[node.nodeType] || "bg-gray-100 text-gray-700";

  return (
    <div
      className={cn(
        "group relative border rounded-lg p-4 transition-all",
        isFocused && !disabled ? "border-primary shadow-md" : "border-border hover:border-primary/50",
        saving && "opacity-50",
        disabled && "opacity-60 bg-gray-50"
      )}
    >
      <div className="flex items-start gap-2 mb-2">
        <span className={cn("text-xs px-2 py-1 rounded font-medium", nodeTypeColor)}>
          {nodeTypeLabel}
        </span>
        <span className="text-xs text-muted-foreground">#{node.order}</span>
        {saving && (
          <span className="text-xs text-muted-foreground ml-auto">Saving...</span>
        )}
      </div>
      
      <textarea
        ref={textareaRef}
        value={text}
        onChange={handleChange}
        onFocus={() => setIsFocused(true)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className={cn(
          "w-full resize-none bg-transparent border-none outline-none",
          "font-mono text-sm leading-relaxed",
          node.nodeType === 'codeBlock' && "font-mono bg-muted p-2 rounded",
          disabled && "cursor-not-allowed"
        )}
        rows={1}
      />

      <div className="opacity-0 group-hover:opacity-100 transition-opacity mt-2 text-xs text-muted-foreground">
        Last edited {lastEditTime} by {node.lastEditType ?? 'unknown'}
      </div>
    </div>
  );
}
