import { useEffect, useRef, useState } from "react";
import { Check, ChevronLeft, ChevronRight, RefreshCw, Save } from "lucide-react";
import type { CorrectionPage, DatasetDetail, DatasetJob } from "../types/datasets";
import { getCorrectionPage, publishCorrections, saveCorrection } from "../services/datasets";
import { applySuggestion, cleanReviewText, reviewSuggestions } from "../features/dataset-review/text";

export function DatasetReview({ projectId, dataset, active, onQueued, onDirtyChange }: {
  projectId: string; dataset: DatasetDetail; active: boolean;
  onQueued: (job: DatasetJob) => void; onDirtyChange: (dirty: boolean) => void;
}) {
  const [versionId, setVersionId] = useState(
    ["failed", "cancelled"].includes(dataset.latestJob?.status ?? "")
      ? dataset.latestJob?.correctionParentVersionId ?? dataset.versions[0]?.id ?? ""
      : dataset.versions[0]?.id ?? "");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CorrectionPage | null>(null);
  const [text, setText] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reload, setReload] = useState(0);
  const [publishReview, setPublishReview] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const mounted = useRef(true);
  const dirty = !!data && (text !== data.text || reviewed !== data.reviewed);
  const blocked = active || saving || loading;
  const selected = dataset.versions.find((v) => v.id === versionId);
  const suggestions = reviewSuggestions(text);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; onDirtyChange(false); }; }, [onDirtyChange]);
  useEffect(() => { onDirtyChange(dirty || saving); }, [dirty, saving, onDirtyChange]);
  useEffect(() => {
    if (!versionId) return;
    const controller = new AbortController();
    setLoading(true); setError(""); setData(null); setImageFailed(false); setPublishReview(false);
    void getCorrectionPage(projectId, dataset.id, versionId, page, controller.signal).then((result) => {
      if (!controller.signal.aborted) { setData(result); setText(result.text); setReviewed(result.reviewed); }
    }).catch((e: unknown) => {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not load the draft.");
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [projectId, dataset.id, versionId, page, reload]);
  useEffect(() => {
    const prevent = (event: BeforeUnloadEvent) => { if (dirty || saving) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [dirty, saving]);
  function edit(next: string) { setText(next); setReviewed(false); setPublishReview(false); setNotice(""); }
  async function save(markReviewed = reviewed, nextPage?: number) {
    if (!data || blocked) return;
    setSaving(true); setError(""); setPublishReview(false);
    try {
      const result = await saveCorrection(projectId, dataset.id, versionId,
        { recordId: data.record.id, text, reviewed: markReviewed, revision: data.revision });
      if (!mounted.current) return;
      setData({ ...data, ...result, text, reviewed: markReviewed });
      setReviewed(markReviewed);
      setNotice(markReviewed ? "Page reviewed and saved." : "Draft saved. This page still needs review.");
      if (nextPage !== undefined) setPage(nextPage);
    } catch (e) {
      if (mounted.current) setError(e instanceof Error ? e.message : "Draft could not be saved.");
    } finally { if (mounted.current) setSaving(false); }
  }
  function go(next: number) {
    if (blocked || !data) return;
    if (dirty) void save(reviewed, next); else setPage(next);
  }
  async function publish() {
    if (!data || blocked || dirty) return;
    setSaving(true); setError("");
    try {
      const job = await publishCorrections(projectId, dataset.id, versionId, data.revision);
      if (!mounted.current) return;
      setPublishReview(false); setNotice("Publishing corrected version. Follow progress above; the parent version is preserved."); onQueued(job);
    } catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : "Could not publish the draft."); }
    finally { if (mounted.current) setSaving(false); }
  }
  if (!dataset.versions.length) return <div className="dataset-empty"><h2>Prepare a version first.</h2><p>Run Processing, then review and correct the saved text here.</p></div>;
  const source = data?.record.provenance[0];
  return <div className="dataset-review">
    <div className="form-heading"><span className="eyebrow">REVIEW & CORRECT</span><h2>Read the source. Refine the text.</h2>
      <p>Drafts are saved separately. Publishing creates a new version with the same records, page references and splits.</p></div>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {notice && <p className="notice" role="status">{notice}</p>}
    <div className="review-toolbar">
      <label>Parent version<select aria-label="Parent version" value={versionId} disabled={blocked || dirty} onChange={(e) => { setVersionId(e.target.value); setPage(1); setNotice(""); }}>
        {dataset.versions.map((v) => <option key={v.id} value={v.id}>Version {v.version} · {new Date(v.createdAt).toLocaleString()}</option>)}
      </select></label>
      <button className="secondary" disabled={blocked || dirty} onClick={() => setReload((v) => v + 1)}><RefreshCw size={14}/> Reload saved draft</button>
      {dirty && <span className="review-unsaved" role="status">Unsaved edits — save or undo before leaving.</span>}
    </div>
    {loading && <p role="status">Loading full page text…</p>}
    {data && <>
      <div className="dataset-stats"><div><strong>{data.summary.reviewed}/{data.summary.total}</strong><span>Records reviewed</span></div>
        <div><strong>{data.summary.changed}</strong><span>Saved corrections</span></div><div><strong>{data.revision}</strong><span>Draft revision</span></div></div>
      <div className="preview-pagination review-pagination">
        <button className="secondary" disabled={blocked || page <= 1} onClick={() => go(page - 1)}><ChevronLeft size={14}/> Previous</button>
        <label>Record <select aria-label="Review record" value={page} disabled={blocked} onChange={(e) => go(Number(e.target.value))}>
          {Array.from({ length: data.summary.total }, (_, index) => <option key={index} value={index + 1}>{index + 1}</option>)}
        </select> of {data.summary.total}</label>
        <button className="secondary" disabled={blocked || page >= data.summary.total} onClick={() => go(page + 1)}>Next <ChevronRight size={14}/></button>
      </div>
      <p className="dataset-caption">{source?.filename} · {source?.page ? `PDF page ${source.page}` : `record ${source?.line}`} · Full text editor</p>
      <div className="review-comparison">
        <section className="review-source"><h3>Original PDF page</h3>
          {data.sourceImageUrl && !imageFailed ? <a href={data.sourceImageUrl} target="_blank" rel="noreferrer" title="Open full source page"><img src={data.sourceImageUrl} alt={`${source?.filename}, page ${source?.page}`} onError={() => setImageFailed(true)}/></a>
            : <p className="info-note">{imageFailed ? "Source image unavailable. Check the original PDF before marking this record reviewed." : "No PDF image for this record. Compare the parent text below with your source."}</p>}
        </section>
        <section className="review-editor"><label htmlFor="corrected-text">Corrected text</label>
          <p className="dataset-caption">Keep numbers, clause references and paragraph order. Use labeled lines for tables, e.g. Requirement / Clause / Meaning.</p>
          <textarea id="corrected-text" value={text} disabled={blocked} onChange={(e) => edit(e.target.value)} spellCheck={false} dir="auto"/>
          <div className="review-tools"><button className="text-button" disabled={blocked || cleanReviewText(text) === text} onClick={() => edit(cleanReviewText(text))}>Normalize spacing / remove invisible U+200B</button>
            <span>{new TextEncoder().encode(text).length.toLocaleString()} bytes · max 1 MiB</span></div>
          {!!suggestions.length && <div className="review-suggestions"><strong>Suggestions — compare with the PDF before applying</strong>
            {suggestions.map((s) => <button className="secondary" key={s.before} disabled={blocked} onClick={() => edit(applySuggestion(text, s.before, s.after))}>{s.before} → {s.after} ({s.count})</button>)}
          </div>}
          <details className="review-before"><summary>Before: saved Version {selected?.version} text {text !== data.record.text ? "· edited" : "· unchanged"}</summary><pre dir="auto">{data.record.text}</pre></details>
          <label className="review-check"><input type="checkbox" checked={reviewed} disabled={blocked} onChange={(e) => { setReviewed(e.target.checked); setPublishReview(false); }}/> I checked this record against its source; no unresolved issues remain.</label>
          <div className="review-tools"><button className="secondary" disabled={blocked || !dirty || !text.trim()} onClick={() => void save()}><Save size={14}/> Save draft</button>
            <button className="text-button" disabled={blocked || !dirty} onClick={() => { setText(data.text); setReviewed(data.reviewed); setError(""); }}>Undo unsaved edits</button>
            <button className="primary" disabled={blocked || !text.trim()} onClick={() => void save(true, page < data.summary.total ? page + 1 : undefined)}><Check size={14}/> Mark reviewed{page < data.summary.total ? " & next" : " & save"}</button></div>
          <p className="dataset-caption">{data.updatedAt ? `Draft saved ${new Date(data.updatedAt).toLocaleString()}.` : "No draft saved yet."} Changing text resets its review status.</p>
        </section>
      </div>
      <section className="review-publish"><h3>Create a corrected version</h3>
        <p>{data.summary.reviewed}/{data.summary.total} records reviewed · {data.summary.changed} records changed. Split percentages and source-page references stay unchanged.</p>
        <button className="secondary" disabled={blocked || dirty || data.summary.reviewed !== data.summary.total} onClick={() => setPublishReview(true)}>Review publication</button>
        {data.summary.reviewed !== data.summary.total && <p className="dataset-caption">Review and save every record to enable publication.</p>}
        {publishReview && <div className="processing-review"><h3>Publish corrections from Version {selected?.version}?</h3>
          <p>You have reviewed all {data.summary.total} records. {data.summary.changed} records differ from the parent. A new version will include corrected splits, page-ordered documents, training-only continuous text and a before/after report.</p>
          <div className="review-tools"><button className="secondary" disabled={blocked} onClick={() => setPublishReview(false)}>Keep reviewing</button>
            <button className="primary" disabled={blocked || dirty} onClick={() => void publish()}>{saving ? "Starting…" : "Create new corrected version"}</button></div>
        </div>}
      </section>
    </>}
  </div>;
}
