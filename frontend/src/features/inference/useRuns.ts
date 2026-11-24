import { useCallback, useEffect, useState } from "react";
import { deleteInference, inferenceAction, inferenceSources, listInferenceRuns } from "../../services/inference";
import { inferenceActive, type InferenceKind, type InferenceRun, type InferenceSource } from "../../types/inference";

export function useRuns(project: string, kind: InferenceKind) {
  const [sources, setSources] = useState<InferenceSource[]>([]);
  const [runs, setRuns] = useState<InferenceRun[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const selected = runs.find((r) => r.id === selectedId) ?? runs[0];
  const active = runs.some(inferenceActive);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const [nextSources, nextRuns] = await Promise.all([inferenceSources(project, signal), listInferenceRuns(project, kind, signal)]);
    if (signal?.aborted) return;
    setSources(nextSources); setRuns(nextRuns);
  }, [project, kind]);
  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal).catch((e: unknown) => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not load inference history."); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [refresh]);
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try { await refresh(controller.signal); } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Polling failed; retrying."); }
      if (!controller.signal.aborted) timer = setTimeout(() => void poll(), (kind === "generation" ? 500 : 1500));
    }
    timer = setTimeout(() => void poll(), (kind === "generation" ? 500 : 1500));
    return () => { controller.abort(); clearTimeout(timer); };
  }, [active, kind, refresh]);
  async function action(command: "cancel" | "retry" | "delete", run: InferenceRun) {
    if (command === "delete" && !window.confirm("Delete this inference run and its results? Original models and datasets remain saved.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      if (command === "delete") { const result = await deleteInference(project, kind, run.id); setNotice(result.cleanupWarning ?? "Run deleted."); }
      else { const next = await inferenceAction(project, kind, run.id, command); if (command === "retry") setSelectedId(next.id); setNotice(command === "cancel" ? "Cancellation requested." : "New run queued with the same saved settings."); }
      await refresh();
    } catch (e) { setError(e instanceof Error ? e.message : "Run action failed."); }
    finally { setBusy(false); }
  }
  async function start(operation: () => Promise<InferenceRun>) {
    setBusy(true); setError(""); setNotice("");
    try { const run = await operation(); setRuns((all) => [run, ...all]); setSelectedId(run.id); setNotice("Run created. Track its status below; saved weights and tokenizer are unchanged."); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not start inference."); }
    finally { setBusy(false); }
  }
  return { sources, runs, selected, setSelectedId, loading, busy, setBusy, error, setError, notice, setNotice, refresh, action, start };
}
