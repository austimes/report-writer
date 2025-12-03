import { useQuery, useMutation } from 'convex/react';
import { api } from '@/lib/convex';
import type { Id } from 'convex/_generated/dataModel';

export function useVersions(_projectId: Id<'projects'>, documentId?: Id<'documents'>) {
  const versions = useQuery(
    api.tables.reportVersions.listByDocument, 
    documentId ? { documentId } : 'skip'
  );
  const createVersion = useMutation(api.features.versions.createVersionSnapshot);
  const restoreVersion = useMutation(api.features.versions.restoreVersion);

  return {
    versions: versions ?? [],
    createVersion,
    restoreVersion,
  };
}
