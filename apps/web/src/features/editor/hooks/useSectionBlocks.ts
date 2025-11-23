import { useQuery } from "convex/react";
import { api } from "../../../lib/convex";
import type { Id } from "convex/_generated/dataModel";

export function useSectionBlocks(sectionId: Id<"sections"> | null) {
  const blocks = useQuery(
    api.tables.blocks.listBySection,
    sectionId ? { sectionId } : "skip"
  );

  return blocks ? [...blocks].sort((a, b) => a.order - b.order) : [];
}
