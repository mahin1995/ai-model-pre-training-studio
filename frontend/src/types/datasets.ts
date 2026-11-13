export type DatasetMetadata = {
  name: string;
  language: string;
  source: string;
  licenseNote: string;
  permission: "unknown" | "needs-review" | "confirmed";
};
export type ProcessingSettings = {
  normalizeUnicode: boolean;
  normalizeNewlines: boolean;
  trimWhitespace: boolean;
  removeEmpty: boolean;
  stripHtml: boolean;
  collapseWhitespace: boolean;
  deduplicate: boolean;
  grouping: "document" | "source";
  train: number;
  validation: number;
  test: number;
  seed: number;
};
export const defaultProcessing: ProcessingSettings = {
  normalizeUnicode: true,
  normalizeNewlines: true,
  trimWhitespace: true,
  removeEmpty: true,
  stripHtml: false,
  collapseWhitespace: false,
  deduplicate: true,
  grouping: "document",
  train: 90,
  validation: 5,
  test: 5,
  seed: 42,
};
export type DatasetJob = {
  id: string;
  datasetId: string;
  correctionParentVersionId?: string | null;
  status:
    | "queued"
    | "cleaning"
    | "deduplicating"
    | "splitting"
    | "completed"
    | "failed"
    | "cancelled";
  settings: ProcessingSettings;
  progress: number;
  cancelRequested: boolean;
  error: string | null;
  resultVersionId: string | null;
  createdAt: string;
  finishedAt: string | null;
};
export const isActiveJob = (job: DatasetJob | null) =>
  !!job &&
  ["queued", "cleaning", "deduplicating", "splitting"].includes(job.status);
export type SplitArtifact = {
  filename: string;
  recordCount: number;
  groupCount: number;
  actualPercent: number;
  requestedPercent: number;
  sizeBytes: number;
  sha256: string;
};
export type DatasetVersion = {
  id: string;
  version: number;
  createdAt: string;
  manifest: {
    counts: {
      input: number;
      changed: number;
      emptyRemoved: number;
      duplicatesRemoved: number;
      output: number;
      groups: number;
    };
    settings: ProcessingSettings;
    splits: Record<"train" | "validation" | "test", SplitArtifact>;
    note: string;
    parentVersionId?: string;
    correction?: { draftRevision: number; reviewedRecords: number; changedRecords: number };
    artifacts?: Record<string, { filename: string; sha256: string; sizeBytes: number }>;
  };
};

export type CorrectionSummary = { total: number; reviewed: number; changed: number };
export type CorrectionPage = {
  page: number;
  revision: number;
  summary: CorrectionSummary;
  record: { id: string; text: string; provenance: { fileId: string; filename: string; page?: number; line: number }[] };
  text: string;
  reviewed: boolean;
  suggestions: { before: string; after: string; count: number }[];
  cleanedText: string;
  sourceImageUrl: string | null;
  updatedAt: string | null;
};
export type Dataset = {
  id: string;
  projectId: string;
  metadata: DatasetMetadata;
  recordCount: number;
  sizeBytes: number;
  emptyCount: number;
  status: string;
  latestJob: DatasetJob | null;
  versionCount: number;
  createdAt: string;
  updatedAt: string;
};
export type DatasetDetail = Dataset & {
  files: {
    id: string;
    name: string;
    sizeBytes: number;
    recordCount: number;
    sha256: string;
    pageCount?: number;
    skippedPages?: number[];
  }[];
  versions: DatasetVersion[];
};
export type DatasetPreview = {
  page: number;
  pageSize: number;
  total: number;
  records: {
    id: string;
    text: string;
    textTruncated: boolean;
    source: string;
    language: string;
    group_id: string;
    duplicateCount?: number;
    provenanceCount: number;
    provenance: { filename: string; line: number; page?: number; source: string }[];
  }[];
};
