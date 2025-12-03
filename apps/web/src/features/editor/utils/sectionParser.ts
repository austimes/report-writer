import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import { toString } from 'mdast-util-to-string';
import type { Root, Heading } from 'mdast';

export interface SectionPathEntry {
  depth: number;
  title: string;
}

export interface Section {
  id: string;
  depth: number;
  title: string;
  startOffset: number;
  endOffset: number;
  path: SectionPathEntry[];
  children: Section[];
}

interface RawSection extends Section {
  parent?: RawSection | null;
}

const parser = unified()
  .use(remarkParse, { position: true })
  .use(remarkGfm);

export function parseMarkdown(markdown: string): Root {
  return parser.parse(markdown) as Root;
}

function makeSectionId(path: SectionPathEntry[]): string {
  const slugPart = (p: SectionPathEntry) =>
    `${p.depth}-${p.title.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '')}`;
  return path.map(slugPart).join('/');
}

export function buildSections(root: Root, markdownLength: number): Section[] {
  const sections: RawSection[] = [];
  const stack: RawSection[] = [];

  const children = root.children;
  const docEndOffset = root.position?.end?.offset ?? markdownLength;

  for (const node of children) {
    if (node.type === 'heading') {
      const heading = node as Heading;
      const depth = heading.depth;
      const title = toString(heading);
      const startOffset = heading.position?.start.offset ?? 0;

      // Close sections with depth >= current heading depth
      while (stack.length > 0 && stack[stack.length - 1].depth >= depth) {
        const last = stack.pop()!;
        last.endOffset = startOffset;
      }

      const parent = stack[stack.length - 1] ?? null;
      const path: SectionPathEntry[] = [
        ...(parent?.path ?? []),
        { depth, title },
      ];

      const id = makeSectionId(path);

      const section: RawSection = {
        id,
        depth,
        title,
        startOffset,
        endOffset: docEndOffset,
        path,
        children: [],
        parent,
      };

      if (parent) {
        parent.children.push(section);
      }

      sections.push(section);
      stack.push(section);
    }
  }

  // Close remaining open sections at doc end
  for (const remaining of stack) {
    remaining.endOffset = docEndOffset;
  }

  // Top-level sections are those with no parent
  const roots = sections.filter(s => !s.parent);

  // Strip internal parent property
  const stripParent = (s: RawSection): Section => ({
    id: s.id,
    depth: s.depth,
    title: s.title,
    startOffset: s.startOffset,
    endOffset: s.endOffset,
    path: s.path,
    children: s.children.map(stripParent),
  });

  return roots.map(stripParent);
}

export function parseMarkdownSections(markdown: string): Section[] {
  const root = parseMarkdown(markdown);
  return buildSections(root, markdown.length);
}
