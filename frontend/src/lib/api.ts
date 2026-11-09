import axios from "axios";
import { useEffect, useState } from "react";

export const TOKEN_KEY = "afed_token";
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string | null) =>
  token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY);

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "/api",
  paramsSerializer: { indexes: null }, // level=a&level=b, the form FastAPI reads as a list
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(undefined, (error) => {
  // /auth/me is the session check itself and runs on public pages too, so AuthProvider handles its answer.
  const url = String(error.config?.url ?? "");
  if (error.response?.status === 401 && getToken() && !url.endsWith("/auth/me") && !url.endsWith("/auth/login")) {
    setToken(null);
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
  }
  return Promise.reject(error);
});

export interface ApiError { status?: number; message: string }

export function toError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail[0]?.msg : undefined;
    return { status: error.response?.status, message: message ?? (error.response ? `Request failed (${error.response.status})` : "The server could not be reached") };
  }
  return { message: "Something went wrong" };
}

export interface Loaded<T> { data?: T; error?: ApiError; loading: boolean; reload: () => void }

export function useApi<T>(url: string | null, params?: object): Loaded<T> {
  const [state, setState] = useState<Omit<Loaded<T>, "reload">>({ loading: Boolean(url) });
  const [tick, setTick] = useState(0);
  const key = JSON.stringify([url, params, tick]);
  useEffect(() => {
    if (!url) return;
    const controller = new AbortController();
    setState((s) => ({ ...s, loading: true, error: undefined }));
    api.get<T>(url, { params, signal: controller.signal })
      .then((r) => setState({ data: r.data, loading: false }))
      .catch((e) => { if (!axios.isCancel(e)) setState({ loading: false, error: toError(e) }); });
    return () => controller.abort();
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return { ...state, reload: () => setTick((t) => t + 1) };
}

/** Fetch with the auth header, then hand the blob to the browser as a download. */
export async function download(path: string, filename: string, params?: object) {
  const response = await api.get(path, { params, responseType: "blob" }).catch(async (error) => {
    // A blob response hides the server's JSON error, so read it back out for toError.
    if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
      error.response.data = await error.response.data.text().then(JSON.parse).catch(() => undefined);
    }
    throw error;
  });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export const NOTIFICATIONS_CHANGED = "afed:notifications-changed";

export type Role = "Admin" | "Analyst" | "Reviewer" | "Viewer";
export interface User {
  id: number; email: string; name: string; role: Role; is_active: boolean;
  preferences: { theme?: "light" | "dark"; language?: "en" | "hi" }; last_login?: string | null;
}
export interface Paged<T> { items: T[]; total: number; page: number; page_size: number }
export interface Person { id: number; name: string }
export interface AlertRow {
  id: number; event_id: string; vendor_id: string; vendor_name: string; amount: number; invoice_date: string; risk: number;
  level: string; flags: string[]; status: string; case_id: number | null; assignee: Person | null;
}
export interface Fact {
  key: string; severity: number; text: string; text_hi: string;
  observed: string | number | null; baseline: string | number | null; ratio: number | null;
}
export interface AlertDetail extends AlertRow {
  event: Record<string, string | number | null>;
  scores: { lstm: number | null; isolation_forest: number; entity_deviation: number; rules: number };
  thresholds: { medium: number; high: number; critical: number };
  facts: Fact[]; explanation: string; explanation_provider: string; model_version: string | null;
  normal_range: { p10: number | null; p50: number | null; p90: number | null; count: number };
  sequence: { event_id: string; date: string; actual: number; expected: number | null; level: string | null; current: boolean }[];
  related: AlertRow[];
  timeline: { action: string; user: string; at: string; detail: Record<string, string> }[];
}
export interface RunRow {
  id: number; status: string; stage: string; progress: number; source: string; rows: number; new_rows: number; alerts: number;
  model_version: string | null; error: string | null; started_at: string; finished_at: string | null;
}
