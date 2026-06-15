import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  useEffect(() => {
    let active = true;
    if (!getToken()) {
      return;
    }

    api.me()
      .then((currentUser) => {
        if (active) setUser(currentUser);
      })
      .catch(() => {
        setToken(null);
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  async function login(credentials) {
    const response = await api.login(credentials);
    setToken(response.access_token);
    setUser(response.user);
    return response.user;
  }

  async function register(payload) {
    const response = await api.register(payload);
    setToken(response.access_token);
    setUser(response.user);
    return response.user;
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  const value = useMemo(() => ({ user, loading, login, register, logout, setUser }), [user, loading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
