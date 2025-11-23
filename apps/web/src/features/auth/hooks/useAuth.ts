import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export interface User {
  id: string;
  email: string;
  name: string;
}

export function useAuth() {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const mockUser: User = {
        id: '1',
        email,
        name: email.split('@')[0],
      };
      setUser(mockUser);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const signup = async (name: string, email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const mockUser: User = {
        id: '1',
        email,
        name,
      };
      setUser(mockUser);
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    navigate('/login');
  };

  return {
    user,
    loading,
    error,
    login,
    signup,
    logout,
    isAuthenticated: user !== null,
  };
}
