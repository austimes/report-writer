import { useState, useEffect } from 'react';
import { Button } from '@/shared/components/ui/Button';
import { useAuth } from '../../auth/hooks/useAuth';
import { useProjects } from '../hooks/useProjects';
import { ProjectCard } from '../components/ProjectCard';
import { CreateProjectModal } from '../components/CreateProjectModal';

export function ProjectsListPage() {
  const { user, logout, getOrCreateUser } = useAuth();
  const userId = user?.id;
  const { projects, createProject } = useProjects(userId);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    if (getOrCreateUser) {
      getOrCreateUser();
    }
  }, [getOrCreateUser]);

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold">My Projects</h1>
          <div className="flex gap-2">
            <span className="text-muted-foreground">{user?.email}</span>
            <Button onClick={logout} variant="outline" size="sm">
              Logout
            </Button>
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-8">
        <div className="mb-6">
          <Button onClick={() => setShowCreateModal(true)} data-testid="open-create-project-modal">
            Create Project
          </Button>
        </div>

        {projects.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            No projects yet. Create your first project to get started.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="project-list">
            {projects.map((project) => (
              <ProjectCard
                key={project._id}
                id={project._id}
                name={project.name}
                description={project.description}
                updatedAt={project.createdAt}
              />
            ))}
          </div>
        )}
      </main>

      {showCreateModal && userId && (
        <CreateProjectModal
          userId={userId}
          onClose={() => setShowCreateModal(false)}
          onCreate={(ownerId, name, description) =>
            createProject({ ownerId, name, description })
          }
        />
      )}
    </div>
  );
}
