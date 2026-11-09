import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useParams } from "react-router-dom";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, axisAmount, ChartTooltip, GRID, Legend, Meter, RangeStrip, RiskGauge, SERIES } from "../components/charts";
import { Async, Button, Card, ChartCard, DownloadButton, Empty, Field, FlagChips, LevelBadge, SimpleTable, StatusBadge } from "../components/ui";
import { api, toError, useApi, type AlertDetail as Detail, type AlertRow, type Person } from "../lib/api";
import { useAuth } from "../lib/auth";
import { date, dateTime, humanise, inr, wallClock } from "../lib/format";

type Action = "confirm" | "dismiss" | "escalate";
const REASONS: Record<Action, string[]> = {
  confirm: ["Verified with documents", "Vendor could not justify", "Policy breach", "Other"],
  dismiss: ["Legitimate business reason", "Known seasonal order", "Data entry error", "Other"],
  escalate: ["Needs senior review", "High value", "Pattern across vendors", "Other"],
};
const SCORE_ROWS = [
  { key: "lstm", label: "LSTM error", hint: "percentile" }, { key: "isolation_forest", label: "Isolation Forest", hint: "A" },
  { key: "entity_deviation", label: "Entity deviation", hint: "D" }, { key: "rules", label: "Rules", hint: "F" },
] as const;

