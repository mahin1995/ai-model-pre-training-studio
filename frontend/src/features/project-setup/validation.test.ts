import { describe, expect, it } from "vitest";
import { newProject, type Project } from "../../types/project";
import { readiness, validate } from "./validation";
function completeProject(): Project {
  const p = newProject();
  return {
    ...p,
    name: "Bangla Mini",
    task: "chatbot" as const,
    language: "bn" as const,
    objective: "Learn reproducible training",
    hardware: {
      location: "local" as const,
      status: "entered" as const,
      gpuModel: "Test GPU",
      gpuCount: 1,
      vramPerGpuGb: 24,
      ramGb: 64,
      freeDiskGb: 200,
    },
    budget: { maxHours: 10, maxCost: null, currency: "USD" },
    hasExistingData: false,
    sources: [
      {
        id: "source1",
        name: "Public domain corpus",
        reference: "/corpus",
        language: "bn",
        permissionNote: "Public domain confirmed",
        permission: "confirmed" as const,
      },
    ],
    successCriteria: {
      ...p.successCriteria,
      qualityNotes: "Coherent sentences on fixed prompts",
    },
  };
}
describe("scope readiness", () => {
  it("keeps an empty partial draft valid but not ready", () => {
    const p = newProject();
    expect(validate(p)).toEqual([]);
    expect(readiness(p).percent).toBe(0);
    expect(readiness(p).ready).toBe(false);
  });
  it("allows a local project without monetary budget", () => {
    expect(readiness(completeProject()).ready).toBe(true);
  });
  it("requires a cloud budget, accepting zero", () => {
    const p = completeProject();
    const cloud = {
      ...p,
      hardware: { ...p.hardware, location: "cloud" as const },
    };
    expect(readiness(cloud).ready).toBe(false);
    cloud.budget.maxCost = 0;
    expect(readiness(cloud).ready).toBe(true);
  });
  it("blocks unknown hardware and unconfirmed source permissions", () => {
    const p = completeProject();
    p.hardware.status = "unknown";
    expect(readiness(p).ready).toBe(false);
    p.hardware.status = "entered";
    p.sources[0].permission = "unknown";
    expect(readiness(p).ready).toBe(false);
  });
  it("requires all source metadata and permission notes", () => {
    const p = completeProject();
    p.sources[0].reference = " ";
    expect(readiness(p).checks[3].complete).toBe(false);
  });
  it("rejects negative, nonfinite, and fractional count values", () => {
    const p = completeProject();
    p.hardware.gpuCount = 1.5;
    p.budget.maxHours = -2;
    p.budget.maxCost = -1;
    p.successCriteria.perplexity = NaN;
    expect(validate(p).map((e) => e.field)).toEqual([
      "GPU count",
      "Training hours",
      "Maximum cost",
      "Perplexity",
    ]);
    expect(readiness(p).ready).toBe(false);
  });
});
