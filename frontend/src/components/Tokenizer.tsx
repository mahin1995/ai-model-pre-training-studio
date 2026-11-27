import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Cpu, RefreshCw } from "lucide-react";
import type { Project } from "../types/project";
import { activeRun, type PreparationRun, type RunKind, type SourceVersion } from "../types/tokenizers";
import { cancelPreparation, deletePreparation, listRuns, listSources, retryPreparation, startSequences, startTokenizer } from "../services/tokenizers";
import { PreparationStatus, RunDownloads } from "./PreparationStatus";
import { TokenizerPlayground } from "./TokenizerPlayground";
import { SequencePanel } from "./SequencePanel";

export function Tokenizer({ project, onSetup, onDatasets }: { project: Project | null; onSetup: () => void; onDatasets: () => void }) {
  if (!project?.revision) return <section className="empty-card"><Cpu size={36}/><h2>Save a project first.</h2><p>Tokenizers and training sequences belong to a saved project and reviewed dataset version.</p><button className="primary" onClick={onSetup}>Project setup</button></section>;
  return <TokenizerWorkspace key={project.id} projectId={project.id} onDatasets={onDatasets}/>;
}

function TokenizerWorkspace({ projectId, onDatasets }: { projectId: string; onDatasets: () => void }) {
  const [sources, setSources] = useState<SourceVersion[]>([]);
  const [runs, setRuns] = useState<PreparationRun[]>([]);
  const [sequences, setSequences] = useState<PreparationRun[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [vocab, setVocab] = useState(8000);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const selected = runs.find((run) => run.id === selectedId) ?? runs[0];
  const hasActive = [...runs, ...sequences].some(activeRun);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const [nextSources, tokenizers, sequenceRuns] = await Promise.all([listSources(projectId, signal), listRuns(projectId, "tokenizers", signal), listRuns(projectId, "sequence-runs", signal)]);
    if (signal?.aborted) return;
    setSources(nextSources); setRuns(tokenizers); setSequences(sequenceRuns);
    setVersionId((current) => nextSources.some((source) => source.versionId === current && source.eligible) ? current : nextSources.find((source) => source.eligible)?.versionId ?? "");
  }, [projectId]);
  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal).catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not load tokenizers."); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => {
    if (!hasActive) return;
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { await refresh(controller.signal); } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Refresh failed; retrying."); }
      if (!controller.signal.aborted) timer = setTimeout(() => void poll(), 2000);
    }
    timer = setTimeout(() => void poll(), 2000);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [hasActive, refresh]);
  async function train(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { const run = await startTokenizer(projectId, versionId, vocab); setRuns((current) => [run, ...current]); setSelectedId(run.id); setNotice("Tokenizer run created. Track its status below; the reviewed source version is fixed."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not start tokenizer training."); }
    finally { setBusy(false); }
  }
  async function action(command: "cancel" | "retry" | "delete", kind: RunKind, run: PreparationRun) {
    if (command === "delete" && !window.confirm("Permanently delete this run and its stored artifacts? Source datasets are kept. Dependent runs must be deleted first.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (command === "cancel") { await cancelPreparation(projectId, kind, run.id); setNotice("Cancellation requested."); }
      if (command === "retry") { const next = await retryPreparation(projectId, kind, run.id); if (kind === "tokenizers") setSelectedId(next.id); setNotice("A new run was queued with the same immutable source and settings."); }
      if (command === "delete") { const result = await deletePreparation(projectId, kind, run.id); setNotice("Run deleted."); if (result.cleanupWarning) setError(result.cleanupWarning); }
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Run action failed."); }
    finally { setBusy(false); }
  }
  async function generate(length: number, datasetVersionId?: string, objective?: "sft") {
    if (!selected) return null;
    setBusy(true); setError(""); setNotice("");
    try { const run = await startSequences(projectId, selected.id, length, datasetVersionId, objective); setSequences((current) => [run, ...current]); setNotice("Sequence run created. Track its status below."); return run; }
    catch (e) { setError(e instanceof Error ? e.message : "Could not generate sequences."); return null; }
    finally { setBusy(false); }
  }
  return <div className="tokenizer-page">
    {error && <div className="error-banner" role="alert">{error}</div>}{notice && <p className="notice" role="status">{notice}</p>}
    <section className="card tokenizer-create"><div className="form-heading"><span className="eyebrow">CUSTOM BYTE-LEVEL BPE</span><h2>A vocabulary for your own text.</h2><p>Fit on reviewed training documents, inspect the saved tokenizer, then export sequences. Runs locally on CPU.</p></div>
      <form onSubmit={(event) => void train(event)}><fieldset disabled={busy || loading} className="saving-fieldset tokenizer-create-fields">
        <label>Reviewed dataset version<select aria-label="Reviewed dataset version" required value={versionId} onChange={(e) => setVersionId(e.target.value)}><option value="">Choose an eligible reviewed version</option>{sources.map((source) => <option key={source.versionId} value={source.versionId} disabled={!source.eligible}>{source.datasetName} · Version {source.version} · {source.eligible ? `${source.trainingRecords} training records` : source.reason}</option>)}</select></label>
        <label>Vocabulary target<input aria-label="Vocabulary target" type="number" min={260} max={32000} step={1} required value={Number.isNaN(vocab) ? "" : vocab} onChange={(e) => setVocab(e.target.valueAsNumber)}/></label>
        <button className="primary" disabled={!versionId || !Number.isInteger(vocab) || vocab < 260 || vocab > 32000} type="submit">Train tokenizer</button>
      </fieldset></form>
      <p className="dataset-caption">Training split only · Full byte coverage · PAD 0 / UNK 1 / BOS 2 / EOS 3. Actual vocabulary can be smaller than the target.</p>
      {!loading && !sources.some((source) => source.eligible) && <div className="info-note"><span>No eligible version yet. Publish a fully reviewed version in Datasets.</span><button className="text-button" onClick={onDatasets}>Open datasets</button></div>}
    </section>
    <div className="dataset-library-heading"><span>{runs.length} tokenizer run(s)</span><button className="text-button" disabled={busy || loading} onClick={() => { setError(""); void refresh().catch((e: unknown) => setError(e instanceof Error ? e.message : "Refresh failed.")); }}><RefreshCw size={14}/>Refresh tokenizers</button></div>
    {loading ? <p role="status">Loading saved tokenizers…</p> : runs.length ? <>
      <div className="tokenizer-run-list">{runs.map((run) => <button key={run.id} className={`card tokenizer-run-choice ${selected?.id === run.id ? "selected" : ""}`} aria-pressed={selected?.id === run.id} onClick={() => setSelectedId(run.id)}><strong>{run.datasetName} · v{run.datasetVersion}</strong><span>{run.status} · {run.manifest?.actualVocabSize?.toLocaleString() ?? run.settings.vocabSize?.toLocaleString()} vocabulary</span><small>{new Date(run.createdAt).toLocaleString()}</small></button>)}</div>
      {selected && <section className="card tokenizer-details"><PreparationStatus run={selected} kind="tokenizers" busy={busy} onAction={(...args) => void action(...args)}/>
        {selected.status === "completed" && selected.manifest && <>
          <div className="dataset-stats"><div><strong>{selected.manifest.actualVocabSize?.toLocaleString()}</strong><span>Actual vocabulary / target {selected.settings.vocabSize?.toLocaleString()}</span></div><div><strong>{selected.manifest.trainingDocuments}</strong><span>Training documents</span></div><div><strong>{selected.manifest.trainingTokens?.toLocaleString()}</strong><span>Training content tokens</span></div></div>
          <p className="dataset-caption">Measured BPE fit: {selected.manifest.trainingSeconds?.toFixed(3)}s · {selected.manifest.trainingBytes?.toLocaleString()} training bytes. Use actual vocabulary size when configuring the model.</p>
          <code className="tokenizer-checksum">Tokenizer SHA-256 {selected.manifest.artifacts.tokenizer.sha256}</code>
          <RunDownloads projectId={projectId} kind="tokenizers" run={selected} artifacts={[["tokenizer", "Tokenizer JSON"], ["config", "Tokenizer configuration"], ["special_tokens", "Special tokens"], ["manifest", "Tokenizer manifest"]]}/>
          <TokenizerPlayground key={selected.id} projectId={projectId} runId={selected.id}/>
          <SequencePanel key={"sequence-" + selected.id} projectId={projectId} tokenizer={selected} sources={sources} runs={sequences.filter((run) => run.tokenizerRunId === selected.id)} busy={busy} onCreate={generate} onAction={(...args) => void action(...args)}/>
        </>}
      </section>}
    </> : <section className="empty-card"><Cpu size={34}/><h2>Your tokenizer starts with reviewed text.</h2><p>Select a reviewed version above. No tokenizer or model has been trained yet.</p></section>}
  </div>;
}
