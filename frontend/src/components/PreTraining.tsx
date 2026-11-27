import { useCallback, useEffect, useState } from "react";
import { FlaskConical, Download } from "lucide-react";
import type { Project } from "../types/project";
import { smokeActive, type ModelConfig, type SmokeRun, type TrainingMetric, type TrainingRuntime as Runtime, type PilotPreview, type TrainingKind } from "../types/training";
import { checkpointDownload, deleteSmoke, listModelConfigs, listSmokeRuns, smokeAction, smokeDownload, smokeMetrics, startSmoke, pilotPreview } from "../services/training";
import { TrainingRuntime } from "./TrainingRuntime";
import { GeneratedText } from "./GeneratedText";

export function PreTraining({ project, onSetup, onConfig }: { project: Project | null; onSetup: () => void; onConfig: () => void }) {
  if (!project?.revision) return <section className="empty-card"><FlaskConical size={36}/><h2>Save a project first.</h2><button className="primary" onClick={onSetup}>Project setup</button></section>;
  return <TrainingWorkspace key={project.id} projectId={project.id} onConfig={onConfig}/>;
}

function TrainingWorkspace({ projectId, onConfig }: { projectId: string; onConfig: () => void }) {
  const [configs, setConfigs] = useState<ModelConfig[]>([]);
  const [runs, setRuns] = useState<SmokeRun[]>([]);
  const [mode, setMode] = useState<TrainingKind>("smoke");
  const [preview, setPreview] = useState<PilotPreview | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [initialCheckpointId, setInitialCheckpointId] = useState("");
  const [configId, setConfigId] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const selected = runs.find((r) => r.id === selectedId) ?? runs[0];
  const modeConfigs = configs.filter((c) => (c.trainingKind ?? "smoke") === mode);
  const config = modeConfigs.find((c) => c.id === configId) ?? modeConfigs[0];
  const parentChoices = config && mode === "pilot" ? runs.filter((run) =>
    run.status === "completed" && run.configuration.vocabSize === config.configuration.vocabSize &&
    run.configuration.contextLength === config.configuration.contextLength && run.configuration.layers === config.configuration.layers &&
    run.configuration.hiddenSize === config.configuration.hiddenSize && run.configuration.heads === config.configuration.heads &&
    configs.find((parentConfig) => parentConfig.id === run.modelConfigId)?.source.tokenizerRunId === config.source.tokenizerRunId,
  ).flatMap((run) => run.checkpoints.map((checkpoint) => ({ run, checkpoint }))) : [];
  const initialCheckpoint = parentChoices.find(({ checkpoint }) => checkpoint.id === initialCheckpointId)?.checkpoint;
  const active = runs.some(smokeActive);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const [nextConfigs, nextRuns, pilots] = await Promise.all([listModelConfigs(projectId, signal), listSmokeRuns(projectId, signal), listSmokeRuns(projectId, signal, "pilot")]);
    if (signal?.aborted) return;
    setConfigs(nextConfigs); setRuns([...nextRuns, ...pilots].sort((a, b) => b.createdAt.localeCompare(a.createdAt)));
  }, [projectId]);
  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal).catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not load training runs."); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { await refresh(controller.signal); } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Polling failed; retrying."); }
      if (!controller.signal.aborted) timer = setTimeout(() => void poll(), 1500);
    }
    timer = setTimeout(() => void poll(), 1500);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [active, refresh]);
  useEffect(() => {
    setPreview(null); setPreviewError("");
    if (mode !== "pilot" || !config) return;
    const controller = new AbortController();
    void pilotPreview(projectId, config.id, controller.signal).then((p) => { if (!controller.signal.aborted) setPreview(p); }).catch((e: unknown) => { if (!controller.signal.aborted) setPreviewError(e instanceof Error ? e.message : "Preview failed."); });
    return () => controller.abort();
  }, [projectId, config?.id, mode]);
  async function command(action: "start" | "cancel" | "retry" | "resume" | "delete", checkpointId?: string) {
    if (action === "delete" && !window.confirm("Delete this run and all its checkpoints? Runs used for resume are protected.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (action === "start" && config) { const next = await startSmoke(projectId, config.id, mode, initialCheckpoint?.id); setSelectedId(next.id); setNotice(`${mode === "pilot" ? "Whole-dataset pilot" : "Smoke-test"} run queued with fixed source and configuration.`); }
      else if (selected && action === "delete") { const result = await deleteSmoke(projectId, selected.id, selected.trainingKind ?? "smoke"); setNotice(result.cleanupWarning ?? "Run deleted."); }
      else if (selected && (action === "cancel" || action === "retry" || action === "resume")) { const next = await smokeAction(projectId, selected.id, action, checkpointId, selected.trainingKind ?? "smoke"); if (action !== "cancel") setSelectedId(next.id); setNotice(action === "cancel" ? "Cancellation requested." : "New run queued. Original artifacts are preserved."); }
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Training action failed."); }
    finally { setBusy(false); }
  }
  const deviceReady = runtime?.ready && (config?.configuration.device === "cpu" || (config?.configuration.device === "cuda" ? runtime.cuda : !runtime.cudaError));
  return <div className="training-page">
    {error && <div className="error-banner" role="alert">{error}</div>}{notice && <p className="notice" role="status">{notice}</p>}
    <TrainingRuntime projectId={projectId} onReport={setRuntime}/>
    <section className="card training-form"><span className="eyebrow">BOUNDED PRE-TRAINING</span><h2>{mode === "pilot" ? "Train on every selected training block." : "Run a small, measurable training check."}</h2><label>Run mode<select aria-label="Run mode" value={mode} disabled={busy} onChange={(e) => { setMode(e.target.value as TrainingKind); setConfigId(""); }}><option value="smoke">Smoke test</option><option value="pilot">Whole-dataset pilot</option></select></label><p>{mode === "pilot" ? "Visit all blocks each epoch and measure coverage. Independent evaluation is separate." : "Train on up to two training blocks to check numerical stability and checkpoints."}</p>
      <label>Saved model configuration<select aria-label="Saved model configuration" disabled={busy || loading} value={config?.id ?? ""} onChange={(e) => setConfigId(e.target.value)}><option value="">Choose a saved configuration</option>{modeConfigs.map((c) => <option key={c.id} value={c.id}>{c.name} · revision {c.revision} · {c.configuration.maxSteps} steps</option>)}</select></label>
      {mode === "pilot" && <label>Initialize weights<select value={initialCheckpoint?.id ?? ""} disabled={busy} onChange={(e) => setInitialCheckpointId(e.target.value)}>
        <option value="">{config?.configuration.objective === "sft" ? "Choose a parent checkpoint" : "Random weights"}</option>
        {parentChoices.map(({ run, checkpoint }) =>
          <option key={checkpoint.id} value={checkpoint.id}>{run.trainingKind === "pilot" ? "Pilot" : "Smoke"} · step {checkpoint.step} · {new Date(run.createdAt).toLocaleString()}</option>)}
      </select></label>}
      {config && <p className="dataset-caption">{config.source.datasetName} v{config.source.datasetVersion} · {config.configuration.vocabSize.toLocaleString()} vocabulary · {config.configuration.contextLength} context · {config.configuration.device} / FP32 · {config.configuration.timeLimitSeconds}s time limit</p>}
      {mode === "pilot" && (preview?.modelConfigId === config?.id && preview ? <div className="info-note pilot-preview" aria-label="Pilot execution plan"><p>{preview.trainingBlocks} training blocks · {preview.trainingDocuments} documents · {preview.epochs} epochs · {preview.totalSteps} updates</p><p>{preview.targetTokensPerEpoch.toLocaleString()} supervised targets per epoch · checkpoints at steps {preview.checkpointSteps.join(", ")}</p><p>Estimated artifacts: {(preview.estimatedStorageBytes/1024**2).toFixed(1)} MiB · {config.configuration.device.toUpperCase()} / FP32 · {preview.timeLimitSeconds}s limit</p>{preview.warnings.map((w) => <p key={w}>{w}</p>)}</div> : <p role={previewError ? "alert" : "status"}>{previewError || (config ? "Validating complete pilot plan…" : "Save a pilot configuration in Model Config first.")}</p>)}
      <div className="training-actions"><button className="primary" disabled={busy || loading || !config || !deviceReady || (mode === "pilot" && preview?.modelConfigId !== config.id) || (config.configuration.objective === "sft" && !initialCheckpoint)} onClick={() => void command("start")}>{mode === "pilot" ? "Start pilot" : "Run smoke test"}</button><button className="secondary" onClick={onConfig}>Model configuration</button><button className="text-button" disabled={busy || loading} onClick={() => { void refresh().catch((e: unknown) => setError(e instanceof Error ? e.message : "Refresh failed.")); }}>Refresh runs</button></div>
      {!runtime && <p className="dataset-caption">Check the training runtime above before starting.</p>}
    </section>
    {loading ? <p role="status">Loading training history…</p> : !runs.length ? <section className="empty-card"><FlaskConical size={36}/><h2>No training runs yet.</h2><p>Save a configuration, check the executor and start a bounded run.</p></section> : <>
      <div className="tokenizer-run-list">{runs.map((r) => <button className={`card tokenizer-run-choice ${selected?.id === r.id ? "selected" : ""}`} aria-pressed={selected?.id === r.id} key={r.id} onClick={() => setSelectedId(r.id)}><strong>{r.trainingKind === "pilot" ? (r.configuration.objective === "sft" ? "SFT pilot" : r.initialCheckpointId ? "Mid-training pilot" : r.parentRunId ? "Resumed pilot" : "Whole-dataset pilot") : (r.parentRunId ? "Resume verification" : "Smoke test")} · {r.status}</strong><span>{r.verdict ?? `${r.metrics.step ?? 0} / ${r.configuration.maxSteps} steps`}</span><small>{new Date(r.createdAt).toLocaleString()}</small></button>)}</div>
      {selected && <RunDetails key={selected.id} projectId={projectId} run={selected} busy={busy} onAction={(a, cp) => void command(a, cp)}/>}
    </>}
  </div>;
}

function RunDetails({ projectId, run, busy, onAction }: { projectId: string; run: SmokeRun; busy: boolean; onAction: (action: "cancel" | "retry" | "resume" | "delete", checkpoint?: string) => void }) {
  const [events, setEvents] = useState<TrainingMetric[]>([]);
  const [error, setError] = useState("");
  const [checkpointId, setCheckpointId] = useState("");
  const active = smokeActive(run);
  const pilot = run.trainingKind === "pilot";
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try { const next = await smokeMetrics(projectId, run.id, -1, controller.signal, run.trainingKind ?? "smoke"); if (!controller.signal.aborted) { setEvents(next.events); setError(""); } }
      catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Metrics unavailable."); }
      if (active && !controller.signal.aborted) timer = setTimeout(() => void refresh(), 1500);
    }
    void refresh(); return () => { controller.abort(); clearTimeout(timer); };
  }, [projectId, run.id, active]);
  const m = run.metrics;
  const report = run.manifest?.report;
  const intermediate = run.checkpoints.filter((c) => c.step < run.configuration.maxSteps);
  const checkpoint = intermediate.find((c) => c.id === checkpointId) ?? intermediate[0];
  return <section className="card smoke-details"><div className="card-heading"><div><span className="pill">{run.status}{run.verdict ? ` · ${run.verdict}` : ""}</span><h2>{pilot ? "Whole-dataset pilot" : (run.parentRunId ? "Resume verification" : "Training diagnostic")}</h2><p>{run.elapsedSeconds.toFixed(1)}s elapsed · {run.runtime.device} · FP32</p></div><div className="training-actions">{active ? <button className="secondary" disabled={busy || run.cancelRequested} onClick={() => onAction("cancel")}>{run.cancelRequested ? "Cancelling…" : "Cancel run"}</button> : <><button className="secondary" disabled={busy} onClick={() => onAction("retry")}>Retry from scratch</button><button className="text-button" disabled={busy} onClick={() => onAction("delete")}>Delete run</button></>}</div></div>
    {run.error && <p className="error-banner" role="alert">{run.error}</p>}
    {active && <p role="status">{run.status === "training" ? (pilot ? "Training on all selected training blocks." : "Training on the fixed diagnostic subset.") : `Stage: ${run.status}.`}</p>}
    <progress aria-label="Optimizer step progress" max={run.configuration.maxSteps} value={m.step ?? 0}/>
    <div className="dataset-stats"><div><strong>{m.step ?? 0} / {run.configuration.maxSteps}</strong><span>Optimizer steps</span></div><div><strong>{m.loss?.toFixed(4) ?? "—"}</strong><span>Latest training loss</span></div><div><strong>{m.targetTokensPerSecond?.toFixed(0) ?? "—"}</strong><span>Supervised target tokens / second</span></div></div>
    {pilot && <div className="dataset-stats"><div><strong>{m.completedEpochs ?? 0} / {run.configuration.epochs}</strong><span>Completed epochs · offset {m.epochOffset ?? 0} / {run.configuration.trainingBlocks}</span></div><div><strong>{m.uniqueBlocksVisited ?? 0} / {run.configuration.trainingBlocks}</strong><span>Unique blocks visited across run lineage</span></div><div><strong>{(m.targetExposures ?? 0).toLocaleString()}</strong><span>Cumulative supervised target exposures</span></div></div>}
    <p className="dataset-caption">Step time: {m.stepSeconds?.toFixed(3) ?? "—"}s · CPU RSS: {m.rssBytes ? (m.rssBytes/1024**2).toFixed(0)+" MiB" : "—"} · CUDA peak allocated / reserved: {m.cudaPeakAllocatedBytes != null ? `${(m.cudaPeakAllocatedBytes/1024**2).toFixed(0)} / ${(m.cudaPeakReservedBytes!/1024**2).toFixed(0)} MiB` : "not applicable"}</p>
    {error && <p role="alert">{error}</p>}{events.length > 0 && <LossChart events={events}/>}
    {report && <><div className="dataset-stats"><div><strong>{report.initialLoss.toFixed(4)} → {report.finalLoss.toFixed(4)}</strong><span>{pilot ? "All-train eval loss" : "Same-subset eval loss"} · {(report.lossDecreaseRatio*100).toFixed(1)}% decrease</span></div><div><strong>{report.parameters.toLocaleString()}</strong><span>Measured parameters</span></div><div><strong>{report.reloadMatches ? "Matched" : "Failed"}</strong><span>Fresh-process checkpoint reload</span></div></div>
      {report.startingStep > 0 && <p>Resumed from optimizer step {report.startingStep}; starting loss {report.startLoss.toFixed(4)}. Decrease is measured against the original run’s initial loss.</p>}
      <p>{report.finiteGradients && report.weightsChanged ? "Finite gradients and changed model weights verified." : "Inspect technical checks."}{!pilot && " A pass requires at least 5% lower fixed-subset loss."}</p>
      {pilot && <div className="training-actions"><a className="secondary" href="/#/evaluation">Open Evaluation</a><a className="secondary" href="/#/playground">Open Playground</a><a className="secondary" href={smokeDownload(projectId, run.id, "coverage", "pilot")}>Coverage report</a></div>}
      {report.warnings.map((w) => <p className="info-note" key={w}>{w}</p>)}
      <div className="training-actions">{[["bundle","Complete training bundle"],["report","Diagnostic report"],["metrics","Metrics JSONL"],["manifest","Manifest"]].map(([key, label]) => <a className="secondary" key={key} href={smokeDownload(projectId, run.id, key, run.trainingKind ?? "smoke")}><Download size={14}/>{label}</a>)}</div>
      <details className="training-sample"><summary>Generated sample (pipeline check)</summary><p>Prompt: {report.sample.prompt}</p><GeneratedText text={report.sample.text}/><p className="dataset-caption">A small-corpus experiment does not establish readable or reliable output. Byte-level generation may produce incomplete characters.</p></details>
    </>}
    <div className="training-checkpoints"><h3>Verified checkpoints</h3>{!run.checkpoints.length && <p>{pilot ? "Checkpoints appear at the planned epoch boundaries and completion." : "Checkpoints appear after every 50 optimizer steps and at completion."}</p>}
      {run.checkpoints.map((c) => <div className="training-checkpoint" key={c.id}><a className="secondary" href={checkpointDownload(projectId, run.id, c.id, run.trainingKind ?? "smoke")}>Download step {c.step}</a><code>{c.sha256}</code></div>)}
      {run.manifest?.report.validation && <div>
        <h4>Validation loss by checkpoint</h4>
        <ul>{run.manifest.report.validation.map((value) => <li key={value.step}>Step {value.step} · loss {value.validationLoss.toFixed(4)} · {value.validationBlocks} blocks</li>)}</ul>
      </div>}
      {(run.status === "completed" || (pilot && ["failed", "cancelled"].includes(run.status))) && <div className="training-actions"><label>Resume checkpoint<select aria-label="Resume checkpoint" value={checkpoint?.id ?? ""} disabled={!intermediate.length} onChange={(e) => setCheckpointId(e.target.value)}>{!intermediate.length && <option value="">No intermediate checkpoint</option>}{intermediate.map((c) => <option key={c.id} value={c.id}>Step {c.step} → {run.configuration.maxSteps}</option>)}</select></label><button className="secondary" disabled={busy || !checkpoint} onClick={() => onAction("resume", checkpoint?.id)}>{pilot ? "Resume pilot" : "Resume verification"}</button></div>}
    </div>
  </section>;
}

