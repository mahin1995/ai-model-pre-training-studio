import { afterEach, describe, expect, it, vi } from "vitest";
import { defaultSmokeSettings, smokeActive } from "../types/training";
import { checkpointDownload, deleteModelConfig, deleteSmoke, listModelConfigs, modelConfigExport, saveModelConfig, smokeAction, smokeDownload, smokeMetrics, startSmoke, trainingRuntime } from "./training";
afterEach(() => vi.unstubAllGlobals());
describe("model and smoke-training API", () => {
  it("saves source references and settings without inventing vocabulary/context", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    const draft = { name: "Tiny", sequenceRunId: "sequence-v3", settings: defaultSmokeSettings };
    await saveModelConfig("p", draft);
    expect(fetcher.mock.calls[0][0]).toBe("/api/projects/p/model-configs");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(draft);
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).not.toHaveProperty("vocabSize");
    await listModelConfigs("p"); await deleteModelConfig("p", "c");
    expect(modelConfigExport("p", "c")).toBe("/api/projects/p/model-configs/c/export");
  });
  it("pins training and resume to saved config/checkpoint IDs", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    await startSmoke("p", "config-1"); await smokeAction("p", "run-1", "resume", "checkpoint-50");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ modelConfigId: "config-1" });
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ checkpointId: "checkpoint-50" });
    await smokeAction("p", "run-1", "cancel"); await smokeAction("p", "run-1", "retry"); await deleteSmoke("p", "run-1");
    expect(fetcher.mock.calls.at(-1)?.[1].method).toBe("DELETE");
  });
  it("scopes runtime, incremental metrics and artifact downloads", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    await trainingRuntime("p", true); await smokeMetrics("p", "r", 50);
    expect(fetcher.mock.calls[0][0]).toBe("/api/projects/p/training-runtime?refresh=true");
    expect(fetcher.mock.calls[1][0]).toBe("/api/projects/p/smoke-runs/r/metrics?afterStep=50");
    expect(smokeDownload("p", "r", "bundle")).toBe("/api/projects/p/smoke-runs/r/download?artifact=bundle");
    expect(checkpointDownload("p", "r", "c")).toBe("/api/projects/p/smoke-runs/r/checkpoints/c/download");
  });
  it("retains actionable failures and marks numerical stages active", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Training runtime is missing." }, { status: 409 })));
    await expect(startSmoke("p", "c")).rejects.toThrow("runtime is missing");
    expect(smokeActive({ status: "initializing" })).toBe(true);
    expect(smokeActive({ status: "verifying" })).toBe(true);
    expect(smokeActive({ status: "completed" })).toBe(false);
  });
});
