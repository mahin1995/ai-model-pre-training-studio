import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Database,
  Download,
  FileText,
  FolderOpen,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import type { Project } from "../types/project";
import {
  defaultProcessing,
  isActiveJob,
  type Dataset,
  type DatasetDetail,
  type DatasetMetadata,
  type DatasetPreview,
  type ProcessingSettings,
} from "../types/datasets";
import {
  cancelJob,
  deleteDataset,
  downloadUrl,
  getDataset,
  getJob,
  importDataset,
  listDatasets,
  previewDataset,
  startProcessing,
  updateDataset,
} from "../services/datasets";
import { Field } from "./Field";
import { DatasetReview } from "./DatasetReview";
const bytes = (size: number) =>
  size >= 1048576
    ? `${(size / 1048576).toFixed(2)} MiB`
    : `${(size / 1024).toFixed(1)} KiB`;
const message = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "The request failed. Retry after checking the server.";
const emptyMetadata: DatasetMetadata = {
  name: "",
  language: "bn",
  source: "",
  licenseNote: "",
  permission: "unknown",
};
const initialProcessing = (detail: DatasetDetail): ProcessingSettings =>
  detail.latestJob?.settings ??
  (detail.files.length === 1 && detail.files[0].name.toLowerCase().endsWith(".pdf")
    ? { ...defaultProcessing, train: 100, validation: 0, test: 0 }
    : { ...defaultProcessing });