function LossChart({ events }: { events: TrainingMetric[] }) {
  const values = events.filter((e) => e.loss != null && Number.isFinite(e.loss));
  const losses = values.map((e) => e.loss!);
  const low = Math.min(...losses), high = Math.max(...losses), maxStep = Math.max(...values.map((e) => e.step ?? 0), 1);
  const firstStep = values[0]?.step ?? 1;
  const points = values.map((e) => `${42+((e.step ?? firstStep)-firstStep)/Math.max(maxStep-firstStep,1)*626},${160-(e.loss!-low)/Math.max(high-low,0.000001)*135}`).join(" ");
  return <figure className="training-loss"><figcaption>Measured training loss · {values.length} optimizer steps</figcaption><svg viewBox="0 0 700 195" role="img" aria-label={`Training loss from ${losses[0]?.toFixed(4)} to ${losses.at(-1)?.toFixed(4)}`}><text x="0" y="24">{high.toFixed(2)}</text><text x="0" y="164">{low.toFixed(2)}</text><line x1="42" y1="170" x2="680" y2="170" stroke="currentColor" opacity=".2"/><polyline points={points} fill="none" stroke="var(--accent, #42683a)" strokeWidth="2"/><text x="42" y="190">Step {firstStep}</text><text x="620" y="190">{maxStep}</text></svg></figure>;
}
