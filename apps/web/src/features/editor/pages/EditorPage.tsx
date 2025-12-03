import { useState, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from 'convex/react';
import { api } from '../../../lib/convex';
import type { Id } from 'convex/_generated/dataModel';
import { SectionsList } from '../components/SectionsList';
import { BlockEditor } from '../components/BlockEditor';
import { MarkdownPreview } from '../components/MarkdownPreview';
import { LineNumberGutter } from '../components/LineNumberGutter';
import { useChildNodes } from '../hooks/useSectionBlocks';
import { useBlockEditor } from '../hooks/useBlockEditor';
import { nodesToMarkdown } from '../utils/blocksToMarkdown';
import { LockButton } from '../../locks/components/LockButton';
import { LockIndicator } from '../../locks/components/LockIndicator';
import { useLock } from '../../locks/hooks/useLock';
import { VersionHistoryPanel } from '../../versions/components/VersionHistoryPanel';
import { VersionCompareView } from '../../versions/components/VersionCompareView';
import { CreateVersionButton } from '../../versions/components/CreateVersionButton';
import { useVersions } from '../../versions/hooks/useVersions';
import { useVersionComparison } from '../../versions/hooks/useVersionComparison';
import { ThreadsPanel } from '../../agentThreads';
import { CommentsPanel } from '../../comments';
import { Button } from '@/shared/components/ui/Button';
import type { Section } from '../utils/sectionParser';
import { getLineRange, getLineCount } from '../utils/lineNumbers';

export function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = id as Id<"projects">;
  
  const [activeNodeId, setActiveNodeId] = useState<Id<"nodes"> | null>(null);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [showAgentThreads, setShowAgentThreads] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [compareVersions, setCompareVersions] = useState<{
    versionA: Id<'reportVersions'>;
    versionB: Id<'reportVersions'>;
  } | null>(null);
  const [fullDocumentMarkdown, setFullDocumentMarkdown] = useState<string>('');
  const [selectedSection, setSelectedSection] = useState<Section | null>(null);
  const [textareaScrollTop, setTextareaScrollTop] = useState(0);
  
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const project = useQuery(api.tables.projects.getById, projectId ? { id: projectId } : "skip");
  const documents = useQuery(api.tables.documents.listByProject, projectId ? { projectId } : "skip");
  const currentUser = useQuery(api.tables.users.getCurrentUser);
  
  // For now, use the first document in the project (or create one)
  const currentDocument = documents?.[0];
  const documentId = currentDocument?._id;
  
  // Get all nodes for the current document
  const allNodes = useQuery(
    api.tables.nodes.listByDocument, 
    documentId ? { documentId } : "skip"
  );
  
  // Get children of active node (for block-level editing)
  const childNodes = useChildNodes(activeNodeId);
  const { debouncedSave, immediateSave, saving } = useBlockEditor(currentUser?._id ?? null);

  const { versions, createVersion, restoreVersion } = useVersions(projectId, documentId);
  const comparison = useVersionComparison(
    compareVersions?.versionA ?? null,
    compareVersions?.versionB ?? null
  );
  const createThread = useMutation(api.features.agent.createThread);

  const activeNode = allNodes?.find((n) => n._id === activeNodeId);
  
  const nodeLock = useLock(
    'node',
    activeNodeId ?? '',
    projectId
  );

  const documentLock = useLock(
    'document',
    documentId ?? '',
    projectId
  );

  const selectedSectionLock = useLock(
    'markdown-section',
    selectedSection?.id ?? '',
    projectId
  );
  
  const canEdit = !activeNodeId || nodeLock.lockStatus === 'acquired';
  const canEditFullDocument = documentLock.lockStatus === 'acquired';
  const canEditSelectedSection = !selectedSection || selectedSectionLock.lockStatus === 'acquired';

  const markdownPreview = useMemo(() => {
    if (!allNodes) return '';
    
    const markdown = nodesToMarkdown(allNodes);
    if (canEditFullDocument && fullDocumentMarkdown === '') {
      setFullDocumentMarkdown(markdown);
    }
    return markdown;
  }, [allNodes, canEditFullDocument, fullDocumentMarkdown]);

  const currentMarkdown = canEditFullDocument ? fullDocumentMarkdown : markdownPreview;
  const lineCount = getLineCount(currentMarkdown);
  
  const selectedLineRange = selectedSection
    ? getLineRange(currentMarkdown, selectedSection.startOffset, selectedSection.endOffset)
    : (!activeNodeId ? { startLine: 1, endLine: lineCount, totalLines: lineCount } : null);

  const handleNodeClick = (nodeId: Id<"nodes"> | null, section?: Section) => {
    if (section) {
      setSelectedSection(section);
      
      if (textareaRef.current) {
        textareaRef.current.focus();
        const lineHeight = 20;
        const linesBeforeSection = fullDocumentMarkdown.substring(0, section.startOffset).split('\n').length;
        textareaRef.current.scrollTop = Math.max(0, (linesBeforeSection - 5) * lineHeight);
      }
    } else {
      setActiveNodeId(nodeId);
      setSelectedSection(null);
    }
  };

  const handleNodeSave = (nodeId: Id<"nodes">, text: string) => {
    immediateSave(nodeId, text);
  };

  const handleNodeBlur = (nodeId: Id<"nodes">, text: string) => {
    debouncedSave(nodeId, text);
  };

  const handleCompare = (versionA: Id<'reportVersions'>, versionB: Id<'reportVersions'>) => {
    setCompareVersions({ versionA, versionB });
  };

  const handleRestore = async (versionId: Id<'reportVersions'>) => {
    await restoreVersion({ versionId });
    setShowVersionHistory(false);
  };

  const handleSaveFullDocument = async () => {
    if (!currentUser || !documentId) {
      alert('You must be logged in and have a document to save');
      return;
    }
    try {
      // TODO: Implement updateFullDocument for nodes model
      // For now, just reset
      setFullDocumentMarkdown('');
      await documentLock.release();
    } catch (error) {
      console.error('Failed to save full document:', error);
      alert('Failed to save document: ' + (error as Error).message);
    }
  };

  if (!project) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Loading project...</p>
      </div>
    );
  }

  if (documents && documents.length === 0) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">No documents in this project yet.</p>
          <Button onClick={() => navigate('/projects')}>Back to Projects</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/projects')}
              className="text-muted-foreground hover:text-foreground transition-colors"
              title="Back to projects"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-6 h-6">
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
            </button>
            <div>
              <h1 className="text-xl font-bold">{project.name}</h1>
              {project.description && (
                <p className="text-sm text-muted-foreground">{project.description}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {documentId && (
              <CreateVersionButton 
                projectId={projectId}
                documentId={documentId}
                onCreateVersion={(pid, docId, summary) => createVersion({ projectId: pid, documentId: docId, summary })} 
              />
            )}
            <button
              onClick={() => setShowVersionHistory(!showVersionHistory)}
              className="px-4 py-2 border rounded-md hover:bg-gray-50"
            >
              {showVersionHistory ? 'Hide History' : 'Version History'}
            </button>
            <button
              onClick={() => setShowAgentThreads(!showAgentThreads)}
              className="px-4 py-2 border rounded-md hover:bg-gray-50"
            >
              {showAgentThreads ? 'Hide Threads' : '🤖 Agent Threads'}
            </button>
            <button
              onClick={() => setShowComments(!showComments)}
              className="px-4 py-2 border rounded-md hover:bg-gray-50"
            >
              {showComments ? 'Hide Comments' : '💬 Comments'}
            </button>
            <button
              onClick={() => navigate(`/projects/${projectId}/settings`)}
              className="px-4 py-2 border rounded-md hover:bg-gray-50"
              title="Project Settings"
            >
              ⚙️ Settings
            </button>
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-64 flex-shrink-0">
          <SectionsList
            nodes={allNodes || []}
            activeNodeId={activeNodeId}
            onNodeClick={handleNodeClick}
            liveMarkdown={canEditFullDocument ? fullDocumentMarkdown : markdownPreview}
            selectedSectionId={selectedSection?.id ?? null}
          />
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          {activeNodeId && activeNode ? (
            <div className="max-w-4xl mx-auto space-y-4">
              <div className="mb-6 flex items-center justify-between">
                <h2 className="text-2xl font-bold">
                  {activeNode.nodeType === 'heading' && activeNode.attrs?.level 
                    ? '#'.repeat(activeNode.attrs.level as number) + ' ' 
                    : ''}{activeNode.text || `(${activeNode.nodeType})`}
                </h2>
                <div className="flex items-center gap-3">
                  <LockIndicator
                    resourceType="node"
                    resourceId={activeNodeId}
                    projectId={projectId}
                  />
                  <LockButton
                    resourceType="node"
                    resourceId={activeNodeId}
                    projectId={projectId}
                  />
                </div>
              </div>
              
              {!canEdit && (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-yellow-800">
                  This node is locked. You need to acquire the lock to edit.
                </div>
              )}
              
              {childNodes.map((node) => (
                <BlockEditor
                  key={node._id}
                  node={node}
                  onSave={handleNodeSave}
                  onBlur={handleNodeBlur}
                  saving={saving}
                  disabled={!canEdit}
                />
              ))}

              {childNodes.length === 0 && (
                <p className="text-muted-foreground text-center py-8">
                  No child nodes yet.
                </p>
              )}
            </div>
          ) : (
            <div className="max-w-4xl mx-auto space-y-4">
              <div className="mb-6">
                <h2 className="text-2xl font-bold">Full Document</h2>
              </div>

              {canEditFullDocument && (
                <>
                  {selectedSection ? (
                    <div className="mb-4 p-4 bg-blue-50 border-2 border-blue-400 rounded-md shadow-sm">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-sm text-blue-900">
                              📍 Selected: {selectedSection.title}
                            </h3>
                            <span className="text-xs text-blue-600 bg-blue-100 px-2 py-0.5 rounded">
                              H{selectedSection.depth}
                            </span>
                          </div>
                          <p className="text-xs text-blue-700 mt-1">
                            {selectedSection.path.map(p => p.title).join(' › ')}
                          </p>
                          <p className="text-xs text-blue-600 mt-1 font-mono">
                            Lines {selectedLineRange?.startLine}–{selectedLineRange?.endLine} of {selectedLineRange?.totalLines}
                            {' • '}
                            Characters {selectedSection.startOffset}–{selectedSection.endOffset} 
                            ({selectedSection.endOffset - selectedSection.startOffset} chars)
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <LockIndicator
                            resourceType="markdown-section"
                            resourceId={selectedSection.id}
                            projectId={projectId}
                          />
                          <LockButton
                            resourceType="markdown-section"
                            resourceId={selectedSection.id}
                            projectId={projectId}
                          />
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => setSelectedSection(null)}
                          >
                            Clear Selection
                          </Button>
                        </div>
                      </div>
                      {!canEditSelectedSection && (
                        <div className="mt-2 text-xs text-yellow-800 bg-yellow-50 p-2 rounded border border-yellow-200">
                          ⚠️ This section is locked. You need to acquire the lock to edit it.
                        </div>
                      )}
                      {selectedSection.children.length > 0 && (
                        <div className="mt-2 text-xs text-blue-600">
                          ℹ️ Includes {selectedSection.children.length} subsection{selectedSection.children.length !== 1 ? 's' : ''}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="mb-4 p-4 bg-blue-50 border-2 border-blue-400 rounded-md shadow-sm">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-sm text-blue-900">
                              📍 Selected: Full Document
                            </h3>
                          </div>
                          <p className="text-xs text-blue-700 mt-1">
                            Entire document selected (all sections)
                          </p>
                          <p className="text-xs text-blue-600 mt-1 font-mono">
                            Lines 1–{lineCount} of {lineCount}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <LockIndicator
                            resourceType="document"
                            resourceId={documentId ?? ''}
                            projectId={projectId}
                          />
                          <LockButton
                            resourceType="document"
                            resourceId={documentId ?? ''}
                            projectId={projectId}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="flex border rounded-md overflow-hidden">
                    <LineNumberGutter
                      lineCount={lineCount}
                      selectedLineRange={selectedLineRange}
                      scrollTop={textareaScrollTop}
                    />
                    <textarea
                      ref={textareaRef}
                      className="flex-1 h-[calc(100vh-300px)] p-4 font-mono text-sm resize-none border-0 outline-none"
                      value={fullDocumentMarkdown}
                      onChange={(e) => setFullDocumentMarkdown(e.target.value)}
                      onScroll={(e) => setTextareaScrollTop(e.currentTarget.scrollTop)}
                      style={{ lineHeight: '1.25rem' }}
                    />
                  </div>
                  <div className="flex gap-2 mt-4">
                    <Button onClick={handleSaveFullDocument}>
                      Save Full Document
                    </Button>
                    <Button variant="outline" onClick={() => {
                      setFullDocumentMarkdown(markdownPreview);
                    }}>
                      Reset
                    </Button>
                  </div>
                </>
              )}

              {!canEditFullDocument && (
                <>
                  {selectedSection ? (
                    <div className="mb-4 p-4 bg-blue-50 border-2 border-blue-400 rounded-md shadow-sm">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-sm text-blue-900">
                              📍 Selected: {selectedSection.title}
                            </h3>
                            <span className="text-xs text-blue-600 bg-blue-100 px-2 py-0.5 rounded">
                              H{selectedSection.depth}
                            </span>
                          </div>
                          <p className="text-xs text-blue-700 mt-1">
                            {selectedSection.path.map(p => p.title).join(' › ')}
                          </p>
                          <p className="text-xs text-blue-600 mt-1 font-mono">
                            Lines {selectedLineRange?.startLine}–{selectedLineRange?.endLine} of {selectedLineRange?.totalLines}
                            {' • '}
                            Characters {selectedSection.startOffset}–{selectedSection.endOffset} 
                            ({selectedSection.endOffset - selectedSection.startOffset} chars)
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <LockIndicator
                            resourceType="markdown-section"
                            resourceId={selectedSection.id}
                            projectId={projectId}
                          />
                          <LockButton
                            resourceType="markdown-section"
                            resourceId={selectedSection.id}
                            projectId={projectId}
                          />
                          <Button 
                            size="sm" 
                            variant="outline"
                            onClick={() => setSelectedSection(null)}
                          >
                            Clear Selection
                          </Button>
                        </div>
                      </div>
                      {!canEditSelectedSection && (
                        <div className="mt-2 text-xs text-yellow-800 bg-yellow-50 p-2 rounded border border-yellow-200">
                          ⚠️ This section is locked. You need to acquire the lock to edit it.
                        </div>
                      )}
                      {selectedSection.children.length > 0 && (
                        <div className="mt-2 text-xs text-blue-600">
                          ℹ️ Includes {selectedSection.children.length} subsection{selectedSection.children.length !== 1 ? 's' : ''}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="mb-4 p-4 bg-blue-50 border-2 border-blue-400 rounded-md shadow-sm">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-sm text-blue-900">
                              📍 Selected: Full Document
                            </h3>
                          </div>
                          <p className="text-xs text-blue-700 mt-1">
                            Entire document selected (all sections)
                          </p>
                          <p className="text-xs text-blue-600 mt-1 font-mono">
                            Lines 1–{lineCount} of {lineCount}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <LockIndicator
                            resourceType="document"
                            resourceId={documentId ?? ''}
                            projectId={projectId}
                          />
                          <LockButton
                            resourceType="document"
                            resourceId={documentId ?? ''}
                            projectId={projectId}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="flex border rounded-md overflow-hidden bg-gray-50">
                    <LineNumberGutter
                      lineCount={lineCount}
                      selectedLineRange={selectedLineRange}
                      scrollTop={textareaScrollTop}
                    />
                    <textarea
                      ref={textareaRef}
                      className="flex-1 h-[calc(100vh-300px)] p-4 font-mono text-sm resize-none border-0 outline-none bg-gray-50"
                      value={markdownPreview}
                      onScroll={(e) => setTextareaScrollTop(e.currentTarget.scrollTop)}
                      style={{ lineHeight: '1.25rem' }}
                      readOnly
                    />
                  </div>
                  <p className="text-sm text-muted-foreground mt-2">
                    Lock the full document to edit, or select a section from the sidebar to edit that section.
                  </p>
                </>
              )}
            </div>
          )}
        </main>

        <aside className="w-96 flex-shrink-0">
          <MarkdownPreview markdown={markdownPreview} />
        </aside>

        {showVersionHistory && (
          <aside className="w-80 flex-shrink-0">
            <VersionHistoryPanel
              versions={versions}
              onRestore={handleRestore}
              onCompare={handleCompare}
              onClose={() => setShowVersionHistory(false)}
            />
          </aside>
        )}

        {showAgentThreads && (
          <aside className="w-96 flex-shrink-0 border-l bg-white">
            <ThreadsPanel projectId={projectId} documentId={documentId} />
          </aside>
        )}

        {showComments && documentId && (
          <aside className="w-96 flex-shrink-0 border-l bg-white">
            <CommentsPanel
              projectId={projectId}
              documentId={documentId}
              onCommentClick={(commentId) => {
                console.log('Comment clicked:', commentId);
              }}
              onCreateThread={async (commentId) => {
                await createThread({
                  projectId,
                  documentId,
                  title: 'Agent thread from comment',
                  anchorCommentId: commentId,
                });
                setShowAgentThreads(true);
              }}
            />
          </aside>
        )}
      </div>

      {compareVersions && (
        <VersionCompareView
          differences={comparison}
          versionA={versions.find((v: any) => v._id === compareVersions.versionA)!}
          versionB={versions.find((v: any) => v._id === compareVersions.versionB)!}
          onClose={() => setCompareVersions(null)}
        />
      )}
    </div>
  );
}
