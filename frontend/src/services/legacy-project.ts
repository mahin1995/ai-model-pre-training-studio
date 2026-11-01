import { newProject, type Project } from "../types/project";
import { readiness, validate } from "../features/project-setup/validation";
const KEY = "pre-training-studio.project.v1";
type StorageAdapter = Pick<Storage, "getItem" | "setItem">;
// Validate every persisted field before restoring it to the UI.
function matches(template: unknown, value: unknown): boolean {
  if (template === null)
    return (
      value === null || (typeof value === "number" && Number.isFinite(value))
    );
  if (Array.isArray(template)) return Array.isArray(value);
  if (typeof template === "object")
    return (
      !!value &&
      typeof value === "object" &&
      Object.entries(template as Record<string, unknown>).every(([key, item]) =>
        matches(item, (value as Record<string, unknown>)[key]),
      )
    );
  return typeof value === typeof template;
}
export function loadProject(storage: StorageAdapter): Project | null {
  const raw = storage.getItem(KEY);
  if (!raw) return null;
  let p: Project;
  try {
    p = JSON.parse(raw) as Project;
  } catch {
    throw new Error(
      "The saved draft is damaged. Start a fresh project; the previous draft will only be replaced when you save.",
    );
  }
  p = { ...p, revision: 0 };
  const template = newProject();
  // Nullable enum fields are validated separately from nullable numeric fields.
  const shape = {
    ...template,
    task: "",
    language: "",
    hasExistingData: false,
    hardware: { ...template.hardware, location: "" },
  };
  const candidate = {
    ...p,
    task: p?.task ?? "",
    language: p?.language ?? "",
    hasExistingData: p?.hasExistingData ?? false,
    hardware: { ...p?.hardware, location: p?.hardware?.location ?? "" },
  };
  const sourceShape = {
    id: "",
    name: "",
    reference: "",
    language: "",
    permissionNote: "",
    permission: "",
  };
  if (
    !matches(shape, candidate) ||
    ![null, "completion", "chatbot", "domain-assistant"].includes(p.task) ||
    ![null, "bn", "en", "mixed"].includes(p.language) ||
    ![null, "local", "cloud"].includes(p.hardware.location) ||
    !["unknown", "entered"].includes(p.hardware.status) ||
    !["draft", "scope-ready"].includes(p.status) ||
    ![null, true, false].includes(p.hasExistingData) ||
    !p.sources.every(
      (s) =>
        matches(sourceShape, s) &&
        ["confirmed", "needs-review", "unknown"].includes(s.permission),
    ) ||
    validate(p).length
  )
    throw new Error(
      "The saved draft could not be read. Start a fresh project; it will only replace the old draft when you save.",
    );
  if (p.status === "scope-ready" && !readiness(p).ready) p.status = "draft";
  return p;
}
