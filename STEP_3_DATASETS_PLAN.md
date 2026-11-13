# Step 3 — Datasets screen and small text pipeline

Implemented: 2026-11-09 (Asia/Dhaka)

## Approved outcome

A saved project can import UTF-8 TXT/JSONL, preview documents, clean text, remove exact duplicates, and create deterministic train/validation/test splits. PostgreSQL stores metadata, job state and immutable version manifests; raw/processed artifacts stay on local disk. No PyTorch dependency is introduced.

## Delivered checklist

- [x] Project-scoped dataset library, import form and Overview/Preview/Processing/Splits tabs.
- [x] Upload limits: 20 files, 20 MiB total, 10,000 documents, 1 MiB per TXT document/JSONL line; request-body and streamed file limits.
- [x] UTF-8/BOM support, file/line errors, preserved source/language/group metadata, bounded 20-record previews.
- [x] Immutable raw files, generated storage paths and original-file checksums.
- [x] NFC/newline/trim/empty cleaning defaults, optional HTML/whitespace cleanup, exact deduplication and provenance.
- [x] Deterministic seeded splits; explicit groups and duplicate connections stay intact; optional whole-source grouping.
- [x] Permission gate, settings review, asynchronous processing and cancellation/retry.
- [x] Durable PostgreSQL queue, single global worker via advisory lock, heartbeat/expired-lease recovery, staging cleanup.
- [x] Versioned JSONL outputs, manifest/settings/counts/checksums and downloads; prior versions survive failed/cancelled runs.
- [x] Two-second active-job polling with navigation cleanup, reload persistence, mobile layouts and checked accessibility.
- [x] Unit/API/live-worker/browser checks, format examples and screenshots in README.

## Implementation interfaces

Dataset routes are under `/api/projects/{project_id}/datasets`; list/import/detail/preview/process/job-status/cancel/version-download are available. A metadata PATCH endpoint also allows source permission to be confirmed after import; active jobs block metadata edits. Old version metadata stays unchanged.

The PostgreSQL migration adds `datasets`, `dataset_jobs`, `dataset_versions` and a one-active-job-per-dataset index. Existing project documents are not rewritten. Successful artifacts are staged then atomically renamed, and only database-published versions are exposed. The dedicated worker uses a separate connection and globally serializes processing across API processes.

## Remaining boundaries

Large corpora, Hugging Face/web import, near-duplicate detection, tokenizer/model training and automatic sensitive-data scanning remain deferred. Previews support manual source/quality inspection. This milestone prepares data; it does not assess model quality or training readiness.

Verification details: [Step 3 verification](artifacts/STEP_3_VERIFICATION.md).
