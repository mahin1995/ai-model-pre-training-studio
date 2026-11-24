import { useEffect, useState } from "react";
import { previewSequences } from "../services/tokenizers";
import { activeRun, type PreparationRun, type RunKind, type SequencePreview, type SourceVersion, type SplitName } from "../types/tokenizers";
import { PreparationStatus, RunDownloads } from "./PreparationStatus";

export function SequencePanel({ projectId, tokenizer, sources, runs, busy, onCreate, onAction }: {
  projectId: string; tokenizer: PreparationRun; sources: SourceVersion[]; runs: PreparationRun[]; busy: boolean;
  onCreate: (length: number, datasetVersionId?: string) => Promise<PreparationRun | null>;
  onAction: (action: "cancel" | "retry" | "delete", kind: RunKind, run: PreparationRun) => void;
}) {
  const [datasetVersionId, setDatasetVersionId] = useState("");
  const [length, setLength] = useState(512);
  const [selectedId, setSelectedId] = useState("");
  const [split, setSplit] = useState<SplitName>("train");
  const [page, setPage] = useState(1);
  const [preview, setPreview] = useState<SequencePreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const selected = runs.find((run) => run.id === selectedId) ?? runs[0];
  useEffect(() => {
    setPreview(null); setError("");
    if (selected?.status !== "completed") return;
    const controller = new AbortController(); setLoading(true);
    void previewSequences(projectId, selected.id, split, page, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setPreview(result); })
      .catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not load sequence preview."); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [projectId, selected?.id, selected?.status, split, page]);
  return <section className="sequence-panel"><div className="form-heading"><span className="eyebrow">TRAINING SEQUENCES</span><h3>Build model-ready blocks.</h3><p>Uses this saved tokenizer to encode the selected reviewed dataset. Each document has one BOS/EOS pair; pages stay in order.</p></div>
    <div className="review-tools">
      <label>Reviewed dataset<select value={datasetVersionId} disabled={busy} onChange={(e) => setDatasetVersionId(e.target.value)}>
        <option value="">{tokenizer.datasetName} · v{tokenizer.datasetVersion} (tokenizer source)</option>
        {sources.filter((source) => source.eligible && source.versionId !== tokenizer.datasetVersionId).map((source) =>
          <option key={source.versionId} value={source.versionId}>{source.datasetName} · v{source.version}</option>)}
      </select></label>
      <label>Sequence length<select aria-label="Sequence length" value={length} disabled={busy} onChange={(e) => setLength(Number(e.target.value))}>{[128, 256, 512, 1024].map((value) => <option key={value} value={value}>{value} tokens</option>)}</select></label>
      <button className="primary" disabled={busy || activeRun(tokenizer)} onClick={() => void onCreate(length, datasetVersionId || undefined).then((run) => { if (run) { setSelectedId(run.id); setPage(1); } })}>Generate sequences</button></div>
    <p className="dataset-caption">Non-overlapping blocks · right padding · labels stay unshifted · padding labels = -100. No model is trained here.</p>
    {runs.length > 0 && <><label>Sequence run<select aria-label="Sequence run" value={selected?.id ?? ""} onChange={(e) => { setSelectedId(e.target.value); setPage(1); }}>
      {runs.map((run) => <option key={run.id} value={run.id}>{run.datasetName} · v{run.datasetVersion} · {run.settings.sequenceLength} tokens · {run.status} · {new Date(run.createdAt).toLocaleString()}</option>)}
    </select></label>
      {selected && <PreparationStatus run={selected} kind="sequence-runs" busy={busy} onAction={onAction}/>}
      {selected?.status === "completed" && selected.manifest && <>
        <div className="sequence-counts">{(["train", "validation", "test"] as const).map((name) => { const counts = selected.manifest!.counts![name]; return <article key={name}><span className="eyebrow">{name}</span><strong>{counts.sequences.toLocaleString()} sequences</strong><p>{counts.documents} document(s) · {counts.contentTokens.toLocaleString()} content tokens</p><p>{counts.boundaryTokens} boundary tokens · {counts.paddedTokens.toLocaleString()} padding tokens</p><p>{(counts.paddingRatio * 100).toFixed(1)}% padding</p></article>; })}</div>
        {selected.manifest.warnings?.map((warning) => <p className="info-note" key={warning}>{warning}</p>)}
        <RunDownloads projectId={projectId} kind="sequence-runs" run={selected} artifacts={[["bundle", "Download complete bundle"], ["train", "Train JSONL"], ["validation", "Validation JSONL"], ["test", "Test JSONL"], ["tokens", "Document token streams"], ["manifest", "Sequence manifest"]]}/>
        <div className="preview-controls"><label>Preview split<select aria-label="Sequence preview split" value={split} onChange={(e) => { setSplit(e.target.value as SplitName); setPage(1); }}>{["train", "validation", "test"].map((name) => <option key={name}>{name}</option>)}</select></label></div>
        {loading && <p role="status">Loading sequences…</p>}{error && <div className="error-banner" role="alert">{error}</div>}
        {preview && <>{preview.records.length === 0 && <p className="dataset-caption">No sequences in this split.</p>}
          {preview.records.map((record) => <article className="sequence-record" key={record.documentId + ":" + record.ordinal}>
            <h4>{record.filename} · block {record.ordinal}</h4><p className="dataset-caption">Document token range {record.tokenRange.join("–")} · {record.input_ids.length} positions · {record.pages.filter((value) => value !== null).length} source page reference(s)</p>
            <pre className="tokenizer-decoded" dir="auto">{record.decodedText}</pre>
            {record.decodedText.includes("\ufffd") && <p className="dataset-caption">A byte-level block can start/end inside a character. Full-document token streams preserve the exact text.</p>}
            {([['input_ids', 'Input IDs'], ['attention_mask', 'Attention mask'], ['labels', 'Training labels']] as const).map(([key, label]) => <details key={key}><summary>{label} ({record[key].length})</summary><pre>{JSON.stringify(record[key])}</pre></details>)}
          </article>)}
          <div className="preview-pagination"><button className="secondary" disabled={loading || page <= 1} onClick={() => setPage(page - 1)}>Previous sequences</button><span>Page {page} of {Math.max(1, Math.ceil(preview.total / 5))}</span><button className="secondary" disabled={loading || page * 5 >= preview.total} onClick={() => setPage(page + 1)}>Next sequences</button></div>
        </>}
      </>}
    </>}
  </section>;
}
