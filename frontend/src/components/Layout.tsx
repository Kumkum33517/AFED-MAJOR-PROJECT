import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { api, NOTIFICATIONS_CHANGED, useApi, type Role, type User } from "../lib/api";
import { OPERATE, useAuth } from "../lib/auth";
import { applyTheme, currentTheme, THEME_CHANGED, type Theme } from "../lib/theme";

const ALL: Role[] = ["Admin", "Analyst", "Reviewer", "Viewer"];
const NAV: { to: string; label: string; roles: Role[] }[] = [
  { to: "/dashboard", label: "Dashboard", roles: ALL }, { to: "/alerts", label: "Alerts", roles: ALL },
  { to: "/cases", label: "Cases", roles: ALL }, { to: "/entities", label: "Entities", roles: ALL },
  { to: "/upload", label: "Data & runs", roles: OPERATE }, { to: "/settings", label: "Model settings", roles: OPERATE },
  { to: "/evaluation", label: "Evaluation", roles: ALL }, { to: "/reports", label: "Reports", roles: ALL },
  { to: "/users", label: "Users", roles: ["Admin"] },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout, update } = useAuth();
  const [theme, setTheme] = useState<Theme>(currentTheme());
  const location = useLocation();
  const notes = useApi<{ unread: number }>("/notifications");

  useEffect(() => { notes.reload(); }, [location.pathname]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const refresh = () => notes.reload();
    window.addEventListener(NOTIFICATIONS_CHANGED, refresh);
    return () => window.removeEventListener(NOTIFICATIONS_CHANGED, refresh);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const sync = () => setTheme(currentTheme());
    window.addEventListener(THEME_CHANGED, sync);
    return () => window.removeEventListener(THEME_CHANGED, sync);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    api.patch<User>("/auth/me", { preferences: { theme: next } }).then((r) => update(r.data)).catch(() => undefined);  // a preference, not worth an error
  };
  if (!user) return null;

  const link = ({ isActive }: { isActive: boolean }) =>
    `whitespace-nowrap rounded px-3 py-1.5 transition-colors ${isActive ? "bg-olive-700 font-medium text-cream-100 shadow-[inset_0_-2px_0_#C98B78]" : "text-cream-200 hover:bg-olive-700/50 hover:text-cream-100"}`;
  const icon = "rounded p-1.5 text-cream-200 transition-colors hover:bg-olive-700/50 hover:text-cream-100";
  const initials = user.name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only z-50 bg-cream-100 px-3 py-2 text-sm text-olive-900 focus:not-sr-only focus:fixed focus:left-2 focus:top-2">Skip to content</a>
      <header className="on-olive sticky top-0 z-30 grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 lg:grid-cols-[auto_1fr_auto] bg-olive-900 px-4 py-2 text-sm text-cream-100 shadow-md shadow-black/10 lg:px-8">
        <Link to="/" className="font-serif text-2xl font-bold tracking-tight">AFED</Link>
        <nav className="col-span-2 row-start-2 -mx-1 flex min-w-0 justify-start gap-1 overflow-x-auto lg:col-span-1 lg:col-start-2 lg:row-start-1 lg:mx-0 lg:justify-center" aria-label="Main">
          {NAV.filter((l) => l.roles.includes(user.role)).map((l) => <NavLink key={l.to} to={l.to} className={link}>{l.label}</NavLink>)}
        </nav>
        <div className="flex items-center gap-2 lg:col-start-3">
          <button type="button" onClick={toggleTheme} className={icon} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            {/* lit bulb in the light theme, unlit in the dark one */}
            <svg width="20" height="20" viewBox="0 0 24 24" fill={theme === "dark" ? "none" : "currentColor"} fillOpacity="0.25" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.6 10.8c.7.5 1.1 1.3 1.1 2.2h5c0-.9.4-1.7 1.1-2.2A6 6 0 0 0 12 3Z" />
            </svg>
          </button>
          <Link to="/notifications" className={`relative ${icon}`} aria-label={`Notifications, ${notes.data?.unread ?? 0} unread`} title="Notifications">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
              <path d="M6 9a6 6 0 1 1 12 0c0 6 2.5 7 2.5 7h-17S6 15 6 9Z" /><path d="M10 20a2.2 2.2 0 0 0 4 0" />
            </svg>
            {!!notes.data?.unread && (
              <span className="absolute -right-0.5 -top-0.5 min-w-4 rounded-full bg-clay-600 px-1 text-center text-[10px] font-semibold leading-4 text-cream-100">
                {notes.data.unread > 99 ? "99+" : notes.data.unread}
              </span>
            )}
          </Link>
          <Link to="/profile" className="ml-1 flex items-center gap-2.5 rounded px-2 py-1 transition-colors hover:bg-olive-700/50" title="Your profile">
            <span aria-hidden="true" className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-olive-500 text-xs font-semibold text-cream-100">{initials}</span>
            <span className="hidden leading-tight md:block">
              <span className="block whitespace-nowrap font-medium text-cream-100">{user.name}</span>
              <span className="block text-[11px] text-olive-300">{user.role}</span>
            </span>
          </Link>
          <button type="button" onClick={logout} className={icon} aria-label="Sign out" title="Sign out">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M9 20H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
            </svg>
          </button>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-[1440px] flex-1 p-4 lg:p-8">{children}</main>
    </div>
  );
}
