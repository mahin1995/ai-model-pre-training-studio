import { describe, expect, it } from "vitest";
import { newProject } from "../types/project";
import { loadProject } from "./legacy-project";
describe("legacy browser draft import", () => {
  it("reads previous drafts without requiring a server revision or modifying storage", () => {
    const { revision: _revision, ...old } = newProject();
    const restored = loadProject({
      getItem: () => JSON.stringify(old),
      setItem: () => {
        throw new Error("Must not overwrite legacy storage");
      },
    });
    expect(restored?.revision).toBe(0);
  });
  it("keeps missing drafts empty and rejects damaged drafts", () => {
    expect(loadProject({ getItem: () => null, setItem: () => {} })).toBeNull();
    for (const value of [
      "broken",
      "{}",
      "null",
      JSON.stringify({ ...newProject(), sources: [null] }),
    ])
      expect(() =>
        loadProject({ getItem: () => value, setItem: () => {} }),
      ).toThrow();
  });
});
