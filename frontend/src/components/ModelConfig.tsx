import { useEffect, useState, type FormEvent } from "react";
import { Cpu, Download } from "lucide-react";
import type { Project } from "../types/project";
import type { PreparationRun, SourceVersion } from "../types/tokenizers";
import { defaultSmokeSettings, type ModelConfig as SavedConfig, type SmokeSettings, type TrainingKind } from "../types/training";
import { listRuns, listSources } from "../services/tokenizers";
import { deleteModelConfig, listModelConfigs, modelConfigExport, saveModelConfig } from "../services/training";

type Draft = { trainingKind: TrainingKind; name: string; sequenceRunId: string; settings: SmokeSettings & { epochs: number; profile: "pilot" | "full" } };
const emptyDraft = (): Draft => ({ trainingKind: "smoke", name: "Tiny GPT-2 smoke test", sequenceRunId: "", settings: { ...defaultSmokeSettings, epochs: 3, profile: "pilot" } });

export function ModelConfig({ project, onSetup, onTokenizer, onTraining, onDirtyChange }: { project: Project | null; onSetup: () => void; onTokenizer: () => void; onTraining: () => void; onDirtyChange: (dirty: boolean) => void }) {
  if (!project?.revision) return <section className="empty-card"><Cpu size={36}/><h2>Save a project first.</h2><button className="primary" onClick={onSetup}>Project setup</button></section>;
  return <ConfigWorkspace key={project.id} projectId={project.id} onTokenizer={onTokenizer} onTraining={onTraining} onDirtyChange={onDirtyChange}/>;
}

