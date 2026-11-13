import { afterEach, describe, expect, it, vi } from "vitest";
import {
  importDataset,
  previewDataset,
  startProcessing,
  cancelJob,
  downloadUrl,
  deleteDataset,
  getCorrectionPage,
  saveCorrection,
  publishCorrections,
} from "./datasets";
import { defaultProcessing } from "../types/datasets";
afterEach(() => vi.unstubAllGlobals());
describe("dataset API adapter", () => {
  it("keeps correction edits and publication scoped to a parent version and draft revision", async () => {
    const fetcher = vi.fn().mockImplementation(async () => Response.json({ revision: 7 }));
    vi.stubGlobal("fetch", fetcher);
    await getCorrectionPage("p", "d", "v1", 3);
    expect(fetcher.mock.calls[0][0]).toBe("/api/projects/p/datasets/d/versions/v1/corrections?page=3");
    const edit = { recordId: "f:3", text: "বাংলা সংশোধন", reviewed: true, revision: 6 };
    await saveCorrection("p", "d", "v1", edit);
    expect(fetcher.mock.calls[1][1].method).toBe("PUT");
    expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual(edit);
    await publishCorrections("p", "d", "v1", 7);
    expect(fetcher.mock.calls[2][0]).toBe("/api/projects/p/datasets/d/versions/v1/corrections/publish");
    expect(JSON.parse(fetcher.mock.calls[2][1].body)).toEqual({ revision: 7 });
  });
  it("deletes only the selected dataset under its project", async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({ id: "duplicate", deleted: true, cleanupWarning: null }));
    vi.stubGlobal("fetch", fetcher);
    await expect(deleteDataset("project", "duplicate")).resolves.toEqual({ id: "duplicate", deleted: true, cleanupWarning: null });
    expect(fetcher.mock.calls[0][0]).toBe("/api/projects/project/datasets/duplicate");
    expect(fetcher.mock.calls[0][1].method).toBe("DELETE");
  });
  it("surfaces a blocked deletion instead of reporting success", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json({ detail: "Cancel or finish dataset processing before deleting this upload." }, { status: 409 })));
    await expect(deleteDataset("project", "duplicate")).rejects.toThrow("Cancel or finish");
  });
  it("uploads multipart files without forcing a JSON Content-Type", async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({ id: "dataset" }));
    vi.stubGlobal("fetch", fetcher);
    const metadata = {
      name: "Bangla",
      language: "bn",
      source: "Books",
      licenseNote: "Public domain",
      permission: "confirmed" as const,
    };
    const file = new File(["বাংলা"], "sample.txt", { type: "text/plain" });
    await importDataset("project", metadata, [file]);
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe("/api/projects/project/datasets");
    expect(init.body).toBeInstanceOf(FormData);
    expect(JSON.parse(init.body.get("metadata"))).toEqual(metadata);
    expect(init.body.getAll("files")[0].name).toBe("sample.txt");
    expect(init.headers.has("Content-Type")).toBe(false);
  });
  it("preserves JSON headers and settings for processing and cancellation", async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ id: "job" }))
      .mockResolvedValueOnce(Response.json({ id: "job" }));
    vi.stubGlobal("fetch", fetcher);
    await startProcessing("p", "d", defaultProcessing);
    await cancelJob("p", "d", "j");
    expect(fetcher.mock.calls[0][1].headers.get("Content-Type")).toBe(
      "application/json",
    );
    expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual(
      defaultProcessing,
    );
    expect(fetcher.mock.calls[1][0]).toBe(
      "/api/projects/p/datasets/d/jobs/j/cancel",
    );
  });
  it("scopes processed preview and download URLs to the selected project and version", async () => {
    const fetcher = vi.fn().mockResolvedValue(Response.json({ records: [] }));
    vi.stubGlobal("fetch", fetcher);
    const controller = new AbortController();
    await previewDataset("p", "d", 2, "v", "train", controller.signal);
    expect(fetcher.mock.calls[0][0]).toBe(
      "/api/projects/p/datasets/d/preview?page=2&page_size=20&version_id=v&split=train",
    );
    expect(fetcher.mock.calls[0][1].signal).toBe(controller.signal);
    expect(downloadUrl("p", "d", "v", "manifest")).toBe(
      "/api/projects/p/datasets/d/versions/v/download?artifact=manifest",
    );
  });
  it("surfaces actionable import size errors without reporting success", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { detail: "Import exceeds the 20 MiB total file size limit." },
            { status: 413 },
          ),
        ),
    );
    await expect(
      importDataset(
        "p",
        {
          name: "x",
          language: "bn",
          source: "x",
          licenseNote: "x",
          permission: "unknown",
        },
        [],
      ),
    ).rejects.toThrow("20 MiB");
  });
});
