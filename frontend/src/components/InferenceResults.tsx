import { useCallback, useEffect, useState } from "react";
import { annotationExport, inferenceDownload, listAnnotations, saveAnnotation } from "../services/inference";
import { inferenceActive, type Annotation, type Generation, type InferenceRun } from "../types/inference";

export function InferenceHistory({ runs, selected, onSelect }: { runs: InferenceRun[]; selected?: InferenceRun; onSelect: (id: string) => void }) {
  return <div className="tokenizer-run-list">{runs.map((r) => <button key={r.id} className={`card tokenizer-run-choice ${selected?.id === r.id ? "selected" : ""}`} aria-pressed={selected?.id === r.id} onClick={() => onSelect(r.id)}><strong>{r.kind === "generation" ? "Completion" : "Evaluation"} · {r.status}</strong><span>Step {r.checkpoints.map((c) => c.step).join(" / ")}</span><small>{new Date(r.createdAt).toLocaleString()}</small></button>)}</div>;
}

export function InferenceResults({ projectId, run, busy, onAction, onDirtyChange }: { projectId: string; run: InferenceRun; busy: boolean; onAction: (action: "cancel" | "retry" | "delete") => void; onDirtyChange?: (dirty: boolean) => void }) {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [notesLoaded, setNotesLoaded] = useState(false);
  const [notesError, setNotesError] = useState("");
  const [drafts, setDrafts] = useState<Record<string, boolean>>({});
  const notesDirty = Object.values(drafts).some(Boolean);
  const draftChanged = useCallback((key: string, value: boolean) => setDrafts((all) => all[key] === value ? all : { ...all, [key]: value }), []);
  useEffect(() => { onDirtyChange?.(notesDirty); }, [notesDirty, onDirtyChange]);
  useEffect(() => () => onDirtyChange?.(false), [onDirtyChange]);
  const loadNotes = useCallback(async (signal?: AbortSignal) => {
    const next = await listAnnotations(projectId, run.id, signal);
    if (signal?.aborted) return;
    setAnnotations(next); setNotesLoaded(true); setNotesError("");
  }, [projectId, run.id]);
  useEffect(() => {
    if (run.kind !== "evaluation" || run.status !== "completed") return;
    const controller = new AbortController();
    void loadNotes(controller.signal).catch((e: unknown) => { if (!controller.signal.aborted) setNotesError(e instanceof Error ? e.message : "Review notes unavailable."); });
    return () => controller.abort();
  }, [run.kind, run.status, loadNotes]);
  const report = run.manifest?.report;
  const active = inferenceActive(run);
  return <section className="card inference-results">
    <div className="card-heading"><div><span className="pill">{run.status}</span><h2>{run.kind === "generation" ? "Saved completion" : "Checkpoint comparison"}</h2><p>{run.elapsedSeconds.toFixed(1)}s elapsed · CPU · greedy decoding</p></div><div className="training-actions">{active ? <button className="secondary" disabled={busy || run.cancelRequested} onClick={() => onAction("cancel")}>{run.cancelRequested ? "Cancelling…" : "Cancel run"}</button> : <><button className="secondary" disabled={busy || notesDirty} onClick={() => onAction("retry")}>Retry same settings</button><button className="text-button" disabled={busy || notesDirty} onClick={() => onAction("delete")}>Delete run</button></>}</div></div>
    {run.error && <p className="error-banner" role="alert">{run.error}</p>}
    {active && <div role="status"><p>Stage: {run.status}{run.metrics.checkpointStep ? ` · checkpoint ${run.metrics.checkpointStep}` : ""}</p><progress aria-label="Inference progress" {...(run.metrics.totalUnits ? { value: run.metrics.completedUnits ?? 0, max: run.metrics.totalUnits } : {})}/>{run.metrics.totalUnits ? <p>{run.metrics.completedUnits ?? 0} / {run.metrics.totalUnits} measured work units</p> : null}</div>}
    {report && <>
      {report.warnings.map((w) => <p className="info-note" key={w}>{w}</p>)}
      <div className="training-actions">{[["bundle", "Complete results ZIP"], ["report", "Report JSON"], ["outputs", "Outputs JSONL"], ["manifest", "Manifest"]].map(([key, label]) => <a className="secondary" key={key} href={inferenceDownload(projectId, run.kind, run.id, key)}>{label}</a>)}{run.kind === "evaluation" && <a className="secondary" href={annotationExport(projectId, run.id)}>Manual review export</a>}</div>
      {run.kind === "evaluation" && <>
        <p className="dataset-caption">{report.protocol.name} · {report.protocol.blockLength} positions · compare only the same tokenizer/data/protocol. Lower training loss is not an automatic quality ranking.</p>
        <div className="inference-table-wrap"><table className="inference-table"><caption>{run.settings.metricScope === "training" ? "Original training-corpus diagnostic" : run.settings.metricScope === "external" ? "Independent evaluation target" : "Original validation split"}</caption><thead><tr><th>Checkpoint</th><th>Target loss</th><th>Block perplexity</th><th>Blocks / targets</th><th>Original smoke-subset loss</th></tr></thead><tbody>{report.results.map((r) => <tr key={r.checkpointId}><th>Step {r.step}</th><td>{r.metrics?.primary.loss?.toFixed(4) ?? "Not available"}</td><td>{r.metrics?.primary.perplexityOverflow ? "Overflow" : r.metrics?.primary.perplexity?.toFixed(3) ?? "Not available"}</td><td>{r.metrics?.primary.blocks ?? 0} / {r.metrics?.primary.targetTokens ?? 0}</td><td>{r.metrics?.trainedSubset.loss?.toFixed(4) ?? "Not available"}</td></tr>)}</tbody></table></div>
        {notesError && <p className="error-banner" role="alert">{notesError}</p>}
        <button className="text-button" disabled={notesDirty} onClick={() => { void loadNotes().catch((e: unknown) => setNotesError(e instanceof Error ? e.message : "Notes unavailable.")); }}>Reload saved review notes</button>
      </>}
      {run.settings.prompts.map((prompt, index) => <section className="inference-prompt-result" key={index}><h3>Prompt {index + 1}</h3><pre className="inference-prompt">{prompt.text || "[Empty prompt: BOS only]"}</pre>{prompt.notes && <p className="dataset-caption">Reviewer context: {prompt.notes}</p>}
        <div className={`inference-comparison ${report.results.length === 1 ? "single" : ""}`}>{report.results.map((r) => {
          const generated = r.generations.find((g) => g.promptIndex === index);
          if (!generated) return null;
          const saved = annotations.find((a) => a.checkpointId === r.checkpointId && a.promptIndex === index);
          return <article className="inference-output" key={r.checkpointId}><h4>Step {r.step}</h4><GenerationOutput value={generated}/>{run.kind === "evaluation" && <details><summary>Manual review notes</summary>{notesLoaded ? <AnnotationEditor key={`${r.checkpointId}-${index}`} projectId={projectId} runId={run.id} checkpointId={r.checkpointId} promptIndex={index} saved={saved} onDraft={draftChanged} onSaved={(next) => setAnnotations((all) => [...all.filter((a) => !(a.checkpointId === next.checkpointId && a.promptIndex === next.promptIndex)), next])}/> : <p>Load saved notes before reviewing.</p>}</details>}</article>;
        })}</div>
      </section>)}
      <p className="dataset-caption">Checkpoint weights verified unchanged. Generated text may be repetitive or unreadable; this tiny model is a text-completion model. Tokenizer SHA-256: <code>{report.tokenizerSha256}</code></p>
    </>}
  </section>;
}

