import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { authApi } from "../api/endpoints";
import { setUnauthorizedHandler, tokenStore } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(Boolean(tokenStore.get()));

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  useEffect(() => {
    if (!tokenStore.get()) return;
    authApi
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setBooting(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const { access_token } = await authApi.login(email, password);
    tokenStore.set(access_token);
    const me = await authApi.me();
    setUser(me);
    return me;
  }, []);

  const value = useMemo(() => ({ user, role: user?.role, booting, login, logout }), [user, booting, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
