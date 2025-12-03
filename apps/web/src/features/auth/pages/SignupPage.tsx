import { SignUp } from '@clerk/clerk-react';

export function SignupPage() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <SignUp routing="path" path="/signup" signInUrl="/login" />
    </div>
  );
}
