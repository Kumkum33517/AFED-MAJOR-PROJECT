import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Async, Button, Card, DownloadButton, Empty, FlagChips, LevelBadge, PageHeader, Pagination, StatusBadge } from "../components/ui";
import { api, toError, useApi, type AlertRow, type Paged, type Person } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date, dateTime, inr } from "../lib/format";

interface CaseRow {
  id: number; vendor_id: string; vendor_name: string; status: string; window_start: string; window_end: string; assignee: Person | null;
  alert_count: number; max_risk: number; total_amount: number; updated_at: string;
}
interface CaseFull extends CaseRow { notes: { author: string; at: string; text: string }[]; alerts: (AlertRow & { explanation: string })[] }

export function Cases() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const page = Number(params.get("page")) || 1;
  const navigate = useNavigate();
  const state = useApi<Paged<CaseRow>>("/cases", { status: status || undefined, page, page_size: 25 });
  return (
    <>
      <PageHeader title="Cases" subtitle="Alerts grouped per vendor over 30 days. A case needs two alerts, or one Critical."
        action={<select aria-label="Status" className="input !w-44" value={status} onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})}>
          <option value="">All statuses</option>{["Open", "Investigating", "Closed"].map((s) => <option key={s}>{s}</option>)}
        </select>} />
      <Async state={state} rows={6}>
        {(data) => (
          <Card className="!p-0">
            {data.items.length === 0 ? <Empty title="No cases">Cases open when a vendor gathers two alerts within 30 days, or one Critical alert.</Empty> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px]">
                  <thead><tr className="border-b border-line">{["Case", "Vendor", "Window", "Alerts", "Top risk", "Exposure", "Status", "Assignee"].map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
                  <tbody>
                    {data.items.map((c) => (
                      <tr key={c.id} onClick={() => navigate(`/cases/${c.id}`)} className="cursor-pointer border-b border-line/60 last:border-0 hover:bg-bg/60">
                        <td className="table-cell"><Link to={`/cases/${c.id}`} className="font-medium hover:underline">{c.id}</Link></td>
                        <td className="table-cell max-w-[220px] truncate">{c.vendor_name}</td>
                        <td className="table-cell whitespace-nowrap text-muted">{date(c.window_start)} to {date(c.window_end)}</td>
                        <td className="table-cell tabular-nums">{c.alert_count}</td>
                        <td className="table-cell tabular-nums">{c.max_risk.toFixed(2)}</td>
                        <td className="table-cell whitespace-nowrap tabular-nums">{inr(c.total_amount)}</td>
                        <td className="table-cell"><StatusBadge status={c.status} /></td>
                        <td className="table-cell text-muted">{c.assignee?.name ?? "Unassigned"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pagination page={data.page} pageSize={data.page_size} total={data.total}
              onPage={(p) => setParams({ ...(status ? { status } : {}), page: String(p) })} />
          </Card>
        )}
      </Async>
    </>
  );
}

export function CaseDetail() {
  const { id } = useParams();
  const { canAct } = useAuth();
  const state = useApi<CaseFull>(`/cases/${id}`);
  const people = useApi<Person[]>(canAct ? "/users/assignees" : null);
  const [error, setError] = useState("");
  const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm<{ text: string }>();

  const patch = async (body: object) => {
    setError("");
    try { await api.patch(`/cases/${id}`, body); state.reload(); } catch (e) { setError(toError(e).message); }
  };
  const addNote = handleSubmit(async ({ text }) => {
    setError("");
    try { await api.post(`/cases/${id}/notes`, { text }); reset(); state.reload(); } catch (e) { setError(toError(e).message); }
  });

  return (
    <Async state={state} rows={5}>
      {(c) => (
        <>
          <Link to="/cases" className="mb-4 inline-block text-sm text-muted hover:text-fg">← Cases</Link>
          <PageHeader title={`Case ${c.id}: ${c.vendor_name}`} subtitle={`${date(c.window_start)} to ${date(c.window_end)}, ${c.alert_count} alerts, ${inr(c.total_amount)} exposure`}
            action={<DownloadButton path={`/reports/case/${c.id}.pdf`} filename={`afed-case-${c.id}.pdf`}>Export PDF</DownloadButton>} />
          {error && <p role="alert" className="notice-error mb-3">{error}</p>}
          <Card title="What this case is about" className="mb-5">
            <p className="text-sm">
              {c.vendor_name} raised {c.alert_count} alert{c.alert_count === 1 ? "" : "s"} between {date(c.window_start)} and {date(c.window_end)},
              worth {inr(c.total_amount)} in total. The highest risk score is {c.max_risk.toFixed(2)}.
              {[...new Set(c.alerts.flatMap((a) => a.flags))].length > 0 && <> Red flags raised: <FlagChips flags={[...new Set(c.alerts.flatMap((a) => a.flags))]} />.</>}
            </p>
            <ul className="mt-4 space-y-3 text-sm">
              {c.alerts.map((a) => (
                <li key={a.id} className="border-l-2 border-brick/50 pl-3">
                  <p className="flex items-center gap-2 text-xs text-muted"><LevelBadge level={a.level} /><span><Link to={`/alerts/${a.id}`} className="hover:underline">Alert {a.id}</Link>, {date(a.invoice_date)}, {inr(a.amount)}</span></p>
                  <p>{a.explanation || "No explanation recorded."}</p>
                </li>
              ))}
            </ul>
          </Card>
          <div className="grid gap-5 lg:grid-cols-3">
            <Card className="!p-0 lg:col-span-2">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px]">
                  <thead><tr className="border-b border-line">{["Alert", "Date", "Amount", "Level", "Red flags", "Status"].map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
                  <tbody>
                    {c.alerts.map((a) => (
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
            </Card>
            <div className="space-y-5">
              <Card title="Workflow">
                {canAct ? (
                  <div className="space-y-3">
                    <label className="block text-xs text-muted">Status
                      <select className="input mt-1" value={c.status} onChange={(e) => patch({ status: e.target.value })}>
                        {["Open", "Investigating", "Closed"].map((s) => <option key={s}>{s}</option>)}
                      </select>
                    </label>
                    <label className="block text-xs text-muted">Assignee
                      <select className="input mt-1" value={c.assignee?.id ?? ""} onChange={(e) => patch({ assignee_id: Number(e.target.value) || null })}>
                        <option value="">Unassigned</option>{people.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                      </select>
                    </label>
                  </div>
                ) : <p className="text-sm"><StatusBadge status={c.status} /> <span className="ml-2 text-muted">{c.assignee?.name ?? "Unassigned"}</span></p>}
              </Card>
              <Card title="Notes">
                {c.notes.length === 0 && <p className="mb-3 text-sm text-muted">No notes yet.</p>}
                <ul className="mb-3 space-y-3 text-sm">
                  {c.notes.map((n, i) => <li key={i}><p className="whitespace-pre-wrap">{n.text}</p><p className="text-xs text-muted">{n.author}, {dateTime(n.at)}</p></li>)}
                </ul>
                {canAct && (
                  <form onSubmit={addNote} className="space-y-2">
                    <textarea aria-label="New note" className="input" rows={2} {...register("text", { required: true })} />
                    <Button type="submit" variant="secondary" disabled={isSubmitting}>Add note</Button>
                  </form>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </Async>
  );
}
