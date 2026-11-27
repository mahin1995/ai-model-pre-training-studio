export type RunKind = "tokenizers" | "sequence-runs";
export type SplitName = "train" | "validation" | "test";
export type SourceVersion = { datasetId: string; datasetName: string; versionId: string; version: number; trainingRecords: number; reviewedRecords: number; eligible: boolean; reason: string | null };
export type SequenceCounts = { documents: number; sequences: number; contentTokens: number; boundaryTokens: number; paddedTokens: number; paddingRatio: number };
export type PreparationManifest = {
  artifacts: Record<string, { filename: string; sizeBytes: number; sha256: string }>;
  actualVocabSize?: number; requestedVocabSize?: number; trainingDocuments?: number; trainingBytes?: number;
  trainingTokens?: number; trainingSeconds?: number; specialIds?: Record<string, number>;
  counts?: Record<SplitName, SequenceCounts>; contentTokens?: number; sequenceLength?: number; warnings?: string[];
  objective?: "sft"; templateVersion?: string; labelsPolicy?: string; tokenizerSha256?: string;
};
export type PreparationRun = {
  id: string; projectId: string; datasetId: string; datasetVersionId: string; datasetVersion: number; datasetName: string;
  tokenizerRunId: string | null; status: string; settings: { vocabSize?: number; sequenceLength?: number };
  cancelRequested: boolean; error: string | null; manifest: PreparationManifest | null; createdAt: string; elapsedSeconds: number;
};
export const activeRun = (run: PreparationRun) => ["queued", "validating", "training", "encoding", "packing", "verifying"].includes(run.status);
export type EncodingPreview = { tokenCount: number; tokenPage: number; pageSize: number;
  tokens: { index: number; id: number; piece: string; offset: [number, number] }[];
  decodedText: string; roundTripMatches: boolean; bytesPerToken: number };
export type SequenceRecord = { input_ids: number[]; attention_mask: number[]; labels: number[];
  documentId: string; filename: string; recordIds: string[]; pages: (number | null)[]; split: SplitName;
  ordinal: number; tokenRange: [number, number]; decodedText: string };
export type SequencePreview = { records: SequenceRecord[]; total: number; page: number; pageSize: number };
