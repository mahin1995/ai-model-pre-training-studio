export type EnvironmentReport = {
  checkedAt: string;
  host: string;
  platform: string;
  pythonExecutable: string;
  scope: "backend-host";
  status: "checks-passed" | "needs-attention";
  checks: {
    id: string;
    title: string;
    status: "pass" | "warning" | "blocked" | "error";
    value: string;
    detail: string;
    action: string;
  }[];
  packages: { name: string; version: string | null; required: boolean }[];
  gpus: { name: string; vramGb: number }[];
  driverGpus: { name: string; vramGb: number; driver: string }[];
  memory: { totalGb: number; availableGb: number } | null;
  disk: { path: string; totalGb: number; freeGb: number } | null;
};
