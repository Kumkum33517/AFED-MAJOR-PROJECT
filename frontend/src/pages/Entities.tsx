import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, axisAmount, ChartTooltip, GRID, Legend, SERIES } from "../components/charts";
import { Async, Card, ChartCard, Empty, FlagChips, LevelBadge, PageHeader, Pagination, SimpleTable, SortHeader, Stat, StatusBadge } from "../components/ui";
import { useApi, type AlertRow, type Paged } from "../lib/api";
import { count, date, inr, percent, plural } from "../lib/format";

interface Row { id: string; name: string; category: string | null; transactions: number; alerts: number; avg_risk: number; recent_alerts: number; trend: "up" | "down" | "flat" }
interface Profile {
  id: string; type: string; name: string; category: string | null; department: string | null; vendor_created: string | null; fallback_baseline: string | null;
  baseline: { median_amount: number; p25_amount: number; p75_amount: number; median_gap_days: number | null; median_processing_days: number | null; history_len: number };
  peers: { category: string; vendors: number; median_amount: number; median_processing_days: number | null; amount_percentile: number } | null;
  series: { event_id: string; date: string; amount: number; risk: number | null; level: string | null; flagged: boolean }[];
  alerts: AlertRow[];
}
const TREND = { up: "Rising", down: "Falling", flat: "Steady" };

