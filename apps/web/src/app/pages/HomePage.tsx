import { Link } from 'react-router-dom';
import { Button } from '@/shared/components/ui/Button';
import { Card } from '@/shared/components/ui/Card';

export function HomePage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold">Report Writer</h1>
          <div className="space-x-2">
            <Link to="/login">
              <Button variant="ghost">Login</Button>
            </Link>
            <Link to="/signup">
              <Button>Sign Up</Button>
            </Link>
          </div>
        </div>
      </header>
      <main className="container mx-auto px-4 py-8">
        <Card className="p-8">
          <h2 className="text-3xl font-bold mb-4">Welcome to Report Writer</h2>
          <p className="text-muted-foreground mb-6">
            Collaborative report writing with real-time editing and AI assistance.
          </p>
          <Button>Get Started</Button>
        </Card>
      </main>
    </div>
  );
}
