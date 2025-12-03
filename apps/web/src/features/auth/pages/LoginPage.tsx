import { SignIn } from '@clerk/clerk-react';

export function LoginPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <SignIn routing="path" path="/login" signUpUrl="/signup" />
    </div>
  );
}
