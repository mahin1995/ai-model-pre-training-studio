import { useCallback, useEffect, useState } from "react";
import { FlaskConical, Download } from "lucide-react";
import type { Project } from "../types/project";
import { smokeActive, type ModelConfig, type SmokeRun, type TrainingMetric, type TrainingRuntime as Runtime } from "../types/training";
import { checkpointDownload, deleteSmoke, listModelConfigs, listSmokeRuns, smokeAction, smokeDownload, smokeMetrics, startSmoke } from "../services/training";
import { TrainingRuntime } from "./TrainingRuntime";

export function PreTraining({ project, onSetup, onConfig }: { project: Project | null; onSetup: () => void; onConfig: () => void }) {
  if (!project?.revision) return <section className="empty-card"><FlaskConical size={36}/><h2>Save a project first.</h2><button className="primary" onClick={onSetup}>Project setup</button></section>;
  return <TrainingWorkspace key={project.id} projectId={project.id} onConfig={onConfig}/>;
}

function TrainingWorkspace({ projectId, onConfig }: { projectId: string; onConfig: () => void }) {
  const [configs, setConfigs] = useState<ModelConfig[]>([]);
  const [runs, setRuns] = useState<SmokeRun[]>([]);
  const [configId, setConfigId] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [runtime, setRuntime] = useState<Runtime | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const selected = runs.find((r) => r.id === selectedId) ?? runs[0];
  const config = configs.find((c) => c.id === configId) ?? configs[0];
  const active = runs.some(smokeActive);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const [nextConfigs, nextRuns] = await Promise.all([listModelConfigs(projectId, signal), listSmokeRuns(projectId, signal)]);
    if (signal?.aborted) return;
    setConfigs(nextConfigs); setRuns(nextRuns);
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
  async function command(action: "start" | "cancel" | "retry" | "resume" | "delete", checkpointId?: string) {
    if (action === "delete" && !window.confirm("Delete this run and all its checkpoints? Runs used for resume are protected.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (action === "start" && config) { const next = await startSmoke(projectId, config.id); setSelectedId(next.id); setNotice("Smoke-test run queued with fixed source and configuration."); }
      else if (selected && action === "delete") { const result = await deleteSmoke(projectId, selected.id); setNotice(result.cleanupWarning ?? "Run deleted."); }
      else if (selected && (action === "cancel" || action === "retry" || action === "resume")) { const next = await smokeAction(projectId, selected.id, action, checkpointId); if (action !== "cancel") setSelectedId(next.id); setNotice(action === "cancel" ? "Cancellation requested." : "New run queued. Original artifacts are preserved."); }
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Training action failed."); }
    finally { setBusy(false); }
  }
  const deviceReady = runtime?.ready && (config?.configuration.device === "cpu" || (config?.configuration.device === "cuda" ? runtime.cuda : !runtime.cudaError));
  return <div className="training-page">
    {error && <div className="error-banner" role="alert">{error}</div>}{notice && <p className="notice" role="status">{notice}</p>}
    <TrainingRuntime projectId={projectId} onReport={setRuntime}/>
    <section className="card training-form"><span className="eyebrow">BOUNDED SMOKE TEST</span><h2>Run a small, measurable training check.</h2><p>Train on up to two training blocks. This checks numerical stability and checkpoints; it does not measure general language ability.</p>
      <label>Saved model configuration<select aria-label="Saved model configuration" disabled={busy || loading} value={config?.id ?? ""} onChange={(e) => setConfigId(e.target.value)}><option value="">Choose a saved configuration</option>{configs.map((c) => <option key={c.id} value={c.id}>{c.name} · revision {c.revision} · {c.configuration.maxSteps} steps</option>)}</select></label>
      {config && <p className="dataset-caption">{config.source.datasetName} v{config.source.datasetVersion} · {config.configuration.vocabSize.toLocaleString()} vocabulary · {config.configuration.contextLength} context · {config.configuration.device} / FP32 · {config.configuration.timeLimitSeconds}s time limit</p>}
      <div className="training-actions"><button className="primary" disabled={busy || loading || !config || !deviceReady} onClick={() => void command("start")}>Run smoke test</button><button className="secondary" onClick={onConfig}>Model configuration</button><button className="text-button" disabled={busy || loading} onClick={() => { void refresh().catch((e: unknown) => setError(e instanceof Error ? e.message : "Refresh failed.")); }}>Refresh runs</button></div>
      {!runtime && <p className="dataset-caption">Check the training runtime above before starting.</p>}
    </section>
    {loading ? <p role="status">Loading smoke-test history…</p> : !runs.length ? <section className="empty-card"><FlaskConical size={36}/><h2>No smoke-test runs yet.</h2><p>Save a configuration, check the executor and start a bounded run.</p></section> : <>
      <div className="tokenizer-run-list">{runs.map((r) => <button className={`card tokenizer-run-choice ${selected?.id === r.id ? "selected" : ""}`} aria-pressed={selected?.id === r.id} key={r.id} onClick={() => setSelectedId(r.id)}><strong>{r.parentRunId ? "Resume verification" : "Smoke test"} · {r.status}</strong><span>{r.verdict ?? `${r.metrics.step ?? 0} / ${r.configuration.maxSteps} steps`}</span><small>{new Date(r.createdAt).toLocaleString()}</small></button>)}</div>
      {selected && <RunDetails key={selected.id} projectId={projectId} run={selected} busy={busy} onAction={(a, cp) => void command(a, cp)}/>}
    </>}
  </div>;
}

function RunDetails({ projectId, run, busy, onAction }: { projectId: string; run: SmokeRun; busy: boolean; onAction: (action: "cancel" | "retry" | "resume" | "delete", checkpoint?: string) => void }) {
  const [events, setEvents] = useState<TrainingMetric[]>([]);
  const [error, setError] = useState("");
  const [checkpointId, setCheckpointId] = useState("");
  const active = smokeActive(run);
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try { const next = await smokeMetrics(projectId, run.id, -1, controller.signal); if (!controller.signal.aborted) { setEvents(next.events); setError(""); } }
      catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Metrics unavailable."); }
      if (active && !controller.signal.aborted) timer = setTimeout(() => void refresh(), 1500);
    }
    void refresh(); return () => { controller.abort(); clearTimeout(timer); };
  }, [projectId, run.id, active]);
  const m = run.metrics;
  const report = run.manifest?.report;
  const intermediate = run.checkpoints.filter((c) => c.step < run.configuration.maxSteps);
  const checkpoint = intermediate.find((c) => c.id === checkpointId) ?? intermediate[0];
  return <section className="card smoke-details"><div className="card-heading"><div><span className="pill">{run.status}{run.verdict ? ` · ${run.verdict}` : ""}</span><h2>{run.parentRunId ? "Resume verification" : "Training diagnostic"}</h2><p>{run.elapsedSeconds.toFixed(1)}s elapsed · {run.runtime.device} · FP32</p></div><div className="training-actions">{active ? <button className="secondary" disabled={busy || run.cancelRequested} onClick={() => onAction("cancel")}>{run.cancelRequested ? "Cancelling…" : "Cancel run"}</button> : <><button className="secondary" disabled={busy} onClick={() => onAction("retry")}>Retry from scratch</button><button className="text-button" disabled={busy} onClick={() => onAction("delete")}>Delete run</button></>}</div></div>
    {run.error && <p className="error-banner" role="alert">{run.error}</p>}
    {active && <p role="status">{run.status === "training" ? "Training on the fixed diagnostic subset." : `Stage: ${run.status}.`}</p>}
    <progress aria-label="Optimizer step progress" max={run.configuration.maxSteps} value={m.step ?? 0}/>
    <div className="dataset-stats"><div><strong>{m.step ?? 0} / {run.configuration.maxSteps}</strong><span>Optimizer steps</span></div><div><strong>{m.loss?.toFixed(4) ?? "—"}</strong><span>Latest training loss</span></div><div><strong>{m.targetTokensPerSecond?.toFixed(0) ?? "—"}</strong><span>Supervised target tokens / second</span></div></div>
    <p className="dataset-caption">Step time: {m.stepSeconds?.toFixed(3) ?? "—"}s · CPU RSS: {m.rssBytes ? (m.rssBytes/1024**2).toFixed(0)+" MiB" : "—"} · CUDA peak allocated / reserved: {m.cudaPeakAllocatedBytes != null ? `${(m.cudaPeakAllocatedBytes/1024**2).toFixed(0)} / ${(m.cudaPeakReservedBytes!/1024**2).toFixed(0)} MiB` : "not applicable"}</p>
    {error && <p role="alert">{error}</p>}{events.length > 0 && <LossChart events={events}/>}
    {report && <><div className="dataset-stats"><div><strong>{report.initialLoss.toFixed(4)} → {report.finalLoss.toFixed(4)}</strong><span>Same-subset eval loss · {(report.lossDecreaseRatio*100).toFixed(1)}% decrease</span></div><div><strong>{report.parameters.toLocaleString()}</strong><span>Measured parameters</span></div><div><strong>{report.reloadMatches ? "Matched" : "Failed"}</strong><span>Fresh-process checkpoint reload</span></div></div>
      {report.startingStep > 0 && <p>Resumed from optimizer step {report.startingStep}; starting loss {report.startLoss.toFixed(4)}. Decrease is measured against the original run’s initial loss.</p>}
      <p>{report.finiteGradients && report.weightsChanged ? "Finite gradients and changed model weights verified." : "Inspect technical checks."} A pass requires at least 5% lower fixed-subset loss.</p>
      {report.warnings.map((w) => <p className="info-note" key={w}>{w}</p>)}
      <div className="training-actions">{[["bundle","Complete training bundle"],["report","Diagnostic report"],["metrics","Metrics JSONL"],["manifest","Manifest"]].map(([key, label]) => <a className="secondary" key={key} href={smokeDownload(projectId, run.id, key)}><Download size={14}/>{label}</a>)}</div>
      <details className="training-sample"><summary>Generated sample (pipeline check)</summary><p>Prompt: {report.sample.prompt}</p><pre>{report.sample.text || "[EOS / empty continuation]"}</pre><p className="dataset-caption">A tiny training subset does not establish readable or reliable output. Byte-level generation may produce incomplete characters.</p></details>
    </>}
    <div className="training-checkpoints"><h3>Verified checkpoints</h3>{!run.checkpoints.length && <p>Checkpoints appear after every 50 optimizer steps and at completion.</p>}
      {run.checkpoints.map((c) => <div className="training-checkpoint" key={c.id}><a className="secondary" href={checkpointDownload(projectId, run.id, c.id)}>Download step {c.step}</a><code>{c.sha256}</code></div>)}
      {run.status === "completed" && <div className="training-actions"><label>Resume checkpoint<select aria-label="Resume checkpoint" value={checkpoint?.id ?? ""} disabled={!intermediate.length} onChange={(e) => setCheckpointId(e.target.value)}>{!intermediate.length && <option value="">No intermediate checkpoint</option>}{intermediate.map((c) => <option key={c.id} value={c.id}>Step {c.step} → {run.configuration.maxSteps}</option>)}</select></label><button className="secondary" disabled={busy || !checkpoint} onClick={() => onAction("resume", checkpoint?.id)}>Resume verification</button></div>}
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
