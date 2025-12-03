import { useQuery } from "convex/react";
import { api } from "../../../lib/convex";
import type { Id } from "convex/_generated/dataModel";

export function useChildNodes(parentId: Id<"nodes"> | null) {
  const nodes = useQuery(
    api.tables.nodes.listChildren,
    parentId ? { parentId } : "skip"
  );

  return nodes ? [...nodes].sort((a, b) => a.order - b.order) : [];
}
