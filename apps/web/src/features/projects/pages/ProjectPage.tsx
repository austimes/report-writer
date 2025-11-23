import { useParams, Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/Button';

export function ProjectPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link to="/">
              <Button variant="outline" size="sm">← Back</Button>
            </Link>
            <h1 className="text-2xl font-bold">Project</h1>
          </div>
          <Link to={`/projects/${id}/settings`}>
            <Button variant="outline" size="sm">Settings</Button>
          </Link>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-8">
        <div className="text-center py-12 text-muted-foreground">
          <p>Project editor will be implemented here.</p>
          <p className="text-sm mt-2">Project ID: {id}</p>
        </div>
      </main>
    </div>
  );
}
