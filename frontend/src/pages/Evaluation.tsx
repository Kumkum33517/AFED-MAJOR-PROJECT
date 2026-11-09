import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, ChartTooltip, GRID, Legend, SERIES } from "../components/charts";
import { Async, Card, ChartCard, Empty, PageHeader, SimpleTable, Stat } from "../components/ui";
import { useApi } from "../lib/api";
import { count, humanise, inr, percent } from "../lib/format";

interface Variant {
  roc_auc: number; average_precision: number; precision_at_k: Record<string, number>; precision: number; recall: number; false_alarm_rate: number;
  true_positives: number; false_positives: number; recall_by_type: Record<string, number>;
  f1?: number; accuracy?: number; balanced_accuracy?: number; false_negative_rate?: number; confusion?: { tp: number; fp: number; fn: number; tn: number };
}
interface Operational {
  anomaly_detection_rate: number; fraud_detection_rate: null;
  amount_at_risk: { alerted: number; anomalous_caught: number; anomalous_missed: number; anomalous_total: number; all_events: number };
  investigation: { events: number; reviewed: number; reduction_vs_all: number; baseline_reviews_for_same_recall: number | null; reduction_vs_baseline: number | null };
  score_distribution: { bins: number[]; normal: number[]; anomalous: number[] };
  processing_seconds: number; ms_per_event: number;
}
interface Compared {
  accuracy: number; balanced_accuracy?: number; precision: number; recall: number; f1: number; roc_auc: number; pr_auc: number;
  false_positive_rate: number; false_negative_rate: number; alerts: number;
  confusion?: { tp: number; fp: number; fn: number; tn: number };
}
interface Metrics extends Partial<Operational> {
  comparison?: Record<string, Compared> | null;
  labelled_events: number; anomalies: number; review_budget: number; variants: Record<string, Variant>; recalibrated_on_reviews?: number;
  detection_rate: number; baseline_detection_rate: number; false_alarm_reduction: number | null;
}
type BenchMeasure = "f1" | "balanced_accuracy" | "recall" | "precision" | "roc_auc" | "pr_auc" | "accuracy";
interface Benchmarks {
  models: Record<string, string>;
  datasets: { name: string; real: boolean; seeds: number; events: number; results: Record<string, Record<BenchMeasure, number>> }[];
}
interface Data {
  benchmarks: Benchmarks | null;
  metrics: Metrics | null; model_version: string | null; variant_labels: Record<string, string>; comparison_labels: Record<string, string>;
  feedback: { totals: Record<string, number>; seeded: number; trend: { week: string; Confirmed: number; Dismissed: number; Escalated: number; false_alarm_share: number | null }[] };
}
const MEASURES = { recall: "Recall", precision: "Precision", average_precision: "Average precision", roc_auc: "ROC-AUC" } as const;
type Measure = keyof typeof MEASURES;

