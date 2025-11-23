import { useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from 'convex/react';
import { api } from '../../../lib/convex';
import type { Id } from 'convex/_generated/dataModel';
import { SectionsList } from '../components/SectionsList';
import { BlockEditor } from '../components/BlockEditor';
import { MarkdownPreview } from '../components/MarkdownPreview';
import { useSectionBlocks } from '../hooks/useSectionBlocks';
import { useBlockEditor } from '../hooks/useBlockEditor';
import { blocksToMarkdown } from '../utils/blocksToMarkdown';

export function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = id as Id<"projects">;
  
  const [activeSectionId, setActiveSectionId] = useState<Id<"sections"> | null>(null);

  const project = useQuery(api.tables.projects.getById, projectId ? { id: projectId } : "skip");
  const sections = useQuery(api.tables.sections.listByProject, projectId ? { projectId } : "skip");
  const currentUser = useQuery(api.tables.users.getCurrentUser);
  
  const blocks = useSectionBlocks(activeSectionId);
  const { debouncedSave, immediateSave, saving } = useBlockEditor(currentUser?._id ?? null);

  const activeSection = sections?.find((s: any) => s._id === activeSectionId);

  const allBlocks = useQuery(api.tables.blocks.listByProject, projectId ? { projectId } : "skip");

  const markdownPreview = useMemo(() => {
    if (!sections || !allBlocks) return '';
    
    const blocksBySectionId = new Map<string, typeof allBlocks>();
    
    allBlocks.forEach((block: any) => {
      const sectionBlocks = blocksBySectionId.get(block.sectionId) || [];
      sectionBlocks.push(block);
      blocksBySectionId.set(block.sectionId, sectionBlocks);
    });

    return blocksToMarkdown(sections, blocksBySectionId);
  }, [sections, allBlocks]);

  const handleSectionClick = (sectionId: Id<"sections">) => {
    setActiveSectionId(sectionId);
  };

  const handleBlockSave = (blockId: Id<"blocks">, text: string) => {
    immediateSave(blockId, text);
  };

  const handleBlockBlur = (blockId: Id<"blocks">, text: string) => {
    debouncedSave(blockId, text);
  };

  if (!project) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Loading project...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-xl font-bold">{project.name}</h1>
          {project.description && (
            <p className="text-sm text-muted-foreground">{project.description}</p>
          )}
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-64 flex-shrink-0">
          <SectionsList
            sections={sections || []}
            activeSectionId={activeSectionId}
            onSectionClick={handleSectionClick}
          />
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          {activeSectionId && activeSection ? (
            <div className="max-w-4xl mx-auto space-y-4">
              <div className="mb-6">
                <h2 className="text-2xl font-bold">
                  {'#'.repeat(activeSection.headingLevel)} {activeSection.headingText}
                </h2>
              </div>
              
              {blocks.map((block) => (
                <BlockEditor
                  key={block._id}
                  block={block}
                  onSave={handleBlockSave}
                  onBlur={handleBlockBlur}
                  saving={saving}
                />
              ))}

              {blocks.length === 0 && (
                <p className="text-muted-foreground text-center py-8">
                  No blocks in this section yet.
                </p>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-full">
              <p className="text-muted-foreground">
                {sections && sections.length > 0
                  ? 'Select a section from the sidebar to start editing'
                  : 'No sections available in this project'}
              </p>
            </div>
          )}
        </main>

        <aside className="w-96 flex-shrink-0">
          <MarkdownPreview markdown={markdownPreview} />
        </aside>
      </div>
    </div>
  );
}
