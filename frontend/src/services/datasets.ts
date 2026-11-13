import { request } from "./api";
import type {
  Dataset,
  DatasetDetail,
  DatasetJob,
  DatasetMetadata,
  DatasetPreview,
  ProcessingSettings,
  CorrectionPage,
  CorrectionSummary,
} from "../types/datasets";
const base = (projectId: string) =>
  `/projects/${encodeURIComponent(projectId)}/datasets`;
export const listDatasets = (projectId: string, signal?: AbortSignal) =>
  request<Dataset[]>(base(projectId), { signal });
export const getDataset = (
  projectId: string,
  datasetId: string,
  signal?: AbortSignal,
) => request<DatasetDetail>(`${base(projectId)}/${datasetId}`, { signal });
export function importDataset(
  projectId: string,
  metadata: DatasetMetadata,
  files: File[],
) {
  const form = new FormData();
  form.append("metadata", JSON.stringify(metadata));
  files.forEach((file) => form.append("files", file));
  return request<DatasetDetail>(base(projectId), {
    method: "POST",
    body: form,
  });
}
export const updateDataset = (
  projectId: string,
  datasetId: string,
  metadata: DatasetMetadata,
) =>
  request<DatasetDetail>(`${base(projectId)}/${datasetId}`, {
    method: "PATCH",
    body: JSON.stringify(metadata),
  });
export const deleteDataset = (projectId: string, datasetId: string) =>
  request<{ id: string; deleted: boolean; cleanupWarning: string | null }>(
    `${base(projectId)}/${datasetId}`,
    { method: "DELETE" },
  );
export const startProcessing = (
  projectId: string,
  datasetId: string,
  settings: ProcessingSettings,
) =>
  request<DatasetJob>(`${base(projectId)}/${datasetId}/process`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
export const getJob = (
  projectId: string,
  datasetId: string,
  jobId: string,
  signal?: AbortSignal,
) =>
  request<DatasetJob>(`${base(projectId)}/${datasetId}/jobs/${jobId}`, {
    signal,
  });
export const cancelJob = (
  projectId: string,
  datasetId: string,
  jobId: string,
) =>
  request<DatasetJob>(`${base(projectId)}/${datasetId}/jobs/${jobId}/cancel`, {
    method: "POST",
  });
export const previewDataset = (
  projectId: string,
  datasetId: string,
  page: number,
  versionId: string,
  split: string,
  signal?: AbortSignal,
) =>
  request<DatasetPreview>(
    `${base(projectId)}/${datasetId}/preview?page=${page}&page_size=20${versionId ? `&version_id=${versionId}&split=${split}` : ""}`,
    { signal },
  );
export const downloadUrl = (
  projectId: string,
  datasetId: string,
  versionId: string,
  artifact: string,
) =>
  `/api${base(projectId)}/${datasetId}/versions/${versionId}/download?artifact=${artifact}`;

export const getCorrectionPage = (projectId: string, datasetId: string, versionId: string, page: number, signal?: AbortSignal) =>
  request<CorrectionPage>(`${base(projectId)}/${datasetId}/versions/${versionId}/corrections?page=${page}`, { signal });

export const saveCorrection = (projectId: string, datasetId: string, versionId: string,
  edit: { recordId: string; text: string; reviewed: boolean; revision: number }) =>
  request<{ revision: number; summary: CorrectionSummary; updatedAt: string }>(
    `${base(projectId)}/${datasetId}/versions/${versionId}/corrections`, { method: "PUT", body: JSON.stringify(edit) });

export const publishCorrections = (projectId: string, datasetId: string, versionId: string, revision: number) =>
  request<DatasetJob>(`${base(projectId)}/${datasetId}/versions/${versionId}/corrections/publish`,
    { method: "POST", body: JSON.stringify({ revision }) });
