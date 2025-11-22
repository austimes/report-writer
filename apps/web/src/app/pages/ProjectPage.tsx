import { useParams } from 'react-router-dom';
import { Card } from '@/shared/components/ui/Card';

export function ProjectPage() {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-xl font-bold">Project Editor</h1>
        </div>
      </header>
      <main className="container mx-auto px-4 py-8">
        <Card className="p-8">
          <h2 className="text-2xl font-bold mb-4">Project: {id}</h2>
          <p className="text-muted-foreground">Editor interface will go here.</p>
        </Card>
      </main>
    </div>
  );
}