function Ablation({ metrics, labels }: { metrics: Metrics; labels: Record<string, string> }) {
  const [measure, setMeasure] = useState<Measure>("recall");
  const keys = Object.keys(labels);
  const data = keys.map((k) => ({ key: k, name: labels[k], value: metrics.variants[k][measure] }));
  return (
    <ChartCard title="Ablation at the same review budget" subtitle={`Each variant reviews its top ${count(metrics.review_budget)} events`}
      hint="Each bar is AFED with parts added one at a time, all allowed the same number of reviews. The step from one bar to the next is what that part adds."
      table={<SimpleTable head={["Variant", "ROC-AUC", "Avg precision", "Precision", "Recall", "False-alarm rate"]} rows={keys.map((k) => {
        const v = metrics.variants[k];
        return [labels[k], v.roc_auc.toFixed(3), v.average_precision.toFixed(3), v.precision.toFixed(3), v.recall.toFixed(3), percent(v.false_alarm_rate, 2)];
      })} />}>
      <div role="group" aria-label="Measure" className="mb-3 flex flex-wrap gap-1 text-xs">
        {(Object.keys(MEASURES) as Measure[]).map((m) => (
          <button key={m} type="button" aria-pressed={m === measure} onClick={() => setMeasure(m)}
            className={`rounded px-2 py-1 ${m === measure ? "bg-accent text-accent-fg" : "text-muted hover:text-fg"}`}>{MEASURES[m]}</button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 44 }} barSize={22}>
          <XAxis type="number" domain={[0, 1]} hide />
          <YAxis type="category" dataKey="name" {...AXIS} axisLine={false} width={92} />
          <Tooltip content={<ChartTooltip format={(v) => v.toFixed(3)} />} cursor={false} />
          <Bar dataKey="value" name={MEASURES[measure]} radius={[0, 4, 4, 0]} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.key} fill={d.key === "afed" ? SERIES.accent : SERIES.three} />)}
            <LabelList dataKey="value" position="right" formatter={(v: unknown) => Number(v).toFixed(2)} style={{ fill: "rgb(var(--fg))", fontSize: 12 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function RecallByType({ metrics, labels }: { metrics: Metrics; labels: Record<string, string> }) {
  const afed = metrics.variants.afed.recall_by_type;
  const base = metrics.variants.global_if.recall_by_type;
  const data = Object.keys(afed).sort((a, b) => afed[a] - afed[b]).map((k) => ({ name: humanise(k), afed: afed[k], global: base[k] }));
  return (
    <ChartCard title="Recall by anomaly type" subtitle="Same review budget, weakest first"
      hint="Which kinds of problem are caught, and which are missed. Short bars are blind spots."
      table={<SimpleTable head={["Type", ...Object.values(labels)]} rows={Object.keys(afed).map((t) => [humanise(t), ...Object.keys(labels).map((k) => metrics.variants[k].recall_by_type[t].toFixed(2))])} />}>
      <Legend items={[{ label: labels.afed, color: SERIES.accent, dot: true }, { label: labels.global_if, color: SERIES.three, dot: true }]} />
      <ResponsiveContainer width="100%" height={380}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 12 }} barSize={10} barGap={2}>
          <CartesianGrid stroke="rgb(var(--line))" horizontal={false} />
          <XAxis type="number" domain={[0, 1]} {...AXIS} tickFormatter={(v) => percent(v)} />
          <YAxis type="category" dataKey="name" {...AXIS} axisLine={false} width={124} interval={0} />
          <Tooltip content={<ChartTooltip format={(v) => percent(v)} />} cursor={false} />
          <Bar dataKey="afed" name={labels.afed} fill={SERIES.accent} radius={[0, 4, 4, 0]} isAnimationActive={false} />
          <Bar dataKey="global" name={labels.global_if} fill={SERIES.three} radius={[0, 4, 4, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/** Each model at its own alert threshold; AFED's row is highlighted. */
function Comparison({ models, labels }: { models: Record<string, Compared>; labels: Record<string, string> }) {
  const cols: [Exclude<keyof Compared, "confusion">, string, (v: number) => string][] = [
    ["accuracy", "Accuracy", (v) => v.toFixed(3)], ["balanced_accuracy", "Balanced acc.", (v) => v.toFixed(3)], ["precision", "Precision", (v) => v.toFixed(3)], ["recall", "Recall", (v) => v.toFixed(3)],
    ["f1", "F1-score", (v) => v.toFixed(3)], ["roc_auc", "ROC-AUC", (v) => v.toFixed(3)], ["pr_auc", "PR-AUC", (v) => v.toFixed(3)],
    ["false_positive_rate", "FPR", (v) => percent(v, 1)], ["false_negative_rate", "FNR", (v) => percent(v, 1)], ["alerts", "Alerts", count],
  ];
  const c = models.afed?.confusion;
  const allNormal = c ? (c.fp + c.tn) / (c.tp + c.fp + c.fn + c.tn) : null;
  return (
    <Card title="Model comparison" subtitle="Every model alerts at its own threshold, on the same labelled events"
      hint={<>Recall is the share of real anomalies a model catches; precision is the share of its alerts that are real; F1 balances the two.
        Balanced accuracy is fair when problems are rare, because flagging nothing scores 50%. Plain accuracy is not{allNormal == null ? "." : <>: here, flagging nothing scores {percent(allNormal, 1)}.</>}</>}>
      <div className="-mx-5 overflow-x-auto">
        <table className="w-full min-w-[960px]">
          <thead><tr className="border-b border-line"><th className="table-head pl-5">Model</th>{cols.map(([, h]) => <th key={h} className="table-head text-right">{h}</th>)}</tr></thead>
          <tbody>
            {Object.keys(labels).filter((k) => models[k]).map((k) => (
              <tr key={k} className={`border-b border-line/60 last:border-0 ${k === "afed" ? "bg-accent/10 font-semibold" : ""}`}>
                <td className={`table-cell pl-5 ${k === "afed" ? "border-l-4 border-accent" : "border-l-4 border-transparent"}`}>{labels[k]}</td>
                {cols.map(([key, h, fmt]) => <td key={h} className="table-cell text-right tabular-nums">{models[k][key] == null ? "n/a" : fmt(models[k][key] as number)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const DATASET_NAMES: Record<string, string> = {
  afed_synthetic: "AFED synthetic", afed_temporal: "AFED temporal", nspcl: "NSPCL, India", mplads: "MPLADS, India",
  chicago: "Chicago, USA", delaware: "Delaware, USA",
};
const BENCH_MEASURES: Record<BenchMeasure, string> = {
  f1: "F1-score", balanced_accuracy: "Balanced accuracy", recall: "Recall", precision: "Precision", roc_auc: "ROC-AUC", pr_auc: "PR-AUC", accuracy: "Accuracy",
};
const SHORT_MODELS: Record<string, string> = { rule_based: "Rule-based", global_if: "Global IF", lof: "LOF", afed: "AFED" };

/** The same four models on every dataset, from experiments/model_comparison.py. The best value per row is bold, AFED or not. */
function AcrossDatasets({ bench }: { bench: Benchmarks }) {
  const [measure, setMeasure] = useState<BenchMeasure>("f1");
  const models = Object.keys(bench.models);
  return (
    <Card title="The same comparison across datasets" subtitle={`Mean of ${bench.datasets[0]?.seeds ?? 3} seeds per dataset, from the comparison experiment`}
      hint={<>The synthetic sets carry their own labels, and AFED's rules were written for their anomaly types, so they are AFED's best case.
        The real sets are genuine payment ledgers with anomalies planted by a seeded script. Their unplanted rows count as normal, so precision
        there is a lower bound. The best model on each row is in bold, including where it is not AFED.</>}>
      <div role="group" aria-label="Measure" className="mb-3 flex flex-wrap gap-1 text-xs">
        {(Object.keys(BENCH_MEASURES) as BenchMeasure[]).map((m) => (
          <button key={m} type="button" aria-pressed={m === measure} onClick={() => setMeasure(m)}
            className={`rounded px-2 py-1 ${m === measure ? "bg-accent text-accent-fg" : "text-muted hover:text-fg"}`}>{BENCH_MEASURES[m]}</button>
        ))}
      </div>
      <div className="-mx-5 overflow-x-auto">
        <table className="w-full min-w-[720px]">
          <thead><tr className="border-b border-line">
            <th className="table-head pl-5">Dataset</th><th className="table-head">Data</th><th className="table-head text-right">Events</th>
            {models.map((m) => <th key={m} className={`table-head text-right ${m === "afed" ? "bg-accent/10" : ""}`}>{SHORT_MODELS[m] ?? m}</th>)}
          </tr></thead>
          <tbody>
            {bench.datasets.map((d) => {
              const best = Math.max(...models.map((m) => d.results[m][measure]));
              return (
                <tr key={d.name} className="border-b border-line/60 last:border-0">
                  <td className="table-cell pl-5 font-medium">{DATASET_NAMES[d.name] ?? d.name}</td>
                  <td className="table-cell text-muted">{d.real ? "Real, planted anomalies" : "Synthetic, labelled"}</td>
                  <td className="table-cell text-right tabular-nums text-muted">{count(d.events)}</td>
                  {models.map((m) => {
                    const value = d.results[m][measure];
                    return <td key={m} className={`table-cell text-right tabular-nums ${m === "afed" ? "bg-accent/10" : ""} ${value === best ? "font-semibold" : "text-muted"}`}>{value.toFixed(3)}</td>;
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/** The confusion matrix and the operational measures for AFED fusion, at its own alert count. */
function OperationalCard({ metrics }: { metrics: Metrics }) {
  const v = metrics.variants.afed;
  if (!v.confusion || !metrics.amount_at_risk || !metrics.investigation || !metrics.score_distribution) return null;  // runs from before these were measured
  const { tp, fp, fn, tn } = v.confusion;
  const allNormal = (fp + tn) / (tp + fp + fn + tn);
  const money = metrics.amount_at_risk;
  const inv = metrics.investigation;
  const dist = metrics.score_distribution;
  const label = (i: number) => `${dist.bins[i].toFixed(2)}${i + 1 < dist.bins.length ? `–${dist.bins[i + 1].toFixed(2)}` : "+"}`;
  return (
    <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2">
      <Card title="Confusion matrix and rates" subtitle="AFED fusion, alerted (Medium and above) against labelled anomalies"
        hint="Alerted and anomalous: caught. Alerted but normal: a false alarm a reviewer dismisses. Not alerted but anomalous: missed. The rates below are built from these four counts.">
        <SimpleTable head={["", "Labelled anomaly", "Labelled normal"]} rows={[["Alerted", count(tp), count(fp)], ["Not alerted", count(fn), count(tn)]]} />
        <div className="mt-4">
          <SimpleTable head={["Measure", "Value"]} rows={[
            ["Precision", v.precision.toFixed(3)], ["Recall (anomaly detection rate)", v.recall.toFixed(3)], ["F1-score", (v.f1 ?? 0).toFixed(3)],
            ["False positive rate", percent(v.false_alarm_rate, 2)], ["False negative rate", percent(v.false_negative_rate, 2)],
            ["ROC-AUC", v.roc_auc.toFixed(3)], ["PR-AUC (average precision)", v.average_precision.toFixed(3)],
            ["Accuracy", `${percent(v.accuracy, 1)} (calling everything normal scores ${percent(allNormal, 1)})`],
            ["Balanced accuracy", v.balanced_accuracy == null ? "n/a" : `${percent(v.balanced_accuracy, 1)} (calling everything normal scores 50%)`],
            ["Fraud detection rate", "Not measurable: no data has confirmed-fraud labels"],
          ]} />
        </div>
      </Card>
      <div className="min-w-0 space-y-5">
        <Card title="Money and workload" hint="What the alerts mean in rupees and in reviewer time, compared with checking everything or using a global Isolation Forest.">
          <SimpleTable head={["Measure", "Value"]} rows={[
            ["Amount on alerted invoices", inr(money.alerted)],
            ["Anomalous amount caught", `${inr(money.anomalous_caught)} of ${inr(money.anomalous_total)}`],
            ["Anomalous amount missed", inr(money.anomalous_missed)],
            ["Events to review", `${count(inv.reviewed)} of ${count(inv.events)} (${percent(inv.reduction_vs_all, 1)} fewer)`],
            ["Global IF reviews for the same recall", inv.baseline_reviews_for_same_recall == null ? "Never reaches it"
              : `${count(inv.baseline_reviews_for_same_recall)} (${percent(inv.reduction_vs_baseline, 1)} fewer with AFED)`],
            ["Processing time", metrics.processing_seconds == null ? "n/a" : `${metrics.processing_seconds.toFixed(1)} s, ${metrics.ms_per_event?.toFixed(2)} ms per event`],
          ]} />
        </Card>
        <Card title="Risk score distribution" subtitle="How many labelled events fall in each risk band"
          hint="A good detector keeps normal events in the low bands and anomalies in the high ones. Where the two columns overlap, mistakes happen.">
          <SimpleTable head={["Risk band", "Normal", "Anomalous"]} rows={dist.bins.map((_, i) => [label(i), count(dist.normal[i]), count(dist.anomalous[i])])} />
        </Card>
      </div>
    </div>
  );
}

function Feedback({ feedback }: { feedback: Data["feedback"] }) {
  const { totals, trend, seeded } = feedback;
  const decided = totals.Confirmed + totals.Dismissed;
  if (!decided && !totals.Escalated) return <Card title="Reviewer feedback"><Empty title="No reviews yet">Confirm or dismiss alerts and the analytics appear here.</Empty></Card>;
  const shares = trend.filter((t) => t.false_alarm_share != null);
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Confirmed" value={count(totals.Confirmed)} />
        <Stat label="Dismissed" value={count(totals.Dismissed)} />
        <Stat label="Escalated" value={count(totals.Escalated)} />
        <Stat label="Dismissed share" value={percent(decided ? totals.Dismissed / decided : null)} note="Of confirmed and dismissed" />
      </div>
      {seeded > 0 && <p className="text-sm text-muted">{seeded} of these reviews are simulated seed data, decided from the synthetic labels. They are not real reviewer judgements, and recalibration ignores them.</p>}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <ChartCard title="Confirmed and dismissed per week" hint="How reviewers judged the alerts each week. Dismissals are false alarms that reached a person."
          table={<SimpleTable head={["Week", "Confirmed", "Dismissed", "Escalated"]} rows={trend.map((t) => [t.week, t.Confirmed, t.Dismissed, t.Escalated])} />}>
          <Legend items={[{ label: "Confirmed", color: SERIES.accent, dot: true }, { label: "Dismissed", color: SERIES.three, dot: true }]} />
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={trend} margin={{ left: -18, right: 8, top: 6 }} maxBarSize={24}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="week" {...AXIS} minTickGap={30} />
              <YAxis {...AXIS} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} cursor={false} />
              <Bar dataKey="Confirmed" stackId="a" fill={SERIES.accent} stroke="rgb(var(--surface))" strokeWidth={2} isAnimationActive={false} />
              <Bar dataKey="Dismissed" stackId="a" fill={SERIES.three} stroke="rgb(var(--surface))" strokeWidth={2} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="False-alarm trend" subtitle="Share of decided alerts that were dismissed, per week"
          hint="A falling line means recalibration is sending reviewers fewer false alarms."
          table={<SimpleTable head={["Week", "Dismissed share"]} rows={shares.map((t) => [t.week, percent(t.false_alarm_share)])} />}>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={shares} margin={{ left: -14, right: 12, top: 8 }}>
              <CartesianGrid {...GRID} />
              <XAxis dataKey="week" {...AXIS} minTickGap={30} />
              <YAxis {...AXIS} domain={[0, 1]} tickFormatter={(v) => percent(v)} />
              <Tooltip content={<ChartTooltip format={(v) => percent(v)} />} cursor={{ stroke: "rgb(var(--muted))" }} />
              <Line dataKey="false_alarm_share" name="Dismissed share" stroke={SERIES.accent} strokeWidth={2} dot={{ r: 4, fill: SERIES.accent, stroke: "rgb(var(--surface))", strokeWidth: 2 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </>
  );
}

export default function Evaluation() {
  const state = useApi<Data>("/evaluation");
  return (
    <>
      <PageHeader title="Evaluation" subtitle="What the latest labelled run measured, and how reviewers have responded." />
      <Async state={state} rows={5}>
        {({ metrics, model_version, variant_labels: labels, comparison_labels, benchmarks, feedback }) => (
          <div className="space-y-5">
            {metrics ? (
              <>
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                  <Stat label="Detection rate" value={percent(metrics.detection_rate)} note={`Global IF: ${percent(metrics.baseline_detection_rate)}`} />
                  <Stat label="False-alarm reduction" value={percent(metrics.false_alarm_reduction)} note="Against global IF, same budget" />
                  <Stat label="Anomalies" value={count(metrics.anomalies)} note={`In ${count(metrics.labelled_events)} labelled events`} />
                  <Stat label="Review budget" value={count(metrics.review_budget)} note={`Model ${model_version}`} />
                </div>
                <p className="text-sm text-muted">
                  Measured on the labelled events loaded here. The bundled demo data is synthetic, and the rules target the same anomaly types it injects, so expect lower figures on real data.
                  {!!metrics.recalibrated_on_reviews && ` Weights were recalibrated on ${metrics.recalibrated_on_reviews} reviewer decisions about this same data, so these figures are not an independent test.`}
                </p>
                {metrics.comparison && <Comparison models={metrics.comparison} labels={comparison_labels} />}
                {benchmarks && benchmarks.datasets.length > 0 && <AcrossDatasets bench={benchmarks} />}
                <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2">
                  <div className="min-w-0 space-y-5">
                    <Ablation metrics={metrics} labels={labels} />
                    <Card title="Precision at k" subtitle="Share of true anomalies in the top k events"
                      hint="If a reviewer opens only the first k events on the list, this is the share that turn out to be real problems.">
                      <SimpleTable head={["Variant", ...Object.keys(metrics.variants.afed.precision_at_k).map((k) => `P@${k}`)]}
                        rows={Object.keys(labels).map((v) => [labels[v], ...Object.keys(metrics.variants.afed.precision_at_k).map((k) => metrics.variants[v].precision_at_k[k].toFixed(2))])} />
                    </Card>
                  </div>
                  <RecallByType metrics={metrics} labels={labels} />
                </div>
                <OperationalCard metrics={metrics} />
              </>
            ) : <Card><Empty title="No evaluation yet">Metrics need a run on data with an is_anomaly column. Unlabelled data produces no accuracy numbers.</Empty></Card>}
            <Feedback feedback={feedback} />
          </div>
        )}
      </Async>
    </>
  );
}
