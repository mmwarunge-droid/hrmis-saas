import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import { authApi } from '../api/authApi';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem('hrmis_access_token');
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await authApi.me();
      setUser(res.data);
    } catch {
      localStorage.removeItem('hrmis_access_token');
      localStorage.removeItem('hrmis_refresh_token');
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadUser(); }, [loadUser]);

  const login = async (credentials) => {
    const res = await authApi.login(credentials);
    localStorage.setItem('hrmis_access_token', res.data.access_token);
    localStorage.setItem('hrmis_refresh_token', res.data.refresh_token);
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    localStorage.removeItem('hrmis_access_token');
    localStorage.removeItem('hrmis_refresh_token');
    setUser(null);
  };

  const value = useMemo(() => ({ user, loading, login, logout, reloadUser: loadUser }), [user, loading, loadUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
