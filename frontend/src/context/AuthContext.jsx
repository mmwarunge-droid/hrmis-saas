import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import { authApi } from '../api/authApi';
import {
  SESSION_EXPIRED_EVENT,
  SESSION_EXPIRED_MESSAGE,
} from '../utils/sessionExpiry.js';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionMessage, setSessionMessage] = useState('');

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

  useEffect(() => {
    const expireSession = () => {
      setUser(null);
      setLoading(false);
      setSessionMessage(SESSION_EXPIRED_MESSAGE);
    };

    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
  }, []);

  const login = useCallback(async (credentials) => {
    setSessionMessage('');
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
      setSessionMessage('');
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      sessionMessage,
      reloadUser: loadUser,
      confirmMfaEnrollment,
      verifyMfaChallenge,
    }),
    [user, loading, loadUser, login, logout, sessionMessage, confirmMfaEnrollment, verifyMfaChallenge],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