function ConfigWorkspace({ projectId, onTokenizer, onTraining, onDirtyChange }: { projectId: string; onTokenizer: () => void; onTraining: () => void; onDirtyChange: (dirty: boolean) => void }) {
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [baseline, setBaseline] = useState<Draft>(emptyDraft);
  const [configs, setConfigs] = useState<SavedConfig[]>([]);
  const [sequences, setSequences] = useState<PreparationRun[]>([]);
  const [tokenizers, setTokenizers] = useState<PreparationRun[]>([]);
  const [sources, setSources] = useState<SourceVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const dirty = JSON.stringify(draft) !== JSON.stringify(baseline);
  useEffect(() => { onDirtyChange(dirty || busy); }, [dirty, busy, onDirtyChange]);
  useEffect(() => () => onDirtyChange(false), [onDirtyChange]);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([listModelConfigs(projectId, controller.signal), listRuns(projectId, "sequence-runs", controller.signal), listRuns(projectId, "tokenizers", controller.signal), listSources(projectId, controller.signal)]).then(([saved, runs, tokens, versions]) => {
      if (controller.signal.aborted) return;
      setConfigs(saved); setSequences(runs); setTokenizers(tokens); setSources(versions);
      const first = runs.find((r) => r.status === "completed" && !!r.manifest?.counts?.train.sequences && versions.some((v) => v.versionId === r.datasetVersionId && v.eligible));
      const initial = saved[0] ? fromSaved(saved[0]) : { ...emptyDraft(), sequenceRunId: first?.id ?? "" };
      setDraft(initial); setBaseline(initial);
    }).catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not load configurations."); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [projectId]);
  function fromSaved(saved: SavedConfig): Draft {
    const settings = { ...defaultSmokeSettings, epochs: saved.configuration.epochs ?? 3, profile: saved.configuration.profile ?? "pilot" };
    for (const key of Object.keys(settings) as (keyof SmokeSettings)[]) if (saved.configuration[key] !== undefined) Object.assign(settings, { [key]: saved.configuration[key] });
    return { trainingKind: saved.trainingKind ?? "smoke", name: saved.name, sequenceRunId: saved.source.sequenceRunId, settings };
  }
  const selected = sequences.find((s) => s.id === draft.sequenceRunId);
  const tokenizer = tokenizers.find((t) => t.id === selected?.tokenizerRunId);
  const vocab = tokenizer?.manifest?.actualVocabSize ?? 0;
  const context = selected?.manifest?.sequenceLength ?? 0;
  const h = draft.settings.hiddenSize;
  const estimate = vocab * h + context * h + draft.settings.layers * (12*h*h+13*h) + 2*h;
  const eligible = (r: PreparationRun) => r.status === "completed" && (draft.trainingKind === "pilot" || r.manifest?.objective !== "sft") && !!r.manifest?.counts?.train.sequences && sources.some((v) => v.versionId === r.datasetVersionId && v.eligible);
  function change<K extends keyof Draft["settings"]>(key: K, value: Draft["settings"][K]) { setDraft((d) => ({ ...d, settings: { ...d.settings, [key]: value } })); }
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try { const saved = await saveModelConfig(projectId, draft); setConfigs((all) => [saved, ...all]); setBaseline(draft); setNotice(`Configuration revision ${saved.revision} saved. Training starts from the Pre-training page.`); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not save configuration."); }
    finally { setBusy(false); }
  }
  async function remove(saved: SavedConfig) {
    if (!window.confirm(`Delete configuration revision ${saved.revision}? Referenced configurations are protected.`)) return;
    setBusy(true); setError("");
    try { await deleteModelConfig(projectId, saved.id); setConfigs((all) => all.filter((c) => c.id !== saved.id)); setNotice("Configuration deleted."); }
    catch (e) { setError(e instanceof Error ? e.message : "Delete failed."); }
    finally { setBusy(false); }
  }
  return <div className="training-page">
    {error && <div className="error-banner" role="alert">{error}</div>}{notice && <p className="notice" role="status">{notice}</p>}
    <section className="card training-form"><span className="eyebrow">RANDOM-WEIGHT CAUSAL MODEL</span><h2>Start small. Verify every connection.</h2><p>Save an immutable configuration tied to reviewed sequences. Choose a fixed-subset smoke check or an epoch-based whole-dataset pilot.</p>
      <form onSubmit={(e) => void save(e)}><fieldset disabled={busy || loading} className="saving-fieldset">
        <div className="training-fields"><label>Training mode<select aria-label="Training mode" value={draft.trainingKind} onChange={(e) => { const mode = e.target.value as TrainingKind; setDraft({ ...draft, trainingKind: mode, name: mode === "pilot" ? "Whole-dataset pilot" : "Tiny GPT-2 smoke test", settings: { ...draft.settings, device: mode === "pilot" ? "cpu" : "auto", profile: "pilot", timeLimitSeconds: 900, maxSteps: mode === "smoke" ? defaultSmokeSettings.maxSteps : draft.settings.maxSteps } }); }}><option value="smoke">Smoke test · up to two blocks</option><option value="pilot">Whole-dataset pilot · all train blocks</option></select></label><label>Configuration name<input required maxLength={100} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })}/></label>
          <label>Completed sequence run<select aria-label="Completed sequence run" required value={draft.sequenceRunId} onChange={(e) => setDraft({ ...draft, sequenceRunId: e.target.value })}><option value="">Choose reviewed training sequences</option>{sequences.map((r) => <option key={r.id} value={r.id} disabled={!eligible(r)}>{r.datasetName} · v{r.datasetVersion} · {r.settings.sequenceLength} tokens · {r.manifest?.objective === "sft" ? "SFT · " : ""}{r.status}{!eligible(r) ? " · unavailable / review permission" : ""}</option>)}</select></label></div>
        {selected && <div className="dataset-stats"><div><strong>{vocab.toLocaleString()}</strong><span>Actual vocabulary · read-only</span></div><div><strong>{context}</strong><span>Context / sequence length · read-only</span></div><div><strong>{selected.manifest?.counts?.train.sequences}</strong><span>{draft.trainingKind === "pilot" ? "Training blocks · uses all" : "Available training sequences · uses up to two"}</span></div></div>}
        <div className="training-fields">
          <label>Layers<select aria-label="Layers" value={draft.settings.layers} onChange={(e) => change("layers", Number(e.target.value))}>{[2,4].map((n) => <option key={n}>{n}</option>)}</select></label>
          <label>Hidden size<select aria-label="Hidden size" value={h} onChange={(e) => change("hiddenSize", Number(e.target.value))}>{[64,128,256].map((n) => <option key={n}>{n}</option>)}</select></label>
          <label>Attention heads<select aria-label="Attention heads" value={draft.settings.heads} onChange={(e) => change("heads", Number(e.target.value))}>{[2,4,8].map((n) => <option key={n}>{n}</option>)}</select></label>
          {draft.trainingKind === "pilot" ? <label>Epochs<input aria-label="Epochs" required type="number" min={1} max={20} step={1} value={Number.isNaN(draft.settings.epochs) ? "" : draft.settings.epochs} onChange={(e) => change("epochs", e.target.valueAsNumber)}/><small>{(selected?.manifest?.counts?.train.sequences ?? 0) * draft.settings.epochs} derived optimizer steps</small></label> : <label>Optimizer steps<input aria-label="Optimizer steps" required type="number" min={50} max={500} step={1} value={Number.isNaN(draft.settings.maxSteps) ? "" : draft.settings.maxSteps} onChange={(e) => change("maxSteps", e.target.valueAsNumber)}/></label>}
          <label>Learning rate<input required type="number" min={0.000001} max={0.01} step="any" value={Number.isNaN(draft.settings.learningRate) ? "" : draft.settings.learningRate} onChange={(e) => change("learningRate", e.target.valueAsNumber)}/></label>
          {draft.trainingKind === "pilot" && <label>Training budget<select value={draft.settings.profile} onChange={(e) => {
            const profile = e.target.value as Draft["settings"]["profile"];
            setDraft((previous) => ({ ...previous, settings: { ...previous.settings, profile, device: "cpu", timeLimitSeconds: 900 } }));
          }}><option value="pilot">Pilot · up to 256 blocks</option><option value="full">Full run · up to 2,048 blocks</option></select></label>}
          <label>Device<select aria-label="Device" disabled={draft.trainingKind === "pilot" && draft.settings.profile === "pilot"} value={draft.settings.device} onChange={(e) => change("device", e.target.value as SmokeSettings["device"])}>{draft.trainingKind === "smoke" && <option value="auto">Auto (verified CUDA or CPU)</option>}<option value="cpu">CPU</option><option value="cuda">CUDA required</option></select></label>
          <label>Random seed<input required type="number" min={0} max={2147483647} step={1} value={Number.isNaN(draft.settings.seed) ? "" : draft.settings.seed} onChange={(e) => change("seed", e.target.valueAsNumber)}/></label>
          <label>Time limit (seconds)<input required type="number" min={60} max={draft.trainingKind === "pilot" && draft.settings.profile === "full" ? 86400 : 900} step={1} value={Number.isNaN(draft.settings.timeLimitSeconds) ? "" : draft.settings.timeLimitSeconds} onChange={(e) => change("timeLimitSeconds", e.target.valueAsNumber)}/></label>
        </div>
        <label>Generation test prompt<textarea aria-label="Generation test prompt" rows={3} maxLength={4096} value={draft.settings.prompt} onChange={(e) => change("prompt", e.target.value)}/></label>
        <p className="dataset-caption">Estimated parameters: {estimate.toLocaleString()} · FP32 · AdamW · batch 1 · no warmup/dropout · PAD 0 / UNK 1 / BOS 2 / EOS 3. Exact count is measured during initialization.</p>
        <div className="training-actions"><button className="primary" type="submit" disabled={!selected || !eligible(selected) || !vocab}>Save new revision</button><button className="secondary" type="button" disabled={!dirty} onClick={() => { setDraft(baseline); setError(""); }}>Discard edits</button>{dirty && <span role="status">Unsaved configuration edits</span>}</div>
      </fieldset></form>
      {!loading && !sequences.some(eligible) && <p>No eligible sequences yet. <button className="text-button" onClick={onTokenizer}>Open tokenizer</button></p>}
    </section>
    <div className="dataset-library-heading"><span>{configs.length} saved configuration revision(s)</span><button className="secondary" disabled={dirty || !configs.length} onClick={onTraining}>Open pre-training</button></div>
    {loading && <p role="status">Loading configurations…</p>}
    {configs.map((saved) => <article key={saved.id} className="card training-config-card"><div><h3>{saved.name} · {saved.trainingKind ?? "smoke"} · revision {saved.revision}</h3><p>{saved.source.datasetName} v{saved.source.datasetVersion} · {saved.configuration.vocabSize.toLocaleString()} vocabulary · {saved.configuration.contextLength} context · {saved.configuration.maxSteps} steps</p></div><div className="training-actions"><button className="secondary" disabled={busy || dirty} onClick={() => { const value = fromSaved(saved); setDraft(value); setBaseline(value); }}>Load settings</button><a className="secondary" href={modelConfigExport(projectId, saved.id)}><Download size={14}/>Export</a><button className="text-button" disabled={busy || dirty} onClick={() => void remove(saved)}>Delete</button></div></article>)}
  </div>;
}
