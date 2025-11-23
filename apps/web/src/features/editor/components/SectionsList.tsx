import { cn } from '@/shared/utils/cn';
import type { Id } from 'convex/_generated/dataModel';

interface Section {
  _id: Id<"sections">;
  headingText: string;
  headingLevel: number;
  order: number;
}

interface SectionsListProps {
  sections: Section[];
  activeSectionId: Id<"sections"> | null;
  onSectionClick: (sectionId: Id<"sections">) => void;
}

export function SectionsList({ sections, activeSectionId, onSectionClick }: SectionsListProps) {
  const sortedSections = [...sections].sort((a, b) => a.order - b.order);

  return (
    <div className="h-full overflow-y-auto border-r bg-card">
      <div className="p-4 border-b">
        <h2 className="font-semibold text-sm text-muted-foreground uppercase">Sections</h2>
      </div>
      <nav className="p-2">
        {sortedSections.map((section) => (
          <button
            key={section._id}
            onClick={() => onSectionClick(section._id)}
            className={cn(
              "w-full text-left px-3 py-2 rounded-md text-sm transition-colors mb-1",
              "hover:bg-accent hover:text-accent-foreground",
              activeSectionId === section._id && "bg-accent text-accent-foreground font-medium",
              section.headingLevel === 2 && "pl-6",
              section.headingLevel === 3 && "pl-9",
              section.headingLevel === 4 && "pl-12",
              section.headingLevel === 5 && "pl-15",
              section.headingLevel === 6 && "pl-18"
            )}
          >
            <span className="text-muted-foreground mr-2">H{section.headingLevel}</span>
            {section.headingText}
          </button>
        ))}
      </nav>
    </div>
  );
}
