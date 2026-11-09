import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, ChartTooltip, GRID, SERIES } from "../components/charts";
import { Async, Card, ChartCard, Empty, LEVEL_FILL, LevelBadge, PageHeader, SimpleTable, Stat, StatusBadge } from "../components/ui";
import { useApi, type AlertRow } from "../lib/api";
import { count, date, dateTime, humanise, inr } from "../lib/format";

interface Data {
  kpis: { total_events: number; flagged: number; critical: number; pending: number; open_cases: number };
  levels: { level: string; count: number }[];
  over_time: { month: string; alerts: number }[];
  top_vendors: { vendor_id: string; vendor_name: string; alerts: number; avg_risk: number; max_risk: number }[];
  recent_alerts: AlertRow[];
  simulated_reviews: number;
  last_run: { id: number; status: string; rows: number; alerts: number; model_version: string | null; finished_at: string | null; source: string } | null;
}

function Levels({ levels }: { levels: Data["levels"] }) {
  const total = Math.max(levels.reduce((sum, l) => sum + l.count, 0), 1);
  return (
    <div className="space-y-3">
      {[...levels].reverse().map((l) => {
        const row = (
          <>
            <span><LevelBadge level={l.level} /></span>
            <span className="h-3 rounded-r bg-bg"><span className="block h-3 rounded-r" style={{ width: `${Math.max((l.count / total) * 100, 1)}%`, background: LEVEL_FILL[l.level] }} /></span>
            <span className="text-right font-medium tabular-nums">{count(l.count)}</span>
          </>
        );
        const layout = "grid grid-cols-[72px_1fr_56px] items-center gap-3 text-sm";
        return l.level === "Low"
          ? <div key={l.level} className={layout}>{row}</div>
          : <Link key={l.level} to={`/alerts?level=${l.level}`} className={`${layout} hover:opacity-80`}>{row}</Link>;
      })}
    </div>
  );
}

export default function Dashboard() {
  const state = useApi<Data>("/dashboard");
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Where reviewers' attention is needed." />
      <Async state={state}>
        {(d) => d.kpis.total_events === 0 ? (
          <Card><Empty title="No events yet">Upload a CSV under Data &amp; runs, or run <code>python scripts/seed.py</code>.</Empty></Card>
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
              <Stat label="Total events" value={count(d.kpis.total_events)} />
              <Stat label="Flagged" value={count(d.kpis.flagged)} note={`${((d.kpis.flagged / d.kpis.total_events) * 100).toFixed(1)}% of events`} />
              <Stat label="Critical" value={count(d.kpis.critical)} />
              <Stat label="Pending review" value={count(d.kpis.pending)} note={d.simulated_reviews ? `${d.simulated_reviews} others have simulated reviews` : undefined} />
              <Stat label="Open cases" value={count(d.kpis.open_cases)} />
            </div>
            <div className="grid gap-5 lg:grid-cols-3">
              <ChartCard className="lg:col-span-2" title="Flagged events over time" subtitle="Alerts per month, by invoice date"
                table={<SimpleTable head={["Month", "Alerts"]} rows={d.over_time.map((m) => [m.month, m.alerts])} />}>
                <ResponsiveContainer width="100%" height={230}>
                  <AreaChart data={d.over_time} margin={{ left: -18, right: 8, top: 6 }}>
                    <CartesianGrid {...GRID} />
                    <XAxis dataKey="month" {...AXIS} minTickGap={40} />
                    <YAxis {...AXIS} allowDecimals={false} />
                    <Tooltip content={<ChartTooltip />} cursor={{ stroke: "rgb(var(--muted))" }} />
                    <Area type="monotone" dataKey="alerts" name="Alerts" stroke={SERIES.accent} strokeWidth={2} fill={SERIES.accent} fillOpacity={0.1} isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </ChartCard>
              <Card title="Risk levels" subtitle="Every scored event; bars show its share"><Levels levels={d.levels} />
                {d.last_run && (
                  <div className="mt-6 border-t border-line pt-4 text-sm">
                    <p className="text-xs text-muted">Last run</p>
                    <p className="mt-1 font-medium">{humanise(d.last_run.status)}{d.last_run.finished_at ? `, ${dateTime(d.last_run.finished_at)}` : ""}</p>
                    <p className="text-xs text-muted">{count(d.last_run.rows)} events, {count(d.last_run.alerts)} alerts</p>
                    <p className="text-xs text-muted">Model {d.last_run.model_version ?? "n/a"}</p>
                  </div>
                )}
              </Card>
            </div>
            <div className="grid gap-5 lg:grid-cols-5">
              <Card className="lg:col-span-2" title="Riskiest vendors" subtitle="By total risk across alerts">
                {d.top_vendors.length === 0 && <p className="text-sm text-muted">No alerts yet.</p>}
                <ol className="space-y-3">
                  {d.top_vendors.map((v) => (
                    <li key={v.vendor_id} className="flex items-baseline justify-between gap-3 text-sm">
                      <Link to={`/entities/vendor/${encodeURIComponent(v.vendor_id)}`} className="truncate hover:underline">{v.vendor_name}</Link>
                      <span className="whitespace-nowrap text-xs tabular-nums text-muted">{v.alerts} alerts, avg {v.avg_risk.toFixed(2)}</span>
                    </li>
                  ))}
                </ol>
              </Card>
              <Card className="lg:col-span-3" title="Recent alerts" subtitle="Latest invoices flagged" action={<Link to="/alerts" className="text-xs text-muted underline underline-offset-2">All alerts</Link>}>
                {d.recent_alerts.length === 0 && <p className="text-sm text-muted">No alerts yet.</p>}
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <tbody>
                      {d.recent_alerts.map((a) => (
                        <tr key={a.id} className="border-b border-line/60 last:border-0">
                          <td className="table-cell !pl-0"><Link to={`/alerts/${a.id}`} className="hover:underline">{a.vendor_name}</Link><span className="block text-xs text-muted">{date(a.invoice_date)}</span></td>
                          <td className="table-cell text-right whitespace-nowrap tabular-nums">{inr(a.amount)}</td>
                          <td className="table-cell"><LevelBadge level={a.level} /></td>
                          <td className="table-cell !pr-0 text-right"><StatusBadge status={a.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          </div>
        )}
      </Async>
    </>
  );
}
