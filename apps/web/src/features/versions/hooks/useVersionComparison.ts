import { useQuery } from 'convex/react';
import { api } from '@/lib/convex';
import type { Id } from 'convex/_generated/dataModel';

export function useVersionComparison(
  versionIdA: Id<'reportVersions'> | null,
  versionIdB: Id<'reportVersions'> | null
) {
  const comparison = useQuery(
    api.features.versions.compareVersions,
    versionIdA && versionIdB ? { versionIdA, versionIdB } : 'skip'
  );

  return comparison ?? [];
}
