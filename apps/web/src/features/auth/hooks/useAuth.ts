import { useAuth as useClerkAuth } from '@clerk/clerk-react';
import { useMutation, useQuery } from 'convex/react';
import { api } from '../../../../../../convex/_generated/api';

export interface User {
  id: string;
  email: string;
  name: string;
}

export function useAuth() {
  const { signOut } = useClerkAuth();
  const getOrCreateUser = useMutation(api.tables.users.getOrCreateUser);
  const currentUser = useQuery(api.tables.users.getCurrentUser);

  const logout = async () => {
    await signOut();
  };

  return {
    user: currentUser ? {
      id: currentUser._id,
      email: currentUser.email,
      name: currentUser.name,
    } : null,
    loading: currentUser === undefined,
    logout,
    isAuthenticated: currentUser !== null,
    getOrCreateUser,
  };
}