function GenerationOutput({ value }: { value: Generation }) {
  return <><pre className="inference-continuation">{value.text || "[EOS / empty continuation]"}</pre>{value.escapedNul && <p className="dataset-caption">NUL is escaped for display; raw token IDs preserve the output.</p>}<p className="dataset-caption">{value.generatedTokenCount} new tokens · {value.elapsedSeconds.toFixed(3)}s · {value.tokensPerSecond.toFixed(1)} tokens/s{value.stoppedOnEOS ? " · stopped on EOS" : ""}</p><details><summary>Raw generated token IDs</summary><pre className="inference-ids">{JSON.stringify(value.newTokenIds)}</pre></details></>;
}

function AnnotationEditor({ projectId, runId, checkpointId, promptIndex, saved, onDraft, onSaved }: { projectId: string; runId: string; checkpointId: string; promptIndex: number; saved?: Annotation; onDraft: (key: string, dirty: boolean) => void; onSaved: (saved: Annotation) => void }) {
  const initial: Annotation = saved ?? { checkpointId, promptIndex, revision: 0, readability: "not-reviewed", repetition: "not-reviewed", sourceAgreement: "not-reviewed", notes: "" };
  const [draft, setDraft] = useState(initial);
  const [baseline, setBaseline] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(baseline);
  const key = `${checkpointId}-${promptIndex}`;
  useEffect(() => { setDraft(initial); setBaseline(initial); }, [initial.revision]); // versioned server updates
  useEffect(() => { onDraft(key, dirty || busy); }, [key, dirty, busy, onDraft]);
  useEffect(() => () => onDraft(key, false), [key, onDraft]);
  async function save() {
    setBusy(true); setError(""); setNotice("");
    try { const next = await saveAnnotation(projectId, runId, draft); setDraft(next); setBaseline(next); onSaved(next); setNotice("Review notes saved."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save notes."); }
    finally { setBusy(false); }
  }
  return <div className="annotation-editor"><p className="dataset-caption">Human observations; no automatic factual accuracy score.</p>
    <label>Readability<select aria-label={`Readability ${key}`} disabled={busy} value={draft.readability} onChange={(e) => setDraft({ ...draft, readability: e.target.value as Annotation["readability"] })}><option value="not-reviewed">Not reviewed</option><option value="readable">Readable</option><option value="needs-review">Needs review</option></select></label>
    <label>Repetition<select aria-label={`Repetition ${key}`} disabled={busy} value={draft.repetition} onChange={(e) => setDraft({ ...draft, repetition: e.target.value as Annotation["repetition"] })}><option value="not-reviewed">Not reviewed</option><option value="present">Present</option><option value="absent">Absent</option></select></label>
    <label>Agreement with source<select aria-label={`Source agreement ${key}`} disabled={busy} value={draft.sourceAgreement} onChange={(e) => setDraft({ ...draft, sourceAgreement: e.target.value as Annotation["sourceAgreement"] })}><option value="not-reviewed">Not reviewed</option><option value="matches-source">Matches reviewed source</option><option value="needs-review">Needs review</option></select></label>
    <label>Review notes<textarea aria-label={`Review notes ${key}`} disabled={busy} maxLength={4000} rows={3} value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })}/></label>
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}<div className="training-actions"><button className="secondary" disabled={busy || !dirty} onClick={() => void save()}>Save review notes</button><button className="text-button" disabled={busy || !dirty} onClick={() => { setDraft(baseline); setError(""); }}>Discard note edits</button></div>
  </div>;
}
