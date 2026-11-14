import { Download, RefreshCw, Square, Trash2 } from "lucide-react";
import { activeRun, type PreparationRun, type RunKind } from "../types/tokenizers";
import { preparationDownload } from "../services/tokenizers";

export function PreparationStatus({ run, kind, busy, onAction }: { run: PreparationRun; kind: RunKind; busy: boolean; onAction: (action: "cancel" | "retry" | "delete", kind: RunKind, run: PreparationRun) => void }) {
  return <div className="preparation-status">
    <div className="card-heading"><div><span className={`dataset-status ${run.status}`}>{run.status}</span><p className="dataset-caption">{run.datasetName} · Version {run.datasetVersion} · {run.elapsedSeconds.toFixed(1)}s elapsed · {new Date(run.createdAt).toLocaleString()}</p></div>
      <div className="review-tools">
        {activeRun(run) ? <button className="secondary" disabled={busy || run.cancelRequested} onClick={() => onAction("cancel", kind, run)}><Square size={13}/>{run.cancelRequested ? "Cancellation requested" : "Cancel run"}</button> : <>
          {["failed", "cancelled"].includes(run.status) && <button className="secondary" disabled={busy} onClick={() => onAction("retry", kind, run)}><RefreshCw size={14}/>Retry as new run</button>}
          <button className="text-button dataset-delete-button" disabled={busy} onClick={() => onAction("delete", kind, run)}><Trash2 size={14}/>Delete run</button>
        </>}
      </div></div>
    {activeRun(run) && <p className="preparation-live" role="status"><span className="status-dot"/> {run.status === "training" ? "Learning BPE merge rules on CPU. Merge progress is not reported by the trainer." : run.status === "queued" ? "Waiting for the local preparation worker." : `Current stage: ${run.status}.`} Updates every two seconds.</p>}
    {run.error && <div className="error-banner" role="alert">{run.error}</div>}
  </div>;
}

export function RunDownloads({ projectId, run, kind, artifacts }: { projectId: string; run: PreparationRun; kind: RunKind; artifacts: [string, string][] }) {
  return <div className="review-downloads">{artifacts.map(([key, label]) => run.manifest?.artifacts[key] && <a className="secondary" key={key} href={preparationDownload(projectId, kind, run.id, key)}><Download size={14}/>{label}</a>)}</div>;
}
