import { Link } from 'react-router-dom';
import { Card } from '@/shared/components/ui/Card';

interface ProjectCardProps {
  id: string;
  name: string;
  description?: string;
  updatedAt?: number;
}

export function ProjectCard({ id, name, description, updatedAt }: ProjectCardProps) {
  const formatDate = (timestamp?: number) => {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleDateString();
  };

  return (
    <Link to={`/projects/${id}`}>
      <Card className="p-6 hover:shadow-lg transition-shadow cursor-pointer">
        <h3 className="text-xl font-semibold mb-2">{name}</h3>
        {description && (
          <p className="text-muted-foreground mb-4 line-clamp-2">{description}</p>
        )}
        <p className="text-sm text-muted-foreground">
          Last updated: {formatDate(updatedAt)}
        </p>
      </Card>
    </Link>
  );
}
