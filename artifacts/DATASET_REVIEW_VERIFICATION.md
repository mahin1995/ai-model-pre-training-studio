# Dataset Review & Correct Verification

Verified: 2026-11-14 (Asia/Dhaka).

## Delivered

- Saved-version review tab with full-record editor, original PDF page images, parent-text comparison and page-local Bangla word suggestions.
- Explicit whitespace/NFC cleanup preserving Bangla ZWJ/ZWNJ and paragraphs. Manual editing supports labeled table rows and complete clause references.
- PostgreSQL drafts with optimistic revisions, save/reload persistence, review flags, unsaved-navigation protection and active-job locks.
- Immutable queued snapshots published through the existing worker. Parent/raw files, record IDs, provenance and split membership remain intact. Invalid parent checksums or cross-split identical corrected text prevent publication.
- Audited corrected versions with JSONL splits, manifest, before/after report, source-separated/page-ordered documents and continuous training-only text.
- Migration `003_dataset_corrections.sql`; existing migrations and version artifacts are unchanged.

## Automated checks

Final results: **52 backend tests passed, 22 frontend tests passed**, and the production frontend build passed. The backend emits an existing Starlette/httpx deprecation warning; no test failures remain.

Backend coverage includes revision conflicts, Unicode/size validation, project isolation, source rendering, all-record review gates, publication/reload, snapshot isolation, checksum failures, cancellation/retry, parent preservation, derived checksums and draft cleanup on deletion.

Frontend coverage includes version/revision API payloads, whole-word suggestion acceptance and paragraph/joiner-preserving cleanup. Production TypeScript/Vite build passes.

Run from the repository root:

```bash
.venv/bin/python -m pytest -q --tb=short
npm test --prefix frontend
npm run build --prefix frontend
```

## Browser checks

Headless local Chrome exercised the built UI against a dedicated temporary PostgreSQL database with a generated three-page PDF; the QA database/server were removed afterward. Verified suggestion acceptance, blocked navigation while unsaved, saved-draft recovery after refresh, review gating, publication of Version 2, unchanged Version 1, corrected downloads, no horizontal overflow at 390px and no JavaScript page errors.

- [Desktop review](dataset-review-desktop.png)
- [Corrected version downloads](dataset-corrected-version-desktop.png)
- [Mobile review](dataset-review-mobile.png)

The fixture verifies the workflow, not the factual accuracy of aviation content or automatic recovery of arbitrary PDF fonts. The user's uploaded corpus remains unchanged until its pages are reviewed and a corrected version is explicitly published.
