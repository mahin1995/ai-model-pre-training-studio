# Step 3 verification — Datasets

Verified on 2026-11-09 (Asia/Dhaka).

## Automated checks

- `npm run build --prefix frontend`: TypeScript and production build passed.
- `npm test --prefix frontend`: **17 tests passed**, including multipart boundary handling, project/version-scoped preview/download URLs, processing requests and upload errors.
- `.venv/bin/python -m pytest -q`: **28 tests passed** against isolated real PostgreSQL databases and temporary dataset directories.
- Backend coverage includes UTF-8/BOM and Bangla preservation, invalid JSON/types/encoding, exact limits, chunked multipart limits, raw preservation, HTML cleanup, duplicate provenance, transitive group connections, identical-content leakage prevention with deduplication on/off, source grouping, deterministic seeded outputs, empty/too-small datasets and ratio validation.
- API/worker checks include project isolation, source permission updates/gating, active-job conflicts, queued/running cancellation, immutable versions, checksum downloads, expired-lease/staging recovery, failed-run preservation, fresh-app artifact restoration and global single-worker serialization across two workers.
- One upstream Starlette test-client deprecation warning about HTTPX remains; tests pass.

## Real browser flow

Headless local Chrome with temporary Playwright/Axe tooling, 1440×1100 desktop and 390×844 mobile.

A dedicated PostgreSQL browser-QA database and separate temporary storage directory were used. The user's project database and training data were not used for browser fixtures.

Verified:

- Saved-project requirement and creation of a project before dataset import.
- Mixed TXT/JSONL upload with Bangla text, UTF-8 BOM, optional source/language/group fields, duplicate and empty records.
- Raw preview pagination at 20 records per page; processed preview after version completion.
- Unconfirmed permission blocking processing, then permission confirmation via metadata save.
- Invalid split ratios blocking submission, explicit settings review, background processing and completion polling.
- 28 raw documents became 26 prepared documents: one empty text and one exact duplicate removed.
- Manifest download matched prepared counts; version persisted after a browser reload.
- Invalid JSON import displayed the filename/line error while keeping the form editable.
- Active job polling stopped after navigating away from Datasets.
- No uncaught browser errors; checked mobile layouts had no horizontal overflow.
- Axe WCAG A/AA checks reported no violations in the checked desktop import/processing/splits and mobile overview/splits snapshots. This is bounded automated coverage, not an exhaustive accessibility audit.

## Screenshots

- [Dataset library](datasets-library-desktop.png)
- [Import form](datasets-import-desktop.png)
- [Raw preview](datasets-preview-desktop.png)
- [Processing review](datasets-processing-desktop.png)
- [Prepared splits](datasets-splits-desktop.png)
- [Mobile overview](datasets-overview-mobile.png)
- [Mobile splits](datasets-splits-mobile.png)

## Boundaries

Only the lightweight `python-multipart` dependency was added. No PyTorch/CUDA setup or training run occurred. Full-corpus processing, remote imports, near-deduplication and automatic sensitive-data detection remain deferred. Temporary browser-QA services and their dedicated database/files are removed at teardown.
