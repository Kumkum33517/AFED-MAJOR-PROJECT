import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken, toError, TOKEN_KEY, type ApiError, type Role, type User } from "./api";
import { applyTheme } from "./theme";

interface Auth {
  user: User | null;
  ready: boolean;
  /** The session could not be checked, as opposed to being invalid. */
  error: ApiError | null;
  retry: () => void;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  update: (user: User) => void;
  /** Reviewer actions on alerts and cases. The API enforces this too; this only tidies the UI. */
  canAct: boolean;
  canOperate: boolean;
}

const Context = createContext<Auth | null>(null);

export const ACT: Role[] = ["Admin", "Reviewer"];
export const OPERATE: Role[] = ["Admin", "Analyst"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(!getToken());
  const [error, setError] = useState<ApiError | null>(null);

  const retry = useCallback(() => {
    if (!getToken()) return;
    setReady(false);
    setError(null);
    api.get<User>("/auth/me").then((r) => setUser(r.data)).catch((e) => {
      const problem = toError(e);
      // Only a 401 means the token is bad. During an outage it is still good, so keep it.
      if (problem.status === 401) setToken(null); else setError(problem);
    }).finally(() => setReady(true));
  }, []);

  useEffect(retry, [retry]);
  useEffect(() => { if (user?.preferences.theme) applyTheme(user.preferences.theme); }, [user]);

  useEffect(() => {
    const signedOutElsewhere = (event: StorageEvent) => { if (event.key === TOKEN_KEY && !event.newValue) setUser(null); };
    window.addEventListener("storage", signedOutElsewhere);
    return () => window.removeEventListener("storage", signedOutElsewhere);
  }, []);

  const login = async (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    const { data } = await api.post<{ access_token: string; user: User }>("/auth/login", form);
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => { setToken(null); setUser(null); };
  const role = user?.role;
  return (
    <Context.Provider value={{ user, ready, error, retry, login, logout, update: setUser,
      canAct: !!role && ACT.includes(role), canOperate: !!role && OPERATE.includes(role) }}>
      {children}
    </Context.Provider>
  );
}

export function useAuth(): Auth {
  const value = useContext(Context);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

export const homeFor = (role: Role) => (role === "Reviewer" ? "/alerts" : role === "Analyst" ? "/upload" : "/dashboard");
