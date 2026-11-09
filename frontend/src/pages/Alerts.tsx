import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Async, Button, Card, Empty, FlagChips, LevelBadge, PageHeader, Pagination, SortHeader, StatusBadge } from "../components/ui";
import { api, toError, useApi, type AlertRow, type Paged, type Person } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date, inr, RULE_LABELS } from "../lib/format";

const PAGE_SIZE = 25;
const CLEAR = "none";

export default function Alerts() {
  const { canAct } = useAuth();
  const [params, setParams] = useSearchParams();
  const get = (key: string) => params.get(key) ?? "";
  const set = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    if (!("page" in changes)) next.delete("page");
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
  };

  const sort = get("sort") || "risk";
  const order = get("order") || "desc";
  const page = Number(get("page")) || 1;
  const state = useApi<Paged<AlertRow>>("/alerts", {
    level: get("level") || undefined, status: get("status") || undefined, rule: get("rule") || undefined,
    entity: get("entity") || undefined, search: get("search") || undefined,
    date_from: get("from") || undefined, date_to: get("to") || undefined, sort, order, page, page_size: PAGE_SIZE,
  });
  const people = useApi<Person[]>(canAct ? "/users/assignees" : null);

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [assignee, setAssignee] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState(get("search"));
  const [entity, setEntity] = useState(get("entity"));

  // Any change to the list, a sidebar link included, must not leave hidden rows selected for a bulk action.
  const query = params.toString();
  useEffect(() => {
    setSelected(new Set());
    setMessage("");
    setSearch(new URLSearchParams(query).get("search") ?? "");
    setEntity(new URLSearchParams(query).get("entity") ?? "");
  }, [query]);

  // Clearing the last page leaves it out of range, with alerts still on the pages before it.
  const data = state.data;
  useEffect(() => {
    if (data && data.items.length === 0 && data.total > 0 && page > 1) set({ page: String(Math.ceil(data.total / PAGE_SIZE)) });
  }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (id: number) => setSelected((s) => {
    const next = new Set(s);
    if (!next.delete(id)) next.add(id);
    return next;
  });

  const bulk = async (action: "assign" | "dismiss") => {
    setBusy(true);
    setMessage("");
    try {
      const { data: result } = await api.post<{ updated: number; skipped: number }>("/alerts/bulk", {
        ids: [...selected], action, assignee_id: action === "assign" && assignee !== CLEAR ? Number(assignee) : undefined,
        reason: action === "dismiss" ? "Bulk dismissal" : "Bulk assignment",
      });
      setSelected(new Set());
      state.reload();
      setMessage(`${result.updated} alerts updated.${result.skipped ? ` ${result.skipped} already decided were left as they are.` : ""}`);
    } catch (e) {
      setMessage(toError(e).message);
    } finally {
      setBusy(false);
    }
  };

  const onSort = (name: string) => set({ sort: name, order: sort === name && order === "desc" ? "asc" : "desc" });
  const sortProps = { sort, order, onSort };

  return (
    <>
      <PageHeader title="Alerts" subtitle="Events at Medium risk or above, highest first." />
      <div className="mb-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
        <input aria-label="Search" className="input xl:col-span-2" placeholder="Search vendor, event or invoice" value={search} onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") set({ search }); }} onBlur={() => { if (search !== get("search")) set({ search }); }} />
        <input aria-label="Vendor or department" className="input" placeholder="Vendor or department" value={entity} onChange={(e) => setEntity(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") set({ entity }); }} onBlur={() => { if (entity !== get("entity")) set({ entity }); }} />
        <select aria-label="Level" className="input" value={get("level")} onChange={(e) => set({ level: e.target.value })}>
          <option value="">All levels</option>{["Critical", "High", "Medium", "Low"].map((l) => <option key={l}>{l}</option>)}
        </select>
        <select aria-label="Status" className="input" value={get("status")} onChange={(e) => set({ status: e.target.value })}>
          <option value="">All statuses</option>{["Pending", "Confirmed", "Dismissed", "Escalated"].map((s) => <option key={s}>{s}</option>)}
        </select>
        <select aria-label="Rule" className="input" value={get("rule")} onChange={(e) => set({ rule: e.target.value })}>
          <option value="">All rules</option>{Object.entries(RULE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input aria-label="From date" type="date" className="input" value={get("from")} onChange={(e) => set({ from: e.target.value })} />
        <input aria-label="To date" type="date" className="input" value={get("to")} onChange={(e) => set({ to: e.target.value })} />
      </div>

      {canAct && selected.size > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 text-sm">
          <span className="font-medium">{selected.size} selected</span>
          <select aria-label="Assign to" className="input !w-44 !py-1" value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="">Choose a person</option>
            {people.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            <option value={CLEAR}>Clear assignee</option>
          </select>
          <Button variant="secondary" className="!py-1" disabled={busy || !assignee} onClick={() => bulk("assign")}>Assign</Button>
          <Button variant="danger" className="!py-1" disabled={busy} onClick={() => bulk("dismiss")}>Dismiss</Button>
        </div>
      )}
      {message && <p role="status" className="mb-3 text-sm text-muted">{message}</p>}

      <Async state={state} rows={6}>
        {(result) => (
          <Card className="!p-0">
            {result.items.length === 0 ? <Empty title="No alerts match">Try removing a filter.</Empty> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[960px]">
                  <thead>
                    <tr className="border-b border-line">
                      {canAct && <th className="table-head w-8">
                        <input type="checkbox" aria-label="Select all on this page" checked={result.items.every((a) => selected.has(a.id))}
                          onChange={(e) => setSelected(e.target.checked ? new Set(result.items.map((a) => a.id)) : new Set())} />
                      </th>}
                      <SortHeader label="ID" name="id" {...sortProps} />
                      <SortHeader label="Vendor" name="vendor" {...sortProps} />
                      <SortHeader label="Amount" name="amount" className="text-right" {...sortProps} />
                      <SortHeader label="Risk" name="risk" className="text-right" {...sortProps} />
                      <th className="table-head">Level</th>
                      <th className="table-head">Red flags</th>
                      <SortHeader label="Status" name="status" {...sortProps} />
                      <SortHeader label="Date" name="date" {...sortProps} />
                      <th className="table-head">Assignee</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.items.map((a) => (
                      <tr key={a.id} className="border-b border-line/60 last:border-0 hover:bg-bg/60">
                        {canAct && <td className="table-cell"><input type="checkbox" aria-label={`Select alert ${a.id}`} checked={selected.has(a.id)} onChange={() => toggle(a.id)} /></td>}
                        <td className="table-cell"><Link to={`/alerts/${a.id}`} className="font-medium underline-offset-2 hover:underline">{a.id}</Link></td>
                        <td className="table-cell max-w-[220px] truncate" title={a.vendor_name}>{a.vendor_name}</td>
                        <td className="table-cell whitespace-nowrap text-right tabular-nums">{inr(a.amount)}</td>
                        <td className="table-cell text-right tabular-nums">{a.risk.toFixed(2)}</td>
                        <td className="table-cell"><LevelBadge level={a.level} /></td>
                        <td className="table-cell"><FlagChips flags={a.flags} limit={2} /></td>
                        <td className="table-cell"><StatusBadge status={a.status} /></td>
                        <td className="table-cell whitespace-nowrap text-muted">{date(a.invoice_date)}</td>
                        <td className="table-cell text-muted">{a.assignee?.name ?? "Unassigned"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPage={(p) => set({ page: String(p) })} />
          </Card>
        )}
      </Async>
    </>
  );
}
