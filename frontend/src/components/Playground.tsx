import { useEffect, useState } from "react";
import type { Project } from "../types/project";
import type { PromptBudget } from "../types/inference";
import { previewInference, startGeneration } from "../services/inference";
import { useRuns } from "../features/inference/useRuns";
import { InferenceHistory, InferenceResults } from "./InferenceResults";

export function Playground({ project, onSetup, onTraining }: { project: Project | null; onSetup: () => void; onTraining: () => void }) {
  if (!project?.revision) return <section className="empty-card"><h2>Save a project first.</h2><button className="primary" onClick={onSetup}>Project setup</button></section>;
  return <Workspace key={project.id} projectId={project.id} onTraining={onTraining}/>;
}

function Workspace({ projectId, onTraining }: { projectId: string; onTraining: () => void }) {
  const state = useRuns(projectId, "generation");
  const [sourceId, setSourceId] = useState("");
  const [checkpointId, setCheckpointId] = useState("");
  const [prompt, setPrompt] = useState("একজন pilot");
  const [maximum, setMaximum] = useState(32);
  const [budget, setBudget] = useState<PromptBudget | null>(null);
  const [previewError, setPreviewError] = useState("");
  const source = state.sources.find((s) => s.id === sourceId) ?? state.sources.find((s) => s.checkpoints.some((c) => c.eligible));
  const eligible = source?.checkpoints.filter((c) => c.eligible) ?? [];
  const checkpoint = eligible.find((c) => c.id === checkpointId) ?? eligible.at(-1);
  const bytes = new TextEncoder().encode(prompt).length;
  useEffect(() => {
    setBudget(null); setPreviewError("");
    if (!checkpoint || bytes > 4096) return;
    const controller = new AbortController();
    const timer = setTimeout(() => { void previewInference(projectId, checkpoint.id, prompt, controller.signal).then((next) => { if (!controller.signal.aborted) setBudget(next); }).catch((e: unknown) => { if (!controller.signal.aborted) setPreviewError(e instanceof Error ? e.message : "Token preview unavailable."); }); }, 350);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [projectId, checkpoint?.id, prompt, bytes]);
  return <div className="training-page inference-page">
    {state.error && <p className="error-banner" role="alert">{state.error}</p>}{state.notice && <p className="notice" role="status">{state.notice}</p>}
    <section className="card training-form"><span className="eyebrow">SAVED CHECKPOINT · CPU</span><h2>Continue a piece of text.</h2><p>Use your frozen tokenizer and trained weights. This is a text-completion model; the prompt is not a chat instruction.</p>
      <div className="training-fields"><label>Training run<select aria-label="Playground training run" value={source?.id ?? ""} disabled={state.busy || state.loading} onChange={(e) => { setSourceId(e.target.value); setCheckpointId(""); }}><option value="">Choose a completed CPU run</option>{state.sources.map((s) => <option key={s.id} value={s.id} disabled={!s.checkpoints.some((c) => c.eligible)}>{s.datasetName} v{s.datasetVersion} · {new Date(s.createdAt).toLocaleString()} · {s.status}</option>)}</select></label>
        <label>Checkpoint<select aria-label="Playground checkpoint" disabled={state.busy || !eligible.length} value={checkpoint?.id ?? ""} onChange={(e) => setCheckpointId(e.target.value)}>{!eligible.length && <option value="">No eligible checkpoint</option>}{eligible.map((c) => <option key={c.id} value={c.id}>Step {c.step}</option>)}</select></label></div>
      {source && <><p className="dataset-caption">{source.configuration.estimatedParameters.toLocaleString()} parameters · {source.configuration.vocabSize} vocabulary · {source.configuration.contextLength} context · final checkpoint is a convenient default, not a quality ranking.</p><code className="tokenizer-checksum">Tokenizer SHA-256 {source.tokenizerSha256}</code></>}
      <label>Completion prompt<textarea aria-label="Completion prompt" maxLength={4096} rows={5} value={prompt} onChange={(e) => setPrompt(e.target.value)}/></label>
      <p className="dataset-caption">{bytes} / 4,096 UTF-8 bytes{budget ? ` · ${budget.promptTokens} prompt tokens + 1 BOS · ${budget.availableNewTokens} output positions available` : " · calculating token budget…"}</p>
      {bytes > 4096 && <p role="alert">Prompt exceeds 4 KiB UTF-8. Shorten it before generating.</p>}{previewError && <p role="alert">{previewError}</p>}
      <div className="training-actions"><label>Maximum new tokens<select aria-label="Maximum new tokens" value={maximum} onChange={(e) => setMaximum(Number(e.target.value))}>{[8,16,32,64,128].map((n) => <option key={n} value={n} disabled={budget ? n > budget.availableNewTokens : false}>{n}</option>)}</select></label><button className="primary" disabled={state.busy || !checkpoint || bytes > 4096 || !budget?.roundTripMatches || maximum > budget.availableNewTokens} onClick={() => { if (checkpoint) void state.start(() => startGeneration(projectId, checkpoint.id, prompt, maximum)); }}>Generate completion</button><button className="text-button" onClick={() => { void state.refresh().catch((e: unknown) => state.setError(e instanceof Error ? e.message : "Refresh failed.")); }}>Refresh</button></div>
      {!state.loading && !source && <p>No eligible saved checkpoint yet. <button className="text-button" onClick={onTraining}>Open pre-training</button></p>}
    </section>
    {state.loading && <p role="status">Loading checkpoints…</p>}<InferenceHistory runs={state.runs} selected={state.selected} onSelect={state.setSelectedId}/>
    {state.selected && <InferenceResults key={state.selected.id} projectId={projectId} run={state.selected} busy={state.busy} onAction={(a) => void state.action(a, state.selected!)}/>}
  </div>;
}
