import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Async, Button, Card, ErrorState, Field, Loading, PageHeader, SimpleTable } from "../components/ui";
import { api, toError, useApi } from "../lib/api";
import { percent } from "../lib/format";

interface Values {
  approval_limit: number; weights: { w1: number; w2: number; w3: number }; thresholds: { medium: number; high: number; critical: number };
  contamination: string | number; lstm: { window: number; mode: string; epochs: number }; rules: Record<string, boolean>; qwen_provider: string;
}
interface Loaded extends Values { rule_info: { name: string; label: string; severity: number }[] }
interface Model { version: string; has_lstm: boolean; recall: number | null; precision: number | null; roc_auc: number | null }
interface Recalibration {
  ok: boolean; reviews: number; message?: string; f1_before?: number; f1_after?: number;
  fit_reviews?: number; check_reviews?: number; heldout_before?: number; heldout_after?: number; weights?: Values["weights"]; thresholds?: Values["thresholds"];
  simulated_excluded: number;
}

const number = { valueAsNumber: true, required: true };

function Form({ data, reload }: { data: Loaded; reload: () => void }) {
  const { rule_info: rules, ...values } = data;
  const { register, handleSubmit, reset, setValue, formState: { isSubmitting } } = useForm<Values>({ defaultValues: values });
  const [saved, setSaved] = useState("");
  const [error, setError] = useState("");
  const [calibration, setCalibration] = useState<Recalibration | null>(null);
  useEffect(() => { reset(values); }, [data]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = handleSubmit(async (form) => {
    setError(""); setSaved("");
    try {
      await api.put("/settings", form);
      setSaved("Saved. These apply to the next run.");
      reload();
    } catch (e) {
      setError(toError(e).message);
    }
  }, () => { setSaved(""); setError("Every field needs a value."); });

  const recalibrate = async () => {
    setError("");
    try {
      const { data: result } = await api.post<Recalibration>("/settings/recalibrate");
      setCalibration(result);
      if (result.ok) {  // only these two changed: other unsaved edits in the form stay as they are
        setValue("weights", result.weights!);
        setValue("thresholds", result.thresholds!);
      }
    } catch (e) {
      setError(toError(e).message);
    }
  };

  return (
    <form onSubmit={save} className="space-y-5">
      <div className="grid gap-5 lg:grid-cols-2">
        <Card title="Risk fusion" subtitle="Risk = w1·A + w2·D + w3·F + 0.10·min(D, F). Weights must add up to 1.">
          <div className="grid grid-cols-3 gap-3">
            <Field label="w1 Isolation Forest"><input className="input" type="number" step="0.01" min="0" max="1" {...register("weights.w1", number)} /></Field>
            <Field label="w2 Deviation"><input className="input" type="number" step="0.01" min="0" max="1" {...register("weights.w2", number)} /></Field>
            <Field label="w3 Rules"><input className="input" type="number" step="0.01" min="0" max="1" {...register("weights.w3", number)} /></Field>
            <Field label="Medium from"><input className="input" type="number" step="0.005" min="0" max="1" {...register("thresholds.medium", number)} /></Field>
            <Field label="High from"><input className="input" type="number" step="0.005" min="0" max="1" {...register("thresholds.high", number)} /></Field>
            <Field label="Critical from"><input className="input" type="number" step="0.005" min="0" max="1" {...register("thresholds.critical", number)} /></Field>
          </div>
        </Card>
        <Card title="Models">
          <div className="grid grid-cols-2 gap-3">
            <Field label="LSTM window"><input className="input" type="number" min="2" max="50" {...register("lstm.window", number)} /></Field>
            <Field label="LSTM mode">
              <select className="input" {...register("lstm.mode")}><option value="forecast">Forecast</option><option value="autoencoder">Autoencoder</option></select>
            </Field>
            <Field label="LSTM epochs"><input className="input" type="number" min="1" max="100" {...register("lstm.epochs", number)} /></Field>
            <Field label="Contamination" hint='"auto" or a share such as 0.03. Sets the forest&apos;s own cut-off only: risk uses its ranking, so scores and alerts do not change.'><input className="input" {...register("contamination", { required: true })} /></Field>
            <Field label="Approval limit (Rs.)"><input className="input" type="number" min="1" {...register("approval_limit", number)} /></Field>
            <Field label="Qwen provider">
              <select className="input" {...register("qwen_provider")}>
                <option value="template">Template (no model)</option><option value="hf_api">Hugging Face API</option><option value="ollama">Ollama</option><option value="local">Local transformers</option>
              </select>
            </Field>
          </div>
        </Card>
      </div>
      <Card title="Red-flag rules" subtitle="Severity feeds the noisy-OR rule score.">
        <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {rules.map((r) => (
            <label key={r.name} className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2"><input type="checkbox" {...register(`rules.${r.name}`)} />{r.label}</span>
              <span className="text-xs tabular-nums text-muted">{r.severity.toFixed(2)}</span>
            </label>
          ))}
        </div>
      </Card>
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={isSubmitting}>Save settings</Button>
        {saved && <span role="status" className="text-sm text-muted">{saved}</span>}
        {error && <span role="alert" className="notice-error">{error}</span>}
      </div>
      <Card title="Recalibrate from feedback" subtitle="Searches weights and the Medium cut-off for the best F1 on the older 70% of real reviewer decisions, then checks the result on the newest 30% and keeps it only if it does at least as well there. Needs 20 decisions, with both outcomes. Simulated seed reviews do not count.">
        <Button variant="secondary" onClick={recalibrate}>Recalibrate</Button>
        {calibration && (calibration.ok ? (
          <p role="status" className="mt-3 text-sm">
            On the {calibration.check_reviews} newest reviews, which the search did not see, F1 went from {calibration.heldout_before?.toFixed(3)} to {calibration.heldout_after?.toFixed(3)}
            (on the {calibration.fit_reviews} it was fitted to: {calibration.f1_before?.toFixed(3)} to {calibration.f1_after?.toFixed(3)}).
            Weights {calibration.weights?.w1}, {calibration.weights?.w2}, {calibration.weights?.w3}; Medium from {calibration.thresholds?.medium}. Saved for the next run.
          </p>
        ) : <p role="status" className="mt-3 text-sm text-muted">
          {calibration.message} Found {calibration.reviews}.{calibration.simulated_excluded > 0 && ` ${calibration.simulated_excluded} simulated reviews were left out, because they are copies of the labels the evaluation is measured on.`}
        </p>)}
      </Card>
    </form>
  );
}

export default function Settings() {
  const state = useApi<Loaded>("/settings");
  const models = useApi<Model[]>("/settings/models");
  return (
    <>
      <PageHeader title="Model settings" subtitle="Changes apply on the next run." />
      <div className="space-y-5">
        <Async state={state} rows={3}>{(data) => <Form data={data} reload={state.reload} />}</Async>
        <Card title="Model versions" subtitle="Saved in models_store, one folder per run">
          {models.error ? <ErrorState error={models.error} retry={models.reload} /> : !models.data ? <Loading rows={2} /> : (
            <div className="overflow-x-auto">
              <SimpleTable head={["Version", "LSTM", "ROC-AUC", "Recall", "Precision"]} rows={models.data.map((m) => [
                m.version, m.has_lstm ? "Yes" : "Skipped", m.roc_auc?.toFixed(3) ?? "No labels", percent(m.recall), percent(m.precision)])} />
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
