import { useEffect, useRef, useState } from "react";
import { Async, Button, Card, Empty, Field, PageHeader, SimpleTable, StatusBadge } from "../components/ui";
import { api, NOTIFICATIONS_CHANGED, toError, useApi, type RunRow } from "../lib/api";
import { count, dateTime, humanise } from "../lib/format";

interface Preview {
  upload_id: string; filename: string; columns: string[]; sample: Record<string, string>[]; suggested: Record<string, string>;
  required: string[]; optional: string[]; labels: string[];
}
interface Report { ok: boolean; rows: number; errors: string[]; warnings: string[]; dropped_rows: number; missing_optional: string[] }

const SAMPLES = `${import.meta.env.BASE_URL}samples/`;
const POLL_MS = 800;
const MAX_POLL_FAILURES = 10;

function Progress({ run }: { run: RunRow }) {
  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <div className="mb-2 flex justify-between text-sm"><span>{run.stage}</span><span className="tabular-nums">{run.progress}%</span></div>
      <div role="progressbar" aria-valuenow={run.progress} aria-valuemin={0} aria-valuemax={100} aria-label="Run progress" className="h-2 rounded bg-bg">
        <div className="h-2 rounded bg-accent transition-all" style={{ width: `${run.progress}%` }} />
      </div>
    </div>
  );
}

