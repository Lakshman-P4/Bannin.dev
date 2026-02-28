'use client';

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import { api, setTokens, clearTokens } from '@/lib/api';
import type { User } from '@/types';

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  hasEmail: boolean;
  isEmailVerified: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  register: (username: string, displayName: string, password: string, email?: string) => Promise<void>;
  logout: () => void;
  resendVerification: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const res = await api.auth.me();
      setUser(res.data);
    } catch {
      setUser(null);
      clearTokens();
    }
  }, []);

  useEffect(() => {
    const token = typeof window !== 'undefined'
      ? localStorage.getItem('bannin_access_token')
      : null;

    if (token) {
      refreshUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [refreshUser]);

  const login = useCallback(async (identifier: string, password: string) => {
    const res = await api.auth.login({ identifier, password });
    setTokens(res.data.accessToken, res.data.refreshToken);
    setUser(res.data.user);
  }, []);

  const register = useCallback(async (username: string, displayName: string, password: string, email?: string) => {
    const body: { username: string; displayName: string; password: string; email?: string } = {
      username,
      displayName,
      password,
    };
    if (email) body.email = email;
    const res = await api.auth.register(body);
    setTokens(res.data.accessToken, res.data.refreshToken);
    setUser(res.data.user);
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    window.location.href = '/';
  }, []);

  const resendVerification = useCallback(async () => {
    await api.auth.resendVerification();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: user !== null,
        hasEmail: user?.email !== null && user?.email !== undefined,
        isEmailVerified: user?.emailVerified ?? false,
        login,
        register,
        logout,
        resendVerification,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
