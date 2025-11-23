import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { SignIn, SignUp, SignedIn, SignedOut, UserButton } from '@clerk/clerk-react';
import { Authenticated, Unauthenticated, AuthLoading } from 'convex/react';
import { ProjectsListPage } from './features/projects/pages/ProjectsListPage';
import { ProjectPage } from './features/projects/pages/ProjectPage';
import { ProjectSettingsPage } from './features/projects/pages/ProjectSettingsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/sign-in/*" element={<SignIn routing="path" path="/sign-in" />} />
        <Route path="/sign-up/*" element={<SignUp routing="path" path="/sign-up" />} />
        <Route
          path="/"
          element={
            <>
              <AuthLoading>
                <div className="flex items-center justify-center min-h-screen">
                  <div>Loading...</div>
                </div>
              </AuthLoading>
              <Unauthenticated>
                <Navigate to="/sign-in" replace />
              </Unauthenticated>
              <Authenticated>
                <div className="min-h-screen">
                  <header className="border-b p-4 flex justify-between items-center">
                    <h1 className="text-xl font-bold">Report Writer</h1>
                    <UserButton />
                  </header>
                  <main>
                    <ProjectsListPage />
                  </main>
                </div>
              </Authenticated>
            </>
          }
        />
        <Route
          path="/projects/:id"
          element={
            <>
              <Unauthenticated>
                <Navigate to="/sign-in" replace />
              </Unauthenticated>
              <Authenticated>
                <div className="min-h-screen">
                  <header className="border-b p-4 flex justify-between items-center">
                    <h1 className="text-xl font-bold">Report Writer</h1>
                    <UserButton />
                  </header>
                  <main>
                    <ProjectPage />
                  </main>
                </div>
              </Authenticated>
            </>
          }
        />
        <Route
          path="/projects/:id/settings"
          element={
            <>
              <Unauthenticated>
                <Navigate to="/sign-in" replace />
              </Unauthenticated>
              <Authenticated>
                <div className="min-h-screen">
                  <header className="border-b p-4 flex justify-between items-center">
                    <h1 className="text-xl font-bold">Report Writer</h1>
                    <UserButton />
                  </header>
                  <main>
                    <ProjectSettingsPage />
                  </main>
                </div>
              </Authenticated>
            </>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
