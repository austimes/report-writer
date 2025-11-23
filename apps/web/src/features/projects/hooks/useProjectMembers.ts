import { useQuery, useMutation } from 'convex/react';
import { api } from 'convex/_generated/api';
import { Id } from 'convex/_generated/dataModel';

export function useProjectMembers(projectId: Id<'projects'>) {
  const members = useQuery(api.tables.projectMembers.listByProject, { projectId });
  const addMember = useMutation(api.tables.projectMembers.add);
  const removeMember = useMutation(api.tables.projectMembers.remove);
  const updateMemberRole = useMutation(api.tables.projectMembers.updateRole);

  return {
    members: members ?? [],
    addMember,
    removeMember,
    updateMemberRole,
  };
}
