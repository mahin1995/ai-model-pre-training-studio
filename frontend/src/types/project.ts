export type Source = {
  id: string;
  name: string;
  reference: string;
  language: string;
  permissionNote: string;
  permission: "confirmed" | "needs-review" | "unknown";
};
export type Project = {
  id: string;
  name: string;
  description: string;
  task: "completion" | "chatbot" | "domain-assistant" | null;
  language: "bn" | "en" | "mixed" | null;
  objective: string;
  hardware: {
    location: "local" | "cloud" | null;
    status: "unknown" | "entered";
    gpuModel: string;
    gpuCount: number | null;
    vramPerGpuGb: number | null;
    ramGb: number | null;
    freeDiskGb: number | null;
  };
  budget: { maxHours: number | null; maxCost: number | null; currency: string };
  hasExistingData: boolean | null;
  sources: Source[];
  successCriteria: {
    qualityNotes: string;
    heldOutLoss: number | null;
    perplexity: number | null;
    maxLatencyMs: number | null;
    maxMemoryGb: number | null;
  };
  status: "draft" | "scope-ready";
  updatedAt: string;
  revision: number;
};
export const sections = [
  "Basics",
  "Hardware",
  "Budget",
  "Data sources",
  "Success criteria",
  "Review",
] as const;
export function newProject(): Project {
  return {
    id: crypto.randomUUID(),
    name: "",
    description: "",
    task: null,
    language: null,
    objective: "",
    hardware: {
      location: null,
      status: "unknown",
      gpuModel: "",
      gpuCount: null,
      vramPerGpuGb: null,
      ramGb: null,
      freeDiskGb: null,
    },
    budget: { maxHours: null, maxCost: null, currency: "USD" },
    hasExistingData: null,
    sources: [],
    successCriteria: {
      qualityNotes: "",
      heldOutLoss: null,
      perplexity: null,
      maxLatencyMs: null,
      maxMemoryGb: null,
    },
    status: "draft",
    updatedAt: "",
    revision: 0,
  };
}
