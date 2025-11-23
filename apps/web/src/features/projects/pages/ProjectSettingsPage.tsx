import { useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { Button } from '@/shared/components/ui/Button';
import { Card } from '@/shared/components/ui/Card';
import { useProjectMembers } from '../hooks/useProjectMembers';
import { useProjects } from '../hooks/useProjects';
import { InviteCollaboratorModal } from '../components/InviteCollaboratorModal';
import { Id } from 'convex/_generated/dataModel';
import { useAuth } from '../../auth/hooks/useAuth';

export function ProjectSettingsPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = id as Id<'projects'>;
  const navigate = useNavigate();
  const { user } = useAuth();
  const userId = user?.id as Id<'users'>;
  const { members, addMember, removeMember } = useProjectMembers(projectId);
  const { archiveProject } = useProjects(userId);
  const [showInviteModal, setShowInviteModal] = useState(false);

  const handleArchive = async () => {
    if (confirm('Are you sure you want to archive this project?')) {
      await archiveProject({ id: projectId });
      navigate('/');
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link to={`/projects/${id}`}>
              <Button variant="outline" size="sm">← Back</Button>
            </Link>
            <h1 className="text-2xl font-bold">Project Settings</h1>
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <Card className="p-6 mb-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">Collaborators</h2>
            <Button onClick={() => setShowInviteModal(true)}>
              Invite Collaborator
            </Button>
          </div>
          
          {members.length === 0 ? (
            <p className="text-muted-foreground">No collaborators yet.</p>
          ) : (
            <div className="space-y-2">
              {members.map((member) => (
                <div key={member._id} className="flex justify-between items-center p-3 border rounded">
                  <div>
                    <p className="font-medium">User {member.userId}</p>
                    <p className="text-sm text-muted-foreground">{member.role}</p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => removeMember({ id: member._id })}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="p-6">
          <h2 className="text-xl font-semibold mb-4">Danger Zone</h2>
          <Button onClick={handleArchive} variant="destructive">
            Archive Project
          </Button>
        </Card>
      </main>

      {showInviteModal && (
        <InviteCollaboratorModal
          projectId={projectId}
          onClose={() => setShowInviteModal(false)}
          onInvite={addMember}
        />
      )}
    </div>
  );
}