export default function Upload() {
  const history = useApi<RunRow[]>("/upload/runs");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [runId, setRunId] = useState<number | null>(null);
  const [run, setRun] = useState<RunRow | null>(null);

  const [starting, setStarting] = useState(false);
  const finished = useRef(new Set<number>());

  // Poll while a run is active. A run already in progress is picked up on page load.
  const active = history.data?.find((r) => r.status === "queued" || r.status === "running");
  // A slow history reply can still list a run as active after polling saw it finish, so finished runs are remembered.
  useEffect(() => { if (active && !runId && !finished.current.has(active.id)) setRunId(active.id); }, [active, runId]);
  useEffect(() => {
    if (!runId) return;
    let stopped = false;
    let failures = 0;
    const poll = async () => {
      try {
        const { data } = await api.get<RunRow>(`/upload/runs/${runId}`);
        if (stopped) return;
        failures = 0;
        setRun(data);
        if (data.status === "completed" || data.status === "failed") {
          finished.current.add(data.id);
          setRunId(null);
          history.reload();
          window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED));
          return;
        }
      } catch (e) {
        if (stopped) return;
        failures += 1;  // one failed poll, such as a brief restart, must not freeze the page
        if (failures >= MAX_POLL_FAILURES) {
          setError(`Lost contact with the run: ${toError(e).message}. Reload this page to see how it ended.`);
          setRunId(null);
          return;
        }
      }
      setTimeout(() => { if (!stopped) void poll(); }, POLL_MS);
    };
    void poll();
    return () => { stopped = true; };
  }, [runId]); // eslint-disable-line react-hooks/exhaustive-deps

  const choose = async (file?: File) => {
    if (!file) return;
    setError(""); setReport(null); setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post<Preview>("/upload/preview", form);
      setPreview(data);
      setMapping(data.suggested);
    } catch (e) {
      setError(toError(e).message);
    } finally {
      setBusy(false);
    }
  };

  // The sample goes through the same preview, mapping and validation as any file, so the demo shows the real path.
  const useSample = async () => {
    setError(""); setBusy(true);
    try {
      const response = await fetch(`${SAMPLES}nspcl_sample.csv`);
      if (!response.ok) throw new Error(`The sample file could not be loaded (${response.status}).`);
      await choose(new File([await response.blob()], "nspcl_sample.csv", { type: "text/csv" }));
    } catch (e) {
      setError(toError(e).message);
      setBusy(false);
    }
  };

  const validate = async () => {
    setError(""); setBusy(true);
    try {
      setReport((await api.post<Report>("/upload/validate", { upload_id: preview!.upload_id, mapping })).data);
    } catch (e) {
      setError(toError(e).message);
    } finally {
      setBusy(false);
    }
  };

  const start = async (path: string, body?: object) => {
    setError(""); setRun(null); setStarting(true);
    try {
      const { data } = await api.post<{ run_id: number }>(path, body);
      setRunId(data.run_id);
      setPreview(null); setReport(null);
    } catch (e) {
      setError(toError(e).message);
    } finally {
      setStarting(false);
    }
  };

  const running = runId !== null || starting;
  return (
    <>
      <PageHeader title="Data & runs" subtitle="New events join the stored history, then every event is rescored. Reviewer decisions are kept."
        action={<Button variant="secondary" disabled={running} onClick={() => start("/upload/rerun")}>Rerun on stored events</Button>} />
      <div className="space-y-5">
        {error && <p role="alert" className="notice-error">{error}</p>}
        {running && run && <Progress run={run} />}
        {!running && run?.status === "completed" && <p role="status" className="text-sm">Run {run.id} finished: {count(run.rows)} events, {count(run.alerts)} alerts.</p>}
        {!running && run?.status === "failed" && <p role="alert" className="notice-error">Run {run.id} failed: {run.error}</p>}

        <Card title="1. Choose a CSV" subtitle="Needs event_id, vendor_id, amount and invoice_date, under any column names. Up to 50 MB.">
          <input aria-label="CSV file" type="file" accept=".csv,text/csv" disabled={busy || running} className="text-sm text-muted file:mr-3 file:cursor-pointer file:rounded file:border-0 file:bg-accent file:px-3.5 file:py-2 file:text-sm file:font-medium file:text-accent-fg" onChange={(e) => { void choose(e.target.files?.[0]); e.target.value = ""; }} />
          <div className="mt-5 grid gap-4 border-t border-line pt-4 text-sm sm:grid-cols-2">
            <div>
              <p className="font-medium">No file to hand?</p>
              <p className="mt-0.5 text-xs text-muted">5,745 real payments by 80 vendors of NSPCL, a Government of India joint venture, from 2023 to 2026. Unlabelled, as real data is.</p>
              <Button variant="secondary" className="mt-2" disabled={busy || running} onClick={useSample}>Use the NSPCL sample</Button>
              <p className="mt-1.5 text-[11px] text-muted">Source: NSPCL vendor payments, nspcl.co.in, reproduced with acknowledgement.</p>
            </div>
            <div>
              <p className="font-medium">Preparing your own data?</p>
              <p className="mt-0.5 text-xs text-muted">Every column AFED understands, with two example rows. Only the first four are required; label columns are for evaluation.</p>
              <a href={`${SAMPLES}afed_template.csv`} download className="mt-2 inline-flex items-center gap-1.5 rounded border border-line bg-surface px-3.5 py-2 text-sm font-medium hover:bg-bg">Download the CSV template</a>
            </div>
          </div>
        </Card>

        {preview && (
          <Card title="2. Map the columns" subtitle={`${preview.filename}: ${preview.columns.length} columns found`}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[...preview.required, ...preview.optional, ...preview.labels].map((target) => (
                <Field key={target} label={`${humanise(target)}${preview.required.includes(target) ? " (required)" : ""}`}>
                  <select className="input" value={mapping[target] ?? ""} onChange={(e) => { setMapping({ ...mapping, [target]: e.target.value }); setReport(null); }}>
                    <option value="">Not in file</option>{preview.columns.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </Field>
              ))}
            </div>
            <div className="mt-4 overflow-x-auto">
              <SimpleTable head={preview.columns} rows={preview.sample.slice(0, 3).map((r) => preview.columns.map((c) => r[c]))} />
            </div>
            <Button className="mt-4" disabled={busy} onClick={validate}>Validate</Button>
          </Card>
        )}

        {report && (
          <Card title="3. Validation report" subtitle={`${count(report.rows)} rows read, ${count(report.dropped_rows)} would be dropped`}>
            {report.errors.map((e) => <p key={e} role="alert" className="notice-error">{e}</p>)}
            {report.warnings.length > 0 && <ul className="list-inside list-disc space-y-1 text-sm text-muted">{report.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
            {report.ok && !report.warnings.length && <p className="text-sm">No problems found.</p>}
            <Button className="mt-4" disabled={!report.ok || running} onClick={() => start("/upload/run", { upload_id: preview!.upload_id, mapping })}>Run detection</Button>
          </Card>
        )}

        <Async state={history} rows={2}>
          {(runs) => (
            <Card title="Run history" className="!p-0 [&>div:first-child]:px-5 [&>div:first-child]:pt-5">
              {runs.length === 0 ? <Empty title="No runs yet">Upload a CSV to start.</Empty> : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px]">
                    <thead><tr className="border-b border-line">{["Run", "Date", "Source", "Rows", "New", "Alerts", "Model", "Status"].map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
                    <tbody>
                      {runs.map((r) => (
                        <tr key={r.id} className="border-b border-line/60 last:border-0">
                          <td className="table-cell font-medium">{r.id}</td>
                          <td className="table-cell whitespace-nowrap text-muted">{dateTime(r.started_at)}</td>
                          <td className="table-cell">{r.source}</td>
                          <td className="table-cell tabular-nums">{count(r.rows)}</td>
                          <td className="table-cell tabular-nums">{count(r.new_rows)}</td>
                          <td className="table-cell tabular-nums">{count(r.alerts)}</td>
                          <td className="table-cell text-muted">{r.model_version ?? "n/a"}</td>
                          <td className="table-cell" title={r.error ?? undefined}><StatusBadge status={humanise(r.status)} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}
        </Async>
      </div>
    </>
  );
}