export function Datasets({
  project,
  onSetup,
  onDirtyChange,
}: {
  project: Project | null;
  onSetup: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  if (!project?.revision)
    return (
      <section className="empty-card">
        <Database size={38} />
        <h2>Give your data a project.</h2>
        <p>
          Create and save your project before importing a dataset. You can save
          a partial project draft.
        </p>
        <button className="primary" onClick={onSetup}>
          Go to project setup
          <ArrowRight size={16} />
        </button>
      </section>
    );
  return <DatasetWorkspace key={project.id} projectId={project.id} onDirtyChange={onDirtyChange} />;
}
function DatasetWorkspace({ projectId, onDirtyChange }: { projectId: string; onDirtyChange: (dirty: boolean) => void }) {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selected, setSelected] = useState<DatasetDetail | null>(null);
  const [importing, setImporting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("Overview");
  const [metadata, setMetadata] = useState<DatasetMetadata>(emptyMetadata);
  const [files, setFiles] = useState<File[]>([]);
  const [settings, setSettings] = useState<ProcessingSettings>({
    ...defaultProcessing,
  });
  const [review, setReview] = useState(false);
  const [deleteReview, setDeleteReview] = useState(false);
  const [correctionDirty, setCorrectionDirty] = useState(false);
  const updateReviewDirty = useCallback((dirty: boolean) => { setCorrectionDirty(dirty); onDirtyChange(dirty); }, [onDirtyChange]);
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [versionId, setVersionId] = useState("");
  const [split, setSplit] = useState("processed");
  const [versionSelection, setVersionSelection] = useState("");
  const mounted = useRef(true);
  const selectionSequence = useRef(0);
  const job = selected?.latestJob ?? null;
  const active = isActiveJob(job);
  const selectedId = selected?.id;
  const selectedVersion =
    selected?.versions.find((v) => v.id === versionSelection) ??
    selected?.versions[0];
  async function refresh(signal?: AbortSignal) {
    setLoading(true);
    setError("");
    try {
      const all = await listDatasets(projectId, signal);
      if (!signal?.aborted && mounted.current) setDatasets(all);
    } catch (e) {
      if (!signal?.aborted && mounted.current) setError(message(e));
    } finally {
      if (!signal?.aborted && mounted.current) setLoading(false);
    }
  }
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => {
      mounted.current = false;
      controller.abort();
    };
  }, [projectId]);
  const libraryHasActiveJobs = datasets.some((dataset) =>
    isActiveJob(dataset.latestJob),
  );
  useEffect(() => {
    if (selectedId || importing || !libraryHasActiveJobs) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function pollLibrary() {
      try {
        const all = await listDatasets(projectId, controller.signal);
        if (controller.signal.aborted) return;
        setDatasets(all);
        if (!all.some((dataset) => isActiveJob(dataset.latestJob))) return;
      } catch (e) {
        if (!controller.signal.aborted) setError(message(e));
      }
      if (!controller.signal.aborted)
        timer = setTimeout(() => void pollLibrary(), 2000);
    }
    timer = setTimeout(() => void pollLibrary(), 2000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [projectId, selectedId, importing, libraryHasActiveJobs]);
  // One request at a time, 2 seconds after each result. Cleanup stops both the
  // timer and the outstanding request on navigation/project changes.
  useEffect(() => {
    if (!selectedId || !job || !isActiveJob(job)) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await getJob(
          projectId,
          selectedId,
          job.id,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        if (!isActiveJob(next)) {
          const detail = await getDataset(
            projectId,
            selectedId,
            controller.signal,
          );
          const all = await listDatasets(projectId, controller.signal);
          if (controller.signal.aborted) return;
          setSelected(detail);
          setDatasets(all);
          if (next.status === "completed") {
            setNotice("Processing completed. Your new version is ready.");
            setVersionSelection(detail.versions[0]?.id ?? "");
          }
          return;
        }
        setSelected((current) =>
          current?.id === selectedId
            ? { ...current, latestJob: next, status: next.status }
            : current,
        );
      } catch (e) {
        if (!controller.signal.aborted)
          setError(
            `Could not refresh job status. ${message(e)} Retrying automatically.`,
          );
      }
      if (!controller.signal.aborted)
        timer = setTimeout(() => void poll(), 2000);
    };
    timer = setTimeout(() => void poll(), 2000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [projectId, selectedId, job?.id, active]);
  useEffect(() => {
    if (tab !== "Preview" || !selectedId) return;
    const controller = new AbortController();
    setPreviewLoading(true);
    setPreview(null);
    void previewDataset(
      projectId,
      selectedId,
      page,
      versionId,
      split,
      controller.signal,
    )
      .then((result) => {
        if (!controller.signal.aborted) setPreview(result);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(message(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setPreviewLoading(false);
      });
    return () => controller.abort();
  }, [projectId, selectedId, tab, page, versionId, split]);
  useEffect(() => {
    if (!importing) return;
    const handler = (event: BeforeUnloadEvent) => {
      if (
        files.length ||
        metadata.name ||
        metadata.source ||
        metadata.licenseNote
      ) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [importing, files, metadata]);
  async function selectDataset(id: string) {
    const sequence = ++selectionSequence.current;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const detail = await getDataset(projectId, id);
      if (!mounted.current || sequence !== selectionSequence.current) return;
      setSelected(detail);
      setMetadata({ ...detail.metadata });
      setSettings({ ...initialProcessing(detail) });
      setDeleteReview(false);
      setImporting(false);
      setTab("Overview");
      setReview(false);
      setVersionId("");
      setVersionSelection(detail.versions[0]?.id ?? "");
      setPage(1);
    } catch (e) {
      if (mounted.current) setError(message(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  function back() {
    setDeleteReview(false);
    setSelected(null);
    setImporting(false);
    setError("");
    setNotice("");
    setReview(false);
    void refresh();
  }
  function openImport() {
    setDeleteReview(false);
    setSelected(null);
    setMetadata({ ...emptyMetadata });
    setFiles([]);
    setImporting(true);
    setNotice("");
    setError("");
  }
  async function confirmDelete() {
    if (!selected || busy || active) return;
    const id = selected.id;
    setBusy(true);
    setError("");
    try {
      const result = await deleteDataset(projectId, id);
      if (!mounted.current) return;
      ++selectionSequence.current;
      setDatasets((current) => current.filter((dataset) => dataset.id !== id));
      setSelected(null);
      setDeleteReview(false);
      setPreview(null);
      setReview(false);
      setNotice("Dataset upload deleted.");
      if (result.cleanupWarning) setError(result.cleanupWarning);
    } catch (e) {
      if (mounted.current) setError(message(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  async function submitImport(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!files.length || files.length > 20) {
      setError("Choose between 1 and 20 TXT/JSONL/PDF files.");
      return;
    }
    if (files.reduce((sum, file) => sum + file.size, 0) > 20 * 1048576) {
      setError("Total file size must not exceed 20 MiB.");
      return;
    }
    setBusy(true);
    try {
      const detail = await importDataset(projectId, metadata, files);
      if (!mounted.current) return;
      setSelected(detail);
      setMetadata({ ...detail.metadata });
      setSettings({ ...initialProcessing(detail) });
      setTab("Overview");
      setImporting(false);
      setReview(false);
      setVersionId("");
      setVersionSelection("");
      setPage(1);
      setNotice("Dataset imported. Raw files are preserved.");
      setDatasets(await listDatasets(projectId));
    } catch (e) {
      if (mounted.current) setError(message(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  async function saveMetadata() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const detail = await updateDataset(projectId, selected.id, metadata);
      if (!mounted.current) return;
      setSelected(detail);
      setDatasets(await listDatasets(projectId));
      setNotice(
        "Dataset metadata saved. Existing versions keep their original metadata snapshot.",
      );
    } catch (e) {
      if (mounted.current) setError(message(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  async function process() {
    if (!selected) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const next = await startProcessing(projectId, selected.id, settings);
      if (!mounted.current) return;
      setSelected({ ...selected, latestJob: next, status: next.status });
      setReview(false);
    } catch (e) {
      if (mounted.current) setError(message(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  async function cancel() {
    if (!selected || !job) return;
    setBusy(true);
    setError("");
    try {
      const next = await cancelJob(projectId, selected.id, job.id);
      if (!mounted.current) return;
      setSelected({ ...selected, latestJob: next, status: next.status });
      if (!isActiveJob(next))
        setSelected(await getDataset(projectId, selected.id));
    } catch (e) {
      if (mounted.current) setError(message(e));
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  function changeSettings(patch: Partial<ProcessingSettings>) {
    setSettings((current) => ({ ...current, ...patch }));
    setReview(false);
  }
  const totalRatio = settings.train + settings.validation + settings.test;
  const validSettings =
    Number.isInteger(settings.seed) &&
    settings.seed >= 0 &&
    settings.seed <= 2147483647 &&
    [settings.train, settings.validation, settings.test].every(
      (v) => Number.isInteger(v) && v >= 0 && v <= 100,
    ) &&
    settings.train > 0 &&
    totalRatio === 100;
  const textField = (
    label: string,
    key: keyof Omit<DatasetMetadata, "permission">,
    placeholder = "",
  ) => (
    <Field label={label}>
      {(id) =>
        key === "licenseNote" ? (
          <textarea
            id={id}
            required
            rows={3}
            maxLength={4000}
            value={metadata[key]}
            placeholder={placeholder}
            onChange={(e) =>
              setMetadata({ ...metadata, [key]: e.target.value })
            }
          />
        ) : (
          <input
            id={id}
            required
            maxLength={key === "name" ? 200 : key === "language" ? 80 : 500}
            value={metadata[key]}
            placeholder={placeholder}
            onChange={(e) =>
              setMetadata({ ...metadata, [key]: e.target.value })
            }
          />
        )
      }
    </Field>
  );
  const metadataFields = (
    <>
      {textField("Dataset name", "name", "e.g. Bangla learning sample")}
      <div className="field-grid">
        {textField("Language", "language", "e.g. bn, en or mixed")}
        {textField("Source", "source", "e.g. Public domain books")}
      </div>
      {textField(
        "License / permission note",
        "licenseNote",
        "Record the license or permission basis.",
      )}
      <Field label="Usage permission">
        {(id) => (
          <select
            id={id}
            value={metadata.permission}
            onChange={(e) =>
              setMetadata({
                ...metadata,
                permission: e.target.value as DatasetMetadata["permission"],
              })
            }
          >
            <option value="unknown">Unknown</option>
            <option value="needs-review">Needs review</option>
            <option value="confirmed">Confirmed</option>
          </select>
        )}
      </Field>
    </>
  );
  return (
    <div className="datasets-page">
      {(selected || importing) && (
        <button
          className="text-button dataset-back"
          disabled={busy || correctionDirty}
          onClick={back}
        >
          <ArrowLeft size={15} />
          Dataset library
        </button>
      )}
      {error && (
        <div className="error-banner" role="alert">
          {error}
          <button
            aria-label="Dismiss dataset error"
            onClick={() => setError("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
      <div role="status" aria-live="polite">
        {notice && (
          <div className="notice">
            <Check size={15} />
            {notice}
            <button
              aria-label="Dismiss dataset notification"
              onClick={() => setNotice("")}
            >
              <X size={15} />
            </button>
          </div>
        )}
      </div>
      {importing ? (
        <section className="card dataset-import">
          <div className="form-heading">
            <span className="eyebrow">START WITH A SMALL SAMPLE</span>
            <h2>Bring your text into the studio.</h2>
            <p>
              TXT, JSONL or text-based PDF · up to 20 files · 20 MiB total · 10,000
              documents
            </p>
          </div>
          <form onSubmit={(e) => void submitImport(e)}>
            <fieldset disabled={busy} className="saving-fieldset form-fields">
              {metadataFields}
              <Field
                label="Dataset files"
                hint="TXT: one document per file. JSONL: one text record per line. PDF: one record per text page, up to 1,000 pages; scanned PDFs need OCR first. Maximum 1 MiB per document/record/page."
              >
                {(id) => (
                  <div className="upload-zone">
                    <Upload size={26} />
                    <strong>Choose your TXT / JSONL / PDF files</strong>
                    <input
                      id={id}
                      type="file"
                      accept=".txt,.jsonl,.pdf"
                      multiple
                      required
                      onChange={(e) =>
                        setFiles(Array.from(e.target.files ?? []))
                      }
                    />
                  </div>
                )}
              </Field>
              {files.length > 0 && (
                <ul className="selected-files">
                  {files.map((file, i) => (
                    <li key={i}>
                      <FileText size={15} />
                      <span>{file.name}</span>
                      <small>{bytes(file.size)}</small>
                    </li>
                  ))}
                </ul>
              )}
              <div className="info-note">
                <ShieldCheck size={17} />
                <span>
                  Raw files are preserved. Source permission can be confirmed
                  after import; processing requires confirmed permission.
                </span>
              </div>
              <div className="form-footer">
                <span className="muted">
                  {files.length} file(s) ·{" "}
                  {bytes(files.reduce((sum, f) => sum + f.size, 0))}
                </span>
                <button className="primary" type="submit">
                  {busy ? "Importing…" : "Import dataset"}
                  <Upload size={16} />
                </button>
              </div>
            </fieldset>
          </form>
        </section>
      ) : selected ? (
        <>
          <section className="dataset-detail-heading">
            <div>
              <span className="eyebrow">DATASET WORKSPACE</span>
              <h2>{selected.metadata.name}</h2>
              <p>
                {selected.recordCount.toLocaleString()} raw documents ·{" "}
                {bytes(selected.sizeBytes)} · {selected.metadata.language}
              </p>
            </div>
            <div className="dataset-detail-actions">
              <span className={`dataset-status ${selected.status}`}>
                {selected.status}
              </span>
              <button
                className="secondary dataset-delete-button"
                disabled={busy || active || deleteReview || correctionDirty}
                onClick={() => setDeleteReview(true)}
                title={active ? "Cancel or finish processing before deleting" : "Delete this dataset upload"}
              >
                <Trash2 size={15} />
                Delete upload
              </button>
            </div>
          </section>
          {deleteReview && (
            <section className="card dataset-delete-confirm" aria-labelledby="delete-dataset-title">
              <h3 id="delete-dataset-title">Delete “{selected.metadata.name}”?</h3>
              <p>
                Permanently removes this imported upload, its processing history and {selected.versionCount} saved version(s).
                Your original PDF on your computer and separately imported copies are kept.
              </p>
              <ul>
                {selected.files.map((file) => <li key={file.id}>{file.name}</li>)}
              </ul>
              <p className="dataset-caption">
                Imported {new Date(selected.createdAt).toLocaleString()} · {bytes(selected.sizeBytes)}
              </p>
              <div className="dataset-detail-actions">
                <button className="secondary" disabled={busy} onClick={() => setDeleteReview(false)}>
                  Keep upload
                </button>
                <button className="secondary dataset-delete-button" disabled={busy || active} onClick={() => void confirmDelete()}>
                  <Trash2 size={15} />
                  {busy ? "Deleting…" : "Permanently delete upload"}
                </button>
              </div>
            </section>
          )}
          {job && (
            <section className="card dataset-job">
              <div className="card-heading">
                <div>
                  <strong>
                    {active
                      ? "Preparing your dataset"
                      : job.status === "completed"
                        ? "Version ready"
                        : job.status === "failed"
                          ? "Processing needs attention"
                          : "Processing cancelled"}
                  </strong>
                  <p>
                    Stage: {job.status} · {job.progress}%
                    {job.cancelRequested && active
                      ? " · Cancellation requested"
                      : ""}
                  </p>
                </div>
                {active && (
                  <button
                    className="secondary"
                    disabled={busy || job.cancelRequested}
                    onClick={() => void cancel()}
                  >
                    {job.cancelRequested ? "Cancelling…" : "Cancel processing"}
                  </button>
                )}
              </div>
              <div className="progress-track">
                <div style={{ width: `${job.progress}%` }} />
              </div>
              {job.error && (
                <p className="job-error" role="alert">
                  {job.error}
                </p>
              )}
              {(job.status === "failed" || job.status === "cancelled") && (
                <button
                  className="text-button"
                  onClick={() => {
                    setSettings({ ...job.settings });
                    setReview(false);
                    setTab(job.correctionParentVersionId ? "Review" : "Processing");
                  }}
                >
                  Review settings & retry
                  <ArrowRight size={14} />
                </button>
              )}
            </section>
          )}
          <div
            className="dataset-tabs"
            role="tablist"
            aria-label="Dataset details"
          >
            {["Overview", "Preview", "Review", "Processing", "Splits"].map((name) => (
              <button
                key={name}
                role="tab"
                id={`dataset-tab-${name}`}
                aria-selected={tab === name}
                aria-controls="dataset-panel"
                disabled={busy || correctionDirty}
                onClick={() => {
                  setTab(name);
                  setNotice("");
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    const names = [
                      "Overview",
                      "Preview",
                      "Review",
                      "Processing",
                      "Splits",
                    ];
                    const next =
                      names[
                        (names.indexOf(name) +
                          (e.key === "ArrowRight" ? 1 : names.length - 1)) %
                          names.length
                      ];
                    setTab(next);
                    document.getElementById(`dataset-tab-${next}`)?.focus();
                  }
                }}
                tabIndex={tab === name ? 0 : -1}
              >
                {name === "Review" ? "Review & Correct" : name}
              </button>
            ))}
          </div>
          <section
            id="dataset-panel"
            role="tabpanel"
            aria-labelledby={`dataset-tab-${tab}`}
            className="card dataset-panel"
          >
            {tab === "Review" && <DatasetReview projectId={projectId} dataset={selected} active={active}
              onDirtyChange={updateReviewDirty}
              onQueued={(next) => { setSelected((current) => current ? { ...current, latestJob: next, status: next.status } : current); }} />}
            {tab === "Overview" && (
              <>
                <div className="dataset-stats">
                  <div>
                    <strong>{selected.recordCount.toLocaleString()}</strong>
                    <span>Raw documents</span>
                  </div>
                  <div>
                    <strong>{selected.emptyCount}</strong>
                    <span>Empty texts</span>
                  </div>
                  <div>
                    <strong>{selected.versionCount}</strong>
                    <span>Saved versions</span>
                  </div>
                </div>
                <form
                  className="form-fields"
                  onSubmit={(e) => {
                    e.preventDefault();
                    void saveMetadata();
                  }}
                >
                  <fieldset
                    className="saving-fieldset form-fields"
                    disabled={busy || active}
                  >
                    {metadataFields}
                    <button type="submit" className="secondary metadata-save">
                      Save metadata
                    </button>
                  </fieldset>
                </form>
                <div className="divider-label">ORIGINAL FILES</div>
                <ul className="dataset-file-list">
                  {selected.files.map((file) => (
                    <li key={file.id}>
                      <FileText size={17} />
                      <div>
                        <strong>{file.name}</strong>
                        <small>
                          {file.recordCount} document(s) ·{" "}
                          {bytes(file.sizeBytes)}
                          {file.pageCount !== undefined && ` · ${file.pageCount} PDF pages`}
                        </small>
                        {!!file.skippedPages?.length && (
                          <small role="status">
                            No selectable text on page(s) {file.skippedPages.join(", ")}; skipped. Scanned pages need OCR.
                          </small>
                        )}
                        <code title={file.sha256}>SHA-256 {file.sha256}</code>
                      </div>
                    </li>
                  ))}
                </ul>
                {selected.files.some((file) => file.pageCount !== undefined) && (
                  <p className="dataset-caption">
                    PDF pages stay together in one split to prevent data leakage.
                    A single PDF uses 100% train by default; add independent documents for validation/test splits.
                    Check extracted text in Preview, especially tables and multiple columns.
                  </p>
                )}
                <p className="dataset-caption">
                  Imported {new Date(selected.createdAt).toLocaleString()}.
                  Updated {new Date(selected.updatedAt).toLocaleString()}.
                  Metadata edits apply to future versions; original record
                  provenance remains intact.
                </p>
              </>
            )}
            {tab === "Preview" && (
              <>
                <div className="preview-controls">
                  <Field label="Preview version">
                    {(id) => (
                      <select
                        id={id}
                        value={versionId}
                        onChange={(e) => {
                          setVersionId(e.target.value);
                          setPage(1);
                        }}
                      >
                        <option value="">Raw import</option>
                        {selected.versions.map((v) => (
                          <option key={v.id} value={v.id}>
                            Processed · version {v.version}
                          </option>
                        ))}
                      </select>
                    )}
                  </Field>
                  {versionId && (
                    <Field label="Preview split">
                      {(id) => (
                        <select
                          id={id}
                          value={split}
                          onChange={(e) => {
                            setSplit(e.target.value);
                            setPage(1);
                          }}
                        >
                          {["processed", "train", "validation", "test"].map(
                            (value) => (
                              <option key={value}>{value}</option>
                            ),
                          )}
                        </select>
                      )}
                    </Field>
                  )}
                  <span className="muted">Up to 20 records per page</span>
                </div>
                {previewLoading ? (
                  <p className="dataset-caption" role="status">
                    Loading preview…
                  </p>
                ) : preview ? (
                  <>
                    <div className="record-list">
                      {preview.records.map((record, index) => (
                        <article key={record.id} className="preview-record">
                          <div>
                            <strong>
                              Document {(page - 1) * 20 + index + 1}
                            </strong>
                            <span>
                              {record.language} · {record.source}
                            </span>
                          </div>
                          <pre>{record.text || "(empty text)"}</pre>
                          {record.textTruncated && (
                            <small>
                              Preview truncated to 4,000 characters. Downloads
                              contain the full text.
                            </small>
                          )}
                          <footer>
                            <span>
                              {record.group_id
                                ? `Group: ${record.group_id}`
                                : "Independent document"}
                              {record.duplicateCount
                                ? ` · ${record.duplicateCount} duplicate(s) merged`
                                : ""}
                            </span>
                            <span>
                              {record.provenance[0]?.filename}:
                              {record.provenance[0]?.page !== undefined
                                ? `page ${record.provenance[0].page}`
                                : record.provenance[0]?.line}
                              {record.provenanceCount > 1
                                ? ` · ${record.provenanceCount} provenance entries`
                                : ""}
                            </span>
                          </footer>
                        </article>
                      ))}
                    </div>
                    {preview.records.length === 0 && (
                      <p className="dataset-caption">
                        No records in this split/page.
                      </p>
                    )}
                    <div className="preview-pagination">
                      <button
                        className="secondary"
                        disabled={page <= 1}
                        onClick={() => setPage(page - 1)}
                      >
                        <ChevronLeft size={14} />
                        Previous
                      </button>
                      <span>
                        Page {page} of{" "}
                        {Math.max(1, Math.ceil(preview.total / 20))} ·{" "}
                        {preview.total} documents
                      </span>
                      <button
                        className="secondary"
                        disabled={page * 20 >= preview.total}
                        onClick={() => setPage(page + 1)}
                      >
                        Next
                        <ChevronRight size={14} />
                      </button>
                    </div>
                  </>
                ) : null}
              </>
            )}
            {tab === "Processing" && (
              <>
                <div className="form-heading">
                  <h2>Clean text. Keep the context.</h2>
                  <p>
                    Every successful run creates a new immutable version. Raw
                    files and previous versions stay intact.
                  </p>
                </div>
                {selected.metadata.permission !== "confirmed" && (
                  <div className="info-note">
                    <ShieldCheck size={18} />
                    <span>
                      Confirm usage permission in Overview before starting
                      processing.
                    </span>
                  </div>
                )}
                <fieldset
                  disabled={busy || active}
                  className="saving-fieldset form-fields"
                >
                  <div className="cleaning-options">
                    {(
                      [
                        ["normalizeUnicode", "Unicode NFC normalization"],
                        ["normalizeNewlines", "Normalize line endings"],
                        ["trimWhitespace", "Trim outer whitespace"],
                        ["removeEmpty", "Remove empty text"],
                        ["stripHtml", "Remove HTML, scripts and styles"],
                        ["collapseWhitespace", "Collapse internal whitespace"],
                        ["deduplicate", "Remove exact duplicates"],
                      ] as const
                    ).map(([key, label]) => (
                      <label key={key}>
                        <input
                          type="checkbox"
                          checked={settings[key]}
                          onChange={(e) =>
                            changeSettings({ [key]: e.target.checked })
                          }
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                  <Field
                    label="Split grouping"
                    hint="Explicit group_id values and identical cleaned text always stay together, including when deduplication is disabled."
                  >
                    {(id) => (
                      <select
                        id={id}
                        value={settings.grouping}
                        onChange={(e) =>
                          changeSettings({
                            grouping: e.target.value as "document" | "source",
                          })
                        }
                      >
                        <option value="document">
                          Document groups (default)
                        </option>
                        <option value="source">
                          Keep each source together
                        </option>
                      </select>
                    )}
                  </Field>
                  <div className="split-settings">
                    {(["train", "validation", "test"] as const).map((key) => (
                      <Field
                        key={key}
                        label={`${key[0].toUpperCase() + key.slice(1)} (%)`}
                      >
                        {(id) => (
                          <input
                            id={id}
                            type="number"
                            min={key === "train" ? 1 : 0}
                            max={100}
                            step={1}
                            value={
                              Number.isNaN(settings[key]) ? "" : settings[key]
                            }
                            onChange={(e) =>
                              changeSettings({ [key]: e.target.valueAsNumber })
                            }
                          />
                        )}
                      </Field>
                    ))}
                    <Field label="Random seed">
                      {(id) => (
                        <input
                          id={id}
                          type="number"
                          min={0}
                          max={2147483647}
                          step={1}
                          value={
                            Number.isNaN(settings.seed) ? "" : settings.seed
                          }
                          onChange={(e) =>
                            changeSettings({ seed: e.target.valueAsNumber })
                          }
                        />
                      )}
                    </Field>
                  </div>
                  <p
                    className={
                      !validSettings ? "field-error" : "dataset-caption"
                    }
                  >
                    {validSettings
                      ? "Ratios total 100%. Actual ratios can vary because groups stay intact."
                      : "Use whole-number percentages totaling 100%, positive train percentage, and an integer seed from 0 to 2147483647."}
                  </p>
                  <button
                    className="secondary metadata-save"
                    disabled={
                      !validSettings ||
                      selected.metadata.permission !== "confirmed"
                    }
                    onClick={() => setReview(true)}
                  >
                    Review processing settings
                    <ArrowRight size={15} />
                  </button>
                  {review && (
                    <div className="processing-review">
                      <h3>Review before processing</h3>
                      <p>
                        {selected.recordCount} raw documents ·{" "}
                        {settings.grouping} grouping · seed {settings.seed}
                      </p>
                      <p>
                        Train {settings.train}% / validation{" "}
                        {settings.validation}% / test {settings.test}%
                      </p>
                      <ul>
                        {Object.entries(settings)
                          .filter(([, v]) => typeof v === "boolean")
                          .map(([key, value]) => (
                            <li key={key}>
                              <span>
                                {
                                  (
                                    {
                                      normalizeUnicode: "Unicode NFC",
                                      normalizeNewlines: "Line endings",
                                      trimWhitespace: "Outer whitespace",
                                      removeEmpty: "Empty removal",
                                      stripHtml: "HTML removal",
                                      collapseWhitespace: "Whitespace collapse",
                                      deduplicate: "Exact deduplication",
                                    } as Record<string, string>
                                  )[key]
                                }
                              </span>
                              <strong>{value ? "On" : "Off"}</strong>
                            </li>
                          ))}
                      </ul>
                      <button
                        className="primary"
                        disabled={
                          !validSettings ||
                          selected.metadata.permission !== "confirmed"
                        }
                        onClick={() => void process()}
                      >
                        Start processing
                        <ArrowRight size={16} />
                      </button>
                    </div>
                  )}
                </fieldset>
              </>
            )}
            {tab === "Splits" &&
              (selectedVersion ? (
                <>
                  <div className="preview-controls">
                    <Field label="Saved dataset version">
                      {(id) => (
                        <select
                          id={id}
                          value={selectedVersion.id}
                          onChange={(e) => setVersionSelection(e.target.value)}
                        >
                          {selected.versions.map((v) => (
                            <option key={v.id} value={v.id}>
                              Version {v.version} ·{" "}
                              {new Date(v.createdAt).toLocaleString()}
                            </option>
                          ))}
                        </select>
                      )}
                    </Field>
                    <a
                      className="secondary"
                      href={downloadUrl(
                        projectId,
                        selected.id,
                        selectedVersion.id,
                        "manifest",
                      )}
                    >
                      <Download size={15} />
                      Download manifest
                    </a>
                  </div>
                  <div className="dataset-stats">
                    <div>
                      <strong>{selectedVersion.manifest.counts.output}</strong>
                      <span>Prepared documents</span>
                    </div>
                    <div>
                      <strong>
                        {selectedVersion.manifest.counts.emptyRemoved}
                      </strong>
                      <span>Empty removed</span>
                    </div>
                    <div>
                      <strong>
                        {selectedVersion.manifest.counts.duplicatesRemoved}
                      </strong>
                      <span>Duplicates removed</span>
                    </div>
                  </div>
                  <div className="split-cards">
                    {(["train", "validation", "test"] as const).map((name) => {
                      const artifact = selectedVersion.manifest.splits[name];
                      return (
                        <article key={name}>
                          <span className="eyebrow">{name.toUpperCase()}</span>
                          <h3>{artifact.recordCount} documents</h3>
                          <p>
                            {artifact.groupCount} groups ·{" "}
                            {artifact.actualPercent}% actual /{" "}
                            {artifact.requestedPercent}% requested
                          </p>
                          <small>{bytes(artifact.sizeBytes)}</small>
                          <code>SHA-256 {artifact.sha256}</code>
                          <a
                            className="secondary"
                            href={downloadUrl(
                              projectId,
                              selected.id,
                              selectedVersion.id,
                              name,
                            )}
                          >
                            <Download size={14} />
                            Download {name}
                          </a>
                        </article>
                      );
                    })}
                  </div>
                  <p className="dataset-caption">
                    {selectedVersion.manifest.note}
                  </p>
                  <a
                    className="docs-link"
                    href={downloadUrl(
                      projectId,
                      selected.id,
                      selectedVersion.id,
                      "processed",
                    )}
                  >
                    Download all processed records
                    <Download size={14} />
                  </a>
                  {selectedVersion.manifest.correction && <div className="review-downloads">
                    <p className="dataset-caption">Reviewed correction · {selectedVersion.manifest.correction.reviewedRecords} records reviewed · {selectedVersion.manifest.correction.changedRecords} changed. Continuous text contains training data only.</p>
                    {([['continuous', 'Continuous training text'], ['documents', 'Page-ordered documents'], ['corrections', 'Before/after correction report']] as const).map(([artifact, label]) =>
                      <a className="secondary" key={artifact} href={downloadUrl(projectId, selected.id, selectedVersion.id, artifact)}><Download size={14}/>{label}</a>)}
                  </div>}
                </>
              ) : (
                <div className="dataset-empty">
                  <FolderOpen size={32} />
                  <h2>Your splits will appear here.</h2>
                  <p>
                    Run processing to create your first version, then download
                    its splits and manifest.
                  </p>
                  <button
                    className="secondary"
                    onClick={() => setTab("Processing")}
                  >
                    Configure processing
                    <ArrowRight size={15} />
                  </button>
                </div>
              ))}
          </section>
        </>
      ) : (
        <>
          <section className="card dataset-library-intro">
            <span className="environment-icon">
              <Database size={27} />
            </span>
            <div>
              <h2>Good models start with good data.</h2>
              <p>
                Import a small text sample. Inspect, clean and split it before
                training.
              </p>
            </div>
            <button className="primary" disabled={busy} onClick={openImport}>
              <Plus size={16} />
              Import dataset
            </button>
          </section>
          <div className="dataset-library-heading">
            <span>{datasets.length} dataset(s) in this project</span>
            <button
              className="text-button"
              disabled={loading || busy}
              onClick={() => void refresh()}
            >
              <RefreshCw size={14} />
              Refresh library
            </button>
          </div>
          {loading ? (
            <section className="empty-card" role="status">
              Loading datasets…
            </section>
          ) : datasets.length ? (
            <div className="dataset-library">
              {datasets.map((dataset) => (
                <button
                  className="card dataset-library-card"
                  key={dataset.id}
                  disabled={busy}
                  onClick={() => void selectDataset(dataset.id)}
                >
                  <div className="card-heading">
                    <span className="dataset-card-icon">
                      <FileText size={22} />
                    </span>
                    <span className={`dataset-status ${dataset.status}`}>
                      {dataset.status}
                    </span>
                  </div>
                  <h3>{dataset.metadata.name}</h3>
                  <p>{dataset.metadata.source}</p>
                  <div className="dataset-card-counts">
                    <span>
                      {dataset.recordCount.toLocaleString()} documents
                    </span>
                    <span>{bytes(dataset.sizeBytes)}</span>
                    <span>{dataset.versionCount} version(s)</span>
                  </div>
                  <footer>
                    <span>
                      Updated {new Date(dataset.updatedAt).toLocaleDateString()}
                    </span>
                    <ArrowRight size={16} />
                  </footer>
                </button>
              ))}
            </div>
          ) : (
            <section className="empty-card">
              <Upload size={38} />
              <h2>Your first dataset starts here.</h2>
              <p>
                Import UTF-8 TXT, JSONL or text-based PDF files. Keep the first experiment
                small: up to 20 MiB and 10,000 documents.
              </p>
              <button className="secondary" onClick={openImport}>
                Choose dataset files
                <Upload size={16} />
              </button>
            </section>
          )}
        </>
      )}
    </div>
  );
}
