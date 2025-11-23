import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/shared/utils/cn';

interface MarkdownPreviewProps {
  markdown: string;
  className?: string;
}

export function MarkdownPreview({ markdown, className }: MarkdownPreviewProps) {
  return (
    <div className={cn("h-full overflow-y-auto border-l bg-card", className)}>
      <div className="p-4 border-b sticky top-0 bg-card z-10">
        <h2 className="font-semibold text-sm text-muted-foreground uppercase">Preview</h2>
      </div>
      <div className="p-6 prose prose-sm max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {markdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}
