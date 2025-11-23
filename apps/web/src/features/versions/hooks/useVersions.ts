import { useQuery, useMutation } from 'convex/react';
import { api } from '@/lib/convex';
import type { Id } from 'convex/_generated/dataModel';

export function useVersions(projectId: Id<'projects'>) {
  const versions = useQuery(api.tables.reportVersions.listByProject, { projectId });
  const createVersion = useMutation(api.features.versions.createVersionSnapshot);
  const restoreVersion = useMutation(api.features.versions.restoreVersion);

  return {
    versions: versions ?? [],
    createVersion,
    restoreVersion,
  };
}