export function Entities() {
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? "vendor";
  const sort = params.get("sort") ?? "alerts";
  const order = params.get("order") ?? "desc";
  const search = params.get("search") ?? "";
  const page = Number(params.get("page")) || 1;
  const [draft, setDraft] = useState(search);
  useEffect(() => { setDraft(search); }, [search]);
  const state = useApi<Paged<Row>>("/entities", { type, sort, order, search: search || undefined, page, page_size: 25 });
  const set = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    if (!("page" in changes)) next.delete("page");
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
  };
  const sortProps = { sort, order, onSort: (name: string) => set({ sort: name, order: sort === name && order === "desc" ? "asc" : "desc" }) };

  return (
    <>
      <PageHeader title="Entities" subtitle="Vendors and departments, with their alert history."
        action={
          <div className="flex flex-wrap gap-2">
            <input aria-label="Search" className="input !w-52" placeholder="Search by name" value={draft} onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") set({ search: draft }); }} onBlur={() => { if (draft !== search) set({ search: draft }); }} />
            <div role="group" aria-label="Entity type" className="flex overflow-hidden rounded border border-line text-sm">
              {["vendor", "department"].map((t) => (
                <button key={t} type="button" aria-pressed={type === t} onClick={() => set({ type: t })}
                  className={`px-3 py-1.5 capitalize ${type === t ? "bg-accent text-accent-fg" : "bg-surface text-muted"}`}>{t}s</button>
              ))}
            </div>
          </div>
        } />
      <Async state={state} rows={6}>
        {(data) => (
          <Card className="!p-0">
            {data.items.length === 0 ? <Empty title="Nothing found">Upload data, or change the search.</Empty> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px]">
                  <thead>
                    <tr className="border-b border-line">
                      <SortHeader label="Name" name="name" {...sortProps} />
                      {type === "vendor" && <th className="table-head">Category</th>}
                      <SortHeader label="Transactions" name="transactions" {...sortProps} />
                      <SortHeader label="Alerts" name="alerts" {...sortProps} />
                      <SortHeader label="Avg risk" name="avg_risk" {...sortProps} />
                      <th className="table-head">Alert trend, 90 days</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((e) => (
                      <tr key={e.id} className="border-b border-line/60 last:border-0 hover:bg-bg/60">
                        <td className="table-cell"><Link to={`/entities/${type}/${encodeURIComponent(e.id)}`} className="hover:underline">{e.name}</Link></td>
                        {type === "vendor" && <td className="table-cell text-muted">{e.category}</td>}
                        <td className="table-cell tabular-nums">{count(e.transactions)}</td>
                        <td className="table-cell tabular-nums">{count(e.alerts)}</td>
                        <td className="table-cell tabular-nums">{e.avg_risk.toFixed(2)}</td>
                        <td className="table-cell text-muted">{TREND[e.trend]} ({e.recent_alerts})</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={(p) => set({ page: String(p) })} />
          </Card>
        )}
      </Async>
    </>
  );
}

function Series({ profile }: { profile: Profile }) {
  const data = profile.series.map((s) => ({ ...s, label: date(s.date) }));
  type Point = (typeof data)[number];
  const dot = ({ cx, cy, payload, index }: { cx?: number; cy?: number; payload?: Point; index?: number }) => {
    if (cx == null || cy == null || !payload?.flagged) return <g key={index} />;
    return <circle key={index} cx={cx} cy={cy} r={4} fill={SERIES.mark} stroke="rgb(var(--surface))" strokeWidth={2} />;
  };
  return (
    <ChartCard title="Transactions over time" subtitle="Every invoice, flagged ones marked"
      table={<SimpleTable head={["Date", "Event", "Amount", "Level"]} rows={[...profile.series].reverse().map((s) => [date(s.date), s.event_id, inr(s.amount), s.level ?? ""])} />}>
      <Legend items={[{ label: "Amount", color: SERIES.one }, { label: "Flagged", color: SERIES.mark, dot: true }]} />
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={data} margin={{ left: 0, right: 12, top: 8 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" {...AXIS} minTickGap={60} />
          <YAxis {...AXIS} tickFormatter={axisAmount} width={44} />
          <Tooltip content={<ChartTooltip format={(v) => inr(v)} />} cursor={{ stroke: "rgb(var(--muted))" }} />
          <Line dataKey="amount" name="Amount" stroke={SERIES.one} strokeWidth={2} dot={dot} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

export function EntityProfile() {
  const { type = "vendor", id = "" } = useParams();
  const state = useApi<Profile>(`/entities/${encodeURIComponent(id)}`, { type });
  return (
    <Async state={state} rows={5}>
      {(p) => (
        <>
          <Link to={`/entities?type=${type}`} className="mb-4 inline-block text-sm text-muted hover:text-fg">← Entities</Link>
          <PageHeader title={p.name}
            subtitle={[p.type === "vendor" ? p.id : null, p.category, p.department, p.vendor_created && `Onboarded ${date(p.vendor_created)}`].filter(Boolean).join(", ")}
            action={
              <div className="flex flex-wrap items-center gap-3">
                {p.fallback_baseline && <span className="rounded border border-amber-400 px-2 py-1 text-xs">New vendor: using {p.fallback_baseline === "peer" ? "peer" : "overall"} baseline</span>}
                <Link to={`/alerts?entity=${encodeURIComponent(p.id)}`} className="text-sm text-muted underline underline-offset-2">Alerts for this {p.type}</Link>
              </div>
            } />
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Stat label="Median amount" value={inr(p.baseline.median_amount)} note={`Middle half ${inr(p.baseline.p25_amount)} to ${inr(p.baseline.p75_amount)}`} />
              <Stat label="Transactions" value={count(p.baseline.history_len)} />
              <Stat label="Median gap" value={p.baseline.median_gap_days == null ? "n/a" : plural(p.baseline.median_gap_days, "day")} />
              <Stat label="Median processing" value={p.baseline.median_processing_days == null ? "n/a" : plural(p.baseline.median_processing_days, "day")} />
            </div>
            <Series profile={p} />
            {p.peers && (
              <Card title="Peer comparison" subtitle={`${plural(p.peers.vendors, "vendor")} in ${p.peers.category}`}>
                <SimpleTable head={["Measure", "This vendor", "Peer median"]} rows={[
                  ["Median amount", inr(p.baseline.median_amount), inr(p.peers.median_amount)],
                  ["Median processing days", p.baseline.median_processing_days ?? "n/a", p.peers.median_processing_days ?? "n/a"],
                ]} />
                {p.peers.vendors > 1 && <p className="mt-3 text-sm text-muted">Median amount is at or above {percent(p.peers.amount_percentile)} of vendors in this category.</p>}
              </Card>
            )}
            <Card className="!p-0" >
              <h2 className="px-5 pt-5 text-sm font-semibold">Alerts ({p.alerts.length})</h2>
              {p.alerts.length === 0 ? <Empty title="No alerts">Nothing here has reached Medium risk.</Empty> : (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full min-w-[640px]">
                    <thead><tr className="border-b border-line">{["Alert", "Date", "Amount", "Level", "Red flags", "Status"].map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
                    <tbody>
                      {p.alerts.map((a) => (
                        <tr key={a.id} className="border-b border-line/60 last:border-0">
                          <td className="table-cell"><Link to={`/alerts/${a.id}`} className="font-medium hover:underline">{a.id}</Link></td>
                          <td className="table-cell whitespace-nowrap text-muted">{date(a.invoice_date)}</td>
                          <td className="table-cell whitespace-nowrap tabular-nums">{inr(a.amount)}</td>
                          <td className="table-cell"><LevelBadge level={a.level} /></td>
                          <td className="table-cell"><FlagChips flags={a.flags} limit={2} /></td>
                          <td className="table-cell"><StatusBadge status={a.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>
        </>
      )}
    </Async>
  );
}
