import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  Cpu,
  ExternalLink,
  RefreshCw,
  Server,
  Terminal,
  XCircle,
} from "lucide-react";
import { request } from "../services/api";
import type { EnvironmentReport } from "../types/environment";
import type { Project } from "../types/project";
export function Environment({
  project,
  onApply,
  onSetup,
}: {
  project: Project | null;
  onApply: (hardware: Project["hardware"]) => void;
  onSetup: () => void;
}) {
  const [report, setReport] = useState<EnvironmentReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [applied, setApplied] = useState(false);
  const controller = useRef<AbortController | null>(null);
  async function run() {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    const timeout = window.setTimeout(() => current.abort("timeout"), 32000);
    setBusy(true);
    setError("");
    setApplied(false);
    try {
      const next = await request<EnvironmentReport>("/environment", {
        signal: current.signal,
      });
      if (!current.signal.aborted) setReport(next);
    } catch (e) {
      if (current.signal.reason !== "unmount")
        setError(
          current.signal.aborted
            ? "Environment check timed out. Retry or inspect the backend environment."
            : e instanceof Error
              ? e.message
              : "Environment checks failed.",
        );
    } finally {
      clearTimeout(timeout);
      if (controller.current === current && current.signal.reason !== "unmount")
        setBusy(false);
    }
  }
  useEffect(() => () => controller.current?.abort("unmount"), []);
  const counts = report?.checks.reduce(
    (acc, check) => {
      acc[check.status] += 1;
      return acc;
    },
    { pass: 0, warning: 0, blocked: 0, error: 0 },
  );
  const applyAvailable = !!(
    report?.gpus.length &&
    report.memory &&
    report.disk
  );
  return (
    <div className="environment-page">
      <section className="environment-intro card">
        <span className="environment-icon">
          <Terminal size={27} />
        </span>
        <div>
          <h2>Check your training environment.</h2>
          <p>
            Inspect the machine running the Python backend. Checks are read-only
            and do not install packages or change your project.
          </p>
        </div>
        <button className="primary" disabled={busy} onClick={() => void run()}>
          <RefreshCw size={16} className={busy ? "spin" : ""} />
          {busy
            ? "Checking…"
            : report
              ? "Run checks again"
              : "Run environment checks"}
        </button>
      </section>
      <div className="info-note">
        <Server size={18} />
        <span>
          {project?.hardware.location === "cloud"
            ? "Your project targets cloud training. These results describe the backend host, which may be your local machine; they do not inspect a remote cloud GPU."
            : "Results describe the backend host, not the browser device."}{" "}
          Hardware detection does not verify model capacity or replace a
          training smoke test.
        </span>
      </div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
          {report && " The previous results below have not been refreshed."}
        </div>
      )}
      <div role="status" aria-live="polite">
        {busy && (
          <p className="environment-loading">
            Checking Python, PyTorch and host resources… This can take up to 30
            seconds.
          </p>
        )}
        {applied && (
          <div className="notice">
            <Check size={16} />
            Detected hardware was copied to your project draft. Review it and
            save the project.
          </div>
        )}
      </div>
      {!report && !busy && !error && (
        <section className="empty-card">
          <Cpu size={38} />
          <h2>See what’s ready. Find what’s missing.</h2>
          <p>
            Check Python, PyTorch, CUDA access, NVIDIA drivers, training
            libraries, system RAM and available disk space.
          </p>
          <span className="pill">NO TRAINING WILL START</span>
        </section>
      )}
      {report && (
        <>
          <div className="environment-summary">
            <div>
              <span className="eyebrow">LATEST CHECK</span>
              <h2>
                {report.status === "checks-passed"
                  ? "Environment checks passed."
                  : "A few things need attention."}
              </h2>
              <p>
                {new Date(report.checkedAt).toLocaleString()} · {report.host}
              </p>
            </div>
            <div className="environment-counts">
              <span className="check-badge pass">{counts!.pass} passed</span>
              <span className="check-badge warning">
                {counts!.warning} warnings
              </span>
              <span className="check-badge blocked">
                {counts!.blocked + counts!.error} blocked / errors
              </span>
            </div>
          </div>
          <div className="environment-check-grid">
            {report.checks.map((check) => (
              <article className="card environment-check" key={check.id}>
                <div className="card-heading">
                  <h3>{check.title}</h3>
                  <span className={`check-badge ${check.status}`}>
                    {check.status === "pass" ? (
                      <Check size={12} />
                    ) : check.status === "warning" ? (
                      <AlertTriangle size={12} />
                    ) : (
                      <XCircle size={12} />
                    )}{" "}
                    {check.status}
                  </span>
                </div>
                <strong className="environment-value">{check.value}</strong>
                <p>{check.detail}</p>
                {check.action && (
                  <div className="check-action">
                    <ArrowRight size={14} />
                    <span>{check.action}</span>
                  </div>
                )}
              </article>
            ))}
          </div>
          <div className="environment-details">
            <section className="card">
              <h3>Host & detected GPUs</h3>
              <dl>
                <div>
                  <dt>Platform</dt>
                  <dd>{report.platform}</dd>
                </div>
                <div>
                  <dt>Python</dt>
                  <dd>{report.pythonExecutable}</dd>
                </div>
                <div>
                  <dt>Disk path</dt>
                  <dd>{report.disk?.path || "Unavailable"}</dd>
                </div>
              </dl>
              {(report.gpus.length ? report.gpus : report.driverGpus).map(
                (gpu, i) => (
                  <div className="gpu-row" key={i}>
                    <Cpu size={18} />
                    <span>
                      <strong>{gpu.name}</strong>
                      <small>
                        {gpu.vramGb} GB VRAM ·{" "}
                        {report.gpus.length
                          ? "Visible to PyTorch"
                          : "Driver-reported; PyTorch access not verified"}
                      </small>
                    </span>
                  </div>
                ),
              )}
              {!report.gpus.length && !report.driverGpus.length && (
                <p>No NVIDIA/CUDA GPUs detected by these checks.</p>
              )}
            </section>
            <section className="card">
              <h3>Training packages</h3>
              <ul className="package-list">
                {report.packages.map((pkg) => (
                  <li key={pkg.name}>
                    <span>
                      {pkg.name}
                      <small>{pkg.required ? "Core" : "Optional"}</small>
                    </span>
                    <strong>{pkg.version || "Not installed"}</strong>
                  </li>
                ))}
              </ul>
              <a
                className="docs-link"
                href="https://pytorch.org/get-started/locally/"
                target="_blank"
                rel="noreferrer"
              >
                Official PyTorch installation guide
                <ExternalLink size={13} />
              </a>
            </section>
          </div>
          <section className="card apply-hardware">
            <div>
              <h3>Use detected hardware in your project</h3>
              <p>
                {!project
                  ? "Create a project first to record detected hardware."
                  : project.hardware.location === "cloud"
                    ? "Automatic copying is disabled for cloud projects: this check only describes the backend host."
                    : "Copy verified GPU visibility, total RAM and current free disk to the local project draft. Existing hardware values will be replaced; save after review."}
              </p>
            </div>
            {!project ? (
              <button className="secondary" onClick={onSetup}>
                Project setup
                <ArrowRight size={15} />
              </button>
            ) : (
              <button
                className="secondary"
                disabled={
                  !applyAvailable ||
                  project.hardware.location === "cloud" ||
                  busy
                }
                onClick={() => {
                  if (!report.memory || !report.disk || !report.gpus.length)
                    return;
                  onApply({
                    location: "local",
                    status: "entered",
                    gpuModel: report.gpus.map((g) => g.name).join(", "),
                    gpuCount: report.gpus.length,
                    vramPerGpuGb: Math.min(...report.gpus.map((g) => g.vramGb)),
                    ramGb: report.memory.totalGb,
                    freeDiskGb: report.disk.freeGb,
                  });
                  setApplied(true);
                }}
              >
                Copy to project draft
                <ArrowRight size={15} />
              </button>
            )}
          </section>
        </>
      )}
    </div>
  );
}
