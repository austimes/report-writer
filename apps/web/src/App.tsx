import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { SignIn, SignUp, UserButton, useAuth } from '@clerk/clerk-react';
import { useConvexAuth } from 'convex/react';
import { ProjectsListPage } from './features/projects/pages/ProjectsListPage';
import { ProjectPage } from './features/projects/pages/ProjectPage';
import { ProjectSettingsPage } from './features/projects/pages/ProjectSettingsPage';
import { useEffect } from 'react';

function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b p-4 flex justify-between items-center">
        <h1 className="text-xl font-bold">Report Writer</h1>
        <UserButton />
      </header>
      <main>{children}</main>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isLoading: isConvexLoading, isAuthenticated } = useConvexAuth();
  const { isLoaded: isClerkLoaded, isSignedIn, userId } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    console.log('[ProtectedRoute] state', {
      clerk: { isClerkLoaded, isSignedIn, userId },
      convex: { isConvexLoading, isAuthenticated },
    });
  }, [isClerkLoaded, isSignedIn, userId, isConvexLoading, isAuthenticated]);

  useEffect(() => {
    if (!isClerkLoaded || isConvexLoading) return;

    if (!isSignedIn) {
      console.log('[ProtectedRoute] redirect → /sign-in (no Clerk session)');
      navigate('/sign-in', { replace: true });
      return;
    }

    if (isSignedIn && !isAuthenticated) {
      console.warn(
        '[ProtectedRoute] Clerk signed in but Convex not authenticated → likely JWT/config issue'
      );
    }
  }, [isClerkLoaded, isConvexLoading, isSignedIn, isAuthenticated, navigate]);

  if (!isClerkLoaded || isConvexLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Auth loading...</div>
      </div>
    );
  }

  if (!isSignedIn) {
    return null;
  }

  if (isSignedIn && !isAuthenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg text-red-600">
          Auth error: Signed in with Clerk, but Convex is not authenticated.
          <br />
          Please open DevTools Console and send a screenshot of the logs.
        </div>
      </div>
    );
  }

  return <AuthenticatedLayout>{children}</AuthenticatedLayout>;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route 
          path="/sign-in/*" 
          element={
            <div className="flex items-center justify-center min-h-screen">
              <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" />
            </div>
          } 
        />
        <Route 
          path="/sign-up/*" 
          element={
            <div className="flex items-center justify-center min-h-screen">
              <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" />
            </div>
          } 
        />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <ProjectsListPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:id"
          element={
            <ProtectedRoute>
              <ProjectPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/projects/:id/settings"
          element={
            <ProtectedRoute>
              <ProjectSettingsPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
