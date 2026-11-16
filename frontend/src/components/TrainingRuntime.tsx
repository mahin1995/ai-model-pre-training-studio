import { useEffect, useState } from "react";
import { trainingRuntime } from "../services/training";
import type { TrainingRuntime as Runtime } from "../types/training";

export function TrainingRuntime({ projectId, onReport }: { projectId: string; onReport?: (report: Runtime) => void }) {
  const [report, setReport] = useState<Runtime | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setReport(null); setError(""); }, [projectId]);
  async function check() {
    setBusy(true); setError("");
    try { const next = await trainingRuntime(projectId, true); setReport(next); onReport?.(next); }
    catch (e) { setError(e instanceof Error ? e.message : "Runtime check failed."); }
    finally { setBusy(false); }
  }
  return <section className="card training-runtime"><div className="card-heading"><div><span className="eyebrow">TRAINING RUNTIME</span><h2>Check the executor.</h2></div><button className="secondary" disabled={busy} onClick={() => void check()}>{busy ? "Checking CPU / CUDA…" : "Check training runtime"}</button></div>
    <p>The isolated training environment runs the model. Backend checks on the Environment page inspect the API interpreter separately.</p>
    {busy && <p role="status">Running import and forward/backward checks. Allow up to 60 seconds.</p>}
    {error && <p className="error-banner" role="alert">{error}</p>}
    {report && <><p role="status"><strong>{report.message}</strong> {report.deviceName && `Device: ${report.deviceName}.`}</p>{report.cudaError && <p className="info-note">{report.cudaError}</p>}
      {!report.ready && <p>{report.action}</p>}<div className="training-versions">{Object.entries(report.versions).map(([name, version]) => <span className="pill" key={name}>{name} {version}</span>)}</div></>}
    <p className="dataset-caption">Setup once: <code>python3 scripts/setup_training.py --profile cpu</code> or <code>--profile cu128</code> for NVIDIA. Checks do not start a training run.</p>
  </section>;
}
