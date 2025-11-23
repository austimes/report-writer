import { useQuery, useMutation } from 'convex/react';
import { api } from 'convex/_generated/api';
import { Id } from 'convex/_generated/dataModel';

export function useProjects(userId: Id<'users'>) {
  const projects = useQuery(api.tables.projects.listByUser, { userId });
  const createProject = useMutation(api.tables.projects.create);
  const updateProject = useMutation(api.tables.projects.update);
  const archiveProject = useMutation(api.tables.projects.archive);

  return {
    projects: projects ?? [],
    createProject,
    updateProject,
    archiveProject,
  };
}
