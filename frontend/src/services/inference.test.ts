import { afterEach, describe, expect, it, vi } from "vitest";
import { inferenceActive } from "../types/inference";
import { annotationExport, deleteInference, inferenceAction, inferenceDownload, inferenceSources, listAnnotations, previewInference, promptSetExport, saveAnnotation, savePromptSet, startEvaluation, startGeneration } from "./inference";
afterEach(() => vi.unstubAllGlobals());
describe("saved-checkpoint inference adapter", () => {
  it("pins generation to a checkpoint and preserves prompt bytes", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    await startGeneration("p", "cp-200", "বাংলা [EOS] e\u0301", 32);
    expect(fetcher.mock.calls[0][0]).toBe("/api/projects/p/generation-runs");
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ checkpointId: "cp-200", prompt: "বাংলা [EOS] e\u0301", maxNewTokens: 32 });
    await previewInference("p", "cp-200", "Hello"); await inferenceSources("p");
    expect(fetcher.mock.calls[1][0]).toBe("/api/projects/p/inference-preview");
  });
  it("snapshots prompt versions and explicit metric scope", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    const body = { checkpointIds: ["cp-50", "cp-200"], promptSetVersionId: "prompts-v2", maxNewTokens: 8, metricScope: "external" as const, externalDatasetVersionId: "reviewed-v3" };
    await startEvaluation("p", body); expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(body);
    await savePromptSet("p", { id: "set", name: "Checks", language: "mixed", prompts: [{ text: "বাংলা", notes: "Human review" }] });
    expect(JSON.parse(fetcher.mock.calls[1][1].body).id).toBe("set");
  });
  it("uses optimistic annotation revisions without echoing server timestamps", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    const body = { checkpointId: "cp", promptIndex: 0, revision: 2, readability: "readable" as const, repetition: "absent" as const, sourceAgreement: "needs-review" as const, notes: "Inspect source", updatedAt: "server timestamp" };
    await saveAnnotation("p", "eval", body); const sent = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(sent.revision).toBe(2); expect(sent).not.toHaveProperty("updatedAt");
    await listAnnotations("p", "eval");
    expect(annotationExport("p", "eval")).toBe("/api/projects/p/evaluation-runs/eval/annotations/export");
  });
  it("keeps lifecycle/downloads scoped and errors actionable", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    await inferenceAction("p", "generation", "r", "cancel"); await inferenceAction("p", "evaluation", "r", "retry"); await deleteInference("p", "evaluation", "r");
    expect(fetcher.mock.calls.map((c) => c[1].method)).toEqual(["POST", "POST", "DELETE"]);
    expect(inferenceDownload("p", "evaluation", "r", "bundle")).toBe("/api/projects/p/evaluation-runs/r/download?artifact=bundle");
    expect(promptSetExport("p", { promptSetId: "set", version: 2 } as Parameters<typeof promptSetExport>[1])).toBe("/api/projects/p/prompt-sets/set/versions/2/export");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "External evaluation overlaps training content." }, { status: 409 })));
    await expect(startGeneration("p", "cp", "Hello", 8)).rejects.toThrow("overlaps training");
    expect(inferenceActive({ status: "loading" })).toBe(true); expect(inferenceActive({ status: "completed" })).toBe(false);
  });
});
