import { afterEach, describe, expect, it, vi } from "vitest";
import { activeRun } from "../types/tokenizers";
import { cancelPreparation, deletePreparation, encodeText, listSources, preparationDownload, previewSequences, retryPreparation, startSequences, startTokenizer } from "./tokenizers";
afterEach(() => vi.unstubAllGlobals());
describe("tokenizer and sequence adapter", () => {
  it("pins fitting to a dataset version and packing to a saved tokenizer", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({ id: "run" })); vi.stubGlobal("fetch", fetcher);
    await startTokenizer("p", "reviewed-v3", 8000); await startSequences("p", "saved-tokenizer", 512);
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ datasetVersionId: "reviewed-v3", vocabSize: 8000 });
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({ tokenizerRunId: "saved-tokenizer", sequenceLength: 512 });
    await listSources("p"); expect(fetcher.mock.calls[2][0]).toBe("/api/projects/p/tokenizers/sources");
  });
  it("paginates encoding and split previews without changing input text", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    await encodeText("p", "t", "বাংলা [EOS]", 2);
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ text: "বাংলা [EOS]", tokenPage: 2 });
    await previewSequences("p", "s", "validation", 3);
    expect(fetcher.mock.calls[1][0]).toBe("/api/projects/p/sequence-runs/s/preview?split=validation&page=3");
  });
  it("keeps lifecycle actions scoped and exposes actionable failures", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({})); vi.stubGlobal("fetch", fetcher);
    await cancelPreparation("p", "tokenizers", "t"); await retryPreparation("p", "sequence-runs", "s"); await deletePreparation("p", "sequence-runs", "s");
    expect(fetcher.mock.calls.map((call) => call[1].method)).toEqual(["POST", "POST", "DELETE"]);
    expect(preparationDownload("p", "sequence-runs", "s", "bundle")).toBe("/api/projects/p/sequence-runs/s/download?artifact=bundle");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Delete dependent sequence runs first." }, { status: 409 })));
    await expect(deletePreparation("p", "tokenizers", "t")).rejects.toThrow("dependent sequence");
  });
  it("treats native BPE training and packing as active stages", () => {
    expect(activeRun({ status: "training" } as Parameters<typeof activeRun>[0])).toBe(true);
    expect(activeRun({ status: "packing" } as Parameters<typeof activeRun>[0])).toBe(true);
    expect(activeRun({ status: "completed" } as Parameters<typeof activeRun>[0])).toBe(false);
  });
});
