import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import { authApi } from '../api/authApi';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const response = await authApi.me();
      setUser(response.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadUser(); }, [loadUser]);

  const login = useCallback(async (credentials) => {
    const response = await authApi.login(credentials);
    if (response.data.mfa_required) return response.data;
    setUser(response.data.user);
    return response.data;
  }, []);

  const confirmMfaEnrollment = useCallback(async (payload) => {
    const response = await authApi.confirmMfaEnrollment(payload);
    setUser(response.data.user);
    return response.data;
  }, []);

  const verifyMfaChallenge = useCallback(async (payload) => {
    const response = await authApi.verifyMfaChallenge(payload);
    setUser(response.data.user);
    return response.data;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      reloadUser: loadUser,
      confirmMfaEnrollment,
      verifyMfaChallenge,
    }),
    [user, loading, loadUser, login, logout, confirmMfaEnrollment, verifyMfaChallenge],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
