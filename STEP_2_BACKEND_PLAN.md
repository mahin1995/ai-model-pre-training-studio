# Step 2 — Python API, PostgreSQL and Environment

User-approved scope: add the backend and Environment screen; use PostgreSQL instead of SQLite for project storage.

## Implementation

- FastAPI with pinned Python dependencies in a repository-local `.venv`.
- PostgreSQL 18, a persistent Docker volume, and versioned transactional SQL migrations.
- Validated project create/list/read/update endpoints using JSONB project documents and indexed timestamps.
- Server-owned revisions with optimistic concurrency checks and server-generated timestamps.
- React project save/load through `/api`, a saved-project selector, and explicit import for old browser drafts.
- Read-only Python/PyTorch/CUDA, NVIDIA driver, memory, disk and training-package checks.
- Environment screen with run/retry, per-check state and actions, host details and package versions.
- Explicit copy of verified hardware into local project drafts; remote cloud hardware is not inferred.
- One-command local development: `python3 scripts/dev.py`.
- A built frontend can also be served from the same Python server as the API.

## Boundaries

This milestone does not install GPU drivers/PyTorch, change the user's training environment, upload datasets, start training, inspect a remote cloud machine, or claim a model will fit in memory. The local workspace does not implement accounts or public hosting.

## Validation

Frontend API/legacy-import/validation unit tests, backend schema and live-PostgreSQL API tests, isolated environment-probe tests, a production build, and desktop/mobile browser checks. Current run results are recorded in `artifacts/STEP_2_VERIFICATION.md` when verification is complete.

## Completion

Implemented and verified. 13 frontend tests and 9 backend tests passed; live PostgreSQL restart persistence, browser flows, production serving and checked accessibility snapshots passed. See `artifacts/STEP_2_VERIFICATION.md` for the exact checks and environment limitations.
