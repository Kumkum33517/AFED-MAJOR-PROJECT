import { useEffect, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { download, toError, type ApiError, type Loaded } from "../lib/api";
import { RULE_LABELS } from "../lib/format";

export function Card({ title, subtitle, action, children, className = "" }: {
  title?: ReactNode; subtitle?: ReactNode; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`min-w-0 rounded-md border border-line bg-surface p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-sm font-semibold">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  useEffect(() => { document.title = `${title} · AFED`; return () => { document.title = "AFED"; }; }, [title]);
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <span aria-hidden="true" className="mb-3 block h-0.5 w-10 bg-brick" />
        <h1 className="font-serif text-3xl font-medium tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

type Variant = "primary" | "secondary" | "danger" | "ghost";
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-accent-fg hover:opacity-90",
  secondary: "border border-line bg-surface text-fg hover:bg-bg",
  danger: "bg-danger text-cream-100 dark:text-stone-950 hover:opacity-90",
  ghost: "text-muted hover:text-fg",
};

export function Button({ variant = "primary", className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return <button type="button" {...props}
    className={`inline-flex items-center justify-center gap-1.5 rounded px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`} />;
}

const LEVELS: Record<string, string> = {
  Low: "bg-olive-300 text-ink", Medium: "bg-amber-400 text-ink", High: "bg-rust-300 text-ink", Critical: "bg-rust-700 text-cream-100",
};
export const LEVEL_FILL: Record<string, string> = { Low: "#A3B18A", Medium: "#D9A441", High: "#D8775F", Critical: "#7E2F1C" };

/** Always a word on a colour: the lighter risk colours do not reach 3:1 against cream on their own. */
export function LevelBadge({ level }: { level: string }) {
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${LEVELS[level] ?? "bg-line"}`}>{level}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const tone = ["Confirmed", "Escalated"].includes(status) ? "border-fg/40 text-fg" : "border-line text-muted";
  return <span className={`inline-block rounded border px-2 py-0.5 text-xs ${tone}`}>{status}</span>;
}

export function FlagChips({ flags, limit }: { flags: string[]; limit?: number }) {
  const shown = limit ? flags.slice(0, limit) : flags;
  if (!flags.length) return <span className="text-xs text-muted">None</span>;
  return (
    <span className="inline-flex flex-wrap gap-1">
      {shown.map((f) => <span key={f} className="whitespace-nowrap rounded-full bg-bg px-2 py-0.5 text-[11px] text-fg">{RULE_LABELS[f] ?? f}</span>)}
      {flags.length > shown.length && <span className="px-1 text-[11px] text-muted" title={flags.slice(shown.length).map((f) => RULE_LABELS[f] ?? f).join(", ")}>+{flags.length - shown.length}</span>}
    </span>
  );
}

export function Loading({ rows = 4 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="animate-pulse space-y-3 motion-reduce:animate-none">
      {Array.from({ length: rows }, (_, i) => <div key={i} className="h-16 rounded-md bg-surface" />)}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="px-6 py-12 text-center">
      <p className="font-serif text-xl">{title}</p>
      {children && <div className="mx-auto mt-2 max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, retry }: { error: ApiError; retry?: () => void }) {
  return (
    <div role="alert" className="rounded-md border border-line bg-surface px-6 py-12 text-center">
      <p className="font-serif text-xl">That did not load</p>
      <p className="mt-2 text-sm text-muted">{error.message}</p>
      {retry && <Button variant="secondary" className="mt-4" onClick={retry}>Try again</Button>}
    </div>
  );
}

export function Forbidden() {
  return <Notice code="403" title="This page is not available to your role" body="Ask an administrator if you need access." />;
}

export function NotFound() {
  return <Notice code="404" title="Nothing here" body="The page or record may have moved, or it no longer exists." />;
}

function Notice({ code, title, body }: { code: string; title: string; body: string }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center p-6 text-center">
      <p className="font-serif text-7xl text-accent">{code}</p>
      <h1 className="mt-3 font-serif text-2xl">{title}</h1>
      <p className="mt-2 text-sm text-muted">{body}</p>
      <Link to="/dashboard" className="mt-5 text-sm font-medium text-accent underline underline-offset-4">Back to the dashboard</Link>
    </div>
  );
}

/** One place for the loading, error, 403 and 404 states of a page. */
export function Async<T>({ state, children, rows }: { state: Loaded<T>; children: (data: T) => ReactNode; rows?: number }) {
  if (state.error?.status === 403) return <Forbidden />;
  if (state.error?.status === 404 || state.error?.status === 422) return <NotFound />;  // 422: an id that cannot exist
  if (state.error) return <ErrorState error={state.error} retry={state.reload} />;
  if (state.data === undefined) return <Loading rows={rows} />;
  return <>{children(state.data)}</>;
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between border-t border-line px-3 py-3 text-sm text-muted">
      <span>{total.toLocaleString("en-IN")} total</span>
      <span className="flex items-center gap-2">
        <Button variant="secondary" className="!px-2.5 !py-1" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
        Page {page} of {pages}
        <Button variant="secondary" className="!px-2.5 !py-1" disabled={page >= pages} onClick={() => onPage(page + 1)}>Next</Button>
      </span>
    </div>
  );
}

export function SortHeader({ label, name, sort, order, onSort, className = "" }: {
  label: string; name: string; sort: string; order: string; onSort: (name: string) => void; className?: string;
}) {
  const active = sort === name;
  return (
    <th className={`table-head ${className}`} aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => onSort(name)} className="uppercase tracking-wider hover:text-fg">
        {label} {active && (order === "asc" ? "↑" : "↓")}
      </button>
    </th>
  );
}

export function Field({ label, error, hint, children }: { label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span role="alert" className="notice-error mt-1 block !text-xs">{error}</span>}
    </label>
  );
}

/** Fetches a report with the auth header and says so if that fails. */
export function DownloadButton({ path, filename, params, variant = "secondary", className, children }: {
  path: string; filename: string; params?: object; variant?: Variant; className?: string; children: ReactNode;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      await download(path, filename, params);
    } catch (e) {
      setError(toError(e).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <span className="inline-flex flex-col gap-1">
      <Button variant={variant} className={className} disabled={busy} onClick={start}>{busy ? "Preparing..." : children}</Button>
      {error && <span role="alert" className="notice-error !text-xs">{error}</span>}
    </span>
  );
}

export function Stat({ label, value, note }: { label: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {note && <p className="mt-0.5 text-xs text-muted">{note}</p>}
    </div>
  );
}

/** A chart with a table view beside it, so nothing depends on seeing the colours. */
export function ChartCard({ title, subtitle, table, children, className }: {
  title: string; subtitle?: ReactNode; table?: ReactNode; children: ReactNode; className?: string;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <Card title={title} subtitle={subtitle} className={className}
      action={table ? <button type="button" onClick={() => setAsTable(!asTable)} className="whitespace-nowrap text-xs text-muted underline underline-offset-2 hover:text-fg">{asTable ? "Show chart" : "Show table"}</button> : undefined}>
      {asTable ? <div className="max-h-72 overflow-auto">{table}</div> : children}
    </Card>
  );
}

export function SimpleTable({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <table className="w-full">
      <thead><tr className="border-b border-line">{head.map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
      <tbody>
        {rows.map((row, i) => <tr key={i} className="border-b border-line/60">{row.map((cell, j) => <td key={j} className="table-cell tabular-nums">{cell}</td>)}</tr>)}
      </tbody>
    </table>
  );
}
