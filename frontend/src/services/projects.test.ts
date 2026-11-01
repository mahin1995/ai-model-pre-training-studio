import { afterEach, describe, expect, it, vi } from "vitest";
import { newProject } from "../types/project";
import { listProjects, loadProject, saveProject } from "./projects";
afterEach(() => vi.unstubAllGlobals());
describe("PostgreSQL project API adapter", () => {
  it("lists and restores server projects", async () => {
    const project = { ...newProject(), revision: 1 };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(Response.json([project]))
      .mockResolvedValueOnce(Response.json(project));
    vi.stubGlobal("fetch", fetcher);
    expect(await listProjects()).toEqual([project]);
    expect(await loadProject(project.id)).toEqual(project);
    expect(fetcher.mock.calls[1][0]).toBe(`/api/projects/${project.id}`);
  });
  it("creates drafts with POST and updates saved revisions with PATCH", async () => {
    const project = newProject();
    const saved = {
      ...project,
      revision: 1,
      updatedAt: "2026-11-01T00:00:00Z",
    };
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(Response.json(saved))
      .mockResolvedValueOnce(Response.json({ ...saved, revision: 2 }));
    vi.stubGlobal("fetch", fetcher);
    expect(await saveProject(project)).toEqual(saved);
    await saveProject(saved);
    expect(fetcher.mock.calls[0][1].method).toBe("POST");
    expect(fetcher.mock.calls[1][1].method).toBe("PATCH");
    expect(JSON.parse(fetcher.mock.calls[1][1].body).revision).toBe(1);
  });
  it("preserves server conflict and unavailable-database errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json(
            { detail: "Project changed in another tab." },
            { status: 409 },
          ),
        )
        .mockResolvedValueOnce(
          Response.json(
            { detail: "PostgreSQL is unavailable." },
            { status: 503 },
          ),
        ),
    );
    await expect(saveProject(newProject())).rejects.toThrow(
      "Project changed in another tab.",
    );
    await expect(listProjects()).rejects.toThrow("PostgreSQL is unavailable.");
  });
  it("explains backend connection errors and validation locations", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockRejectedValueOnce(new TypeError("Network error"))
        .mockResolvedValueOnce(
          Response.json(
            {
              detail: [
                {
                  loc: ["body", "budget", "maxHours"],
                  msg: "Must be greater than zero",
                },
              ],
            },
            { status: 422 },
          ),
        ),
    );
    await expect(listProjects()).rejects.toThrow(
      "Cannot reach the Python server",
    );
    await expect(saveProject(newProject())).rejects.toThrow("budget.maxHours");
  });
  it("rejects invalid values and incomplete scope before issuing a request", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const p = newProject();
    p.budget.maxHours = -1;
    await expect(saveProject(p)).rejects.toThrow("Fix the highlighted values");
    p.budget.maxHours = null;
    p.status = "scope-ready";
    await expect(saveProject(p)).rejects.toThrow(
      "Complete the readiness checklist",
    );
    expect(fetcher).not.toHaveBeenCalled();
  });
});
