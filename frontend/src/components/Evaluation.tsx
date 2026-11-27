import { useCallback, useEffect, useState } from "react";
import type { Project } from "../types/project";
import type { SourceVersion } from "../types/tokenizers";
import type { PromptSetDraft, PromptVersion } from "../types/inference";
import { deletePromptSet, listPromptSets, promptSetExport, savePromptSet, startEvaluation } from "../services/inference";
import { listSources } from "../services/tokenizers";
import { useRuns } from "../features/inference/useRuns";
import { InferenceHistory, InferenceResults } from "./InferenceResults";

const emptySet = (): PromptSetDraft => ({ name: "Checkpoint comparison", language: "mixed", prompts: [{ text: "একজন pilot", notes: "" }] });

export function Evaluation({ project, onSetup, onTraining, onDirtyChange }: { project: Project | null; onSetup: () => void; onTraining: () => void; onDirtyChange: (dirty: boolean) => void }) {
  if (!project?.revision) return <section className="empty-card"><h2>Save a project first.</h2><button className="primary" onClick={onSetup}>Project setup</button></section>;
  return <Workspace key={project.id} projectId={project.id} onTraining={onTraining} onDirtyChange={onDirtyChange}/>;
}

function Workspace({ projectId, onTraining, onDirtyChange }: { projectId: string; onTraining: () => void; onDirtyChange: (dirty: boolean) => void }) {
  const state = useRuns(projectId, "evaluation");
  const [sourceId, setSourceId] = useState("");
  const [selectedCheckpoints, setSelectedCheckpoints] = useState<string[] | null>(null);
  const [sets, setSets] = useState<PromptVersion[]>([]);
  const [setId, setSetId] = useState("");
  const [versions, setVersions] = useState<SourceVersion[]>([]);
  const [scope, setScope] = useState<"training" | "validation" | "test" | "external" | "final-test">("training");
  const [externalId, setExternalId] = useState("");
  const [maximum, setMaximum] = useState(32);
  const [draft, setDraft] = useState<PromptSetDraft>(emptySet);
  const [baseline, setBaseline] = useState<PromptSetDraft>(emptySet);
  const [saving, setSaving] = useState(false);
  const [notesDirty, setNotesDirty] = useState(false);
  const promptDirty = JSON.stringify(draft) !== JSON.stringify(baseline);
  const dirty = promptDirty || notesDirty || saving;
  const noteChanged = useCallback((value: boolean) => setNotesDirty(value), []);
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([listPromptSets(projectId, controller.signal), listSources(projectId, controller.signal)]).then(([saved, sources]) => {
      if (!controller.signal.aborted) { setSets(saved); setVersions(sources); }
    }).catch((e: unknown) => { if (!controller.signal.aborted) state.setError(e instanceof Error ? e.message : "Could not load prompt/source versions."); });
    return () => controller.abort();
  }, [projectId]);
  const source = state.sources.find((s) => s.id === sourceId) ?? state.sources.find((s) => s.checkpoints.some((c) => c.eligible));
  const eligible = source?.checkpoints.filter((c) => c.eligible) ?? [];
  const needsCorpus = scope === "external" || scope === "final-test";
  const otherCandidates = needsCorpus && source ? state.sources
    .filter((run) => run.id !== source.id && run.tokenizerSha256 === source.tokenizerSha256 &&
      run.configuration.layers === source.configuration.layers && run.configuration.hiddenSize === source.configuration.hiddenSize &&
      run.configuration.heads === source.configuration.heads && run.configuration.contextLength === source.configuration.contextLength)
    .flatMap((run) => run.checkpoints.filter((checkpoint) => checkpoint.eligible).map((checkpoint) =>
      ({ ...checkpoint, name: `${run.currentDatasetName ?? run.datasetName} · ${new Date(run.createdAt).toLocaleString()}` }))) : [];
  const candidates = [...eligible.map((checkpoint) => ({ ...checkpoint, name: "" })), ...otherCandidates];
  const checkpoints = selectedCheckpoints?.filter((id) => candidates.some((candidate) => candidate.id === id)) ?? eligible.slice(-4).map((c) => c.id);
  const promptSet = sets.find((s) => s.id === setId) ?? sets[0];
  const external = versions.find((v) => v.versionId === externalId && v.eligible);
  function guard(operation: () => void) {
    if (dirty) { state.setError("Save or discard prompt/review-note edits before changing the selected report or prompt draft."); return; }
    operation();
  }
  async function saveSet() {
    setSaving(true); state.setError(""); state.setNotice("");
    try { const next = await savePromptSet(projectId, draft); setSets((all) => [next, ...all]); setSetId(next.id); const value: PromptSetDraft = { id: next.promptSetId, name: next.name, language: next.language, prompts: next.prompts }; setDraft(value); setBaseline(value); state.setNotice(`Prompt-set version ${next.version} saved.`); }
    catch (e) { state.setError(e instanceof Error ? e.message : "Could not save prompt set."); }
    finally { setSaving(false); }
  }
  function editSet(saved: PromptVersion) { guard(() => { const value = { id: saved.promptSetId, name: saved.name, language: saved.language, prompts: saved.prompts }; setDraft(value); setBaseline(value); }); }
  async function removeSet(saved: PromptVersion) {
    if (!window.confirm("Delete this prompt set and all versions? Referenced sets are protected.")) return;
    setSaving(true); state.setError("");
    try { await deletePromptSet(projectId, saved.promptSetId); setSets((all) => all.filter((s) => s.promptSetId !== saved.promptSetId)); state.setNotice("Prompt set deleted."); }
    catch (e) { state.setError(e instanceof Error ? e.message : "Delete failed."); }
    finally { setSaving(false); }
  }
  return <div className="training-page inference-page">
    {state.error && <p className="error-banner" role="alert">{state.error}</p>}{state.notice && <p className="notice" role="status">{state.notice}</p>}
    <section className="card training-form"><span className="eyebrow">VERSIONED PROMPTS</span><h2>Compare the same prompts.</h2><p>Save completion prompts before comparing checkpoints. Reviewer notes describe what to inspect; they do not create an automatic accuracy score.</p>
      <fieldset className="saving-fieldset" disabled={saving || state.busy}><div className="training-fields"><label>Prompt-set name<input aria-label="Prompt-set name" required maxLength={100} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })}/></label><label>Prompt language<select aria-label="Prompt language" value={draft.language} onChange={(e) => setDraft({ ...draft, language: e.target.value as PromptSetDraft["language"] })}><option value="mixed">Bangla + English</option><option value="bn">Bangla</option><option value="en">English</option></select></label></div>
      {draft.prompts.map((prompt, index) => <div className="prompt-editor-row" key={index}><label>Prompt {index + 1}<textarea aria-label={`Prompt text ${index + 1}`} maxLength={4096} rows={3} value={prompt.text} onChange={(e) => setDraft({ ...draft, prompts: draft.prompts.map((p, i) => i === index ? { ...p, text: e.target.value } : p) })}/></label><label>Reviewer context {index + 1}<input aria-label={`Reviewer context ${index + 1}`} maxLength={4000} value={prompt.notes} onChange={(e) => setDraft({ ...draft, prompts: draft.prompts.map((p, i) => i === index ? { ...p, notes: e.target.value } : p) })}/></label><button className="text-button" disabled={draft.prompts.length === 1} onClick={() => setDraft({ ...draft, prompts: draft.prompts.filter((_, i) => i !== index) })}>Remove prompt {index + 1}</button></div>)}
      <div className="training-actions"><button className="secondary" disabled={draft.prompts.length >= 20} onClick={() => setDraft({ ...draft, prompts: [...draft.prompts, { text: "", notes: "" }] })}>Add prompt</button><button className="primary" disabled={!draft.name.trim()} onClick={() => void saveSet()}>{draft.id ? "Save new prompt version" : "Save prompt set"}</button><button className="secondary" disabled={!promptDirty} onClick={() => setDraft(baseline)}>Discard prompt edits</button><button className="text-button" disabled={dirty} onClick={() => { const value = emptySet(); setDraft(value); setBaseline(value); }}>New prompt set</button></div>
      {promptDirty && <p role="status">Unsaved prompt-set edits</p>}</fieldset>
    </section>
    <section className="card training-form"><span className="eyebrow">CPU CHECKPOINT EVALUATION</span><h2>Inspect progress without updating weights.</h2>
      <div className="training-fields"><label>Training run<select aria-label="Evaluation training run" disabled={state.busy || state.loading} value={source?.id ?? ""} onChange={(e) => { setSourceId(e.target.value); setSelectedCheckpoints(null); }}><option value="">Choose a completed training run</option>{state.sources.map((s) => <option key={s.id} value={s.id} disabled={!s.checkpoints.some((c) => c.eligible)}>{s.configuration.trainingKind === "pilot" ? "Pilot" : "Smoke"} · {s.currentDatasetName ?? s.datasetName} v{s.datasetVersion} · {new Date(s.createdAt).toLocaleString()} · {s.status}</option>)}</select></label>
        <label>Saved prompt-set version<select aria-label="Saved prompt-set version" value={promptSet?.id ?? ""} disabled={state.busy || saving} onChange={(e) => guard(() => setSetId(e.target.value))}><option value="">Save a prompt set first</option>{sets.map((s) => <option key={s.id} value={s.id}>{s.name} · v{s.version} · {s.prompts.length} prompts</option>)}</select></label></div>
      {promptSet && <div className="training-actions"><button className="secondary" disabled={dirty} onClick={() => editSet(promptSet)}>Edit as new version</button><a className="secondary" href={promptSetExport(projectId, promptSet)}>Export prompts</a><button className="text-button" disabled={dirty} onClick={() => void removeSet(promptSet)}>Delete prompt set</button></div>}
      <fieldset className="checkpoint-options"><legend>Compare up to four checkpoints</legend>{candidates.map((c) => <label key={c.id}><input type="checkbox" aria-label={`Compare step ${c.step}`} checked={checkpoints.includes(c.id)} disabled={state.busy || (!checkpoints.includes(c.id) && checkpoints.length >= 4)} onChange={(e) => setSelectedCheckpoints(e.target.checked ? [...checkpoints, c.id] : checkpoints.filter((id) => id !== c.id))}/>{c.name ? `${c.name} · ` : ""}Step {c.step}</label>)}</fieldset>
      {source && <p className="dataset-caption">{source.configuration.vocabSize} vocabulary · {source.configuration.contextLength} context · {source.trainingBlocks} train blocks · {source.validationBlocks} validation blocks. Same tokenizer and protocol are used for every checkpoint.</p>}
      <div className="training-fields"><label>Metric source<select aria-label="Metric source" value={scope} onChange={(e) => setScope(e.target.value as typeof scope)}><option value="training">All original train blocks — diagnostic</option><option value="validation">Original validation split — if available</option><option value="external">Independent reviewed external corpus</option><option value="final-test">Independent Q&A final-test split</option><option value="test" disabled={!source?.testBlocks}>Reserved test split</option></select></label><label>Evaluation new tokens<select aria-label="Evaluation new tokens" value={maximum} onChange={(e) => setMaximum(Number(e.target.value))}>{[8,16,32,64,128].map((n) => <option key={n}>{n}</option>)}</select></label></div>
      {needsCorpus && <label>Independent reviewed dataset<select aria-label="Independent reviewed dataset" value={externalId} onChange={(e) => setExternalId(e.target.value)}><option value="">Choose an independent corpus</option>{versions.map((v) => <option key={v.versionId} value={v.versionId} disabled={!v.eligible}>{v.datasetName} · v{v.version}{!v.eligible ? ` · ${v.reason}` : ""}</option>)}</select></label>}
      <p className="info-note">{scope === "training" ? "Training diagnostic only. The remaining blocks of the same PDF are not independent evaluation data." : scope === "validation" && !source?.validationBlocks ? "Not available — add independent documents. Prompt comparisons can still run; held-out metrics will remain unavailable." : scope === "test" ? "Use reserved test data after selecting checkpoints and freezing the evaluation protocol." : "The checkpoint tokenizer stays frozen. Known source/content overlaps are blocked; near-duplicates still need manual review."}</p>
      <div className="training-actions"><button className="primary" disabled={state.busy || dirty || !promptSet || !checkpoints.length || (needsCorpus && !external) || (scope === "test" && !source?.testBlocks)} onClick={() => { if (promptSet) void state.start(() => startEvaluation(projectId, { checkpointIds: checkpoints, promptSetVersionId: promptSet.id, maxNewTokens: maximum, metricScope: scope, ...(needsCorpus ? { externalDatasetVersionId: externalId } : {}) })); }}>Run evaluation</button><button className="text-button" onClick={() => { void state.refresh().catch((e: unknown) => state.setError(e instanceof Error ? e.message : "Refresh failed.")); }}>Refresh evaluations</button></div>
      {!state.loading && !source && <button className="secondary" onClick={onTraining}>Open pre-training</button>}
    </section>
    <InferenceHistory runs={state.runs} selected={state.selected} onSelect={(id) => guard(() => state.setSelectedId(id))}/>
    {state.selected && <InferenceResults key={state.selected.id} projectId={projectId} run={state.selected} busy={state.busy} onAction={(a) => void state.action(a, state.selected!)} onDirtyChange={noteChanged}/>}
  </div>;
}