function Explanation({ alert }: { alert: Detail }) {
  const { user } = useAuth();
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const [override, setOverride] = useState<{ text: string; provider: string; fellBack: boolean } | null>(null);
  const [showFacts, setShowFacts] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const latest = useRef(0);

  const narrate = async (next: "en" | "hi") => {
    const request = ++latest.current;  // a slower, older reply must not overwrite a newer one
    setBusy(true);
    setError("");
    try {
      const { data } = await api.get<{ explanation: string; provider: string; fell_back: boolean }>(`/alerts/${alert.id}/explain`, { params: { language: next } });
      if (request !== latest.current) return;
      setLanguage(next);
      setOverride({ text: data.explanation, provider: data.provider, fellBack: data.fell_back });
    } catch (e) {
      if (request === latest.current) setError(toError(e).message);
    } finally {
      if (request === latest.current) setBusy(false);
    }
  };

  // The stored explanation is English; a Hindi reader's has to be fetched.
  useEffect(() => { if (user?.preferences.language === "hi") void narrate("hi"); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const hi = language === "hi";
  const provider = override?.provider ?? alert.explanation_provider;
  return (
    <Card title="Why this was flagged" subtitle={override?.fellBack ? "Qwen's wording did not pass the fact check, so the template is shown"
        : provider === "template" ? "Written from the facts by template" : `Reworded by Qwen (${provider}) from the facts only, and checked`}
      action={
        <div className="flex items-center gap-2 text-xs">
          <div role="group" aria-label="Language" className="flex overflow-hidden rounded border border-line">
            {(["en", "hi"] as const).map((l) => (
              <button key={l} type="button" aria-pressed={language === l} onClick={() => narrate(l)}
                className={`px-2 py-1 ${language === l ? "bg-accent text-accent-fg" : "text-muted"}`}>{l === "en" ? "EN" : "हिं"}</button>
            ))}
          </div>
          <Button variant="secondary" className="!px-2 !py-1 !text-xs" disabled={busy} onClick={() => narrate(language)}>{busy ? "Working..." : "Regenerate"}</Button>
        </div>
      }>
      <p lang={hi ? "hi" : "en"} className="leading-relaxed">{override?.text ?? alert.explanation}</p>
      {error && <p role="alert" className="notice-error mt-2">{error}</p>}
      <button type="button" aria-expanded={showFacts} onClick={() => setShowFacts(!showFacts)} className="mt-3 text-xs text-muted underline underline-offset-2">
        {showFacts ? "Hide facts" : `Show facts (${alert.facts.length})`}
      </button>
      {showFacts && (
        <div className="mt-3 overflow-x-auto">
          <SimpleTable head={["Fact", "Observed", "Baseline", "Ratio"]} rows={alert.facts.map((f) => [
            <span lang={hi ? "hi" : "en"}>{hi ? f.text_hi : f.text}</span>, f.observed ?? "", f.baseline ?? "", f.ratio ? `${f.ratio}x` : "",
          ])} />
        </div>
      )}
    </Card>
  );
}

const DONE: Record<Action, string> = { confirm: "Confirmed", dismiss: "Dismissed", escalate: "Escalated" };

function Actions({ alert, onDone }: { alert: Detail; onDone: () => void }) {
  const [action, setAction] = useState<Action | null>(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState("");
  const people = useApi<Person[]>("/users/assignees");
  const { register, handleSubmit, reset, formState: { isSubmitting, errors } } = useForm<{ reason: string; comment: string }>({ defaultValues: { reason: "", comment: "" } });

  const open = (next: Action) => {
    reset({ reason: "", comment: "" });  // each action has its own reasons, so one must not carry over to another
    setAction(next);
    setSaved("");
  };

  const submit = handleSubmit(async (values) => {
    setError("");
    try {
      await api.post(`/alerts/${alert.id}/${action}`, values);
      setSaved(`${DONE[action!]}, and recorded under Activity.`);
      setAction(null);
      onDone();
    } catch (e) {
      setError(toError(e).message);
    }
  });

  const assign = async (value: string) => {
    setError("");
    try {
      await api.post(`/alerts/${alert.id}/assign`, { assignee_id: Number(value) || null });
      onDone();
    } catch (e) {
      setError(toError(e).message);
    }
  };

  const current = alert.assignee;
  const options = current && !people.data?.some((p) => p.id === current.id) ? [...(people.data ?? []), current] : people.data ?? [];
  return (
    <Card title="Decision">
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => open("confirm")}>Confirm</Button>
        <Button variant="secondary" onClick={() => open("dismiss")}>Dismiss</Button>
        <Button variant="danger" onClick={() => open("escalate")}>Escalate</Button>
      </div>
      {saved && <p role="status" className="mt-3 text-sm text-muted">{saved}</p>}
      {action && (
        <form key={action} onSubmit={submit} className="mt-4 space-y-3 border-t border-line pt-4">
          <Field label={`Reason to ${action}`} error={errors.reason?.message}>
            <select className="input" {...register("reason", { required: "Choose a reason" })}>
              <option value="" disabled>Choose a reason</option>
              {REASONS[action].map((r) => <option key={r}>{r}</option>)}
            </select>
          </Field>
          <Field label="Comment"><textarea className="input" rows={2} {...register("comment")} /></Field>
          <div className="flex gap-2">
            <Button type="submit" disabled={isSubmitting}>Save decision</Button>
            <Button variant="ghost" onClick={() => setAction(null)}>Cancel</Button>
          </div>
        </form>
      )}
      <div className="mt-4 border-t border-line pt-4">
        <Field label="Assignee">
          <select className="input" value={current?.id ?? ""} onChange={(e) => assign(e.target.value)}>
            <option value="">Unassigned</option>{options.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </Field>
      </div>
      {error && <p role="alert" className="notice-error mt-2">{error}</p>}
    </Card>
  );
}

function Sequence({ alert }: { alert: Detail }) {
  const data = alert.sequence.map((s) => ({ ...s, label: date(s.date), flagged: s.level && s.level !== "Low" ? s.actual : null }));
  const hasForecast = alert.sequence.some((s) => s.expected != null);
  type Point = (typeof data)[number];
  const dot = (props: { cx?: number; cy?: number; payload?: Point; index?: number }) => {
    const { cx, cy, payload, index } = props;
    if (cx == null || cy == null || !payload?.flagged) return <g key={index} />;
    const r = payload.current ? 6 : 4;
    return <circle key={index} cx={cx} cy={cy} r={r} fill={SERIES.mark} stroke="rgb(var(--surface))" strokeWidth={2} />;
  };
  return (
    <ChartCard title={`Last ${alert.sequence.length} invoices from this vendor`} subtitle={hasForecast ? "Actual amount against what the LSTM expected from the sequence" : "The LSTM did not run, so there is no expected line"}
      table={<SimpleTable head={["Date", "Actual", "LSTM expected", "Level"]} rows={alert.sequence.map((s) => [date(s.date), inr(s.actual), inr(s.expected), s.level ?? ""])} />}>
      <Legend items={[{ label: "Actual", color: SERIES.one }, ...(hasForecast ? [{ label: "LSTM expected", color: SERIES.two, dashed: true }] : []), { label: "Flagged", color: SERIES.mark, dot: true }]} />
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={data} margin={{ left: 0, right: 12, top: 8 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" {...AXIS} minTickGap={50} />
          <YAxis {...AXIS} tickFormatter={axisAmount} width={44} />
          <Tooltip content={<ChartTooltip format={(v) => inr(v)} />} cursor={{ stroke: "rgb(var(--muted))" }} />
          <Line dataKey="expected" name="LSTM expected" stroke={SERIES.two} strokeWidth={2} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
          <Line dataKey="actual" name="Actual" stroke={SERIES.one} strokeWidth={2} dot={dot} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function AlertList({ items, empty }: { items: (AlertRow & { shared_flags?: string[] })[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <ul className="space-y-2 text-sm">
      {items.map((a) => (
        <li key={a.id} className="flex items-center justify-between gap-2">
          <Link to={`/alerts/${a.id}`} className="truncate hover:underline">{a.id} {a.shared_flags ? a.vendor_name : date(a.invoice_date)}</Link>
          <span className="flex flex-shrink-0 items-center gap-1.5"><LevelBadge level={a.level} /><StatusBadge status={a.status} /></span>
        </li>
      ))}
    </ul>
  );
}

export default function AlertDetail() {
  const { id } = useParams();
  const { canAct } = useAuth();
  const state = useApi<Detail>(`/alerts/${id}`);
  const similar = useApi<(AlertRow & { shared_flags: string[] })[]>(`/alerts/${id}/similar`);
  useEffect(() => { window.scrollTo(0, 0); }, [id]);  // braces: Chrome's scrollTo returns a Promise, which React would call as a cleanup

  return (
    <Async state={state} rows={6}>
      {(a) => {
        const e = a.event;
        const range = a.normal_range;
        return (
          <div className="space-y-5">
            <div>
              <Link to="/alerts" className="mb-4 inline-block text-sm text-muted hover:text-fg">← Alerts</Link>
              <div className="mt-1 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
                <div className="min-w-0">
                  <h1 className="font-serif text-3xl font-medium tracking-tight">
                    <Link to={`/entities/vendor/${encodeURIComponent(a.vendor_id)}`} className="hover:underline">{a.vendor_name}</Link>
                  </h1>
                  <p className="mt-1 text-lg font-medium tabular-nums">{inr(a.amount)} <span className="text-sm font-normal text-muted">on {date(a.invoice_date)}</span></p>
                  <p className="mt-1 break-words text-sm text-muted">Alert {a.id}, event {a.event_id}{e.invoice_number ? `, invoice ${e.invoice_number}` : ""}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <LevelBadge level={a.level} /><StatusBadge status={a.status} />
                    <DownloadButton path={`/reports/alert/${a.id}.pdf`} filename={`afed-alert-${a.id}.pdf`} className="!py-1">PDF</DownloadButton>
                  </div>
                </div>
                <div className="w-44 flex-shrink-0"><RiskGauge risk={a.risk} level={a.level} cuts={[a.thresholds.medium, a.thresholds.high, a.thresholds.critical]} /></div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <div className="min-w-0 space-y-5 lg:col-span-2">
                <Explanation key={a.id} alert={a} />
                <Card title="Score breakdown" subtitle="Each signal runs from 0 to 1. Risk combines A, D and F.">
                  <div className="space-y-3">{SCORE_ROWS.map((row) => <Meter key={row.key} label={row.label} hint={row.hint} value={a.scores[row.key]} />)}</div>
                </Card>
                <Card title="This event against the vendor's normal range" subtitle={`Based on ${range.count} earlier invoices, log scale`}>
                  {range.p10 != null && range.p50 != null && range.p90 != null
                    ? <RangeStrip amount={a.amount} p10={range.p10} p50={range.p50} p90={range.p90} />
                    : <Empty title="No earlier invoices">This is the vendor's first invoice.</Empty>}
                </Card>
                <Sequence alert={a} />
              </div>

              <div className="min-w-0 space-y-5">
                <Card title="Event">
                  <dl className="space-y-2 text-sm">
                    {[["Amount", inr(a.amount)], ["Usual amount", inr(e.baseline_amount as number)], ["Invoice date", date(a.invoice_date)],
                      ["Approved", wallClock(e.approval_date as string | null)], ["Category", e.category], ["Department", e.department],
                      ["Approver", e.approver_id], ["Created by", e.created_by], ["Baseline from", e.baseline_source], ["Model", a.model_version]]
                      .map(([k, v]) => <div key={String(k)} className="flex justify-between gap-3"><dt className="text-muted">{k}</dt><dd className="text-right">{v ?? "n/a"}</dd></div>)}
                  </dl>
                  <div className="mt-4 border-t border-line pt-3"><p className="mb-2 text-xs text-muted">Red flags</p><FlagChips flags={a.flags} /></div>
                </Card>
                {canAct && <Actions key={a.id} alert={a} onDone={state.reload} />}
                <Card title="Related alerts" subtitle="Same vendor"
                  action={a.case_id ? <Link to={`/cases/${a.case_id}`} className="text-xs text-muted underline underline-offset-2">Case {a.case_id}</Link> : undefined}>
                  <AlertList items={a.related} empty="No other alerts for this vendor." />
                </Card>
                <Card title="Similar alerts" subtitle={a.flags.length ? "Other vendors, same red flags" : "Other vendors, also with no red flags"}>
                  {similar.error ? <p role="alert" className="notice-error">{similar.error.message}</p>
                    : similar.data ? <AlertList items={similar.data} empty="None found." /> : <p className="text-sm text-muted">Loading...</p>}
                </Card>
                <Card title="Activity">
                  {a.timeline.length === 0 ? <p className="text-sm text-muted">No activity yet.</p> : (
                    <ol className="space-y-3 text-sm">
                      {a.timeline.map((t, i) => (
                        <li key={i}>
                          <p>{humanise(t.action.replace("alert_", ""))} by {t.user}</p>
                          {t.detail.reason && <p className="text-xs text-muted">{t.detail.reason}{t.detail.comment ? `: ${t.detail.comment}` : ""}</p>}
                          <p className="text-xs text-muted">{dateTime(t.at)}</p>
                        </li>
                      ))}
                    </ol>
                  )}
                </Card>
              </div>
            </div>
          </div>
        );
      }}
    </Async>
  );
}
