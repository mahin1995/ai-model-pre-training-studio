import type { Project } from "../../types/project";
export type Issue = { section: number; field: string; message: string };
export function validate(p: Project): Issue[] {
  const issues: Issue[] = [];
  const number = (
    value: number | null,
    section: number,
    field: string,
    positive = true,
    integer = false,
  ) => {
    if (
      value !== null &&
      (!Number.isFinite(value) ||
        (positive ? value <= 0 : value < 0) ||
        (integer && !Number.isInteger(value)))
    )
      issues.push({
        section,
        field,
        message: `${field} must be ${positive ? "greater than zero" : "zero or greater"}${integer ? " and a whole number" : ""}.`,
      });
  };
  number(p.hardware.gpuCount, 1, "GPU count", true, true);
  number(p.hardware.vramPerGpuGb, 1, "VRAM");
  number(p.hardware.ramGb, 1, "RAM");
  number(p.hardware.freeDiskGb, 1, "Free disk");
  number(p.budget.maxHours, 2, "Training hours");
  number(p.budget.maxCost, 2, "Maximum cost", false);
  number(p.successCriteria.heldOutLoss, 4, "Held-out loss", false);
  number(p.successCriteria.perplexity, 4, "Perplexity");
  number(p.successCriteria.maxLatencyMs, 4, "Latency");
  number(p.successCriteria.maxMemoryGb, 4, "Memory limit");
  return issues;
}
export function readiness(p: Project) {
  const errors = validate(p);
  const checks = [
    {
      title: "Project scope",
      detail: "Name, task, language and primary objective",
      complete: !!(p.name.trim() && p.task && p.language && p.objective.trim()),
    },
    {
      title: "Hardware recorded",
      detail: "Location, GPU, VRAM, RAM and free disk",
      complete:
        p.hardware.status === "entered" &&
        !!(
          p.hardware.location &&
          p.hardware.gpuModel.trim() &&
          p.hardware.gpuCount &&
          p.hardware.vramPerGpuGb &&
          p.hardware.ramGb &&
          p.hardware.freeDiskGb
        ),
    },
    {
      title: "Budget defined",
      detail: "Time limit and cloud spending limit, if applicable",
      complete:
        p.budget.maxHours !== null &&
        (p.hardware.location !== "cloud" || p.budget.maxCost !== null) &&
        !!p.budget.currency.trim(),
    },
    {
      title: "Data permissions",
      detail: "Data availability and at least one confirmed source",
      complete:
        p.hasExistingData !== null &&
        p.sources.length > 0 &&
        p.sources.every(
          (s) =>
            !!(
              s.name.trim() &&
              s.reference.trim() &&
              s.language.trim() &&
              s.permissionNote.trim()
            ) && s.permission === "confirmed",
        ),
    },
    {
      title: "Success criteria",
      detail: "A concrete description of a successful model",
      complete: !!p.successCriteria.qualityNotes.trim(),
    },
  ].map((check, index) => ({
    ...check,
    complete: check.complete && !errors.some((e) => e.section === index),
  }));
  return {
    checks,
    percent: checks.filter((c) => c.complete).length * 20,
    ready: checks.every((c) => c.complete),
  };
}
