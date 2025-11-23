import { useState, useRef, useEffect } from 'react';
import { cn } from '@/shared/utils/cn';
import type { Id } from 'convex/_generated/dataModel';

interface Block {
  _id: Id<"blocks">;
  markdownText: string;
  blockType: string;
  order: number;
  lastEditedAt: number;
  lastEditorUserId: Id<"users">;
  lastEditType: "human" | "agent";
}

interface BlockEditorProps {
  block: Block;
  onSave: (blockId: Id<"blocks">, text: string) => void;
  onBlur: (blockId: Id<"blocks">, text: string) => void;
  saving?: boolean;
}

const blockTypeLabels: Record<string, string> = {
  paragraph: "P",
  bulletList: "UL",
  numberedList: "OL",
  table: "Table",
  image: "Image",
  codeBlock: "Code",
};

const blockTypeColors: Record<string, string> = {
  paragraph: "bg-blue-100 text-blue-700",
  bulletList: "bg-green-100 text-green-700",
  numberedList: "bg-green-100 text-green-700",
  table: "bg-purple-100 text-purple-700",
  image: "bg-pink-100 text-pink-700",
  codeBlock: "bg-gray-100 text-gray-700",
};

export function BlockEditor({ block, onSave, onBlur, saving }: BlockEditorProps) {
  const [text, setText] = useState(block.markdownText);
  const [isFocused, setIsFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setText(block.markdownText);
  }, [block.markdownText]);

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
    if (text !== block.markdownText) {
      onBlur(block._id, text);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      onSave(block._id, text);
    }
  };

  const lastEditTime = new Date(block.lastEditedAt).toLocaleString();
  const blockTypeLabel = blockTypeLabels[block.blockType] || block.blockType;
  const blockTypeColor = blockTypeColors[block.blockType] || "bg-gray-100 text-gray-700";

  return (
    <div
      className={cn(
        "group relative border rounded-lg p-4 transition-all",
        isFocused ? "border-primary shadow-md" : "border-border hover:border-primary/50",
        saving && "opacity-50"
      )}
    >
      <div className="flex items-start gap-2 mb-2">
        <span className={cn("text-xs px-2 py-1 rounded font-medium", blockTypeColor)}>
          {blockTypeLabel}
        </span>
        <span className="text-xs text-muted-foreground">#{block.order}</span>
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
        className={cn(
          "w-full resize-none bg-transparent border-none outline-none",
          "font-mono text-sm leading-relaxed",
          block.blockType === 'codeBlock' && "font-mono bg-muted p-2 rounded"
        )}
        rows={1}
      />

      <div className="opacity-0 group-hover:opacity-100 transition-opacity mt-2 text-xs text-muted-foreground">
        Last edited {lastEditTime} by {block.lastEditType}
      </div>
    </div>
  );
}
